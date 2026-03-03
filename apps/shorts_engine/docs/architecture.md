# Architecture Overview (Layer-2 + Layer-1)

Bu doküman, shorts_engine'in sorumluluk sınırlarını ve veri akışını tanımlar.

Amaç:

- Katmanlar arası bağımlılığı netleştirmek
- Release gate’in neden bu adımları kontrol ettiğini açıklamak
- Gelecekte refactor yapılırken sözleşmeleri korumak

---

## Katmanlar

### Layer-2 (Orkestrasyon Katmanı)

Sorumluluklar:

- Job validation (`validate_job.py`)
- CLI giriş noktası (`cli/render_job.py`)
- Run store organizasyonu
- Layer-1’e adapter üretimi

Layer-2 şunları yapmaz:

- Gerçek video render etmez
- FFmpeg ile doğrudan konuşmaz

---

### Layer-1 (Render Motoru)

Sorumluluklar:

- Görsel üretim
- Altyazı üretimi
- Ses + video birleşimi
- MP4 çıktısı üretimi

Layer-1, iş mantığını bilmez:

- Hook nedir?
- Pattern break nedir?
- Retention mantığı nedir?

Layer-1 yalnızca verilen job'u üretir.

---

## Veri Akışı

```
User CLI
   ↓
layer2.cli.render_job
   ↓
validate_job()
   ↓
Layer-1 adapter job
   ↓
Layer-1 render
   ↓
output/test.mp4
```

Release gate şu noktaları doğrular:

1) CLI compile edilebilir mi?
2) Validation çalışıyor mu?
3) Layer-1 render gerçekten mp4 üretiyor mu?
4) Çıktı boş değil mi?

---

## Verify ve Run Store İlişkisi

verify.ps1:

- Runtime smoke test yapar
- CLI çıktısını parse eder
- run_id ve cached bilgilerini JSON’a dahil eder

Bu alanlar ileride:

- runs/<run_id>/ meta doğrulaması
- cache stratejisi analizi
- performans metrikleri

için temel anahtar olacaktır.

---

## Sözleşme Seviyeleri

Bu projede üç sözleşme vardır:

1) Compile Contract
   - py_compile başarısızsa release yok

2) Runtime Contract
   - verify.ps1 -Json → ok=true

3) Documentation Contract
   - run_store.md + verification.md mevcut

Release_check bu üç katmanı birlikte garanti eder.

---

## Tasarım İlkesi

- CLI taşıyıcıdır.
- Core mantıktır.
- Verify kanıttır.
- Docs sözleşmedir.

Bu ayrım korunursa proje kontrollü evrimleşir.

---

## Contract-First Not

V0.6 ile operasyonel sözleşmelerin merkezi:

- `docs/contracts.md`

Yeni katkılar şu sırayı korumalıdır:

1) `status.json` ve batch report alanları ile uyum
2) Exit code sözleşmesini bozmama
3) `tools/smoke_batch.ps1` ve `tools/release_check.ps1` gate’lerini geçme
