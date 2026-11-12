# D01: three-line diamond recovery plant

D01 is a synthetic 1536 by 1024 photographic reference and a manually
image-guided, module-level digital twin for a future telemetry / Fabric RTI demo.
It is **not a real plant, a surveyed layout, an engineering design or a
photogrammetric reconstruction**.

The existing Italy North Spot T4 could not restart: Azure returned
`SkuNotAvailable`. No D01 SAM2/Idol inference has run and no Gaussian result is
published. The downloadable geometry is deliberately labeled authored
parametric mesh geometry. This does not replace or relabel the incumbent
Gaussian reconstructions.

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

These checks establish publication and authored-layout consistency, not
photographic reconstruction accuracy. Actual D01 SAM2/Idol inference is still
blocked by unavailable retained-worker GPU capacity. No Fabric infrastructure or
telemetry simulator has been deployed.

## Pending Gaussian reconstruction

`cases/diamond-plant-trial.json` isolates D01 from the six frozen photographic
trials. Twelve manually reviewed canonical crops, including the foreground
line's six modules, drive supervised SAM2 extraction. Three explicit placements
reuse each line-module concept; these are authored instances, not three
independently recovered appearances. A reviewed box is not a segmentation or
accuracy ground-truth label.

Once the retained, approved GPU environment is available, with the existing
protected token and frozen model/SDK pins supplied by the normal job, the
runner accepts this separate manifest:

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
