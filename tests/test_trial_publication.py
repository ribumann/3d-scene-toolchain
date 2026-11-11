import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.package_trials import package_trials, safe_report, validate_trial_package
from scripts.private_gpu_smoke import SmokeError
from scripts.build_static_demo import build_demo
from scripts.package_pilots import APPROVED_PINS, package_pilots
from scripts.private_gpu_smoke import ROOT
import tests.test_private_gpu_trials as fixtures
import tests.test_private_gpu_batch as pilot_fixtures


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
        import fcntl
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.prepare(root)
            checkpoint = root / "trials/T01/baseline/trial.json"
            completed = checkpoint.read_bytes()
            with checkpoint.with_name(".lock").open("rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                checkpoint.write_text("invalid active checkpoint must not be read")
                active = package_trials(root, root / "locked", manifest, approve=True)
                self.assertEqual(active["trials"][0]["status"], "processing")
                self.assertIsNone(active["trials"][0]["scene"])
            checkpoint.write_bytes(completed)
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

    def test_trial_build_is_additive_and_refuses_to_drop_complete_pilot_baseline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.prepare(root)
            trial_package = root / "trial-package"
            package_trials(root, trial_package, manifest, approve=True)
            with self.assertRaisesRegex(ValueError, "complete approved eight-source"):
                build_demo(root / "unsafe", trial_package=trial_package)
            self.assertFalse((root / "unsafe").exists())
            for case, category in (
                ("I01", "region"), ("I02", "tree"), ("I03", "tank"), ("I04", "region"),
                ("I05", "region"), ("G01", "shelf"), ("G02", "conveyor"), ("G03", "tree"),
            ):
                worker = pilot_fixtures.PrivateBatchTests()
                worker.setUp()
                worker.environment.update(APPROVED_PINS)
                worker.case_id, worker.categories = case, [category]
                preview = root / f"{case}.webp"
                preview.write_bytes((ROOT / f"apps/web/public/references/{case}.webp").read_bytes())
                self.assertEqual(worker.run_private(root, preview)[0], 0)
            pilot_package = root / "pilot-package"
            package_pilots(root, pilot_package, approve=True)
            public = root / "public"
            with patch("scripts.package_trials.APPROVED_MANIFEST", manifest):
                build_demo(public, pilot_package, trial_package)
                build_demo(public, pilot_package, trial_package)
            for source in (pilot_package / "scenes").iterdir():
                self.assertEqual(source.read_bytes(), (public / "demo" / source.name).read_bytes())
            self.assertTrue((public / "trial-assets/T01/baseline/object-000.ply").is_file())
            self.assertTrue((public / "trial-references/T01.png").is_file())
            cases = json.loads((public / "demo/cases.json").read_text())
            self.assertEqual(len([case for case in cases if case["status"] == "ready"]), 13)
            statuses = json.loads((public / "demo/trials.json").read_text())
            self.assertEqual(statuses[1]["variant"], "optimized")
            self.assertIn("definition", statuses[0])
            with self.assertRaisesRegex(ValueError, "Unexpected public demo content"):
                build_demo(public)

    def test_portable_validation_rejects_unsafe_diagnostics_and_requires_real_scene(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.prepare(root)
            destination = root / "publication"
            package = package_trials(root, destination, manifest, approve=True)
            report = package["trials"][0]["report"]
            for field, value in (("seconds_this_run", float("nan")), ("detected_objects", "/private/input.png")):
                with self.assertRaisesRegex(SmokeError, "unsafe_trial_"):
                    safe_report({**report, field: value})
            report["objects"][0]["status"] = "/private/unsafe.log"
            with self.assertRaisesRegex(SmokeError, "unsafe_trial_object_status"):
                safe_report(report)
            portable = subprocess.run([sys.executable, "-c", """
import builtins, sys
from pathlib import Path
original_import = builtins.__import__
def without_fcntl(name, *args, **kwargs):
    if name == "fcntl":
        raise ImportError("Simulated Windows: no fcntl")
    return original_import(name, *args, **kwargs)
builtins.__import__ = without_fcntl
from scripts.package_trials import package_trials, validate_trial_package
from scripts.private_gpu_smoke import SmokeError
root = Path(sys.argv[1])
validate_trial_package(root / "publication", root / "manifest.json")
try:
    package_trials(root, root / "unsupported-export", root / "manifest.json", approve=True)
except SmokeError as error:
    assert str(error) == "trial_export_requires_POSIX_flock"
else:
    raise AssertionError("Private trial export must not bypass locking")
""", str(root)], capture_output=True, text=True)
            self.assertEqual(portable.returncode, 0, portable.stderr)
            report["objects"][0]["status"] = "succeeded"
            package["trials"][0]["scene"] = None
            (destination / "trials.json").write_text(json.dumps(package))
            with self.assertRaisesRegex(SmokeError, "completed_trial_scene_missing"):
                validate_trial_package(destination, manifest)
