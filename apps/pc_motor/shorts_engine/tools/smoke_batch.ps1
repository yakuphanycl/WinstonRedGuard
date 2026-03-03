param()

$ErrorActionPreference = "Stop"

function Die([string]$msg) {
  Write-Error $msg
  exit 1
}

function Assert-True([bool]$cond, [string]$msg) {
  if (-not $cond) { Die $msg }
}

function Assert-ItemKeys([object]$item, [string]$label) {
  $required = @("job_path", "run_id", "result_rc", "cached", "out_path", "error_type")
  foreach ($k in $required) {
    if (-not $item.PSObject.Properties.Name.Contains($k)) {
      Die "$label missing required key: $k"
    }
  }
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== smoke_batch ==" -ForegroundColor Cyan

# 1) Success batch
$okJob = "layer2/examples/min_job.json"
if (!(Test-Path -LiteralPath $okJob)) { Die "missing success job: $okJob" }

$okOut = & python -m layer2.cli.render_batch --jobs-dir layer2/examples --glob min_job.json --max 1 2>&1
$okRc = $LASTEXITCODE
Assert-True ($LASTEXITCODE -eq 0) "expected success batch rc=0"
if ($okRc -ne 0) {
  Write-Host $okOut
  Die "success batch failed rc=$okRc"
}

try {
  $okJson = ($okOut | Out-String) | ConvertFrom-Json
} catch {
  Write-Host $okOut
  Die "success batch output is not valid JSON"
}

$okRunId = $null
if ($okJson.items -and $okJson.items.Count -gt 0) {
  $okRunId = [string]$okJson.items[0].run_id
}
if (-not $okRunId) { Die "success batch missing run_id in items[0]" }
Assert-ItemKeys -item $okJson.items[0] -label "success item"

$okReportPath = "output/_smoke_batch_ok_report.json"
$null = & python -m layer2.cli.render_batch --jobs-dir layer2/examples --glob min_job.json --max 1 --json-out $okReportPath 2>&1
Assert-True (Test-Path -LiteralPath $okReportPath) "missing success report: $okReportPath"
$report = Get-Content -LiteralPath $okReportPath -Raw | ConvertFrom-Json
Assert-True ($report.schema_version -eq "0.1") "report.schema_version missing/changed"
Assert-True (-not [string]::IsNullOrWhiteSpace([string]$report.generated_at)) "report.generated_at missing"
Assert-True (-not [string]::IsNullOrWhiteSpace([string]$report.tool_version)) "report.tool_version missing"

$okStatusPath = Join-Path (Join-Path "runs" $okRunId) "status.json"
if (!(Test-Path -LiteralPath $okStatusPath)) { Die "missing status.json for success run: $okStatusPath" }

$okStatus = Get-Content -LiteralPath $okStatusPath -Raw | ConvertFrom-Json
if (-not [bool]$okStatus.ok) {
  Die "success status.json ok != true ($okStatusPath)"
}
if (-not $okStatus.PSObject.Properties.Name.Contains("schema_version")) {
  Die "success status.json missing schema_version ($okStatusPath)"
}

Write-Host "OK: success batch status validated ($okRunId)" -ForegroundColor Green

# 1.5) skip-existing should emit cached=true
$skipOut = & python -m layer2.cli.render_batch --jobs-dir layer2/examples --glob min_job.json --max 1 --skip-existing 2>&1
$skipRc = $LASTEXITCODE
if ($skipRc -ne 0) {
  Write-Host $skipOut
  Die "skip-existing batch failed rc=$skipRc"
}
try {
  $skipJson = ($skipOut | Out-String) | ConvertFrom-Json
} catch {
  Write-Host $skipOut
  Die "skip-existing output is not valid JSON"
}
if (-not $skipJson.items -or $skipJson.items.Count -lt 1) {
  Die "skip-existing missing items[0]"
}
Assert-ItemKeys -item $skipJson.items[0] -label "skip-existing item"
Assert-True ($skipJson.items[0].cached -eq $true) "expected cached=true for skip-existing"
Assert-True ($skipJson.items[0].result_rc -eq 0) "expected cached success rc=0"
Write-Host "OK: skip-existing cached path validated" -ForegroundColor Green

# 2) Invalid v0.2 job -> validation failure
$tmpDir = "layer2/jobs"
New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
$tmpJob = Join-Path $tmpDir "_smoke_bad_v02.json"
$tmpList = Join-Path $tmpDir "_smoke_bad_v02.list.txt"

$bad = Get-Content -LiteralPath $okJob -Raw | ConvertFrom-Json
$bad.version = "0.2"
$badJson = $bad | ConvertTo-Json -Depth 64
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $tmpJob), $badJson, [System.Text.UTF8Encoding]::new($false))
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $tmpList), $tmpJob + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

$badOut = & python -m layer2.cli.render_batch --jobs-file $tmpList --max 1 2>&1
$badRc = $LASTEXITCODE
if ($badRc -ne 2) {
  Write-Host $badOut
  Remove-Item -LiteralPath $tmpJob -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $tmpList -Force -ErrorAction SilentlyContinue
  Die "invalid batch exit code expected 2, got $badRc"
}

try {
  $badJsonOut = ($badOut | Out-String) | ConvertFrom-Json
} catch {
  Write-Host $badOut
  Remove-Item -LiteralPath $tmpJob -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $tmpList -Force -ErrorAction SilentlyContinue
  Die "invalid batch output is not valid JSON"
}

$badRunId = $null
if ($badJsonOut.items -and $badJsonOut.items.Count -gt 0) {
  $badRunId = [string]$badJsonOut.items[0].run_id
}
if (-not $badRunId) {
  Remove-Item -LiteralPath $tmpJob -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $tmpList -Force -ErrorAction SilentlyContinue
  Die "invalid batch missing run_id in items[0]"
}
Assert-ItemKeys -item $badJsonOut.items[0] -label "invalid item"

$badReportPath = "output/_smoke_batch_bad_report.json"
$null = & python -m layer2.cli.render_batch --jobs-file $tmpList --max 1 --json-out $badReportPath 2>&1
Assert-True (Test-Path -LiteralPath $badReportPath) "missing invalid report: $badReportPath"
$r2 = Get-Content -LiteralPath $badReportPath -Raw | ConvertFrom-Json
Assert-True ($r2.items.Count -ge 1) "expected at least 1 item"
Assert-True ($r2.items[0].error_type -eq "validation_error") "expected error_type=validation_error"
Assert-True ($r2.items[0].result_rc -eq 2) "expected items[0].result_rc=2"

$badStatusPath = Join-Path (Join-Path "runs" $badRunId) "status.json"
if (!(Test-Path -LiteralPath $badStatusPath)) {
  Remove-Item -LiteralPath $tmpJob -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $tmpList -Force -ErrorAction SilentlyContinue
  Die "missing status.json for invalid run: $badStatusPath"
}

$badStatus = Get-Content -LiteralPath $badStatusPath -Raw | ConvertFrom-Json
if ([bool]$badStatus.ok) {
  Remove-Item -LiteralPath $tmpJob -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $tmpList -Force -ErrorAction SilentlyContinue
  Die "invalid status.json ok expected false ($badStatusPath)"
}
if ([string]$badStatus.error_type -ne "validation_error") {
  Remove-Item -LiteralPath $tmpJob -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $tmpList -Force -ErrorAction SilentlyContinue
  Die "invalid status.json error_type expected 'validation_error', got '$($badStatus.error_type)'"
}
if (-not $badStatus.PSObject.Properties.Name.Contains("schema_version")) {
  Remove-Item -LiteralPath $tmpJob -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $tmpList -Force -ErrorAction SilentlyContinue
  Die "invalid status.json missing schema_version ($badStatusPath)"
}

Remove-Item -LiteralPath $tmpJob -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $tmpList -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $okReportPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $badReportPath -Force -ErrorAction SilentlyContinue
Write-Host "OK: invalid batch status validated ($badRunId)" -ForegroundColor Green

Write-Host "OK: smoke_batch passed" -ForegroundColor Green
exit 0
