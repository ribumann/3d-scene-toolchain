import hashlib
import io
import json
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from scene_pipeline.extract import PrerequisiteError, extract_diagram, extract_photo, masked_crop
from scene_pipeline.store import Store


class ExtractionTests(unittest.TestCase):
    def test_benchmark_uses_saved_alpha_and_offset_xywh_boxes(self):
        from scripts.benchmark_masked_crop import benchmark
        from scripts.private_gpu_batch import digest, snapshot_extraction, write_json
        from scripts.private_gpu_smoke import ROOT
        from scripts.trial_contracts import load_manifest

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = root / "approved-trials"
            sources.mkdir()
            image = Image.new("RGB", (40, 30), "blue")
            image.save(sources / "R01.png")
            data = next(trial for trial in load_manifest(ROOT / "cases/trials.json").trials if trial.id == "R01").model_dump(mode="json")
            data["source"]["sha256"] = digest(sources / "R01.png")
            manifest = root / "manifest.json"
            write_json(manifest, {"schema_version": 1, "trials": [data]})
            folder = root / "trials/R01/optimized/extraction-000"
            folder.mkdir(parents=True)
            mask = np.zeros((30, 40), dtype=np.uint8)
            mask[8:17, 7:25] = 1
            masked_crop(image, mask, (5, 6, 30, 20)).save(folder / "object-000.png")
            write_json(folder / "extraction.json", {"annotations": [{"node_id": "object-000", "crop": "object-000.png", "bbox_pixels": [5, 6, 25, 14]}]})
            checkpoint = folder.parent / "trial.json"
            write_json(checkpoint, {"status": "succeeded", "extraction": {"directory": folder.name, "files": snapshot_extraction(folder)}})
            result = benchmark(root, manifest, repeats=5)["results"][0]
            self.assertTrue(result["pixels_and_png_identical"])
            self.assertEqual(result["crop_pixels"], 25 * 14)
            state = json.loads(checkpoint.read_text())
            state["status"] = "running"
            write_json(checkpoint, state)
            with self.assertRaisesRegex(ValueError, "completed successful"):
                benchmark(root, manifest, repeats=5)

    def test_crop_first_matches_full_frame_rgba_pixels_and_encoded_png_at_edges(self):
        image = Image.fromarray(np.arange(19 * 23 * 3, dtype=np.uint8).reshape(19, 23, 3))
        for mask in (
            np.ones((19, 23), dtype=bool),
            np.zeros((19, 23), dtype=bool),
            np.arange(19 * 23).reshape(19, 23) % 3 - 1,
        ):
            for box in ((0, 0, 23, 19), (0, 0, 1, 1), (22, 18, 23, 19), (3, 5, 17, 16)):
                with self.subTest(box=box, foreground=int(np.count_nonzero(mask > 0))):
                    legacy = image.convert("RGBA")
                    legacy.putalpha(Image.fromarray((mask > 0).astype(np.uint8) * 255))
                    legacy = legacy.crop(box)
                    optimized = masked_crop(image, mask, box)
                    self.assertEqual(optimized.tobytes(), legacy.tobytes())
                    encoded = [io.BytesIO(), io.BytesIO()]
                    legacy.save(encoded[0], format="PNG")
                    optimized.save(encoded[1], format="PNG")
                    self.assertEqual(encoded[0].getvalue(), encoded[1].getvalue())

    def test_masked_crop_rejects_mismatched_mask_and_invalid_boxes(self):
        image = Image.new("RGB", (20, 10))
        with self.assertRaisesRegex(ValueError, "source-sized mask"):
            masked_crop(image, np.zeros((9, 20)), (0, 0, 5, 5))
        for box in ((-1, 0, 3, 3), (0, 0, 21, 10), (2, 2, 2, 3)):
            with self.assertRaisesRegex(ValueError, "in-bounds box"):
                masked_crop(image, np.zeros((10, 20)), box)

    @unittest.skipUnless(importlib.util.find_spec("cv2"), "OCR extra required")
    def test_pilot_diagrams_can_include_more_than_100_regions_without_invented_topology(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = Image.new("RGB", (1200, 1000), "white")
            draw = ImageDraw.Draw(image)
            for row in range(10):
                for column in range(12):
                    x, y = 10 + column * 98, 10 + row * 98
                    draw.rectangle((x, y, x + 65, y + 60), outline="black", width=3)
            path = root / "synthetic-diagram.png"
            image.save(path)
            source = {"preview_path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "filename": path.name}
            case = Store(root / "data").definition("I01")
            def ocr(arguments, **kwargs):
                return SimpleNamespace(stdout="eng\n" if "--list-langs" in arguments else "level\tconf\ttext\n")
            with patch("scene_pipeline.extract.shutil.which", return_value="/mock/tesseract"), patch(
                "scene_pipeline.extract.subprocess.run", side_effect=ocr,
            ):
                limited, _ = extract_diagram(case, source, root / "local")
                all_regions, report = extract_diagram(case, source, root / "pilot", max_regions=None)
            self.assertEqual(len(limited.nodes), 100)
            self.assertGreater(len(all_regions.nodes), 100)
            self.assertFalse(all_regions.assets)
            self.assertFalse(all_regions.edges)
            self.assertEqual(report["topology_status"], "not_extracted")
            self.assertTrue(all(node.evidence.origin == "inferred" and not node.evidence.reviewed for node in all_regions.nodes))

    def test_photo_missing_runtime_is_not_success(self):
        if importlib.util.find_spec("torch") and importlib.util.find_spec("transformers"):
            self.skipTest("GPU/model behavior is verified separately on an actual model worker")
        with tempfile.TemporaryDirectory() as temporary:
            store = Store(temporary)
            with self.assertRaises(PrerequisiteError):
                extract_photo(store.definition("I02"), {}, Path(temporary) / "output")

    @unittest.skipUnless(importlib.util.find_spec("cv2") and shutil.which("tesseract"), "OCR extra and Tesseract required")
    def test_synthetic_diagram_regions_are_unreviewed_without_invented_edges(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            image = Image.new("RGB", (800, 600), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((70, 100, 260, 260), outline="black", width=4)
            draw.rectangle((450, 300, 710, 520), outline="black", width=4)
            draw.line((260, 180, 500, 180), fill="black", width=3)
            path = folder / "synthetic.png"
            image.save(path)
            store = Store(folder / "data")
            source = {"preview_path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "filename": path.name}
            scene, report = extract_diagram(store.definition("I01"), source, folder / "result")
            self.assertTrue(scene.nodes)
            self.assertEqual(scene.edges, [])
            self.assertEqual(report["topology_status"], "not_extracted")
            self.assertTrue(all(not node.evidence.reviewed for node in scene.nodes))
            self.assertTrue((folder / "result/extraction.json").exists())
            self.assertEqual(scene.sources[0].sha256, source["sha256"])


if __name__ == "__main__":
    unittest.main()
