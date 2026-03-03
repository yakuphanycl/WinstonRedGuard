# Docs Index

Bu klasör, shorts_engine için “sözleşme” dokümanlarını içerir.
Amaç: herkesin aynı gerçeklik testine bakması (doküman ≈ kontrat).

---

## Dependencies (Validation)

Schema validation için önerilen paket:

- `jsonschema` (Draft 2020-12)

---

## 0) En hızlı başlangıç

Release gate (HARD):

```powershell
pwsh tools/release_check.ps1 -Job layer2/examples/min_job.json
```

Smoke verify (insan modu):

```powershell
pwsh tools/verify.ps1
```

CI/automation (JSON):

```powershell
pwsh tools/verify.ps1 -Json
```

---

## 1) Okuma sırası (önerilen)

1. `verification.md`
   - Gate sözleşmesi (HARD), JSON output contract, komut haritası

2. `run_store.md`
   - runs/<run_id>/ kanıt paketi ve artifact mapping

3. `architecture.md`
   - Layer-2 orkestrasyon vs Layer-1 render motoru sınırları

---

## 2) “Bir şey bozuldu” akışı

1) `pwsh tools/verify.ps1 -Json` çalıştır → `ok/rc/artifacts_ok` bak  
2) `runs/<run_id>/render_trace.txt` oku  
3) `runs/<run_id>/render_meta.json` incele  
4) Job kaynak: `layer2/examples/min_job.json`

---

## 3) Sözleşme prensibi

- CLI taşıyıcıdır.
- Core mantıktır.
- Verify kanıttır.
- Docs sözleşmedir.
