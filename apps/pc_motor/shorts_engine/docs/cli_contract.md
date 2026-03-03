# CLI Contract (v0.x)

## Rule 1 - Final stdout line is JSON
All Layer-2 CLIs MUST end stdout with exactly one single-line JSON object.
Pretty/log output may appear earlier (stdout or stderr), but consumers should parse the final line.

Example (bash):
  python -m shorts_engine.layer2.cli.render_batch --help 2>&1 | tail -n 1 | jq .

Example (PowerShell):
  $last = (python -m shorts_engine.layer2.cli.render_batch --help 2>&1 | Select-Object -Last 1)
  $payload = $last | ConvertFrom-Json

## Rule 2 - JSON fields (minimum)
- contract_version: "1"
- ok: true|false
- exit_code: int|null
- error: {type,message,hint}|null
- report_path: string|null
- items: array
- runs: array
- summary: object|null

## Rule 3 - Exit code policy (minimum)
- 0: success
- 2: usage error (invalid args / invalid input)
- 3: unhandled exception (tool crash)
Other codes are allowed but must be documented per command.

