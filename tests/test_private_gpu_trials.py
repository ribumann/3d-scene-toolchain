"""Synthetic orchestration checks, never evidence of actual trial inference."""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from scene_pipeline.models import Case
from scripts.package_pilots import APPROVED_PINS
from scripts.private_gpu_batch import digest, write_json
from scripts.private_gpu_smoke import SmokeError
from scripts.private_gpu_trials import SETTINGS, crop_plan, generation_key, run_trial, stage_sources
from scripts.trial_contracts import Trial, TrialManifest
import tests.test_private_gpu_batch as fixtures


def trial_fixture(root):
    source = root / "approved-trials/T01.png"
    source.parent.mkdir()
    Image.new("RGB", (256, 256), "white").save(source)
    return Trial.model_validate({
        "id": "T01", "title": "Synthetic pump trial",
        "source": {
            "filename": "T01.png", "sha256": digest(source),
            "url": "https://raw.githubusercontent.com/ribumann/3d-scene-toolchain/" + "a" * 40 + "/trials/T01.png",
            "kind": "generated-photographic-scene",
            "generator": "Copilot image_generation tool; underlying image model/version not exposed",
            "prompt": "Explicit synthetic unit-test fixture, not an actual generated trial.",
            "publication_approved": True,
        },
        "detector_phrases": ["pump"], "expected_inventory": [{"identity": "pump-a", "category": "pump", "count": 1}],
        "reviewed_objects": [{"id": "pump-a", "identity": "pump-a", "category": "pump", "box": [0, 0, .5, .5], "reviewed": True}],
    })


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.worker = fixtures.PrivateBatchTests()
        self.worker.setUp()
        self.worker.environment.update(APPROVED_PINS)
        self.calls = []
        self.fail_stage = False
        self.interrupt = False

    def stage(self, arguments, log, timeout, measurement):
        measurement["seconds"] = 1.0
        if "extract" in arguments:
            folder = Path(arguments[arguments.index("--output") + 1])
            self.worker.case_id = "T01"
            scene, report = self.worker.extraction(folder, {"filename": "T01.png", "sha256": self.trial.source.sha256}, ["pump"])
            report["annotations"][0].update(identity="pump-a", reviewed_id="pump-a")
            if arguments[arguments.index("--variants") + 1] == "optimized":
                report["method"] = "reviewed-boxes+sam2"
            write_json(folder / "extraction.json", report)
            self.calls.append("extract")
        else:
            crop = Path(arguments[arguments.index("--image") + 1])
            folder = Path(arguments[arguments.index("--out") + 1])
            self.calls.append("idol")
            if self.fail_stage:
                self.fail_stage = False
                raise SmokeError("synthetic_stage_failure")
            self.worker.generation(folder, crop)
            if self.interrupt:
                self.interrupt = False
                raise KeyboardInterrupt

    def run_variant(self, root, manifest, variant):
        with patch.dict(os.environ, self.worker.environment), patch("scripts.private_gpu_trials.run_stage", side_effect=self.stage), redirect_stdout(io.StringIO()):
            return run_trial(root, manifest, self.trial, variant)

    def prepare(self, root):
        self.trial = trial_fixture(root)
        manifest = root / "manifest.json"
        write_json(manifest, TrialManifest(schema_version=1, trials=[self.trial]).model_dump())
        return manifest

    def test_exact_cross_variant_cache_and_resume_revalidate_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.prepare(root)
            baseline = self.run_variant(root, manifest, "baseline")
            self.assertEqual((baseline["status"], baseline["independent_generations"]), ("succeeded", 1))
            optimized = self.run_variant(root, manifest, "optimized")
            self.assertEqual((optimized["status"], optimized["cache_hits"], optimized["independent_generations"]), ("succeeded", 1, 0))
            self.assertEqual(self.calls.count("idol"), 1)
            resumed = self.run_variant(root, manifest, "optimized")
            self.assertEqual(resumed["resumed"], 1)
            cache = next((root / "trials/cache").iterdir())
            (cache / "object.ply").write_bytes(b"corrupted")
            invalid = self.run_variant(root, manifest, "optimized")
            self.assertEqual(invalid["status"], "failed")
            self.assertEqual(invalid["objects"][0]["resume_rejected"], "trial_resume_revalidation_failed")
            self.assertEqual(self.calls.count("idol"), 1)

    def test_failures_are_not_cached_and_interrupted_completed_output_can_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.prepare(root)
            self.fail_stage = True
            failed = self.run_variant(root, manifest, "baseline")
            self.assertEqual(failed["status"], "failed")
            self.assertFalse((root / "trials/cache").exists())
            self.interrupt = True
            interrupted = self.run_variant(root, manifest, "baseline")
            self.assertEqual(interrupted["status"], "interrupted")
            result = self.run_variant(root, manifest, "baseline")
            self.assertEqual((result["status"], result["resumed"]), ("succeeded", 1))
            self.assertEqual(self.calls, ["extract", "idol", "idol"])

    def test_settings_and_manifest_changes_refuse_resume_and_cache_key_changes_with_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.prepare(root)
            self.run_variant(root, manifest, "baseline")
            key = generation_key("a" * 64)
            with patch.dict(SETTINGS, {"seed": 99}):
                self.assertNotEqual(generation_key("a" * 64), key)
                result = self.run_variant(root, manifest, "baseline")
            self.assertEqual(result["failure_reason"], "trial_manifest_or_settings_resume_mismatch")
            self.assertEqual(self.calls.count("idol"), 1)

    def test_duplicate_masks_need_reviewed_identity_and_tiny_crops_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.trial = trial_fixture(root)
            scene, report = self.worker.extraction(root / "extraction", {"filename": "T01.png", "sha256": self.trial.source.sha256}, ["pump"] * 4)
            scene.case_id = "T01"
            folder = root / "extraction"
            for index in (1, 2):
                (folder / f"object-{index:03d}.png").write_bytes((folder / "object-000.png").read_bytes())
            report["annotations"][0]["identity"] = report["annotations"][1]["identity"] = "pump-a"
            report["annotations"][2]["identity"] = "pump-b"
            Image.new("RGBA", (8, 8)).save(folder / "object-003.png")
            candidates, rejected = crop_plan(scene, report, folder, self.trial, "optimized")
            self.assertEqual([item["node_id"] for item in candidates], ["object-000", "object-002"])
            self.assertEqual([item["reason"] for item in rejected], ["duplicate_reviewed_identity_and_mask", "degenerate_or_tiny_crop"])
            baseline, _ = crop_plan(scene, report, folder, self.trial, "baseline")
            self.assertEqual(len(baseline), 3)

    def test_manifest_rejects_private_sources_people_and_unapproved_instancing(self):
        with tempfile.TemporaryDirectory() as temporary:
            trial = trial_fixture(Path(temporary))
            for field, value in (("url", "file:///private/original.png"), ("publication_approved", False)):
                data = trial.model_dump()
                data["source"][field] = value
                with self.assertRaises(ValueError):
                    Trial.model_validate(data)
            data = trial.model_dump()
            data["instances"] = [
                {"id": identifier, "object_id": "pump-a", "position": [index, 0, 0], "size": [1, 1, 1]}
                for index, identifier in enumerate(("instance-a", "instance-b"))
            ]
            with self.assertRaisesRegex(ValueError, "explicit reusable asset"):
                Trial.model_validate(data)

    def test_staging_rejects_wrong_hash_redirect_and_oversize_without_partial_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.prepare(root)
            source = root / "approved-trials/T01.png"
            original = source.read_bytes()
            source.unlink()
            for content, url, reason in (
                (b"incorrect", self.trial.source.url, "checksum_mismatch"),
                (original, "https://example.com/redirect.png", "redirect_refused"),
                (b"x" * (12 * 1024 * 1024 + 1), self.trial.source.url, "exceeds_12mib"),
            ):
                response = io.BytesIO(content)
                response.geturl = lambda: url
                with patch("scripts.private_gpu_trials.urllib.request.urlopen", return_value=response):
                    with self.assertRaisesRegex(SmokeError, reason):
                        stage_sources(root, manifest)
                self.assertFalse(source.exists())
                self.assertFalse((source.parent / "T01.png.partial").exists())
