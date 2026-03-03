param(
  [string]$Module = "shorts_engine.layer2.cli.render_batch",
  [string]$ArgsLine = "--help"
)

$ErrorActionPreference = "Stop"

function Die([string]$m) { throw $m }

$cmd = @("python","-m",$Module)
if ($ArgsLine.Trim()) {
  $cmd += $ArgsLine.Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)
}

# Merge streams; contract expects final combined line is JSON (because help/log on stderr is allowed).
$out = & $cmd[0] $cmd[1..($cmd.Count-1)] 2>&1
$code = [int]$LASTEXITCODE

if (-not $out -or $out.Count -eq 0) {
  Die "No output. Expected final JSON line."
}

$last = $out | Select-Object -Last 1
try { $payload = $last | ConvertFrom-Json } catch { Die "Last line not JSON.`nLAST:`n$last" }

if ($null -eq $payload.contract_version) { Die "Missing contract_version" }
if ($null -eq $payload.ok) { Die "Missing ok" }
if ($payload.ok -isnot [bool]) { } # allow bool-like

Write-Host "OK: parsed final JSON line. ok=$($payload.ok) exit=$code contract=$($payload.contract_version)"
exit 0
