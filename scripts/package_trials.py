"""Publish only approved generated trial references and validated derived outputs."""

import argparse
import json
import math
import re
import shutil
import tempfile
from pathlib import Path

from scene_pipeline.gaussians import validate_ply
from scene_pipeline.models import Scene
from scripts.package_pilots import pinned_environment, public_ply
from scripts.private_gpu_batch import digest, private_path, snapshot_extraction, write_json
from scripts.private_gpu_smoke import ROOT, SmokeError
from scripts.private_gpu_trials import SETTINGS, assemble, checked_result, crop_plan, generation_key, source_path
from scripts.trial_contracts import VARIANTS, TrialManifest, load_manifest

APPROVED_MANIFEST = ROOT / "cases/trials.json"
STATUSES = {"not_run", "processing", "failed", "partial", "succeeded", "interrupted"}
SUMMARY_FIELDS = {
    "trial_id", "variant", "status", "failure_reason", "expected_objects", "detected_objects",
    "usable_crops", "rejected", "objects", "cache_hits", "cache_misses", "resumed",
    "independent_generations", "settings", "source_sha256", "supervision", "seconds_this_run",
    "objects_succeeded", "objects_failed", "published_instances",
}


def safe_report(report):
    required = SUMMARY_FIELDS - {"objects_succeeded", "objects_failed", "published_instances"}
    if not required <= set(report) <= SUMMARY_FIELDS or report["status"] not in STATUSES:
        raise SmokeError("invalid_trial_public_report")
    if report["trial_id"] not in ("T01", "T02", "T03") or report["variant"] not in VARIANTS or report["supervision"] not in ("manual-reviewed-boxes", "detector-proposals"):
        raise SmokeError("invalid_trial_public_report")
    for field in ("expected_objects", "detected_objects", "usable_crops", "cache_hits", "cache_misses", "resumed", "independent_generations", "objects_succeeded", "objects_failed", "published_instances"):
        if field in report and (type(report[field]) is not int or not 0 <= report[field] <= 10000):
            raise SmokeError("unsafe_trial_count")
    if type(report["seconds_this_run"]) not in (int, float) or not math.isfinite(report["seconds_this_run"]) or report["seconds_this_run"] < 0:
        raise SmokeError("unsafe_trial_measurement")
    for record in report.get("objects", []) + report.get("rejected", []):
        if set(record) - {"node_id", "status", "timing", "failure_reason", "reason", "duplicate_of", "resume_rejected"}:
            raise SmokeError("unexpected_trial_object_report")
        for field in ("failure_reason", "reason", "resume_rejected", "node_id", "duplicate_of"):
            if field in record and not re.fullmatch(r"[a-zA-Z0-9_.-]{1,120}", record[field]):
                raise SmokeError("unsafe_trial_failure_diagnostic")
        if "status" in record and record["status"] not in ("running", "succeeded", "failed", "resumed", "cache_hit"):
            raise SmokeError("unsafe_trial_object_status")
        if "timing" in record and (
            set(record["timing"]) - {"seconds", "peak_device_memory_mib_sampled", "sample_interval_seconds"}
            or any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in record["timing"].values())
        ):
            raise SmokeError("unsafe_trial_measurement")
    if report.get("failure_reason") is not None and not re.fullmatch(r"[a-zA-Z0-9_.-]{1,120}", report["failure_reason"]):
        raise SmokeError("unsafe_trial_failure_diagnostic")
    return report


def package_trials(directory, destination, manifest_path=APPROVED_MANIFEST, approve=False):
    try:
        import fcntl
    except ImportError:
        raise SmokeError("trial_export_requires_POSIX_flock") from None

    if not approve:
        raise SmokeError("explicit_trial_publication_approval_required")
    approved = load_manifest(manifest_path)
    if destination.exists() or destination.is_symlink():
        raise SmokeError("trial_publication_destination_must_be_new")
    destination.parent.mkdir(parents=True, exist_ok=True)
    package = {"schema_version": 1, "approved_generated_trial_publication": True, "trials": [], "files": {}}
    with tempfile.TemporaryDirectory(prefix=destination.name + "-", dir=destination.parent) as temporary, pinned_environment():
        staging = Path(temporary)
        write_json(staging / "trial-manifest.json", approved.model_dump(mode="json"))
        package["files"]["trial-manifest.json"] = digest(staging / "trial-manifest.json")
        for trial in approved.trials:
            source = source_path(directory, trial)
            reference = f"references/{trial.id}.png"
            (staging / "references").mkdir(exist_ok=True)
            shutil.copyfile(source, staging / reference)
            package["files"][reference] = digest(staging / reference)
            for variant in VARIANTS:
                entry = {"trial_id": trial.id, "variant": variant, "status": "not_run", "scene": None, "report": None}
                package["trials"].append(entry)
                output = private_path(directory, f"trials/{trial.id}/{variant}")
                checkpoint = private_path(output, "trial.json")
                if not checkpoint.exists():
                    continue
                with private_path(output, ".lock").open("rb") as lock:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        entry["status"] = "processing"
                        continue
                    state = json.loads(checkpoint.read_text())
                    if state["status"] == "running":
                        entry["status"] = "processing"
                        continue
                    if state["contract"] != {"trial": trial.model_dump(mode="json"), "variant": variant, "settings": SETTINGS}:
                        raise SmokeError("trial_publication_contract_mismatch")
                    entry.update(status=state["status"], report=safe_report(state["report"]))
                    if not state.get("scene"):
                        continue
                    receipt = state["extraction"]
                    folder = private_path(output, receipt["directory"])
                    if snapshot_extraction(folder) != receipt["files"]:
                        raise SmokeError("trial_publication_extraction_changed")
                    extracted = Scene.model_validate_json((folder / "scene.json").read_text())
                    extraction = json.loads((folder / "extraction.json").read_text())
                    candidates, rejected = crop_plan(extracted, extraction, folder, trial, variant)
                    if rejected != entry["report"]["rejected"]:
                        raise SmokeError("trial_publication_plan_changed")
                    successes = state["successes"]
                    for candidate in candidates:
                        identifier = candidate["node_id"]
                        if identifier not in successes:
                            continue
                        result = successes[identifier]
                        generated = private_path(directory, result["directory"])
                        attempt = state["objects"][identifier]["attempts"][-1]
                        metadata, _ = checked_result(generated, candidate["path"], attempt["files"])
                        if metadata != result["metadata"]:
                            raise SmokeError("trial_publication_generation_changed")
                    scene = assemble(trial, variant, extracted, candidates, successes)
                    for asset in scene.assets:
                        parent = asset.provenance["parent_node_id"]
                        relative = f"assets/{trial.id}/{variant}/{parent}.ply"
                        validated = public_ply(private_path(directory, successes[parent]["directory"]) / "object.ply", staging / relative)
                        asset.sha256 = validated["sha256"]
                        provenance = asset.provenance
                        asset.provenance = {
                            **validated, "model": "speridlabs/idol", "mode": "real",
                            "steps": 50, "seed": 42, "model_pins": SETTINGS["model_pins"],
                            "sdk_revision": SETTINGS["sdk_revision"],
                            **{key: provenance[key] for key in (
                                "trial_id", "variant", "parent_node_id", "crop_sha256", "source_sha256",
                                "bbox_pixels", "cache_key", "reused", "reusable_asset_id", "instance", "layout",
                            )},
                        }
                        package["files"][relative] = validated["sha256"]
                    entry["scene"] = f"scenes/{trial.id}-{variant}.json"
                    (staging / "scenes").mkdir(exist_ok=True)
                    write_json(staging / entry["scene"], scene.model_dump())
                    package["files"][entry["scene"]] = digest(staging / entry["scene"])
        write_json(staging / "trials.json", package)
        validate_trial_package(staging, manifest_path)
        staging.rename(destination)
    return package


def validate_trial_package(directory, manifest_path=None):
    approved = load_manifest(manifest_path or APPROVED_MANIFEST)
    manifest = TrialManifest.model_validate_json(private_path(directory, "trial-manifest.json").read_text())
    if manifest != approved or directory.is_symlink():
        raise SmokeError("unapproved_trial_manifest")
    package = json.loads(private_path(directory, "trials.json").read_text())
    if set(package) != {"schema_version", "approved_generated_trial_publication", "trials", "files"} or package["schema_version"] != 1 or package["approved_generated_trial_publication"] is not True:
        raise SmokeError("unapproved_trial_package")
    if [(item["trial_id"], item["variant"]) for item in package["trials"]] != [
        (trial.id, variant) for trial in approved.trials for variant in VARIANTS
    ]:
        raise SmokeError("trial_package_inventory_mismatch")
    allowed = {"trials.json", "trial-manifest.json"}
    for trial in approved.trials:
        relative = f"references/{trial.id}.png"
        if digest(private_path(directory, relative)) != trial.source.sha256:
            raise SmokeError("trial_reference_hash_mismatch")
        allowed.add(relative)
    for entry in package["trials"]:
        case, variant = entry["trial_id"], entry["variant"]
        trial = next(item for item in approved.trials if item.id == case)
        if set(entry) != {"trial_id", "variant", "status", "scene", "report"} or entry["status"] not in STATUSES:
            raise SmokeError("unsafe_trial_entry")
        if (entry["report"] is None) != (entry["status"] in ("not_run", "processing")):
            raise SmokeError("invalid_trial_report_status")
        if entry["report"] is not None:
            report = safe_report(entry["report"])
            if (report["settings"] != SETTINGS or report["source_sha256"] != trial.source.sha256
                or report["status"] != entry["status"] or report["trial_id"] != case or report["variant"] != variant
                or report["expected_objects"] != sum(item.count for item in trial.expected_inventory)):
                raise SmokeError("invalid_trial_report_provenance")
        if entry["scene"] is None:
            if entry["status"] in ("succeeded", "partial"):
                raise SmokeError("completed_trial_scene_missing")
            continue
        if entry["status"] not in ("succeeded", "partial") or entry["scene"] != f"scenes/{case}-{variant}.json":
            raise SmokeError("invalid_trial_scene_status")
        allowed.add(entry["scene"])
        scene = Scene.model_validate_json(private_path(directory, entry["scene"]).read_text())
        if (scene.case_id != f"{case}-{variant}" or not scene.nodes or scene.edges
            or len(scene.assets) != len(scene.nodes) or any(not node.asset_id for node in scene.nodes)
            or len(scene.nodes) != report.get("published_instances")):
            raise SmokeError("invalid_trial_scene_identity")
        if not scene.sources or any(source.filename != trial.source.filename or source.sha256 != trial.source.sha256 for source in scene.sources):
            raise SmokeError("invalid_trial_scene_source")
        for asset in scene.assets:
            parent = asset.provenance["parent_node_id"]
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", parent):
                raise SmokeError("unsafe_trial_asset")
            relative = f"assets/{case}/{variant}/{parent}.ply"
            if asset.kind != "ply" or asset.uri != f"/api/assets/trials/{case}/{variant}/{parent}.ply":
                raise SmokeError("unsafe_trial_asset")
            validated = validate_ply(private_path(directory, relative))
            if validated["gaussian_count"] != 32768 or asset.sha256 != validated["sha256"]:
                raise SmokeError("invalid_trial_gaussians")
            provenance = asset.provenance
            expected_fields = {
                *validated, "model", "mode", "steps", "seed", "model_pins", "sdk_revision",
                "trial_id", "variant", "parent_node_id", "crop_sha256", "source_sha256",
                "bbox_pixels", "cache_key", "reused", "reusable_asset_id", "instance", "layout",
            }
            if (set(provenance) != expected_fields
                or any(provenance[key] != value for key, value in validated.items())
                or provenance["trial_id"] != case or provenance["variant"] != variant
                or provenance["source_sha256"] != trial.source.sha256
                or provenance["model_pins"] != SETTINGS["model_pins"]
                or provenance["sdk_revision"] != SETTINGS["sdk_revision"]
                or provenance["model"] != "speridlabs/idol" or provenance["mode"] != "real"
                or provenance["steps"] != 50 or provenance["seed"] != 42
                or not re.fullmatch(r"[a-f0-9]{64}", provenance["crop_sha256"])
                or provenance["cache_key"] != generation_key(provenance["crop_sha256"])
                or provenance["layout"] != trial.layout_kind
                or type(provenance["reused"]) is not bool or type(provenance["instance"]) is not bool
                or len(provenance["bbox_pixels"]) != 4
                or any(type(value) is not int or value < 0 for value in provenance["bbox_pixels"])
                or provenance["reusable_asset_id"] not in {None, *(item.reusable_asset_id for item in trial.reviewed_objects)}):
                raise SmokeError("invalid_trial_asset_provenance")
            allowed.add(relative)
        if len({asset.provenance["parent_node_id"] for asset in scene.assets}) != report.get("objects_succeeded"):
            raise SmokeError("invalid_trial_success_count")
    actual = set()
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise SmokeError("unsafe_trial_package_symlink")
        if path.is_file():
            actual.add(path.relative_to(directory).as_posix())
    if actual != allowed or set(package["files"]) != allowed - {"trials.json"}:
        raise SmokeError("unexpected_trial_package_files")
    for name, checksum in package["files"].items():
        if not re.fullmatch(r"[a-f0-9]{64}", checksum) or digest(private_path(directory, name)) != checksum:
            raise SmokeError("trial_package_file_changed")
    return package, approved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=APPROVED_MANIFEST)
    parser.add_argument("--approve-generated-trial-publication", action="store_true")
    args = parser.parse_args()
    package_trials(args.data_dir, args.out, args.manifest, args.approve_generated_trial_publication)


if __name__ == "__main__":
    main()
