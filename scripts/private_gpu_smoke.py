"""One private I02 crop -> real Idol output. Never upload media or raw logs."""

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

from PIL import Image, ImageOps, UnidentifiedImageError

from scene_pipeline.gaussians import validate_ply
from scene_pipeline.idol_worker import SDK_REVISION
from scene_pipeline.models import Scene

ROOT = Path(__file__).resolve().parents[1]
PIN_NAMES = (
    "SCENE_IDOL_MODEL_REVISION", "SCENE_DINOV3_REVISION", "SCENE_FLUX2_REVISION",
    "SCENE_DETECTOR_REVISION", "SCENE_SEGMENTER_REVISION",
)
ALLOWED_CATEGORIES = {"building", "conveyor", "truck", "tree"}
CASE_CATEGORIES = {
    "I02": ALLOWED_CATEGORIES,
    "I03": {"industrial vessel", "tank", "valve", "pipe"},
    "G01": {"shelf", "checkout counter", "refrigerator"},
    "G02": {"industrial machine", "conveyor", "buffer"},
    "G03": {"enclosure", "tree", "building", "pond"},
}
PILOT_IDS = ("I01", "I02", "I03", "I04", "I05", "G01", "G02", "G03")


class SmokeError(RuntimeError):
    pass


def load_source(directory: Path, public_preview: Path | None = None, case_id="I02"):
    if public_preview is not None:
        content = public_preview.read_bytes()
        with Image.open(public_preview) as image:
            if image.format != "WEBP":
                raise SmokeError("public_preview_is_not_webp")
            image.verify()
        return {
            "preview_path": str(public_preview), "filename": f"{case_id}-public-preview.webp",
            "sha256": hashlib.sha256(content).hexdigest(),
        }, "public-webp-preview"
    database = directory / "scene.sqlite3"
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        row = connection.execute("SELECT sha256,filename FROM sources WHERE case_id=?", (case_id,)).fetchone()
    if row is None or not re.fullmatch(r"[0-9a-f]{64}", row[0]):
        raise SmokeError("private_I02_source_metadata_missing")
    folder = directory / "sources" / case_id / row[0]
    original, preview = folder / "original", folder / "preview.png"
    if hashlib.sha256(original.read_bytes()).hexdigest() != row[0]:
        raise SmokeError("private_original_checksum_mismatch")
    with Image.open(original) as image, Image.open(preview) as display:
        if image.format not in ("JPEG", "PNG", "WEBP") or image.width * image.height > 20_000_000:
            raise SmokeError("private_source_image_invalid")
        expected = ImageOps.exif_transpose(image).convert("RGB")
        actual = display.convert("RGB")
        if expected.size != actual.size or expected.tobytes() != actual.tobytes():
            raise SmokeError("private_preview_does_not_match_original")
    return {"preview_path": str(preview), "filename": row[1], "sha256": row[0]}, "private-original"


def enumerate_crops(scene: Scene, extraction: dict, directory: Path):
    if scene.case_id not in CASE_CATEGORIES or extraction.get("method") != "grounding-dino+sam2":
        raise SmokeError("unexpected_extraction_contract")
    nodes = {node.id: node for node in scene.nodes}
    annotations = {}
    for annotation in extraction["annotations"]:
        identifier = annotation["node_id"]
        if identifier not in nodes or identifier in annotations:
            raise SmokeError("unexpected_or_duplicate_extraction_annotation")
        annotations[identifier] = annotation
    candidates, rejected = [], []
    for node in sorted(scene.nodes, key=lambda item: item.id):
        annotation = annotations.get(node.id, {})
        reason = None
        if not node.visible or node.category not in CASE_CATEGORIES[scene.case_id]:
            reason = "not_an_approved_non_person_object"
        elif annotation.get("crop") != f"{node.id}.png":
            reason = "invalid_crop_reference"
        else:
            path = directory / annotation["crop"]
            if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
                reason = "unsafe_crop_path"
            else:
                try:
                    with Image.open(path) as image:
                        image.load()
                        if image.mode != "RGBA" or min(image.size) < 32:
                            reason = "invalid_crop_format_or_size"
                        elif list(image.size) != annotation["bbox_pixels"][2:]:
                            reason = "crop_bounds_mismatch"
                        else:
                            histogram = image.getchannel("A").histogram()
                            foreground = sum(histogram[1:])
                            if foreground < 256 or histogram[0] == 0:
                                reason = "empty_or_unsegmented_alpha"
                            else:
                                candidates.append({
                                    "node_id": node.id, "category": node.category, "path": path,
                                    "confidence": node.evidence.confidence, "foreground_pixels": foreground,
                                    "crop_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                    "bbox_pixels": annotation["bbox_pixels"],
                                })
                except (OSError, UnidentifiedImageError):
                    reason = "unreadable_crop"
        if reason:
            rejected.append({"node_id": node.id, "category": node.category, "reason": reason})
    return candidates, rejected


def select_crop(scene: Scene, extraction: dict, directory: Path):
    candidates, rejected = enumerate_crops(scene, extraction, directory)
    if not candidates:
        raise SmokeError("no_valid_non_person_segmented_crop")
    selected = max(candidates, key=lambda item: (item["confidence"], item["foreground_pixels"], item["node_id"]))
    counts = {}
    for item in rejected:
        counts[item["reason"]] = counts.get(item["reason"], 0) + 1
    return selected["path"], {
        "selected_node": selected["node_id"], "selected_category": selected["category"],
        "foreground_pixels": selected["foreground_pixels"], "rejected_crops": counts,
    }


def validate_extraction(scene: Scene, extraction: dict, source_sha256: str, case_id="I02"):
    if scene.case_id != case_id or not any(item.sha256 == source_sha256 for item in scene.sources):
        raise SmokeError("extraction_source_changed")
    if case_id in ("I01", "I04", "I05"):
        if extraction.get("method") != "opencv-line-contours+tesseract" or extraction.get("topology_status") != "not_extracted":
            raise SmokeError("unexpected_diagram_extraction_contract")
        return
    if extraction["detector"] != {
        "model": "IDEA-Research/grounding-dino-tiny", "revision": os.environ["SCENE_DETECTOR_REVISION"],
    } or extraction["segmenter"] != {
        "model": "facebook/sam2.1-hiera-small", "revision": os.environ["SCENE_SEGMENTER_REVISION"],
    }:
        raise SmokeError("extraction_model_pins_mismatch")


def validate_generation(output: Path, crop: Path):
    if any((output / name).is_symlink() for name in ("generation.json", "object.ply")):
        raise SmokeError("unsafe_generation_symlink")
    metadata = json.loads((output / "generation.json").read_text())
    if any(metadata.get(key) != value for key, value in {
        "model": "speridlabs/idol", "mode": "real", "steps": 50, "seed": 42, "sdk_revision": SDK_REVISION,
        "model_revision": os.environ["SCENE_IDOL_MODEL_REVISION"],
        "input_sha256": hashlib.sha256(crop.read_bytes()).hexdigest(),
    }.items()) or metadata.get("encoder_revisions") != {key: os.environ[key] for key in ("SCENE_DINOV3_REVISION", "SCENE_FLUX2_REVISION")}:
        raise SmokeError("idol_provenance_mismatch")
    validated = validate_ply(output / "object.ply")
    if validated["gaussian_count"] != 32768:
        raise SmokeError("unexpected_gaussian_count_no_quality_fallback")
    if any(metadata.get(key) != value for key, value in validated.items()):
        raise SmokeError("idol_output_metadata_mismatch")
    return metadata


def gpu_memory_mib():
    result = subprocess.run(
        ["nvidia-smi", "-i", "0", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode or not result.stdout.strip().isdigit():
        raise SmokeError("gpu_memory_sampling_unavailable")
    return int(result.stdout.strip())


def run_stage(arguments, log: Path, timeout: int, measurement: dict):
    started = time.monotonic()
    measurement.update(seconds=0, peak_device_memory_mib_sampled=0, sample_interval_seconds=2)
    with log.open("w") as stream:
        process = subprocess.Popen(arguments, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while process.poll() is None:
                measurement["peak_device_memory_mib_sampled"] = max(
                    measurement["peak_device_memory_mib_sampled"], gpu_memory_mib(),
                )
                if time.monotonic() - started > timeout:
                    raise SmokeError("stage_timeout")
                time.sleep(2)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            measurement["seconds"] = round(time.monotonic() - started, 3)
    if process.returncode:
        diagnostic = log.read_text(errors="replace")
        if "OutOfMemoryError" in diagnostic or "CUDA out of memory" in diagnostic:
            raise SmokeError("cuda_out_of_memory_no_quality_fallback")
        raise SmokeError("stage_failed_inspect_private_log")


def extract_only(directory: Path, output: Path, public_preview: Path | None, all_objects=False, case_id="I02"):
    from scene_pipeline.extract import extract_diagram, extract_photo
    from scene_pipeline.models import Case

    source, _ = load_source(directory, public_preview, case_id)
    case = next(Case.model_validate(item) for item in json.loads((ROOT / "cases/manifest.json").read_text()) if item["id"] == case_id)
    if case.input_type in ("diagram", "plan"):
        scene, _ = extract_diagram(case, source, output / "extraction", max_regions=None)
    else:
        scene, _ = extract_photo(case, source, output / "extraction", max_objects=None if all_objects else 48)
    (output / "extraction/scene.json").write_text(scene.model_dump_json(indent=2))


def run_smoke(directory: Path, output: Path, public_preview: Path | None):
    report = {
        "case_id": "I02", "status": "failed", "mode": "real",
        "gaussian_count_requested": 32768, "steps": 50, "seed": 42,
        "stage": "preflight", "failure_reason": "not_completed", "timings": {},
    }
    created = False
    try:
        for name in PIN_NAMES:
            if not re.fullmatch(r"[0-9a-f]{40}", os.environ.get(name, "")):
                raise SmokeError("missing_immutable_model_pin")
        if not os.environ.get("HF_TOKEN"):
            raise SmokeError("HF_TOKEN_missing")
        source, kind = load_source(directory, public_preview)
        output.mkdir(mode=0o700)
        created = True
        report["source_kind"] = kind
        if kind == "public-webp-preview":
            report["public_preview_sha256"] = source["sha256"]
        (output / "input-provenance.json").write_text(json.dumps({"source_kind": kind, "sha256": source["sha256"]}, indent=2))
        arguments = ["/home/scene/scene-vision-venv/bin/python", str(Path(__file__).resolve()), "extract", "--data-dir", str(directory), "--output", str(output)]
        if public_preview is not None:
            arguments += ["--public-preview", str(public_preview)]
        report["stage"] = "extract"
        report["timings"]["extract"] = {}
        run_stage(arguments, output / "extract-private.log", 1200, report["timings"]["extract"])
        folder = output / "extraction"
        scene = Scene.model_validate_json((folder / "scene.json").read_text())
        extraction = json.loads((folder / "extraction.json").read_text())
        validate_extraction(scene, extraction, source["sha256"])
        crop, selection = select_crop(scene, extraction, folder)
        report.update(selection)
        report["objects_detected"] = len(scene.nodes)
        report["stage"] = "idol"
        report["timings"]["idol"] = {}
        run_stage(
            [sys.executable, "-m", "scene_pipeline.idol_worker", "--image", str(crop),
             "--out", str(output), "--mode", "real", "--count", "32768"],
            output / "idol-private.log", 3600, report["timings"]["idol"],
        )
        metadata = validate_generation(output, crop)
        report.update(status="succeeded", stage="complete", failure_reason=None, gaussian_count=metadata["gaussian_count"])
    except SmokeError as error:
        report["failure_reason"] = str(error)
    except (OSError, ValueError, KeyError, sqlite3.Error, subprocess.TimeoutExpired):
        report["failure_reason"] = "private_input_output_or_runtime_validation_failed"
    finally:
        if created:
            (output / "safe-status.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "succeeded" else 1


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "extract"))
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--public-preview", type=Path)
    parser.add_argument("--all-objects", action="store_true", help="Extract every detection for the separate private batch.")
    parser.add_argument("--case", choices=PILOT_IDS, default="I02")
    args = parser.parse_args()
    if args.all_objects and args.command != "extract":
        parser.error("--all-objects is only supported by the extraction subprocess")
    if args.command == "run" and args.case != "I02":
        parser.error("The original smoke supports I02 only; use the pilot batch for other cases")
    if args.command == "extract":
        extract_only(args.data_dir, args.output, args.public_preview, args.all_objects, args.case)
        return 0
    def interrupt(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, interrupt)
    return run_smoke(args.data_dir, args.output, args.public_preview)


if __name__ == "__main__":
    raise SystemExit(main())
