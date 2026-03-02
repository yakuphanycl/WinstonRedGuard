\# workspace-inspector



A small CLI tool that scans a workspace (folder) and generates a clear summary

of files by type and total size. Read-only, safe, and fast.



> A simple tool to quickly understand what's inside a folder.



---



\## 🇹🇷 Türkçe Açıklama



\*\*workspace-inspector\*\*, bir klasörü (çalışma alanını) tarayan ve içindeki

dosyalar hakkında net bir özet çıkaran küçük bir komut satırı (CLI) aracıdır.



Dosyalara \*\*asla dokunmaz\*\*, silmez veya taşımaz.  

Sadece okur ve raporlar.



---



\## What it does / Ne yapar?

\- Scans a given directory  

\- Counts files by category (audio, video, images, other)  

\- Calculates total size  

\- Prints a simple summary report  



\*\*Türkçe:\*\*

\- Verilen klasörü tarar  

\- Dosyaları türlerine göre sayar  

\- Toplam boyutu hesaplar  

\- Basit bir özet rapor üretir  



---



\## What it does NOT do / Ne yapmaz?

\- Does not modify files  

\- Does not delete or move anything  

\- No network access  

\- No background services  



\*\*Türkçe:\*\*

\- Dosyaları değiştirmez  

\- Silme veya taşıma yapmaz  

\- İnternete bağlanmaz  

\- Arka planda çalışan servis yoktur  



---



\## Who is this for? / Kimler için?

\- Developers  

\- Content creators  

\- Anyone with messy folders  



\*\*Türkçe:\*\*

\- Geliştiriciler  

\- İçerik üreticileri  

\- Klasörleri dağınık olan herkes  



---



\## Usage (V0) / Kullanım



```bash

workspace-inspector ./my\_workspace

```

---

## Behavior Contract

- Exit codes: `0` on success, non-zero on error.
- Default ignores: `.git`, `node_modules`, `.venv`, `venv`, `__pycache__`.
- `--ignore` adds extra ignored names (comma-separated).
- `--json <path>` writes a machine-readable UTF-8 JSON report to that file.
- Console output remains a human-readable summary.
- For sandbox/restricted-shell Git notes, see `DEV_ENV.md`.


