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

After connecting to the new worker:

```sh
nvidia-smi
sudo apt-get update
sudo apt-get install -y python3-venv git blender python3-numpy tesseract-ocr tesseract-ocr-jpn
git clone https://github.com/ribumann/3d-scene-toolchain.git
cd 3d-scene-toolchain
git checkout <verified-implementation-commit>
python3 -m venv .venv
.venv/bin/pip install -e ".[vision]" -r requirements-idol.txt
```

Supply `HF_TOKEN` through the operator's secret facility; do not put it in shell
history, Git, deployment parameters or public logs. Accept the gated encoder terms
and configure the immutable model revision variables described in the main README.
Start with one low-count object and measure memory on the T4:

```sh
.venv/bin/scene-toolchain preflight
.venv/bin/scene-toolchain run --cases P02 --stages extract blender idol --report report.json
```

Only run the full procedural batch after the real inference succeeds. Transfer
the `.scene-data` bundle privately to the browser host; serve it using
`SCENE_DATA_DIR`. For a long-lived worker use restricted self-hosted Actions
configuration only after establishing its trust/lifecycle policy.

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
