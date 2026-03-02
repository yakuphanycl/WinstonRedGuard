$ErrorActionPreference = "Stop"

Write-Host "== YYFE SMOKE ==" -ForegroundColor Cyan
Write-Host "PWD: $(Get-Location)" -ForegroundColor DarkGray

New-Item -Force -ItemType Directory .\output | Out-Null

Write-Host "`n== GOLDEN ==" -ForegroundColor Cyan
python -m yyfe golden

Write-Host "`n== PLAN ==" -ForegroundColor Cyan
python -m yyfe plan --out .\output\plan.json

Write-Host "`n== VALIDATE ==" -ForegroundColor Cyan
python -m yyfe validate --plan .\output\plan.json

Write-Host "`n== APPLY ==" -ForegroundColor Cyan
python -m yyfe apply --plan .\output\plan.json

Write-Host "`nSMOKE_OK" -ForegroundColor Green
