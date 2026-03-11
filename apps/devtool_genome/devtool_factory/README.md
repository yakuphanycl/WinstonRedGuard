# devtool_factory

App scaffold generator.

## Usage

```bash
python -m cli.factory_cli generate <tool_name> [--description <text>] [--template <name>] [--output-root <path>] [--smoke-check] [--evaluate] [--min-score <int>] [--allow-quarantine] [--register]
```

```bash
python -m cli.factory_cli generate example_app --template wrg_app --description "Example WRG app"
```

```bash
python -m cli.factory_cli generate example_app --template wrg_app --output-root apps
```

```bash
python -m cli.factory_cli generate example_app --template wrg_app --smoke-check
```

```bash
python -m cli.factory_cli generate saha_guard --template wrg_app --output-root C:\dev\WinstonRedGuard\apps --smoke-check --evaluate
```

```bash
python -m cli.factory_cli generate saha_guard --template wrg_app --output-root C:\dev\WinstonRedGuard\apps --smoke-check --evaluate --min-score 5 --register
```

```bash
python -m cli.factory_cli generate saha_guard --template wrg_app --output-root C:\dev\WinstonRedGuard\apps --smoke-check --evaluate --min-score 5 --allow-quarantine --register
```

## Registry Behavior

- Registry add runs only after generation and structural smoke check succeed.
- When `--register` is used without `--smoke-check`, the same structural smoke check is still applied before registry add.
- When `--evaluate` is enabled:
  - `score >= min_score` -> registry `status=active`
  - `score < min_score` + `--allow-quarantine` -> registry `status=quarantine`
  - `score < min_score` without `--allow-quarantine` -> registry skipped, non-zero exit
- Registry metadata includes:
  - `status`: `candidate`, `active`, or `quarantine`
  - `verified`: `true` after successful smoke check
  - `score`: evaluator score or `null` when evaluate is not used
  - `source_template`: selected template
  - `created_by`: `devtool_factory`
  - `app_path`: absolute generated app path
- If app already exists in registry, generation remains successful and registry step is skipped with:
  - `registry skip: app already exists: <app_name>`

## Decision Table

- smoke fail -> no register
- smoke pass + no evaluate -> `candidate`
- score >= min_score -> `active`
- score < min_score + allow quarantine -> `quarantine`
- score < min_score + quarantine disabled -> no register

## Templates

- `cli_tool`: flat minimal CLI scaffold
- `single_file_cli`: single-file CLI scaffold
- `wrg_app`: WRG-standard app layout (`src/<app_name>`, `tests`, `data`)
