param([Parameter(Mandatory=$true)][string]$RunDir)

$ErrorActionPreference = "Stop"

function Fail($m) { Write-Host "FAIL: $m"; exit 1 }

$meta = Join-Path $RunDir "meta.json"
$status = Join-Path $RunDir "status.json"
$trace = Join-Path $RunDir "trace.txt"

$missing = @()
if (!(Test-Path -LiteralPath $meta)) { $missing += "meta.json" }
if (!(Test-Path -LiteralPath $status)) { $missing += "status.json" }
if (!(Test-Path -LiteralPath $trace)) { $missing += "trace.txt" }

if ($missing.Count -gt 0) { Fail ("run contract missing: " + ($missing -join ", ")) }

$st = Get-Content -LiteralPath $status -Raw | ConvertFrom-Json
if (-not $st.state) { Fail "status.state missing" }
if ($st.state -notin @("started", "failed", "succeeded")) { Fail "status.state invalid" }

Write-Host "OK: run contract present + status sane"
exit 0
