param(
  [string]$RepoRoot = (git rev-parse --show-toplevel),
  [string]$Py = "python"
)

$ErrorActionPreference = "Stop"

function Assert-True($cond, $msg) {
  if (-not $cond) { throw "ASSERT FAIL: $msg" }
}

Write-Host "== smoke_trace_fallback =="

Set-Location $RepoRoot

$tmp = Join-Path $RepoRoot "_junk\trace_fallback_smoke"
New-Item -ItemType Directory -Force $tmp | Out-Null

$runId = "smoke_trace_fallback_0001"
$runDir = Join-Path $tmp "runs\$runId"
New-Item -ItemType Directory -Force $runDir | Out-Null

$stdoutPath = Join-Path $runDir "layer1_stdout.txt"
$stderrPath = Join-Path $runDir "layer1_stderr.txt"

"stdout: hello`nstdout: last line" | Set-Content -LiteralPath $stdoutPath -Encoding utf8
"stderr: something went wrong`nstderr: stacktrace..." | Set-Content -LiteralPath $stderrPath -Encoding utf8

$pyCode = @"
import json
from pathlib import Path
from shorts_engine.layer2.core import render as R

run_dir = Path(r"$runDir")
stdout_path = Path(r"$stdoutPath")
stderr_path = Path(r"$stderrPath")
trace_path = run_dir / "trace.txt"

if trace_path.exists():
    trace_path.unlink()

R._write_trace_fallback(trace_path, stdout_path=stdout_path, stderr_path=stderr_path)

assert trace_path.exists(), "trace.txt was not created"
txt = trace_path.read_text(encoding="utf-8", errors="replace")
assert "BEGIN layer1 stdout" in txt, "stdout header missing"
assert "BEGIN layer1 stderr" in txt, "stderr header missing"

print(json.dumps({
    "ok": True,
    "trace_path": str(trace_path),
    "trace_bytes": len(txt.encode("utf-8", errors="replace"))
}))
"@

$raw = & $Py -c $pyCode
if ($LASTEXITCODE -ne 0) {
  throw "python failed rc=$LASTEXITCODE"
}

$j = $raw | ConvertFrom-Json
Assert-True ($j.ok -eq $true) "python returned ok=false"
Assert-True ([int]$j.trace_bytes -gt 10) "trace too small"

Write-Host "OK: trace fallback produced trace.txt"
Write-Host ("trace_path=" + $j.trace_path)
Write-Host ("trace_bytes=" + $j.trace_bytes)

Remove-Item -Recurse -Force $tmp

Write-Host "OK: smoke_trace_fallback passed"
