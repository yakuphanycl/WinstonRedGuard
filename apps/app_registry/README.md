# app_registry

`app_registry` is the WinstonRedGuard app inventory CLI.
It stores app records in a local JSON file and supports simple list/show/add flows.

## Commands

```bash
app_registry list
app_registry list --status quarantine
app_registry show <name>
app_registry add --name tool_name --version 0.1.0 --role worker --entrypoint tool.cli:main
app_registry add --name tool_name --version 0.1.0 --role worker --entrypoint tool.cli:main --status active --score 6 --verified --source-template wrg_app --created-by devtool_factory --app-path C:\dev\WinstonRedGuard\apps\tool_name
app_registry add --name tool_name --version 0.1.0 --role worker --entrypoint tool.cli:main --class worker --primary-role "ops worker" --internal-customer ops --external-product-potential medium --productization-stage internal_mvp
app_registry classify tool_name --class dual_role_product --primary-role "dual role utility" --internal-customer ops external_builders --external-product-potential high --productization-stage product_candidate --assigned-by governance_check --reason "promotion approved"
app_registry audit
app_registry reevaluate saha_guard --min-score 5
app_registry reevaluate saha_guard --min-score 5 --activate-on-pass
app_registry reevaluate-all --min-score 4
app_registry reevaluate-all --min-score 4 --activate-on-pass
app_registry reevaluate-all --min-score 4 --status quarantine
```

## Registry Data Format

Path:

`data/registry.json`

Schema:

```json
{
  "apps": [
    {
      "name": "app_registry",
      "version": "0.1.0",
      "role": "inventory",
      "entrypoint": "app_registry.cli:main",
      "app_type": "python_app",
      "layout": "src",
      "python_package": "app_registry",
      "stack": null,
      "status": "active",
      "score": 6,
      "verified": true,
      "source_template": "wrg_app",
      "created_by": "devtool_factory",
      "app_path": "C:\\dev\\WinstonRedGuard\\apps\\app_registry",
      "class": "internal_infra",
      "primary_role": "registry authority",
      "internal_customer": ["platform", "all apps"],
      "external_product_potential": "medium",
      "productization_stage": "internal_operational",
      "class_assigned_at": "2026-03-08T00:00:00+00:00",
      "class_assigned_by": "human",
      "reclassification_reason": null,
      "reclassification_history": [],
      "last_verified_at": "2026-03-07T19:00:00"
    }
  ]
}
```

## Classification Metadata

Official class enum:

- `worker`
- `internal_infra`
- `dual_role_product`

Required classification-alignment fields:

- `class`
- `primary_role`
- `internal_customer`
- `external_product_potential` (`low|medium|high`)
- `productization_stage` (`experimental_lab|internal_mvp|internal_operational|product_exploration|product_candidate|market_ready_candidate`)

Reclassification tracking fields:

- `class_assigned_at`
- `class_assigned_by`
- `reclassification_reason`
- `reclassification_history`

Rollout behavior:

- Existing legacy records without these fields remain readable.
- Invalid enum values are rejected on add/classify/update paths.

## Extended Fields

- `status`: app state (`candidate`, `active`, `quarantine`)
- `verified`: structural/evaluation checks have been completed
- `score`: evaluator score when available; may be `null`
- `source_template`: scaffold template used during generation
- `created_by`: source system that created the record (for example `devtool_factory`)
- `app_path`: absolute app location for traceability
- `app_type` (optional): app runtime family (for example `python_app`, `node_app`)
- `layout` (optional): package/layout hint (`src`, `flat`, `legacy_flat`, `custom`)
- `python_package` (optional): explicit import package when different from app folder name
- `stack` (optional): stack hint for non-python apps (for example `electron-vite`)

## Status Lifecycle

- low score app -> `quarantine`
- reevaluate pass (`score >= min_score`) -> `active`
- reevaluate fail (`score < min_score`) -> `quarantine`
- no evaluate but smoke-passed generated app -> `candidate`

## Reevaluate-All

- `reevaluate-all` scans registry entries and reevaluates them in bulk.
- Optional `--status` filter scopes targets, non-matching entries are reported as `SKIPPED (status filter mismatch)`.
- Per-item levels:
  - `UPDATED`: evaluator ran and registry row updated
  - `SKIPPED`: expected skip such as missing `app_path`, path not found, or filter mismatch
  - `ERROR`: unexpected evaluator/update failure
- Summary and exit code:
  - `error=0` => exit code `0`
  - `error>0` => exit code `1`

## Audit

- `app_registry audit` scans every registry entry and validates:
  - `name`
  - `app_path` presence and filesystem existence
  - `entrypoint` (`python_app` için zorunlu; `node_app` için eksikse warning)
  - metadata completeness (`status`, `score`, `verified`)
- Output levels:
  - `OK`
  - `WARNING`
  - `ERROR`
- Exit code:
  - `0` when there is no `ERROR`
  - `1` when at least one `ERROR` exists
