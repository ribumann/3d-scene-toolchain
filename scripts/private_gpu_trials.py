"""Opt-in sequential generated-input trials; never modify frozen pilot checkpoints."""

import argparse
import fcntl
import json
import os
import shutil
import signal
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

from scene_pipeline.models import Asset, Case, Scene
from scripts.package_pilots import APPROVED_PINS
from scripts.private_gpu_batch import digest, private_path, snapshot_extraction, write_json
from scripts.private_gpu_smoke import SDK_REVISION, SmokeError, run_stage, validate_generation
from scripts.trial_contracts import TRIAL_IDS, VARIANTS, fingerprint, load_manifest

SETTINGS = {
    "model_pins": APPROVED_PINS, "sdk_revision": SDK_REVISION, "count": 32768,
    "steps": 50, "seed": 42, "attention_backend": "sdpa", "compile": "0",
    "crop_policy": "rgba-min32-alpha256-v1",
}
ERRORS = (OSError, ValueError, KeyError, TypeError)


def source_path(directory, trial):
    source = private_path(directory, f"approved-trials/{trial.source.filename}")
    if digest(source) != trial.source.sha256:
        raise SmokeError("trial_source_checksum_mismatch")
    with Image.open(source) as image:
        if image.format != "PNG" or image.width * image.height > 20_000_000:
            raise SmokeError("invalid_trial_source")
        image.verify()
    return source


def extract_trial(directory, output, manifest, case_id, variant):
    from scene_pipeline.extract import extract_photo

    trial = next(item for item in load_manifest(manifest).trials if item.id == case_id)
    source = source_path(directory, trial)
    reviewed = trial.reviewed_objects if variant == "optimized" else []
    case = Case(id=trial.id, title=trial.title, input_type="generated", summary="Synthetic photographic-scene trial; inferred layout.")
    scene, report = extract_photo(
        case, {"preview_path": str(source), "filename": trial.source.filename, "sha256": trial.source.sha256},
        output, max_objects=None, caption=". ".join(trial.detector_phrases) + ".",
        reviewed_boxes=[list(item.box) for item in reviewed] if reviewed else None,
        reviewed_labels=[item.category for item in reviewed] if reviewed else None,
    )
    report["supervision"] = "manual-reviewed-boxes" if reviewed else "detector-proposals"
    if reviewed:
        for node, annotation, item in zip(scene.nodes, report["annotations"], reviewed):
            annotation.update(reviewed_id=item.id, identity=item.identity, reusable_asset_id=item.reusable_asset_id)
    write_json(output / "scene.json", scene.model_dump())
    write_json(output / "extraction.json", report)


def box_iou(left, right):
    x, y = max(left[0], right[0]), max(left[1], right[1])
    right_edge = min(left[0] + left[2], right[0] + right[2])
    bottom = min(left[1] + left[3], right[1] + right[3])
    intersection = max(0, right_edge - x) * max(0, bottom - y)
    return intersection / (left[2] * left[3] + right[2] * right[3] - intersection)


def same_mask(left, right):
    # Compare in source coordinates, not resized crop space.
    a, b = left["bbox_pixels"], right["bbox_pixels"]
    if box_iou(a, b) < .95:
        return False
    width = max(a[0] + a[2], b[0] + b[2]) - min(a[0], b[0])
    height = max(a[1] + a[3], b[1] + b[3]) - min(a[1], b[1])
    masks = []
    for candidate in (left, right):
        x, y, w, h = candidate["bbox_pixels"]
        with Image.open(candidate["path"]) as image:
            alpha = np.asarray(image.getchannel("A")) > 0
        canvas = np.zeros((height, width), dtype=bool)
        dx, dy = x - min(a[0], b[0]), y - min(a[1], b[1])
        canvas[dy:dy + h, dx:dx + w] = alpha
        masks.append(canvas)
    union = np.count_nonzero(masks[0] | masks[1])
    return bool(union and np.count_nonzero(masks[0] & masks[1]) / union >= .98)


def crop_plan(scene, extraction, folder, trial, variant):
    nodes = {node.id: node for node in scene.nodes}
    annotations = {item["node_id"]: item for item in extraction["annotations"]}
    if len(annotations) != len(extraction["annotations"]) or set(annotations) != set(nodes):
        raise SmokeError("invalid_trial_annotations")
    candidates, rejected = [], []
    for node in scene.nodes:
        item = annotations[node.id]
        reason = None
        if node.category not in trial.detector_phrases or not node.visible:
            reason = "unapproved_non_person_category"
        elif item.get("crop") != f"{node.id}.png":
            reason = "invalid_crop_reference"
        else:
            crop = private_path(folder, item["crop"])
            with Image.open(crop) as image:
                image.load()
                if image.mode != "RGBA" or min(image.size) < 32 or list(image.size) != item["bbox_pixels"][2:]:
                    reason = "degenerate_or_tiny_crop"
                else:
                    histogram = image.getchannel("A").histogram()
                    if sum(histogram[1:]) < 256 or histogram[0] == 0:
                        reason = "empty_or_unsegmented_alpha"
            if not reason:
                candidate = {**item, "path": crop, "crop_sha256": digest(crop), "category": node.category}
                if variant == "optimized":
                    duplicate = next((
                        previous for previous in candidates
                        if candidate.get("identity") and candidate.get("identity") == previous.get("identity")
                        and same_mask(candidate, previous)
                    ), None)
                    if duplicate:
                        rejected.append({"node_id": node.id, "reason": "duplicate_reviewed_identity_and_mask", "duplicate_of": duplicate["node_id"]})
                        continue
                candidates.append(candidate)
        if reason:
            rejected.append({"node_id": node.id, "reason": reason})
    return candidates, rejected


def generation_key(crop_sha256):
    return fingerprint({"crop_sha256": crop_sha256, "settings": SETTINGS})


def checked_result(folder, crop, receipt=None):
    metadata = validate_generation(folder, crop)
    hashes = {name: digest(folder / name) for name in ("generation.json", "object.ply")}
    if receipt is not None and receipt != hashes:
        raise SmokeError("trial_cached_output_changed")
    return metadata, hashes


def cache_result(directory, candidate, cache_enabled):
    key = generation_key(candidate["crop_sha256"])
    cache = private_path(directory, f"trials/cache/{key}")
    if cache_enabled and cache.exists():
        receipt = json.loads((cache / "receipt.json").read_text())
        if receipt["key"] != key:
            raise SmokeError("trial_cache_key_mismatch")
        checked_result(cache, candidate["path"], receipt["files"])
        return cache, key
    return None, key


def save_cache(directory, key, result, candidate):
    cache = private_path(directory, f"trials/cache/{key}")
    if cache.exists():
        receipt = json.loads((cache / "receipt.json").read_text())
        if receipt["key"] != key:
            raise SmokeError("trial_cache_key_mismatch")
        checked_result(cache, candidate["path"], receipt["files"])
        return
    cache.mkdir(parents=True)
    for name in ("generation.json", "object.ply"):
        shutil.copyfile(result / name, cache / name)
    _, hashes = checked_result(cache, candidate["path"])
    write_json(cache / "receipt.json", {"key": key, "files": hashes})


def assemble(trial, variant, extracted, candidates, successes):
    scene = extracted.model_copy(deep=True)
    scene.id = scene.case_id = f"{trial.id}-{variant}"
    scene.description = "Synthetic photographic-scene trial. Appearance generated; layout/scale/depth are inferred, not metric."
    nodes = {node.id: node for node in extracted.nodes}
    scene.nodes, scene.assets, scene.edges = [], [], []
    for candidate in candidates:
        identifier = candidate["node_id"]
        if identifier not in successes:
            continue
        result = successes[identifier]
        placements = [
            item for item in trial.instances
            if variant == "optimized" and item.object_id == candidate.get("reviewed_id")
        ]
        for placement in placements or [None]:
            node = nodes[identifier].model_copy(deep=True)
            if placement:
                node.id = placement.id
                node.position, node.rotation, node.size = placement.position, placement.rotation, placement.size
                node.evidence.note += " Explicit authored relative instance, not an independent reconstruction."
            node.asset_id = f"idol-{node.id}"
            scene.nodes.append(node)
            scene.assets.append(Asset(
                id=node.asset_id, kind="ply", node_id=node.id,
                uri=f"/api/assets/trials/{trial.id}/{variant}/{identifier}.ply",
                sha256=result["metadata"]["sha256"],
                provenance={
                    **result["metadata"], "trial_id": trial.id, "variant": variant,
                    "parent_node_id": identifier, "crop_sha256": candidate["crop_sha256"],
                    "source_sha256": trial.source.sha256, "bbox_pixels": candidate["bbox_pixels"],
                    "cache_key": result["cache_key"], "reused": result["reused"],
                    "reusable_asset_id": candidate.get("reusable_asset_id"),
                    "instance": placement is not None, "layout": trial.layout_kind,
                },
            ))
    return Scene.model_validate(scene.model_dump())


def run_trial(directory, manifest_path, trial, variant):
    started = time.monotonic()
    output = private_path(directory, f"trials/{trial.id}/{variant}")
    output.mkdir(parents=True, exist_ok=True)
    state = None
    report = {
        "trial_id": trial.id, "variant": variant, "status": "running", "failure_reason": None,
        "expected_objects": sum(item.count for item in trial.expected_inventory),
        "detected_objects": 0, "usable_crops": 0, "rejected": [], "objects": [],
        "cache_hits": 0, "cache_misses": 0, "resumed": 0, "independent_generations": 0,
        "settings": SETTINGS, "source_sha256": trial.source.sha256,
        "supervision": "manual-reviewed-boxes" if variant == "optimized" and trial.reviewed_objects else "detector-proposals",
    }
    with (output / ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SmokeError("trial_already_running") from None
        try:
            if {name: os.environ.get(name) for name in APPROVED_PINS} != APPROVED_PINS:
                raise SmokeError("trial_requires_frozen_model_pins")
            if os.environ.get("ATTN_BACKEND", "sdpa") != "sdpa" or os.environ.get("SCENE_IDOL_COMPILE", "0") != "0":
                raise SmokeError("trial_requires_comparable_settings")
            if not os.environ.get("HF_TOKEN"):
                raise SmokeError("trial_HF_TOKEN_missing")
            source_path(directory, trial)
            contract = {"trial": trial.model_dump(mode="json"), "variant": variant, "settings": SETTINGS}
            checkpoint = output / "trial.json"
            state = json.loads(checkpoint.read_text()) if checkpoint.exists() else {
                "contract": contract, "extraction": None, "objects": {}, "extraction_attempts": [],
            }
            if state["contract"] != contract:
                state = None
                raise SmokeError("trial_manifest_or_settings_resume_mismatch")
            state.update(status="running", scene=None)
            write_json(checkpoint, state)
            receipt = state["extraction"]
            if receipt is None:
                folder = output / f"extraction-{len(state['extraction_attempts']):03d}"
                folder.mkdir()
                attempt = {"directory": folder.name, "timing": {}, "source_revision": os.environ.get("SCENE_SOURCE_REVISION", "local-unversioned")}
                state["extraction_attempts"].append(attempt)
                write_json(checkpoint, state)
                run_stage([
                    "/home/scene/scene-vision-venv/bin/python", "-m", "scripts.private_gpu_trials",
                    "extract", "--data-dir", str(directory), "--manifest", str(manifest_path),
                    "--cases", trial.id, "--variants", variant, "--output", str(folder),
                ], output / f"{folder.name}-private.log", 1200, attempt["timing"])
                state["extraction"] = {"directory": folder.name, "files": snapshot_extraction(folder)}
                write_json(checkpoint, state)
            else:
                folder = private_path(output, receipt["directory"])
                if snapshot_extraction(folder) != receipt["files"]:
                    raise SmokeError("trial_extraction_changed")
            extracted = Scene.model_validate_json((folder / "scene.json").read_text())
            extraction = json.loads((folder / "extraction.json").read_text())
            if extracted.case_id != trial.id or not any(source.sha256 == trial.source.sha256 for source in extracted.sources):
                raise SmokeError("trial_extraction_source_mismatch")
            expected_method = "reviewed-boxes+sam2" if variant == "optimized" and trial.reviewed_objects else "grounding-dino+sam2"
            if extraction.get("method") != expected_method or extraction.get("detector") != {
                "model": "IDEA-Research/grounding-dino-tiny", "revision": APPROVED_PINS["SCENE_DETECTOR_REVISION"],
            } or extraction.get("segmenter") != {
                "model": "facebook/sam2.1-hiera-small", "revision": APPROVED_PINS["SCENE_SEGMENTER_REVISION"],
            }:
                raise SmokeError("trial_extraction_method_or_pins_mismatch")
            candidates, report["rejected"] = crop_plan(extracted, extraction, folder, trial, variant)
            report.update(detected_objects=len(extracted.nodes), usable_crops=len(candidates))
            successes = {}
            for candidate in candidates:
                identifier = candidate["node_id"]
                record = {"node_id": identifier, "status": "running", "timing": {}}
                report["objects"].append(record)
                entry = state["objects"].setdefault(identifier, {"attempts": []})
                try:
                    previous = entry["attempts"][-1] if entry["attempts"] else None
                    result = None
                    if previous and previous["status"] in ("running", "interrupted", "succeeded"):
                        result = private_path(directory, previous["directory"])
                        try:
                            metadata, hashes = checked_result(result, candidate["path"], previous.get("files"))
                            report["resumed"] += 1
                            record["status"] = "resumed"
                        except (SmokeError, *ERRORS):
                            previous.update(status="failed", failure_reason="trial_resume_revalidation_failed")
                            record["resume_rejected"] = previous["failure_reason"]
                            result = None
                    if result is None:
                        result, key = cache_result(directory, candidate, variant == "optimized")
                        if result is not None:
                            report["cache_hits"] += 1
                            record["status"] = "cache_hit"
                        else:
                            report["cache_misses"] += 1
                            result = output / f"objects/{identifier}/attempt-{len(entry['attempts']):03d}"
                            result.mkdir(parents=True)
                            attempt = {
                                "directory": result.relative_to(directory).as_posix(), "status": "running",
                                "source_revision": os.environ.get("SCENE_SOURCE_REVISION", "local-unversioned"),
                                "timing": record["timing"],
                            }
                            entry["attempts"].append(attempt)
                            write_json(checkpoint, state)
                            run_stage([
                                sys.executable, "-m", "scene_pipeline.idol_worker", "--image", str(candidate["path"]),
                                "--out", str(result), "--mode", "real", "--count", "32768",
                            ], result / "idol-private.log", 3600, record["timing"])
                            record["status"] = "succeeded"
                            report["independent_generations"] += 1
                        metadata, hashes = checked_result(result, candidate["path"])
                        save_cache(directory, key, result, candidate)
                        if record["status"] == "cache_hit":
                            entry["attempts"].append({
                                "directory": result.relative_to(directory).as_posix(), "status": "succeeded",
                                "reused": True, "files": hashes,
                                "source_revision": os.environ.get("SCENE_SOURCE_REVISION", "local-unversioned"),
                            })
                    entry["attempts"][-1].update(status="succeeded", files=hashes)
                    save_cache(directory, generation_key(candidate["crop_sha256"]), result, candidate)
                    successes[identifier] = {
                        "directory": result.relative_to(directory).as_posix(), "metadata": metadata,
                        "cache_key": generation_key(candidate["crop_sha256"]),
                        "reused": record["status"] in ("cache_hit", "resumed"),
                    }
                except (SmokeError, *ERRORS) as error:
                    record.update(status="failed", failure_reason=str(error) if isinstance(error, SmokeError) else "trial_object_runtime_or_validation_failed")
                    if entry["attempts"] and entry["attempts"][-1]["status"] == "running":
                        entry["attempts"][-1].update(status="failed", failure_reason=record["failure_reason"])
                write_json(checkpoint, state)
            state["successes"] = successes
            report.update(objects_succeeded=len(successes), objects_failed=len(candidates) - len(successes))
            if successes:
                scene = assemble(trial, variant, extracted, candidates, successes)
                write_json(output / "scene.json", scene.model_dump())
                state["scene"] = "scene.json"
                report["published_instances"] = len(scene.nodes)
            report["status"] = "succeeded" if candidates and len(successes) == len(candidates) else "partial" if successes else "failed"
            if report["status"] != "succeeded":
                report["failure_reason"] = "trial_objects_failed_or_no_usable_crops"
        except (KeyboardInterrupt, SystemExit):
            report.update(status="interrupted", failure_reason="trial_interrupted_resume_required")
        except (SmokeError, *ERRORS) as error:
            report.update(status="failed", failure_reason=str(error) if isinstance(error, SmokeError) else "trial_input_output_or_checkpoint_invalid")
        finally:
            report["seconds_this_run"] = round(time.monotonic() - started, 3)
            if state is not None:
                state["status"] = report["status"]
                state["report"] = report
                write_json(output / "trial.json", state)
            write_json(output / "safe-status.json", report)
    print(json.dumps(report), flush=True)
    return report


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "extract"))
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", choices=TRIAL_IDS, required=True)
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    trials = {item.id: item for item in manifest.trials}
    if len(set(args.cases)) != len(args.cases) or len(set(args.variants)) != len(args.variants) or any(case not in trials for case in args.cases):
        parser.error("Select unique manifested trials and variants")
    if args.command == "extract":
        if len(args.cases) != 1 or len(args.variants) != 1 or args.output is None:
            parser.error("Extraction requires one case/variant and output")
        extract_trial(args.data_dir, args.output, args.manifest, args.cases[0], args.variants[0])
        return 0
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(128 + signum))
    failed = False
    for case in args.cases:
        for variant in args.variants:
            report = run_trial(args.data_dir, args.manifest, trials[case], variant)
            if report["status"] == "interrupted":
                return 1
            failed |= report["status"] != "succeeded"
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
