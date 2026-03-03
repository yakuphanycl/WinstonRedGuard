# Releasing

## Version Source
- Single source of truth: `shorts_engine/layer2/core/version.py`
- Runtime `engine_version` fields in meta/status are derived from this version.

## Release CLI
Command:
- `python -m shorts_engine.layer2.cli.release status`
- `python -m shorts_engine.layer2.cli.release bump --part patch|minor|major`
- `python -m shorts_engine.layer2.cli.release bump --set X.Y.Z`
- `python -m shorts_engine.layer2.cli.release build`

Exit codes:
- `0` success
- `2` usage/gate failure
- `1` unexpected exception

## Bump Workflow
1. Run `release status`.
2. Run `release bump --part patch` (or `minor`/`major`, or `--set`).
3. Update the generated changelog stub in `CHANGELOG.md`.
4. Run release checks.

`bump` updates:
- `shorts_engine/layer2/core/version.py`
- `shorts_engine/CHANGELOG.md` (prepends a new version section stub)

## Build Workflow
`release build`:
1. Runs `tools/release_check.ps1 -Job layer2/examples/min_job.json` (unless `--skip-gates`).
2. Produces `shorts_engine/dist/shorts_engine_<version>.zip`.
3. Writes `shorts_engine/dist/release_manifest.json`.

## Bundle Rules
Included roots:
- `shorts_engine/layer1`
- `shorts_engine/layer2`
- `shorts_engine/tools`
- `shorts_engine/docs`
- `shorts_engine/CHANGELOG.md`
- `shorts_engine/README.md` (if present)
- `shorts_engine/LICENSE` (if present)

Excluded patterns:
- `**/__pycache__/**`
- `**/*.pyc`, `**/*.pyo`
- `**/*.mp4`
- `**/runs/**`
- `**/output/**`
- `**/_tmp/**`, `**/_junk/**`
- `**/dist/**`

## Manifest Contract
`shorts_engine/dist/release_manifest.json` includes:
- schema/version metadata
- git branch/commit (best effort)
- gate status
- zip + manifest hashes
- include/exclude rule snapshot

