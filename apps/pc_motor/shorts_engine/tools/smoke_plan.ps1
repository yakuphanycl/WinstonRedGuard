param(
  [string]$RepoRoot = (git rev-parse --show-toplevel),
  [string]$Py = "python"
)

$ErrorActionPreference = "Stop"

function Assert-True($cond, $msg) { if (-not $cond) { throw "ASSERT FAIL: $msg" } }
function Parse-LastJson([string[]]$lines) {
  $last = $lines | Select-Object -Last 1
  return ($last | ConvertFrom-Json)
}

Write-Host "== smoke_plan =="
Set-Location $RepoRoot

$tmp = Join-Path $RepoRoot "_junk\smoke_plan"
$dataDir = Join-Path $tmp "data"
New-Item -ItemType Directory -Force $dataDir | Out-Null

# 1) seed ideas
$a1 = & $Py -m shorts_engine.layer2.cli.ideas --data-dir $dataDir add --topic "P1" --hook "Kisa Hook 1" --body "Kisa Body 1" --ending "Kisa End 1" --lang "tr" --duration-sec 8
Assert-True ($LASTEXITCODE -eq 0) "ideas add #1 failed"
$j1 = Parse-LastJson -lines $a1
Assert-True ($j1.ok -eq $true) "ideas add #1 json not ok"

$a2 = & $Py -m shorts_engine.layer2.cli.ideas --data-dir $dataDir add --topic "P2" --hook "Kisa Hook 2" --body "Kisa Body 2" --ending "Kisa End 2" --lang "tr" --duration-sec 8
Assert-True ($LASTEXITCODE -eq 0) "ideas add #2 failed"
$j2 = Parse-LastJson -lines $a2
Assert-True ($j2.ok -eq $true) "ideas add #2 json not ok"

# 2) make plan
$day = "2026-02-22"
$mk = & $Py -m shorts_engine.layer2.cli.plan --data-dir $dataDir make --date $day --ideas-target 2 --selection oldest --render-target 2 --continue-on-error --max-fail 2
Assert-True ($LASTEXITCODE -eq 0) "plan make failed"
$mj = Parse-LastJson -lines $mk
Assert-True ($mj.ok -eq $true) "plan make json not ok"
Assert-True ([int]$mj.selected -eq 2) "plan selected expected 2"

# 3) build
$bd = & $Py -m shorts_engine.layer2.cli.plan --data-dir $dataDir build --date $day
Assert-True ($LASTEXITCODE -eq 0) "plan build failed"
$bj = Parse-LastJson -lines $bd
Assert-True ($bj.ok -eq $true) "plan build json not ok"

$planPath = Join-Path $dataDir ("plans\" + $day + "\plan.json")
Assert-True (Test-Path -LiteralPath $planPath) "plan.json missing"
$plan = Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json
Assert-True ($plan.status.stage -eq "generated") "plan stage expected generated"
Assert-True (Test-Path -LiteralPath $plan.artifacts.inputs_csv) "inputs_csv missing"
Assert-True (Test-Path -LiteralPath $plan.artifacts.manifest_path) "manifest_path missing"
Assert-True (Test-Path -LiteralPath $plan.artifacts.jobs_file) "jobs_file missing"

# 4) render
$rd = & $Py -m shorts_engine.layer2.cli.plan --data-dir $dataDir render --date $day --continue-on-error --max-fail 2
Assert-True (($LASTEXITCODE -eq 0) -or ($LASTEXITCODE -eq 2)) "plan render unexpected exit"
$rj = Parse-LastJson -lines $rd
Assert-True ($rj.exit_code -in @(0,2)) "plan render exit_code unexpected"

$plan2 = Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json
Assert-True ($plan2.status.stage -in @("rendered","partial")) "plan stage expected rendered/partial"
Assert-True (Test-Path -LiteralPath $plan2.artifacts.batch_report) "batch_report missing"

$donePath = Join-Path $dataDir ("plans\" + $day + "\done.jsonl")
Assert-True (Test-Path -LiteralPath $donePath) "done.jsonl missing"
$doneLines = Get-Content -LiteralPath $donePath | Where-Object { $_ -and $_.Trim() -ne "" }
Assert-True ($doneLines.Count -ge 3) "done.jsonl expected >= 3 events"

Remove-Item -Recurse -Force $tmp
Write-Host "OK: smoke_plan passed"
