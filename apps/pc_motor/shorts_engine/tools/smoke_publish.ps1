param(
  [string]$RepoRoot = (git rev-parse --show-toplevel),
  [string]$Py = "python"
)

$ErrorActionPreference = "Stop"

function Assert-True($cond, $msg) { if (-not $cond) { throw "ASSERT FAIL: $msg" } }
function Get-RunId([string[]]$lines) {
  $m = $lines | Select-String -Pattern "run_id=([0-9a-fA-F_]+)" | Select-Object -First 1
  if ($m -and $m.Matches.Count -gt 0) { return $m.Matches[0].Groups[1].Value }
  return $null
}

Write-Host "== smoke_publish =="
Set-Location $RepoRoot

$job = "shorts_engine/layer2/examples/min_job.json"
$out = & $Py -m shorts_engine.layer2.cli.render_job --job $job
Assert-True ($LASTEXITCODE -eq 0) "render_job failed for publish smoke"
$runId = Get-RunId -lines $out
Assert-True ($runId) "missing run_id"

$tmp = Join-Path $RepoRoot "_junk\smoke_publish"
New-Item -ItemType Directory -Force $tmp | Out-Null
$journal = Join-Path $tmp "publish_journal.jsonl"

$p1 = & $Py -m shorts_engine.layer2.cli.publish add --repo-root $RepoRoot --journal $journal --run-id $runId --title "Smoke Publish"
Assert-True ($LASTEXITCODE -eq 0) "publish add failed"
Assert-True (Test-Path -LiteralPath $journal) "publish journal missing"

$p2 = & $Py -m shorts_engine.layer2.cli.publish list --repo-root $RepoRoot --journal $journal --limit 5
Assert-True ($LASTEXITCODE -eq 0) "publish list failed"
$last = $p2 | Select-Object -Last 1 | ConvertFrom-Json
Assert-True ($last.ok -eq $true) "publish list JSON not ok"
Assert-True ($last.count -ge 1) "publish list expected >=1 item"

Remove-Item -Recurse -Force $tmp
Write-Host "OK: smoke_publish passed"
