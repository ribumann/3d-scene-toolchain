import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blender"))
from scene_toolchain.coordinates import (  # noqa: E402
    blender_rotation_to_web, blender_size_to_web, blender_to_web,
    web_euler_matrix, web_matrix_to_euler, web_rotation_to_blender,
    web_size_to_blender, web_to_blender,
)


def fixture():
    return {
        "schema_version": "1.0", "id": "scene-1", "case_id": "case-1",
        "name": "Manufacturing cell", "description": "Fixture", "revision": 1,
        "units": "meters", "coordinates": "right-handed-y-up",
        "nodes": [
            {"id": "machine-1", "label": "Machine", "category": "equipment",
             "shape": "box", "position": [1, 2, 3], "rotation": [0.31, -0.62, 0.81],
             "size": [2, 3, 4], "color": "#336699", "visible": True,
             "evidence": {"origin": "generated", "confidence": 0.7, "reviewed": False,
                          "source_id": "src", "note": "Illustrative"},
             "asset_id": "asset-1"},
            {"id": "tank", "label": "Tank", "category": "equipment",
             "shape": "cylinder", "position": [-2, 1, 0], "rotation": [0, 0, 0],
             "size": [2, 4, 2], "color": "#ffaa00", "visible": True,
             "evidence": {"origin": "observed", "confidence": 1, "reviewed": True,
                          "note": ""}, "asset_id": None},
            {"id": "sphere", "label": "Sphere", "category": "equipment",
             "shape": "sphere", "position": [0, 1, 0], "rotation": [0, 0, 0],
             "size": [1, 2, 3], "color": "#abc", "visible": True,
             "evidence": {"origin": "assumed", "confidence": 0.5, "reviewed": False, "note": ""}},
            {"id": "cone", "label": "Cone", "category": "equipment",
             "shape": "cone", "position": [0, 1, 0], "rotation": [0, 0, 0],
             "size": [1, 2, 3], "color": "#abcdef", "visible": True,
             "evidence": {"origin": "assumed", "confidence": 0.5, "reviewed": False, "note": ""}},
            {"id": "plane", "label": "Hidden floor", "category": "floor",
             "shape": "plane", "position": [0, 0, 0], "rotation": [0, 0, 0],
             "size": [4, 0.1, 3], "color": "#ffffff", "visible": False,
             "evidence": {"origin": "inferred", "confidence": 0.5, "reviewed": False, "note": ""}},
        ],
        "edges": [{"id": "route-1", "source": "machine-1", "target": "tank",
                   "kind": "conveyor", "label": "Flow", "points": [[1, 0, 3], [-2, 0, 0]]}],
        "assets": [{"id": "asset-1", "kind": "ply", "uri": "/api/assets/object.ply",
                    "sha256": "abc", "node_id": "machine-1", "provenance": {"tool": "test"}},
                   {"id": "mesh-1", "kind": "glb", "uri": "/api/assets/scene.glb",
                    "sha256": "def", "provenance": {"tool": "test"}}],
        "sources": [{"id": "src", "kind": "plan", "filename": "source.png", "sha256": None}],
    }


class CoordinatesTest(unittest.TestCase):
    def assertMatrixClose(self, actual, expected, places=6):
        for row_a, row_b in zip(actual, expected):
            for a, b in zip(row_a, row_b):
                self.assertAlmostEqual(a, b, places=places)

    def test_positions_and_dimensions(self):
        self.assertEqual(web_to_blender((1, 2, 3)), (1, -3, 2))
        self.assertEqual(blender_to_web((1, -3, 2)), (1, 2, 3))
        self.assertEqual(blender_size_to_web(web_size_to_blender((1, 2, 3))), (1, 2, 3))

    def test_rotation_round_trips_as_matrices(self):
        for angles in [(0, 0, 0), (0.31, -0.62, 0.81), (-2.4, 1.2, 2.8),
                       (0.3, math.pi / 2 - 0.0001, -0.2),
                       (0.7, math.pi / 2, -0.3), (-0.7, -math.pi / 2, 0.3)]:
            with self.subTest(angles=angles):
                original = web_euler_matrix(angles)
                native = web_rotation_to_blender(original)
                back = blender_rotation_to_web(native)
                self.assertMatrixClose(original, back)
                self.assertMatrixClose(original, web_euler_matrix(web_matrix_to_euler(back)))


BLENDER = os.environ.get("BLENDER_BIN") or shutil.which("blender")


@unittest.skipUnless(BLENDER, "Blender is not installed; set BLENDER_BIN to run the smoke test")
class BlenderSmokeTest(unittest.TestCase):
    def run_blender(self, *args, expected=0):
        command = [BLENDER, "--background", "--threads", "2", *map(str, args)]
        result = subprocess.run(command, cwd="/", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=180)
        self.assertEqual(result.returncode, expected, msg=result.stdout[-12000:])
        return result.stdout

    def test_build_reference_and_addon_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.json"
            out = root / "result"
            source.write_text(json.dumps(fixture()), encoding="utf-8")
            self.run_blender("--python", ROOT / "blender/build_scene.py", "--",
                             "--scene", source, "--out", out)
            for filename in ("scene.blend", "scene.glb", "assets.json",
                             "references/machine-1.png", "references/manifest.json"):
                self.assertGreater((out / filename).stat().st_size, 0, filename)
            self.assertEqual(json.loads((out / "references/manifest.json").read_text()),
                             [{"node_id": "machine-1", "image": "machine-1.png"}])
            self.assertEqual(json.loads((out / "assets.json").read_text())["assets"], fixture()["assets"])
            glb = (out / "scene.glb").read_bytes()
            self.assertEqual(glb[:4], b"glTF")
            json_len = struct.unpack_from("<I", glb, 12)[0]
            gltf = json.loads(glb[20:20 + json_len])
            ids = {n.get("extras", {}).get("scene_toolchain_id") for n in gltf["nodes"]}
            self.assertTrue({"machine-1", "tank", "route-1"}.issubset(ids))
            self.assertNotIn("plane", ids)
            script = root / "check.py"
            script.write_text('''
import json, math, sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector
sys.path.insert(0, sys.argv[sys.argv.index("--") + 1])
from scene_toolchain import authoring, register, unregister
from scene_toolchain.coordinates import blender_rotation_to_web, web_euler_matrix
register()
assert hasattr(bpy.ops.scene_toolchain, "import_scene")
assert hasattr(bpy.ops.scene_toolchain, "export_scene")
scene = bpy.context.scene
original = json.loads(scene[authoring.SCENE_KEY])
nodes = authoring._objects_by_id(scene, "node")
edges = authoring._objects_by_id(scene, "edge")
assert tuple(round(v, 5) for v in nodes["tank"].dimensions) == (2.0, 2.0, 4.0)
data = authoring.scene_data(scene)
for actual, expected in zip(data["nodes"], original["nodes"]):
    for field in ("position", "rotation", "size"):
        assert all(abs(a-b) < 1e-5 for a,b in zip(actual[field], expected[field])), (field, actual, expected)
    assert actual["evidence"] == expected["evidence"]
    assert actual.get("asset_id") == expected.get("asset_id")
assert data["sources"] == original["sources"] and data["assets"] == original["assets"]
image = bpy.data.images.load(str(Path(bpy.data.filepath).parent / "references/machine-1.png"))
assert image.size[:] == (256, 256)
pixels = image.pixels[:]
alphas = pixels[3::4]
assert max(alphas) > .9 and min(alphas) < .1, "reference must contain isolated object and transparency"
obj = nodes["machine-1"]
obj.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0, 0, 1)
obj.matrix_world = Matrix.Translation((4, 5, 6)) @ Matrix.Rotation(0.35, 4, "X") @ Matrix.Diagonal((2, 3, 4, 1))
edges["route-1"].data.splines[0].points[0].co = (7, 8, 9, 1)
bpy.context.view_layer.update()
out = Path(bpy.data.filepath).parent / "edited.json"
assert bpy.ops.scene_toolchain.export_scene(filepath=str(out)) == {"FINISHED"}
edited = json.loads(out.read_text())
node = edited["nodes"][0]
assert all(abs(a-b) < 1e-5 for a,b in zip(node["position"], (4, 6, -5)))
assert all(abs(a-b) < 1e-5 for a,b in zip(node["rotation"], (.35, 0, 0)))
assert all(abs(a-b) < 1e-5 for a,b in zip(node["size"], (2, 4, 3)))
assert node["color"] == "#ff0000"
assert all(abs(a-b) < 1e-5 for a,b in zip(edited["edges"][0]["points"][0], (7, 9, -8)))
assert edited["assets"] == original["assets"] and edited["sources"] == original["sources"]
assert node["evidence"] == original["nodes"][0]["evidence"]
assert out.with_suffix(".glb").is_file()
obj.matrix_world = (Matrix.Translation((1, 2, 3)) @ Matrix.Rotation(.4, 4, "Z")
                    @ Matrix.Rotation(-.6, 4, "Y") @ Matrix.Rotation(.9, 4, "X")
                    @ Matrix.Diagonal((2, 3, 4, 1)))
bpy.context.view_layer.update()
native_rotation = obj.matrix_world.to_quaternion().to_matrix()
exported_rotation = web_euler_matrix(authoring.scene_data(scene)["nodes"][0]["rotation"])
expected_rotation = blender_rotation_to_web(native_rotation)
assert all(abs(exported_rotation[i][j] - expected_rotation[i][j]) < 1e-5 for i in range(3) for j in range(3))
new_scene = bpy.data.scenes.new("Import test")
bpy.context.window.scene = new_scene
assert bpy.ops.scene_toolchain.import_scene(filepath=str(Path(bpy.data.filepath).parent.parent / "input.json")) == {"FINISHED"}
imported = authoring.scene_data(new_scene)
assert imported["sources"] == original["sources"] and imported["assets"] == original["assets"]
assert imported["nodes"][0]["evidence"] == original["nodes"][0]["evidence"]
unregister()
''', encoding="utf-8")
            self.run_blender(out / "scene.blend", "--python-exit-code", "7",
                             "--python", script, "--", ROOT / "blender")

    def test_explicit_reference_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.json"
            source.write_text(json.dumps(fixture()), encoding="utf-8")
            self.run_blender("--python", ROOT / "blender/build_scene.py", "--",
                             "--scene", source, "--out", root / "out", "--reference-node", "tank")
            manifest = json.loads((root / "out/references/manifest.json").read_text())
            self.assertEqual(manifest, [{"node_id": "tank", "image": "tank.png"}])
            self.assertTrue((root / "out/references/tank.png").is_file())

    def test_default_candidate_matches_pipeline_not_just_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = fixture()
            ground = dict(data["nodes"][0], id="ground", category="ground")
            data["nodes"].insert(0, ground)
            data["nodes"][1]["evidence"]["origin"] = "inferred"
            source = root / "input.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            self.run_blender("--python", ROOT / "blender/build_scene.py", "--",
                             "--scene", source, "--out", root / "out")
            self.assertTrue((root / "out/references/machine-1.png").is_file())
            self.assertFalse((root / "out/references/ground.png").exists())

    def test_unsafe_reference_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = fixture()
            data["nodes"][0]["id"] = "../escape"
            data["edges"][0]["source"] = "../escape"
            source = root / "input.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            output = self.run_blender("--python", ROOT / "blender/build_scene.py", "--",
                                      "--scene", source, "--out", root / "out", expected=1)
            self.assertIn("not a safe filename", output)
            self.assertFalse((root / "out/escape.png").exists())

    def test_invalid_zero_dimension_fails_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = fixture()
            data["nodes"][0]["size"][0] = 0
            source = Path(tmp) / "bad.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            output = self.run_blender("--python", ROOT / "blender/build_scene.py", "--",
                                      "--scene", source, "--out", Path(tmp) / "out", expected=1)
            self.assertIn("positive", output)
