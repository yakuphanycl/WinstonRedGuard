# Run Store Contract (Layer-2)

Bu doküman, Layer-2 render komutunun ürettiği *run artifacts* yapısını ve sözleşmesini tanımlar.
Amaç: her render çalışmasını izlenebilir, tekrarlanabilir ve debug edilebilir hale getirmek.

> Kapsam: Layer-2 (`python -m layer2.cli.render_job`) run store davranışı.

---

## Compat Bridge: CLI Finalize (Legacy → runs/<run_id>/)

Bazı sürümlerde kanıt dosyaları (meta/trace/layer1 job) önce `output/` altında üretilir.
Bu durumda Layer-2 CLI, başarılı render sonrasında **best-effort** bir “finalize” adımıyla
bu legacy kanıtları `runs/<run_id>/` içine taşır (kopyalar).

Amaç:

- Run store geçişini kırmadan güçlendirmek
- `runs/<run_id>/` klasörünü gerçek bir “kanıt paketi” haline getirmek

Bu finalize adımı:

- Render başarısını bozmaz (kopyalama hatası render'ı fail etmez)
- Var olan dosyaların üstüne yazmaz (mevcutsa dokunmaz)

---

## Legacy Artifacts (output/ altında)

Bazı workspace'lerde “son koşu” kanıtları `output/` altında tutulur:

- `output/_last_render_meta.json`
- `output/_last_render_trace.txt`
- `output/_captured_layer1_job.json`

Bu dosyalar **runs/** moduna geçişte kaynak olarak kullanılabilir.

### Mapping (önerilen)

Legacy → runs/<run_id>/:

- `output/_last_render_meta.json`  → `runs/<run_id>/render_meta.json`
- `output/_last_render_trace.txt` → `runs/<run_id>/render_trace.txt`
- `output/_captured_layer1_job.json` → `runs/<run_id>/layer1_job.json`

Not:

- Bu mapping şu an otomatik olmayabilir.
- verify script’i varsayılan olarak “read-only” kalır (kanıtlar, tamir etmez).
- Run store tamamlandığında meta/trace doğrudan run_dir içine yazılmalıdır.

---

## Verify ile İlişki

`tools/verify.ps1` doğrulama script’i, run store’un minimum “kanıt” katmanını kontrol eder:

- Render komutu çalışıyor mu?
- Çıktı mp4 gerçekten üretiliyor mu? (0 byte değil)

İnsan modu:

```powershell
pwsh tools/verify.ps1
```

CI modu (JSON):

```powershell
pwsh tools/verify.ps1 -Json | ConvertFrom-Json
```

Not:

- Verify script’i artık JSON modunda `run_id` ve `cached` alanlarını best-effort parse eder.
- `runs/<run_id>/` varsa best-effort artifact alanlarını da üretir:
  `run_dir`, `meta_path`, `trace_path`, `artifacts_ok`.
- `artifacts_ok=true` olması için run_dir içinde en az bir meta/trace ve mp4 kanıtı bulunmalıdır.

Pratik durum (hibrit mod):

- Bazı workspace'lerde `runs/<run_id>/` klasörü açılır ama `render_meta.json` / `render_trace.txt`
  henüz üretilmez.
- Bu durumda verify:
  - `run_dir` dolu
  - `meta_path/trace_path` null
  - `artifacts_ok=false`

Bu bir "fail" olmak zorunda değildir; run_store tamamlanınca gate sertleştirilebilir.

---

## Terminoloji

- **Run**: Tek bir render çalışması (job input + deterministik config + çıktı üretimi).
- **run_id**: Run'ın benzersiz kimliği (genellikle kısa hex).
- **cached**: Aynı job hash / aynı parametreler ile daha önce üretilen çıktı tekrar kullanıldı mı?
- **artifacts**: Run'a ait kanıt dosyaları (meta, trace, job kopyaları, çıktı vb.)

---

## Dizin Yapısı

Run artifacts aşağıdaki iki şekilde tutulabilir:

### A) Legacy (output root)

`shorts_engine/output/` altında:

- `output/test.mp4`
- `output/_last_render_meta.json`
- `output/_last_render_trace.txt`
- `output/_captured_layer1_job.json` (varsa)

Bu yaklaşım basittir ancak eski run'lar üzerine yazabilir.

### B) Preferred (runs/)

`shorts_engine/runs/<run_id>/` altında:

```
runs/
  <run_id>/
    layer2_job.json
    layer1_job.json
    render_meta.json
    render_trace.txt
    output.mp4
```

Bu yaklaşım her run'ı ayrı bir klasörde saklar ve geçmişi korur.

---

## Artifact Dosyaları

### 1) layer2_job.json

Layer-2'ye verilen job'un normalize edilmiş kopyası.

Zorunlu alanlar (özet):

- `version`
- `output.path`
- `video.resolution`
- `video.fps`
- `video.duration_sec`
- `subtitles.items[]`

### 2) layer1_job.json

Layer-1 renderer'a gönderilen adapter job kopyası.

Amaç:

- Layer-2 -> Layer-1 mapping'i kanıtlamak
- Layer-1 debug'ında aynı input ile yeniden koşabilmek

### 3) render_meta.json

Run'a ait makine-okunur metaveri.

Önerilen alanlar:

- `run_id` (string)
- `created_at` (ISO-8601)
- `cached` (bool)
- `rc` (int)
- `output_path` (string, relative/absolute)
- `duration_sec` (float)
- `tool_versions` (dict; python, ffmpeg, etc.)

### 4) render_trace.txt

Run'ın insan-okunur izi.

İçerik örnekleri:

- çağrılan komutlar
- stdout/stderr özetleri
- hata stacktrace (varsa)

### 5) output.mp4 / output path

Asıl render çıktısı.

Minimum sözleşme:

- Dosya mevcut olmalı
- Boyut > 0 olmalı
- Timestamp çalışma zamanına yakın olmalı

---

## CLI Çıktı Sözleşmesi

`python -m layer2.cli.render_job --job <job.json>` çıktısında en az bir satır *sonuç* bilgisi olmalı:

- `RESULT ok rc=0 out=<path> run_id=<id> cached=True|False`

Hata durumunda:

- `RESULT fail rc=<nonzero> ...` benzeri bir satır
- veya stderr'de anlamlı mesaj + exit code

---

## Cache Davranışı

Cache, aynı run'ın tekrar üretimini engelleyerek zaman kazandırır.

Minimum sözleşme:

- `cached=True` ise:
  - çıktı yolunda dosya yine var olmalı
  - `render_meta.json` içinde cached bayrağı açık olmalı
- `cached=False` ise:
  - render gerçekten çalışmış olmalı
  - meta/trace güncellenmiş olmalı

---

## Debug Golden Path

Bir run'ı debug ederken şu sırayla ilerle:

1) `render_meta.json` -> `rc`, `cached`, `output_path`
2) `render_trace.txt` -> hata veya komut izleri
3) `layer2_job.json` -> job normalize doğru mu?
4) `layer1_job.json` -> adapter doğru mu?
5) çıktı mp4 -> mevcut mu, boyut>0 mı?

---

## Notlar / Tasarım İlkeleri

- Run store, CLI'nin davranış sözleşmesinin parçasıdır.
- "Sessiz varsayılan, konuşkan opsiyon": normalde kısa sonuç, `--verbose/--json` ile daha fazla detay.
- `runs/` yaklaşımı tercih edilir; legacy output dosyaları sadece "son run" kolaylığı sağlar.
