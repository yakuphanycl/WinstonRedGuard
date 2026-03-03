# WinstonRedGuard

WinstonRedGuard, Python uygulamalarını release öncesinde doğrulayan ve politika kapısı (policy gate) uygulayan bir PowerShell + Python otomasyon altyapısıdır.

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

## Apps

<!-- WRG:APPS_START -->
| App | Tier |
|-----|------|
| pc_motor | legacy |
| shorts_engine | workspace |
| workspace_inspector | release |
| yyfe_lab | release |
<!-- WRG:APPS_END -->

