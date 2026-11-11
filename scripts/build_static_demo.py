"""Publish only deterministic public templates, never runtime store contents."""

import json
from pathlib import Path

from scene_pipeline.models import Case
from scene_pipeline.templates import compile_prompt

ROOT = Path(__file__).resolve().parents[1]


def build_demo(destination: Path):
    allowed = {"cases.json", "P01.json", "P02.json", "P03.json"}
    if destination.exists():
        for path in destination.iterdir():
            if path.name not in allowed or not path.is_file() or path.is_symlink():
                raise ValueError(f"Unexpected public demo content: {path}. Remove it before publishing.")
    cases = [Case.model_validate(item) for item in json.loads((ROOT / "cases/manifest.json").read_text())]
    destination.mkdir(parents=True, exist_ok=True)
    for case in cases:
        case.source_filename = None
        case.source_url = None
        case.status = "ready" if case.id in ("P01", "P02", "P03") else "awaiting_input"
        if case.status == "ready":
            scene = compile_prompt(case)
            (destination / f"{case.id}.json").write_text(scene.model_dump_json(indent=2) + "\n")
    (destination / "cases.json").write_text(
        json.dumps([case.model_dump() for case in cases], indent=2) + "\n"
    )


if __name__ == "__main__":
    public = ROOT / "apps/web/public-demo"
    if public.exists() and any(path.name != "demo" or path.is_symlink() for path in public.iterdir()):
        raise ValueError("public-demo must contain only the generated demo directory.")
    build_demo(public / "demo")
