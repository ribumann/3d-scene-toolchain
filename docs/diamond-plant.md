# D01: three-line diamond recovery plant

**Current result:** [open the photo-derived twin](https://red-wave-0c7bb6c0f.4.azurestaticapps.net/?case=D01).
Twelve components were reconstructed from the original generated photograph;
ten concepts across twenty placements pass rendered review. Clean module and
whole-plant GLBs remain available for the same 24-module, 50-stream, 56-tag twin.
Sizing and connectivity are authored, not measured from the photograph.

Use the [two-mode app integration contract](digital-twin-integration.md#d01-two-visual-modes-one-twin)
to offer Clean / Reconstructed in the consuming app. Jump to
[actual reconstruction results](#component-gaussian-reconstruction) for the
approved publication and quality limitations. The initial mesh deployment record
below is retained as reference, not the latest appearance result.

D01 is a synthetic 1536 by 1024 photographic reference and a manually
image-guided, module-level digital twin for a future telemetry / Fabric RTI demo.
It is **not a real plant, a surveyed layout, an engineering design or a
photogrammetric reconstruction**.

The first publication used authored parametric mesh geometry after Azure
returned `SkuNotAvailable` for the retained Italy North Spot T4. The worker has
since completed a separate, supervised SAM2/Idol reconstruction run.
An independently validated Gaussian package overlays component appearances without
replacing the authored layout or relabeling incumbent reconstructions. The
portable GLB remains the authored mesh model, not an export of the splats.

## What is provided

- Original synthetic PNG with exact generation prompt and SHA-256 provenance.
- 24 visible process modules: six modules on each of lines A/B/C, plus six shared
  modules. Logical equipment children have IDs, not independent geometry.
- A portable whole-plant GLB with conveyor/pipe representations, and twelve
  reusable module GLBs. Module bounds match their authored dimensions.
- A scaled SVG site layout and JSON metadata with 64 logical equipment children,
  50 directed material/utility streams, connection ports and explicit route
  points, and 56 numeric telemetry tags.
- A strict event JSON Schema embedded in the metadata. Simulation envelopes are
  fictional demo values, not operating limits or safety thresholds.
- A separate reviewed-crop manifest ready for the existing SAM2/Idol runner.

The plant group collapses independently in the workbench. Line A/B/C, shared
services and utility routes have viewport-only visibility controls. All downloads
keep the complete plant; hiding a line does not delete assets or change metadata.

## Coordinates and geometry

The site envelope is 100 m east-west by 75 m north-south, with a 16 m vertical
envelope. Coordinates are right-handed, Y-up, in metres: X east, Z south, origin
at the site centre at ground level. Module positions are bounding-box centres;
Y equals half the authored height, so bases sit at ground level.
Sizes are X/Y/Z dimensions; rotations are radians. The SVG is a north-up X/Z
projection with a 10 m scale bar.

Line A/B/C centres are Z = -16 / 0 / +16 m. A line contains feed preparation /
crushing, drum scrubbing, wet sizing, DMS, drain/rinse/medium recovery and enclosed
X-ray sorting. Shared modules are a raw-feed hopper, thickener, process-water
tank, secure recovery lab, control hut and tailings zone. Modules intentionally
abstract away small pipes, pumps and hidden internals.

Example stable ID: `D01.A.crusher`. Its logical bearing is
`D01.A.crusher.bearing`; its bearing-temperature tag is
`D01.A.crusher.bearing_temperature`.

`metadata.json` module dimensions, GLB bounds and scene-node dimensions use the
same authored model. The site has non-overlapping module footprints. This is a
spatial consistency check, **not** a service-clearance or engineering acceptance.
The photo is oblique and uncalibrated; its perspective cannot establish metre
scale, exact dimensions, identical equipment or hidden routing.

## Process and telemetry semantics

Each line routes ore through crushing, scrubbing, wet sizing, DMS and medium
recovery to sorting and the secure lab. Both sinks and floats pass through
drain/rinse before concentrate or tailings; medium recycles to DMS. Fines and
wash effluent go to the thickener, with recovered water returned to the water
tank. Utility connections are initially hidden to keep the visual abstraction
readable. Grizzly/oversize handling is contained in feed preparation; oversize
is not presumed barren waste.

The image cannot identify the X-ray sensor principle. D01 assumes enclosed XRT,
not XRF elemental analysis. Process context:
[SGS Bateman modular diamond recovery plants](https://www.sgs.com/-/media/sgscorp/documents/corporate/brochures/sgs-nr-diamond-recovery-en.cdn.en-MU.pdf)
and [TOMRA diamond flowsheets / XRT](https://www.tomra.com/en-gb/mining/media-center/news/2021/tomra-new-diamond-microsite).
No equipment throughput, recovery percentage, plant mass/water balance,
control logic, cleaning chemistry or safety system is certified.

A future simulator can emit events such as:

```json
{
  "timestamp": "2026-11-11T12:00:00Z",
  "plant_id": "D01",
  "module_id": "D01.A.crusher",
  "equipment_id": "D01.A.crusher.bearing",
  "tag_id": "D01.A.crusher.bearing_temperature",
  "value": 54.2,
  "unit": "Cel",
  "quality": "good"
}
```

This is an illustrative event, not real telemetry. Join `tag_id` to
`telemetry_tags`, then enforce its module, equipment, unit and numeric value
contract. JSON Schema enum membership alone cannot enforce those cross-field
joins. Fabric resources, ingestion, a simulator and dashboards are **not**
provisioned by this change.

The [telemetry and Fabric demo specification](diamond-plant-demo.md) defines
every tag's meaning, normal range, low-volume 30/60-second cadence and generation
behavior, plus a focused set of Fabric calculations, alerts and app views.
It is a proposal for the next implementation, not a claim that live sensor data
or a Fabric connection has been added to this viewer.

## Provenance and reproducible publication

`cases/diamond-plant-source.json` records the original prompt, factual generator
description and image hash. The immutable source commit is
`25070e70285e9228ab4453dbd0cf70a844a11922`.
`scripts/diamond_plant.py` authors the layout and exports;
`scripts/plant_geometry.py` writes deterministic glTF 2.0 geometry without adding
dependencies. `plant/files.json` hashes every plant deliverable except itself.
`metadata.scene_sha256` hashes the exact UTF-8 scene JSON bytes including final LF.
Module assets in the static viewer must match the plant file receipts.

The static build is opt-in with `SCENE_INCLUDE_DIAMOND_PLANT=1`. All three
retained packages are required. The CI dispatch uses `include_plant=true` with
`pilot_run_id=43079293375`, `trial_run_id=43185525449`,
`illustration_run_id=43237905142`; the default build remains unchanged.

## Verified live delivery

[Open D01 in the workbench](https://red-wave-0c7bb6c0f.4.azurestaticapps.net/?case=D01).
Downloads: [original PNG](https://red-wave-0c7bb6c0f.4.azurestaticapps.net/plant/D01.png),
[scaled layout SVG](https://red-wave-0c7bb6c0f.4.azurestaticapps.net/plant/layout.svg),
[metadata JSON](https://red-wave-0c7bb6c0f.4.azurestaticapps.net/plant/metadata.json)
and [whole-plant GLB](https://red-wave-0c7bb6c0f.4.azurestaticapps.net/plant/plant.glb).

Deployment
[43257118267](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43257118267)
succeeded at source `fbde9b0b02628b3d9de076c5bffde567e629b632`.
The Python/Blender and web jobs both passed, including full tests, a real Blender
import and the opt-in static build. The frozen pilot, photographic-trial and
illustration publications above were retained.

Live verification matched 139 public-file hashes to the approved candidate,
including four application files and the plant receipts. The 30 catalog entries
include three explicitly not-run photographic baselines, not 30 successful
reconstructions. Desktop (1600 px) and mobile (390 px) browser checks loaded all
24 authored module models, decoded the original 1536 by 1024 image and verified
all 16 plant deliverable hashes. Seven collapsible groups, line/shared/utility
visibility, view controls and downloads worked without page errors or horizontal
overflow. Hiding Line A reduced visible labels from 24 to 18; restoring it
returned 24.

These checks describe the initial mesh publication, not photographic
reconstruction accuracy. No Fabric infrastructure or telemetry simulator is
deployed by this repository's viewer publication.

## Component Gaussian reconstruction

The real reconstruction run
[43294502236](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43294502236)
completed all twelve canonical crops using 32,768 Gaussians each, 50 steps and
seed 42. Sequential extraction/inference took 2,889 seconds, with a sampled peak
GPU memory of 9,295 MiB. These were twelve independent generations, not cache
hits; their appearances are reused across 24 authored module placements.
The retained GPU was deallocated after the artifact was published.

An actual rendered review retained ten concepts across twenty placements.
The DMS tower and raw-feed hopper lost their defining vertical volume and are
hidden by exact-hash entries in `cases/appearance-reviews.json`. They remain
available through **Show screened-out objects** without changing acceptance.
The other components retain photographic surface detail, but some include
small surrounding pads/conveyors and have approximate depth. This is a
component-assembled single-image reconstruction, not whole-scene photogrammetry.
All 24 semantic module IDs, 50 streams and 56 telemetry tags remain intact,
including hidden appearances; the portable authored GLB remains available.

Twin consumers must join each appearance SHA-256 to `/demo/quality.json` and
hide excluded assets by default, then apply the documented grounded,
aspect-preserving fit rather than stretching each axis to the module envelope.
An excluded splat is not silently replaced by a geometric proxy.

The Gaussian publication is live via deployment
[43381383927](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43381383927)
at source `891d4f3d877d1d8acc7097c017b4e865b73ec8e2`.
Live checks matched 152 public-file hashes, including all 29 plant deliverables
and four application files, while retaining the original 30-entry catalog.
Desktop and mobile checks loaded ten accepted appearances, loaded all twelve
when the review flag was enabled, and restored screening when disabled.
Layer controls, downloads and source-image decoding passed without browser
errors or horizontal overflow. The complete raw generation evidence is
available in `/plant/reconstruction.json`; these checks establish publication
integrity and usable rendering, not reconstructed engineering accuracy.

`cases/diamond-plant-trial.json` isolates D01 from the six frozen photographic
trials. Twelve manually reviewed canonical crops, including the foreground
line's six modules, drive supervised SAM2 extraction. Three explicit placements
reuse each line-module concept; these are authored instances, not three
independently recovered appearances. A reviewed box is not a segmentation or
accuracy ground-truth label.

With the existing protected token and frozen model/SDK pins supplied by the
normal job, the runner accepts this separate manifest:

```sh
python -m scripts.private_gpu_trials stage \
  --data-dir /home/scene/scene-private-data \
  --manifest cases/diamond-plant-trial.json --cases D01
python -m scripts.private_gpu_trials run \
  --data-dir /home/scene/scene-private-data \
  --manifest cases/diamond-plant-trial.json \
  --cases D01 --variants optimized
python -m scripts.package_trials \
  --data-dir /home/scene/scene-private-data \
  --manifest cases/diamond-plant-trial.json \
  --out /home/scene/plant-publication \
  --approve-generated-trial-publication
```

Use the existing pinned runtime (32,768 Gaussians, 50 steps, seed 42); do not
silently resolve new models, overwrite baseline checkpoints or publish unfinished
outputs. This prepares a separate validated package, **not** a deployed Gaussian
plant. Actual extraction outcomes, failed crops, quality screening and appearance
fidelity must be reviewed before any subsequent additive publication.

The registered workflow accepts `smoke_mode=trials`, `pilot_cases=D01`,
`trial_variants=optimized`, and `publish_trials=true`. D01 must run alone and
uses `cases/diamond-plant-trial.json`, not the frozen photographic-trial
manifest. Its public artifact is `plant-splats-<runID>`. Cache validation and
resume settings are identical to the existing trial pipeline.

For static publication, set `SCENE_PLANT_SPLAT_PACKAGE` to that validated
package alongside the three retained packages and
`SCENE_INCLUDE_DIAMOND_PLANT=1`. CI exposes the equivalent
`plant_splat_run_id` input. Each successful canonical crop is loaded once and
shared across its explicit module placements. Stable module IDs, positions,
sizes, connection routes and all telemetry attachments remain unchanged.
Unreconstructed modules retain explicitly authored GLBs; screened-out
reconstructed appearances are hidden rather than silently replaced by boxes.
The existing review-only visibility flag can show excluded splats.

`plant/reconstruction.json` records actual inference counts, failures, settings
and source hash; `plant/files.json` binds all published PLY bytes. The browser
also requires matching hash-bound Gaussian quality assessments and the
original source hash. Numerical validity and conservative extent screening do
not certify photographic fidelity, hidden geometry or recovered dimensions.
Metadata also joins each module's `appearance_asset_id` to `appearance_assets`,
including file hashes and model provenance. A consuming twin can translate
`/api/assets/plant/` to the static `/plant/` prefix. Apply the documented pinned
Idol SDK half-turn around X, then uniform aspect-fit and ground each splat
inside its authored module envelope; do not stretch it independently by axis.
