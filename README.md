# WinstonRedGuard

WinstonRedGuard, Python uygulamalarını release öncesinde doğrulayan ve politika kapısı (policy gate) uygulayan bir PowerShell + Python otomasyon altyapısıdır.

<<<<<<< HEAD
## Proje Yapısı
```
WinstonRedGuard/
├── tools/
│   ├── _lib.ps1            # Ortak PowerShell yardımcıları (WRG-* fonksiyonları)
│   └── release_check.ps1   # Release doğrulama pipeline'ı
└── apps/
    └── yyfe_lab/
        ├── pyproject.toml
        ├── src/
        └── tests/
            └── test_policy_gate.py
```
=======
## Release Gate Notes

`tools/release_check.ps1` now includes:

- Combined pytest gate for `apps/app_registry/tests` + `apps/governance_check/tests`
- Governance gate via `python -m governance_check.cli check --json-out artifacts/governance_check.json`
- Company health aggregation artifact: `artifacts/company_health.json` (best-effort aggregate; summarizes policy + governance outputs when present, reports missing source artifacts in `highlights`, and may still be written even when governance gate fails)

## Apps
>>>>>>> 55edd37 (stabilize governance docs source and registry verification)

## Ne Yapar?

- `release_check.ps1` — Wheel build alır, temiz venv'e kurar, smoke import + pytest koşturur.
- `_lib.ps1` — WRG-* ortak yardımcı fonksiyonları.
- `apps/yyfe_lab` — `yyfe` CLI; politika kapısı testleri içerir.

## Gereksinimler

- PowerShell 7+
- Python 3.10+

## Kurulum
```powershell
git clone https://github.com/yakuphanycl/WinstonRedGuard.git
cd WinstonRedGuard
cd apps/yyfe_lab
pip install -e ".[dev]"
```

## Kullanım
```powershell
# Tek uygulama
.\tools\release_check.ps1 -App yyfe_lab

# Tüm uygulamalar
.\tools\release_check.ps1 -All

# Testler
pytest apps/yyfe_lab/tests/ -v
```

## Lisans

MIT
