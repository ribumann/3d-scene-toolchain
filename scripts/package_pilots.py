"""Explicit approval boundary: revalidate private pilot results, export public-only assets."""

import argparse
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

from scene_pipeline.gaussians import validate_ply
from scene_pipeline.models import Scene
from scripts.private_gpu_batch import (
    assemble_scene, digest, make_plan, private_path, snapshot_extraction, validated_attempt, write_json,
)
from scripts.private_gpu_smoke import PILOT_IDS, PIN_NAMES, ROOT, SDK_REVISION, SmokeError, validate_extraction
from scripts.resolve_smoke_models import I02_BATCH_REVISIONS

PIN_OUTPUTS = ("idol_revision", "dinov3_revision", "flux2_revision", "detector_revision", "segmenter_revision")
APPROVED_PINS = dict(zip(PIN_NAMES, (I02_BATCH_REVISIONS[key] for key in PIN_OUTPUTS)))
PUBLIC_STATUSES = {"not_run", "processing", "failed", "partial", "succeeded", "proposals"}
DIAGRAM_IDS = {"I01", "I04", "I05"}
ENTRY_KEYS = {
    "case_id", "status", "objects", "failed_objects", "rejected_objects", "reference_origin",
    "input_kind", "not_original_bytes", "reference_sha256", "layout", "scene", "source_revisions",
}


def source_revisions(state):
    attempts = list(state.get("extraction_attempts", []))
    for entry in state.get("objects", {}).values():
        attempts.extend(entry["attempts"])
    return sorted({
        attempt["source_revision"] for attempt in attempts
        if re.fullmatch(r"[a-f0-9]{40}|local-unversioned", attempt.get("source_revision", ""))
    })


@contextmanager
def pinned_environment():
    previous = {name: os.environ.get(name) for name in PIN_NAMES}
    os.environ.update(APPROVED_PINS)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def public_ply(source, destination):
    validate_ply(source)
    # Rebuild the header so model-written comments cannot carry private paths.
    with source.open("rb") as stream:
        header = []
        while True:
            line = stream.readline()
            if line.startswith((b"ply\n", b"format ", b"element vertex ", b"property ")):
                header.append(line)
            if line.strip() == b"end_header":
                break
        payload = stream.read()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"".join(header) + b"end_header\n" + payload)
    return validate_ply(destination)


@contextmanager
def locked_checkpoint(directory, case, incremental):
    try:
        import fcntl
    except ImportError:
        raise SmokeError("private_publication_export_requires_posix_flock") from None
    output = private_path(directory, f"assets/{case}/object-batch-public-preview")
    checkpoint = private_path(output, "batch.json")
    if not output.exists() or (incremental and not checkpoint.exists()):
        yield output, None
        return
    with private_path(output, ".lock").open("rb") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if incremental:
                yield output, {"status": "processing"}
                return
            raise SmokeError("cannot_package_running_case") from None
        state = json.loads(checkpoint.read_text())
        if state.get("status") == "running":
            if incremental:
                yield output, {"status": "processing"}
                return
            raise SmokeError("publication_requires_stopped_case_checkpoint")
        yield output, state


def checked_scene(directory, output, case, source, state):
    contract = state["contract"]
    provenance = contract.get("input_provenance", {})
    if (
        contract["case_id"] != case or contract["source_kind"] != "user-approved-public-webp-preview"
        or contract["source_sha256"] != digest(source) or contract["preview_sha256"] != digest(source)
        or provenance.get("sha256") != digest(source) or provenance.get("not_original_bytes") is not True
        or contract["model_pins"] != APPROVED_PINS or contract["sdk_revision"] != SDK_REVISION
        or contract["count"] != 32768 or contract["steps"] != 50 or contract["seed"] != 42
        or contract["attention_backend"] != "sdpa" or contract["idol_compile"] != "0"
    ):
        raise SmokeError("publication_source_pins_or_settings_mismatch")
    receipt = state.get("extraction")
    if receipt is None:
        return None, {"case_id": case, "status": "failed", "objects": 0, "failed_objects": 0}
    folder = private_path(output, receipt["directory"])
    if snapshot_extraction(folder) != receipt["files"]:
        raise SmokeError("publication_extraction_changed")
    scene = Scene.model_validate_json((folder / "scene.json").read_text())
    extraction = json.loads((folder / "extraction.json").read_text())
    validate_extraction(scene, extraction, contract["source_sha256"], case)
    if case in DIAGRAM_IDS:
        if contract["mode"] != "diagram-proposals" or not scene.nodes or scene.assets or scene.edges:
            raise SmokeError("invalid_public_diagram_proposals")
        return scene, {
            "case_id": case, "status": "proposals", "objects": len(scene.nodes),
            "failed_objects": 0, "source_revisions": source_revisions(state),
        }
    if contract["mode"] != "real":
        raise SmokeError("invalid_public_appearance_mode")
    plan, rejected = make_plan(scene, extraction, folder)
    if plan != state["plan"] or rejected != state["rejected"]:
        raise SmokeError("publication_parent_crop_mapping_changed")
    validated = {}
    for group in plan:
        attempts = state["objects"].get(group["node_id"], {}).get("attempts", [])
        if not attempts or attempts[-1]["status"] != "succeeded":
            continue
        crop = private_path(folder, group["parents"][0]["crop"])
        validated[group["node_id"]] = validated_attempt(output, crop, dict(attempts[-1]))
    count = len(validated)
    result_status = "succeeded" if count and count == len(plan) else "partial" if count else "failed"
    summary = {
        "case_id": case, "status": result_status,
        "objects": sum(len(group["parents"]) for group in plan if group["node_id"] in validated),
        "failed_objects": len(plan) - count, "rejected_objects": len(rejected),
        "source_revisions": source_revisions(state),
    }
    if not validated:
        return None, summary
    assembled = assemble_scene(scene, plan, validated, contract["source_sha256"], directory / "assets", provenance)
    return assembled, summary


def export_case(directory, destination, manifest, scene, summary):
    case = summary["case_id"]
    entry = {
        **summary, "reference_origin": "ai-generated" if case.startswith("G") else "user-supplied-original",
        "input_kind": "user-approved-public-webp-preview", "not_original_bytes": True,
        "reference_sha256": digest(ROOT / f"apps/web/public/references/{case}.webp"),
        "layout": "inferred-not-metric", "scene": None,
    }
    if scene is not None:
        scene.name = next(item["title"] for item in json.loads((ROOT / "cases/manifest.json").read_text()) if item["id"] == case)
        scene.description = (
            "Unreviewed OCR/contour region proposals. Assumed height/scale; no recovered topology or Idol appearance."
            if case in DIAGRAM_IDS else
            "Validated generated object appearances only. Incomplete scene coverage; inferred placement/scale/depth, not metric truth."
        )
        for item in scene.sources:
            item.filename = f"{case}.webp"
        for asset in scene.assets:
            source = private_path(directory / "assets", asset.uri.removeprefix("/api/assets/"))
            if digest(source) != asset.sha256:
                raise SmokeError("publication_ply_changed")
            relative = f"assets/{case}/{asset.node_id}.ply"
            validated = public_ply(source, destination / relative)
            asset.sha256 = validated["sha256"]
            asset.uri = f"/api/assets/pilot/{case}/{asset.node_id}.ply"
            original = asset.provenance
            asset.provenance = {
                **validated, "model": "speridlabs/idol", "mode": "real", "steps": 50, "seed": 42,
                "model_revision": APPROVED_PINS["SCENE_IDOL_MODEL_REVISION"], "sdk_revision": SDK_REVISION,
                "parent_node_id": asset.node_id, "crop_sha256": original["crop_sha256"],
                "source_sha256": entry["reference_sha256"], "bbox_pixels": original["bbox_pixels"],
                "duplicate_of": original["duplicate_of"], "layout": "inferred-not-metric",
                "input_kind": entry["input_kind"], "not_original_bytes": True,
            }
            manifest["files"][relative] = validated["sha256"]
        scene = Scene.model_validate(scene.model_dump())
        entry["scene"] = f"scenes/{case}.json"
        (destination / "scenes").mkdir(exist_ok=True)
        write_json(destination / entry["scene"], scene.model_dump())
        manifest["files"][entry["scene"]] = digest(destination / entry["scene"])
    manifest["cases"].append(entry)


def package_pilots(directory, destination, approve=False, incremental=False):
    if not approve:
        raise SmokeError("explicit_derived_publication_approval_required")
    if destination.exists() or destination.is_symlink():
        raise SmokeError("publication_destination_must_be_new")
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 1, "approved_derived_publication": True, "cases": [], "files": {}}
    with tempfile.TemporaryDirectory(prefix=destination.name + "-", dir=destination.parent) as temporary, pinned_environment():
        staging = Path(temporary)
        for case in PILOT_IDS:
            source = ROOT / f"apps/web/public/references/{case}.webp"
            with locked_checkpoint(directory, case, incremental) as (output, state):
                if state is None or state.get("status") == "processing":
                    scene, summary = None, {
                        "case_id": case, "status": "processing" if state else "not_run",
                        "objects": 0, "failed_objects": 0,
                    }
                else:
                    scene, summary = checked_scene(directory, output, case, source, state)
                export_case(directory, staging, manifest, scene, summary)
        write_json(staging / "pilots.json", manifest)
        validate_package(staging)
        staging.rename(destination)
    return manifest


def validate_package(directory):
    if directory.is_symlink():
        raise SmokeError("unsafe_public_package")
    manifest = json.loads(private_path(directory, "pilots.json").read_text())
    if manifest.get("schema_version") != 1 or manifest.get("approved_derived_publication") is not True:
        raise SmokeError("unapproved_public_package")
    if set(manifest) != {"schema_version", "approved_derived_publication", "cases", "files"}:
        raise SmokeError("unexpected_public_manifest_fields")
    cases = manifest["cases"]
    if [case["case_id"] for case in cases] != list(PILOT_IDS):
        raise SmokeError("public_package_case_allowlist_mismatch")
    allowed = {"pilots.json"}
    for entry in cases:
        case = entry["case_id"]
        if set(entry) - ENTRY_KEYS:
            raise SmokeError("unexpected_public_case_fields")
        if not isinstance(entry.get("source_revisions", []), list) or any(
            not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{40}|local-unversioned", revision)
            for revision in entry.get("source_revisions", [])
        ):
            raise SmokeError("invalid_public_source_revisions")
        if entry["reference_origin"] != ("ai-generated" if case.startswith("G") else "user-supplied-original") or entry["layout"] != "inferred-not-metric":
            raise SmokeError("public_package_reference_origin_mismatch")
        if any(not isinstance(entry[field], int) or entry[field] < 0 for field in ("objects", "failed_objects")):
            raise SmokeError("public_package_invalid_counts")
        if entry["status"] not in PUBLIC_STATUSES or entry["reference_sha256"] != digest(ROOT / f"apps/web/public/references/{case}.webp"):
            raise SmokeError("public_package_status_or_reference_mismatch")
        if entry["not_original_bytes"] is not True or entry["input_kind"] != "user-approved-public-webp-preview":
            raise SmokeError("public_package_provenance_mismatch")
        if entry["scene"] is None:
            if entry["status"] not in ("not_run", "processing", "failed") or entry["objects"] != 0:
                raise SmokeError("public_package_missing_scene")
            continue
        if entry["scene"] != f"scenes/{case}.json":
            raise SmokeError("unsafe_public_scene_path")
        allowed.add(entry["scene"])
        scene = Scene.model_validate_json(private_path(directory, entry["scene"]).read_text())
        if scene.case_id != case or not scene.nodes or len(scene.nodes) != entry["objects"]:
            raise SmokeError("public_package_scene_identity_mismatch")
        if any(source.filename != f"{case}.webp" or source.sha256 != entry["reference_sha256"] for source in scene.sources):
            raise SmokeError("public_package_source_mismatch")
        if case in DIAGRAM_IDS:
            if entry["status"] != "proposals" or scene.assets or scene.edges:
                raise SmokeError("invalid_public_diagram_scene")
        else:
            if entry["status"] not in ("partial", "succeeded") or any(node.asset_id is None for node in scene.nodes):
                raise SmokeError("public_appearance_requires_validated_assets")
        for asset in scene.assets:
            relative = f"assets/{case}/{asset.node_id}.ply"
            if asset.kind != "ply" or asset.uri != f"/api/assets/pilot/{case}/{asset.node_id}.ply":
                raise SmokeError("unsafe_public_asset_path")
            allowed.add(relative)
            validated = validate_ply(private_path(directory, relative))
            if validated["gaussian_count"] != 32768 or validated["sha256"] != asset.sha256:
                raise SmokeError("invalid_public_ply")
    actual = set()
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise SmokeError("unsafe_public_package_symlink")
        if path.is_file():
            actual.add(path.relative_to(directory).as_posix())
    if actual != allowed or set(manifest["files"]) != allowed - {"pilots.json"}:
        raise SmokeError("unexpected_public_package_files")
    for relative, checksum in manifest["files"].items():
        if not re.fullmatch(r"[a-f0-9]{64}", checksum) or digest(private_path(directory, relative)) != checksum:
            raise SmokeError("public_package_checksum_mismatch")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--approve-derived-publication", action="store_true")
    parser.add_argument("--incremental", action="store_true", help="Skip active cases as processing; export stopped results only.")
    args = parser.parse_args()
    package_pilots(args.data_dir, args.out, args.approve_derived_publication, args.incremental)


if __name__ == "__main__":
    main()
