param(
  [string]$RepoRoot = (git rev-parse --show-toplevel),
  [string]$Py = "python"
)

$ErrorActionPreference = "Stop"

function Assert-True($cond, $msg) {
  if (-not $cond) { throw "ASSERT FAIL: $msg" }
}

function Get-RunId([string[]]$lines) {
  $m = $lines | Select-String -Pattern "run_id=([0-9a-fA-F_]+)" | Select-Object -First 1
  if ($m -and $m.Matches.Count -gt 0) { return $m.Matches[0].Groups[1].Value }
  return $null
}

function Calc-RunIdFromJob([string]$jobPath) {
  $code = @"
import json, hashlib, sys
from shorts_engine.layer2.core.presets import apply_preset
from shorts_engine.layer2.core.run_store import run_id_from_job
p = sys.argv[1]
obj = json.loads(open(p, "r", encoding="utf-8-sig").read())
eff, _, _ = apply_preset(obj) if isinstance(obj, dict) else (obj, None, None)
print(run_id_from_job(eff if isinstance(eff, dict) else {}))
"@
  $out = & python -c $code $jobPath
  if ($LASTEXITCODE -ne 0) { return $null }
  return ($out | Select-Object -First 1).Trim()
}

function Get-RunDir([string]$root, [string]$runId) {
  $cands = @(
    (Join-Path $root ("runs\" + $runId)),
    (Join-Path $root ("shorts_engine\runs\" + $runId))
  )
  foreach ($c in $cands) {
    if (Test-Path -LiteralPath $c) { return $c }
  }
  return $null
}

Write-Host "== smoke_lint =="
Set-Location $RepoRoot

$tmp = Join-Path $RepoRoot "_junk\smoke_lint"
New-Item -ItemType Directory -Force $tmp | Out-Null

$validJobPath = Join-Path $RepoRoot "shorts_engine/layer2/examples/min_job.json"
$invalidJobPath = Join-Path $tmp "invalid_lint_job.json"

$valid = Get-Content -LiteralPath $validJobPath -Raw | ConvertFrom-Json
$valid.subtitles.items = @(@{ text = "SupercalifragilisticexpialidociousSupercalifragilisticexpialidocious" })
$valid.output.path = "output/smoke_lint_invalid.mp4"
$valid | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $invalidJobPath -Encoding utf8

# 1) invalid lint should fail
$lintBadOut = & $Py -m shorts_engine.layer2.cli.lint --job $invalidJobPath
Assert-True ($LASTEXITCODE -eq 2) "lint expected exit 2 for invalid job"
$lintBadJson = $lintBadOut | Select-Object -Last 1 | ConvertFrom-Json
Assert-True ($lintBadJson.ok -eq $false) "lint invalid expected ok=false"
Assert-True ([int]$lintBadJson.summary.errors -ge 1) "lint invalid expected errors>=1"

# 2) valid lint should pass
$lintGoodOut = & $Py -m shorts_engine.layer2.cli.lint --job $validJobPath
Assert-True ($LASTEXITCODE -eq 0) "lint expected exit 0 for valid job"
$lintGoodJson = $lintGoodOut | Select-Object -Last 1 | ConvertFrom-Json
Assert-True ($lintGoodJson.ok -eq $true) "lint valid expected ok=true"

# 3) render_job should fail validation due to lint integration
$renderBadOut = & $Py -m shorts_engine.layer2.cli.render_job --job $invalidJobPath
Assert-True ($LASTEXITCODE -eq 2) "render_job invalid lint expected exit 2"
$runId = Get-RunId -lines $renderBadOut
if (-not $runId) {
  $runId = Calc-RunIdFromJob -jobPath $invalidJobPath
}
Assert-True ($runId) "render_job invalid expected run_id in output"
$runDir = Get-RunDir -root $RepoRoot -runId $runId
Assert-True ($runDir) "run dir for invalid lint render not found"
$metaPath = Join-Path $runDir "meta.json"
Assert-True (Test-Path -LiteralPath $metaPath) "meta.json missing for invalid lint run"
$meta = Get-Content -LiteralPath $metaPath -Raw | ConvertFrom-Json
Assert-True ($meta.error_type -eq "validation") "meta.error_type expected validation"

Remove-Item -Recurse -Force $tmp
Write-Host "OK: smoke_lint passed"
