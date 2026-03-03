# Job Generator (gen_jobs) v0.1

## Purpose
- Generate many Layer-2 jobs deterministically from simple CSV input and a JSON template.
- Produce machine-readable build proof via `manifest.json`.

## CLI
- `python -m shorts_engine.layer2.cli.gen_jobs --input <csv> --template <template.json> --out-dir <dir> [flags]`

## CSV columns
Recommended columns:
- `id` (optional, used for deterministic row key)
- `hook`
- `body`
- `ending`
- `duration_sec` (optional)
- `voice` (optional)
- `lang` (optional)
- `tags` (optional, comma-separated)

Additional columns are allowed and available as placeholders.

## Placeholder rules
- Template placeholders are string tokens like `{{hook}}`, `{{body}}`, `{{ending}}`.
- Replacement is string-only.
- Unknown placeholder:
  - default: replaced by `""`
  - with `--strict-template`: treated as error (exit code 2)

## Deterministic naming
- `row_key`:
  - if `id` exists: normalized id
  - else: `sha1(hook|body|ending)` short prefix
- Output filename:
  - `<prefix>_<index:04d>_<row_key>.json`
- Rows are sorted by `row_key` before indexing.
- Same input/template/policy yields stable output filenames.

## Overwrite/skip behavior
- Default (`--overwrite` off): existing files are skipped.
- With `--overwrite`: existing files are replaced.
- `--dry-run`: computes plan/manifest without writing job files.

## Manifest contract (`manifest_v0_1`)
Top-level keys:
- `schema_version`
- `created_at`
- `input_path`
- `template_path`
- `out_dir`
- `generator_version`
- `policy`
- `counts`
- `hashes`
- `items`

`hashes`:
- `input_sha1`
- `template_sha1`
- `manifest_sha1`

`items[]`:
- `row_key`
- `source_id`
- `job_path`
- `job_hash`
- `duration_sec`
- `tags`

## Recommended workflow
1. `gen_jobs` -> generate jobs + `jobs.txt` + manifest.
2. Optional: `jobset build` from generated jobs.
3. `render_batch --jobs-file jobs.txt` (or `--jobset`).
4. Apply retention with `clean_runs`.
