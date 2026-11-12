# Opt-in photographic industrial trials

## Prompt and schema reference candidates

An opt-in `gpu-batch.yml` `smoke_mode=illustrations` route generates contextual
photographic candidates for explicit concept identities in `cases/illustrations.json`.
Select `cases="P01 P02 P03 I01 I04 I05"` for all currently curated descriptions.
This is not a reconstruction result or a public demo release.

The generator is Apache-2.0 `segmind/SSD-1B` pinned to
`60987f37e94cd59c36b1cba832b9f97b57395a10`, using the existing Diffusers runtime,
fp16, CPU offload, 1024px, 30 steps and guidance 9. Each identity gets a stable
seed; receipts record the exact description, prompt, model/settings, output hash
and actual library versions. Exact successful candidates can resume; changing
the description/settings changes the cache location. No frozen runtime is upgraded.

Candidates retain a background and require inspection, target-box review,
segmentation and Idol reconstruction before becoming illustrative scene assets.
They invent appearance from descriptions: they cannot recover the actual hidden
appearance of schematic equipment. The workflow uploads only these generated
candidates and receipts, never private inputs, masks, logs or credentials.

The subsequent `smoke_mode=illustrated-objects` route requires a committed
`cases/illustration-reviews.json` with exact candidate hashes, normalized XYWH
boxes and review notes. It runs SAM2 and Idol in separate sequential processes,
validates successful receipts before resuming, and exports only a strictly
validated `illustration-publication-<run>` package. Source pixels, segmentation
and generation files are hash checked; failures do not produce replacement
boxes. No category-only similarity cache is used.

The optional `ci.yml` `illustration_run_id` builds six **additional**
`P01/P02/P03/I01/I04/I05-illustrated` cases, never replacing original cases or
interim comparisons. It requires the retained pilot `43079293375` and trial
`43185525449` publications. Prompt objects intentionally share concept assets;
complete machines replace overlapping housing/control proxies, and complete
trees replace separate trunk/canopy primitives.

I04 preserves all 93 numbered main-line/engine stations, eight buffers and
100 directed relationships, including the Engine branch into Chassis 2.
I01 asserts only two reviewed feed relationships; ambiguous junctions remain
unasserted. I05 uses eight reviewed principal building footprints and invents
no process links from proximity. Edge evidence records reviewed diagram
relationships separately from authored prompt routes. All 3D routes are
relative authored paths, not measured physical pipes or flow simulation.

## Scene-wide geometry screening

The static builder assesses every approved original and interim PLY without
changing its bytes or the frozen publication. A separate `demo/quality.json`
binds assessments to exact PLY hashes. Missing or mismatched assessments fail
explicitly. Covariance-aware bounds include four-sigma support for Gaussians
whose opacity is at least 1/255; essentially invisible tails do not set scale.
Exclusions cover support over four times the visible center extent and center
outliers over six times the 1st-to-99th-percentile extent.

The viewer now fits these extents **uniformly** instead of independently stretching
all three axes. It also excludes appearances requiring over 8x aspect distortion
against the provisional semantic box, with visible reasons and no representative
box substitute. Existing layouts and source credits remain unchanged.
These are conservative geometric heuristics, not semantic acceptance, proof of
bad source dimensions, recovered scale or accuracy certification. An excluded
object can need a better crop, corrected semantic dimensions or a new generation.

## Licensed real photographs and crop preparation

R01-R03 are real, whole-frame photographs found on Wikimedia Commons, not generated
images or isolated product cutouts. The committed `cases/trials.json` adds these to
the unchanged T01-T03 definitions. Immutable prepared PNGs and original provenance
are at input commit `073aa63dc4428aea5080b3c4ae93ecc17aa44c1b`, under
`research/real-photos/`. The source model requires creator, source page, original
and prepared hashes, preparation changes, limitations, and CC BY-SA 4.0 licensing
for both the source and source-derived adaptations. That license is separate from
the software MIT license; credits and modification notices accompany public scenes.

R01 targets one foreground horizontal pump/motor assembly; R02 one foreground
vertical pump/motor; R03 two distinct central blue pump assemblies. Reviewed boxes
are manual semantic supervision, not ground-truth masks. R01 has background
overlap; R02 is cut at the lower image edge; R03 intentionally stresses wider-site
occlusion. None establishes optimal capture or recovered hidden geometry.

The additional optimization crops RGB pixels and the SAM mask **before** creating
RGBA buffers, instead of allocating full-frame RGBA/mask images per object.
Regression cases check exact pixels and PNG bytes at image edges and with empty,
full and signed masks. The model pins, seed, sampling steps, crop policy, and
exact-cache keys are unchanged. This is a CPU preparation optimization, not a
claim of faster GPU sampling or improved 3D accuracy.

Run only the four reviewed targets with:

```sh
gh workflow run gpu-batch.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain \
  -f smoke_mode=trials -f smoke_source=public-preview \
  -f 'pilot_cases=R01 R02 R03' -f trial_variants=optimized
```

The existing isolated trial publisher exports the additive six-input package.
Original three-input packages remain accepted only when their complete T01-T03
definitions exactly match the registered originals. Publication must retain pilot
package `43079293375`; unexecuted real-photo baselines stay explicitly `not_run`.

### Completed real-photo run and measured preparation

Protected GPU run
[`43183250475`](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43183250475)
succeeded at source `7af4cd6a55e4b5290bad68bd8405d2076e19be3d`:
R01 produced one validated appearance in 215.010 seconds, R02 one in 221.060
seconds, and R03 two in 440.043 seconds. These were four independent generations
with no exact-cache hits. The boxes were reviewed manually; the counts do not
measure automatic detection, complete assemblies or reconstruction accuracy.
R03's occluded, cropped assemblies remain a difficult partial-visibility example.
The isolated publisher
[`43185525449`](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43185525449)
retains all six synthetic variants and adds the three successful real-photo
variants plus three explicitly unexecuted baselines: 33 hash-bound files.

The actual saved SAM alpha crops passed exact pixel and encoded-PNG equivalence
against the legacy preparation. On the same VM, after three warmups and 25
alternating paired repetitions per crop:

| Actual crop | Legacy median ms | Crop-first median ms | Source pixels | Crop pixels |
|---|---:|---:|---:|---:|
| R01 object-000 | 5.3906 | 4.1087 | 2,430,000 | 1,588,248 |
| R02 object-000 | 4.9547 | 3.3165 | 2,160,000 | 1,179,900 |
| R03 object-000 | 5.0628 | 0.5813 | 2,430,000 | 167,670 |
| R03 object-001 | 5.0451 | 0.5987 | 2,430,000 | 172,431 |

This is approximately 24-89% less **CPU crop-preparation time only**, saving
milliseconds rather than the roughly 215 seconds of object inference. It is not
an end-to-end speedup claim. Pixel areas describe the RGBA working region, not
measured peak process memory. Segmentation, PNG encoding, annotation and GPU
sampling are excluded. Reproduce with `scripts.benchmark_masked_crop` against
completed, unchanged private trial checkpoints.

These trials are separate from the frozen eight-source pilot and its approved
publication `43079293375`. Primary T01-T03 inputs are synthetic photographic
equipment-room scenes with backgrounds, clutter, shadows and modest occlusion,
not isolated studio products. Earlier studio images are controls only, not primary
inputs or evidence of pipeline improvement. T01-T03 compare detector/SAM2 extraction with explicitly
supervised reviewed-box/SAM2 extraction, not a pure algorithm A/B or a measured
reconstruction-accuracy benchmark. Manual boxes are a supervised comparison, not
proof that automatic detection improved. Expected inventories count target
equipment, not every background cable/shelf; extraction mistakes, contamination
and failures still require explicit review. No persons or private reference imagery are
inputs. Synthetic photographic inputs, manually authored semantics/layout and generated
3D appearances are distinct evidence.

## Completed photographic comparison

Actual protected GPU run
[`43164397173`](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43164397173)
completed successfully on the existing T4, with sequential baseline/optimized
execution at source `546ba7ee4332ccbf345171f88e7cc9bf9dff1197`.
Final isolated publication
[`43171067330`](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43171067330)
contains all six stopped variants, 13 independently generated appearances and
23 hash-bound files. All outputs use the frozen settings below. No cache hit,
resume, fabricated appearance or shared-identity instancing occurred in this run.

| Input | Target equipment | Baseline proposals / validated appearances | Reviewed-box proposals / validated appearances | Baseline wall seconds | Reviewed-box wall seconds |
|---|---:|---:|---:|---:|---:|
| T01 utility-room pump | 1 | 1 / 1 | 1 / 1 | 407.548 | 223.110 |
| T02 pump, tank and cabinet | 3 | 5 / 5 | 3 / 3 | 1088.790 | 652.884 |
| T03 two separate pumps | 2 | 1 / 1 | 2 / 2 | 225.102 | 440.168 |

`Succeeded` means generation and validation succeeded for the usable proposals,
not that the declared equipment inventory was recovered accurately. T02's baseline
labels include two cabinet and two tank proposals; supervised boxes targeted the
three declared assemblies instead. T03's baseline produced only one proposal for
two target pumps, whereas supervised boxes produced two. These observations support
reviewing equipment identities before spending inference on every proposal; they
do not establish automatic detector accuracy or geometric fidelity.

The comparison is ordered and not repeated: T01's first generation took 340.577
seconds versus roughly 215 seconds for subsequent individual generations, so
startup/order effects confound its apparent speed difference. T02's lower wall
time accompanies two fewer generations; T03's more complete target inventory
costs an additional generation. Manual annotation time is not included.
Exact-cache correctness is covered by regression tests, but these photographic
variants did not demonstrate a cache speedup because their crop bytes differed.

Deployment
[`43171802129`](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43171802129)
published source `a56985176963ace74d5e9d9ee1de3932eca45f59`, including the
orientation correction below. Live verification matched all 69 data/reference
hashes and four app files, retaining the eight original pilots and all six trial
variants in the 17-case catalog. The public browser loaded the six variants with
appearance counts 1, 1, 5, 3, 1 and 2, respectively, and original I02 with 9/9.
The reviewed T02 pump, tank and cabinet were also visually checked upright.
Open the [reviewed T02 scene](https://red-wave-0c7bb6c0f.4.azurestaticapps.net/?case=T02-optimized)
and use the trial controls to compare its detector baseline.

The additional illustrative-reference review selects 25 concepts with exact PNG
hashes and normalized boxes in `cases/illustration-reviews.json`. Factory-interior
and cropped-tank candidates were rejected. A replacement exterior was accepted;
the replacement tank still depicted the wrong equipment and is not authorized as
a thickener. Missing appearances are omitted, not replaced with boxes. Input
review authorizes reconstruction, not acceptance of the resulting 3D geometry.
Generated machines illustrate equipment roles and do not verify their engineering.

`cases/appearance-reviews.json` additionally excludes two individually inspected
G03 outputs (pond 2 and enclosure 3) whose disconnected fragments passed numeric
screening. Overrides bind exact public PLY SHA256 values, never categories or
mutable asset IDs; the frozen input packages and PLY bytes remain unchanged.

### Actual illustrated-object results

GPU run [`43221874007`](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43221874007)
completed 25 independent Idol generations from reviewed generated photographs.
Its publication failed on an overly restrictive dtype check, not reconstruction.
The worker actually exported `bf16`; publication now preserves that value and
accepts only the worker's supported `bf16`/`fp32` exports. Successful recovery
[`43237905142`](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43237905142)
validated and resumed all 25 checkpoints without another generation.
All outputs use the frozen model/SDK revisions, 32,768 Gaussians, 50 steps and seed 42.

Six additive `-illustrated` cases preserve the original eleven cases and interim
trials. They contain 174 authored placements, not 174 independent generations or
recovered equipment identities. The same decoded appearance is explicitly shared
across instances, including I04's 93 assembly stations and eight buffers.
Connections retain reviewed diagram evidence or explicit prompt intent; I05
building proximity does not invent process links. Two unconvincing thickener
references were rejected before reconstruction.

Actual browser inspection covered all six layouts and 24 isolated captures
(23 unique numerically eligible appearances, with the shared buffer shown twice).
It also revealed viewport growth driven by the expanded case library and narrow
camera framing: the viewport is now bounded to screen height, isolation reframes
the selected object, and camera distance accounts for portrait aspect ratios.
Uniformly fitted appearances are seated on their provisional semantic-node base
instead of floating at the center of an oversized box. This is authored placement,
not measured physical pose or metric scale.

Keep the quality gates, rather than stretching failures into plausibility:
all 18 P01 shelving placements fail the aspect gate, and P02's wafer-loader fails
the Gaussian-support extent gate. Individually reviewed generated tree and
conveyor PLY hashes are additionally excluded: the tree lacks the requested
complete trunk, while the conveyor consists of disconnected sections. Those
two appearances account for 13 placements. Thus 142 of the 174 authored
placements remain eligible after 32 exclusions; exclusion is not a failed-load
box substitute. These are illustrative, sometimes incomplete appearances, not
validated engineering models or recovered hidden detail.

Deployment [`43242769693`](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43242769693)
passed both full CI jobs and published source
`2efa3bb57af111cea343efb03319c5ac45c9b603`, retaining pilot `43079293375`,
trial `43185525449` and illustration `43237905142` packages. All 121 public-file
hashes were checked against the exact deployed artifact, including the four
application files and all 73 PLYs covered by quality assessments. The 29 catalog entries
include three explicitly not-run real-photo baselines.

Final local browser confirmation covered all six illustrated layouts and their
21 eligible unique appearances at desktop width, plus P03/I04 at 390 pixels.
Public-origin checks confirmed P03 3/4 appearances with 12 excluded placements,
I01 7/8 with one exclusion, and I04 2/2 shared appearances with 101 placements.
Public narrow-screen P03 checks confirmed readable, non-overlapping quality
warnings and complete isolated-object framing. Retained I02, G03 and R03 loaded
5/9, 5/16 and 2/2 respectively; excluded counts were 4, 11 and 0, not load
failures replaced by geometry. The illustrated P01 default and API absence (404)
were also confirmed. No page errors were observed in these checks; this does not
certify device performance, geometric accuracy or all possible camera views.

### Next comparisons and better input capture

The highest-value improvement is better observation, not a larger generation
step count. Use complete objects including feet/baseplates, sharp textures,
diffuse and consistent exposure, margins for masks, and visible gaps between
neighboring objects. Record identity and a real scale reference separately.
Avoid motion, heavy occlusion, strong reflections and transparent surfaces.
For multiview reconstruction, photograph the same stationary object or facility
from overlapping views at several elevations, with consistent focus and lighting;
do not mix independently generated viewpoints and call them calibrated evidence.

For prompt-only illustrations, specify equipment role, broad shape/material,
complete silhouette, a three-quarter photographic view and a realistic installed
background. Do not request a finished 3D render. Review the image before masking:
reject wrong equipment types, cut-off objects and ambiguous overlapping subjects.
Generated reference scale, unseen sides, labels and mechanical details remain
invented even when the picture looks realistic.

For schemata and plans, prefer straight, high-resolution scans or vector exports,
readable component IDs, a declared equipment inventory, explicit ports and arrow
directions, a legend and a scale where actually known. Keep appearance generation
separate from the connectivity graph; no relation follows just from nearby boxes.
Next evaluate mask coverage, recognizable identity, aspect/extent failures and
held-out-view consistency separately from syntax-valid PLY counts. Report model
loading, extraction, sampling, annotation and publication time separately.
Profile model loading before introducing a persistent warmed worker; preserve
vision/reconstruction VRAM separation, exact-cache contracts and exporter/viewer
orientation checks. A warmed worker is a proposed improvement, not a measured
speedup in these runs.

| Candidate | Most useful comparison | Constraint from primary documentation |
| --- | --- | --- |
| [SAM 3D Objects](https://github.com/facebookresearch/sam-3d-objects) | Mask-conditioned objects in cluttered/occluded natural photographs, including pose/layout | [Setup](https://github.com/facebookresearch/sam-3d-objects/blob/main/doc/setup.md) requires Linux, at least 32 GB VRAM and authorized checkpoint access under the custom SAM License. Not a drop-in for this 16 GB T4. |
| [TRELLIS.2](https://github.com/microsoft/TRELLIS.2) | Textured mesh/PBR alternatives for individual objects and thin/open surfaces | MIT-licensed repository; official setup requires at least 24 GB VRAM. Published seconds are H100 measurements, not T4 predictions. GLB output is not itself a Gaussian splat. |
| [Hunyuan3D-2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1) | Image-to-shape and textured mesh comparison, subject to licensing | Official figures are 10 GB for shape, 21 GB for texture and 29 GB combined. Its [community license](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/main/LICENSE) excludes the EU, UK and South Korea; do not trial it on this Italy-hosted worker without a separate applicable grant. |
| [Nerfstudio Splatfacto](https://docs.nerf.studio/nerfology/methods/splat.html) | Actual multiview site/object reconstruction rather than single-view completion | Uses photographs and camera/SfM information; documentation recommends COLMAP initialization and lists about 6 GB for default/12 GB for big. Capture quality and a scale anchor still determine evidence and units. |

These are researched candidates, not executed head-to-head benchmarks or quality
winners. Keep new dependencies and hardware trials isolated from the frozen Idol
environment.

### Would Fable 5.2 alone be better?

The [official Bedrock model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-fable-5-2.html)
documents image/text inputs and text output, not native image or 3D output.
Fable could help interpret OCR, normalize object descriptions, propose a
connectivity graph and produce procedural scene code. That is a useful semantic
front end, not evidence that it replaces masking, trained image-to-3D generation,
multiview reconstruction or a renderer. Code-generated geometry would remain
procedural interpretation, not recovered photographic appearance.

No authorized Fable inference endpoint was available in this work, so no Fable
trial was run and no measured superiority is claimed. The recommended comparison
is a language-model-assisted inventory/graph stage feeding the same validated
appearance backend, measured against the current reviewed inputs; it is not
replacing the reconstruction pipeline with a language model alone.

## Protected sequential workflow

The original T01-T03 subset of committed `cases/trials.json` is semantically
identical to immutable synthetic input manifest
[`6ebc4cc.../manifest.json`](https://raw.githubusercontent.com/ribumann/3d-scene-toolchain/6ebc4ccc49a0db48c9cfa6c3cbf038ae67db6dde/experiments/overnight-20261111/manifest.json)
(upstream byte SHA256 `793c0057baaae75363c663839bfda910e9c67f79b1b2c30de41ba5a9d8eb4cb2`).
The three PNGs decode to **1448 x 1086**, independently checked rather than assumed.
T01 targets one pump assembly; T02 targets one pump, tank and control cabinet;
T03 targets two separate pump assemblies. T03 has no reusable-asset assertion.

An authorized operator can dispatch the existing registered workflow:

```sh
gh workflow run gpu-batch.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain \
  -f smoke_mode=trials -f smoke_source=public-preview \
  -f 'pilot_cases=T01 T02 T03' -f trial_variants=both
```

For the first small run set `pilot_cases=T01`. `trial_variants` also accepts
`baseline` or `optimized`; redispatch resumes the selected matching checkpoints.
The trial route uses the committed photographic manifest, not the pilot source
selector or baseline Store. All selected variants run sequentially in the existing
single-GPU concurrency group, with a 360-minute bound. Existing
`SCENE_GPU_RUNNER`, the protected Actions `HF_TOKEN` secret and both prepared
interpreters/model caches are required. No operator token extraction or new
model/service provisioning is needed. The workflow stages only immutable same-repo
PNG URLs, checks SHA256, rejects redirects, caps each download at 12 MiB and checks
PNG decoding and a 20-million-pixel ceiling before atomic placement.

## Direct backend execution

Private trial execution and export are **Linux/POSIX-only**: both require real
`fcntl.flock` checkpoint locks on the prepared worker. Windows supports downloaded
package validation and static builds, not private inference/export. The Linux
test suite exercises locking and symlink protection; missing Windows flock or
symlink privileges are not grounds to weaken those checks.

Use the **current checkout**, the existing two prepared interpreters, and stage
approved generated PNGs at
`/home/scene/scene-private-data/approved-trials/{T01,T02,T03}.png`.
The manifest is strict schema version 1 (see `scripts/trial_contracts.py`):
only T01-T03, exact source filename/SHA, immutable raw repository URL, explicit
publication approval, prompt, expected inventory, optional reviewed normalized
boxes and optional relative instance placements. Generator provenance is exactly
`Copilot image_generation tool; underlying image model/version not exposed`.
No model/version is invented.

The source metadata `kind` is `generated-photographic-scene`.
`detector_phrases` and reviewed categories allow pump, motor, tank, control cabinet,
conveyor and industrial machine only. Boxes use normalized `[x,y,width,height]`.
Expected inventory is a declared target, not a reviewed accuracy score.
Reviewed objects have explicit IDs/identities and `reviewed=true`; repeated
authored placements require a `reusable_asset_id` and are not independent
reconstructions. Differing generated copies are never presumed identical.

Once an approved manifest/input is staged, run one or more selected variants:

```sh
cd "$GITHUB_WORKSPACE"
export PYTHONPATH="$GITHUB_WORKSPACE/services/pipeline"
# Supply HF_TOKEN via the existing protected job environment, never a file.
/home/scene/scene-worker-venv/bin/python - <<'PY'
import os
from scripts.package_pilots import APPROVED_PINS
os.environ.update(APPROVED_PINS)
os.environ.update(ATTN_BACKEND="sdpa", SCENE_IDOL_COMPILE="0")
from scripts.private_gpu_trials import main
import sys
sys.argv = ["private_gpu_trials", "run",
    "--data-dir", "/home/scene/scene-private-data",
    "--manifest", "/home/scene/scene-private-data/approved-trials/manifest.json",
    "--cases", "T01", "--variants", "baseline", "optimized"]
raise SystemExit(main())
PY
```

Only the selected variants execute, sequentially. Extraction runs in
`scene-vision-venv`; each Idol process runs in `scene-worker-venv`. Both variants
retain the frozen five model pins, SDK, 32,768 Gaussians / 50 steps / seed 42,
SDPA and compile-off settings. There is no higher-quality sweep, model change,
synthetic fallback or arbitrary object truncation.

## Optimization, resume and evidence

Outputs are isolated at `trials/{ID}/{variant}/`, with atomic `trial.json` and
`safe-status.json`. Matching extraction/crop hashes are revalidated on resume.
Manifest/source/settings changes explicitly reject reuse. Interruption preserves
readable checkpoints; a complete-but-uncheckpointed output can resume only after
actual generation/PLY validation. Individual failures remain visible and do not
become cached successes.

Both variants reject tiny/degenerate/unsegmented crops. Optimized duplicate
suppression additionally requires the **same reviewed identity**, box IoU at least
0.95 and source-coordinate alpha-mask IoU at least 0.98. Same category or a similar
appearance alone is insufficient. Every removed proposal records its canonical
ID/reason. No heuristic claims repeated generated copies are the same asset.

Successful actual outputs populate `trials/cache/{fingerprint}/`. The fingerprint
binds exact crop bytes, immutable models/SDK, Gaussian count, steps/seed,
attention/compile and crop policy. Only optimized variants read this shared cache;
baseline executes its own uncached comparison unless resuming its own checkpoint.
Cache hits revalidate generation provenance, PLY attributes/count and receipt
hashes; invalid entries fail explicitly instead of pretending success.
Exact reuse is reported as reuse, not another independent reconstruction.

Reports include expected/detected/usable counts, rejected reasons, individual
failure/timing records, wall time, cache hit/miss, resume and independent generation
counts, plus settings/source hashes. Counts are coverage observations, not accuracy
or fidelity scores. Timings are actual observations only; no unmeasured speedup
is promised. Layout, scale and depth remain inferred or explicitly authored
relative assumptions, not recovered metric truth.

### Idol appearance orientation

The pinned Idol SDK `8db700349a5570aac390e4780fa32e3eed6b587a`
[`Gaussian.save_ply`](https://github.com/speridlabs/idol-sdk/blob/8db700349a5570aac390e4780fa32e3eed6b587a/idol/gaussian.py)
exports its z-up object as `(x, -z, y)`, putting up along negative Y.
The workbench applies a proper 180-degree X rotation to appearances identified
by that model and SDK, before the semantic node rotation, to match the scene's
positive-Y-up convention. Bounds centering follows the same transform; Spark
rotates the Gaussian covariances with the object. This display correction applies
to both pilot and trial appearances without changing their PLY bytes, hashes,
model settings or checkpoints. Other splats, GLBs and procedural geometry retain
their existing orientation. It does not recover an object's real-site heading.

## Derived-only export and additive public build

Publication is a separate explicit opt-in, using the existing isolated CPU
publisher (`SCENE_PUBLISH_RUNNER`, distinct from the GPU runner/work directory):

```sh
gh workflow run gpu-batch.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain \
  -f smoke_mode=trial-package -f publish_trials=true
```

The CPU route has no model token or CUDA visibility. It locks each variant,
skips active checkpoints as `processing` with no scene, and revalidates stopped
extraction receipts, actual output hashes/provenance and 32,768-Gaussian PLYs.
No private root is uploaded. Only the dedicated new
`$RUNNER_TEMP/trial-publication-$GITHUB_RUN_ID/` directory becomes artifact
`trial-publication-<runID>`, retained seven days:

| Path | Content |
|---|---|
| `trials.json` | Exact T01-T03 baseline/optimized inventory, safe counts/status/timing and declared file hashes |
| `trial-manifest.json` | Exact approved generated-input provenance, prompts, target inventory, reviewed boxes and authored relative layout |
| `references/T0N.png` | Only the explicitly approved, hash-bound generated photographic PNGs |
| `scenes/T0N-<variant>.json` | Completed validated appearances only, with inferred/authored placement provenance |
| `assets/T0N/<variant>/<object>.ply` | Validated appearances with stripped header comments |

No crops/masks, raw logs, source-runtime paths or tokens are allowed. Failures are
safe error codes, never copied exception logs. A failed/interrupted/no-output
variant remains visible without substitute geometry. Read-only validation/build
is portable; private export requires Linux/POSIX flock.

After review, build additively with the **unchanged approved final pilot package
43079293375**, never an empty default baseline:

```sh
gh workflow run ci.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain \
  -f pilot_run_id=43079293375 -f trial_run_id=TRIAL_PACKAGE_RUN_ID -f deploy=false
```

Both runs must be completed trusted `gpu-batch.yml` runs on this branch;
workflow path/registered ID and exact artifact names are checked through REST.
All package files/hashes and committed source authorization are revalidated.
The trial CI path refuses a missing or different pilot run ID. The static builder
also rejects trials without a complete eight-source pilot package.

For approved packages already downloaded locally:

```sh
SCENE_PILOT_PUBLIC_PACKAGE=/path/to/approved-pilot-package \
SCENE_TRIAL_PUBLIC_PACKAGE=/path/to/approved-trial-package npm run build:demo
```

Only `apps/web/dist-demo/` is publishable. Trial PLYs/references use isolated
`/trial-assets/` and `/trial-references/` paths; the original eight views/files
remain intact. The compact Trials section exposes both methods, expected versus
actual counts, rejections/failures, timing, exact reuse/resume, pins and source
provenance. Direct links use `?case=T01-baseline` or `?case=T01-optimized`
(similarly T02/T03), including honest pending/processing states. Neither the
normal default build nor a source commit proves trial inference or deploys results.
Do not deploy the default reference-only build over the approved public baseline.
