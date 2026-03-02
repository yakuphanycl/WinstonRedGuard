# Changelog

## v0.2.5
- Add JSON root metadata: schema_version/tool/tool_version/generated_at.
- Keep stdout JSON clean for `--json -`.

## v0.2.4
- Route CLI errors to stderr.
- Enforce `--quiet` keeps stdout empty in file-output mode (tests added).

## v0.2.3
- Add `__main__.py` so `python -m workspace_inspector` works.
- Make `--json` default to stdout when used without a value.
- Add CI smoke (pytest-free).
