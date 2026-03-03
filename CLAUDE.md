# WinstonRedGuard (WRG) — Claude Code Project Instructions

## Repo amacı
- Bu repo tek monorepo: WinstonRedGuard.
- Alt projeler `apps/<app_name>/` altında.
- `tools/` PowerShell otomasyonları ve release gate scriptleri içerir.
- Repo içinde "yakup" ismi geçmeyecek (naming/brand tercihi).

## Teknoloji / Tooling
- OS: Windows (PowerShell 7+)
- Python: 3.12 (tercih)
- Paketleme: `python -m build --wheel`
- Test: `pytest`
- Stil: basit ve deterministik; “golden path” önce.

## Monorepo yapısı
- `apps/<app>/pyproject.toml` her uygulamanın kendi paketidir.
- Her app kendi `src/<pkg>/` yapısını kullanır.
- `tools/release_check.ps1` tüm app’leri dolaşıp wheel + smoke + pytest çalıştırır.

## Golden Path (Release Gate)
Repo kökünde:
- Tüm uygulamalar:
  - `pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\release_check.ps1 -All`
- Tek uygulama:
  - `pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\release_check.ps1 -App <app_name>`

Beklenenler:
- Exit code 0 => PASS
- Uygulama import/smoke testleri **wheel üzerinden** geçmeli (repo source shadowing yok).
- Pytest, mümkünse temp dizinde ve venv python ile çalışır.

## Kod/PR kuralları (kısa)
- CLI–CORE–DATA katman ayrımı korunur.
- Regex ile “yamayla” düzeltmek yerine doğru yapı: küçük, izole refactor.
- “Sessiz varsayılan, konuşkan opsiyon”: verbose/debug/json opt-in.
- Çıktı sözleşmesi (stdout/json/exit code) bozulmaz.
- Test eklerken: önce crash yok + exit code; sonra detay.

## PowerShell notları
- UTF-8 hijyeni:
  - `chcp 65001`
  - `$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)`

## Sık komutlar
- Wheel build (app içinde):
  - `py -3 -m build --wheel`
- Pytest (app tests):
  - `py -3 -m pytest -q`
- Import smoke (örnek):
  - `py -3 -c "import <pkg>; print('ok')"`

## Claude Code için beklenti
- Değişiklik yapmadan önce:
  - hedef dosyaları listele
  - “golden path”i kırmayacak şekilde minimal patch öner
- Her öneride: komutlar PowerShell formatında ve kopyala-yapıştır hazır.
