import io
import os
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from scene_pipeline.api import create_app
from scene_pipeline.gaussians import assess_ply, validate_ply
from scene_pipeline.jobs import Runner
from scene_pipeline.models import JobRequest, Scene
from scene_pipeline.store import ConflictError, Store


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = Store(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()


class SceneContractTests(Fixture):
    def test_eleven_cases_and_three_real_prompt_scenes(self):
        self.assertEqual(len(self.store.cases()), 11)
        for case in self.store.cases():
            if case.id.startswith("P"):
                scene = self.store.current(case.id)
                self.assertGreater(len(scene.nodes), 20)
                self.assertTrue(scene.edges)
                self.assertTrue(all(not node.evidence.reviewed for node in scene.nodes))
                self.assertTrue(all(node.evidence.origin == "generated" for node in scene.nodes))
            else:
                self.assertIsNone(self.store.current(case.id))
                self.assertEqual(case.status, "awaiting_input")

    def test_duplicate_ids_rejected(self):
        scene = self.store.current("P01").model_dump()
        scene["nodes"].append(scene["nodes"][0])
        with self.assertRaises(ValidationError):
            Scene.model_validate(scene)

    def test_dangling_edge_rejected(self):
        scene = self.store.current("P02").model_dump()
        scene["edges"][0]["source"] = "missing"
        with self.assertRaises(ValidationError):
            Scene.model_validate(scene)

    def test_nonfinite_and_nonpositive_dimensions_rejected(self):
        for value in (float("nan"), 0, -1):
            scene = self.store.current("P01").model_dump()
            scene["nodes"][0]["size"] = (value, 1, 1)
            with self.assertRaises(ValidationError):
                Scene.model_validate(scene)

    def test_source_reference_rejected(self):
        scene = self.store.current("P01").model_dump()
        scene["nodes"][0]["evidence"]["source_id"] = "unknown"
        with self.assertRaises(ValidationError):
            Scene.model_validate(scene)

    def test_optimistic_revision(self):
        first = self.store.current("P01")
        second = self.store.save(first, expected_revision=1)
        self.assertEqual(second.revision, 2)
        with self.assertRaises(ConflictError):
            self.store.save(first, expected_revision=1)
        self.assertEqual(self.store.current("P01").revision, 2)

    def test_asset_traversal(self):
        for path in ("../scene.sqlite3", "/etc/passwd"):
            with self.assertRaises(ValueError):
                self.store.asset_path(path)

    def test_restart_preserves_edits(self):
        scene = self.store.current("P01")
        scene.nodes[0].label = "Edited floor"
        self.store.save(scene, expected_revision=1, manual=True)
        other = Store(self.temporary.name)
        self.assertEqual(other.current("P01").nodes[0].label, "Edited floor")
        self.assertTrue(other.has_manual_edits("P01"))

    def test_job_order_rejected(self):
        for stages in (["idol", "extract"], ["extract", "extract"], []):
            with self.assertRaises(ValidationError):
                JobRequest(stages=stages)


class ApiTests(Fixture):
    def setUp(self):
        super().setUp()
        self.app = create_app(self.temporary.name)
        self.client_context = TestClient(self.app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        super().tearDown()

    def image(self, color="blue"):
        output = io.BytesIO()
        Image.new("RGB", (64, 48), color).save(output, "PNG")
        return output.getvalue()

    def upload(self, case="I02", color="blue"):
        return self.client.post(f"/api/cases/{case}/source", files={"file": ("sample.png", self.image(color), "image/png")})

    def test_cases_and_waiting_state(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(len(self.client.get("/api/cases").json()), 11)
        self.assertEqual(self.client.get("/api/cases/I01/scene").status_code, 409)
        self.assertEqual(self.client.get("/api/cases/nope/scene").status_code, 404)

    def test_valid_edit_and_stale_conflict(self):
        scene = self.client.get("/api/cases/P01/scene").json()
        scene["nodes"][1]["position"][0] += 1
        response = self.client.put("/api/cases/P01/scene", json=scene)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["revision"], 2)
        self.assertEqual(self.client.put("/api/cases/P01/scene", json=scene).status_code, 409)
        self.assertEqual(self.client.get("/api/cases/P01/revisions").json(), [2, 1])
        self.assertEqual(self.client.get("/api/cases/P01/revisions/1").status_code, 200)

    def test_unknown_scene_identity_rejected(self):
        scene = self.client.get("/api/cases/P01/scene").json()
        scene["case_id"] = "P02"
        self.assertEqual(self.client.put("/api/cases/P01/scene", json=scene).status_code, 422)

    def test_upload_and_no_fake_reconstruction(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "ready")
        self.assertEqual(self.client.get("/api/cases/I02/source").headers["content-type"], "image/png")
        self.assertEqual(self.client.get("/api/cases/I02/scene").status_code, 409)
        metadata = self.client.get("/api/cases/I02/source-metadata").json()
        self.assertEqual(metadata["width"], 64)
        self.assertNotIn("original_path", metadata)

    def test_fake_image_rejected(self):
        response = self.client.post("/api/cases/I01/source", files={"file": ("not.png", b"not an image", "image/png")})
        self.assertEqual(response.status_code, 422)
        self.assertIsNone(self.store.source("I01"))

    def test_prompt_upload_rejected(self):
        self.assertEqual(self.upload("P01").status_code, 422)

    def test_untrusted_origin_cannot_mutate(self):
        response = self.client.post("/api/cases/P01/jobs", json={"stages": ["extract"]}, headers={"Origin": "https://evil.example"})
        self.assertEqual(response.status_code, 403)

    def test_job_failure_is_visible(self):
        response = self.client.post("/api/cases/I01/jobs", json={"stages": ["extract"]})
        self.assertEqual(response.status_code, 202)
        identifier = response.json()["id"]
        for _ in range(100):
            job = self.client.get(f"/api/jobs/{identifier}").json()
            if job["status"] in ("failed", "succeeded", "cancelled"):
                break
            time.sleep(.01)
        self.assertEqual(job["status"], "failed")
        self.assertIn("Original source image is missing", job["error"])
        self.assertIsNone(self.store.current("I01"))

    def test_import_image_scene_requires_source_hash(self):
        self.upload()
        scene = self.client.get("/api/cases/P01/scene").json()
        scene["id"] = scene["case_id"] = "I02"
        scene["revision"] = 1
        self.assertEqual(self.client.put("/api/cases/I02/scene", json=scene).status_code, 409)
        source = self.store.source("I02")
        scene["sources"].append({"id": "image", "kind": "photo", "filename": "sample.png", "sha256": source["sha256"]})
        response = self.client.put("/api/cases/I02/scene", json=scene)
        self.assertEqual(response.status_code, 200, response.text)
        self.upload(color="red")
        self.assertEqual(self.client.get("/api/cases/I02/scene").status_code, 409)


class JobTests(Fixture):
    def setUp(self):
        super().setUp()
        self.runner = Runner(self.store)

    def tearDown(self):
        self.runner.close()
        super().tearDown()

    def run_job(self, case="P01", stages=None):
        identifier = uuid.uuid4().hex
        self.store.create_job(identifier, case, stages or ["extract"])
        self.runner.execute(identifier)
        return self.store.job(identifier)

    def test_repeatable_prompt_generation(self):
        first = self.run_job()
        self.assertEqual(first["status"], "succeeded")
        second = self.run_job()
        self.assertEqual(second["status"], "succeeded")

    def test_manual_edits_not_overwritten(self):
        scene = self.store.current("P01")
        scene.nodes[1].position = (100, 1, 0)
        self.store.save(scene, expected_revision=1, manual=True)
        result = self.run_job()
        self.assertEqual(result["status"], "failed")
        self.assertIn("overwrite", result["error"])
        self.assertEqual(self.store.current("P01").nodes[1].position, (100, 1, 0))

    def test_cancel_before_start(self):
        identifier = uuid.uuid4().hex
        self.store.create_job(identifier, "P01", ["extract"])
        self.store.update_job(identifier, cancel_requested=1)
        self.runner.execute(identifier)
        self.assertEqual(self.store.job(identifier)["status"], "cancelled")
        self.assertEqual(self.store.current("P01").revision, 1)

    def test_conflicting_queued_edit(self):
        identifier = uuid.uuid4().hex
        self.store.create_job(identifier, "P01", ["extract"])
        self.store.save(self.store.current("P01"), expected_revision=1)
        self.runner.execute(identifier)
        self.assertEqual(self.store.job(identifier)["status"], "failed")
        self.assertIn("Scene changed", self.store.job(identifier)["error"])

    def test_interrupted_job_marked_failed(self):
        identifier = uuid.uuid4().hex
        self.store.create_job(identifier, "P01", ["extract"])
        self.store.update_job(identifier, status="running")
        self.runner.start()
        self.assertEqual(self.store.job(identifier)["status"], "failed")

    def test_missing_blender_explicit(self):
        with patch("scene_pipeline.jobs.shutil.which", return_value=None), patch.dict(os.environ, {"BLENDER_BIN": ""}):
            job = self.run_job(stages=["blender"])
        self.assertEqual(job["status"], "failed")
        self.assertIn("Blender is unavailable", job["error"])


class GaussianTests(unittest.TestCase):
    def create_ply(self, path, bad=False, **updates):
        names = ["x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity", "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]
        count = len(updates.get("x", [-.1, .1]))
        values = np.zeros(count, dtype=[(name, "<f4") for name in names])
        for name in ("x", "y", "z"):
            values[name] = np.resize([-.1, .1], count)
        for name in ("scale_0", "scale_1", "scale_2"):
            values[name] = -4
        values["rot_0"] = 1
        if bad:
            values["opacity"][0] = float("nan")
        for name, value in updates.items():
            values[name] = value
        header = f"ply\nformat binary_little_endian 1.0\nelement vertex {count}\n" + "".join(f"property float {name}\n" for name in names) + "end_header\n"
        path.write_bytes(header.encode() + values.tobytes())

    def test_validated_gaussian_bounds(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "object.ply"
            self.create_ply(path)
            self.assertEqual(validate_ply(path)["gaussian_count"], 2)

    def test_nonfinite_gaussian_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "object.ply"
            self.create_ply(path, bad=True)
            with self.assertRaisesRegex(ValueError, "Nonfinite"):
                validate_ply(path)

    def test_quality_uses_rotated_covariance_and_does_not_change_ply_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "object.ply"
            self.create_ply(path, scale_0=np.log(.01), scale_1=np.log(.04), scale_2=np.log(.02),
                            rot_0=np.sqrt(.5), rot_3=np.sqrt(.5))
            original = path.read_bytes()
            report = assess_ply(path)
            self.assertEqual(report["status"], "accepted")
            np.testing.assert_allclose(report["render_bounds"]["min"], [-.26, -.14, -.18], atol=1e-7)
            np.testing.assert_allclose(report["render_bounds"]["max"], [.26, .14, .18], atol=1e-7)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(report["sha256"], validate_ply(path)["sha256"])

    def test_valid_centers_do_not_hide_giant_gaussian_radii(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "object.ply"
            self.create_ply(path, scale_0=0)
            self.assertEqual(validate_ply(path)["gaussian_count"], 2)
            report = assess_ply(path)
            self.assertEqual(report["status"], "excluded")
            self.assertIn("gaussian_support_over_four_times_center_extent", report["reasons"])

    def test_invisible_gaussian_does_not_inflate_render_bounds(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "object.ply"
            self.create_ply(path, x=[-.1, .1, 50], y=[-.1, .1, 50], z=[-.1, .1, 50],
                            opacity=[0, 0, -100], scale_0=[-4, -4, 10])
            report = assess_ply(path)
            self.assertEqual(report["status"], "accepted")
            self.assertLess(max(report["render_bounds"]["max"]), .2)

    def test_extreme_center_outliers_are_explicitly_excluded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "object.ply"
            positions = np.resize([-.1, .1], 1000)
            positions[-1] = 5
            self.create_ply(path, x=positions, y=positions, z=positions)
            self.assertIn("extreme_center_outliers", assess_ply(path)["reasons"])


if __name__ == "__main__":
    unittest.main()
