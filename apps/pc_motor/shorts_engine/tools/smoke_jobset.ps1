param(
  [string]$RepoRoot = (git rev-parse --show-toplevel),
  [string]$Py = "python"
)

$ErrorActionPreference = "Stop"

function Assert-True($cond, $msg) { if (-not $cond) { throw "ASSERT FAIL: $msg" } }
function Assert-Has($obj, [string]$key, [string]$ctx) {
  Assert-True ($obj.PSObject.Properties.Name -contains $key) "$ctx missing key: $key"
}

Write-Host "== smoke_jobset =="
Set-Location $RepoRoot

$tmp = Join-Path $RepoRoot "_junk\smoke_jobset"
New-Item -ItemType Directory -Force $tmp | Out-Null

$jobsDir = Join-Path $RepoRoot "shorts_engine/layer2/examples"
$jobsetPath = Join-Path $tmp "jobset.v0_1.json"
$jobsListPath = Join-Path $tmp "jobs.list.txt"
$batchReport = Join-Path $tmp "batch.report.json"

# 1) build
& $Py -m shorts_engine.layer2.cli.jobset build --jobs-dir $jobsDir --limit 2 --out $jobsetPath | Out-Host
Assert-True ($LASTEXITCODE -eq 0) "jobset build failed"
Assert-True (Test-Path -LiteralPath $jobsetPath) "jobset output missing"
$js = Get-Content -LiteralPath $jobsetPath -Raw | ConvertFrom-Json
Assert-Has $js "schema_version" "jobset"
Assert-Has $js "jobs" "jobset"
Assert-Has $js "jobset_hash" "jobset"
Assert-True ($js.schema_version -eq "0.1") "jobset schema_version expected 0.1"
Assert-True ($js.jobs.Count -ge 1) "jobset should include at least one job"

# 2) inspect
$insp = & $Py -m shorts_engine.layer2.cli.jobset inspect --jobset $jobsetPath
Assert-True ($LASTEXITCODE -eq 0) "jobset inspect failed"
$last = $insp | Select-Object -Last 1
$ij = $last | ConvertFrom-Json
Assert-True ($ij.ok -eq $true) "inspect final JSON ok expected true"

# 3) emit-list
& $Py -m shorts_engine.layer2.cli.jobset emit-list --jobset $jobsetPath --out $jobsListPath | Out-Host
Assert-True ($LASTEXITCODE -eq 0) "jobset emit-list failed"
Assert-True (Test-Path -LiteralPath $jobsListPath) "jobs list missing"
$lines = Get-Content -LiteralPath $jobsListPath | Where-Object { $_ -and $_.Trim() -ne "" }
Assert-True ($lines.Count -eq $js.jobs.Count) "emit-list line count mismatch jobset jobs count"

# 4) render_batch with --jobset
& $Py -m shorts_engine.layer2.cli.render_batch --jobset $jobsetPath --continue-on-error --json-out $batchReport | Out-Host
Assert-True (($LASTEXITCODE -eq 0) -or ($LASTEXITCODE -eq 2)) "render_batch --jobset unexpected exit code"
Assert-True (Test-Path -LiteralPath $batchReport) "batch report missing"
$br = Get-Content -LiteralPath $batchReport -Raw | ConvertFrom-Json
Assert-Has $br "jobset_hash" "batch_report"
Assert-Has $br "jobset_path" "batch_report"
Assert-True ([string]$br.jobset_hash -eq [string]$js.jobset_hash) "batch report jobset_hash mismatch"
Assert-Has $br "timing" "batch_report"
Assert-Has $br.timing "total_duration_ms" "batch_report.timing"
Assert-Has $br.timing "avg_duration_ms" "batch_report.timing"
Assert-Has $br.timing "max_duration_ms" "batch_report.timing"
Assert-Has $br.timing "min_duration_ms" "batch_report.timing"
Assert-Has $br "slowest" "batch_report"
Assert-Has $br.slowest "items" "batch_report.slowest"

Remove-Item -Recurse -Force $tmp
Write-Host "OK: smoke_jobset passed"
