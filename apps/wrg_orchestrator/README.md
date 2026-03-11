# wrg_orchestrator

`wrg_orchestrator` is the orchestration entrypoint for WinstonRedGuard workflows.

It is different from analysis apps:
- analysis tools inspect and report data
- orchestration coordinates multi-step workflows and returns workflow results

## Usage

```bash
python -m wrg_orchestrator.cli list
python -m wrg_orchestrator.cli run daily_check
python -m wrg_orchestrator.cli run daily_check --json-out apps/wrg_orchestrator/data/daily_check.json
```

## Built-in Workflows (v0)

- `daily_check`
  - scan apps structure
  - summarize health
  - return workflow result object

