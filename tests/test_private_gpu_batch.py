"""Synthetic CPU fixtures verify orchestration, not actual GPU model execution."""

import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from scene_pipeline.gaussians import validate_ply
from scene_pipeline.models import Evidence, Node, Scene, Source
from scene_pipeline.store import Store
from scripts.private_gpu_batch import make_plan, run_batch, run_cases
from scripts.private_gpu_smoke import PIN_NAMES, ROOT, SDK_REVISION, SmokeError, load_source
from scripts.resolve_smoke_models import I02_BATCH_REVISIONS, MODELS, resolve_models


class PrivateBatchTests(unittest.TestCase):
    def setUp(self):
        self.environment = {name: "a" * 40 for name in PIN_NAMES}
        self.environment["HF_TOKEN"] = "PRIVATE_TEST_TOKEN"
        self.calls = []
        self.categories = ["building", "tree", "truck"]
        self.failures = {}
        self.bad_provenance = set()
        self.interrupt_after_write = set()
        self.case_id = "I02"

    def source(self, root, color="green"):
        stream = io.BytesIO()
        Image.new("RGB", (64, 64), color).save(stream, format="PNG")
        Store(root).save_source("I02", stream.getvalue(), stream.getvalue(), "private-original.png")
        return load_source(root)[0]

    def extraction(self, folder, source, categories=None):
        categories = categories or self.categories
        folder.mkdir(parents=True, exist_ok=True)
        scene = Scene(
            id=f"scene-{self.case_id}", case_id=self.case_id, name="Synthetic test extraction",
            description="Synthetic image-plane proposals, not measured dimensions.",
            sources=[Source(id="image", kind="photo", filename=source["filename"], sha256=source["sha256"])],
            nodes=[Node(
                id=f"object-{index:03d}", label=category, category=category,
                position=(index, 1, 0), size=(1, 2, 1), color="#ffffff",
                evidence=Evidence(origin="inferred", confidence=.8, source_id="image", note="Inferred fixture placement"),
            ) for index, category in enumerate(categories)],
        )
        annotations = []
        for index, node in enumerate(scene.nodes):
            image = Image.new("RGBA", (64, 64), (index % 256, 120, 140, 0))
            ImageDraw.Draw(image).rectangle((8, 8, 55, 55), fill=(index % 256, 120, 140, 255))
            image.save(folder / f"{node.id}.png")
            annotations.append({"node_id": node.id, "crop": f"{node.id}.png", "bbox_pixels": [0, 0, 64, 64]})
        report = {
            "method": "grounding-dino+sam2", "annotations": annotations,
            "detector": {"model": "IDEA-Research/grounding-dino-tiny", "revision": self.environment["SCENE_DETECTOR_REVISION"]},
            "segmenter": {"model": "facebook/sam2.1-hiera-small", "revision": self.environment["SCENE_SEGMENTER_REVISION"]},
        }
        if self.case_id in ("I01", "I04", "I05"):
            for node in scene.nodes:
                node.category = "footprint" if self.case_id == "I05" else "equipment-candidate"
            report.update(method="opencv-line-contours+tesseract", topology_status="not_extracted")
            report.pop("detector")
            report.pop("segmenter")
        (folder / "scene.json").write_text(scene.model_dump_json())
        (folder / "extraction.json").write_text(json.dumps(report))
        return scene, report

    def generation(self, folder, crop):
        names = ["x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity",
                 "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]
        values = np.zeros(32768, dtype=[(name, "<f4") for name in names])
        for name in ("x", "y", "z"):
            values[name] = np.linspace(-.1, .1, len(values))
        for name in ("scale_0", "scale_1", "scale_2"):
            values[name] = -4
        values["rot_0"] = 1
        header = "ply\nformat binary_little_endian 1.0\nelement vertex 32768\n"
        header += "".join(f"property float {name}\n" for name in names) + "end_header\n"
        (folder / "object.ply").write_bytes(header.encode() + values.tobytes())
        metadata = {
            **validate_ply(folder / "object.ply"), "model": "speridlabs/idol",
            "input_sha256": hashlib.sha256(crop.read_bytes()).hexdigest(),
            "model_revision": self.environment["SCENE_IDOL_MODEL_REVISION"], "sdk_revision": SDK_REVISION,
            "mode": "real", "steps": 50, "seed": 42,
            "encoder_revisions": {key: self.environment[key] for key in ("SCENE_DINOV3_REVISION", "SCENE_FLUX2_REVISION")},
        }
        if crop.stem in self.bad_provenance:
            metadata["input_sha256"] = "b" * 64
        (folder / "generation.json").write_text(json.dumps(metadata))

    def stage(self, arguments, log, timeout, measurement):
        measurement.update(seconds=1, peak_device_memory_mib_sampled=100, sample_interval_seconds=2)
        if "extract" in arguments:
            self.assertIn("--all-objects", arguments)
            self.calls.append("extract")
            root = Path(arguments[arguments.index("--data-dir") + 1])
            destination = Path(arguments[arguments.index("--output") + 1])
            preview = Path(arguments[arguments.index("--public-preview") + 1]) if "--public-preview" in arguments else None
            self.extraction(destination / "extraction", load_source(root, preview, self.case_id)[0])
            return
        crop = Path(arguments[arguments.index("--image") + 1])
        destination = Path(arguments[arguments.index("--out") + 1])
        self.assertEqual(arguments[arguments.index("--mode") + 1], "real")
        self.assertEqual(arguments[arguments.index("--count") + 1], "32768")
        self.calls.append(crop.stem)
        log.write_text("Sensitive private model diagnostics PRIVATE_TEST_TOKEN")
        failure = self.failures.pop(crop.stem, None)
        if failure is not None:
            raise failure
        self.generation(destination, crop)
        if crop.stem in self.interrupt_after_write:
            self.interrupt_after_write.remove(crop.stem)
            raise KeyboardInterrupt

    def run_private(self, root, public_preview=None):
        stdout = io.StringIO()
        with patch.dict(os.environ, self.environment), patch(
            "scripts.private_gpu_batch.run_stage", side_effect=self.stage,
        ), redirect_stdout(stdout):
            code = run_batch(root, public_preview, self.case_id)
        self.assertNotIn("PRIVATE_TEST_TOKEN", stdout.getvalue())
        self.assertNotIn("Sensitive private", stdout.getvalue())
        return code, json.loads(stdout.getvalue())

    def manifest(self, root):
        output = root / "assets/I02/object-batch"
        return output, json.loads((output / "batch.json").read_text())

    def test_enumerates_beyond_48_and_preserves_exact_duplicate_parent_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.source(root)
            scene, report = self.extraction(root / "extraction", source, ["tree"] * 51 + ["person", "building", "truck"])
            folder = root / "extraction"
            (folder / "object-052.png").write_bytes((folder / "object-000.png").read_bytes())
            Image.new("RGBA", (8, 8)).save(folder / "object-053.png")
            plan, rejected = make_plan(scene, report, folder)
            self.assertEqual(len(plan), 51)
            self.assertEqual([parent["node_id"] for parent in plan[0]["parents"]], ["object-000", "object-052"])
            self.assertEqual(
                {item["node_id"]: item["reason"] for item in rejected},
                {"object-051": "not_an_approved_non_person_object", "object-053": "invalid_crop_format_or_size"},
            )

    def test_individual_failure_does_not_stop_others_and_resume_skips_validated_objects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.source(root)
            self.failures["object-001"] = SmokeError("cuda_out_of_memory_no_quality_fallback")
            code, first = self.run_private(root)
            self.assertEqual(code, 1)
            self.assertEqual(first["status"], "partial")
            self.assertEqual(self.calls, ["extract", "object-000", "object-001", "object-002"])
            output, state = self.manifest(root)
            scene = Scene.model_validate_json((output / state["scene_path"]).read_text())
            self.assertEqual([node.id for node in scene.nodes], ["object-000", "object-002"])
            self.assertTrue(all(node.asset_id for node in scene.nodes))
            self.assertTrue(all(asset.provenance["source_sha256"] == source["sha256"] for asset in scene.assets))
            self.assertTrue(all(asset.provenance["parent_node_id"] == asset.node_id for asset in scene.assets))
            self.assertTrue(all(asset.provenance["layout"] == "inferred-image-plane-not-metric" for asset in scene.assets))
            self.calls.clear()
            code, second = self.run_private(root)
            self.assertEqual((code, second["status"]), (0, "succeeded"))
            self.assertEqual(self.calls, ["object-001"])
            self.assertEqual([item["status"] for item in second["objects"]], ["resumed", "succeeded", "resumed"])
            output, state = self.manifest(root)
            attempts = state["objects"]["object-001"]["attempts"]
            self.assertEqual([attempt["status"] for attempt in attempts], ["failed", "succeeded"])
            self.assertTrue((output / attempts[0]["directory"] / "idol-private.log").exists())

    def test_duplicate_crops_reconstruct_once_and_assemble_both_parent_nodes(self):
        self.categories = ["tree", "building"]
        original_extraction = self.extraction
        def duplicate(*arguments, **kwargs):
            scene, report = original_extraction(*arguments, **kwargs)
            folder = arguments[0]
            (folder / "object-001.png").write_bytes((folder / "object-000.png").read_bytes())
            return scene, report
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.source(root)
            with patch.object(self, "extraction", side_effect=duplicate):
                code, report = self.run_private(root)
            self.assertEqual(code, 0)
            self.assertEqual(self.calls, ["extract", "object-000"])
            self.assertEqual(report["nodes_reconstructed"], 2)
            output, state = self.manifest(root)
            scene = Scene.model_validate_json((output / state["scene_path"]).read_text())
            self.assertEqual([asset.node_id for asset in scene.assets], ["object-000", "object-001"])
            self.assertEqual(scene.assets[0].uri, scene.assets[1].uri)
            self.assertEqual(scene.assets[1].provenance["duplicate_of"], "object-000")
            self.assertEqual(scene.nodes[1].position, (1, 1, 0))
            self.assertEqual(scene.nodes[1].size, (1, 2, 1))

    def test_resume_rejects_source_pin_and_settings_mismatch_without_running_models(self):
        self.categories = ["tree"]
        for mismatch in ("source", "pin", "settings"):
            with self.subTest(mismatch=mismatch), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.source(root)
                self.assertEqual(self.run_private(root)[0], 0)
                output, state = self.manifest(root)
                if mismatch == "source":
                    self.source(root, color="red")
                elif mismatch == "pin":
                    self.environment["SCENE_DINOV3_REVISION"] = "b" * 40
                else:
                    state["contract"]["steps"] = 49
                    (output / "batch.json").write_text(json.dumps(state))
                before = (output / "batch.json").read_bytes()
                self.calls.clear()
                code, report = self.run_private(root)
                self.assertEqual(code, 1)
                self.assertEqual(report["failure_reason"], "batch_source_pins_or_settings_mismatch")
                self.assertFalse(self.calls)
                self.assertEqual((output / "batch.json").read_bytes(), before)
                self.environment["SCENE_DINOV3_REVISION"] = "a" * 40

    def test_corrupt_completed_ply_is_not_resumed_or_used_in_assembly(self):
        self.categories = ["tree", "truck"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.source(root)
            self.assertEqual(self.run_private(root)[0], 0)
            output, state = self.manifest(root)
            corrupted = output / state["objects"]["object-000"]["attempts"][-1]["directory"] / "object.ply"
            corrupted.write_bytes(b"corrupted previous output")
            self.calls.clear()
            code, report = self.run_private(root)
            self.assertEqual(code, 0)
            self.assertEqual(self.calls, ["object-000"])
            self.assertEqual(report["objects"][0]["resume_rejected"], "cached_output_failed_revalidation")
            self.assertEqual(report["objects"][1]["status"], "resumed")
            self.assertEqual(corrupted.read_bytes(), b"corrupted previous output")

    def test_changed_extraction_refuses_resume_without_repeating_models_or_claiming_a_scene(self):
        self.categories = ["tree"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.source(root)
            self.assertEqual(self.run_private(root)[0], 0)
            output, state = self.manifest(root)
            crop = output / state["extraction"]["directory"] / "object-000.png"
            Image.new("RGBA", (64, 64), "red").save(crop)
            self.calls.clear()
            code, report = self.run_private(root)
            self.assertEqual((code, report["failure_reason"]), (1, "cached_extraction_changed"))
            self.assertFalse(self.calls)
            self.assertIsNone(self.manifest(root)[1]["scene_path"])

    def test_interruption_preserves_completed_checkpoints_and_partial_scene(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.source(root)
            self.failures["object-001"] = KeyboardInterrupt()
            code, report = self.run_private(root)
            self.assertEqual((code, report["status"]), (1, "interrupted"))
            output, state = self.manifest(root)
            self.assertEqual(state["objects"]["object-000"]["attempts"][-1]["status"], "succeeded")
            self.assertEqual(state["objects"]["object-001"]["attempts"][-1]["status"], "interrupted")
            scene = Scene.model_validate_json((output / state["scene_path"]).read_text())
            self.assertEqual([node.id for node in scene.nodes], ["object-000"])
            self.calls.clear()
            self.assertEqual(self.run_private(root)[0], 0)
            self.assertEqual(self.calls, ["object-001", "object-002"])

    def test_revalidates_finished_output_if_interrupted_before_completion_checkpoint(self):
        self.categories = ["tree"]
        self.interrupt_after_write.add("object-000")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.source(root)
            self.assertEqual(self.run_private(root)[1]["status"], "interrupted")
            self.calls.clear()
            code, report = self.run_private(root)
            self.assertEqual(code, 0)
            self.assertFalse(self.calls)
            self.assertEqual(report["objects"][0]["status"], "resumed")

    def test_wrong_crop_provenance_fails_only_that_object(self):
        self.categories = ["tree", "truck"]
        self.bad_provenance.add("object-000")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.source(root)
            code, report = self.run_private(root)
            self.assertEqual((code, report["status"]), (1, "partial"))
            self.assertEqual(report["objects"][0]["failure_reason"], "idol_provenance_mismatch")
            output, state = self.manifest(root)
            scene = Scene.model_validate_json((output / state["scene_path"]).read_text())
            self.assertEqual([node.id for node in scene.nodes], ["object-001"])

    def test_all_unusable_crops_fail_without_model_calls_or_empty_scene_success(self):
        self.categories = ["person"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.source(root)
            code, report = self.run_private(root)
            self.assertEqual((code, report["status"]), (1, "failed"))
            self.assertEqual(report["failure_reason"], "no_valid_non_person_segmented_crop")
            self.assertEqual(self.calls, ["extract"])
            self.assertIsNone(self.manifest(root)[1]["scene_path"])

    def test_explicit_preview_needs_no_original_store_and_records_real_webp_provenance(self):
        self.categories = ["tree"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            preview = root / "I02.webp"
            original_bytes = (ROOT / "apps/web/public/references/I02.webp").read_bytes()
            preview.write_bytes(original_bytes)
            code, report = self.run_private(root, preview)
            self.assertEqual(code, 0)
            self.assertEqual(report["source_kind"], "user-approved-public-webp-preview")
            self.assertTrue(report["not_original_bytes"])
            self.assertEqual(report["sha256"], hashlib.sha256(original_bytes).hexdigest())
            output = root / "assets/I02/object-batch-public-preview"
            state = json.loads((output / "batch.json").read_text())
            self.assertEqual(state["contract"]["source_kind"], report["source_kind"])
            scene = Scene.model_validate_json((output / state["scene_path"]).read_text())
            provenance = scene.assets[0].provenance["input_provenance"]
            self.assertEqual(provenance["sha256"], report["sha256"])
            self.assertTrue(provenance["not_original_bytes"])
            self.assertEqual(provenance["dimensions"], [715, 429])
            self.assertFalse((root / "scene.sqlite3").exists())
            self.assertFalse((root / "assets/I02/object-batch").exists())
            self.calls.clear()
            self.assertEqual(self.run_private(root, preview)[0], 0)
            self.assertFalse(self.calls)

    def test_unapproved_preview_bytes_fail_before_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            preview = root / "I02.webp"
            Image.new("RGB", (64, 64), "red").save(preview, format="WEBP")
            code, report = self.run_private(root, preview)
            self.assertEqual(code, 1)
            self.assertEqual(report["failure_reason"], "public_preview_does_not_match_authorized_asset")
            self.assertFalse(self.calls)
            self.assertFalse((root / "assets").exists())

    def test_other_photo_generated_and_diagram_cases_use_independent_honest_routes(self):
        examples = {"I03": "tank", "G01": "shelf", "G02": "industrial machine", "G03": "pond",
                    "I01": "region", "I04": "region", "I05": "region"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for case, category in examples.items():
                with self.subTest(case=case):
                    self.case_id, self.categories = case, [category, "person"]
                    preview = root / f"{case}.webp"
                    preview.write_bytes((ROOT / f"apps/web/public/references/{case}.webp").read_bytes())
                    self.calls.clear()
                    code, report = self.run_private(root, preview)
                    self.assertEqual(code, 0)
                    output = root / f"assets/{case}/object-batch-public-preview"
                    state = json.loads((output / "batch.json").read_text())
                    scene = Scene.model_validate_json((output / state["scene_path"]).read_text())
                    self.assertEqual(scene.case_id, case)
                    if case in ("I01", "I04", "I05"):
                        self.assertEqual(report["status"], "proposals")
                        self.assertEqual(self.calls, ["extract"])
                        self.assertFalse(scene.assets)
                        self.assertFalse(scene.edges)
                        self.assertIsNone(report["gaussian_count_per_object"])
                    else:
                        self.assertEqual(report["status"], "succeeded")
                        self.assertEqual(self.calls, ["extract", "object-000"])
                        self.assertEqual(len(scene.nodes), 1)
                        self.assertEqual(report["reference_origin"], "ai-generated" if case.startswith("G") else "user-supplied-original")

    def test_case_orchestrator_continues_failed_cases_but_stops_on_interruption(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls = []
            def batch(directory, preview, case):
                calls.append(case)
                print(json.dumps({"case_id": case, "status": "failed" if case == "I01" else "proposals"}))
                return 1 if case == "I01" else 0
            with patch("scripts.private_gpu_batch.run_batch", side_effect=batch), redirect_stdout(io.StringIO()):
                self.assertEqual(run_cases(root, ["I01", "I04"], "public-preview"), 1)
            self.assertEqual(calls, ["I01", "I04"])
            status = json.loads((root / "pilot-status.json").read_text())
            self.assertFalse(status["complete"])
            with self.assertRaisesRegex(SmokeError, "invalid_unique"):
                run_cases(root, ["I02", "I02"], "public-preview")


class PinnedBatchReadinessTests(unittest.TestCase):
    def test_checks_historical_verified_revisions_instead_of_floating_to_main(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temporary:
            requested = []
            def model_info(repo_id, token, revision):
                requested.append((repo_id, revision))
                return SimpleNamespace(sha=revision)
            def download(**arguments):
                config = {"image_encoders": {"dinov3": MODELS["dinov3_revision"], "flux2_vae": MODELS["flux2_revision"]}} if arguments["repo_id"] == MODELS["idol_revision"] else {}
                path = Path(temporary) / arguments["repo_id"].replace("/", "_")
                path.write_text(json.dumps(config))
                self.assertEqual(arguments["revision"], dict(requested)[arguments["repo_id"]])
                self.assertTrue(arguments["force_download"])
                return path
            pins = resolve_models(SimpleNamespace(model_info=model_info), download, "fake", temporary, I02_BATCH_REVISIONS)
            self.assertEqual(len(requested), 5)
            self.assertEqual(pins, I02_BATCH_REVISIONS)
