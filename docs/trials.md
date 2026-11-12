# Opt-in generated industrial trials

These trials are separate from the frozen eight-source pilot and its approved
publication `43079293375`. Primary T01-T03 inputs are synthetic photographic
equipment-room scenes with backgrounds, clutter, shadows and modest occlusion,
not isolated studio products. Earlier studio images are controls only, not primary
inputs or evidence of pipeline improvement. T01-T03 compare detector/SAM2 extraction with explicitly
supervised reviewed-box/SAM2 extraction, not a pure algorithm A/B or a measured
reconstruction-accuracy benchmark. Manual boxes are a supervised comparison, not
proof that automatic detection improved. Expected inventories count target
equipment, not every background cable/shelf; extraction mistakes, contamination
and failures still require explicit review. No persons or private reference imagery are
inputs. Synthetic photographic inputs, manually authored semantics/layout and generated
3D appearances are distinct evidence.

## Protected sequential workflow

The committed `cases/trials.json` is the approved primary photographic manifest,
semantically identical to immutable input manifest
[`6ebc4cc.../manifest.json`](https://raw.githubusercontent.com/ribumann/3d-scene-toolchain/6ebc4ccc49a0db48c9cfa6c3cbf038ae67db6dde/experiments/overnight-20261111/manifest.json)
(upstream byte SHA256 `793c0057baaae75363c663839bfda910e9c67f79b1b2c30de41ba5a9d8eb4cb2`).
The three PNGs decode to **1448 x 1086**, independently checked rather than assumed.
T01 targets one pump assembly; T02 targets one pump, tank and control cabinet;
T03 targets two separate pump assemblies. T03 has no reusable-asset assertion.

An authorized operator can dispatch the existing registered workflow:

```sh
gh workflow run gpu-batch.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain \
  -f smoke_mode=trials -f smoke_source=public-preview \
  -f 'pilot_cases=T01 T02 T03' -f trial_variants=both
```

For the first small run set `pilot_cases=T01`. `trial_variants` also accepts
`baseline` or `optimized`; redispatch resumes the selected matching checkpoints.
The trial route uses the committed photographic manifest, not the pilot source
selector or baseline Store. All selected variants run sequentially in the existing
single-GPU concurrency group, with a 360-minute bound. Existing
`SCENE_GPU_RUNNER`, the protected Actions `HF_TOKEN` secret and both prepared
interpreters/model caches are required. No operator token extraction or new
model/service provisioning is needed. The workflow stages only immutable same-repo
PNG URLs, checks SHA256, rejects redirects, caps each download at 12 MiB and checks
PNG decoding and a 20-million-pixel ceiling before atomic placement.

## Direct backend execution

Private trial execution and export are **Linux/POSIX-only**: both require real
`fcntl.flock` checkpoint locks on the prepared worker. Windows supports downloaded
package validation and static builds, not private inference/export. The Linux
test suite exercises locking and symlink protection; missing Windows flock or
symlink privileges are not grounds to weaken those checks.

Use the **current checkout**, the existing two prepared interpreters, and stage
approved generated PNGs at
`/home/scene/scene-private-data/approved-trials/{T01,T02,T03}.png`.
The manifest is strict schema version 1 (see `scripts/trial_contracts.py`):
only T01-T03, exact source filename/SHA, immutable raw repository URL, explicit
publication approval, prompt, expected inventory, optional reviewed normalized
boxes and optional relative instance placements. Generator provenance is exactly
`Copilot image_generation tool; underlying image model/version not exposed`.
No model/version is invented.

The source metadata `kind` is `generated-photographic-scene`.
`detector_phrases` and reviewed categories allow pump, motor, tank, control cabinet,
conveyor and industrial machine only. Boxes use normalized `[x,y,width,height]`.
Expected inventory is a declared target, not a reviewed accuracy score.
Reviewed objects have explicit IDs/identities and `reviewed=true`; repeated
authored placements require a `reusable_asset_id` and are not independent
reconstructions. Differing generated copies are never presumed identical.

Once an approved manifest/input is staged, run one or more selected variants:

```sh
cd "$GITHUB_WORKSPACE"
export PYTHONPATH="$GITHUB_WORKSPACE/services/pipeline"
# Supply HF_TOKEN via the existing protected job environment, never a file.
/home/scene/scene-worker-venv/bin/python - <<'PY'
import os
from scripts.package_pilots import APPROVED_PINS
os.environ.update(APPROVED_PINS)
os.environ.update(ATTN_BACKEND="sdpa", SCENE_IDOL_COMPILE="0")
from scripts.private_gpu_trials import main
import sys
sys.argv = ["private_gpu_trials", "run",
    "--data-dir", "/home/scene/scene-private-data",
    "--manifest", "/home/scene/scene-private-data/approved-trials/manifest.json",
    "--cases", "T01", "--variants", "baseline", "optimized"]
raise SystemExit(main())
PY
```

Only the selected variants execute, sequentially. Extraction runs in
`scene-vision-venv`; each Idol process runs in `scene-worker-venv`. Both variants
retain the frozen five model pins, SDK, 32,768 Gaussians / 50 steps / seed 42,
SDPA and compile-off settings. There is no higher-quality sweep, model change,
synthetic fallback or arbitrary object truncation.

## Optimization, resume and evidence

Outputs are isolated at `trials/{ID}/{variant}/`, with atomic `trial.json` and
`safe-status.json`. Matching extraction/crop hashes are revalidated on resume.
Manifest/source/settings changes explicitly reject reuse. Interruption preserves
readable checkpoints; a complete-but-uncheckpointed output can resume only after
actual generation/PLY validation. Individual failures remain visible and do not
become cached successes.

Both variants reject tiny/degenerate/unsegmented crops. Optimized duplicate
suppression additionally requires the **same reviewed identity**, box IoU at least
0.95 and source-coordinate alpha-mask IoU at least 0.98. Same category or a similar
appearance alone is insufficient. Every removed proposal records its canonical
ID/reason. No heuristic claims repeated generated copies are the same asset.

Successful actual outputs populate `trials/cache/{fingerprint}/`. The fingerprint
binds exact crop bytes, immutable models/SDK, Gaussian count, steps/seed,
attention/compile and crop policy. Only optimized variants read this shared cache;
baseline executes its own uncached comparison unless resuming its own checkpoint.
Cache hits revalidate generation provenance, PLY attributes/count and receipt
hashes; invalid entries fail explicitly instead of pretending success.
Exact reuse is reported as reuse, not another independent reconstruction.

Reports include expected/detected/usable counts, rejected reasons, individual
failure/timing records, wall time, cache hit/miss, resume and independent generation
counts, plus settings/source hashes. Counts are coverage observations, not accuracy
or fidelity scores. Timings are actual observations only; no unmeasured speedup
is promised. Layout, scale and depth remain inferred or explicitly authored
relative assumptions, not recovered metric truth.

## Derived-only export and additive public build

Publication is a separate explicit opt-in, using the existing isolated CPU
publisher (`SCENE_PUBLISH_RUNNER`, distinct from the GPU runner/work directory):

```sh
gh workflow run gpu-batch.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain \
  -f smoke_mode=trial-package -f publish_trials=true
```

The CPU route has no model token or CUDA visibility. It locks each variant,
skips active checkpoints as `processing` with no scene, and revalidates stopped
extraction receipts, actual output hashes/provenance and 32,768-Gaussian PLYs.
No private root is uploaded. Only the dedicated new
`$RUNNER_TEMP/trial-publication-$GITHUB_RUN_ID/` directory becomes artifact
`trial-publication-<runID>`, retained seven days:

| Path | Content |
|---|---|
| `trials.json` | Exact T01-T03 baseline/optimized inventory, safe counts/status/timing and declared file hashes |
| `trial-manifest.json` | Exact approved generated-input provenance, prompts, target inventory, reviewed boxes and authored relative layout |
| `references/T0N.png` | Only the explicitly approved, hash-bound generated photographic PNGs |
| `scenes/T0N-<variant>.json` | Completed validated appearances only, with inferred/authored placement provenance |
| `assets/T0N/<variant>/<object>.ply` | Validated appearances with stripped header comments |

No crops/masks, raw logs, source-runtime paths or tokens are allowed. Failures are
safe error codes, never copied exception logs. A failed/interrupted/no-output
variant remains visible without substitute geometry. Read-only validation/build
is portable; private export requires Linux/POSIX flock.

After review, build additively with the **unchanged approved final pilot package
43079293375**, never an empty default baseline:

```sh
gh workflow run ci.yml --repo ribumann/3d-scene-toolchain \
  --ref copilot/hybrid-scene-toolchain \
  -f pilot_run_id=43079293375 -f trial_run_id=TRIAL_PACKAGE_RUN_ID -f deploy=false
```

Both runs must be completed trusted `gpu-batch.yml` runs on this branch;
workflow path/registered ID and exact artifact names are checked through REST.
All package files/hashes and committed source authorization are revalidated.
The trial CI path refuses a missing or different pilot run ID. The static builder
also rejects trials without a complete eight-source pilot package.

For approved packages already downloaded locally:

```sh
SCENE_PILOT_PUBLIC_PACKAGE=/path/to/approved-pilot-package \
SCENE_TRIAL_PUBLIC_PACKAGE=/path/to/approved-trial-package npm run build:demo
```

Only `apps/web/dist-demo/` is publishable. Trial PLYs/references use isolated
`/trial-assets/` and `/trial-references/` paths; the original eight views/files
remain intact. The compact Trials section exposes both methods, expected versus
actual counts, rejections/failures, timing, exact reuse/resume, pins and source
provenance. Direct links use `?case=T01-baseline` or `?case=T01-optimized`
(similarly T02/T03), including honest pending/processing states. Neither the
normal default build nor a source commit proves trial inference or deploys results.
Do not deploy the default reference-only build over the approved public baseline.
