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

This verifies infrastructure and the installed driver, **not PyTorch/CUDA model
execution or Idol inference**. The extension initially left an active/partial
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
now declares that dependency; the operator must install and verify it on the
worker, preserve the failed private output and re-register the consumed
ephemeral runner before retrying. No inference success is implied.

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

The unchanged source template's deployment path and actual GPU inference remain
unverified. The Spot infrastructure snapshot above does not validate that
template or model compatibility; local tests cover guard behavior only.

## Cleanup

Retrieve artifacts, then delete only the verified dedicated group:

```sh
python scripts/azure_gpu.py delete \
  --subscription <approved-subscription-id> --tenant <approved-tenant-id> \
  --group scene-twin-example --confirm-delete
```

Deletion requires matching project ownership tags. Confirm in Azure that the
group and billable resources are gone.
