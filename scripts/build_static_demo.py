"""Publish templates, authorized previews and an explicitly approved pilot package."""

import json
import os
import shutil
from pathlib import Path

from scene_pipeline.models import Case
from scene_pipeline.templates import compile_prompt

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_IDS = ("I01", "I02", "I03", "I04", "I05", "G01", "G02", "G03")
REFERENCE_SOURCE = ROOT / "apps/web/public/references"


def build_demo(public: Path, pilot_package: Path | None = None):
    from scripts.package_pilots import validate_package

    pilots = validate_package(pilot_package) if pilot_package is not None else None
    entries = {item["case_id"]: item for item in pilots["cases"]} if pilots else {}
    destination, references = public / "demo", public / "references"
    for directory, allowed in (
        (public, {"demo", "references"} | ({"pilot-assets"} if pilots else set())),
        (destination, {"cases.json", "P01.json", "P02.json", "P03.json", "pilots.json"} | ({*(f"{case}.json" for case, item in entries.items() if item["scene"])} if pilots else set())),
        (references, {f"{identifier}.webp" for identifier in REFERENCE_IDS}),
    ):
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise ValueError(f"Unexpected public demo content: {directory}")
        for path in directory.iterdir() if directory.exists() else ():
            valid_type = path.is_dir() if directory == public else path.is_file()
            if path.name not in allowed or not valid_type or path.is_symlink():
                raise ValueError(f"Unexpected public demo content: {path}. Remove it before publishing.")
    if (public / "pilot-assets").exists():
        expected = {
            "pilot/" + name.removeprefix("assets/")
            for name in pilots["files"] if name.startswith("assets/")
        } if pilots else set()
        for path in (public / "pilot-assets").rglob("*"):
            if path.is_symlink() or (path.is_file() and path.relative_to(public / "pilot-assets").as_posix() not in expected):
                raise ValueError("Unexpected public pilot asset output")
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
        entry = entries.get(case.id)
        case.status = "ready" if case.id in ("P01", "P02", "P03") else "awaiting_input"
        if entry and entry["scene"]:
            case.status = "ready"
            case.summary = (
                "Unreviewed OCR/contour region proposals, not reconstructed appearance or recovered process topology."
                if entry["status"] == "proposals" else
                f"{entry['status'].capitalize()} object batch: {entry['objects']} validated object appearances; {entry['failed_objects']} failed or unfinished distinct crops. Layout/depth/scale inferred, not metric."
            )
        if case.id in ("P01", "P02", "P03"):
            scene = compile_prompt(case)
            (destination / f"{case.id}.json").write_text(scene.model_dump_json(indent=2) + "\n")
    (destination / "cases.json").write_text(
        json.dumps([case.model_dump() for case in cases], indent=2) + "\n"
    )
    for identifier in REFERENCE_IDS:
        shutil.copyfile(REFERENCE_SOURCE / f"{identifier}.webp", references / f"{identifier}.webp")
    (destination / "pilots.json").write_text(json.dumps(pilots["cases"] if pilots else [], indent=2) + "\n")
    if pilots:
        # Publish only validated package paths, never its parent/private runtime.
        for name in pilots["files"]:
            if name.startswith("assets/"):
                target = public / "pilot-assets/pilot" / name.removeprefix("assets/")
            else:
                target = destination / Path(name).name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pilot_package / name, target)


if __name__ == "__main__":
    package = os.environ.get("SCENE_PILOT_PUBLIC_PACKAGE")
    build_demo(ROOT / "apps/web/public-demo", Path(package) if package else None)
