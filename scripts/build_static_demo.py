"""Publish templates, authorized previews and an explicitly approved pilot package."""

import json
import os
import re
import shutil
from pathlib import Path

from scene_pipeline.models import Case
from scene_pipeline.templates import compile_prompt

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_IDS = ("I01", "I02", "I03", "I04", "I05", "G01", "G02", "G03")
REFERENCE_SOURCE = ROOT / "apps/web/public/references"


def apply_visual_exclusions(quality, reviews):
    if not isinstance(reviews, dict) or set(reviews) != {"schema_version", "excluded"} or type(reviews["schema_version"]) is not int or reviews["schema_version"] != 1 or not isinstance(reviews["excluded"], dict):
        raise ValueError("Invalid visual exclusion review manifest")
    for sha256, note in reviews["excluded"].items():
        if not re.fullmatch(r"[0-9a-f]{64}", sha256) or not isinstance(note, str) or not 10 <= len(note) <= 500:
            raise ValueError("Visual exclusions require exact SHA256 and a bounded review note")
    for sha256, note in reviews["excluded"].items():
        if sha256 in quality:
            quality[sha256] = {
                **quality[sha256], "status": "excluded",
                "reasons": [*quality[sha256]["reasons"], f"visual_review: {note}"],
            }


def build_demo(public: Path, pilot_package: Path | None = None, trial_package: Path | None = None, illustration_package: Path | None = None):
    from scripts.package_pilots import validate_package
    from scene_pipeline.gaussians import assess_ply

    pilots = validate_package(pilot_package) if pilot_package is not None else None
    trials = None
    if trial_package is not None:
        if pilots is None or any(item["scene"] is None for item in pilots["cases"]):
            raise ValueError("Trial publication requires the complete approved eight-source pilot package")
        from scripts.package_trials import validate_trial_package
        trials = validate_trial_package(trial_package)
    trial_entries = trials[0]["trials"] if trials else []
    illustrations = None
    if illustration_package is not None:
        if pilots is None or trials is None:
            raise ValueError("Illustrative publication must retain approved original and interim packages")
        from scripts.package_illustrations import validate_illustration_package
        illustrations = validate_illustration_package(illustration_package)
    illustration_ids = set(illustrations["cases"]) if illustrations else set()
    trial_ids = {f"{entry['trial_id']}-{entry['variant']}" for entry in trial_entries if entry["scene"]}
    entries = {item["case_id"]: item for item in pilots["cases"]} if pilots else {}
    destination, references = public / "demo", public / "references"
    for directory, allowed in (
        (public, {"demo", "references"} | ({"pilot-assets"} if pilots else set()) | ({"trial-assets", "trial-references"} if trials else set()) | ({"illustration-assets"} if illustrations else set())),
        (destination, {"cases.json", "P01.json", "P02.json", "P03.json", "pilots.json", "trials.json", "quality.json"} | {f"{case}.json" for case in trial_ids | illustration_ids} | ({*(f"{case}.json" for case, item in entries.items() if item["scene"])} if pilots else set())),
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
    for dirname, prefix in (("trial-assets", "assets/"), ("trial-references", "references/")):
        directory = public / dirname
        expected = {name.removeprefix(prefix) for name in trials[0]["files"] if name.startswith(prefix)} if trials else set()
        if directory.exists():
            for path in directory.rglob("*"):
                if path.is_symlink() or (path.is_file() and path.relative_to(directory).as_posix() not in expected):
                    raise ValueError("Unexpected public trial output")
    illustration_assets = public / "illustration-assets"
    if illustration_assets.exists():
        expected = {name.removeprefix("assets/") for name in illustrations["files"] if name.startswith("assets/")} if illustrations else set()
        for path in illustration_assets.rglob("*"):
            if path.is_symlink() or (path.is_file() and path.relative_to(illustration_assets).as_posix() not in expected):
                raise ValueError("Unexpected public illustration output")
    for identifier in REFERENCE_IDS:
        source = REFERENCE_SOURCE / f"{identifier}.webp"
        if REFERENCE_SOURCE.is_symlink() or source.is_symlink() or not source.is_file():
            raise ValueError(f"Authorized reference preview missing or unsafe: {identifier}")
    cases = [Case.model_validate(item) for item in json.loads((ROOT / "cases/manifest.json").read_text())]
    destination.mkdir(parents=True, exist_ok=True)
    references.mkdir(parents=True, exist_ok=True)
    quality = {}
    for package, manifest in ((pilot_package, pilots), (trial_package, trials[0] if trials else None), (illustration_package, illustrations)):
        if manifest is not None:
            for name in manifest["files"]:
                if name.startswith("assets/") and name.endswith(".ply"):
                    assessment = assess_ply(package / name)
                    quality[assessment["sha256"]] = assessment
    apply_visual_exclusions(quality, json.loads((ROOT / "cases/appearance-reviews.json").read_text()))
    (destination / "quality.json").write_text(json.dumps({
        "version": 1,
        "policy": "Four-sigma support above 1/255 opacity, aspect-fit screening and exact-hash visual exclusions; retained assets are not semantic acceptance.",
        "assets": quality,
    }, indent=2) + "\n")
    for case in cases:
        case.source_filename = f"{case.id}.webp" if case.id in REFERENCE_IDS else None
        case.source_url = f"/references/{case.id}.webp" if case.id in REFERENCE_IDS else None
        if case.id in REFERENCE_IDS:
            provenance = "AI-generated" if case.input_type == "generated" else "original"
            case.summary = f"User-supplied {provenance} reference, shared as a public WebP preview. No 3D reconstruction is published."
        entry = entries.get(case.id)
        case.status = "ready" if case.id in ("P01", "P02", "P03") else "awaiting_input"
        if entry and entry["status"] == "processing":
            case.summary = "Processing at publication snapshot. Active outputs are not published; this is not live status."
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
    if trials:
        for trial in trials[1].trials:
            for entry in (item for item in trial_entries if item["trial_id"] == trial.id):
                cases.append(Case(
                    id=f"{trial.id}-{entry['variant']}", title=f"{trial.title} / {entry['variant']}",
                    input_type="photo" if trial.source.kind == "licensed-real-photograph" else "generated",
                    summary="Licensed real-photo trial; reviewed-box supervision, inferred geometry." if trial.source.kind == "licensed-real-photograph" else "Synthetic photographic trial; supervised comparison, not accuracy certification.",
                    status="ready" if entry["scene"] else "awaiting_input", source_filename=trial.source.filename,
                    source_url=f"/trial-references/{trial.source.filename}",
                ))
    if illustrations:
        from scene_pipeline.models import Scene
        for identifier in illustrations["cases"]:
            scene = Scene.model_validate_json((illustration_package / f"scenes/{identifier}.json").read_text())
            original = next(case for case in cases if case.id == identifier.removesuffix("-illustrated"))
            cases.append(Case(
                id=identifier, title=scene.name, input_type=original.input_type, status="ready",
                summary=f"Illustrative generated appearances: {len(scene.assets)} shared concepts, {sum(node.asset_id is not None for node in scene.nodes)} authored instances; not recovered source appearance. {scene.description}",
                prompt=original.prompt, source_filename=original.source_filename, source_url=original.source_url,
            ))
    (destination / "cases.json").write_text(
        json.dumps([case.model_dump() for case in cases], indent=2) + "\n"
    )
    for identifier in REFERENCE_IDS:
        shutil.copyfile(REFERENCE_SOURCE / f"{identifier}.webp", references / f"{identifier}.webp")
    (destination / "pilots.json").write_text(json.dumps(pilots["cases"] if pilots else [], indent=2) + "\n")
    (destination / "trials.json").write_text(json.dumps([
        {**entry, "definition": next(trial.model_dump(mode="json") for trial in trials[1].trials if trial.id == entry["trial_id"])}
        for entry in trial_entries
    ], indent=2) + "\n")
    if pilots:
        # Publish only validated package paths, never its parent/private runtime.
        for name in pilots["files"]:
            if name.startswith("assets/"):
                target = public / "pilot-assets/pilot" / name.removeprefix("assets/")
            else:
                target = destination / Path(name).name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pilot_package / name, target)
    if trials:
        for name in trials[0]["files"]:
            if name.startswith("assets/"):
                target = public / "trial-assets" / name.removeprefix("assets/")
            elif name.startswith("references/"):
                target = public / "trial-references" / Path(name).name
            elif name.startswith("scenes/"):
                target = destination / Path(name).name
            else:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(trial_package / name, target)
    if illustrations:
        for name in illustrations["files"]:
            if name.startswith("assets/"):
                target = public / "illustration-assets" / name.removeprefix("assets/")
            elif name.startswith("scenes/"):
                target = destination / Path(name).name
            else:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(illustration_package / name, target)


if __name__ == "__main__":
    package = os.environ.get("SCENE_PILOT_PUBLIC_PACKAGE")
    trials = os.environ.get("SCENE_TRIAL_PUBLIC_PACKAGE")
    illustrations = os.environ.get("SCENE_ILLUSTRATION_PUBLIC_PACKAGE")
    build_demo(ROOT / "apps/web/public-demo", Path(package) if package else None, Path(trials) if trials else None, Path(illustrations) if illustrations else None)
