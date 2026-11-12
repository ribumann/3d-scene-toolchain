import json
import unittest
from pathlib import Path

from scripts.illustration_reconstruct import ReviewedReference
from scripts.illustration_scenes import illustration_scene


class IllustrationSceneTests(unittest.TestCase):
    def setUp(self):
        manifest = json.loads((Path(__file__).resolve().parents[1] / "cases/illustrations.json").read_text())
        self.appearances = {item["id"]: {"sha256": "a" * 64} for item in manifest["concepts"]}

    def test_explicit_prompt_instances_preserve_routes_without_duplicate_housings(self):
        scene = illustration_scene("P02", self.appearances)
        self.assertEqual(len(scene.edges), 6)
        self.assertEqual(len(scene.assets), 8)
        self.assertEqual(sum(node.asset_id is not None for node in scene.nodes), 13)
        self.assertFalse(any(node.category in ("housing", "control") for node in scene.nodes))
        self.assertTrue(all(edge.evidence.origin == "generated" for edge in scene.edges))
        zoo = illustration_scene("P03", self.appearances)
        self.assertEqual(sum(node.asset_id == "illustration-tree" for node in zoo.nodes), 12)
        self.assertFalse(any("-trunk-" in node.id for node in zoo.nodes))

    def test_assembly_branch_enters_chassis_two_and_preserves_station_counts(self):
        scene = illustration_scene("I04", self.appearances)
        self.assertEqual(sum(node.category == "assembly-station" for node in scene.nodes), 93)
        self.assertEqual(len(scene.edges), 100)
        connections = {(edge.source, edge.target) for edge in scene.edges}
        self.assertIn(("engine-6", "engine-buffer"), connections)
        self.assertIn(("engine-buffer", "chassis2-01"), connections)
        self.assertNotIn(("engine-buffer", "trim1-01"), connections)
        self.assertTrue(all(edge.evidence.reviewed and edge.evidence.source_id == "image" for edge in scene.edges))

    def test_plan_proximity_does_not_invent_process_connections(self):
        scene = illustration_scene("I05", self.appearances)
        self.assertEqual(len(scene.nodes), 8)
        self.assertEqual(len(scene.assets), 1)
        self.assertEqual(scene.edges, [])
        self.assertTrue(all(node.evidence.origin == "generated" for node in scene.nodes))

    def test_missing_appearance_is_not_replaced_by_a_box(self):
        scene = illustration_scene("P01", {"checkout": self.appearances["checkout"]})
        self.assertEqual(sum(node.category == "checkout" for node in scene.nodes), 3)
        self.assertFalse(any(node.category in ("shelf", "endcap") for node in scene.nodes))
        with self.assertRaisesRegex(ValueError, "No reconstructed"):
            illustration_scene("I01", {})

    def test_review_rejects_out_of_frame_and_nonfinite_boxes(self):
        for box in ((.8, .1, .3, .2), (0, 0, float("nan"), .5), (0, 0, 0, 1)):
            with self.assertRaises(ValueError):
                ReviewedReference(id="pump", sha256="a"*64, box=box, reviewed=True, note="Reviewed complete main object")

    def test_edge_evidence_must_reference_an_actual_source(self):
        scene = illustration_scene("I04", self.appearances)
        content = scene.model_dump()
        content["edges"][0]["evidence"]["source_id"] = "missing"
        with self.assertRaisesRegex(ValueError, "unknown evidence source"):
            type(scene).model_validate(content)
