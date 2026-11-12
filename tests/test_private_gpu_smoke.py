import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw

from scene_pipeline.models import Evidence, Node, Scene
from scene_pipeline.store import Store
from scripts.private_gpu_smoke import PIN_NAMES, SmokeError, load_source, run_smoke, select_crop
from scripts.resolve_smoke_models import MODELS, ReadinessError, resolve_models


class PrivateSmokeTests(unittest.TestCase):
    def scene(self, categories):
        return Scene(
            id="I02", case_id="I02", name="Test", description="Synthetic selection fixture",
            nodes=[Node(
                id=f"object-{index:03d}", label=category, category=category,
                position=(0, 0, 0), size=(1, 1, 1), color="#ffffff",
                evidence=Evidence(origin="inferred", confidence=.9 - index * .1, note="Synthetic fixture"),
            ) for index, category in enumerate(categories)],
        )

    def crop(self, directory, identifier, kind="masked"):
        image = Image.new("RGBA", (64, 64), (100, 120, 140, 0 if kind != "opaque" else 255))
        if kind == "masked":
            ImageDraw.Draw(image).rectangle((8, 8, 55, 55), fill=(100, 120, 140, 255))
        image.save(directory / f"{identifier}.png")
        return {"node_id": identifier, "crop": f"{identifier}.png", "bbox_pixels": [0, 0, 64, 64]}

    def test_selects_valid_non_person_mask_and_reports_rejections(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            scene = self.scene(["person", "tree", "building"])
            annotations = [self.crop(folder, node.id, "empty" if index == 1 else "masked") for index, node in enumerate(scene.nodes)]
            crop, result = select_crop(scene, {"method": "grounding-dino+sam2", "annotations": annotations}, folder)
            self.assertEqual(crop.name, "object-002.png")
            self.assertEqual(result["selected_category"], "building")
            self.assertEqual(result["foreground_pixels"], 48 * 48)
            self.assertEqual(result["rejected_crops"], {"not_an_approved_non_person_object": 1, "empty_or_unsegmented_alpha": 1})

    def test_refuses_unsegmented_and_traversal_crops_without_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            scene = self.scene(["building"])
            annotation = self.crop(folder, scene.nodes[0].id, "opaque")
            extraction = {"method": "grounding-dino+sam2", "annotations": [annotation]}
            with self.assertRaisesRegex(SmokeError, "no_valid_non_person"):
                select_crop(scene, extraction, folder)
            annotation["crop"] = "../private-image.png"
            with self.assertRaisesRegex(SmokeError, "no_valid_non_person"):
                select_crop(scene, extraction, folder)

    def test_private_source_rebases_store_layout_and_verifies_preview(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = Store(root)
            stream = io.BytesIO()
            Image.new("RGB", (64, 64), "green").save(stream, format="PNG")
            digest = store.save_source("I02", stream.getvalue(), stream.getvalue(), "private-original.png")
            source, kind = load_source(root)
            self.assertEqual(kind, "private-original")
            self.assertEqual(source["sha256"], digest)
            preview = root / "sources/I02" / digest / "preview.png"
            Image.new("RGB", (64, 64), "red").save(preview)
            with self.assertRaisesRegex(SmokeError, "preview_does_not_match"):
                load_source(root)

    def test_public_preview_records_its_own_bytes_not_original_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            preview = root / "public.webp"
            Image.new("RGB", (64, 64), "blue").save(preview, format="WEBP")
            source, kind = load_source(root, preview)
            self.assertEqual(kind, "public-webp-preview")
            self.assertEqual(source["sha256"], hashlib.sha256(preview.read_bytes()).hexdigest())
            self.assertEqual(source["filename"], "I02-public-preview.webp")

    def test_failure_report_does_not_expose_raw_private_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = io.StringIO()
            environment = {name: "a" * 40 for name in PIN_NAMES}
            environment["HF_TOKEN"] = "SENSITIVE_TEST_TOKEN"
            with patch.dict(os.environ, environment), patch(
                "scripts.private_gpu_smoke.load_source",
                side_effect=OSError("service envelope SENSITIVE_TEST_TOKEN private account"),
            ), redirect_stdout(output):
                result = run_smoke(Path(temporary), Path(temporary) / "output", None)
            self.assertEqual(result, 1)
            report = json.loads(output.getvalue())
            self.assertEqual(report["status"], "failed")
            self.assertNotIn("SENSITIVE_TEST_TOKEN", output.getvalue())
            self.assertNotIn("service envelope", output.getvalue())


class ModelReadinessTests(unittest.TestCase):
    def test_downloads_actual_gated_configs_at_resolved_immutable_pins(self):
        with tempfile.TemporaryDirectory() as temporary:
            calls = []
            api = SimpleNamespace(model_info=lambda repo_id, token: SimpleNamespace(sha=hashlib.sha1(repo_id.encode()).hexdigest()))
            def download(**arguments):
                calls.append(arguments)
                config = {"image_encoders": {"dinov3": MODELS["dinov3_revision"], "flux2_vae": MODELS["flux2_revision"]}} if arguments["repo_id"] == MODELS["idol_revision"] else {}
                path = Path(temporary) / f"{len(calls)}.json"
                path.write_text(json.dumps(config))
                return path
            pins = resolve_models(api, download, "not-a-real-token", temporary)
            self.assertEqual(len(pins), 5)
            self.assertEqual([call["filename"] for call in calls], ["config.json", "vae/config.json", "config.json"])
            for call in calls:
                self.assertEqual(call["revision"], hashlib.sha1(call["repo_id"].encode()).hexdigest())
                self.assertTrue(call["force_download"])

    def test_rejects_mutable_revision_before_download(self):
        api = SimpleNamespace(model_info=lambda **kwargs: SimpleNamespace(sha="main"))
        with self.assertRaises(ReadinessError):
            resolve_models(api, lambda **kwargs: self.fail("must not download mutable revision"), "fake", "/unused")
