import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from .models import Case, Evidence, Node, Scene, Source


class PrerequisiteError(RuntimeError):
    pass


def source_scene(case: Case, source: dict):
    return Scene(
        id=case.id, case_id=case.id, name=case.title,
        description=case.summary + " Dimensions and depth are assumed. Review extracted regions before authoring.",
        nodes=[],
        sources=[Source(id="image", kind=case.input_type, filename=source["filename"], sha256=source["sha256"])],
    )


def extract_diagram(case: Case, source: dict, output: Path):
    try:
        import cv2
    except ImportError as error:
        raise PrerequisiteError("Diagram extraction requires opencv-python-headless; install .[vision] or the documented CPU extraction extra") from error
    if not shutil.which("tesseract"):
        raise PrerequisiteError("Diagram extraction requires Tesseract OCR; install tesseract-ocr and Japanese language data for I05")
    image = Image.open(source["preview_path"]).convert("RGB")
    width, height = image.size
    grayscale = np.array(ImageOps.grayscale(image))
    binary = cv2.threshold(grayscale, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    lines = np.zeros_like(binary)
    for kernel in ((max(10, width // 70), 1), (1, max(10, height // 70))):
        lines |= cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((kernel[1], kernel[0]), np.uint8))
    contours, _ = cv2.findContours(lines, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    rectangles = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        if .0007 * width * height < area < .3 * width * height and w > 8 and h > 8:
            if not any(abs(x - a) < 4 and abs(y - b) < 4 and abs(w - c) < 8 and abs(h - d) < 8 for a, b, c, d in rectangles):
                rectangles.append((x, y, w, h))
    rectangles = sorted(rectangles, key=lambda value: value[2] * value[3], reverse=True)[:100]
    languages = subprocess.run(["tesseract", "--list-langs"], check=True, capture_output=True, text=True).stdout.split()
    language = "eng+jpn" if case.id == "I05" else "eng"
    if case.id == "I05" and "jpn" not in languages:
        raise PrerequisiteError("I05 requires the Tesseract Japanese language pack; refusing to present English-only OCR as Japanese extraction")
    result = subprocess.run(
        ["tesseract", source["preview_path"], "stdout", "-l", language, "--psm", "11", "tsv"],
        check=True, capture_output=True, text=True, timeout=120,
    )
    import csv
    import io
    words = []
    for row in csv.DictReader(io.StringIO(result.stdout), delimiter="\t"):
        if row.get("text", "").strip() and float(row["conf"]) >= 20:
            words.append({**{key: int(row[key]) for key in ("left", "top", "width", "height")}, "text": row["text"], "confidence": float(row["conf"]) / 100})
    scene = source_scene(case, source)
    scale = 40 / max(width, height)
    annotations = []
    for index, (x, y, w, h) in enumerate(rectangles):
        contained = [word for word in words if x <= word["left"] + word["width"] / 2 <= x + w and y <= word["top"] + word["height"] / 2 <= y + h]
        label = " ".join(word["text"] for word in sorted(contained, key=lambda word: (word["top"] // 12, word["left"])))
        identifier = f"region-{index:03d}"
        scene.nodes.append(Node(
            id=identifier, label=(label or f"Unlabeled region {index + 1}")[:500], category="footprint" if case.input_type == "plan" else "equipment-candidate",
            shape="box", position=((x + w / 2 - width / 2) * scale, 1, (y + h / 2 - height / 2) * scale),
            size=(max(.1, w * scale), 2, max(.1, h * scale)), color="#7599aa",
            evidence=Evidence(origin="inferred", confidence=.35, source_id="image", note="Unreviewed line-contour region; OCR labels may be grouped incorrectly. Height/scale assumed; no process connection is implied."),
        ))
        annotations.append({"node_id": identifier, "bbox_pixels": [x, y, w, h], "ocr": contained})
    if not scene.nodes:
        raise ValueError("No plausible rectangular regions detected. Use manual scene import/correction; no empty successful reconstruction was published.")
    report = {
        "method": "opencv-line-contours+tesseract", "annotations": annotations,
        "ocr_words": words, "reviewed": False, "assumed_span_meters": 40,
        "topology_status": "not_extracted",
        "warnings": ["Directional topology, symbols, junctions and translations require review. No automatic process edges were invented."],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "extraction.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return scene, report


def extract_photo(case: Case, source: dict, output: Path, *, max_objects: int | None = 48):
    if max_objects is not None and max_objects < 1:
        raise ValueError("Photo object limit must be positive or None for all detections")
    try:
        import torch
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor, Sam2Model, Sam2Processor
    except ImportError as error:
        raise PrerequisiteError("Photo segmentation requires the .[vision] optional dependencies and cached Grounding DINO/SAM2 weights") from error
    if not torch.cuda.is_available():
        raise PrerequisiteError("Photo segmentation is configured for the separate GPU worker; CUDA is unavailable on this host")
    detector_name = os.environ.get("SCENE_DETECTOR_MODEL", "IDEA-Research/grounding-dino-tiny")
    segmenter_name = os.environ.get("SCENE_SEGMENTER_MODEL", "facebook/sam2.1-hiera-small")
    detector_revision = os.environ.get("SCENE_DETECTOR_REVISION")
    segmenter_revision = os.environ.get("SCENE_SEGMENTER_REVISION")
    if any(not value or len(value) != 40 or any(c not in "0123456789abcdef" for c in value) for value in (detector_revision, segmenter_revision)):
        raise PrerequisiteError("Pin SCENE_DETECTOR_REVISION and SCENE_SEGMENTER_REVISION to exact model commits before inference")
    image = Image.open(source["preview_path"]).convert("RGB")
    captions = {
        "I02": "building. conveyor. truck. tree.",
        "I03": "industrial vessel. tank. valve. pipe.",
        "G01": "shelf. checkout counter. refrigerator.",
        "G02": "industrial machine. conveyor. buffer.",
        "G03": "enclosure. tree. building. pond.",
    }
    processor = AutoProcessor.from_pretrained(detector_name, revision=detector_revision)
    detector = AutoModelForZeroShotObjectDetection.from_pretrained(detector_name, revision=detector_revision).to("cuda")
    inputs = processor(images=image, text=captions[case.id], return_tensors="pt").to("cuda")
    with torch.inference_mode():
        prediction = detector(**inputs)
    detected = processor.post_process_grounded_object_detection(
        prediction, inputs.input_ids, threshold=.3, text_threshold=.25, target_sizes=[image.size[::-1]],
    )[0]
    boxes = detected["boxes"].cpu().tolist()[:max_objects]
    labels = detected["text_labels"][:max_objects]
    scores = detected["scores"].cpu().tolist()[:max_objects]
    del detector, inputs, prediction
    torch.cuda.empty_cache()
    if not boxes:
        raise ValueError("No objects met the detector threshold; refine object phrases or manually annotate before retrying")
    sam_processor = Sam2Processor.from_pretrained(segmenter_name, revision=segmenter_revision)
    sam = Sam2Model.from_pretrained(segmenter_name, revision=segmenter_revision).to("cuda")
    encoded = sam_processor(images=image, input_boxes=[boxes], return_tensors="pt").to("cuda")
    with torch.inference_mode():
        masks = sam(**encoded, multimask_output=False)
    # Sam2's postprocessor returns original-resolution masks per image/object.
    masks_array = sam_processor.post_process_masks(masks.pred_masks.cpu(), encoded["original_sizes"])[0].numpy()
    scene = source_scene(case, source)
    output.mkdir(parents=True, exist_ok=True)
    width, height = image.size
    annotations = []
    for index, (box, label, score) in enumerate(zip(boxes, labels, scores)):
        x1, y1, x2, y2 = [int(value) for value in box]
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
        if x2 <= x1 or y2 <= y1:
            raise ValueError("Detector produced an invalid bounding box")
        identifier = f"object-{index:03d}"
        mask_array = masks_array[index].reshape(height, width)
        mask = Image.fromarray((mask_array > 0).astype(np.uint8) * 255)
        crop = image.convert("RGBA")
        crop.putalpha(mask)
        crop = crop.crop((x1, y1, x2, y2))
        crop.save(output / f"{identifier}.png")
        extent = max(.3, (x2 - x1) / width * 30)
        vertical = max(.3, (y2 - y1) / height * 8)
        scene.nodes.append(Node(
            id=identifier, label=f"{label} {index + 1}", category=label, shape="cylinder" if "tank" in label or "vessel" in label else "box",
            position=((x1 + x2 - width) / width * 15, vertical / 2, (y1 + y2 - height) / height * 10),
            size=(extent, vertical, max(.3, extent * .65)), color="#809fab",
            evidence=Evidence(origin="inferred", confidence=float(score), source_id="image", note="Mask grounded in image; 3D depth, scale and placement are provisional, not recovered dimensions."),
        ))
        annotations.append({"node_id": identifier, "bbox_pixels": [x1, y1, x2 - x1, y2 - y1], "crop": f"{identifier}.png", "score": score})
    report = {
        "method": "grounding-dino+sam2", "annotations": annotations, "reviewed": False,
        "detector": {"model": detector_name, "revision": detector_revision},
        "segmenter": {"model": segmenter_name, "revision": segmenter_revision},
        "warnings": ["Photo positions are an illustrative image-plane layout. No calibrated depth or process connectivity is inferred."],
    }
    (output / "extraction.json").write_text(json.dumps(report, indent=2))
    return scene, report
