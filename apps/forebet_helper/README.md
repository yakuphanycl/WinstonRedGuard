# forebet-helper

Kişisel kullanım için küçük bir Python CLI aracıdır. Tek bir Forebet maç sayfasını URL veya kayıtlı HTML dosyasından okuyup yapılandırılmış JSON çıktı üretir.

Parse edilemeyen alanlar uydurulmaz; `null` kalır ve `missing_fields` içinde görünmeye devam eder.

## Install

```bash
python -m pip install -e ".[dev]"
```

## Test

```bash
python -m pytest -q
```

`pytest.ini` Windows üzerinde problem çıkaran geçici dizin izin hatasını önlemek için project-local `--basetemp=.\.pytest_tmp` kullanır.

## Example usage

Yerel HTML snapshot ile:

```bash
python -m forebet_helper --html-file ".\Lille vs Aston Villa Prediction, Stats, H2H - 12 Mar 2026.html" --out .\result.json
```

İsterseniz URL ile de çalıştırabilirsiniz:

```bash
python -m forebet_helper "https://www.forebet.com/en/football/matches/example-match"
```

## Notes

- Bu araç personal-use helper tooling içindir.
- Çıktı tek bir maç için özet sinyal JSON'ıdır.
- Önemli alanlar arasında `prediction_1x2`, `correct_score`, `btts`, `over_under_2_5`, `ht_ft`, `prob_home`, `prob_draw`, `prob_away` ve `missing_fields` bulunur.
