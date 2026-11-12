# Blender scene authoring

This tool creates editable, illustrative manufacturing and other digital-twin
scenes from the shared Scene 1.0 JSON. It is not an engineering-certified twin;
dimensions, inferred content, and hidden geometry require independent review.
It does not ingest live telemetry. The stable node IDs and retained source and
evidence fields are the extension seam for future overlays.

## Requirements and headless build

Use Blender 3.6 or newer with its bundled glTF 2.0 exporter and Cycles CPU
renderer. Some Linux distribution packages split out NumPy, which the glTF
exporter requires (on Ubuntu: `apt install blender python3-numpy`).

```sh
blender --background --python /absolute/path/to/blender/build_scene.py -- \
  --scene /absolute/path/to/scene.json --out /absolute/path/to/output
```

Paths may also be relative to the process working directory. Outputs:

- `scene.blend`: editable nodes, route curves, studio camera, lights and ground.
- `scene.glb`: visible node meshes and routes, with semantic IDs in glTF extras;
  the studio camera, lights and ground are not exported.
- `references/{node_id}.png`: transparent 256×256 isolated-object images rendered
  from the proxy geometry, plus `references/manifest.json` mapping filenames to
  node IDs. These contain no input/source images.
- `assets.json`: original external asset references and provenance, not copied
  assets. PLY/Gaussian splats are **not** interpreted, imported as a point cloud,
  or rendered. Nodes remain editable geometric proxies, including for GLB assets.

By default, the first visible node excluding categories `ground`, `fence`,
`vegetation`, and `control` gets a reference, regardless of evidence origin.
If there is no suitable node, no image is rendered. To choose different visible
nodes, repeat `--reference-node NODE_ID`. Reference IDs must use the pipeline's
safe identifier format: an ASCII letter or digit followed by up to 95 ASCII
letters, digits, underscores, dots or hyphens. Unsafe IDs are rejected rather
than written outside the reference directory. At most 16 references are allowed;
choose a subset if necessary. Rendering uses 8 Cycles
CPU samples, a fixed resolution, and a three-bounce limit. The command exits
nonzero on invalid data or build failures. Keep generated outputs outside the
repository if they contain private scene data.

## Add-on installation and use

Create a portable add-on ZIP from the package directory (not from the whole repo):

```sh
cd /absolute/path/to/blender
zip -r /tmp/scene_toolchain.zip scene_toolchain -x '*/__pycache__/*' '*.pyc'
```

In Blender, use **Edit → Preferences → Add-ons → Install from Disk** (on older
versions, **Install**), select the ZIP, and enable **Scene Toolchain**. Open the
3D View sidebar with `N`, then **Scene Twin**. Import a Scene JSON into a fresh,
empty Blender scene (remove the default cube if present). The panel displays the active node's stable ID, evidence, source
and asset reference. Sources/assets remain in the imported scene's metadata;
images and assets are not fetched. Save the `.blend` to retain that metadata.

Use Blender's standard move, rotate, scale, material and poly-curve edit tools.
Export with **Export Scene JSON and GLB**; the chosen JSON and a same-named GLB
are written together. Export ends Edit Mode to flush geometry changes. Node and
route IDs must not be deleted, duplicated or changed; the exporter refuses to
silently drop them. Export preserves the original sources, assets, evidence,
categories and other metadata. Changes to a node's Principled BSDF base color
and render visibility, transform and local mesh bounding dimensions are saved.
JSON retains the original primitive shape, not arbitrary mesh edits; the GLB
contains edited meshes. Route editing uses a single poly spline per route; adding
other spline types or additional splines is rejected rather than losing data.
Empty paths remain empty. Sheared or degenerate transforms are rejected.

Scene positions are right-handed Y-up meters; the basis change is
`(x, y, z) → (x, -z, y)` in Blender. Rotation uses Three.js XYZ Euler matrices
and a basis conjugation, not an Euler component swap. Dimensions are local
primitive dimensions, not rotated world-axis bounding boxes. Cylinders and cones
have their height along web Y / Blender Z. Planes are thin solids with the
specified positive dimensions. Colors are CSS hex (`#rgb`, `#rgba`, `#rrggbb`,
or `#rrggbbaa`); zero or negative dimensions are rejected.

## Verification

From the repository root, run `python -m unittest discover -s tests`. Blender
smoke tests run when `blender` is on PATH, or when `BLENDER_BIN` names its
executable; otherwise they are explicitly skipped. Tests build into temporary
directories and verify a real GLB, transparent reference render, add-on export,
metadata and coordinate round trips.
