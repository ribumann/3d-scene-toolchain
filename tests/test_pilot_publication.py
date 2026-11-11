import fcntl
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_static_demo import build_demo
from scripts.package_pilots import APPROVED_PINS, package_pilots, validate_package
from scripts.private_gpu_smoke import ROOT, SmokeError
import tests.test_private_gpu_batch as fixtures


class PilotPublicationTests(unittest.TestCase):
    def prepare(self, root, case="I02"):
        worker = fixtures.PrivateBatchTests()
        worker.setUp()
        worker.environment.update(APPROVED_PINS)
        worker.case_id = case
        worker.categories = ["tree"] if case == "I02" else ["region"]
        preview = root / f"{case}.webp"
        preview.write_bytes((ROOT / f"apps/web/public/references/{case}.webp").read_bytes())
        self.assertEqual(worker.run_private(root, preview)[0], 0)
        return worker

    def test_explicit_approval_packages_validated_outputs_not_originals_crops_logs_or_private_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare(root)
            self.prepare(root, "I01")
            destination = root / "publication"
            with self.assertRaisesRegex(SmokeError, "approval_required"):
                package_pilots(root, destination)
            self.assertFalse(destination.exists())
            manifest = package_pilots(root, destination, approve=True)
            statuses = {item["case_id"]: item["status"] for item in manifest["cases"]}
            self.assertEqual(statuses["I01"], "proposals")
            self.assertEqual(statuses["I02"], "succeeded")
            self.assertEqual(statuses["G01"], "not_run")
            files = {path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()}
            self.assertEqual(files, {"pilots.json", "scenes/I01.json", "scenes/I02.json", "assets/I02/object-000.ply"})
            contents = "\n".join(path.read_text() for path in destination.rglob("*.json"))
            for private in ("PRIVATE_TEST_TOKEN", "Sensitive private", "idol-private.log", "attempt-000", str(root)):
                self.assertNotIn(private, contents)
            scene = json.loads((destination / "scenes/I02.json").read_text())
            self.assertEqual(scene["assets"][0]["uri"], "/api/assets/pilot/I02/object-000.ply")
            self.assertTrue(scene["assets"][0]["provenance"]["not_original_bytes"])
            public = root / "public"
            build_demo(public, destination)
            self.assertTrue((public / "pilot-assets/pilot/I02/object-000.ply").exists())
            cases = json.loads((public / "demo/cases.json").read_text())
            self.assertEqual([case["id"] for case in cases if case["status"] == "ready"], ["P01", "P02", "P03", "I01", "I02"])
            self.assertFalse((public / "demo/I03.json").exists())
            self.assertEqual(json.loads((public / "demo/pilots.json").read_text())[0]["status"], "proposals")
            with self.assertRaisesRegex(ValueError, "Unexpected public demo content"):
                build_demo(public)

    def test_tampered_ply_and_unexpected_private_file_refuse_publication_or_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare(root)
            destination = root / "publication"
            package_pilots(root, destination, approve=True)
            (destination / "private-original.webp").write_bytes(b"private")
            with self.assertRaisesRegex(SmokeError, "unexpected_public_package_files"):
                validate_package(destination)
            (destination / "private-original.webp").unlink()
            (destination / "assets/I02/object-000.ply").write_bytes(b"invalid")
            with self.assertRaises(ValueError):
                build_demo(root / "public", destination)
            self.assertFalse((root / "public").exists())

    def test_changed_private_output_cannot_be_packaged_as_previous_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare(root)
            output = root / "assets/I02/object-batch-public-preview"
            state = json.loads((output / "batch.json").read_text())
            ply = output / state["objects"]["object-000"]["attempts"][-1]["directory"] / "object.ply"
            ply.write_bytes(b"not valid generated output")
            with self.assertRaises(ValueError):
                package_pilots(root, root / "publication", approve=True)
            self.assertFalse((root / "publication").exists())

    def test_running_cases_refuse_export_but_stopped_partial_exports_only_validated_objects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            worker = fixtures.PrivateBatchTests()
            worker.setUp()
            worker.environment.update(APPROVED_PINS)
            worker.categories = ["tree", "building"]
            worker.failures["object-001"] = SmokeError("synthetic_failed_inference")
            preview = root / "I02.webp"
            preview.write_bytes((ROOT / "apps/web/public/references/I02.webp").read_bytes())
            self.assertEqual(worker.run_private(root, preview)[0], 1)
            output = root / "assets/I02/object-batch-public-preview"
            destination = root / "publication"
            with (output / ".lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(SmokeError, "cannot_package_running_case"):
                    package_pilots(root, destination, approve=True)
            state = json.loads((output / "batch.json").read_text())
            state["status"] = "running"
            (output / "batch.json").write_text(json.dumps(state))
            with self.assertRaisesRegex(SmokeError, "stopped_case_checkpoint"):
                package_pilots(root, destination, approve=True)
            self.assertFalse(destination.exists())
            state["status"] = "interrupted"
            (output / "batch.json").write_text(json.dumps(state))
            manifest = package_pilots(root, destination, approve=True)
            entry = next(item for item in manifest["cases"] if item["case_id"] == "I02")
            self.assertEqual((entry["status"], entry["objects"], entry["failed_objects"]), ("partial", 1, 1))
            scene = json.loads((destination / entry["scene"]).read_text())
            self.assertEqual([node["id"] for node in scene["nodes"]], ["object-000"])
            entry["private_log"] = "private contents must not pass the publication boundary"
            (destination / "pilots.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(SmokeError, "unexpected_public_case_fields"):
                validate_package(destination)
