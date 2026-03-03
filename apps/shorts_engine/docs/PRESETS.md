# Presets

## Purpose
Layer-2 presets provide deterministic default style rules so large job batches keep consistent typography, margins, and pacing.

Jobs can declare:
- `"preset": "tr_psych_v1"`

Preset files live under:
- `shorts_engine/layer2/presets/`

## Contract
Each preset uses schema `0.1` and includes:
- `name`
- `description`
- style sections like `video`, `subtitles`, `visual`, `voice`

Current presets:
- `tr_psych_v1`
- `tr_psych_v2_fast`
- `tr_psych_v3_minimal`

## Merge Rules
- Preset is applied in-memory during `render_job`.
- Merge is limited to safe sections: `video`, `subtitles`, `visual`, `voice`.
- Job explicit values override preset defaults (job wins).
- Input job file is not mutated.

## Validation
- If `preset` is present, validator checks:
  - preset file exists
  - `schema_version == "0.1"`
  - preset `name` matches file name
- Unknown/invalid preset => validation error (exit code `2`).

## Determinism and Hashing
- Effective job (after preset merge) is used for:
  - `job_hash`
  - `run_id`
- Therefore changing preset content or preset name changes `job_hash`/`run_id` deterministically.

Meta/status fields:
- `preset_name`
- `preset_hash`

## CLI
Inspect presets:
- `python -m shorts_engine.layer2.cli.presets list`
- `python -m shorts_engine.layer2.cli.presets show --name tr_psych_v1`
- `python -m shorts_engine.layer2.cli.presets hash --name tr_psych_v1`

