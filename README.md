# WinstonRedGuard

WinstonRedGuard, Python uygulamalarını release öncesinde doğrulayan ve politika kapısı (policy gate) uygulayan bir PowerShell + Python otomasyon altyapısıdır.

## Release Gate Notes

`tools/release_check.ps1` now includes:

- Combined pytest gate for `apps/app_registry/tests` + `apps/governance_check/tests`
- Governance gate via `python -m governance_check.cli check --json-out artifacts/governance_check.json`
- Company health aggregation artifact: `artifacts/company_health.json` (best-effort aggregate; summarizes policy + governance outputs when present, reports missing source artifacts in `highlights`, and may still be written even when governance gate fails)

## Apps

<!-- WRG:APPS_START -->
| App | Tier |
|-----|------|
| pc_motor | legacy |
| shorts_engine | workspace |
| workspace_inspector | release |
| yyfe_lab | release |
<!-- WRG:APPS_END -->

