"""Compare equivalent crop preparation on completed real-photo SAM extractions."""

import argparse
import gc
import io
import json
import statistics
import time
from pathlib import Path

import numpy as np
from PIL import Image

from scene_pipeline.extract import masked_crop
from scripts.private_gpu_batch import private_path, snapshot_extraction
from scripts.private_gpu_trials import source_path
from scripts.trial_contracts import load_manifest


def legacy_crop(image, mask, box):
    result = image.convert("RGBA")
    result.putalpha(Image.fromarray((mask > 0).astype(np.uint8) * 255))
    return result.crop(box)


def png_bytes(image):
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def benchmark(directory, manifest, repeats=25):
    if not 5 <= repeats <= 1000:
        raise ValueError("Use 5 to 1000 paired repetitions")
    results = []
    for trial in load_manifest(manifest).trials:
        if trial.source.kind != "licensed-real-photograph":
            continue
        output = private_path(directory, f"trials/{trial.id}/optimized")
        state = json.loads(private_path(output, "trial.json").read_text())
        if state["status"] != "succeeded":
            raise ValueError("Benchmark requires a completed successful real-photo extraction")
        folder = private_path(output, state["extraction"]["directory"])
        if snapshot_extraction(folder) != state["extraction"]["files"]:
            raise ValueError("Extraction changed since inference")
        with Image.open(source_path(directory, trial)) as source:
            image = source.convert("RGB")
        extraction = json.loads(private_path(folder, "extraction.json").read_text())
        for item in extraction["annotations"]:
            x1, y1, width, height = item["bbox_pixels"]
            box = (x1, y1, x1 + width, y1 + height)
            _, _, x2, y2 = box
            with Image.open(private_path(folder, item["crop"])) as saved:
                crop = saved.convert("RGBA")
            mask = np.zeros((image.height, image.width), dtype=np.uint8)
            mask[y1:y2, x1:x2] = np.asarray(crop.getchannel("A"))
            legacy = legacy_crop(image, mask, box)
            optimized = masked_crop(image, mask, box)
            if not (legacy.tobytes() == optimized.tobytes() == crop.tobytes()
                    and png_bytes(legacy) == png_bytes(optimized)):
                raise ValueError("Crop preparation changed actual SAM crop pixels or PNG bytes")
            samples = {"legacy": [], "crop_first": []}
            operations = {"legacy": legacy_crop, "crop_first": masked_crop}
            for operation in operations.values():
                for _ in range(3):
                    operation(image, mask, box).close()
            for index in range(repeats):
                order = ("legacy", "crop_first") if index % 2 == 0 else ("crop_first", "legacy")
                for name in order:
                    gc.collect()
                    started = time.perf_counter()
                    result = operations[name](image, mask, box)
                    samples[name].append((time.perf_counter() - started) * 1000)
                    result.close()
            results.append({
                "trial_id": trial.id, "node_id": item["node_id"],
                "source_sha256": trial.source.sha256, "bbox_pixels": item["bbox_pixels"],
                "source_pixels": image.width * image.height, "crop_pixels": crop.width * crop.height,
                "pixels_and_png_identical": True, "paired_repetitions": repeats,
                "median_ms": {name: round(statistics.median(values), 4) for name, values in samples.items()},
            })
    if not results:
        raise ValueError("Manifest contains no completed real-photo targets")
    return {
        "scope": "CPU crop preparation only; excludes segmentation, PNG encoding, GPU sampling and annotation",
        "masks": "Actual saved SAM alpha inside each crop; outside-crop mask values are irrelevant to output",
        "timing": "Alternating paired order after warmup; no end-to-end speedup or peak-RSS claim",
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=25)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.data_dir, args.manifest, args.repeats), indent=2))


if __name__ == "__main__":
    main()
