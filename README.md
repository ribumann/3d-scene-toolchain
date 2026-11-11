# 3D scene toolchain

An evidence-linked **scene preparation package for digital-twin browser apps**.
Descriptions, photos and schematics feed a shared scene contract; Blender creates
editable geometry, Idol creates selected Gaussian appearance assets, and a React
Three Fiber/Spark workbench renders and edits the result.

**Current milestone:** the three procedural scenarios run through real Blender
exports. Eleven case slots are implemented. The eight image cases require their
original files; actual segmentation/Idol GPU inference has not yet been verified.
An operator-deployed Italy North Spot T4 now has verified driver/hardware access,
not verified model execution. This is not a calibrated or telemetry-connected
digital twin.

## Start locally

Requirements: Python 3.11+, Node 22.12+, npm, and Blender 4.x for authoring/export.
The browser requires WebGL2; no inference GPU needs to be attached to the browser
host.

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
npm ci
.venv/bin/scene-toolchain serve
```

In another terminal:

```sh
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`. Select Grocery aisles, Semiconductor assembly or Zoo
habitats. Select objects, inspect provenance, edit positions/labels/visibility and
save a new revision. JSON import/export supports explicit scene interchange.
The UI reports unavailable tools, conflicting revisions and failed jobs.

The API binds to loopback by default. It is an unauthenticated **local workbench**,
not a production multi-tenant service. Do not expose it publicly without adding
authentication, tenant isolation, quotas and a hardened asset storage policy.
`SCENE_WEB_ORIGIN` allows an explicitly configured frontend origin; no wildcard
cross-origin mutation permission is granted.

## Public read-only demo build

[Open the public read-only demo](https://red-wave-0c7bb6c0f.4.azurestaticapps.net/).
The operator verified all three WebGL2 scenes on the real HTTPS origin. It has
no API backend, uploaded image inputs or actual Idol inference results.

The separate static build needs no backend, Blender or inference GPU:

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
npm ci
. .venv/bin/activate
npm run build:demo
python3 -m http.server 4173 --bind 127.0.0.1 --directory apps/web/dist-demo
```

Open `http://127.0.0.1:4173`. This is the existing workbench in explicitly
read-only demo mode: browse three deterministic procedural scenes, select and
isolate objects, inspect evidence, change camera/labels, play illustrative routes
and download JSON. Eight image-input slots remain visibly unavailable.
Uploads, imports, scene edits, job execution and all `/api` requests are disabled.
The published geometry is compiled directly from the public templates; it does
not include private runtime data, Blender exports, image reconstruction, splats
or actual Idol results. `npm run build` remains the normal editable local build.

Publish only `apps/web/dist-demo/`, not the repository or `.scene-data/`.
Azure static website preparation and deployment commands are in
[`infra/azure/static-demo.md`](infra/azure/static-demo.md).

Runtime metadata and private media live under ignored `.scene-data/`; set
`SCENE_DATA_DIR` to use another directory. Source files are never committed
automatically. They may also appear in derived crops/renders: review publication
rights before sharing assets or Actions artifacts.

## Pipeline

```text
description -> fixed scenario layout/reference renders --+
photo -> Grounding DINO + SAM2 object masks/crops --------+
diagram/plan -> OCR + line-contour region proposals ------+
                                                         |
                                      reviewable scene.json
                                         /             \
                                Blender meshes      Idol object PLY
                                         \             /
                                  browser scene + proxies
```

`schemas/scene.schema.json` is generated from the Python validation model.
`packages/scene/types.ts` supplies matching browser types. Scenes use meters,
right-handed Y-up coordinates, stable semantic IDs, directed routes, provenance,
sources and versioned assets. Validation rejects duplicate IDs, dangling
references, invalid dimensions, nonfinite values and external asset URLs.

Blender's headless builder produces `.blend`, `.glb` and isolated object renders.
The add-on imports/exports scene JSON while preserving IDs and evidence; see
[`blender/README.md`](blender/README.md). Gaussian assets remain external with
proxy geometry in Blender. Idol's PLY export is already Y-up; the workbench fits
each splat to its semantic node dimensions without a second axis flip.

Scene edits use optimistic revision checking. Regeneration refuses to overwrite
manually edited layouts. Original revisions remain retrievable. Worker stages
record timings and errors; queued work is persisted, interrupted jobs fail
explicitly, and cancellation prevents publication of unfinished stages.
Validated source/reference artifacts can be reused for later steps. Full
content-addressed stage-result caching and distributed workers are not implemented.

### Procedural batch

```sh
.venv/bin/scene-toolchain preflight
.venv/bin/scene-toolchain run --cases P01 P02 P03 \
  --stages extract blender --report .scene-data/procedural-report.json
.venv/bin/scene-toolchain export P02 --out .scene-data/P02-scene.json
```

Set `BLENDER_BIN` if Blender is not on PATH. The CLI writes a nonzero exit status
if any requested case/stage fails. The three description cases use intentionally
fixed, deterministic templates, not an unrestricted natural-language CAD parser.
Their shapes are illustrative primitives and can be improved in Blender or
replaced with verified assets.

## Image cases and review

| Cases | Inputs | Initial extraction |
|---|---|---|
| I01, I04 | Mineral flowsheet, assembly diagram | OCR/line-contour region proposals |
| I05 | Japanese factory plan | Footprint candidates, original Japanese OCR |
| I02, I03 | Outdoor plant, vessel-room photo | Grounding DINO + SAM2 masks/crops |
| G01-G03 | Separately generated retail, semiconductor and zoo images | Same object-segmentation path |

Upload the original JPEG, PNG or WebP to its case (12 MiB, 20 million pixels max).
The five images displayed in the planning conversation are **not included**:
conversation display does not automatically make their original bytes available
to the checkout. Generated-image starter prompts are frozen in
[`cases/manifest.json`](cases/manifest.json); create them elsewhere and upload
their outputs. This package does not spend image-generation API credits.

CPU diagram extraction:

```sh
sudo apt-get install tesseract-ocr tesseract-ocr-jpn
.venv/bin/pip install -e ".[ocr]"
```

Extraction produces **unreviewed candidates**, not ground truth. The initial OCR
adapter does not solve arrows, line crossings, recirculation, semantic symbols or
translation. Review labels/footprints and explicitly author directed edges using
scene JSON or Blender; do not infer factory placement from a logical flowsheet.
Photos use approximate image-plane placement, not calibrated depth. The person in
the vessel-room reference is not an identity-reconstruction target.

## GPU worker and gated model access

Idol reconstructs an **individual object's appearance**, not a whole room or a
schematic. Its public weights depend on gated image encoders:

- [DINOv3 ViT-H+](https://huggingface.co/facebook/dinov3-vith16plus-pretrain-lvd1689m)
- [FLUX.2-dev](https://huggingface.co/black-forest-labs/FLUX.2-dev), VAE only

Accept both models' access terms with your Hugging Face account. Configure a
read-access `HF_TOKEN` on the GPU worker (or as an Actions secret), never in Git,
chat, the frontend, shell history or deployment templates. Model terms and
commercial-use rights must be reviewed separately from this repository's MIT
license and Idol's Apache-2.0 SDK license.

Install on a CUDA-capable worker, not necessarily this development host:

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[vision]" -r requirements-idol.txt
```

Pin full **40-character commit SHAs** in the worker environment:

```text
SCENE_IDOL_MODEL_REVISION=<speridlabs/idol commit>
SCENE_DINOV3_REVISION=<DINOv3 commit>
SCENE_FLUX2_REVISION=<FLUX.2-dev commit>
SCENE_DETECTOR_REVISION=<IDEA-Research/grounding-dino-tiny commit>
SCENE_SEGMENTER_REVISION=<facebook/sam2.1-hiera-small commit>
```

The SDK is pinned in `requirements-idol.txt`. First run:

```sh
.venv/bin/scene-toolchain run --cases P02 \
  --stages extract blender idol --report .scene-data/gpu-smoke.json
```

The initial adapter uses 32,768 Gaussians, 50 steps and seed 42. A T4 gets a
float32 DINO encoder and SDPA rather than assuming native bf16 support. Compile is
disabled until measured; `SCENE_IDOL_COMPILE=1` enables the SDK optimization path.
Only the FLUX VAE is downloaded. PLY output is checked for Gaussian attributes,
finite values, normalized rotations and nondegenerate bounds before publication.
Generated hidden surfaces remain guesses. The first selected visible non-ground
object gets the appearance asset; full automatic per-object quality ranking,
batch generation and metric calibration are future improvements.

### Where to run

- **Regular GitHub Actions:** CPU checks and Blender exports; not GPU inference.
- **Configured GPU runner:** manual `Trusted GPU benchmark` workflow, protected
  `scene-gpu` environment, actual label in `SCENE_GPU_RUNNER`. A GitHub-hosted T4
  larger runner requires eligible organization setup. A self-hosted GPU label
  can also work with an appropriate trust policy and preinstalled Blender.
- **Azure Italy North:** OIDC preflight plus a bounded dedicated T4 VM deployment
  template and operator commands in [`infra/azure/README.md`](infra/azure/README.md).
  Authorization does not supply an Azure identity: the intended external tenant
  and subscription must be authenticated/configured first.

The coordinating operator deployed an explicitly approved Italy North Spot T4
without auto-shutdown and verified real `nvidia-smi`; PyTorch/model inference
remains unrun. See the Azure guide for the observed status and source-template
limitations. Do not queue against a guessed GPU runner or reuse another project's
cloud identities/resources. GPU artifact upload is opt-in and limited to the
procedural benchmark; uploaded source images are excluded.

## Validation

```sh
.venv/bin/python -m unittest discover -s tests -v
npm run build
npm test -- --run
```

Tests include actual Blender GLB/reference exports, coordinate/rotation
round-trips, schema/API revisions, source safety, missing prerequisites,
cancellation, Gaussian validation, OCR on a **synthetic test diagram**, and Azure
guard logic. `tests/create_renderer_fixture.py` creates explicitly synthetic
Gaussians for renderer-only checks; it is not Idol inference evidence.

Actual case status and limits are in [`docs/benchmark-status.md`](docs/benchmark-status.md).
No fidelity/performance certification is claimed from passing unit tests.

## Digital-twin extension seam

Use semantic node IDs to bind future equipment data, not mesh indices or labels.
Keep live values, timestamps, quality/staleness and units outside geometry
revisions. See [`docs/digital-twin-integration.md`](docs/digital-twin-integration.md)
for a proposed envelope and manufacturing, maintenance, training, inventory and
visitor-wayfinding uses. Telemetry ingestion and safety/process simulation are
not implemented in this milestone.
