import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.package_trials import package_trials, validate_trial_package
from scripts.private_gpu_smoke import SmokeError
import tests.test_private_gpu_trials as fixtures


class TrialPublicationTests(unittest.TestCase):
    def prepare(self, root):
        worker = fixtures.TrialTests()
        worker.setUp()
        manifest = worker.prepare(root)
        worker.run_variant(root, manifest, "baseline")
        worker.run_variant(root, manifest, "optimized")
        return manifest

    def test_explicit_trial_publication_excludes_crops_logs_and_private_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.prepare(root)
            destination = root / "publication"
            with self.assertRaisesRegex(SmokeError, "approval_required"):
                package_trials(root, destination, manifest)
            package = package_trials(root, destination, manifest, approve=True)
            self.assertEqual([item["status"] for item in package["trials"]], ["succeeded", "succeeded"])
            validate_trial_package(destination, manifest)
            files = {path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()}
            self.assertEqual(files, {
                "trials.json", "trial-manifest.json", "references/T01.png",
                "scenes/T01-baseline.json", "scenes/T01-optimized.json",
                "assets/T01/baseline/object-000.ply", "assets/T01/optimized/object-000.ply",
            })
            contents = "\n".join(path.read_text() for path in destination.rglob("*.json"))
            for private in (str(root), "PRIVATE_TEST_TOKEN", "idol-private.log", "attempt-000"):
                self.assertNotIn(private, contents)
            (destination / "private.log").write_text("private")
            with self.assertRaisesRegex(SmokeError, "unexpected_trial_package_files"):
                validate_trial_package(destination, manifest)

    def test_tampered_generation_is_not_published_and_active_case_is_skipped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.prepare(root)
            checkpoint = root / "trials/T01/baseline/trial.json"
            state = json.loads(checkpoint.read_text())
            state["status"] = "running"
            checkpoint.write_text(json.dumps(state))
            package = package_trials(root, root / "first", manifest, approve=True)
            self.assertEqual(package["trials"][0]["status"], "processing")
            self.assertIsNone(package["trials"][0]["scene"])
            self.assertFalse((root / "first/assets/T01/baseline").exists())
            output = root / "trials/T01/optimized/trial.json"
            state = json.loads(output.read_text())
            cached = root / state["successes"]["object-000"]["directory"] / "object.ply"
            cached.write_bytes(b"corrupted")
            with self.assertRaises(ValueError):
                package_trials(root, root / "second", manifest, approve=True)
            self.assertFalse((root / "second").exists())
