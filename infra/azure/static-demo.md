# Public static read-only demo

## Scope and status

This deployment uses Azure Storage static website hosting, with no FastAPI
backend, GPU, container or model credentials. Three public procedural scene
snapshots are generated directly from the repository's deterministic templates.
The eight image-input cases are listed as unavailable, not reconstructed.
This is an illustrative scene viewer, not a live or engineering-certified
digital twin. Public upload, import, editing, evidence review and pipeline
execution are disabled; the demo sends no `/api` requests.

The coordinating operator reported creation of these dedicated resources.
Resource creation is not deployment or public rendering verification:

| Setting | Intended value |
|---|---|
| Tenant | `ecd6dfda-d2ce-47a8-9901-e35f31fe18dd` |
| Subscription | `86677b6e-28fc-48e4-8988-5ab9e568eece` (`ME-MngEnvMCAP621318-ribumann-2`) |
| Resource group | `rg-3d-scene-toolchain-poc` |
| Storage account | `scene3dpoc86677b6e` |
| Region / SKU | `swedencentral` / `Standard_LRS`, StorageV2 |
| Planned endpoint | `https://scene3dpoc86677b6e.z1.web.core.windows.net/` |

The account has HTTPS-only transport, minimum TLS 1.2 and blob public ACLs
disabled. The **static website endpoint is nevertheless intentionally public**;
disabling blob ACLs does not make `$web` website contents private. Publish only
the allowlisted build output and never uploaded source images, tokens, runtime
stores or a repository archive. Do not expose the unauthenticated local API.

## Build and inspect

Requirements: Python 3.11+, Node 22.12+ (see package engine constraints), npm.
Neither Blender nor CUDA is needed to build or host this demo. The visiting
browser needs WebGL2; view controls do not require a cloud GPU.

From the repository root on the continuation branch:

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
npm ci
. .venv/bin/activate
.venv/bin/python -m unittest tests.test_static_demo -v
npm test -- --run
npm run build:demo
python3 -m http.server 4173 --bind 127.0.0.1 --directory apps/web/dist-demo
```

Inspect `http://127.0.0.1:4173/`. All static asset paths are same-origin root
paths, compatible with the planned Azure website root (not a subpath).
Check all three scenes, object selection/isolation, top/reset camera, labels,
route pause/play, JSON export, missing-image states and a narrow viewport.
Network inspection must show no `/api` requests, uploads or mutation calls.

**Artifact:** `apps/web/dist-demo/` contains `index.html`, bundled `assets/`,
and `demo/{cases,P01,P02,P03}.json`. The separate `apps/web/dist/` is the
editable local frontend and must **not** be substituted for this artifact.
Generated JSON includes no external assets, private sources or runtime data.
The generator refuses unexpected files in its public output rather than
silently bundling them.

## Operator-only Azure publication

These commands are a handoff, not an automatic deploy script. The operator must
verify fresh ARM authorization and the exact tenant/subscription first. Do not
change credentials, request model tokens or provision a GPU for this demo.

```sh
az account show --query '{subscription:id,tenant:tenantId,name:name,state:state}' -o json
az storage account show \
  --subscription 86677b6e-28fc-48e4-8988-5ab9e568eece \
  --resource-group rg-3d-scene-toolchain-poc --name scene3dpoc86677b6e \
  --query '{id:id,website:primaryEndpoints.web,https:enableHttpsTrafficOnly,tls:minimumTlsVersion,publicBlobACLs:allowBlobPublicAccess}'
```

Stop on any identity/resource mismatch. Publishing with `--auth-mode login`
requires an appropriate blob data-plane role, such as **Storage Blob Data
Contributor** on this dedicated account; subscription Contributor alone does
not imply blob data access. Role changes are a separate operator decision.
Use the authenticated CLI environment; never put account keys or SAS tokens in
source, frontend configuration or chat.

```sh
az storage blob service-properties update \
  --account-name scene3dpoc86677b6e --auth-mode login \
  --static-website --index-document index.html
az storage blob upload-batch \
  --account-name scene3dpoc86677b6e --auth-mode login \
  --destination '$web' --source apps/web/dist-demo --overwrite true
```

The build is root-only and does not need SPA route fallbacks. Leave unknown
paths, especially `/api/...`, as errors rather than mapping them to `index.html`.
Verify upload content types (`text/html`, JavaScript, CSS, `application/json`);
do not disable HTTPS or enable public blob-container ACLs to solve access
failures.

After publication, verify HTTPS, each JSON snapshot, browser WebGL rendering and
no `/api` requests on the real public origin before claiming a deployed demo.
Storage/egress have small but nonzero costs; apply an operator-managed budget
and delete the dedicated resource group when the PoC is no longer needed.
Upload-batch does not remove older hashed bundles; remove only known obsolete
files if needed, never unrelated account contents.
