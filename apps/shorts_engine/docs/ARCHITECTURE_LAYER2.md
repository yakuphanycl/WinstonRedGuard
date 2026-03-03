# Architecture Layer-2

## Scope
- This document explains the active Layer-2 golden path and its gates in `shorts_engine`.
- Entrypoints are confirmed in generated output (`shorts_engine/docs/_generated/entrypoints.txt:L3-L9`).

## Responsibilities of Layer-2
- Accept CLI input and fail fast on missing/invalid job path (`shorts_engine/layer2/cli/render_job.py:L113-L123`).
- Validate Layer-2 jobs (schema + semantic checks) before rendering (`shorts_engine/layer2/cli/render_job.py:L131-L142`, `shorts_engine/layer2/core/validate_job.py:L102-L115`, `shorts_engine/layer2/core/validate_job.py:L120-L198`).
- Orchestrate run-store lifecycle and call Layer-1 renderer through core (`shorts_engine/layer2/cli/render_job.py:L144-L151`, `shorts_engine/layer2/core/render.py:L64-L117`).
- Record run-store metadata fields in meta/finalize paths (`shorts_engine/layer2/core/render.py:L81-L90`, `shorts_engine/layer2/core/render.py:L137-L146`, `shorts_engine/layer2/cli/render_job.py:L159-L170`, `shorts_engine/layer2/cli/render_job.py:L199-L220`).
- Emit canonical result line consumed by verify (`shorts_engine/layer2/cli/render_job.py:L221-L224`, `shorts_engine/tools/verify.ps1:L169-L181`).

## Non-Responsibilities
- Layer-2 does not perform low-level video rendering itself; Layer-1 does via ffmpeg in `layer1/cli/render_job.py` (`shorts_engine/layer2/core/render.py:L107-L116`, `shorts_engine/layer1/cli/render_job.py:L110-L137`, `shorts_engine/layer1/cli/render_job.py:L173`).
- Best-effort artifact finalization and telemetry writes do not fail the render (`shorts_engine/layer2/cli/render_job.py:L50-L77`, `shorts_engine/layer2/cli/render_job.py:L80-L110`).

## Run-Store v0.5 Invariants
- `RUN_STORE_VERSION` is code-defined as `"0.5"` (`shorts_engine/layer2/core/run_store.py:L11`).
- `REQUIRED_ARTIFACTS` source of truth is in `run_store.py` (`shorts_engine/layer2/core/run_store.py:L17-L23`).
- `run_id` deterministic for dict jobs (`sha256(stable_json(job))[:12]`) (`shorts_engine/layer2/core/run_store.py:L42-L49`, `shorts_engine/layer2/core/run_store.py:L52-L54`).
- `cached=True` is set on cache-hit path when run-local output already exists (`shorts_engine/layer2/core/render.py:L68-L98`).

## Key Semantics
- `ok` (verify-level): `true` only after compile + render + output checks succeed (`shorts_engine/tools/verify.ps1:L240-L283`, `shorts_engine/tools/verify.ps1:L317-L347`).
- `artifacts_ok_fs`: filesystem contract check result from required artifacts (`shorts_engine/tools/verify.ps1:L71-L105`, `shorts_engine/tools/verify.ps1:L147-L153`).
- `artifacts_ok`: backward-compatible alias to filesystem result (`shorts_engine/tools/verify.ps1:L151-L153`).
- `artifacts_missing`: missing artifact list from FS check (`shorts_engine/tools/verify.ps1:L100-L103`, `shorts_engine/tools/verify.ps1:L336-L337`).

## Layer-1 Boundary
- Layer-2 core invokes Layer-1 with subprocess command:
  - `python -m layer1.cli.render_job <runs/<run_id>/job.layer1.json>`
  - Evidence: `shorts_engine/layer2/core/render.py:L107-L116`.

## Gates and Guarantees
- `verify.ps1` guarantees compile+smoke render+output existence and emits JSON contract (`shorts_engine/tools/verify.ps1:L240-L283`, `shorts_engine/tools/verify.ps1:L317-L347`).
- `verify.ps1` now resolves canonical v0.5 artifacts by default and only uses legacy substitutions in compatibility mode (`shorts_engine/tools/verify.ps1:L71-L105`, `shorts_engine/tools/verify.ps1:L114-L176`).
- `release_check.ps1` guarantees hard gate on `artifacts_ok` (`true` required) and docs existence checks (`shorts_engine/tools/release_check.ps1:L82-L88`, `shorts_engine/tools/release_check.ps1:L103-L114`).

## Notes on Verification and Compatibility
- Verification resolves run artifacts with a version-aware strategy.
- Canonical resolution is default for run-store v0.5.
- Legacy resolution is enabled only for older/unknown versions or explicit `-CompatLegacy`.
- Any substitutions are explicit in JSON output (`compat_mode`, `legacy_probes_used`, `resolved_*_path`, `artifacts_substitutions`).
- This keeps the current pipeline deterministic while still allowing safe inspection of historical runs.
