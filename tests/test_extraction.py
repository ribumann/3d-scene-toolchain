import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw

from scene_pipeline.extract import PrerequisiteError, extract_diagram, extract_photo
from scene_pipeline.store import Store


class ExtractionTests(unittest.TestCase):
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
