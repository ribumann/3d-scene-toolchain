import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from scene_pipeline.extract import PrerequisiteError, extract_diagram, extract_photo
from scene_pipeline.store import Store


class ExtractionTests(unittest.TestCase):
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
