# Runs Retention (v0.1)

## Why cleanup exists
- Cache/idempotency keeps repeated jobs fast, but `runs/` grows over time.
- Cleanup prevents unbounded disk growth while preserving failed runs for debugging.

## Tool
- `python -m shorts_engine.layer2.cli.clean_runs`

## Default policy
- `keep_last=50`: keep newest 50 run folders.
- `keep_days=14`: keep runs newer than 14 days.
- `keep_failed=true`: never delete failed runs.
- `keep_batch_last=20`: keep newest 20 batch folders under `runs/_batch`.

Keep set is union of:
- newest `keep_last`
- within `keep_days`
- failed runs (if `keep_failed=true`)

## Failed run rule
A run is treated as failed when:
- `meta.error_type` is non-null/non-empty, or
- `meta.artifacts.artifacts_ok == false`

## Safety constraints
- Only deletes run folders with hex-like id (`8..16`) and `meta.json` present.
- Only deletes batch folders under `runs/_batch` when `batch_report.json` exists.
- Never deletes `runs/` root or unknown folders.

## Dry-run vs apply
- Default mode is dry-run (plan only).
- Use `--apply` to perform deletion.
- JSON report can be written with `--json-out`.

## Interaction with determinism/cache
- Deterministic `run_id` + cache still work after cleanup.
- If a cached run was cleaned, next execution re-renders and recreates artifacts.
