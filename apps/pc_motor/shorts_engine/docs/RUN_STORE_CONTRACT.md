## Required artifacts

# Run Store Contract

## Run Store Version
- `RUN_STORE_VERSION = "0.5"`.
- Evidence: `shorts_engine/layer2/core/run_store.py:L11`.

## REQUIRED_ARTIFACTS (single source of truth)
Exactly as code defines:
- `job.layer2.json`
- `job.layer1.json`
- `meta.json`
- `stdout.log`
- `*.mp4`

Evidence: `shorts_engine/layer2/core/run_store.py:L17-L23`.

## Directory Layout
- Run root: `shorts_engine/runs/`.
- Per-run directory: `runs/<run_id>/`.
- Canonical paths built by `RunPaths`.
- Evidence: `shorts_engine/layer2/core/run_store.py:L31-L39`, `shorts_engine/layer2/core/run_store.py:L52-L65`.

## Semantics
- `ok`:
  - Verify-level status (compile + render + output checks passed).
  - Evidence: `shorts_engine/tools/verify.ps1:L240-L283`, `shorts_engine/tools/verify.ps1:L317-L347`.
- `artifacts_ok_fs`:
  - Filesystem check against REQUIRED_ARTIFACTS contract.
  - Evidence: `shorts_engine/tools/verify.ps1:L71-L105`, `shorts_engine/tools/verify.ps1:L147-L150`.
- `artifacts_ok`:
  - Backward-compatible alias to `artifacts_ok_fs`.
  - Evidence: `shorts_engine/tools/verify.ps1:L151-L153`.
- `cached`:
  - `True` on cache-hit path where run-local output already exists and render is skipped.
  - Evidence: `shorts_engine/layer2/core/render.py:L68-L98`.

## Required Artifact Check Rules
- Python helper contract (`check_required_artifacts`) in run_store:
  - checks presence of REQUIRED_ARTIFACTS under run dir,
  - supports wildcard entries,
  - requires mp4 size `>= mp4_min_bytes` (default 1024).
- Evidence: `shorts_engine/layer2/core/run_store.py:L72-L104`.

## Meta Fields (versioned)
- Core writes in `meta.json`:
  - `run_store_version`, `required_artifacts`.
  - Evidence: `shorts_engine/layer2/core/render.py:L81-L90`, `shorts_engine/layer2/core/render.py:L137-L146`.
- CLI best-effort meta/status writes include:
  - `run_store_version`, `required_artifacts`, `artifacts_ok_fs`, `artifacts_ok`, `artifacts_missing`.
  - Evidence: `shorts_engine/layer2/cli/render_job.py:L159-L167`, `shorts_engine/layer2/cli/render_job.py:L179-L187`, `shorts_engine/layer2/cli/render_job.py:L205-L214`.

## Failure Modes
- Missing required artifacts:
  - `artifacts_ok_fs=false`, `artifacts_missing` contains missing entries.
  - Evidence: `shorts_engine/tools/verify.ps1:L96-L105`, `shorts_engine/tools/verify.ps1:L336-L337`.
- Render failure (`rc != 0`):
  - core writes `trace.txt` best-effort,
  - CLI marks failed state and returns `1`.
  - Evidence: `shorts_engine/layer2/core/render.py:L131-L135`, `shorts_engine/layer2/cli/render_job.py:L153-L173`.
- Best-effort writes may be partial:
  - finalize/telemetry writes swallow exceptions and do not fail the render.
  - Evidence: `shorts_engine/layer2/cli/render_job.py:L50-L77`, `shorts_engine/layer2/cli/render_job.py:L100-L110`, `shorts_engine/layer2/cli/render_job.py:L215-L218`.

## Verify Version Match
- Verify reads `run_store_version` from `meta.json` (best-effort), imports expected version from Python, and emits:
  - `run_store_version`
  - `run_store_version_expected`
  - `run_store_version_match`
- Missing metadata yields `UNKNOWN`.
- Evidence: `shorts_engine/tools/verify.ps1:L58-L69`, `shorts_engine/tools/verify.ps1:L154-L164`, `shorts_engine/tools/verify.ps1:L313-L340`.

## Compatibility Mode (verify)
- Default (`compat_mode=canonical`): verify checks canonical artifact names from `REQUIRED_ARTIFACTS`.
- Auto-legacy mode (`compat_mode=legacy`): enabled when `run_store_version` is `UNKNOWN` or older than expected, or when `-CompatLegacy` is passed.
- In legacy mode, verify allows mapped substitutions and records them in `artifacts_substitutions`.
- Evidence: `shorts_engine/tools/verify.ps1:L71-L105`, `shorts_engine/tools/verify.ps1:L107-L176`, `shorts_engine/tools/verify.ps1:L334-L345`.

During verification, artifact resolution follows a versioned compatibility model:
- For `run_store_version >= 0.5`, verification uses canonical mode: only names from `REQUIRED_ARTIFACTS` are accepted.
- For older/`UNKNOWN` versions, or when `-CompatLegacy` is set, verification uses legacy mode and may substitute known legacy filenames.
- Substitutions are explicit in output via `compat_mode`, `legacy_probes_used`, `resolved_*_path`, and `artifacts_substitutions`.
- This preserves backward compatibility without weakening the v0.5 contract.

### Artifacts (optional diagnostics)
- `layer1_stdout_path`: string (optional), canonicalize sırasında bulunan Layer-1 stdout dosyası.
- `layer1_stderr_path`: string (optional), canonicalize sırasında bulunan Layer-1 stderr dosyası.
- `source_mp4`: string (optional), canonicalization öncesi referans alınan mp4 kaynağı.
- `source_trace`: string (optional), canonicalization öncesi referans alınan trace kaynağı.
- `trace_fallback_used`: string (optional), trace bulunamazsa stdout+stderr birleştirilerek `trace.txt` üretildiğinde `"true"`.

Notes:
- `trace.txt` mümkün olduğunca deterministiktir; trace yoksa stdout/stderr'den fallback üretilir.
- Fallback trace boyutu sınırlandırılabilir (tail-truncate).

