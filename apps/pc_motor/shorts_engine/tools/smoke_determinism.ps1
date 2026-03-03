param(
  [string]$RepoRoot = (git rev-parse --show-toplevel),
  [string]$Py = "python",
  [string]$Job = "shorts_engine/layer2/examples/min_job.json"
)

$ErrorActionPreference = "Stop"

function Assert-True($cond, $msg) { if (-not $cond) { throw "ASSERT FAIL: $msg" } }

Write-Host "== smoke_determinism =="
Set-Location $RepoRoot

function Get-RunIdFromOutput([string[]]$lines) {
  $m = $lines | Select-String -Pattern "run_id=([0-9a-fA-F_]+)" | Select-Object -First 1
  if ($m -and $m.Matches.Count -gt 0) { return $m.Matches[0].Groups[1].Value }
  return $null
}

# 1) Run #1
$out1 = & $Py -m shorts_engine.layer2.cli.render_job --job $Job
$rc1 = $LASTEXITCODE
Assert-True ($rc1 -eq 0) "render_job run#1 failed rc=$rc1"

$runId1 = Get-RunIdFromOutput -lines $out1
Assert-True ($runId1) "run_id not found in run#1 stdout"

$meta1 = Join-Path $RepoRoot ("runs\" + $runId1 + "\meta.json")
Assert-True (Test-Path -LiteralPath $meta1) "meta.json missing for run#1: $meta1"
$j1 = Get-Content -LiteralPath $meta1 -Raw | ConvertFrom-Json
Assert-True ($j1.job_hash) "meta.job_hash missing"
Assert-True ($j1.engine_version) "meta.engine_version missing"

# 2) Run #2 (same job)
$out2 = & $Py -m shorts_engine.layer2.cli.render_job --job $Job
$rc2 = $LASTEXITCODE
Assert-True ($rc2 -eq 0) "render_job run#2 failed rc=$rc2"

$runId2 = Get-RunIdFromOutput -lines $out2
Assert-True ($runId2) "run_id not found in run#2 stdout"
Assert-True ($runId2 -eq $runId1) "run_id is not deterministic: $runId1 != $runId2"

$meta2 = Join-Path $RepoRoot ("runs\" + $runId2 + "\meta.json")
Assert-True (Test-Path -LiteralPath $meta2) "meta.json missing for run#2: $meta2"
$j2 = Get-Content -LiteralPath $meta2 -Raw | ConvertFrom-Json
Assert-True ($j2.job_hash -eq $j1.job_hash) "job_hash mismatch between runs"
Assert-True ($j2.engine_version -eq $j1.engine_version) "engine_version mismatch between runs"

$cached2 = $false
try { $cached2 = [bool]$j2.artifacts.cached } catch { $cached2 = $false }

$mp4b1 = 0
$mp4b2 = 0
try { $mp4b1 = [int]$j1.artifacts.mp4_bytes } catch { $mp4b1 = 0 }
try { $mp4b2 = [int]$j2.artifacts.mp4_bytes } catch { $mp4b2 = 0 }

Assert-True ( $cached2 -or ($mp4b1 -gt 0 -and $mp4b2 -eq $mp4b1) ) "ne cached=true ne mp4_bytes stable (b1=$mp4b1 b2=$mp4b2 cached2=$cached2)"

Write-Host "OK: deterministic run_id"
Write-Host ("OK: job_hash=" + $j1.job_hash)
Write-Host ("OK: engine_version=" + $j1.engine_version)
Write-Host "OK: smoke_determinism passed"
