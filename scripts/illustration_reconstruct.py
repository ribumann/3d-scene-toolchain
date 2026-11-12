"""Reconstruct only hash-bound, explicitly reviewed generated reference candidates."""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Literal

from PIL import Image
from pydantic import Field, model_validator

from scene_pipeline.models import Case, Identifier, StrictModel
from scripts.generated_references import Manifest, reference_folder, validate_reference
from scripts.package_pilots import APPROVED_PINS
from scripts.private_gpu_batch import digest, private_path, snapshot_extraction, write_json
from scripts.private_gpu_smoke import run_stage, validate_generation


class ReviewedReference(StrictModel):
    id: Identifier
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    box: tuple[float, float, float, float]
    reviewed: Literal[True]
    note: str = Field(min_length=10, max_length=1000)

    @model_validator(mode="after")
    def valid_box(self):
        x, y, w, h = self.box
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x+w > 1 or y+h > 1:
            raise ValueError("Reviewed reference box must be normalized in-bounds XYWH")
        return self


class Reviews(StrictModel):
    schema_version: Literal[1]
    objects: list[ReviewedReference] = Field(min_length=1, max_length=48)

    @model_validator(mode="after")
    def unique(self):
        if len({item.id for item in self.objects}) != len(self.objects):
            raise ValueError("Duplicate reviewed reference")
        return self


def extract_reference(directory, concept, review, output):
    from scene_pipeline.extract import extract_photo
    source = reference_folder(directory, concept)
    receipt = validate_reference(source, concept)
    if receipt["sha256"] != review.sha256:
        raise ValueError("Reviewed candidate hash changed")
    scene, report = extract_photo(
        Case(id=concept.id, title=concept.subject, input_type="generated", summary="Generated illustrative object reference."),
        {"preview_path": str(source / "reference.png"), "filename": f"{concept.id}.png", "sha256": review.sha256},
        output, reviewed_boxes=[list(review.box)], reviewed_labels=[concept.category],
    )
    write_json(output / "scene.json", scene.model_dump())
    return report


def reconstruct(directory, manifest_path, reviews_path, export):
    if {key: os.environ.get(key) for key in APPROVED_PINS} != APPROVED_PINS:
        raise ValueError("Illustrative reconstruction requires frozen approved model pins")
    manifest = Manifest.model_validate_json(manifest_path.read_text())
    concepts = {item.id: item for item in manifest.concepts}
    reviews = Reviews.model_validate_json(reviews_path.read_text())
    if set(item.id for item in reviews.objects) - concepts.keys():
        raise ValueError("Review references an unknown generated concept")
    export.mkdir(parents=True, exist_ok=False)
    results = {}
    for review in reviews.objects:
        concept = concepts[review.id]
        source = reference_folder(directory, concept)
        reference = validate_reference(source, concept)
        if reference["sha256"] != review.sha256:
            raise ValueError("Reviewed reference changed")
        folder = private_path(directory, f"illustrations/reconstruction/{concept.id}/{source.name}")
        folder.mkdir(parents=True, exist_ok=True)
        expected = {"reference": reference, "review": review.model_dump(mode="json"), "pins": APPROVED_PINS, "steps": 50, "count": 32768, "seed": 42}
        checkpoint = folder / "contract.json"
        if checkpoint.exists() and json.loads(checkpoint.read_text()) != expected:
            raise ValueError("Reviewed reconstruction resume contract changed")
        write_json(checkpoint, expected)
        extraction = folder / "extraction"
        receipt_path = folder / "extraction-receipt.json"
        if receipt_path.exists():
            if snapshot_extraction(extraction) != json.loads(receipt_path.read_text()):
                raise ValueError("Reviewed extraction changed")
        else:
            extraction.mkdir(exist_ok=True)
            run_stage([
                "/home/scene/scene-vision-venv/bin/python", "-m", "scripts.illustration_reconstruct",
                "extract", "--data-dir", str(directory), "--manifest", str(manifest_path),
                "--reviews", str(reviews_path), "--concept", concept.id, "--export", str(extraction),
            ], folder / "extraction-private.log", 1200, {})
            write_json(receipt_path, snapshot_extraction(extraction))
        crop = extraction / "object-000.png"
        with Image.open(crop) as image:
            image.load()
            histogram = image.getchannel("A").histogram() if image.mode == "RGBA" else []
            if not histogram or min(image.size) < 32 or sum(histogram[1:]) < 256 or histogram[0] == 0:
                raise ValueError("Generated target has no usable segmented foreground")
        result = folder / "generation"
        timing = {}
        resumed = (folder / "generation-receipt.json").exists()
        if not resumed:
            result.mkdir(exist_ok=True)
            run_stage([
                sys.executable, "-m", "scene_pipeline.idol_worker", "--image", str(crop),
                "--out", str(result), "--mode", "real", "--count", "32768",
            ], folder / "idol-private.log", 3600, timing)
        metadata = validate_generation(result, crop)
        hashes = {name: digest(result / name) for name in ("object.ply", "generation.json")}
        if resumed and json.loads((folder / "generation-receipt.json").read_text()) != hashes:
            raise ValueError("Generated appearance changed since its successful receipt")
        write_json(folder / "generation-receipt.json", hashes)
        target = export / f"{concept.id}.ply"
        shutil.copyfile(result / "object.ply", target)
        results[concept.id] = {
            **metadata, "reference": reference, "review": review.model_dump(mode="json"),
            "segmentation": "reviewed-box+SAM2", "crop_sha256": digest(crop),
            "illustrative": True, "resumed": resumed, "timing_this_run": timing,
        }
        write_json(export / "appearances.json", results)
        print(json.dumps({"id": concept.id, "status": "succeeded", "resumed": resumed}), flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("extract", "run"))
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--concept")
    args = parser.parse_args()
    if args.operation == "extract":
        manifest = Manifest.model_validate_json(args.manifest.read_text())
        reviews = Reviews.model_validate_json(args.reviews.read_text())
        extract_reference(
            args.data_dir, next(item for item in manifest.concepts if item.id == args.concept),
            next(item for item in reviews.objects if item.id == args.concept), args.export,
        )
    else:
        reconstruct(args.data_dir, args.manifest, args.reviews, args.export)


if __name__ == "__main__":
    main()
