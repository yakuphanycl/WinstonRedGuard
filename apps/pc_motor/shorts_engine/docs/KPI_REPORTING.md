# KPI Reporting

`report_kpi.py` creates a lightweight weekly/date-range production summary from local files.

## What It Measures

Sources:
- `layer2/data/plans/<date>/plan.json`
- `layer2/data/plans/<date>/done.jsonl`
- `plan.artifacts.batch_report` (or `<plan_dir>/batch_report.json` fallback)
- `layer2/data/publish_journal.jsonl`

Outputs include:
- planning totals and stage distribution
- rendering totals (`jobs_ok`, `jobs_fail`, `cached`, `rendered`)
- rates (`cache_rate`, `fail_rate`)
- publishing totals and platform breakdown

## What It Does Not Measure

- external platform analytics (views, retention, CTR)
- revenue/performance attribution
- post-publish behavioral metrics

## Usage

Weekly report:

```powershell
python -m shorts_engine.layer2.cli.report_kpi --days 7
```

Custom range:

```powershell
python -m shorts_engine.layer2.cli.report_kpi --start 2026-02-16 --end 2026-02-22 --platform youtube_shorts
```

Write explicit output:

```powershell
python -m shorts_engine.layer2.cli.report_kpi --days 7 --json-out shorts_engine/layer2/data/reports/kpi_week.json
```

## Interpretation Tips

- `cache_rate` high + `published_count` low can indicate planning/rendering works but publishing cadence lags.
- `fail_rate` rising usually signals job quality drift (schema/lint/content shape) or environment regressions.
- `days_with_plans` below target week cadence indicates execution inconsistency, not renderer speed.

## Weekly Loop

1. Run daily plan/build/render flow.
2. Publish selected runs and append publish journal entries.
3. End of week: run `report_kpi --days 7` and review totals + notes.
4. Adjust next week’s `ideas_target/render_target/publish_target` policy based on report.
