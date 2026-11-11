"""Private, resumable I02 object reconstruction; no uploads or scene publication."""

import argparse
import hashlib
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from scene_pipeline.models import Asset, Scene
from scripts.private_gpu_smoke import (
    PIN_NAMES, ROOT, SDK_REVISION, SmokeError, enumerate_crops, load_source,
    run_stage, validate_extraction, validate_generation,
)

VALIDATION_ERRORS = (OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.TimeoutExpired)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    if path.is_symlink() or temporary.is_symlink():
        raise SmokeError("unsafe_checkpoint_symlink")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def private_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(part in (".", "..") for part in path.parts):
        raise SmokeError("unsafe_checkpoint_path")
    result = root
    for part in path.parts:
        result = result / part
        if result.is_symlink():
            raise SmokeError("unsafe_checkpoint_symlink")
    if not result.resolve().is_relative_to(root.resolve()):
        raise SmokeError("unsafe_checkpoint_path")
    return result


def make_plan(scene, extraction, folder):
    candidates, rejected = enumerate_crops(scene, extraction, folder)
    groups = {}
    for candidate in candidates:
        parent = {key: value for key, value in candidate.items() if key != "path"}
        parent["crop"] = candidate["path"].name
        groups.setdefault(candidate["crop_sha256"], []).append(parent)
    return [
        {"node_id": parents[0]["node_id"], "crop_sha256": checksum, "parents": parents}
        for checksum, parents in groups.items()
    ], rejected


def snapshot_extraction(folder):
    files = {}
    for path in sorted(folder.iterdir()):
        if path.is_symlink() or not path.is_file():
            raise SmokeError("unsafe_extraction_artifact")
        files[path.name] = digest(path)
    return files


def extraction_for(directory, output, state, report, public_preview=None):
    receipt = state.get("extraction")
    if receipt is None:
        attempts = state.setdefault("extraction_attempts", [])
        attempt = {"directory": f"extractions/attempt-{len(attempts):03d}", "status": "running", "timing": {}}
        attempts.append(attempt)
        write_json(output / "batch.json", state)
        destination = private_path(output, attempt["directory"])
        destination.mkdir(parents=True)
        arguments = [
            "/home/scene/scene-vision-venv/bin/python", str(ROOT / "scripts/private_gpu_smoke.py"),
            "extract", "--all-objects", "--data-dir", str(directory), "--output", str(destination),
        ]
        if public_preview is not None:
            arguments += ["--public-preview", str(public_preview)]
        run_stage(
            arguments,
            destination / "extract-private.log", 1200, attempt["timing"],
        )
        folder = destination / "extraction"
    else:
        folder = private_path(output, receipt["directory"])
        if snapshot_extraction(folder) != receipt["files"]:
            raise SmokeError("cached_extraction_changed")
    scene = Scene.model_validate_json((folder / "scene.json").read_text())
    extraction = json.loads((folder / "extraction.json").read_text())
    validate_extraction(scene, extraction, state["contract"]["source_sha256"])
    plan, rejected = make_plan(scene, extraction, folder)
    if receipt is None:
        state["extraction"] = {"directory": str(folder.relative_to(output)), "files": snapshot_extraction(folder)}
        state["plan"], state["rejected"] = plan, rejected
        attempt["status"] = "succeeded"
        write_json(output / "batch.json", state)
    elif plan != state["plan"] or rejected != state["rejected"]:
        raise SmokeError("cached_extraction_plan_changed")
    report["objects_detected"] = len(scene.nodes)
    report["usable_distinct_crops"] = len(plan)
    report["rejected"] = [{key: item[key] for key in ("node_id", "reason")} for item in rejected]
    return scene, folder, plan


def validated_attempt(output, crop, attempt):
    folder = private_path(output, attempt["directory"])
    metadata = validate_generation(folder, crop)
    if attempt.get("generation_sha256") not in (None, digest(folder / "generation.json")):
        raise SmokeError("cached_generation_changed")
    if attempt.get("ply_sha256") not in (None, metadata["sha256"]):
        raise SmokeError("cached_ply_changed")
    attempt.update(
        status="succeeded", failure_reason=None,
        generation_sha256=digest(folder / "generation.json"), ply_sha256=metadata["sha256"],
    )
    return {"directory": folder, "metadata": metadata}


def assemble_scene(scene, plan, validated, source_sha256, asset_root, input_provenance=None):
    assembled = scene.model_copy(deep=True)
    assembled.nodes, assembled.assets = [], []
    assembled.description += (
        " Private object batch: only validated successful appearances are included. "
        "Image-plane placement/depth/scale remain inferred, not metric truth or a complete plant."
    )
    nodes = {node.id: node for node in scene.nodes}
    for group in plan:
        result = validated.get(group["node_id"])
        if result is None:
            continue
        for parent in group["parents"]:
            node = nodes[parent["node_id"]].model_copy(deep=True)
            node.asset_id = f"idol-{node.id}"
            node.evidence.note += (
                " Appearance generated by Idol; detector confidence is not reconstruction accuracy. "
                "Position, depth and scale remain provisional and unreviewed."
            )
            node.evidence.reviewed = False
            assembled.nodes.append(node)
            assembled.assets.append(Asset(
                id=node.asset_id, kind="ply", node_id=node.id,
                uri="/api/assets/" + (result["directory"] / "object.ply").relative_to(asset_root).as_posix(),
                sha256=result["metadata"]["sha256"],
                provenance={
                    **result["metadata"], "parent_node_id": node.id, "source_sha256": source_sha256,
                    "crop_sha256": parent["crop_sha256"], "crop": parent["crop"],
                    "bbox_pixels": parent["bbox_pixels"], "duplicate_of": group["node_id"] if node.id != group["node_id"] else None,
                    "layout": "inferred-image-plane-not-metric",
                    **({"input_provenance": input_provenance} if input_provenance else {}),
                },
            ))
    included = {node.id for node in assembled.nodes}
    assembled.edges = [edge for edge in scene.edges if edge.source in included and edge.target in included]
    return Scene.model_validate(assembled.model_dump())


def checkpoint_scene(directory, output, state, scene, plan, validated):
    state["scene_path"] = None
    if validated:
        assembled = assemble_scene(
            scene, plan, validated, state["contract"]["source_sha256"], directory / "assets",
            state["contract"].get("input_provenance"),
        )
        revision = state.get("assembly_revision", 0) + 1
        folder = private_path(output, "scenes")
        folder.mkdir(exist_ok=True)
        filename = f"scenes/scene-{revision:06d}.json"
        assembled.revision = revision
        write_json(output / filename, assembled.model_dump())
        state.update(scene_path=filename, assembly_revision=revision)
    write_json(output / "batch.json", state)


def reconstruct_objects(directory, output, state, report, scene, folder, plan):
    validated = {}
    report["objects"] = []
    # Validate all reusable results before assembling or starting another model.
    for group in plan:
        identifier = group["node_id"]
        record = {
            "node_id": identifier, "category": group["parents"][0]["category"],
            "parent_nodes": [parent["node_id"] for parent in group["parents"]], "status": "pending",
        }
        report["objects"].append(record)
        entry = state.setdefault("objects", {}).setdefault(identifier, {"attempts": []})
        if entry["attempts"] and entry["attempts"][-1]["status"] in ("succeeded", "running", "interrupted"):
            attempt = entry["attempts"][-1]
            try:
                crop = private_path(folder, group["parents"][0]["crop"])
                validated[identifier] = validated_attempt(output, crop, attempt)
                record["status"] = "resumed"
                record["timing"] = attempt.get("timing", {})
            except (SmokeError, *VALIDATION_ERRORS):
                attempt.update(status="failed", failure_reason="cached_output_failed_revalidation")
                record["resume_rejected"] = "cached_output_failed_revalidation"
    checkpoint_scene(directory, output, state, scene, plan, validated)
    if not plan:
        raise SmokeError("no_valid_non_person_segmented_crop")
    for group, record in zip(plan, report["objects"]):
        identifier = group["node_id"]
        if identifier in validated:
            continue
        entry = state["objects"][identifier]
        attempt = {
            "directory": f"objects/{identifier}/attempt-{len(entry['attempts']):03d}",
            "status": "running", "timing": {},
        }
        entry["attempts"].append(attempt)
        record["status"] = "running"
        write_json(output / "batch.json", state)
        write_json(output / "safe-status.json", report)
        destination = private_path(output, attempt["directory"])
        destination.mkdir(parents=True)
        crop = private_path(folder, group["parents"][0]["crop"])
        try:
            if digest(crop) != group["crop_sha256"]:
                raise SmokeError("crop_changed_before_inference")
            run_stage(
                [sys.executable, "-m", "scene_pipeline.idol_worker", "--image", str(crop),
                 "--out", str(destination), "--mode", "real", "--count", "32768"],
                destination / "idol-private.log", 3600, attempt["timing"],
            )
            validated[identifier] = validated_attempt(output, crop, attempt)
            record["status"] = "succeeded"
        except SmokeError as error:
            attempt.update(status="failed", failure_reason=str(error))
            record.update(status="failed", failure_reason=str(error))
        except VALIDATION_ERRORS:
            attempt.update(status="failed", failure_reason="private_object_runtime_or_validation_failed")
            record.update(status="failed", failure_reason=attempt["failure_reason"])
        record["timing"] = attempt["timing"]
        checkpoint_scene(directory, output, state, scene, plan, validated)
        write_json(output / "safe-status.json", report)
    report["objects_succeeded"] = len(validated)
    report["nodes_reconstructed"] = sum(len(group["parents"]) for group in plan if group["node_id"] in validated)
    report["objects_failed"] = len(plan) - len(validated)
    report["status"] = "succeeded" if len(validated) == len(plan) else "partial" if validated else "failed"
    report["failure_reason"] = None if report["status"] == "succeeded" else "one_or_more_objects_failed"


def run_batch(directory, public_preview=None):
    directory = Path(directory).absolute()
    output = directory / ("assets/I02/object-batch-public-preview" if public_preview is not None else "assets/I02/object-batch")
    state, lock = None, None
    started = time.monotonic()
    report = {
        "case_id": "I02", "source_kind": "private-original", "mode": "real",
        "scope": "usable_segmented_objects_not_full_plant", "status": "running",
        "stage": "preflight",
        "gaussian_count_per_object": 32768, "steps": 50, "seed": 42,
        "failure_reason": None,
    }
    try:
        if not os.environ.get("HF_TOKEN"):
            raise SmokeError("HF_TOKEN_missing")
        pins = {name: os.environ.get(name, "") for name in PIN_NAMES}
        if any(not re.fullmatch(r"[0-9a-f]{40}", value) for value in pins.values()):
            raise SmokeError("missing_immutable_model_pin")
        input_provenance = None
        if public_preview is not None:
            public_preview = Path(public_preview).absolute()
            authorized = ROOT / "apps/web/public/references/I02.webp"
            if public_preview.is_symlink() or digest(public_preview) != digest(authorized):
                raise SmokeError("public_preview_does_not_match_authorized_asset")
            source, _ = load_source(directory, public_preview)
            input_provenance = {
                "source_kind": "user-approved-public-webp-preview",
                "sha256": source["sha256"], "bytes": public_preview.stat().st_size,
                "url": "https://red-wave-0c7bb6c0f.4.azurestaticapps.net/references/I02.webp",
                "not_original_bytes": True,
            }
            from PIL import Image
            with Image.open(public_preview) as image:
                input_provenance["dimensions"] = [image.width, image.height]
            report.update(input_provenance)
        else:
            source, _ = load_source(directory)
        contract = {
            "version": 1, "case_id": "I02", "source_kind": "private-original",
            "source_sha256": source["sha256"], "preview_sha256": digest(Path(source["preview_path"])),
            "model_pins": pins, "sdk_revision": SDK_REVISION,
            "mode": "real", "count": 32768, "steps": 50, "seed": 42,
            "attention_backend": os.environ.get("ATTN_BACKEND", "sdpa"),
            "idol_compile": os.environ.get("SCENE_IDOL_COMPILE", "0"),
            "crop_contract": "approved-non-person-rgba-min32-alpha256-v1",
            "detector_max_objects": None,
        }
        if input_provenance is not None:
            contract.update(source_kind=input_provenance["source_kind"], input_provenance=input_provenance)
        if directory.is_symlink():
            raise SmokeError("unsafe_private_data_root")
        private_path(directory, "assets/I02/object-batch")
        output.mkdir(parents=True, exist_ok=True, mode=0o700)
        import fcntl
        lock = private_path(output, ".lock").open("a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SmokeError("private_batch_already_running") from None
        manifest = private_path(output, "batch.json")
        if manifest.exists():
            previous = json.loads(manifest.read_text())
            if previous.get("contract") != contract:
                raise SmokeError("batch_source_pins_or_settings_mismatch")
            state = previous
        else:
            if any(path.name != ".lock" for path in output.iterdir()):
                raise SmokeError("unrecognized_batch_output")
            state = {"contract": contract, "extraction": None, "objects": {}, "scene_path": None}
        state.update(status="running", failure_reason=None, scene_path=None)
        write_json(manifest, state)
        report["stage"] = "extraction"
        write_json(output / "safe-status.json", report)
        scene, folder, plan = extraction_for(directory, output, state, report, public_preview)
        report["stage"] = "objects"
        reconstruct_objects(directory, output, state, report, scene, folder, plan)
        report["stage"] = "complete"
    except SmokeError as error:
        report.update(status="failed", failure_reason=str(error))
    except (KeyboardInterrupt, SystemExit):
        report.update(status="interrupted", failure_reason="interrupted_resume_required")
        if state is not None:
            for entry in state["objects"].values():
                if entry["attempts"] and entry["attempts"][-1]["status"] == "running":
                    entry["attempts"][-1].update(status="interrupted", failure_reason="interrupted_resume_required")
            for record in report.get("objects", []):
                if record["status"] == "running":
                    record["status"] = "interrupted"
    except VALIDATION_ERRORS:
        report.update(status="failed", failure_reason="private_batch_input_output_or_checkpoint_invalid")
    finally:
        if report["status"] == "running":
            report.update(status="failed", failure_reason="private_batch_not_completed")
        report["seconds_this_run"] = round(time.monotonic() - started, 3)
        if state is not None:
            for attempt in state.get("extraction_attempts", []):
                if attempt["status"] == "running":
                    attempt.update(status=report["status"], failure_reason=report["failure_reason"])
            for entry in state["objects"].values():
                if entry["attempts"] and entry["attempts"][-1]["status"] == "running":
                    entry["attempts"][-1].update(status="failed", failure_reason=report["failure_reason"])
            state["status"] = report["status"]
            state["failure_reason"] = report["failure_reason"]
            write_json(output / "batch.json", state)
            write_json(output / "safe-status.json", report)
        if lock is not None:
            lock.close()
        print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "succeeded" else 1


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--public-preview", type=Path, help="Explicit authorized I02 WebP input, never original bytes.")
    args = parser.parse_args()
    def interrupt(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, interrupt)
    return run_batch(args.data_dir, args.public_preview)


if __name__ == "__main__":
    raise SystemExit(main())
