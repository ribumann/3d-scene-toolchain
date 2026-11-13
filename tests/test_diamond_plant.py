import copy
import hashlib
import json
import math
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from scripts.diamond_plant import ROOT, TYPES, apply_reconstructed_appearances, design, public_files, publish, trial_manifest, validate_design
from scene_pipeline.models import Asset
from scripts.plant_geometry import glb
from scripts.trial_contracts import TrialManifest, load_manifest


def decode_glb(data):
    magic, version, length = struct.unpack_from("<4sII", data)
    assert (magic, version, length) == (b"glTF", 2, len(data))
    count, kind = struct.unpack_from("<I4s", data, 12)
    assert kind == b"JSON" and count % 4 == 0
    document = json.loads(data[20:20 + count])
    binary_count, kind = struct.unpack_from("<I4s", data, 20 + count)
    assert kind == b"BIN\0" and binary_count % 4 == 0 and 28 + count + binary_count == len(data)
    binary = data[28 + count:]
    assert document["buffers"][0]["byteLength"] == len(binary)
    for accessor in document["accessors"]:
        view = document["bufferViews"][accessor["bufferView"]]
        assert accessor["count"] * 12 == view["byteLength"]
        assert view["byteOffset"] % 4 == 0
        assert view["byteOffset"] + view["byteLength"] <= len(binary)
        values = struct.unpack_from("<" + "f" * accessor["count"] * 3, binary, view["byteOffset"])
        assert all(math.isfinite(value) for value in values)
    return document, binary


class DiamondPlantTests(unittest.TestCase):
    def test_gaussian_overlay_preserves_twin_ids_routes_and_shares_repeated_appearances(self):
        metadata = design()
        scene, files = public_files(metadata)
        original_nodes = [node.model_dump(exclude={"asset_id"}) for node in scene.nodes]
        original_edges = scene.edges.copy()
        recovered = scene.model_copy(deep=True)
        recovered.nodes = [node for node in recovered.nodes if node.id.endswith(".crusher")]
        recovered.edges = []
        recovered.assets = []
        for node in recovered.nodes:
            node.asset_id = "idol-" + node.id
            recovered.assets.append(Asset(
                id=node.asset_id, kind="ply", node_id=node.id, uri="/api/assets/trials/D01/optimized/object-000.ply",
                sha256="a" * 64, provenance={"parent_node_id": "object-000"},
            ))
        entry = {"variant": "optimized", "scene": "scene.json", "report": {"independent_generations": 1}}
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            (package / "scene.json").write_text(recovered.model_dump_json())
            asset = package / "assets/D01/optimized/object-000.ply"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"validated by the isolated trial package validator")
            with patch("scripts.package_trials.validate_trial_package", return_value=({"trials": [entry]}, None)):
                apply_reconstructed_appearances(scene, metadata, files, package)
        self.assertEqual([node.model_dump(exclude={"asset_id"}) for node in scene.nodes], original_nodes)
        self.assertEqual(scene.edges, original_edges)
        self.assertEqual(sum(asset.kind == "ply" for asset in scene.assets), 1)
        self.assertEqual(sum(asset.kind == "glb" for asset in scene.assets), 21)
        self.assertEqual(len({node.asset_id for node in scene.nodes if node.id.endswith(".crusher")}), 1)
        self.assertEqual(metadata["reconstruction"]["gaussian_module_placements"], 3)
        self.assertEqual(len(metadata["telemetry_tags"]), 56)
        self.assertEqual(
            {module["appearance_asset_id"] for module in metadata["modules"]},
            {asset["id"] for asset in metadata["appearance_assets"]},
        )
        self.assertIn("splats/object-000.ply", files)

    def test_authored_inventory_has_nonoverlapping_grounded_modules_and_joinable_telemetry(self):
        metadata = design()
        self.assertEqual(len(metadata["modules"]), 24)
        self.assertEqual(len(metadata["equipment"]), 64)
        self.assertEqual(len(metadata["streams"]), 50)
        self.assertEqual(len(metadata["telemetry_tags"]), 56)
        for module in metadata["modules"]:
            self.assertEqual(module["position"][1], module["size"][1] / 2)
        for mutation, error in (
            (lambda m: m["modules"].append(copy.deepcopy(m["modules"][0])), "inventory"),
            (lambda m: m["modules"][0].update(position=[-13, 3.5, -16]), "overlap"),
            (lambda m: m["streams"][0]["source"].update(port_id="unknown"), "port"),
            (lambda m: m["telemetry_tags"][0].update(module_id="unknown"), "attachment"),
        ):
            changed = copy.deepcopy(metadata)
            mutation(changed)
            with self.assertRaisesRegex(ValueError, error):
                validate_design(changed)
        bearing = next(tag for tag in metadata["telemetry_tags"] if tag["id"] == "D01.A.crusher.bearing_temperature")
        self.assertEqual(bearing["equipment_id"], "D01.A.crusher.bearing")
        self.assertEqual(metadata["reconstruction"]["independent_idol_generations"], 0)

    def test_d01_manifest_reparses_with_explicit_instances_without_loosening_original_trials(self):
        manifest = trial_manifest(design())
        self.assertEqual(TrialManifest.model_validate_json(manifest.model_dump_json()), manifest)
        self.assertEqual(load_manifest(ROOT / "cases/diamond-plant-trial.json"), manifest)
        self.assertEqual(len(manifest.trials[0].reviewed_objects), 12)
        self.assertEqual(len(manifest.trials[0].instances), 24)
        original = load_manifest(ROOT / "cases/trials.json")
        invalid = original.model_dump(mode="json")
        invalid["trials"][0]["instances"] *= 2
        invalid["trials"][0]["source"]["filename"] = "D01.png"
        with self.assertRaises(ValidationError):
            TrialManifest.model_validate(invalid)
        invalid = manifest.model_dump(mode="json")
        invalid["trials"][0]["source"]["url"] = invalid["trials"][0]["source"]["url"].replace("/" + "25070e70285e9228ab4453dbd0cf70a844a11922" + "/", "/main/")
        with self.assertRaises(ValidationError):
            TrialManifest.model_validate(invalid)

    def test_export_receipts_bind_source_scene_models_and_spatial_routes(self):
        metadata = design()
        scene, files = public_files(metadata)
        receipts = json.loads(files["files.json"])
        self.assertEqual(receipts, {name: hashlib.sha256(value).hexdigest() for name, value in files.items() if name != "files.json"})
        self.assertEqual(metadata["scene_sha256"], hashlib.sha256((scene.model_dump_json(indent=2) + "\n").encode()).hexdigest())
        self.assertEqual(receipts["D01.png"], metadata["source"]["sha256"])
        self.assertEqual(len(scene.assets), len(scene.nodes))
        for stream, edge in zip(metadata["streams"], scene.edges, strict=True):
            self.assertEqual(stream["route_points_m"], edge.model_dump(mode="json")["points"])
        document, _ = decode_glb(files["plant.glb"])
        self.assertTrue(any(node.get("name", "").startswith("process-") for node in document["nodes"]))
        for asset in scene.assets:
            self.assertEqual(asset.sha256, receipts[asset.uri.removeprefix("/api/assets/plant/")])

    def test_glb_module_bounds_match_authored_dimensions_and_repeat_deterministically(self):
        for kind, (_, size, _, _) in TYPES.items():
            spec = [{"id": kind, "kind": kind, "position": [0, 0, 0], "size": size}]
            data = glb(spec)
            self.assertEqual(data, glb(spec))
            document, binary = decode_glb(data)
            parent = document["nodes"][0]
            points = []
            for index in parent["children"]:
                child = document["nodes"][index]
                primitive = document["meshes"][child["mesh"]]["primitives"][0]
                accessor = document["accessors"][primitive["attributes"]["POSITION"]]
                view = document["bufferViews"][accessor["bufferView"]]
                values = struct.unpack_from("<" + "f" * accessor["count"] * 3, binary, view["byteOffset"])
                angle = 2 * math.atan2(child["rotation"][2], child["rotation"][3])
                cosine, sine = math.cos(angle), math.sin(angle)
                for start in range(0, len(values), 3):
                    x, y, z = [values[start + i] * child["scale"][i] for i in range(3)]
                    point = [x * cosine - y * sine, x * sine + y * cosine, z]
                    points.append([(point[i] + child["translation"][i]) * parent["scale"][i] + parent["translation"][i] for i in range(3)])
            for axis in range(3):
                self.assertAlmostEqual(min(point[axis] for point in points), -size[axis] / 2, places=5)
                self.assertAlmostEqual(max(point[axis] for point in points), size[axis] / 2, places=5)

    def test_publication_is_idempotent_and_refuses_unapproved_files(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "plant"
            first = publish(target)
            self.assertEqual(publish(target), first)
            (target / "unapproved.txt").write_text("private")
            with self.assertRaisesRegex(ValueError, "Unexpected"):
                publish(target)

    @unittest.skipUnless(shutil.which("blender"), "Blender is verified on the Linux CI runner")
    def test_portable_plant_imports_into_blender(self):
        _, files = public_files(design())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plant.glb"
            path.write_bytes(files["plant.glb"])
            code = (
                "import bpy; bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False); "
                f"bpy.ops.import_scene.gltf(filepath={str(path)!r}); "
                "names={o.name for o in bpy.data.objects}; "
                "assert 'D01.A.crusher' in names and 'D01.C.dms' in names; "
                "assert any(name.startswith('process-') for name in names); "
                "assert len([o for o in bpy.data.objects if o.type=='MESH'])>24; "
                "print('D01_IMPORT_VERIFIED')"
            )
            result = subprocess.run(["blender", "--background", "--factory-startup", "--python-exit-code", "1",
                                     "--python-expr", code], capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("D01_IMPORT_VERIFIED", result.stdout)


if __name__ == "__main__":
    unittest.main()
