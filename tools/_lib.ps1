# WinstonRedGuard/tools/_lib.ps1
# Common helpers for PowerShell gates (WRG-*).

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function WRG-Die([string]$msg, [int]$rc = 1) {
  Write-Host "[FAIL] $msg" -ForegroundColor Red
  exit $rc
}

function WRG-Info([string]$msg) { Write-Host "[INFO] $msg" -ForegroundColor DarkGray }
function WRG-Ok([string]$msg)   { Write-Host "[ OK ] $msg" -ForegroundColor Green }
function WRG-Warn([string]$msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }

function WRG-AssertPath([string]$path, [string]$label = "path") {
  if (-not (Test-Path -LiteralPath $path)) {
    WRG-Die "$label not found: $path" 1
  }
}

function WRG-PushDir {
  [CmdletBinding()]
  param([Parameter(Mandatory)][string]$Path)

  if (-not (Test-Path -LiteralPath $Path)) {
    WRG-Die "directory not found: $Path" 1
  }
  Push-Location -LiteralPath $Path
}

function WRG-PopDir {
  [CmdletBinding()]
  param()
  try { Pop-Location } catch { WRG-Die "Pop-Location failed (stack empty?)" 1 }
}

function WRG-GetPythonArgv {
  [CmdletBinding()]
  param()

  if (Get-Command py -ErrorAction SilentlyContinue) {
    try {
& py -c "import sys; print(sys.executable)" 1>$null 2>$null
      if ($LASTEXITCODE -eq 0) { return @("py","-3") }
    } catch {}
  }

  foreach ($c in @("python","python3")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) {
      try {
        & $c -c "import sys; print(sys.executable)" 1>$null 2>$null
        if ($LASTEXITCODE -eq 0) { return @($c) }
      } catch {}
    }
  }

  WRG-Die "python not found (tried: py -3, python, python3)" 1
}

function WRG-GetPythonString {
  [CmdletBinding()]
  param()
  $p = WRG-GetPythonArgv
  return ($p -join " ")
}

function WRG-GetPython {
  [CmdletBinding()]
  param()
  return (WRG-GetPythonArgv)
}

function WRG-RunDirect {
  [CmdletBinding(DefaultParameterSetName="Named")]
  param(
    # Named style
    [Parameter(Mandatory, ParameterSetName="Named")][string]$FilePath,
    [Parameter(ParameterSetName="Named")][string[]]$Args,
    [Parameter(ParameterSetName="Named")][string]$Cwd,
    [Parameter(ParameterSetName="Named")][hashtable]$Env,
    [Parameter(ParameterSetName="Named")][int[]]$OkExitCodes = @(0),
    [Parameter(ParameterSetName="Named")][switch]$Capture,
    [Parameter(ParameterSetName="Named")][switch]$Quiet,
    [Parameter(ParameterSetName="Named")][switch]$NoThrow,

    # Legacy style:
    # WRG-RunDirect "label" @("python","-V") @(0)
    # optionally: WRG-RunDirect "label" @cmd @(0) "C:\cwd"
    [Parameter(Mandatory, Position=0, ParameterSetName="Legacy")][string]$Label,
    [Parameter(Mandatory, Position=1, ParameterSetName="Legacy")][object[]]$Command,
    [Parameter(Position=2, ParameterSetName="Legacy")][int[]]$LegacyOkExitCodes = @(0),
    [Parameter(Position=3, ParameterSetName="Legacy")][string]$LegacyCwd
  )

  if ($PSCmdlet.ParameterSetName -eq "Legacy") {
    if (-not $Command -or $Command.Count -lt 1) {
      WRG-Die "WRG-RunDirect legacy: empty command (label=$Label)" 1
    }

    $FilePath = [string]$Command[0]
    if ($Command.Count -gt 1) { $Args = $Command[1..($Command.Count-1)] | ForEach-Object { [string]$_ } }
    else { $Args = @() }

    $OkExitCodes = $LegacyOkExitCodes
    $Cwd = $LegacyCwd

    if (-not $Quiet) { WRG-Info $Label }
  }

  # Compat: FilePath may include inline args ("py"). Split if the exe exists.
  if ($FilePath -match '\s') {
    $parts = $FilePath -split '\s+'
    if ($parts.Count -ge 2) {
      $exe = $parts[0]
      if (Get-Command $exe -ErrorAction SilentlyContinue) {
        $extra = $parts[1..($parts.Count-1)]
        $FilePath = $exe
        $existing = if ($Args) { @($Args) } else { @() }
        $Args = @($extra + $existing)
      }
    }
  }

  # env override (process scope, temporary)
  $savedEnv = @{}
  if ($Env) {
    foreach ($k in $Env.Keys) {
      $savedEnv[$k] = [Environment]::GetEnvironmentVariable($k, "Process")
      [Environment]::SetEnvironmentVariable($k, [string]$Env[$k], "Process")
    }
  }

  $pushed = $false
  if ($Cwd) { Push-Location -LiteralPath $Cwd; $pushed = $true }

  try {
    if (-not $Quiet) {
      $argText = if ($Args) {
        ($Args | ForEach-Object { if ($_ -match '\s') { '"{0}"' -f $_ } else { $_ } }) -join ' '
      } else { "" }
      Write-Host "==> $FilePath $argText"
    }

    $out = $null
    if ($Capture) {
      $out = & $FilePath @Args 2>&1
      $rc = $global:LASTEXITCODE
      if (-not $Quiet -and $out) { $out | ForEach-Object { Write-Host $_ } }
    } else {
      & $FilePath @Args 2>&1 | Out-Host
      $rc = $global:LASTEXITCODE
    }

    if ($null -eq $rc) { $rc = 0 }
    $global:LASTEXITCODE = $rc

    if (-not ($OkExitCodes -contains $rc)) {
      $msg = "[ERR] rc=$rc while running: $FilePath " + (($Args) -join ' ')
      if ($NoThrow) {
        if (-not $Quiet) { Write-Error $msg }
      } else {
        throw $msg
      }
    }

    if ($Capture) { return [pscustomobject]@{ rc = $rc; output = $out } }
    return
  }
  finally {
    if ($pushed) { Pop-Location }
    if ($Env) {
      foreach ($k in $Env.Keys) {
        [Environment]::SetEnvironmentVariable($k, $savedEnv[$k], "Process")
      }
    }
  }
}

function WRG-FindWheel {
    param([Parameter(Mandatory=$true)][string]$DistDir)

    if (-not (Test-Path -LiteralPath $DistDir)) {
        throw "[ERR] dist dir not found: $DistDir"
    }

    $wheel = Get-ChildItem -LiteralPath $DistDir -Recurse -File -Filter *.whl -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if (-not $wheel) {
        throw "[ERR] no wheel found under: $DistDir"
    }

    return (($wheel -replace '^\s*py\s+-3\s*$', 'py')).FullName
}

# --- WRG compat helpers (for release_check.ps1) ---
if (-not (Get-Command WRG-NewTempDir -ErrorAction SilentlyContinue)) {
  function WRG-NewTempDir {
    param([Parameter(Mandatory=$true)][string]$Prefix)
    $base = [System.IO.Path]::GetTempPath()
    $name = "{0}-{1}" -f $Prefix, ([System.Guid]::NewGuid().ToString("N").Substring(0,8))
    $path = Join-Path $base $name
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    return $path
  }
}

if (-not (Get-Command WRG-RemoveTree -ErrorAction SilentlyContinue)) {
  function WRG-RemoveTree {
    param([Parameter(Mandatory=$true)][string]$Path)
    if (Test-Path -LiteralPath $Path) {
      Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
}

if (-not (Get-Command WRG-AssertPath -ErrorAction SilentlyContinue)) {
  function WRG-AssertPath {
    param(
      [Parameter(Mandatory=$true)][string]$Path,
      [Parameter(Mandatory=$true)][string]$What
    )
    if (-not (Test-Path -LiteralPath $Path)) {
      throw ("[ERR] missing {0}: {1}" -f $What, $Path)
    }
    return $Path
  }
}

function WRG-RemoveDirSafe {
  param([Parameter(Mandatory=$true)][string]$Path)

  if (-not $Path) { return }
  if (-not (Test-Path -LiteralPath $Path)) { return }

  try {
    Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
    return
  } catch {
    # fallback: clear attributes then retry
    try {
      Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue |
        ForEach-Object { try { $_.Attributes = "Normal" } catch {} }
      Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
      return
    } catch {
      # last resort: best-effort, do not fail release_check cleanup
      try { Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue } catch {}
      return
    }
  }
}






