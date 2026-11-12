import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scene_pipeline.models import Case, Scene
from scripts.build_static_demo import apply_visual_exclusions, build_demo, REFERENCE_IDS, REFERENCE_SOURCE


class StaticDemoTests(unittest.TestCase):
    def test_visual_exclusion_is_bound_to_exact_appearance_bytes(self):
        sha256 = "a" * 64
        quality = {sha256: {"sha256": sha256, "status": "accepted", "reasons": []}}
        note = "Individually reviewed disconnected, floating fragments."
        apply_visual_exclusions(quality, {"schema_version": 1, "excluded": {"b" * 64: note}})
        self.assertEqual(quality[sha256]["status"], "accepted")
        apply_visual_exclusions(quality, {"schema_version": 1, "excluded": {sha256: note}})
        self.assertEqual(quality[sha256]["status"], "excluded")
        self.assertEqual(quality[sha256]["reasons"], [f"visual_review: {note}"])

    def test_visual_exclusion_rejects_unbound_or_invalid_reviews(self):
        for reviews in (
            {"schema_version": 1, "excluded": {"object-id": "Invalid non-hash identity."}},
            {"schema_version": 1, "excluded": {"a" * 64: ""}},
            {"schema_version": True, "excluded": {}},
            {"schema_version": 1, "excluded": {}, "unreviewed": True},
        ):
            with self.subTest(reviews=reviews), self.assertRaises(ValueError):
                apply_visual_exclusions({}, reviews)

    def test_refuses_stale_or_unreviewed_files_in_public_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "private-image.png").write_bytes(b"not for publication")
            with self.assertRaisesRegex(ValueError, "Unexpected public demo content"):
                build_demo(output)
            self.assertFalse((output / "cases.json").exists())

    def test_refuses_unreviewed_nested_files_and_symlinks(self):
        for child in ("demo", "references"):
            with self.subTest(child=child), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                (output / child).mkdir()
                (output / child / "original.png").write_bytes(b"private")
                with self.assertRaisesRegex(ValueError, "Unexpected public demo content"):
                    build_demo(output)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "references").symlink_to(REFERENCE_SOURCE, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "Unexpected public demo content"):
                build_demo(output)

    def test_missing_authorized_preview_fails_before_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "public"
            with patch("scripts.build_static_demo.REFERENCE_SOURCE", Path(directory)):
                with self.assertRaisesRegex(ValueError, "Authorized reference preview missing"):
                    build_demo(output)
            self.assertFalse(output.exists())

    def test_does_not_copy_other_source_files(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "incoming", Path(directory) / "public"
            source.mkdir()
            for identifier in REFERENCE_IDS:
                (source / f"{identifier}.webp").write_bytes((REFERENCE_SOURCE / f"{identifier}.webp").read_bytes())
            (source / "private-original.png").write_bytes(b"not authorized")
            with patch("scripts.build_static_demo.REFERENCE_SOURCE", source):
                build_demo(output)
            self.assertFalse((output / "references/private-original.png").exists())
            self.assertEqual(len(list((output / "references").iterdir())), 8)

    def test_publishes_only_procedural_scenes_and_authorized_reference_previews(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build_demo(output)
            build_demo(output)
            self.assertEqual({path.name for path in output.iterdir()}, {"demo", "references"})
            self.assertEqual(
                {path.name for path in (output / "demo").iterdir()},
                {"cases.json", "P01.json", "P02.json", "P03.json", "pilots.json", "trials.json", "quality.json"},
            )
            self.assertEqual(
                {path.name for path in (output / "references").iterdir()},
                {f"{identifier}.webp" for identifier in REFERENCE_IDS},
            )
            for identifier in REFERENCE_IDS:
                self.assertEqual(
                    (output / "references" / f"{identifier}.webp").read_bytes(),
                    (REFERENCE_SOURCE / f"{identifier}.webp").read_bytes(),
                )
            cases = [Case.model_validate(item) for item in json.loads((output / "demo/cases.json").read_text())]
            self.assertEqual(len(cases), 11)
            self.assertEqual([case.id for case in cases if case.status == "ready"], ["P01", "P02", "P03"])
            for case in cases:
                if case.status != "ready":
                    self.assertIn(case.id, REFERENCE_IDS)
                    self.assertEqual(case.source_url, f"/references/{case.id}.webp")
                    self.assertEqual(case.source_filename, f"{case.id}.webp")
                    continue
                self.assertIsNone(case.source_url)
                self.assertIsNone(case.source_filename)
                scene = Scene.model_validate_json((output / "demo" / f"{case.id}.json").read_text())
                self.assertEqual(scene.case_id, case.id)
                self.assertGreater(len(scene.nodes), 0)
                self.assertGreater(len(scene.edges), 0)
                self.assertFalse(scene.assets)
                self.assertTrue(all(node.evidence.origin == "generated" and not node.evidence.reviewed for node in scene.nodes))
