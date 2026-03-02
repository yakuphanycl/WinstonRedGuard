# STATE

## Current contract (stable)

- Run: `python -m workspace_inspector ...`
- JSON:
  - `--json` defaults to `-` (stdout)
  - `--json -` writes JSON to stdout
  - `--json PATH` writes JSON to file
- Stdout/Stderr:
  - When emitting JSON to stdout, stdout is pure JSON (no human text).
  - Errors go to stderr.
- Quiet:
  - `--quiet` suppresses human-readable stdout (including file-output mode).
- JSON metadata:
  - `schema_version`, `tool`, `tool_version`, `generated_at` exist at root.
- Tests:
  - `tools/smoke.ps1` is the pytest-free contract check.
- CI:
  - GitHub Actions runs module smoke (no install).
