# Digital-twin integration

The initial package prepares **renderable, editable scenes**. It is not yet a
live digital-twin runtime, calibrated engineering model, OPC UA connector or
production simulation.

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
