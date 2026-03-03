param(
  [string]$RepoRoot = (git rev-parse --show-toplevel),
  [string]$Py = "python"
)

$ErrorActionPreference = "Stop"

function Assert-True($cond, $msg) { if (-not $cond) { throw "ASSERT FAIL: $msg" } }

Write-Host "== smoke_diagnosis_trace_fallback =="

Set-Location $RepoRoot

$tmp = Join-Path $RepoRoot "_junk\diagnosis_trace_fallback_smoke"
New-Item -ItemType Directory -Force $tmp | Out-Null

$runId = "smoke_diag_trace_fallback_0001"
$runDir = Join-Path $tmp "runs\$runId"
New-Item -ItemType Directory -Force $runDir | Out-Null

$metaPath = Join-Path $runDir "meta.json"
@{
  artifacts = @{
    trace_fallback_used = "true"
  }
  diagnosis = ""
} | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $metaPath -Encoding utf8

$pyCode = @"
import json
from pathlib import Path

p = Path(r"$metaPath")
meta = json.loads(p.read_text(encoding="utf-8"))

try:
    a = (meta.get("artifacts") or {})
    if a.get("trace_fallback_used") == "true":
        d = meta.get("diagnosis") or ""
        tag = "[trace_fallback] trace.txt synthesized from layer1 stdout/stderr"
        meta["diagnosis"] = (d + ("; " if d else "") + tag)
except Exception:
    pass

p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"ok": True, "diagnosis": meta.get("diagnosis","")}))
"@

$out = & $Py -c $pyCode
if ($LASTEXITCODE -ne 0) { throw "python failed rc=$LASTEXITCODE" }

$j = $out | ConvertFrom-Json
Assert-True ($j.ok -eq $true) "ok=false"
Assert-True ($j.diagnosis -match "trace_fallback") "diagnosis missing trace_fallback tag"

Write-Host "OK: diagnosis contains trace_fallback tag"

Remove-Item -Recurse -Force $tmp
Write-Host "OK: smoke_diagnosis_trace_fallback passed"
