# shorts_engine

## Docs

- Docs index (başlangıç noktası): `docs/README.md`
- Run artifacts sözleşmesi: `docs/run_store.md`
- Doğrulama / gate sözleşmesi: `docs/verification.md`
- Mimari akış ve katmanlar: `docs/architecture.md`

---

## Release Gate (Tek komut)

Release öncesi “kapı” kontrolü:

```powershell
pwsh tools/release_check.ps1 -Job layer2/examples/min_job.json
```

Bu komut:

- py_compile kontrolü yapar
- verify gate çalıştırır (JSON parse)
- docs varlığını kontrol eder

---

## Quick Start (En hızlı doğrulama)

Layer-2 pipeline’ın bu workspace’te çalıştığını **tek komutla** doğrulamak için:

```powershell
pwsh tools/verify.ps1
```

Başarılı durumda:

- `✔ VERIFICATION OK`
- `output/test.mp4` üretilmiş olur (boyut > 0)

---

## CLI Smoke Render

Doğrudan CLI ile denemek istersen:

```powershell
python -m layer2.cli.render_job --job layer2/examples/min_job.json
```

Beklenen çıktı örneği:

- `RESULT ok rc=0 out=output\test.mp4 run_id=<id> cached=True|False`

---

## How to run smoke

```powershell
pwsh -File tools/smoke_batch.ps1
```

Bu komut iki temel kontrol yapar:

- Geçerli örnek job ile batch success + `status.json` doğrulaması
- Geçersiz (`version=0.2`) job ile validation-failure ve exit code doğrulaması

---

## Run store concept

Run store, her çalıştırmayı `runs/<run_id>/` altında saklayan sözleşmedir.

- `meta.json`: render meta verileri
- `status.json`: makine-okunur durum/sonuç (`schema_version`, `ok`, `error_type`, `duration_ms`)
- `stdout.log`, `trace.txt`: tanılama
- `*.mp4`: render çıktısı

Batch çalıştırmaları ayrıca:

- `runs/_batch/<batch_run_id>/batch_status.json`

olarak raporlanır.

---

## Troubleshooting (Sık görülenler)

### 1) “render_impl.py nerede?”

Bu workspace’te `layer2/core/render_impl.py` yoktur.
Aktif modül:

- `layer2/core/render.py`

### 2) “Repo dirty kaldı, release gate karışıyor”

Release/verify öncesi çalışma ağacını temizlemek için:

```powershell
git status -sb
git restore --worktree --staged ^
  shorts_engine/layer2/cli/render_job.py ^
  shorts_engine/layer2/core/validate_job.py
```

### 3) Output var ama mp4 boş/0 byte

Bu genelde render’ın erken exit ettiği veya output path’in yanlış olduğu anlamına gelir.
Şunları kontrol et:

- `output/_last_render_trace.txt`
- `docs/verification.md` adımlarını
