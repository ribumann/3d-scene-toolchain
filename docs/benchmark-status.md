# Benchmark status

This records the development milestone, not full acceptance of the eleven-case
toolchain. All eight I01-I05/G01-G03 references are privately ingested on the
operator's host. Eight authorized public WebP previews are packaged separately;
verified model reconstruction remains pending.

## Original CPU batch (before private image intake)

The results below describe the earlier batch, when original image bytes were
missing. They are historical execution results, not current intake availability.

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

## Private original-image intake (2026-11-11)

The user supplied all eight image references. The coordinating operator verified their
exact checksums against the attached bytes and ingested them privately through
the existing FastAPI upload API, including originals, previews and metadata:

| Case | Original dimensions | Current intake status |
|---|---|---|
| I01 Mineral flowsheet | 557 x 550 | Validated and ingested privately |
| I02 Outdoor plant | 715 x 429 | Validated and ingested privately |
| I03 Vessel room | 2000 x 1333 | Validated and ingested privately |
| I04 Assembly diagram | 474 x 647 | Validated and ingested privately |
| I05 Japanese factory plan | 720 x 1263 | Validated and ingested privately |

G01 grocery, G02 semiconductor and G03 zoo AI-generated references were also
privately ingested; their original dimensions are not recorded in this report.
All eight full originals remain in the operator's private runtime, not this
cloud checkout or public build. The user explicitly authorized publication of
eight metadata-stripped WebP previews (~2.13 MiB total), committed separately at
`ed50316`. This intake/publication is not extraction, reconstruction or actual
Idol inference. No derived output publication is implied.

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
  mocks. The subsequent authenticated infrastructure check below is separate
  from those tests and from actual inference.
- GitHub CPU CI also passed both the web job and the Python/Blender job:
  https://github.com/ribumann/3d-scene-toolchain/actions/runs/42899375347
  This includes the three procedural cases on a hosted CPU runner, not GPU work.

## Verified GPU infrastructure (2026-11-11)

The coordinating operator reported a running `Standard_NC4as_T4_v3` Spot VM in
Italy North, in the dedicated `scene-twin-poc-1111` group. Real `nvidia-smi`
reported Tesla T4, 16,384 MiB and driver `615.71.10` after package installation
completed. The user explicitly approved no auto-shutdown. Spot eviction remains
possible despite activity; the operator must checkpoint work and manage cleanup.

The operator prepared separate Python 3.12 vision/Idol environments and verified
their imports and CUDA availability. CPU readiness
[43004864760](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43004864760)
actually downloaded the required gated configs and resolved five immutable model
pins; no HF token failure was observed. Actual CUDA kernels/model reconstruction
and Idol inference remain unverified. The source deployment defaults were not
changed; this worker used an operator-only Spot/no-shutdown variant after policy
and schedule-region blockers. See the [GPU operator guide](../infra/azure/README.md).

## Remaining acceptance work

### Read-only static viewer preparation

A separate `npm run build:demo` artifact packages public deterministic templates
for P01-P03, with 28, 28 and 49 semantic objects respectively, plus exactly eight
authorized WebP previews. Image cases display original-vs-AI-generated
provenance and explicitly state that no reconstructed 3D scene is published.
No runtime store, full original image, Blender export or Gaussian inference
result is included.

Local Chromium/WebGL2 checks loaded and rendered all three JSON scenes and
exercised object selection/isolation, camera controls, labels, route pause/play
and JSON export. The earlier build checked eight missing-input states; the
reference-preview update separately decoded all eight actual WebPs, checked
provenance/no-scene labels and error/reload behavior on desktop and at 390 pixels.
No `/api` requests
or mutation controls were present. The 390-pixel layout had no horizontal
document overflow; the browser pass also corrected canvas sizing within the
mobile viewport. Python snapshot tests, frontend tests and both local/demo
production builds passed. These checks do not certify fidelity or frame rate.

Enforced Storage network policy blocked the original publication target. A
dedicated Free Azure Static Web App was created instead; CPU workflow
[43000921576](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43000921576)
successfully uploaded only the read-only build, with no API/Functions.
The coordinating operator subsequently verified the actual public origin at
https://red-wave-0c7bb6c0f.4.azurestaticapps.net/: secure HTTPS 200, catalog and
P01-P03 JSON 200 with `application/json`, and all three visibly rendered WebGL2
scenes (28/28/49 objects) with no lost context. Labels toggled; switching cases
made no `/api` requests, and an explicit `/api/cases` probe returned 404.
The public browser panel was 173 pixels wide; local 390-pixel layout checks
remain separate evidence, not a public performance or device certification.
The original Storage account remains provisioned but network-disabled and
unused; it is not the viewer host. That initial public-origin verification
predates the reference-preview UI; each new deployment needs a separate check.
The eight-reference update subsequently passed CPU/Blender and web/deployment in
[43006759156](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43006759156),
source `c7b4507acc2f340634daba29289f3389231433b6`. Although this cloud workspace
was blocked by DNS/client policy, the coordinating operator subsequently verified
the updated public origin in Browser on 2026-11-11. All eight preview URLs
returned HTTP 200 `image/webp` and decoded at expected dimensions; `/api/cases`
returned 404. Selected G03 showed AI-generated provenance, original-kept-private
copy, no reconstructed scene and zero objects. P01 still visibly rendered
28 objects before switching. This verifies reference publication and the
existing procedural viewer, not image reconstruction or Idol inference.
See [`infra/azure/static-demo.md`](../infra/azure/static-demo.md) for the artifact
boundary, exact target and opt-in deployment controls.

### Full pipeline

Use the privately ingested eight originals on the authorized operator host;
no additional image generation is needed. Confirm per-worker
private input access and use the readiness job's immutable model revisions. Run
one actual Idol object first, then all eleven full pipeline cases. Review masks,
labels, graph directions/loops, footprint layout and source-linked uncertainty.

Directional diagram topology, translations and precise photo depth are currently
manual correction work rather than solved automatic extraction. Raw versus
corrected scores require a frozen reviewed annotation baseline that does not yet
exist. Human review, geometric fidelity, load/download budgets and the proposed
30 FPS/p95 frame-time target are not certified by unit tests or synthetic rendering
fixtures. Keep them pending instead of treating a completed UI as full success.
