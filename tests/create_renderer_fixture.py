"""Create an explicitly synthetic Gaussian fixture, NOT an Idol inference result.

Usage: .venv/bin/python tests/create_renderer_fixture.py /tmp/scene-render-test
Run the API with SCENE_DATA_DIR pointing there to smoke-test the GPU renderer.
"""

import hashlib
import sys
from pathlib import Path

import numpy as np

from scene_pipeline.models import Asset
from scene_pipeline.store import Store


def create(directory):
    store = Store(directory)
    scene = store.current("P02")
    scene.name = "RENDERER TEST - synthetic Gaussians"
    scene.description = "Rendering fixture only: these synthetic Gaussians were not produced by Idol."
    node = next(node for node in scene.nodes if node.id == "station-0")
    count = 2048
    names = ["x", "y", "z", "nx", "ny", "nz", "f_dc_0", "f_dc_1", "f_dc_2",
             "opacity", "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]
    values = np.zeros(count, dtype=[(name, "<f4") for name in names])
    rng = np.random.default_rng(42)
    positions = rng.uniform(-.45, .45, (count, 3))
    for axis, name in enumerate(("x", "y", "z")):
        values[name] = positions[:, axis]
    for name in ("scale_0", "scale_1", "scale_2"):
        values[name] = -3.4
    values["rot_0"] = 1
    values["opacity"] = 2
    values["f_dc_0"], values["f_dc_1"], values["f_dc_2"] = 1, .2, -.8
    path = store.asset_path("renderer-test/synthetic.ply")
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"ply\nformat binary_little_endian 1.0\nelement vertex {count}\n"
    header += "".join(f"property float {name}\n" for name in names) + "end_header\n"
    path.write_bytes(header.encode() + values.tobytes())
    scene.assets.append(Asset(
        id="synthetic-renderer-fixture", kind="ply", uri="/api/assets/renderer-test/synthetic.ply",
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(), node_id=node.id,
        provenance={"synthetic_test_fixture": True, "not_idol_output": True,
                    "bounds": {"min": positions.min(axis=0).tolist(), "max": positions.max(axis=0).tolist()}},
    ))
    node.asset_id = "synthetic-renderer-fixture"
    node.evidence.note = "Synthetic renderer fixture, not an Idol model result or manufacturing evidence."
    store.save(scene, expected_revision=scene.revision)
    print(f"Created isolated rendering test data at {store.root}; do not count as inference validation")


if __name__ == "__main__":
    create(Path(sys.argv[1]))
