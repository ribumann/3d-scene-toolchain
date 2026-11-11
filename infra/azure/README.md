# Italy North GPU worker

This is an **operator-run deployment path**. The source template retains its
original bounded, scheduled-shutdown defaults; the explicitly approved running
PoC below used an operator-only Spot/no-shutdown template variant.
Existing `llmserving` credentials/resources are not copied or modified.

## Verified PoC infrastructure (2026-11-11)

The authenticated coordinating operator confirmed ARM deployment success,
running power state and actual `nvidia-smi` output:

| Setting | Observed value |
|---|---|
| VM / dedicated resource group | `scene-twin-poc-1111` / `scene-twin-poc-1111` |
| Subscription | `86677b6e-28fc-48e4-8988-5ab9e568eece` |
| Location / size | `italynorth` / `Standard_NC4as_T4_v3` |
| Priority / eviction policy | Spot / Deallocate |
| Maximum price | `-1` (Azure's on-demand price ceiling, not free compute) |
| GPU / memory | Tesla T4 / 16,384 MiB |
| NVIDIA driver | `615.71.10` |
| Auto-shutdown | None, explicitly approved by the user |

That infrastructure snapshot alone does not prove model execution; the separate
successful private one-object smoke is recorded below. The extension initially
left an active/partial
package installation; standard apt lock waiting and dependency repair completed
it without killing package processes or bypassing locks.

The operator-only variant was necessary because the subscription's MCAPS policy
rejected on-demand allocation and `Microsoft.DevTestLab/schedules` was unavailable
in Italy North. The source helper/template have not been changed to reproduce
that exception: they still request the original scheduled, non-Spot deployment,
and the helper conservatively rejects even Zone-only SKU restrictions. Do not
run the unchanged create command against this policy as though it were the
verified Spot path, or reuse the already-created group.

Spot capacity can be evicted at any time; keepalive activity cannot prevent it.
Checkpoint work and retain results outside the VM. With no shutdown schedule,
the operator must monitor runtime and explicitly deallocate/delete approved
resources when finished. Deallocation stops compute billing but leaves
chargeable disks and public IPs. The expiry tag is not an enforced deadline.

## Authenticate and inspect

Use the intended external tenant, not an arbitrary current account. UUIDs below
are placeholders; keep real identity configuration out of the public repository.

```sh
az login --tenant <approved-tenant-id>
python scripts/azure_gpu.py preflight \
  --subscription <approved-subscription-id> --tenant <approved-tenant-id>
```

The script checks exact identity, enabled subscription, Italy North SKU
restrictions, T4 family and regional vCPU headroom. It cannot guarantee live
allocation capacity. Inspect current Azure pricing and the billed disk/IP
resources before creating the worker.

Alternatively configure `scene-azure` as a protected GitHub environment with
`AZURE_CLIENT_ID`, `AZURE_TENANT_ID` and `AZURE_SUBSCRIPTION_ID` secrets, and a
federated credential for that exact repository/environment. The manual
**Azure Italy North read-only preflight** workflow authenticates with OIDC.
It does not deploy anything. Neither environment names nor secrets automatically
carry across from another repository.

## Provision a dedicated worker

The create command requires a new `scene-twin-*` resource group, an SSH **public**
key, a single approved public operator IP, and an explicit paid-operation flag:

```sh
python scripts/azure_gpu.py create \
  --subscription <approved-subscription-id> --tenant <approved-tenant-id> \
  --group scene-twin-example \
  --ssh-public-key ~/.ssh/scene.pub --ssh-source-cidr <operator-public-ip>/32 \
  --hours 2 --confirm-paid-create
```

The Bicep template deploys one `Standard_NC4as_T4_v3` worker in Italy North, a
restricted SSH rule, an NVIDIA driver extension, and Azure auto-shutdown near the
requested deadline. There are no browser/API inbound rules and no model tokens
in VM custom-data, deployment outputs or templates.

**Auto-shutdown deallocates compute; it does not delete disks and public IPs.**
The `expiresAt` tag is an operator cleanup signal, not an automatic deletion
service. This initial path is deliberately not a falsely advertised unattended
cloud lifecycle. Monitor the operation and delete the dedicated group after
retrieving results. Deployment failure triggers deletion of the newly created
dedicated group; if Azure cleanup itself fails, inspect/delete that exact group.
Do not use this script to reuse an existing group's resources.

## Configure and run jobs

### Dedicated private one-object smoke

The manually dispatched, registered `gpu-batch.yml` workflow now routes explicit
smoke modes to the dedicated reusable `gpu-smoke.yml`. Its default
`smoke_mode=off` preserves the old procedural benchmark; no push or pull request
can start this smoke. A workflow introduced only on a feature branch may not
be dispatchable directly, so use the registered parent:

```sh
gh workflow run gpu-batch.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain -f smoke_mode=readiness
```

Readiness uses only `ubuntu-latest` CPU compute and the repository `HF_TOKEN`
secret. It resolves full 40-character commits for Idol, DINOv3, FLUX.2 VAE,
Grounding DINO and SAM2, actually downloads the two gated small configs at those
pins, and checks Idol's encoder IDs. Only model IDs and immutable pins are
printed; failures report sanitized gate/status errors without service envelopes
or account data. A configured token is not proof of accepted gated-model terms.

CPU [run 43004864760](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43004864760)
actually passed these gated downloads and five model-pin checks on 2026-11-11.
That verifies the current secret's required model access, not GPU reconstruction.

The operator must prepare the existing GPU VM before requesting GPU mode:

- An isolated, trusted ephemeral repository runner with its unique label in
  `SCENE_GPU_RUNNER`; no assumed hosted GPU runner.
- `/home/scene/scene-vision-venv`: Python 3.12, base project plus `.[vision]`,
  including CUDA-matched PyTorch/torchvision, Grounding DINO and SAM2. Install
  torch/torchvision builds from the same PyTorch wheel index, letting torchvision's
  package requirements enforce compatible torch versions. Verify a real CUDA
  torchvision operation (such as `torchvision.ops.nms`) and
  `Sam2Processor.from_pretrained` at the resolved segmenter revision; successful
  imports and basic torch CUDA arithmetic alone do not prove processor readiness.
- `/home/scene/scene-worker-venv`: Python 3.12, base project (`-e .`) plus the
  exact Git-pinned `requirements-idol.txt`, with working CUDA PyTorch/Idol imports.
- Private data root `/home/scene/scene-private-data`, owned by `scene`, mode 0700,
  with I02 registered in `scene.sqlite3` and canonical
  `sources/I02/<original-sha256>/{original,preview.png}` from the upload API.
- `/home/scene/scene-private-data/smoke-output` must not already exist; previous
  results are never silently overwritten. Preserve/move them privately before
  an explicitly approved retry. Allow disk space for gated weights and caches.

**Keep the two environments separate.** The current vision dependency cap
(`transformers<5`) requires `huggingface-hub<1`, while the pinned Idol SDK's
`diffusers>=0.40` requires a newer hub major. Combining `.[vision]` and the Idol
requirements in one environment is not supported; do not loosen the vision cap
or downgrade model quality to make a smoke appear successful. The old full-batch
workflow still has its original combined installation path and is not certified
against this dependency conflict.

Private smoke [43010122800](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43010122800)
passed gated readiness, checked-out imports, the SDK pin and actual CUDA kernels
in both environments. Checksum-verified private I02 intake also succeeded.
Extraction failed after 24.339 seconds because the vision environment lacked
torchvision, required by `Sam2ImageProcessorFast`. This was a missing dependency,
not a model permission failure or successful reconstruction. The vision extra
now declares that dependency. The operator installed torch `2.15.0+cu132` with
torchvision `0.29.2+cu132` in the vision environment only, verified CUDA NMS with
synchronization and SAM2 fast processing of a real PIL input, preserved the
failed output privately at `smoke-failures/run-43010122800`, and re-registered
the consumed ephemeral runner.

The subsequent private smoke
[43011155168](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43011155168)
**succeeded**: checksum-verified I02 `private-original`, `mode=real`, 11 detected
objects, selected `object-000` (`tree`, 2,925 foreground pixels), one rejected
`invalid_crop_format_or_size`, exactly 32,768 validated Gaussians, 50 steps and
seed 42. Final status was `stage=complete`, `status=succeeded`,
`failure_reason=null`; both CUDA/import checks and the SDK pin passed.
Extraction took 16.229 seconds with a sampled device peak of 1,059 MiB; Idol
took 326.585 seconds with 9,295 MiB. Sampling interval was two seconds, not an
exact allocator peak. Actual weights executed successfully, establishing HF
access beyond the readiness configs.

This is **one tree object**, not a full plant/room/digital-twin reconstruction or
an all-eight benchmark. The I02 original, segmentation crops, PLY and logs remain
private on the VM; no smoke media was published and the public previews are unchanged.
Full archive intake on the VM remains incomplete (chunks 00-07 present); I02
was complete through a separate checksum-verified transfer. All eight originals
are valid in the operator's local runtime. See
[`docs/benchmark-status.md`](../../docs/benchmark-status.md) for the result and
remaining acceptance limits.

Once readiness and VM setup are confirmed:

```sh
gh workflow run gpu-batch.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain -f smoke_mode=gpu \
  -f smoke_source=private-original
```

The checked-out source SHA is used in both environments without reinstalling
packages. Both interpreters verify actual CUDA arithmetic and synchronize, not
just `is_available()`. Gate verification uses real pinned downloads rather than
the version-specific `HfApi.auth_check` metadata endpoint; the Idol worker still
downloads its pinned gated encoder files using the job-scoped token.
The extraction subprocess exits before the separate Idol process
starts, releasing detector/segmenter CUDA allocations. I02 uses the existing
`building. conveyor. truck. tree.` prompts. Selection requires an approved
non-person category, a matching RGBA crop at least 32 pixels per side, at least
256 foreground pixels and some transparent mask background. Invalid candidates
are counted; no valid candidate fails explicitly.

Exactly one selected crop is passed to the existing Idol CLI with `--mode real`,
32,768 Gaussians, 50 steps and seed 42. Generation provenance and actual PLY
validity/count are checked before success. There is no Blender batch, synthetic
substitution, reduced-quality retry or automatic publication. A CUDA memory
failure remains a failed smoke.

If private transfer is not ready, the user separately authorized
`-f smoke_source=public-preview`: it uses the checked-in I02 WebP preview and
records that file's actual SHA-256 as `public-webp-preview`, never as original
image bytes. This is an explicit input choice, not a silent fallback.

Originals, crops, scene annotations, raw logs, PLY and preprocessed images stay
on the private VM. The workflow uploads **no artifacts**. Only a constructed
status/timing report is printed; the private output also retains it as
`safe-status.json`. Device VRAM is sampled with `nvidia-smi` every two seconds,
so `peak_device_memory_mib_sampled` is an observed device-wide sample, not a
certified instantaneous per-process peak. Child processes have bounded stage
timeouts and are stopped on interruption. Spot eviction can still interrupt
work; checkpointing and cleanup remain the operator's responsibility.

The unchanged source template's deployment path remains unverified. Successful
one-object inference on the operator's Spot variant does not validate that
template, every model/input combination or full-scene quality; local guard tests
are separate from the actual execution evidence above.

### Private object batch and I02 original-input route

Use the same prepared two environments, unique ephemeral runner label and
checksum-verified I02 original. Full archive intake for the other seven cases
is **not** a prerequisite. Dispatch only when the operator approves execution:

```sh
gh workflow run gpu-batch.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain -f smoke_mode=batch \
  -f smoke_source=private-original
```

This registered-parent route still allocates exactly **one self-hosted job**.
CPU readiness verifies the five exact model revisions observed in successful
smoke `43011155168`, not floating `main`; the pins are recorded in
`scripts/resolve_smoke_models.py`. Inputs must be explicitly selected as
`private-original` or user-approved `public-preview`; there is no silent fallback.
The job keeps its existing CUDA/import/SDK checks and job-scoped HF token.
No packages are installed on the GPU worker by the workflow.

`python -m scripts.private_gpu_batch --data-dir /home/scene/scene-private-data`
runs under `/home/scene/scene-worker-venv/bin/python`. It launches extraction once
in the vision environment with **all** above-threshold detections, explicitly
opting out of the existing local/smoke 48-box limit. Usability retains the
smoke's exact non-person category/visibility/RGBA/size/mask checks. Every
parent node is accounted for, with rejected crops and reasons preserved.
There is no confidence-only selection or arbitrary batch count limit.
Exact byte-identical crop aliases share one inference while retaining all
parent IDs, bounding boxes and crop hashes; similar or overlapping crops are
not heuristically merged.

Every usable distinct crop runs sequentially in a fresh Idol process:
`mode=real`, 32,768 Gaussians, 50 steps, seed 42, compile disabled and SDPA.
An object's failure/OOM/timeout is recorded with its private log; remaining
objects continue without lower-quality or synthetic retries. A run with any
usable-object failure exits nonzero and reports partial/failed status. An empty
usable set fails explicitly. Only all usable distinct outputs passing actual
PLY/provenance validation can produce batch success; this is not full-plant
coverage or geometric-quality acceptance.

Private output root:
`/home/scene/scene-private-data/assets/I02/object-batch/`.
The original-input command above remains unchanged. The user also explicitly
approved using published WebP previews now, retaining originals for final
comparison. To choose that input:

```sh
gh workflow run gpu-batch.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain -f smoke_mode=batch \
  -f smoke_source=public-preview
```

The operator stages `approved-public-previews/I02.webp` under the private data
root. The batch independently requires a byte-for-byte SHA match with the
authorized committed I02 WebP, validates its WebP format, and records
`source_kind=user-approved-public-webp-preview`, SHA, bytes, decoded dimensions,
public URL and `not_original_bytes=true` in the input contract, safe report and
assembled asset provenance. It never writes original Store records or claims
that compressed preview bytes are originals. Its separate output root is
`assets/I02/object-batch-public-preview/`, preventing reuse/mixing with an
original-input batch. No original Store intake is required for this route.

All eight authorized previews may be staged privately with an operator
`intake-report.json`; seven retain their original dimensions, while I03 was
resized from 2000 x 1333 to 1600 x 1066. All are compressed WebPs. The generalized
eight-case selector below uses this same explicit input contract. Diagrams/plans
retain their diagram pipeline. Full-original transfer and final comparison remain separate.

`batch.json` is an atomic checkpoint binding original/preview SHA, five pins,
SDK, settings and a hashed extraction snapshot. It retains the full parent/crop
plan, rejection list, isolated extraction/object attempts and current
`scene_path`. `safe-status.json` and constructed console JSON contain safe
per-object outcomes/timings; raw logs and media remain private.

Redispatch the same command after re-registering a consumed ephemeral runner to
resume. A matching completed extraction is reused, and each completed object is
rechecked against its crop, generation settings/pins, PLY count/attributes and
saved hashes before skipping inference. Complete outputs left by an interrupted
checkpoint are also revalidated. Invalid cached outputs are explicitly marked
and retried in a new attempt directory; prior files are retained. Changed
source/pins/settings or a changed extraction snapshot fail explicitly rather
than silently mixing results. For an intentionally different context, preserve
the entire old batch directory privately before starting a new batch. The prior
single-object smoke directory is not implicitly trusted or imported.

The current private scene snapshot uses the existing Scene/Asset schema and
contains **only validated successful object assets**, not failed-object proxy
substitutions. Original parent IDs, source hash, crop/bbox mapping and duplicate
aliases remain in asset provenance. Positions/sizes retain their unreviewed
inferred image-plane interpretation, not metric or recovered depth. Asset
`/api/assets/` URIs are local schema references under the private Store root:
the batch does not save a scene revision into the database, start an endpoint
or publish anything.

Each child has a bounded timeout (20 minutes extraction, 60 minutes per Idol
object); the single batch job allows 360 minutes. These are execution bounds,
not an object cap. Interruptions leave readable checkpoints and never claim
success; Spot eviction still requires an operator-managed retry. The workflow
uploads no batch artifacts by default, and never originals, crops or raw logs.
The separate derived-publication opt-in below is required for public PLY packaging. The public demo,
public reference previews, default benchmark route and local API behavior are
unchanged. Actual multi-object execution/quality remains pending; the earlier
successful result still establishes only the single-tree smoke.

### Eight-case pilot execution

The private batch now accepts all eight explicit approved preview inputs:

```sh
gh workflow run gpu-batch.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain -f smoke_mode=batch \
  -f smoke_source=public-preview \
  -f 'pilot_cases=I01 I02 I03 I04 I05 G01 G02 G03'
```

Select any unique subset with `pilot_cases`, for example `I03 G01`. The default
remains I02. One self-hosted job processes selected cases sequentially, continues
after a case failure, and stops on interruption. Redispatch a subset to resume
after Spot eviction or the 360-minute job bound. Failed cases do not become
successful merely because other cases complete. Per-case `batch.json` /
`safe-status.json` live under `assets/{ID}/object-batch-public-preview/`;
`pilot-status.json` summarizes this invocation. Extract/object attempt records
include `SCENE_SOURCE_REVISION` (the checked-out Git SHA); checkpoints still bind
source/model/settings and revalidate files before reuse across code checkouts.

I02/I03/G01/G02/G03 use their existing detector prompts and case-specific strict
non-person category allowlists, then sequential real Idol inference with the
same exact model pins and 32,768/50/42 settings. Generated inputs retain
AI-generated reference provenance; compressed WebPs are never original bytes.

I01/I04 diagrams and I05 plan use OCR/line-contour extraction **without** the
normal local 100-region truncation. The vision environment needs OpenCV and
system Tesseract with `eng` and `jpn` language data (I05 fails without Japanese).
Their result is `status=proposals`, not reconstructed appearance: unreviewed
inferred region boxes, assumed height/scale and no invented process topology.
They do not feed symbolic diagram crops into Idol as if they were object photos.
The existing local API and single-object smoke retain their previous defaults.

All eight previews must match the committed authorized bytes. Original Store
records are unchanged; actual original-image transfer/comparison is independent.
No batch artifacts or media are uploaded by default. The operator dispatched
[43043580373](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43043580373)
at `90e478cae3629232440abe7c7beef9b866666fc1` on the recovered Spot T4;
it was still in progress at this source milestone. Actual eight-case completion
and quality acceptance remain pending; source support is not evidence that eight
scenes were reconstructed.

### Explicit derived-only export

The operator approved derived pilot scenes for publication, not private inputs
or logs. `publish_pilots` defaults to **false**. Use
`smoke_mode=batch -f smoke_source=public-preview -f publish_pilots=true`
to package after processing selected cases. A failed batch still fails the job;
packaging may separately export revalidated successful objects with honest partial
statuses. It does not mask inference or package failures.

To export existing **stopped** preview checkpoints without repeating extraction
or inference, register a fresh ephemeral runner, then:

```sh
gh workflow run gpu-batch.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain -f smoke_mode=package \
  -f smoke_source=public-preview -f publish_pilots=true
```

This still uses the registered parent and exactly one prepared self-hosted job.
It skips CUDA/inference stages; readiness retains its pinned-config check.
It refuses an active case lock or `running` checkpoint. A stale running checkpoint
after an abrupt eviction must first be recovered by the normal batch resume route,
not manually marked successful. Stopped interrupted/partial checkpoints may export
only independently revalidated successful objects. It always inventories all eight
cases; `pilot_cases` selects execution, not export scope. Missing checkpoints
remain `not_run`.

The package step runs the **current Actions checkout**, not the stale editable
`/home/scene/scene-worker/source`. Equivalent operator command:

```sh
cd "$GITHUB_WORKSPACE"
PYTHONPATH="$GITHUB_WORKSPACE/services/pipeline" \
  /home/scene/scene-worker-venv/bin/python -m scripts.package_pilots \
  --data-dir /home/scene/scene-private-data \
  --out "$RUNNER_TEMP/pilot-publication-$GITHUB_RUN_ID" \
  --approve-derived-publication
```

The destination must be new. Source/preview SHA, immutable models/SDK/settings,
extraction hashes, parent/crop mapping and actual successful PLYs are revalidated.
Original-input checkpoints are not implicitly approved. Only the dedicated
`$RUNNER_TEMP/pilot-publication-$GITHUB_RUN_ID/` directory uploads after package
validation succeeds, as **`pilot-publication-<runID>`**, retained seven days.
The private data root is never an upload path. Portable contents are exactly
`pilots.json`, declared `scenes/{ID}.json`, and `assets/{ID}/{parent}.ply`.
No originals, masks/crops, raw logs, generation journals or credentials are copied.
Scene/asset provenance is allowlisted; PLY header comments are removed.

The [static demo guide](static-demo.md#approved-derived-pilot-packages) documents
the portable manifest, optional CPU artifact ingestion and separately explicit
deployment. Export success establishes validated file contracts, not human
fidelity acceptance, metric placement or a complete facility.

## Cleanup

Retrieve artifacts, then delete only the verified dedicated group:

```sh
python scripts/azure_gpu.py delete \
  --subscription <approved-subscription-id> --tenant <approved-tenant-id> \
  --group scene-twin-example --confirm-delete
```

Deletion requires matching project ownership tags. Confirm in Azure that the
group and billable resources are gone.
