# Verification (2026-02-20)

Bu doküman, Layer-2 pipeline'ın çalıştığını gösteren minimum doğrulama adımlarını içerir.
Bu doküman aynı zamanda release gate'in (hard policy) sözleşmesidir.

---

## Gate Policy (artifacts_ok) — CURRENT: HARD

`tools/verify.ps1 -Json` çıktısındaki `artifacts_ok` alanı, run store geçişinin “tamamlanma”
durumunu gösterir.

Release gate (`tools/release_check.ps1`) hard policy ile çalışır:

- `artifacts_ok=true` → **OK**
- `artifacts_ok=false` → **FAIL** (meta/trace eksik)
- `artifacts_ok=null` → **FAIL** (runs/<run_id>/ bekleniyor ama tespit edilemedi)

Bu workspace’te normal koşul:

- CLI finalize (legacy → runs) tamamlandığı için `artifacts_ok=true` beklenir.

Not:

- Bu workspace’te CLI finalize (legacy → runs) tamamlandığı için normal koşul `artifacts_ok=true`’dur.
- Hard policy aktifken `artifacts_ok=false|null` çıktısı, release’i durduracak seviyede bir regressionsinyalidir.

---

## (Deprecated) Soft Policy Notu

Geçmişte `artifacts_ok=false` durumunda sadece uyarı (soft policy) uygulanıyordu.
Run store kanıt paketi artık zorunlu olduğu için soft policy devre dışıdır.

---

## Release Gate Sözleşmesi (release_check.ps1)

`tools/release_check.ps1` bir “release kapısıdır”. Başarılı geçtiğinde şunlar garanti edilir:

1) **Compile OK**
   - Layer-2 CLI ve core modülleri `py_compile` ile syntax/import seviyesinde sağlamdır.

2) **Runtime Verify OK**
   - `tools/verify.ps1 -Json` çalışır ve `ok=true` döner.
   - `layer2/examples/min_job.json` ile smoke render yapılabilir.
   - `output/test.mp4` oluşur ve boyutu sıfırdan büyüktür.

3) **Docs OK**
   - `docs/run_store.md` ve `docs/verification.md` mevcut.

Komut (shorts_engine köküne göre job path):

```powershell
pwsh tools/release_check.ps1 -Job layer2/examples/min_job.json
```

---

## Release Check (Gate) Kullanımı

Release gate script'i `shorts_engine` köküne `cd` ettiği için `-Job` parametresi
**shorts_engine root'a göre relatif** verilmelidir.

Doğru kullanım:

```powershell
pwsh tools/release_check.ps1 -Job layer2/examples/min_job.json
```

Yanlış kullanım örneği (job not found üretir):

```powershell
pwsh tools/release_check.ps1 -Job shorts_engine/layer2/examples/min_job.json
```

Amaç:

- Gate aynı kök dizinde deterministik çalışsın
- CI ve lokal kullanımda path sürprizi olmasın

## Working Tree Hygiene (Release öncesi temizlik)

Doğrulama ve release süreçlerinde hedef: **clean working tree**.

Önerilen kontrol:

```powershell
git status -sb
```

Eğer sadece iki dosyada (ör. `render_job.py`, `validate_job.py`) lokal deneme değişiklikleri kaldıysa:

```powershell
git restore --worktree --staged `
  shorts_engine/layer2/cli/render_job.py `
  shorts_engine/layer2/core/validate_job.py
```

Bu sayede dokümantasyon/CI kontrolü ile yerel denemeler birbirine karışmaz.

## Runtime Path

- Bu workspace'te `shorts_engine/layer2/core/render_impl.py` **yoktur**.
- Aktif modül: `shorts_engine/layer2/core/render.py`

## 1) Compile Checks

Komut (shorts_engine içinde):

```powershell
python -m py_compile `
  .\layer2\cli\render_job.py `
  .\layer2\core\render.py `
  .\layer2\core\validate_job.py
```

Beklenen:

- Komut başarıyla biter (exit code 0)

---

## Automated Verification (Önerilen)

Aynı doğrulama adımlarını tek komutla çalıştırmak için:

```powershell
pwsh tools/verify.ps1
```

CI/parsing için JSON çıktı modu:

```powershell
pwsh tools/verify.ps1 -Json
```

Bu script:

- py_compile kontrollerini yapar
- min_job.json ile smoke render çalıştırır
- output mp4 var mı / boş mu kontrol eder
- `-Json` ile machine-readable sonuç üretir (`ok`, `rc`, `step`, `output_*`)

Başarılı durumda yeşil **VERIFICATION OK** mesajı basar.

Başarılı örnek JSON alanları:

- `ok`, `rc`
- `output_path`, `output_bytes`, `output_mtime`
- `compile_rc`, `render_rc`

---

## JSON Output Contract (verify.ps1)

`-Json` bayrağı ile çalışan doğrulama script’i **makine-okunur ve stabil** bir JSON üretir.
Bu çıktı CI, release gate veya diğer otomasyonlar tarafından parse edilmek üzere tasarlanmıştır.

### Ortak Alanlar

Her durumda (success veya failure) şu alanlar bulunur:

- `ok` (bool)  
  - `true` → doğrulama başarılı  
  - `false` → doğrulama başarısız

- `rc` (int)  
  - Process exit code (0 = başarı)

- `root` (string)  
  - shorts_engine çalışma dizini

- `job` (string)  
  - Kullanılan job dosyası yolu

---

### Başarılı Çıktı (ok = true)

Ek alanlar:

- `output_path` (string)
- `output_bytes` (int)
- `output_mtime` (ISO-8601 string)
- `compile_rc` (int)
- `render_rc` (int)
- `run_id` (string | null)
  - Render CLI çıktısındaki `run_id` (best-effort parse). Bulunamazsa `null`.
- `cached` (bool | null)
  - Render CLI çıktısındaki `cached` (best-effort parse). Bulunamazsa `null`.

Best-effort artifacts alanları (yalnızca `runs/<run_id>/` mevcutsa dolar):

- `run_dir` (string | null)
- `meta_path` (string | null)
- `trace_path` (string | null)
- `artifacts_ok` (bool | null)
  - `true` → run_dir içinde en az bir meta/trace var ve mp4 kanıtı mevcut
  - `false` → run_dir var ama beklenen kanıt dosyaları eksik
  - `null` → run_dir yok (runs kullanılmıyor olabilir)

Örnek:

```json
{
  "ok": true,
  "rc": 0,
  "root": "C:\\dev\\pc_motor\\shorts_engine",
  "job": "layer2/examples/min_job.json",
  "output_path": "output\\test.mp4",
  "output_bytes": 28071,
  "output_mtime": "2026-02-20T23:18:14.0000000+03:00",
  "compile_rc": 0,
  "render_rc": 0,
  "run_id": "9e81ee3631c8",
  "cached": true,
  "run_dir": "C:\\dev\\pc_motor\\shorts_engine\\runs\\9e81ee3631c8",
  "meta_path": null,
  "trace_path": null,
  "artifacts_ok": null
}
```

---

### Hatalı Çıktı (ok = false)

Ek alanlar:

- `step` (string, opsiyonel)
  - `"py_compile"` veya `"render_job"`
- `error` veya `output` (string)

Örnek:

```json
{
  "ok": false,
  "rc": 1,
  "step": "render_job",
  "root": "C:\\dev\\pc_motor\\shorts_engine",
  "job": "layer2/examples/min_job.json",
  "output": "Traceback (most recent call last): ..."
}
```

---

## CI / Release Gate Kullanımı

Önerilen kontrol:

```powershell
$r = pwsh tools/verify.ps1 -Json | ConvertFrom-Json
if (-not $r.ok) { exit 1 }
```

Bu yaklaşım:

- string parsing gerektirmez
- stdout formatı değişse bile bozulmaz
- release sürecini deterministik hale getirir

## 2) Smoke Render

Komut (shorts_engine içinde):

```powershell
python -m layer2.cli.render_job --job .\layer2\examples\min_job.json
```

Örnek başarılı sonuç:

- `RESULT ok rc=0 out=output\test.mp4 run_id=9e81ee3631c8 cached=True`

## 3) Output Check

- `shorts_engine/output/test.mp4` mevcut
- Boyut > 0
- Timestamp çalıştırma anında güncel

## 4) Change Policy

Bu doğrulama adımında aşağıdaki dosyalar değiştirilmemiştir:

- `shorts_engine/layer2/cli/render_job.py`
- `shorts_engine/layer2/core/validate_job.py`
