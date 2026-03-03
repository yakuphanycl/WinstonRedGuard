# Contracts (V0.6)

## Job Schema
- Layer-2 jobs are validated against:
  - `layer2/schemas/job_v0_5.json`
- `version` must be `"0.5"` for current gate.

## Run Status Schema (`runs/<run_id>/status.json`)
- `schema_version`: `"0.1"`
- `state`: `"running" | "done"`
- `ok`: boolean
- `result_rc`: integer
- `artifacts_ok`: boolean
- `error_type`: `"none" | "validation" | "io" | "core" | "unknown"`
- `error_code`: optional string (`E_SCHEMA`, `E_INPUT_MISSING`, `E_RENDER`, `E_ARTIFACTS`, `E_EXCEPTION`)
- `message`: optional string
- `started_at`: ISO8601 timestamp
- `ended_at`: ISO8601 timestamp
- `duration_ms`: integer
- `out_path`: optional string
- `cached`: optional boolean
- `artifacts`:
  - `mp4`: optional path
  - `meta`: optional path
  - `trace`: optional path

## Batch Report Schema (`--json-out` and `runs/_batch/<batch_run_id>/batch_status.json`)
- Required top-level keys:
  - `meta`, `summary`, `fail_by_type`, `sample_failures`, `items`
- `schema_version`: `"0.1"`
- `meta`:
  - `tool`, `timestamp`, `cwd`, `args`
- `summary`:
  - `total`, `ok`, `fail`, `cached`
  - `retries_attempted`, `retries_succeeded`
  - `total_duration_ms`, `avg_duration_ms`, `max_duration_ms`
- `fail_by_type`:
  - `validation_error`, `io_error`, `render_error`, `timeout`, `internal_error`
- `sample_failures`:
  - up to 3 items with `job_path`, `error_type`, `message`
- `items`:
  - required: `job_path`, `status` (`ok|fail|skipped`), `duration_sec`
  - backward-compatible fields retained: `run_id`, `result_rc`, `cached`, `out_path`, `error_type`
  - on failure, item includes `error` object with `type` + `message`

## Error Type Mapping
- Allowed taxonomy:
  - `validation_error`, `io_error`, `render_error`, `timeout`, `internal_error`
- Mapping intent:
  - schema/semantic validation -> `validation_error`
  - missing input / FS access -> `io_error`
  - renderer/subprocess/artifact failures -> `render_error`
  - timeout conditions -> `timeout`
  - unmapped/unexpected failures -> `internal_error`

## Exit Codes
- `render_job`:
  - `0`: success
  - `2`: validation/user error
  - `1`: internal/runtime failure
- `render_batch`:
  - `0`: all items OK (or OK + skipped only)
  - `2`: one or more items failed (report still produced)
  - `1`: batch runner usage/crash path

## Backward Compatibility
- `schema_version` is required in status and batch report payloads.
- New fields may be added; consumers must ignore unknown fields.
- Existing keys keep semantic meaning across minor updates.
