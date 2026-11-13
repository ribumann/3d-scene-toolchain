# Digital-twin integration: one contract, two appearances

This package supplies geometry, source-derived appearances and semantic
attachment points. The consuming app supplies live data, Fabric queries and
alerts. Switching appearance must not switch the plant, its telemetry or its
operational state.

## D01: two visual modes, one twin

Offer **Clean model** and **Reconstructed model** in the existing mining view.
Use Clean model as the default operational view; keep the selected mode as a
view preference. Both use the same 24 modules, 64 equipment children, 50 streams,
56 tags, authored metre layout and source catalog.

| Mode | What to render | What it means |
|---|---|---|
| Clean model | Authored module GLBs or the whole-plant GLB | Clean, readable, Blender-compatible geometry; dimensions and process topology are demo assumptions. |
| Reconstructed model | Photo-derived component PLYs, shared across module placements | Appearance reconstructed from the original synthetic photograph; unobserved surfaces and depth are approximate. |

The phrase "Blender clean version" refers to the clean asset set, not another
plant or simulator. D01 GLBs are written by the deterministic Python exporter
and can be opened in Blender. Existing procedural scenarios also have actual
Blender exports. Do not label the D01 meshes as photographically recovered.

### Published assets and bindings

The current public base is
`https://red-wave-0c7bb6c0f.4.azurestaticapps.net`.
Paths below are relative to that base. Asset loading does not use a public
`/api` backend.

| Path | Use |
|---|---|
| `/plant/metadata.json` | Canonical modules, equipment, tags, dimensions, ports, routes and appearance mappings |
| `/plant/files.json` | SHA-256 receipts for plant files; pin this manifest/revision in the consuming app |
| `/plant/modules/<kind>.glb` | Twelve reusable clean concepts; use each module's `kind` |
| `/plant/plant.glb` | Complete clean plant in its authored world layout, including simplified physical connections |
| `/demo/D01.json` | Reconstructed scene nodes/assets and stable directed edges |
| `/plant/splats/<parent>.ply` | Twelve independent photo-derived component assets |
| `/demo/quality.json` | Exact-hash Gaussian acceptance/exclusion and visible render bounds |
| `/plant/reconstruction.json` | Generation counts, settings, source hash and fitting notes |
| `/plant/layout.svg`, `/plant/D01.png` | Clean top-plan and original synthetic photographic reference |

Do not construct PLY filenames from equipment categories. Resolve
`module.appearance_asset_id` through `metadata.appearance_assets` (or the scene
asset list), and translate only the validated `/api/assets/plant/` URI prefix
to `/plant/`. Reject traversal, unexpected external destinations, missing
receipts and mismatched hashes. Pin the approved publication and vendor/cache
its bounded assets through the existing app build/storage rather than depending
on a mutable demo URL forever. This needs no new storage account or GPU service.

The verified Gaussian deployment is run `43381383927`, application source
`891d4f3d877d1d8acc7097c017b4e865b73ec8e2`; generation run is `43294502236`.
Implementation and updated documentation are in
[PR #3](https://github.com/ribumann/3d-scene-toolchain/pull/3), not yet merged at
this writing. Inspect current merge status instead of assuming main contains
the Gaussian integration.

### Placement, rendering and quality

**Clean:** for reusable module GLBs, normalize local geometry bounds and apply
the module's `position`, `rotation` and `size`, following
[`fitModelToNode`](../apps/web/src/assets.ts). Reuse loaded source geometry across
placements. The whole-plant GLB already carries world transforms and has top-level
module names such as `D01.A.crusher`; map child selections to that module name.
Do not apply module transforms again to the whole-plant asset or render its
connections twice.

**Reconstructed:** use Spark or an equivalent Gaussian renderer, with one loaded
source per appearance and distinct transforms/interaction targets for each
module. Reuse the existing
[`fitSplatToNode`](../apps/web/src/assets.ts) and
[`splatFit`/`splatIssue`](../apps/web/src/model.ts) behavior, not a bounding-box
approximation:

- Join `asset.sha256` to the version-1 quality report and use its `render_bounds`.
  Reject missing/invalid quality, dimensions or bounds.
- Apply the X-axis half-turn only for the documented Idol model/SDK pin.
  The helper combines orientation, bounds-centering and grounded fit correctly;
  do not add a generic second axis flip.
- Fit uniformly inside the authored module envelope, preserving aspect ratio
  and grounding at its base. Do not stretch X/Y/Z independently.
- Honor exact-hash exclusions and the existing over-8x aspect screen. A separate,
  off-by-default **Show screened-out objects** flag may permit review but never
  marks those assets accepted or bypasses invalid bounds/load errors.

Twelve concepts generated successfully, but **ten concepts / twenty placements**
are accepted for default rendering. The flattened DMS tower (three placements)
and raw-feed hopper (one) are hidden. All 24 semantic modules remain selectable
in the equipment list, with live data and an explicit appearance-unavailable or
screened-out explanation. Selecting a hidden module can show a labeled
selection envelope; never imply that envelope is reconstructed appearance.

Unreconstructed modules may use explicitly labeled authored mesh fallbacks when
the publication contains them; currently D01 has outputs for all twelve concepts.
Do not silently insert clean meshes for screened-out splats. If a hybrid
fallback is later offered, label it as a separate, deliberate display policy.

### Keep operational behavior identical

One module-ID-keyed state store drives selection, incident focus, equipment
drawers, timestamps, quality/staleness and query filters in both modes. Switching
modes retains the selected module, camera target, line/utility filters, run and
time window. It must not restart a simulator, refetch a new plant catalog or
change Fabric subscriptions/refresh cadence.

Use shared labels, status badges and selection outlines over either renderer.
Preserve photo colors; do not rely on tinting splats to encode alarm severity.
Keep the equipment list and top-plan usable if WebGL/Gaussian loading fails.
Report the error and allow explicit switching to Clean model, not a
success-shaped automatic substitution. Dispose inactive renderer resources;
mode toggling must not accumulate GPU buffers or duplicate interactions.

### Copyable assignment for the twin-app agent

> Extend the existing mining twin view in ribumann/fabrictritwin with a
> **Visual model: Clean / Reconstructed** selector, defaulting to Clean.
> Read docs/digital-twin-integration.md and docs/mining-twin-agent-dod.md in
> ribumann/3d-scene-toolchain PR #3 (or its merged revision). Consume the
> approved D01 GLB and Gaussian assets; do not rerun reconstruction.
> Keep one catalog, simulator, telemetry/query state and stable module IDs.
> Preserve selection, incident focus, camera target and filters across modes.
> Render clean module GLBs using the authored layout; render reconstructed PLYs
> using shared sources, pinned orientation correction, uniform grounded fit and
> exact-hash quality screening. Ten concepts / twenty placements are accepted;
> DMS and hopper remain hidden unless review-only visibility is enabled, while
> their semantic modules and data remain available. Show explicit load/screening
> status, not silent proxy/fallback geometry. Reuse current hosting, storage,
> Fabric capacity, identity and deployment automation. Prove both modes on the
> hosted app, including the same alert-to-module selection and Fabric data,
> mode-toggle cleanup, desktop/mobile access, and no additional telemetry load.

Acceptance is defined in G2/G6 of the
[mining twin Definition of Done](mining-twin-agent-dod.md). This is an assignment
for the consuming project, not a claim its two-mode UI has already been built.

## Stable integration boundary

`Scene.id`, `Scene.case_id` and `Node.id` identify the scene and semantic assets.
IDs survive browser/Blender transform edits and GLB export. A device connector
should map external equipment identifiers to these IDs, not to screen labels or
mesh array positions. Keep telemetry outside the geometry revision:

```json
{
  "scene_id": "P02",
  "node_id": "station-5",
  "external_asset_id": "line-A/tester-01",
  "observed_at": "2026-11-10T20:00:00Z",
  "measurements": {
    "temperature": {"value": 38.2, "unit": "degC", "quality": "good"},
    "state": {"value": "idle", "quality": "good"}
  }
}
```

This is a **proposed future envelope**, not an implemented ingestion endpoint.
A future adapter can consume OPC UA, MQTT, REST or event streams, retain original
units/timestamps/quality, and update a separate view-model keyed by `node_id`.
Do not silently turn absent/stale values into zero or a healthy state.

Suitable first overlays: equipment status, quality, maintenance notices, work
orders and sensor values. Distinguish stale/offline/unknown; combine color with
text and symbols. Use the existing accessible object list and evidence panel
as non-canvas alternatives. Keep alarms deterministic and auditable rather than
delegating safety decisions to generated geometry.

## Useful adjacent packages

| Use case | Reuses | Additional requirement |
|---|---|---|
| Factory layout and maintenance planning | Stable nodes, Blender authoring, saved positions, isolation | Measured dimensions, clearances and verified equipment inventory |
| Warehouse/retail space exploration | Repeated assets, departments, navigation routes | Shelf/product catalog and operational data binding |
| Operator training | Labeled equipment, selection, illustrative process paths | Reviewed procedures and scenario state machine; not a safety certification |
| Campus, zoo or museum guide | Site footprints, visitor paths and selectable zones | Accessible wayfinding and accurate visitor constraints |
| Industrial process explanation | Diagram nodes and explicit directed routes | Human-reviewed topology and terminology |
| Asset-inventory inspection | Source-linked objects, provenance and revisions | Asset-register connector and identity reconciliation |

These are extension opportunities, not features claimed complete by the PoC.

## Quality boundary

Single-image Idol assets hallucinate unseen surfaces. Photo layouts have
uncalibrated depth. Schematic topology does not specify physical placement.
Unknown dimensions are assumptions and cannot establish collision clearance or
engineering fit. Gaussian appearance assets use mesh interaction proxies; an
accurate-looking splat is not a metrology mesh.
