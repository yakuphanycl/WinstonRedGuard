# repo_doctor

Scans `apps/` in the monorepo and reports structural health for each app.

Primary role metadata: developer tool catalog.

## Usage

```bash
python -m repo_doctor.cli scan
```

```bash
python -m repo_doctor.cli scan --json-out apps/repo_doctor/data/report.json
```

## Status Meanings

- `OK`: `pyproject.toml`, `src/<app_name>/`, `src/<app_name>/cli.py`, and tests (`tests/test_*.py`) all exist.
- `PARTIAL`: `pyproject.toml` and `src/<app_name>/` exist, but `cli.py` or tests are missing.
- `BROKEN`: `pyproject.toml` or `src/<app_name>/` is missing.
