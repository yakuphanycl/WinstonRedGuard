# refinery

`refinery` inspects WRG apps for productization signals, creates a minimal refine plan, marks packaging state, and suggests bundles.

Primary role metadata: developer tool catalog.

## Usage

```bash
python -m refinery.cli inspect app_registry
python -m refinery.cli refine-plan app_registry
python -m refinery.cli package-mark app_registry --market-ready
python -m refinery.cli bundle-suggest app_registry
python -m refinery.cli show app_registry
python -m refinery.cli list
```

## Data

- default: `apps/refinery/data/refinery_records.json`
- optional override: `REFINERY_DATA_PATH`
