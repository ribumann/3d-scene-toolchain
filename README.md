# 3D scene toolchain

An evidence-linked **scene preparation package for digital-twin browser apps**.
Descriptions, photos and schematics feed a shared scene contract; Blender creates
editable geometry, Idol creates selected Gaussian appearance assets, and a React
Three Fiber/Spark workbench renders and edits the result.

**Current milestone:** the [public workbench](https://red-wave-0c7bb6c0f.4.azurestaticapps.net/)
retains the original eleven samples and interim photographic trials, and adds six
illustrated prompt/schema variants. Twenty-five independent Idol generations
support 142 eligible authored placements after 32 quality exclusions; shared
instances are not independent generations. Connections retain source evidence or
explicit prompt intent. Generated appearances and provisional scale are
illustrative, not recovered engineering detail. See the [actual results, capture
recommendations and reconstruction alternatives](docs/trials.md#actual-illustrated-object-results).

**Initial baseline:** the three procedural scenarios run through real Blender
exports. Eleven case slots are implemented. All eight image references
(I01-I05 originals and G01-G03 AI-generated images) were supplied by the user and
ingested privately by the coordinating operator. The user authorized eight
metadata-stripped public WebP previews; full originals remain private.
The approved-WebP eight-case pilot subsequently completed on the Italy North
Spot T4 in [run 43043580373](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43043580373):
**31 validated real object appearances** across five photo/generated sources
and **203 unreviewed region proposals** across three diagrams/plans. The GPU job
took 1h 51m 20s; appearances used 32,768 Gaussians, 50 steps and seed 42.
These are output-contract results, not full-facility reconstruction, metric
accuracy or a calibrated/telemetry-connected digital twin. All eight derived
views are now public; their 39 derived-file hashes and eight reference hashes
were verified against the approved package. Per-case visual fidelity remains
unaccepted.

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
The initial reference-only deployment verified all three WebGL2 scenes on the real HTTPS origin. It has
no API backend. The eight authorized previews
are deployed with explicit original-vs-AI-generated provenance. The operator
separately verified all eight public preview URLs and image decoding, G03's
reference-only state, P01's 28 rendered objects and the absent API (404).

The latest retained-package deployment is
[43242769693](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43242769693),
source `2efa3bb57af111cea343efb03319c5ac45c9b603`. All 121 packaged public-file
hashes, including the four application files, match its artifact. Its 29 catalog entries
include three explicitly not-run real-photo baselines, not 29 successful
reconstructions. Six additional illustrated scenes preserve the original cases;
quality exclusions are visible and never replaced with representative geometry.
Desktop/mobile browser checks and their limits are recorded in
[the trial report](docs/trials.md#actual-illustrated-object-results).

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
and download JSON. Select I01-I05 to view original-reference previews or G01-G03
to view AI-generated-reference previews; open a preview in a new tab for detail.
The default build labels each **reference only**; an explicitly approved derived
package adds actual available outputs as described below.
Uploads, imports, scene edits, job execution and all `/api` requests are disabled.
The default build's geometry is compiled directly from the public templates; it does
not include private runtime data, Blender exports, image reconstruction, splats
or actual Idol results. `npm run build` remains the normal editable local build.

An optional, explicitly approved pilot package can add validated object PLYs
and diagram/plan proposals without exposing a backend. The viewer distinguishes
successful, partial, failed and not-run cases, keeps reference comparisons, and
never substitutes geometry for failed appearance loading. The operator verified
the initial I01-I05 derived deployment, including live I02 loading 9/9 appearances.
Final all-eight deployment also succeeded, with exact public-package hash and
case-inventory verification. This does not establish every case's browser
rendering or visual accuracy.
See the [approved export/build route](infra/azure/static-demo.md#approved-derived-pilot-packages).

Opt-in [photographic trials](docs/trials.md) compare detector/SAM2 extraction with
explicitly supervised reviewed-box/SAM2 extraction and exact validated asset reuse.
Their generated inputs and outputs remain separate from the frozen pilot;
additive trial publication requires its unchanged approved final package.
Preparation is not evidence of reconstruction quality or a measured speedup.
The additional licensed real-photo run produced four validated appearances from
three Wikimedia Commons photographs, retaining CC BY-SA 4.0 source/adaptation
credits. Actual-mask checks measured 24-89% lower CPU crop-preparation time with
identical pixels and PNG bytes; this saves milliseconds, not GPU inference time.
See the trial report for exact runs, timings, supervision and occlusion limits.

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
On 2026-11-11 the user supplied all eight image references. The coordinating
operator validated and ingested originals, previews and metadata privately
through the existing upload API. Full originals are available in that
operator's private runtime, **not in this repository or public demo**.
Only the eight separately authorized, metadata-stripped WebP previews live at
`apps/web/public/references/{I01-I05,G01-G03}.webp`. G01/G02/G03 correspond to
grocery/semiconductor/zoo. Private intake and public previews are not extraction
or reconstruction. Frozen starter prompts remain in
[`cases/manifest.json`](cases/manifest.json), but are not claimed as the exact
generation prompts for the supplied images. No further image generation is
needed; this package does not spend image-generation API credits.

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

Prepare separate CUDA-capable Python 3.12 environments for `.[vision]` extraction
and base-project + `requirements-idol.txt` inference. Their current Hugging Face
hub major requirements conflict; do not combine them or loosen the vision cap.
The vision extra includes torchvision for SAM2's fast image processor. Use
CUDA-matched torch/torchvision builds from the same PyTorch wheel index; verify
a CUDA torchvision operation and SAM2 processor loading, not just imports.
The dedicated one-object smoke uses the prepared fixed worker environments
described in [`infra/azure/README.md`](infra/azure/README.md), not this cloud
development host. `smoke_mode=readiness` checks real gated-config access on CPU
before `smoke_mode=gpu` can request the private worker.

The opt-in **private eight-case batch** is separate from the single-object smoke:

```sh
gh workflow run gpu-batch.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain -f smoke_mode=batch \
  -f smoke_source=public-preview \
  -f 'pilot_cases=I01 I02 I03 I04 I05 G01 G02 G03'
```

It extracts each photo/generated case once without the local adapter's 48-box
truncation, enumerates every usable approved non-person crop, and reconstructs distinct crops
sequentially with the successful smoke's immutable model pins and 32,768/50/42
settings. Exact duplicate crops retain every parent mapping. Completed outputs
are revalidated before resume; failures are isolated and reported, never filled
with fake geometry. I01/I04/I05 instead produce unreviewed OCR/contour region
proposals, without the normal 100-region truncation or invented process topology;
they are not Idol appearances. Placement/scale/depth are inferred, not metric.
Select a unique subset with `pilot_cases`; its default remains I02.
The eight-case run completed successfully; counts and execution evidence are in
[`docs/benchmark-status.md`](docs/benchmark-status.md), not an accuracy certificate.
Setup, output/checkpoint paths and retry semantics are in the Azure guide.
The user approved published previews for faster input intake, retaining originals
for final comparison. This uses staged, authorized WebPs and records `user-approved-public-webp-preview` provenance,
actual SHA/dimensions and `not_original_bytes=true` in a separate checkpoint
tree. It never overwrites original Store records or silently falls back.
The original-input I02 route remains available as `smoke_source=private-original`.
Outputs remain private by default. `publish_pilots=true` explicitly approves only
revalidated derived preview-input scenes/PLY for a separate allowlisted artifact;
`smoke_mode=package` exports stopped checkpoints without repeating inference.
Neither option uploads originals, masks/crops or raw logs.
Package-only mode uses a separate CPU publisher runner; with
`incremental_pilots=true`, completed sources can be published individually while
the GPU batch continues. Active cases remain honestly labeled `processing`, with
no scene or in-progress object publication.

Pin full **40-character commit SHAs** in the worker environment:

```text
SCENE_IDOL_MODEL_REVISION=<speridlabs/idol commit>
SCENE_DINOV3_REVISION=<DINOv3 commit>
SCENE_FLUX2_REVISION=<FLUX.2-dev commit>
SCENE_DETECTOR_REVISION=<IDEA-Research/grounding-dino-tiny commit>
SCENE_SEGMENTER_REVISION=<facebook/sam2.1-hiera-small commit>
```

The SDK is pinned in `requirements-idol.txt`. The historical combined-environment full-batch command below is not certified
against that dependency conflict; prefer the documented isolated smoke first:

```sh
.venv/bin/scene-toolchain run --cases P02 \
  --stages extract blender idol --report .scene-data/gpu-smoke.json
```

The initial adapter uses 32,768 Gaussians, 50 steps and seed 42. A T4 gets a
float32 DINO encoder and SDPA rather than assuming native bf16 support. Compile is
disabled until measured; `SCENE_IDOL_COMPILE=1` enables the SDK optimization path.
Only the FLUX VAE is downloaded. PLY output is checked for Gaussian attributes,
finite values, normalized rotations and nondegenerate bounds before publication.
Generated hidden surfaces remain guesses. The unchanged normal local API adapter
attaches an appearance asset to its first suitable visible object; the private
pilot batch is a separate explicit route. Automatic per-object quality ranking
and metric calibration remain future improvements.

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
without auto-shutdown and verified real `nvidia-smi`, CUDA kernels and one private
I02 tree-object Idol reconstruction. Full archive intake on that VM remains
incomplete; I02 was transferred and checksum-verified separately, while all eight
originals remain valid in the operator's local runtime.
See the Azure guide for the observed status and source-template
limitations. Do not queue against a guessed GPU runner or reuse another project's
cloud identities/resources. GPU artifacts are opt-in: the original procedural
report and the separately approved derived pilot package have distinct allowlists.
Uploaded original images, segmentation crops and raw inference logs are excluded.

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
