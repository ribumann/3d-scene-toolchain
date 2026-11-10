# Benchmark status

This records the development milestone, not full acceptance of the eleven-case
toolchain. Original image bytes and GPU/model access remain external prerequisites.

## Executed case batch

Command:

```sh
scene-toolchain --data-dir /tmp/scene-full-evaluation run \
  --cases P01 P02 P03 I01 I02 I03 I04 I05 G01 G02 G03 \
  --stages extract blender --report eleven-case-report.json
```

Environment: Linux x86_64, two logical CPUs, about 7.5 GiB RAM, Blender 4.0.2.
No CUDA device was exposed.

| Case | Procedural/extraction result | Blender export | Actual Idol |
|---|---|---|---|
| P01 Grocery | Deterministic illustrative layout | Passed, including reference PNG | Not run: GPU/model access unavailable |
| P02 Semiconductor packaging | Deterministic illustrative layout | Passed, including reference PNG | Not run: GPU/model access unavailable |
| P03 Zoo | Deterministic illustrative layout | Passed, including reference PNG | Not run: GPU/model access unavailable |
| I01 Mineral flowsheet | Blocked: original file missing | Not run | Not run |
| I02 Outdoor plant | Blocked: original file missing | Not run | Not run |
| I03 Vessel room | Blocked: original file missing | Not run | Not run |
| I04 Assembly diagram | Blocked: original file missing | Not run | Not run |
| I05 Japanese plan | Blocked: original file missing | Not run | Not run |
| G01 Generated grocery | Blocked: generated image missing | Not run | Not run |
| G02 Generated semiconductor | Blocked: generated image missing | Not run | Not run |
| G03 Generated zoo | Blocked: generated image missing | Not run | Not run |

The CLI records missing-input attempts as explicit failed jobs with prerequisite
messages, not successful empty scenes. This batch correctly exited nonzero.
The successful rows cover **CPU stages only**.

Measured extraction/template + Blender stage seconds in one run:

| Case | Template | Blender | Separate GLB size from an earlier verification run |
|---|---:|---:|---:|
| P01 | 0.02 | 3.54 | 73,312 bytes |
| P02 | 0.01 | 3.09 | 80,396 bytes |
| P03 | 0.01 | 3.05 | 438,476 bytes |

These are local observations, not latency guarantees. Blender output includes
primitive geometry; no resemblance or physical accuracy score is implied.

## Additional checks

- Python tests exercise scene validation, API/source handling, persistence,
  optimistic revisions, job conflict/cancellation/restart behavior, explicit
  missing prerequisites and Gaussian-format validation.
- Real Blender tests exercise `.blend`/GLB export, isolated reference renders,
  semantic IDs and position/rotation round-trips with mixed Euler angles.
- OCR runs on a clearly synthetic diagram fixture and reports unreviewed region
  proposals with **no invented process edges**. It does not validate the supplied
  mineral flowsheet or Japanese plan.
- Frontend tests/build cover model operations, API errors, JSON interchange and
  revision saves. A browser pass found and corrected a label-root lifecycle issue.
- A labeled synthetic 2,048-Gaussian fixture initialized in Spark alongside
  geometry, with no reported alerts/console errors after the lifecycle fixes.
  This verifies the renderer path, not generated-object quality or Idol inference.
  A browser label edit persisted as the next revision with the original node ID.
  At a 390-pixel viewport, the page had no horizontal document overflow.
- Azure tests cover identity, resource-group, quota, SSH and duration guards using
  mocks. There has been no authenticated Azure deployment or cost allocation.
- GitHub CPU CI also passed both the web job and the Python/Blender job:
  https://github.com/ribumann/3d-scene-toolchain/actions/runs/42899375347
  This includes the three procedural cases on a hosted CPU runner, not GPU work.

## Remaining acceptance work

Obtain the original five files and the three generated references. Confirm the
intended GPU backend, gated encoder access and immutable model revisions. Run
one actual Idol object first, then all eleven full pipeline cases. Review masks,
labels, graph directions/loops, footprint layout and source-linked uncertainty.

Directional diagram topology, translations and precise photo depth are currently
manual correction work rather than solved automatic extraction. Raw versus
corrected scores require a frozen reviewed annotation baseline that does not yet
exist. Human review, geometric fidelity, load/download budgets and the proposed
30 FPS/p95 frame-time target are not certified by unit tests or synthetic rendering
fixtures. Keep them pending instead of treating a completed UI as full success.
