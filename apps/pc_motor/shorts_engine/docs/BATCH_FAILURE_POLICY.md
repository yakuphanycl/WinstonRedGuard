# Batch Failure Policy (v0.1)

## Flags
- `--continue-on-error`: continue processing after failures.
- `--max-fail N`: stop once failures reach `N`.
- `--only-failed-from <batch_report.json>`: select only failed jobs from previous report.
- `--retry-failed`: marks retry intent when used with `--only-failed-from`.

## Default behavior
- Default mode is stop-on-first-failure (`continue_on_error=false`, `max_fail=1`).
- Batch stops early on first failed job unless `--continue-on-error` is set.

## Exit codes
- `0`: all selected jobs succeeded (`batch_ok=true`).
- `2`: one or more jobs failed, or batch stopped early due to failure policy.
- `1`: runner usage/runtime crash path.

## Report contract fields
Top-level batch report includes:
- `batch_ok`
- `stopped_early`
- `stop_reason`
- `continue_on_error`
- `max_fail`
- `selection_mode` (`all` | `only_failed_from` | `retry_failed_from`)
- `source_batch_report`
- `selected_jobs_count`

## Retry and cache interaction
- Retry selection uses prior `items[]` failure markers (`result_rc`, `error_type`, `status`).
- Existing successful cached runs can still be reused by normal cache policy.
- Failed stale runs are re-executed (not skipped) unless explicit skip conditions are met.
