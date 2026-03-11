# devtool_genome

Developer tool genome catalog CLI.

## Goal

Catalog developer tools as structured records and query them from CLI.

## Planned commands

- `dgen list`
- `dgen find <keyword>`
- `dgen show <tool_id>`

## Status

V0 skeleton initialized.

## Acquisition Backend Pilot (Optional)

- Default fetch backend remains lightweight requests path.
- Scrapling is pilot-only and fully optional.
- Business logic remains backend-agnostic through app-local fetch adapter.
- Adapter emits a minimal acquisition observation envelope:
  `observation_version`, `backend_requested`, `backend_used`, `fallback_used`,
  `duration_ms`, `success`, `error_type` (and optional `run_id`, `source_id`, `artifact_path`).

Enable Scrapling backend (opt-in):

```bash
set DEVTOOL_GENOME_FETCH_BACKEND=scrapling
```

Disable Scrapling backend / return to default:

```bash
set DEVTOOL_GENOME_FETCH_BACKEND=default
```

Optional install for pilot backend:

```bash
pip install ".[scrapling]"
```
