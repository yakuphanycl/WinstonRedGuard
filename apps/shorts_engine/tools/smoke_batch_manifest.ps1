param(
  [string]$Batch = ".\layer2\examples\batches\smoke_batch_001.json"
)

$ErrorActionPreference = "Stop"

function Die([string]$msg) {
  Write-Host "FAIL: $msg" -ForegroundColor Red
  exit 1
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (!(Test-Path -LiteralPath $Batch)) { Die "missing batch file: $Batch" }

python -m py_compile .\layer2\cli\render_batch.py
if ($LASTEXITCODE -ne 0) { Die "py_compile failed: render_batch.py" }

# Current CLI accepts --jobs-file; JSON manifest is supported.
python -m layer2.cli.render_batch --jobs-file $Batch
$code = $LASTEXITCODE

if ($code -eq 1) { Die "batch crashed (exit=1)" }

# Resolve report path from batch manifest when present.
$report = ".\output\batch_report.json"
try {
  $manifest = Get-Content -LiteralPath $Batch -Raw | ConvertFrom-Json
  if ($manifest -and $manifest.report_out -and [string]::IsNullOrWhiteSpace([string]$manifest.report_out) -eq $false) {
    $report = [string]$manifest.report_out
  }
} catch {
}

if (![System.IO.Path]::IsPathRooted($report)) {
  $report = Join-Path $root $report
}

if (!(Test-Path -LiteralPath $report)) { Die "report not found: $report" }

$json = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json

if (-not $json.meta) { Die "report missing meta" }
if (-not $json.summary) { Die "report missing summary" }
if (-not $json.fail_by_type) { Die "report missing fail_by_type" }
if (-not $json.sample_failures) { Die "report missing sample_failures" }
if (-not $json.items) { Die "report missing items" }

Write-Host "OK: batch ran (exit=$code), report exists: $report" -ForegroundColor Green
exit 0

