# wrg_control

`wrg_control` is the top-level control entrypoint for the WinstonRedGuard system.

It provides a single CLI surface to inspect overall monorepo app status.

Primary role metadata: developer tool catalog.

## Usage

```bash
python -m wrg_control.cli status
```

```bash
python -m wrg_control.cli status --json-out apps/wrg_control/data/status.json
```

## Status Rules

Each app under `apps/` is checked for:
- `has_pyproject`: `pyproject.toml` exists
- `has_src_package`: `src/<app_name>/` exists
- `has_cli`: `src/<app_name>/cli.py` exists
- `has_tests`: `tests/` exists and contains at least one `test_*.py`

Classification:
- `OK`: all checks pass
- `PARTIAL`: `pyproject` and `src package` exist, but `cli` or `tests` are missing
- `BROKEN`: `pyproject` missing or `src package` missing
