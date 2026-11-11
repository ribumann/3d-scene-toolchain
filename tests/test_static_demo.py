import json
import tempfile
import unittest
from pathlib import Path

from scene_pipeline.models import Case, Scene
from scripts.build_static_demo import build_demo


class StaticDemoTests(unittest.TestCase):
    def test_refuses_stale_or_unreviewed_files_in_public_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "private-image.png").write_bytes(b"not for publication")
            with self.assertRaisesRegex(ValueError, "Unexpected public demo content"):
                build_demo(output)
            self.assertFalse((output / "cases.json").exists())

    def test_publishes_only_public_procedural_templates(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build_demo(output)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {"cases.json", "P01.json", "P02.json", "P03.json"},
            )
            cases = [Case.model_validate(item) for item in json.loads((output / "cases.json").read_text())]
            self.assertEqual(len(cases), 11)
            self.assertEqual([case.id for case in cases if case.status == "ready"], ["P01", "P02", "P03"])
            self.assertTrue(all(case.source_url is None and case.source_filename is None for case in cases))
            for case in cases:
                if case.status != "ready":
                    continue
                scene = Scene.model_validate_json((output / f"{case.id}.json").read_text())
                self.assertEqual(scene.case_id, case.id)
                self.assertGreater(len(scene.nodes), 0)
                self.assertGreater(len(scene.edges), 0)
                self.assertFalse(scene.assets)
                self.assertTrue(all(node.evidence.origin == "generated" and not node.evidence.reviewed for node in scene.nodes))
