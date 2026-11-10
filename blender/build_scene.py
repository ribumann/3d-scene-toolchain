"""Run with blender --background --python build_scene.py -- --scene ... --out ..."""

import argparse
import json
import os
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy
from scene_toolchain import authoring


def main():
    parser = argparse.ArgumentParser(description="Build a semantic Blender digital-twin scene")
    parser.add_argument("--scene", required=True, help="Scene JSON")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--reference-node", action="append", default=None,
                        help="Visible node ID to render; repeat up to 16 times (default: first suitable object)")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    data = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    authoring.validate_scene(data)
    if args.reference_node is None:
        candidate = next((node for node in data["nodes"] if node["visible"]
                          and node["category"] not in ("ground", "fence", "vegetation", "control")), None)
        refs = [candidate["id"]] if candidate else []
    else:
        refs = args.reference_node
    if len(refs) > 16:
        raise ValueError("At most 16 reference renders; select nodes with --reference-node")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 8
    scene.cycles.use_denoising = False
    scene.cycles.max_bounces = 3
    authoring.import_scene(data)
    authoring.export_glb(out / "scene.glb", scene)
    authoring.render_references(out / "references", refs)
    (out / "assets.json").write_text(json.dumps({
        "description": "External asset references only; PLY is not rendered as Gaussian splats.",
        "assets": data["assets"],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "scene.blend"))
    print(f"Scene outputs written to {out}", flush=True)


if __name__ == "__main__":
    # Blender otherwise reports many Python failures as process exit code 0.
    completed = False
    try:
        main()
        completed = True
    finally:
        if not completed:
            traceback.print_exc()
            sys.stderr.flush()
            os._exit(1)
