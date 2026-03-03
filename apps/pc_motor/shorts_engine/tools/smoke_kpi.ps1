param(
  [string]$RepoRoot = (git rev-parse --show-toplevel),
  [string]$Py = "python"
)

$ErrorActionPreference = "Stop"

function Assert-True($cond, $msg) { if (-not $cond) { throw "ASSERT FAIL: $msg" } }
function Utf8NoBomWrite([string]$path, [string]$txt) {
  [System.IO.File]::WriteAllText($path, $txt, [System.Text.UTF8Encoding]::new($false))
}

Write-Host "== smoke_kpi =="
Set-Location $RepoRoot

$tmp = Join-Path $RepoRoot "_junk\smoke_kpi"
$dataDir = Join-Path $tmp "data"
$planDir = Join-Path $dataDir "plans\2026-02-22"
New-Item -ItemType Directory -Force $planDir | Out-Null

$batchReport = Join-Path $planDir "batch_report.json"
$planPath = Join-Path $planDir "plan.json"
$donePath = Join-Path $planDir "done.jsonl"
$pubPath = Join-Path $dataDir "publish_journal.jsonl"
$outPath = Join-Path $tmp "kpi_report.json"

$batchObj = @{
  schema_version = "0.1"
  batch_run_id = "batch_smoke_0001"
  ok_count = 3
  fail_count = 1
  cached_count = 2
  rendered_count = 2
  items = @()
}
$batchObj | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $batchReport -Encoding utf8

$planObj = @{
  schema_version = "0.1"
  date = "2026-02-22"
  created_at = "2026-02-22T10:00:00Z"
  policy = @{
    ideas_target = 2
    render_target = 2
    publish_target = 1
    selection_mode = "oldest"
    tag = $null
    max_fail = 2
    continue_on_error = $true
  }
  selection = @{
    idea_keys = @("k1","k2")
    counts = @{ queued_available = 5; selected = 2 }
  }
  artifacts = @{
    inputs_csv = (Join-Path $planDir "inputs.csv")
    gen_out_dir = (Join-Path $planDir "jobs")
    manifest_path = (Join-Path $planDir "jobs\manifest.json")
    jobs_file = (Join-Path $planDir "jobs\jobs.txt")
    jobset_path = (Join-Path $planDir "jobset.json")
    batch_report = $batchReport
  }
  status = @{ stage = "rendered"; note = $null }
}
$planObj | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $planPath -Encoding utf8

$doneEvents = @(
  @{ created_at = "2026-02-22T10:00:00Z"; action = "plan_make"; ok = $true; detail = @{ selected = 2 } },
  @{ created_at = "2026-02-22T10:05:00Z"; action = "plan_render"; ok = $true; detail = @{ ok_count = 3; fail_count = 1 } }
)
$doneLines = $doneEvents | ForEach-Object { $_ | ConvertTo-Json -Compress }
Utf8NoBomWrite $donePath (($doneLines -join "`n") + "`n")

$pubEvents = @(
  @{ created_at = "2026-02-22T12:00:00Z"; platform = "youtube_shorts"; status = "published"; idea_key = "k1" }
)
$pubLines = $pubEvents | ForEach-Object { $_ | ConvertTo-Json -Compress }
Utf8NoBomWrite $pubPath (($pubLines -join "`n") + "`n")

$out = & $Py -m shorts_engine.layer2.cli.report_kpi --data-dir $dataDir --days 7 --json-out $outPath
Assert-True ($LASTEXITCODE -eq 0) "report_kpi failed"
Assert-True (Test-Path -LiteralPath $outPath) "kpi report file missing"

$last = $out | Select-Object -Last 1 | ConvertFrom-Json
Assert-True ($last.ok -eq $true) "final json ok=false"

$r = Get-Content -LiteralPath $outPath -Raw | ConvertFrom-Json
Assert-True ($r.schema_version -eq "0.1") "schema_version expected 0.1"
Assert-True ($null -ne $r.rendering) "rendering section missing"
Assert-True ($null -ne $r.publishing) "publishing section missing"
Assert-True ([int]$r.publishing.published_count -eq 1) "published_count expected 1"
Assert-True ([int]$r.rendering.jobs_ok -eq 3) "jobs_ok expected 3"

Remove-Item -Recurse -Force $tmp
Write-Host "OK: smoke_kpi passed"
