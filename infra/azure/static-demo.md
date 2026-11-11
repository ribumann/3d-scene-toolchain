# Public static read-only demo

## Scope and status

This deployment uses a dedicated **Free Azure Static Web App**, with no FastAPI
backend, GPU, container or model credentials. Three public procedural scene
snapshots are generated directly from the repository's deterministic templates.
Eight authorized metadata-stripped WebP reference previews are also included:
I01-I05 original references, and G01/G02/G03 AI-generated grocery/semiconductor/zoo.
They are labeled **reference only**, not reconstructed 3D scenes.
This is an illustrative scene viewer, not a live or engineering-certified
digital twin. Public upload, import, editing, evidence review and pipeline
execution are disabled; the demo sends no `/api` requests.

The coordinating operator reported creation of these dedicated resources.
Resource creation is not deployment or public rendering verification:

| Setting | Configured target |
|---|---|
| Tenant | `ecd6dfda-d2ce-47a8-9901-e35f31fe18dd` |
| Subscription | `86677b6e-28fc-48e4-8988-5ab9e568eece` (`ME-MngEnvMCAP621318-ribumann-2`) |
| Resource group | `rg-3d-scene-toolchain-poc` |
| Static Web App | `swa-3d-scene-toolchain-poc` |
| Region / plan | `eastus2` / Free |
| Public endpoint | `https://red-wave-0c7bb6c0f.4.azurestaticapps.net/` |
| Original storage target (blocked) | `scene3dpoc86677b6e`, `swedencentral`, Standard_LRS |

The original Storage website publication was blocked by enforced
`publicNetworkAccess: Disabled`; a normal public-network update did not override
the policy. No firewall, authentication or TLS bypass was used. A separate
Free Static Web App was therefore created in the same dedicated resource group.
West Europe returned a regional new-customer capacity refusal, so this app uses
East US 2. The original Storage account remains provisioned, network-disabled
and unused; it does not host the demo.

The site is intentionally public. Publish only the allowlisted build output and
never full original images, tokens, runtime stores or a repository archive.
Reference-image publication authorization covers these eight WebP previews,
not private originals or masks/crops. The operator separately approved validated
derived pilot scenes/PLY for the explicit package route below; the ordinary build
still includes no inference output, and this new route is not yet deployed.
Do not expose the unauthenticated local API. The operator configured the
repository secret `AZURE_STATIC_WEB_APPS_API_TOKEN_SCENE_POC` for this exact app;
its value must never be copied into source, logs, frontend configuration or chat.
CPU workflow run
[43000921576](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43000921576)
completed the upload successfully and reported this exact public hostname,
with Oryx skipped and no API/Functions created.

On 2026-11-11 the coordinating operator separately verified the public origin:
HTTPS returned 200 in a secure context; the case catalog and all three scene
snapshots returned 200 with `application/json`; actual WebGL2 geometry rendered
for Grocery (28 objects), Semiconductor (28) and Zoo (49), with no lost context.
Case switching sent no `/api` requests, labels toggled successfully, and an
explicit `/api/cases` probe returned 404. The public browser panel was only
173 pixels wide; the earlier 390-pixel no-overflow check was a separate local
verification, not a public-device/performance certification. This initial public
check predates the reference-preview UI; do not treat it as verification of a
later preview deployment.

The eight-reference update was published successfully by CPU workflow
[43006759156](https://github.com/ribumann/3d-scene-toolchain/actions/runs/43006759156),
source `c7b4507acc2f340634daba29289f3389231433b6`. Both CPU/Blender checks and the
web build/deployment passed. Artifact `13849271102` is
`static-demo-c7b4507acc2f340634daba29289f3389231433b6`, with upload digest
`sha256:1ed465a30aa7d17d2572953ff36e45a7c23ea71476c704fa6ba3db49105d96a5`.
An independent download verified the exact public file boundary and all eight
preview files byte-for-byte against the authorized repository assets.
Local browser checks decoded all eight actual previews at desktop/mobile sizes,
with correct provenance, no image-case 3D canvas, no `/api` requests or mutation
controls, and a working image-error/reload state. This cloud workspace could not
repeat the public-origin check because of DNS/client policy; no bypass was
attempted. The coordinating operator subsequently verified the updated public
origin in Browser on 2026-11-11: all eight `/references/{ID}.webp` URLs returned
HTTP 200 with `image/webp` and decoded at the expected dimensions; `/api/cases`
returned 404. Selecting G03 showed the correct AI-generated provenance,
original-kept-private copy, no reconstructed 3D scene and zero objects.
P01 still visibly rendered 28 objects before switching. These are public-origin
observations, separate from the local desktop/mobile checks and not evidence of
image reconstruction or actual Idol inference.

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
route pause/play, JSON export, all eight reference images and provenance labels,
preview-error/reload behavior and a narrow viewport.
Network inspection must show no `/api` requests, uploads or mutation calls.

**Artifact:** `apps/web/dist-demo/` contains `index.html`, bundled `assets/`,
`demo/{cases,pilots,P01,P02,P03}.json`, and exactly
`references/{I01,I02,I03,I04,I05,G01,G02,G03}.webp`. The separate `apps/web/dist/` is the
editable local frontend and must **not** be substituted for this artifact.
Generated JSON includes only root-relative authorized preview URLs, no private
sources or runtime data. The generator explicitly copies only these eight files
from `apps/web/public/references`; it never copies the general public tree or a
runtime store. Missing allowlisted previews, output symlinks or unexpected output
files fail the build rather than silently publishing partial/unreviewed content.
By default `demo/pilots.json` is empty: no I/G scene JSON, masks, crops, PLY files
or full originals are published.

The **CPU toolchain checks** workflow also builds this artifact and uploads it
as `static-demo-<full-commit-SHA>` for seven days, using only CPU workers. Its
ordinary build/artifact path uses no Azure/model credentials. If local package
access is blocked, download the
successful run's artifact rather than bypassing TLS verification:

```sh
gh run download <successful-run-id> --repo ribumann/3d-scene-toolchain \
  --name static-demo-<full-commit-SHA> --dir apps/web/dist-demo
```

Verify the run's source SHA and artifact digest before publishing. The download
contains the build root directly (`index.html`, `assets/`, `demo/`); do not
substitute the separate procedural-report artifact or an unverified local build.

## Approved derived pilot packages

The private GPU workflow has a separate explicit `publish_pilots=true` approval
flag, default **false**, and a `smoke_mode=package` route for stopped checkpoints
without repeating inference. See the [operator export command](README.md#explicit-derived-only-export).
Only validated preview-input results enter **`pilot-publication-<GPUrunID>`**
with seven-day retention; no upload ever targets the private data root.
The portable allowlist is:

| File | Contract |
|---|---|
| `pilots.json` | Schema version 1, explicit derived approval, ordered eight-case status entries, exact declared-file SHA256 map |
| `scenes/{ID}.json` | Existing Scene schema; only successful appearances or unreviewed diagram/plan proposals |
| `assets/{ID}/{parent}.ply` | Revalidated 32,768-Gaussian object output, sanitized header/provenance |

Each case records `status` (`not_run`, `failed`, `partial`, `succeeded`, `proposals`),
published parent-object count, `failed_objects` (failed **or unfinished** distinct
crops), optional rejected count and extraction/object Git `source_revisions`.
It retains original-vs-generated reference origin, authorized preview SHA,
`input_kind=user-approved-public-webp-preview`, `not_original_bytes=true`, and
`layout=inferred-not-metric`. It never relabels compressed/generated input as
original photography. `scene=null` is required for no-result cases. Scene assets
retain parent IDs, crop hashes, pixel bounding boxes, duplicate aliases and
model/SDK settings; crop bytes, private paths, raw logs and tokens are excluded.
File validation is not human fidelity acceptance.

The CPU workflow can consume an explicitly selected completed GPU run on this
same branch, including a failed run that successfully exported partial results:

```sh
gh workflow run ci.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain \
  -f pilot_run_id=<GPUrunID> -f deploy=false
```

It downloads only the exact named artifact, revalidates the allowlist/checksums,
and builds the usual `static-demo-<source-SHA>` artifact. To publish after review,
use that same command with `deploy=true`; deployment remains separately opt-in.
A missing, expired, wrong-branch or invalid package fails rather than falling back.
Omitting `pilot_run_id` preserves the reference/procedural-only build.

Local equivalent, from the **current checked-out source** with the Python
environment activated:

```sh
gh run download <GPUrunID> --repo ribumann/3d-scene-toolchain \
  --name pilot-publication-<GPUrunID> --dir <new-approved-package-directory>
SCENE_PILOT_PUBLIC_PACKAGE=<approved-package-directory> npm run build:demo
```

The optional build adds `/demo/pilots.json` status entries, declared `/demo/{ID}.json`
and `/pilot-assets/pilot/{ID}/{parent}.ply`. Private `/api/assets/...` schema URIs
are remapped only to these allowlisted same-origin static paths; no API is exposed.
To change/remove a package in a reused build directory, remove only the known old
generated pilot files first; stale/unapproved output is intentionally rejected.

The viewer separates actual object splats from unreviewed diagram boxes and
reference-only/failed cases, shows partial/unfinished counts, and keeps reference
comparisons. Actual appearances have **no geometry substitute** while loading or
on failure; loading/errors are explicit. Layout/depth/scale remain inferred.
The default P01-P03 demos and local editable API behavior are unchanged.

Local checks using explicitly **synthetic test PLYs** traversed all eight statuses,
loaded object appearances (including `Loaded 1/1` with WebGL2 context intact),
and checked a 390-pixel no-overflow proposal/reference layout without `/api`
requests. These are renderer/orchestration checks, not eight-case Idol execution
or public-origin verification. Actual derived deployment and per-case fidelity
acceptance remain pending the operator's output review.

## Opt-in Static Web Apps publication

Deployment is disabled by default. Pushes, pull requests and manual runs with
`deploy=false` only build, test and publish the artifact. A manual run with
`deploy=true` additionally invokes the official `Azure/static-web-apps-deploy@v1`
action, using only the dedicated app's repository secret. It uploads
`apps/web/dist-demo` directly with `skip_app_build=true`, empty output location
and no API location (therefore no API build). It does not publish the ordinary editable frontend,
create Azure resources or request GPU/model access.

The operator must verify the exact target and current authorization before
dispatching; do not change resource policies or copy deployment keys:

```sh
az account show --query '{subscription:id,tenant:tenantId,name:name,state:state}' -o json
az staticwebapp show \
  --subscription 86677b6e-28fc-48e4-8988-5ab9e568eece \
  --resource-group rg-3d-scene-toolchain-poc --name swa-3d-scene-toolchain-poc \
  --query '{id:id,hostname:defaultHostname,sku:sku.name}'
```

Stop on an identity/resource mismatch. After verifying the approved source
revision on the continuation branch, dispatch the CPU workflow explicitly:

```sh
gh workflow run ci.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain -f deploy=true
```

Check the deployment step's real outcome and reported hostname: the verified
upload targeted the main public hostname, not a preview environment.
A successful artifact upload alone is not a successful site deployment.

The build is root-only and does not need SPA route fallbacks. Leave unknown
paths, especially `/api/...`, as errors rather than mapping them to `index.html`.
Verify upload content types (`text/html`, JavaScript, CSS, `application/json`);
do not disable HTTPS or enable public blob-container ACLs to solve access
failures.

After each new publication, repeat the HTTPS, JSON, WebGL and no-`/api` checks;
the verified observations above are a point-in-time deployment check.
The app uses the Free plan, not a paid hosting tier. Other resources in the
dedicated group can still incur charges; apply an operator-managed budget and
delete only the verified dedicated resources when the PoC is no longer needed.
