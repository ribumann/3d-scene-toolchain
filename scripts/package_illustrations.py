"""Strict additive publication of reviewed, generated illustrative appearances."""

import argparse
import json
import math
import re
from pathlib import Path

from scene_pipeline.gaussians import validate_ply
from scene_pipeline.models import Scene
from scripts.generated_references import CASES, Manifest, validate_reference_receipt
from scripts.illustration_reconstruct import Reviews
from scripts.illustration_scenes import illustration_scene
from scripts.package_pilots import APPROVED_PINS, public_ply
from scripts.private_gpu_batch import digest, private_path, write_json
from scripts.private_gpu_smoke import SDK_REVISION

ROOT = Path(__file__).resolve().parents[1]


def validate_appearances(appearances, root):
    concepts = {item.id: item for item in Manifest.model_validate_json((ROOT / "cases/illustrations.json").read_text()).concepts}
    reviews = {item.id: item for item in Reviews.model_validate_json((ROOT / "cases/illustration-reviews.json").read_text()).objects}
    if set(appearances) != set(reviews):
        raise ValueError("Illustrative publication must match the exact reviewed concept set")
    for identifier, metadata in appearances.items():
        allowed = {
            "sha256", "gaussian_count", "bounds", "coordinates", "model", "input_sha256",
            "model_revision", "sdk_revision", "mode", "seed", "steps", "dinov3_dtype",
            "encoder_revisions", "reference", "review", "segmentation", "crop_sha256",
            "illustrative", "resumed", "timing_this_run", "generation_sha256",
        }
        if set(metadata) - allowed:
            raise ValueError("Unexpected illustrative public metadata")
        ply = private_path(root, f"assets/{identifier}.ply")
        validated = validate_ply(ply)
        if any(metadata.get(key) != value for key, value in validated.items()):
            raise ValueError("Illustrative PLY differs from generation metadata")
        if any(metadata.get(key) != value for key, value in {
            "model": "speridlabs/idol", "mode": "real", "steps": 50, "seed": 42,
            "gaussian_count": 32768, "sdk_revision": SDK_REVISION,
            "model_revision": APPROVED_PINS["SCENE_IDOL_MODEL_REVISION"], "illustrative": True,
            "segmentation": "reviewed-box+SAM2",
        }.items()) or metadata.get("encoder_revisions") != {
            key: APPROVED_PINS[key] for key in ("SCENE_DINOV3_REVISION", "SCENE_FLUX2_REVISION")
        }:
            raise ValueError("Illustrative generation model/settings differ")
        validate_reference_receipt(metadata["reference"], concepts[identifier])
        if metadata["review"] != reviews[identifier].model_dump(mode="json") or metadata["reference"]["sha256"] != reviews[identifier].sha256:
            raise ValueError("Generated input does not match the reviewed reference")
        if metadata.get("dinov3_dtype") != "fp32" or type(metadata.get("resumed")) is not bool:
            raise ValueError("Unexpected illustrative encoder dtype or resume state")
        if not re.fullmatch(r"[0-9a-f]{64}", metadata.get("crop_sha256", "")) or metadata["crop_sha256"] != metadata.get("input_sha256"):
            raise ValueError("Illustrative segmentation input hash differs")
        if "generation_sha256" in metadata and not re.fullmatch(r"[0-9a-f]{64}", metadata["generation_sha256"]):
            raise ValueError("Invalid original generation hash")
        timing = metadata["timing_this_run"]
        if timing and (
            set(timing) != {"seconds", "peak_device_memory_mib_sampled", "sample_interval_seconds"}
            or any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in timing.values())
        ):
            raise ValueError("Unexpected illustrative timing metadata")


def validate_illustration_package(root):
    if root.is_symlink():
        raise ValueError("Unsafe illustration publication directory")
    manifest_path = private_path(root, "publication.json")
    manifest = json.loads(manifest_path.read_text())
    if set(manifest) != {"version", "kind", "files", "cases"} or manifest["version"] != 1 or manifest["kind"] != "reviewed-generated-illustrations":
        raise ValueError("Unknown illustration publication")
    reviews = Reviews.model_validate_json((ROOT / "cases/illustration-reviews.json").read_text())
    expected = {"appearances.json"} | {f"assets/{item.id}.ply" for item in reviews.objects} | {f"scenes/{case}-illustrated.json" for case in CASES}
    if set(manifest["files"]) != expected or manifest["cases"] != [f"{case}-illustrated" for case in CASES]:
        raise ValueError("Unexpected illustrative publication inventory")
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Illustration publication contains a symlink")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != expected | {"publication.json"}:
        raise ValueError("Unexpected illustrative package files")
    for name, checksum in manifest["files"].items():
        if digest(private_path(root, name)) != checksum:
            raise ValueError("Illustrative publication hash changed")
    appearances = json.loads((root / "appearances.json").read_text())
    validate_appearances(appearances, root)
    for case in CASES:
        scene = Scene.model_validate_json((root / f"scenes/{case}-illustrated.json").read_text())
        if scene != illustration_scene(case, appearances):
            raise ValueError("Illustrative scene differs from the reviewed layout and appearances")
    return manifest


def package_illustrations(generated, destination):
    if destination.exists() or destination.is_symlink():
        raise ValueError("Illustrative publication destination must be new")
    appearances = json.loads((generated / "appearances.json").read_text())
    destination.mkdir(parents=True)
    (destination / "assets").mkdir()
    for identifier, metadata in appearances.items():
        source = private_path(generated, f"{identifier}.ply")
        public_metadata = public_ply(source, destination / f"assets/{identifier}.ply")
        metadata["generation_sha256"] = metadata["sha256"]
        metadata.pop("camera", None)
        metadata.update(public_metadata)
    write_json(destination / "appearances.json", appearances)
    validate_appearances(appearances, destination)
    (destination / "scenes").mkdir()
    for case in CASES:
        write_json(destination / f"scenes/{case}-illustrated.json", illustration_scene(case, appearances).model_dump())
    manifest = {
        "version": 1, "kind": "reviewed-generated-illustrations",
        "files": {path.relative_to(destination).as_posix(): digest(path) for path in destination.rglob("*") if path.is_file()},
        "cases": [f"{case}-illustrated" for case in CASES],
    }
    write_json(destination / "publication.json", manifest)
    validate_illustration_package(destination)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    package_illustrations(arguments.generated, arguments.out)


if __name__ == "__main__":
    main()
