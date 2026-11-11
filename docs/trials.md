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

## Early backend execution

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

Publication/UI integration is a separate additive milestone: the existing
approved pilot package must remain present, and no private crops/logs/tokens may
enter a portable trial package. Backend preparation alone does not publish inputs
or prove actual trial inference.
