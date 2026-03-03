# Ideas Pipeline (v0.1)

## Purpose
- Maintain an append-only ideas inventory.
- Build deterministic CSV input for bulk job generation.
- Track lifecycle state (`queued -> rendered -> published`).

## Data files
Default under `shorts_engine/layer2/data/`:
- `ideas.jsonl` (append-only)
- `state.json` (mutable small state)

CLI supports `--data-dir` to override this location.

## ideas.jsonl schema
Each line is a JSON object:
- `id` (optional)
- `created_at` (iso)
- `topic`
- `hook`
- `body`
- `ending`
- `lang` (optional)
- `duration_sec` (optional)
- `tags` (optional list)
- `source` (optional)
- `idea_key` (deterministic)

## state.json schema
- `schema_version: "0.1"`
- `updated_at`
- `items` map by `idea_key`
  - `status`: `queued|rendered|published|dropped`
  - `last_changed_at`
  - `note`
  - `run_id`
  - `job_path`
  - `batch_run_id`

## Deterministic identity (idea_key)
`idea_key = sha1(normalize(hook) + "|" + normalize(body) + "|" + normalize(ending))`

This key is used for:
- dedup
- stable ordering
- state linkage

## build-csv determinism
- `ideas build-csv` filters by state/tag.
- Output ordering is deterministic: sorted by `idea_key` ascending.
- CSV columns:
  - `id,hook,body,ending,duration_sec,lang,tags`
- UTF-8 write with normalized LF.

## Recommended production loop
1. `ideas add` / `ideas import-csv`
2. `ideas build-csv --status queued`
3. `gen_jobs --input inputs.csv --template ... --out-dir ...`
4. `render_batch --jobs-file jobs.txt` (or `--jobset`)
5. `ideas mark --idea-key ... --status rendered|published`
6. `clean_runs` retention
