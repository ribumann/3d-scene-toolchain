"""Publish deterministic templates and eight authorized reference previews only."""

import json
import shutil
from pathlib import Path

from scene_pipeline.models import Case
from scene_pipeline.templates import compile_prompt

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_IDS = ("I01", "I02", "I03", "I04", "I05", "G01", "G02", "G03")
REFERENCE_SOURCE = ROOT / "apps/web/public/references"


def build_demo(public: Path):
    destination, references = public / "demo", public / "references"
    for directory, allowed in (
        (public, {"demo", "references"}),
        (destination, {"cases.json", "P01.json", "P02.json", "P03.json"}),
        (references, {f"{identifier}.webp" for identifier in REFERENCE_IDS}),
    ):
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise ValueError(f"Unexpected public demo content: {directory}")
        for path in directory.iterdir() if directory.exists() else ():
            valid_type = path.is_dir() if directory == public else path.is_file()
            if path.name not in allowed or not valid_type or path.is_symlink():
                raise ValueError(f"Unexpected public demo content: {path}. Remove it before publishing.")
    for identifier in REFERENCE_IDS:
        source = REFERENCE_SOURCE / f"{identifier}.webp"
        if REFERENCE_SOURCE.is_symlink() or source.is_symlink() or not source.is_file():
            raise ValueError(f"Authorized reference preview missing or unsafe: {identifier}")
    cases = [Case.model_validate(item) for item in json.loads((ROOT / "cases/manifest.json").read_text())]
    destination.mkdir(parents=True, exist_ok=True)
    references.mkdir(parents=True, exist_ok=True)
    for case in cases:
        case.source_filename = f"{case.id}.webp" if case.id in REFERENCE_IDS else None
        case.source_url = f"/references/{case.id}.webp" if case.id in REFERENCE_IDS else None
        if case.id in REFERENCE_IDS:
            provenance = "AI-generated" if case.input_type == "generated" else "original"
            case.summary = f"User-supplied {provenance} reference, shared as a public WebP preview. No 3D reconstruction is published."
        case.status = "ready" if case.id in ("P01", "P02", "P03") else "awaiting_input"
        if case.status == "ready":
            scene = compile_prompt(case)
            (destination / f"{case.id}.json").write_text(scene.model_dump_json(indent=2) + "\n")
    (destination / "cases.json").write_text(
        json.dumps([case.model_dump() for case in cases], indent=2) + "\n"
    )
    for identifier in REFERENCE_IDS:
        shutil.copyfile(REFERENCE_SOURCE / f"{identifier}.webp", references / f"{identifier}.webp")


if __name__ == "__main__":
    build_demo(ROOT / "apps/web/public-demo")
