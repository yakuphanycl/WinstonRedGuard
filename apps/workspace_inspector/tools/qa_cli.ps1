Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Optional: PS7+ native error behavior (safe if missing).
$var = Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope Global -ErrorAction SilentlyContinue
if ($null -ne $var) { $global:PSNativeCommandUseErrorActionPreference = $true }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir "_pslib.ps1")

$repo = Resolve-Path -LiteralPath (Join-Path $ScriptDir "..")
Set-Location -LiteralPath $repo

function Remove-VolatileFields {
  [CmdletBinding()]
  param([Parameter(Mandatory)] $Obj)

  if ($Obj.PSObject.Properties.Name -contains "generated_at") { $Obj.PSObject.Properties.Remove("generated_at") }
  if ($Obj.PSObject.Properties.Name -contains "run_id") { $Obj.PSObject.Properties.Remove("run_id") }
  if ($Obj.PSObject.Properties.Name -contains "duration_ms") { $Obj.PSObject.Properties.Remove("duration_ms") }

  if (($Obj.PSObject.Properties.Name -contains "meta") -and $Obj.meta) {
    if ($Obj.meta.PSObject.Properties.Name -contains "generated_at") { $Obj.meta.PSObject.Properties.Remove("generated_at") }
    if ($Obj.meta.PSObject.Properties.Name -contains "run_id") { $Obj.meta.PSObject.Properties.Remove("run_id") }
    if ($Obj.meta.PSObject.Properties.Name -contains "duration_ms") { $Obj.meta.PSObject.Properties.Remove("duration_ms") }
  }

  return $Obj
}

function Invoke-Check {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][string] $Label,
    [Parameter(Mandatory)][scriptblock] $Check
  )
  & $Check
  Write-Host $Label
}

try {
  Invoke-Check -Label "PASS 1/3 JSON parses" -Check {
    $jsonRaw = (Run "workspace-inspector" @(".", "--json") | Out-String)
    $outDir = Join-Path $repo "output"
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $jsonTmp = Join-Path $outDir "qa_cli_json_tmp.json"
    Set-Content -LiteralPath $jsonTmp -Value $jsonRaw -Encoding UTF8
    Run "python" @("-c", "import json,sys; json.load(open(sys.argv[1],encoding='utf-8')); print('JSON_OK')", $jsonTmp) | Out-Null
  }

  Invoke-Check -Label "PASS 2/3 quiet output is empty" -Check {
    $quietOut = (Run "workspace-inspector" @(".", "--quiet") 2>&1 | Out-String).Trim()
    if ($quietOut.Length -ne 0) {
      throw ("FAIL 2/3 quiet produced output: {0}" -f $quietOut)
    }
  }

  Invoke-Check -Label "PASS 3/3 deterministic except volatile fields" -Check {
    $o1 = ((Run "workspace-inspector" @(".", "--json") | Out-String) | ConvertFrom-Json)
    Start-Sleep -Milliseconds 200
    $o2 = ((Run "workspace-inspector" @(".", "--json") | Out-String) | ConvertFrom-Json)

    $j1 = (Remove-VolatileFields $o1) | ConvertTo-Json -Depth 50
    $j2 = (Remove-VolatileFields $o2) | ConvertTo-Json -Depth 50
    if ($j1 -ne $j2) {
      throw "FAIL 3/3 deterministic compare failed after volatile-field normalization"
    }
  }

  Write-Host "QA_PASS"
  exit 0
} catch {
  Write-Host ("QA_FAIL: {0}" -f $_.Exception.Message)
  exit 2
}
