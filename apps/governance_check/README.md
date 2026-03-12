# governance_check

`governance_check` is a deterministic WRG worker that audits repository governance compliance against:

- `company_map.md`
- `AGENT_CONTEXT.md`

Primary role metadata: developer tool catalog.

## Usage

```bash
python -m governance_check.cli check
```

```bash
python -m governance_check.cli check --json-out artifacts/governance_check.json
```

## What It Checks

- Required app structure under `apps/<app_name>/`
- App type/layout aware checks via optional registry metadata (`app_type`, `layout`, `python_package`, `stack`)
- App naming validity
- Registry consistency (`apps/app_registry/data/registry.json`) when present
- Governance status sanity (`candidate`, `active`, `quarantine`, `retired`)
- Classification policy metadata (`class`, `primary_role`, `internal_customer`, `external_product_potential`, `productization_stage`)
- Class/stage consistency and drift signals
- Dual-role promotion guard checks (`dual_role_product` gate conditions)
- Reclassification metadata and history consistency
- Documentation alignment with documented worker names

Type-aware required structure behavior:

- `python_app`: `pyproject.toml` expected; package path is evaluated by `layout` (`src` or `flat`)
- `node_app`: `package.json` is required; python-specific `src/<name>/cli.py` checks are skipped
- `legacy_flat` / `custom` python layouts can downgrade strict structure gaps from `ERROR` to `WARNING`

## Classification Policy Surface

Governance uses these class values:

- `worker`
- `internal_infra`
- `dual_role_product`

And these productization stages:

- `experimental_lab`
- `internal_mvp`
- `internal_operational`
- `product_exploration`
- `product_candidate`
- `market_ready_candidate`

Each app check now contains deterministic findings with stable fields:

- `app`
- `code`
- `message`
- `severity`
- `rule`

## Exit Code

- `0` when report has no `ERROR`
- `1` when one or more `ERROR` entries exist
