# app_evaluator

`app_evaluator` evaluates a WinstonRedGuard app folder and produces a minimal quality report.

Role: verification / audit worker.
Primary role metadata: developer tool catalog.

## Usage

```bash
app_evaluator eval --app-path apps/app_registry
app_evaluator eval --app-path apps/app_registry --json-out reports/eval.json
```

## Checks

- `app_exists`
- `pyproject_exists`
- `cli_exists` (expects `src/<app_name>/cli.py` with `main()` function)
- `tests_exist`
- `smoke_test_exists`
- `pytest_passed` (`python -m pytest <app>/tests -q`)

## Exit Codes

- `0`: evaluation complete and PASS
- `1`: evaluation complete and FAIL
- `2`: usage error
