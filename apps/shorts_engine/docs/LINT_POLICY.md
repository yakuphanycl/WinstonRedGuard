# Lint Policy

## Purpose
Layer-2 lint catches deterministic content-shape issues before render.

It is fast, local, and dependency-free.

## Severities
- `error`: fails lint run and (by default) validation.
- `warn`: reported but does not fail unless `--fail-on warn`.
- `info`: telemetry/estimation only.

## Rules

### Error
1. Missing/invalid `output.path` or extension not `.mp4`.
2. `video.duration_sec` outside allowed range (`3..90`).
3. Subtitle overflow risk:
   - line longer than `max_chars_per_line`
   - wrapped line count exceeds `max_lines`
   - single word longer than max chars
4. Invalid control characters in text (`ord < 32`, except `\n`, `\r`, `\t`).
5. Empty subtitle text item.
6. Empty `hook/body/ending` when field is present.

### Warn
1. Text density high (chars/sec heuristic above threshold).
2. Repeated subtitle phrases.
3. Subtitle item count high (`> 12`).
4. Hook too long (`> 80` chars).

### Info
1. Estimated CPS and WPM.
2. Derived subtitle constraints in effect.

## Preset Influence
- If job has `preset`, lint uses preset subtitle constraints:
  - `max_lines`
  - `max_chars_per_line`
- If absent, defaults are used:
  - `max_lines = 2`
  - `max_chars_per_line = 26`

## CLI
Run linter:
- `python -m shorts_engine.layer2.cli.lint --job <job.json>`
- `python -m shorts_engine.layer2.cli.lint --jobs-file <jobs.txt>`
- `python -m shorts_engine.layer2.cli.lint --jobs-dir <dir>`

Options:
- `--fail-on error|warn`
- `--format text|json`
- `--json-out <path>`

## Validation Integration
- `validate_job` runs lint by default.
- Disable lint only with env override:
  - `SHORTS_LINT=0` (or `false/off/no`)
- `render_job` records lint telemetry in meta/status:
  - `lint_ok`
  - `lint_error_count`
  - `lint_warn_count`

