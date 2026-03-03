# Cache Policy (v0.1)

## Default behavior
- `render_job` computes deterministic `run_id` from job JSON.
- If `runs/<run_id>/meta.json` exists, `artifacts.artifacts_ok == true`, and the resolved mp4 exists on disk:
  - treat as cache hit
  - do not invoke Layer-1 render
  - return `rc=0` with `cached=true`

## Cache miss behavior
- If meta is missing, unreadable, `artifacts_ok` is false, or mp4 is missing:
  - treat as cache miss
  - proceed with render path

## Flags
- `--force`: always re-render (cache bypass).
- `--no-cache`: ignore cache hit and re-render.
- `--reuse`: explicit reuse mode (same as default behavior).

## Telemetry fields
- `meta.json` includes:
  - `cache_hit: bool`
  - `cache_reason: string|null`
  - `cached: bool`
- `status.json` includes:
  - `cached: bool`
  - `cache_hit: bool`
  - `cache_reason: string|null`
- `batch_report.json` summary includes:
  - `cached_count: int`
  - `rendered_count: int`
