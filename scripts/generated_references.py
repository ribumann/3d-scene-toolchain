"""Generate inspectable photographic candidates, never recovered schema appearance."""

import argparse
import hashlib
import json
import shutil
import time
from importlib.metadata import version
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw
from pydantic import Field, model_validator

from scene_pipeline.models import Identifier, StrictModel
from scripts.private_gpu_batch import digest, private_path, write_json

MODEL = "segmind/SSD-1B"
REVISION = "60987f37e94cd59c36b1cba832b9f97b57395a10"
NEGATIVE = "cropped, cut off, people, text, logo, watermark, cartoon, illustration, 3D render, blurry"
CASES = ("P01", "P02", "P03", "I01", "I04", "I05")


class Concept(StrictModel):
    id: Identifier
    category: str = Field(min_length=1, max_length=100)
    cases: list[Literal["P01", "P02", "P03", "I01", "I04", "I05"]] = Field(min_length=1, max_length=6)
    subject: str = Field(min_length=5, max_length=400)


class Manifest(StrictModel):
    schema_version: Literal[1]
    concepts: list[Concept] = Field(min_length=1, max_length=48)

    @model_validator(mode="after")
    def unique_concepts(self):
        if len({item.id for item in self.concepts}) != len(self.concepts):
            raise ValueError("Duplicate illustrative object identities")
        return self


def contract(concept):
    seed = int.from_bytes(hashlib.sha256(concept.id.encode()).digest()[:4], "big")
    prompt = (
        f"Photograph of {concept.subject}. Single complete main subject, three-quarter view, "
        "centered, realistic materials, soft daylight, contextual floor and background, "
        "unobstructed silhouette, ample margin."
    )
    return {
        "concept": concept.model_dump(mode="json"), "model": MODEL, "revision": REVISION,
        "prompt": prompt, "negative_prompt": NEGATIVE, "seed": seed,
        "width": 1024, "height": 1024, "steps": 30, "guidance_scale": 9.0,
        "dtype": "float16", "cpu_offload": True,
        "kind": "generated-illustrative-photographic-candidate",
    }


def reference_folder(directory, concept):
    key = hashlib.sha256(json.dumps(contract(concept), sort_keys=True).encode()).hexdigest()
    return private_path(directory, f"illustrations/references/{concept.id}/{key}")


def validate_reference(folder, concept):
    receipt = json.loads((folder / "reference.json").read_text())
    if receipt["contract"] != contract(concept) or receipt["sha256"] != digest(folder / "reference.png"):
        raise ValueError("Illustrative reference contract or image hash changed")
    with Image.open(folder / "reference.png") as image:
        if image.format != "PNG" or image.size != (1024, 1024):
            raise ValueError("Illustrative reference image format or dimensions changed")
        image.verify()
    return receipt


def generate_references(directory, manifest_path, selected, export):
    if not selected or len(selected) != len(set(selected)) or set(selected) - set(CASES):
        raise ValueError("Select unique supported prompt/schema cases")
    manifest = Manifest.model_validate_json(manifest_path.read_text())
    concepts = [item for item in manifest.concepts if set(item.cases) & set(selected)]
    export.mkdir(parents=True, exist_ok=False)
    pipeline = None
    reports = []
    for concept in concepts:
        folder = reference_folder(directory, concept)
        folder.mkdir(parents=True, exist_ok=True)
        if not (folder / "reference.json").exists():
            import torch
            from diffusers import StableDiffusionXLPipeline
            if not torch.cuda.is_available():
                raise RuntimeError("Reference generation requires actual CUDA; no image substitute")
            if pipeline is None:
                if shutil.disk_usage(directory).free < 15 * 1024**3:
                    raise RuntimeError("Reference model download requires at least 15 GiB free disk")
                pipeline = StableDiffusionXLPipeline.from_pretrained(
                    MODEL, revision=REVISION, torch_dtype=torch.float16,
                    variant="fp16", use_safetensors=True,
                )
                pipeline.enable_model_cpu_offload()
                pipeline.enable_vae_slicing()
            settings = contract(concept)
            for tokenizer in (pipeline.tokenizer, pipeline.tokenizer_2):
                if len(tokenizer(settings["prompt"]).input_ids) > tokenizer.model_max_length:
                    raise ValueError(f"Reference prompt would be truncated: {concept.id}")
            started = time.monotonic()
            image = pipeline(
                prompt=settings["prompt"], negative_prompt=NEGATIVE,
                num_inference_steps=30, guidance_scale=9.0, height=1024, width=1024,
                generator=torch.Generator("cpu").manual_seed(settings["seed"]),
            ).images[0]
            image.convert("RGB").save(folder / "reference.tmp.png")
            (folder / "reference.tmp.png").replace(folder / "reference.png")
            write_json(folder / "reference.json", {
                "contract": settings, "sha256": digest(folder / "reference.png"),
                "seconds": round(time.monotonic() - started, 3),
                "libraries": {name: version(name) for name in ("torch", "diffusers", "transformers", "accelerate")},
                "reviewed": False, "limitations": "Invented appearance from a description; not recovered from a schema.",
            })
        receipt = validate_reference(folder, concept)
        shutil.copyfile(folder / "reference.png", export / f"{concept.id}.png")
        reports.append({"id": concept.id, **receipt})
        print(json.dumps({"id": concept.id, "status": "candidate_ready", "reviewed": False}), flush=True)
        write_json(export / "references.json", reports)
    sheet = Image.new("RGB", (5 * 224, ((len(concepts) + 4) // 5) * 248), "white")
    draw = ImageDraw.Draw(sheet)
    for index, concept in enumerate(concepts):
        x, y = index % 5 * 224, index // 5 * 248
        with Image.open(export / f"{concept.id}.png") as image:
            image.thumbnail((220, 220))
            sheet.paste(image, (x, y + 24))
        draw.text((x + 4, y + 4), concept.id, fill="black")
    sheet.save(export / "contact-sheet.jpg", quality=90)
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", required=True)
    parser.add_argument("--export", type=Path, required=True)
    arguments = parser.parse_args()
    generate_references(arguments.data_dir, arguments.manifest, arguments.cases, arguments.export)


if __name__ == "__main__":
    main()
