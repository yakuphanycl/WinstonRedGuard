# Jobset Contract (v0.1)

## Purpose
- Deterministically build and inspect a selected set of jobs before running batch.
- Reduce friction for subset selection and reproducible batch inputs.

## CLI
- `python -m shorts_engine.layer2.cli.jobset build ...`
- `python -m shorts_engine.layer2.cli.jobset inspect --jobset <path>`
- `python -m shorts_engine.layer2.cli.jobset emit-list --jobset <path> --out <path>`

## Jobset JSON shape
`schema_version: "0.1"` payload includes:
- `schema_version`
- `created_at`
- `jobset_hash`
- `source`:
  - `jobs_dir`
  - `glob`
  - `jobs_file`
- `filters`:
  - `only_version`
  - `min_duration`
  - `max_duration`
  - `contains_text`
  - `limit`
- `jobs[]`:
  - `job_path`
  - `job_hash`
  - `duration_sec`
- `counts`:
  - `scanned`
  - `selected`

## Determinism rules
- Input job paths are normalized and sorted stably by `job_path`.
- `jobset_hash` is computed from normalized selected job paths + source + filters.
- Rebuilding with identical inputs/filters yields identical `jobset_hash`.

## render_batch integration
- `render_batch --jobset <jobset.json>` consumes `jobs[].job_path`.
- Batch report records:
  - `selection_mode: "jobset"`
  - `jobset_path`
  - `jobset_hash`

## Difference vs --jobs-file
- `--jobs-file`: plain list input only.
- `--jobset`: versioned, hashable, inspectable contract with source/filters metadata.
