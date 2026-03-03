# Flow Render Job

## End-to-End Flow (numbered)
1. Parse args (`--job` or positional).
- Function: `_parse_args`, `main`.
- Evidence: `shorts_engine/layer2/cli/render_job.py:L43-L47`, `shorts_engine/layer2/cli/render_job.py:L113-L116`.

2. Fail fast on missing job arg/path.
- Exit `2` if missing or not found.
- Evidence: `shorts_engine/layer2/cli/render_job.py:L116-L123`.

3. Start timing window.
- `_t0` and `_ts0` captured before validation/render.
- Evidence: `shorts_engine/layer2/cli/render_job.py:L125-L126`.

4. Load and validate job.
- Read JSON, load schema, validate.
- Validation errors return `2`.
- Evidence: `shorts_engine/layer2/cli/render_job.py:L129-L142`, `shorts_engine/layer2/cli/render_job.py:L227-L229`.

5. Enter core orchestration (`render_from_job`).
- Evidence: `shorts_engine/layer2/cli/render_job.py:L144-L147`.

6. Core maps Layer-2 -> Layer-1 job.
- Script fallback chain and output fallback are applied.
- Evidence: `shorts_engine/layer2/core/render.py:L11-L43`.

7. Core creates run store (`runs/<run_id>/...`).
- Uses `prepare_run` path contract.
- Evidence: `shorts_engine/layer2/core/render.py:L64-L67`, `shorts_engine/layer2/core/run_store.py:L52-L65`.

8. Cache-hit path (if run-local output already exists).
- Skips subprocess render.
- Ensures requested output copy.
- Writes `meta.json` including `cached=True`, `run_store_version`, `required_artifacts`.
- Evidence: `shorts_engine/layer2/core/render.py:L68-L90`.

9. Normal render path.
- Writes `job.layer2.json` and `job.layer1.json`.
- Invokes `python -m layer1.cli.render_job <job.layer1.json>`.
- Captures stdout/stderr into `stdout.log`.
- Evidence: `shorts_engine/layer2/core/render.py:L101-L116`.

10. Core output handling.
- On success copies run output to requested output (if different).
- On failure writes `trace.txt` best-effort.
- Writes `meta.json` with `run_store_version` and `required_artifacts`.
- Evidence: `shorts_engine/layer2/core/render.py:L125-L146`.

11. Back in CLI: rc failure branch.
- Updates `meta.json` state/error.
- Adds `run_store_version`, `required_artifacts`, `artifacts_ok_fs`, `artifacts_ok`, `artifacts_missing` best-effort.
- Ensures fallback `trace.txt`.
- Returns `1`.
- Evidence: `shorts_engine/layer2/cli/render_job.py:L153-L173`.

12. Back in CLI: success branch meta update.
- Updates `meta.json` with done state + out_path.
- Writes run-store fields (`run_store_version`, `required_artifacts`, `artifacts_ok_fs`, `artifacts_ok`, `artifacts_missing`).
- Evidence: `shorts_engine/layer2/cli/render_job.py:L175-L190`.

13. Best-effort finalize legacy artifacts into run dir.
- Copies `output/_last_render_meta.json` -> `runs/<run_id>/render_meta.json`
- Copies `output/_last_render_trace.txt` -> `runs/<run_id>/render_trace.txt`
- Copies `output/_captured_layer1_job.json` -> `runs/<run_id>/layer1_job.json`
- Evidence: `shorts_engine/layer2/cli/render_job.py:L92-L107`, `shorts_engine/layer2/cli/render_job.py:L191`.

14. Timing finalize write.
- Computes `_dur_ms = round((_t1 - _t0)*1000)`.
- Writes `render_start_ts`, `render_end_ts`, `render_duration_ms` and run-store fields into `render_meta.json` best-effort.
- Evidence: `shorts_engine/layer2/cli/render_job.py:L193-L220`.

15. Emit success result line and exit `0`.
- `RESULT ok rc=0 out=... run_id=... cached=...`
- Evidence: `shorts_engine/layer2/cli/render_job.py:L221-L225`.

## Exit Codes
- `0`: success (`shorts_engine/layer2/cli/render_job.py:L225`).
- `1`: render/internal failure (`shorts_engine/layer2/cli/render_job.py:L172-L173`, `shorts_engine/layer2/cli/render_job.py:L249-L250`).
- `2`: usage/validation failure (`shorts_engine/layer2/cli/render_job.py:L116-L123`, `shorts_engine/layer2/cli/render_job.py:L227-L229`).
