param(
  [string]$RepoRoot = (git rev-parse --show-toplevel),
  [string]$Py = "python"
)

$ErrorActionPreference = "Stop"

function Assert-True($cond, $msg) { if (-not $cond) { throw "ASSERT FAIL: $msg" } }

function Assert-HasKeys($obj, [string[]]$keys, [string]$label) {
  foreach ($k in $keys) {
    Assert-True ($obj.PSObject.Properties.Name -contains $k) "$label missing key: $k"
  }
}

Write-Host "== smoke_batch_resume =="
Set-Location $RepoRoot

$tmp = Join-Path $RepoRoot "_junk\smoke_batch_resume"
$jobsDir = Join-Path $tmp "jobs"
New-Item -ItemType Directory -Force $jobsDir | Out-Null

$baseJobPath = Join-Path $RepoRoot "shorts_engine/layer2/examples/min_job.json"
Assert-True (Test-Path -LiteralPath $baseJobPath) "missing base job: $baseJobPath"
$base = Get-Content -LiteralPath $baseJobPath -Raw | ConvertFrom-Json

$ok1 = $base | ConvertTo-Json -Depth 64 | ConvertFrom-Json
$ok1.version = "0.5"
if (-not $ok1.output) { $ok1 | Add-Member -NotePropertyName output -NotePropertyValue (@{}) -Force }
$ok1.output.path = "output/smoke_batch_resume_ok1.mp4"

$ok2 = $base | ConvertTo-Json -Depth 64 | ConvertFrom-Json
$ok2.version = "0.5"
if (-not $ok2.output) { $ok2 | Add-Member -NotePropertyName output -NotePropertyValue (@{}) -Force }
$ok2.output.path = "output/smoke_batch_resume_ok2.mp4"

$bad = $base | ConvertTo-Json -Depth 64 | ConvertFrom-Json
$bad.version = "0.2"
if (-not $bad.output) { $bad | Add-Member -NotePropertyName output -NotePropertyValue (@{}) -Force }
$bad.output.path = "output/smoke_batch_resume_bad.mp4"

$job1 = Join-Path $jobsDir "job_ok_1.json"
$job2 = Join-Path $jobsDir "job_bad.json"
$job3 = Join-Path $jobsDir "job_ok_2.json"
$ok1 | ConvertTo-Json -Depth 64 | Set-Content -LiteralPath $job1 -Encoding utf8
$bad | ConvertTo-Json -Depth 64 | Set-Content -LiteralPath $job2 -Encoding utf8
$ok2 | ConvertTo-Json -Depth 64 | Set-Content -LiteralPath $job3 -Encoding utf8

$jobsFile = Join-Path $tmp "jobs.list.txt"
@($job1, $job2, $job3) | Set-Content -LiteralPath $jobsFile -Encoding utf8

$r1 = Join-Path $tmp "report_default.json"
$r2 = Join-Path $tmp "report_continue.json"
$r3 = Join-Path $tmp "report_retry_failed.json"

# 1) Default behavior: stop on first failure
$out1 = & $Py -m shorts_engine.layer2.cli.render_batch --jobs-file $jobsFile --json-out $r1
$rc1 = $LASTEXITCODE
Assert-True ($rc1 -eq 2) "default batch expected rc=2, got $rc1"
Assert-True (Test-Path -LiteralPath $r1) "missing report_default.json"
$j1 = Get-Content -LiteralPath $r1 -Raw | ConvertFrom-Json
Assert-True ($j1.stopped_early -eq $true) "default batch should stop early"
Assert-True ([int]$j1.fail_count -ge 1) "default fail_count expected >=1"
Assert-True ($j1.continue_on_error -eq $false) "default continue_on_error expected false"
Assert-True ($j1.items.Count -lt 3) "default mode should not process all jobs"

# 2) Continue-on-error: process all jobs
$out2 = & $Py -m shorts_engine.layer2.cli.render_batch --jobs-file $jobsFile --continue-on-error --json-out $r2
$rc2 = $LASTEXITCODE
Assert-True ($rc2 -eq 2) "continue-on-error batch expected rc=2, got $rc2"
Assert-True (Test-Path -LiteralPath $r2) "missing report_continue.json"
$j2 = Get-Content -LiteralPath $r2 -Raw | ConvertFrom-Json
Assert-True ($j2.stopped_early -eq $false) "continue-on-error should not stop early"
Assert-True (([int]$j2.ok_count + [int]$j2.summary.skipped) -eq 2) "continue-on-error success count (ok+skipped) expected 2"
Assert-True ([int]$j2.fail_count -eq 1) "continue-on-error fail_count expected 1"
Assert-True ($j2.items.Count -eq 3) "continue-on-error should process all jobs"

# 3) Retry only failed from previous report (after fixing invalid job)
$fixed = Get-Content -LiteralPath $job2 -Raw | ConvertFrom-Json
$fixed.version = "0.5"
$fixed | ConvertTo-Json -Depth 64 | Set-Content -LiteralPath $job2 -Encoding utf8

$out3 = & $Py -m shorts_engine.layer2.cli.render_batch --only-failed-from $r2 --json-out $r3
$rc3 = $LASTEXITCODE
Assert-True ($rc3 -eq 0) "retry failed expected rc=0, got $rc3"
Assert-True (Test-Path -LiteralPath $r3) "missing report_retry_failed.json"
$j3 = Get-Content -LiteralPath $r3 -Raw | ConvertFrom-Json
Assert-True ([int]$j3.selected_jobs_count -eq 1) "retry selected_jobs_count expected 1"
Assert-True (([int]$j3.ok_count + [int]$j3.summary.skipped) -eq 1) "retry success count (ok+skipped) expected 1"
Assert-True ([int]$j3.fail_count -eq 0) "retry fail_count expected 0"
Assert-True ([string]$j3.selection_mode -eq "only_failed_from") "retry selection_mode expected only_failed_from"

# 4) Contract keys on report
$requiredTop = @(
  "batch_ok",
  "stopped_early",
  "stop_reason",
  "continue_on_error",
  "max_fail",
  "selection_mode",
  "source_batch_report"
)
Assert-HasKeys -obj $j2 -keys $requiredTop -label "report_continue"

Remove-Item -Recurse -Force $tmp
Write-Host "OK: smoke_batch_resume passed"
