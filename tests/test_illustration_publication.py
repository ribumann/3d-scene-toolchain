"""Synthetic publication fixtures, not evidence of generated image quality."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from scripts.generated_references import Manifest, contract
from scripts.package_illustrations import ROOT, package_illustrations, validate_illustration_package
from scripts.package_pilots import APPROVED_PINS
from scripts.private_gpu_batch import digest, write_json
import tests.test_private_gpu_batch as fixtures


class IllustrationPublicationTests(unittest.TestCase):
    def prepare(self, root):
        authorization = root / "authorization"
        (authorization / "cases").mkdir(parents=True)
        shutil.copyfile(ROOT / "cases/illustrations.json", authorization / "cases/illustrations.json")
        concepts = Manifest.model_validate_json((authorization / "cases/illustrations.json").read_text()).concepts
        selected = {"grocery-shelf", "wafer-loader", "tree", "slurry-pump", "assembly-station", "factory-building"}
        generated = root / "generated"
        generated.mkdir()
        crop = root / "synthetic-crop.png"
        Image.new("RGB", (64, 64), "white").save(crop)
        worker = fixtures.PrivateBatchTests()
        worker.setUp()
        worker.environment.update(APPROVED_PINS)
        worker.generation(generated, crop)
        base = json.loads((generated / "generation.json").read_text())
        appearances, reviews = {}, []
        for concept in concepts:
            if concept.id not in selected:
                continue
            review = {
                "id": concept.id, "sha256": digest(crop), "box": [.1, .1, .8, .8],
                "reviewed": True, "note": "Synthetic test fixture; no actual visual quality claim.",
            }
            reviews.append(review)
            shutil.copyfile(generated / "object.ply", generated / f"{concept.id}.ply")
            appearances[concept.id] = {
                **base, "dinov3_dtype": "fp32", "camera": {"not_public": str(root)},
                "reference": {
                    "contract": contract(concept), "sha256": digest(crop), "seconds": 1.0,
                    "libraries": {name: "1.0.0" for name in ("torch", "diffusers", "transformers", "accelerate")},
                    "reviewed": False, "limitations": "Invented appearance from a description; not recovered from a schema.",
                },
                "review": review, "segmentation": "reviewed-box+SAM2",
                "crop_sha256": digest(crop), "illustrative": True, "resumed": False,
                "timing_this_run": {"seconds": 1, "peak_device_memory_mib_sampled": 100, "sample_interval_seconds": 2},
            }
        write_json(generated / "appearances.json", appearances)
        write_json(authorization / "cases/illustration-reviews.json", {"schema_version": 1, "objects": reviews})
        return authorization, generated

    def test_strict_publication_strips_camera_and_rejects_extra_files_and_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            authorization, generated = self.prepare(root)
            publication = root / "publication"
            with patch("scripts.package_illustrations.ROOT", authorization):
                manifest = package_illustrations(generated, publication)
                self.assertEqual(len(manifest["cases"]), 6)
                public = (publication / "appearances.json").read_text()
                self.assertNotIn(str(root), public)
                self.assertNotIn('"camera"', public)
                (publication / "private.log").write_text("private")
                with self.assertRaisesRegex(ValueError, "package files"):
                    validate_illustration_package(publication)
                (publication / "private.log").unlink()
                path = publication / "appearances.json"
                appearances = json.loads(path.read_text())
                next(iter(appearances.values()))["private_log"] = "not public"
                write_json(path, appearances)
                manifest["files"]["appearances.json"] = digest(path)
                write_json(publication / "publication.json", manifest)
                with self.assertRaisesRegex(ValueError, "public metadata"):
                    validate_illustration_package(publication)

    def test_rehashed_scene_cannot_forge_reviewed_relationships(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            authorization, generated = self.prepare(root)
            publication = root / "publication"
            with patch("scripts.package_illustrations.ROOT", authorization):
                manifest = package_illustrations(generated, publication)
                name = "scenes/I04-illustrated.json"
                path = publication / name
                scene = json.loads(path.read_text())
                scene["edges"][0]["evidence"]["note"] = "Forged measured physical connection"
                write_json(path, scene)
                manifest["files"][name] = digest(path)
                write_json(publication / "publication.json", manifest)
                with self.assertRaisesRegex(ValueError, "reviewed layout"):
                    validate_illustration_package(publication)
