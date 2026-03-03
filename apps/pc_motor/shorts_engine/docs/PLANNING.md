# Planning

`plan.py` provides a deterministic daily cadence over ideas -> jobs -> render.

## Data Layout

Under `shorts_engine/layer2/data/plans/<YYYY-MM-DD>/`:

- `plan.json`: canonical daily plan (`schema_version=0.1`).
- `done.jsonl`: append-only execution events.

## Plan Stages

- `planned`: selection created.
- `generated`: CSV/jobs/jobset artifacts created.
- `rendered`: batch render completed with no failures.
- `partial`: render completed with failures.
- `published`: manual publish mark step completed.
- `failed`: reserved for future hard-fail workflows.

## CLI Workflow

1. Create plan:

```powershell
python -m shorts_engine.layer2.cli.plan make --date 2026-02-22 --ideas-target 20 --selection oldest
```

2. Build artifacts:

```powershell
python -m shorts_engine.layer2.cli.plan build --date 2026-02-22
```

This generates:

- `inputs.csv`
- generated jobs dir (`jobs/`)
- `manifest.json`
- `jobs.txt`
- `jobset.json`

3. Render planned jobs:

```powershell
python -m shorts_engine.layer2.cli.plan render --date 2026-02-22 --continue-on-error --max-fail 3
```

4. Optional publish marker:

```powershell
python -m shorts_engine.layer2.cli.plan mark-published --date 2026-02-22
```

## Determinism Rules

- Selection uses queued ideas from `ideas/state`.
- `oldest`: stable by `created_at` then insertion/index.
- `round_robin`: stable sorted keys with date-based rotation.
- `random_seeded`: deterministic with explicit or date-derived seed.

## Recovery From Partial Failures

- Re-run `plan render --date <day>` after fixing failures.
- `plan build --force` regenerates artifacts if inputs changed.
- `done.jsonl` keeps an append-only execution audit.
