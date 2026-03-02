Set-StrictMode -Version Latest

if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope Global -ErrorAction SilentlyContinue) {
  $global:PSNativeCommandUseErrorActionPreference = $true
}

function Run {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][string] $Exe,
    [string[]] $Args = @()
  )
  & $Exe @Args
  if ($LASTEXITCODE -ne 0) {
    throw ("FAILED: {0} {1} (exit={2})" -f $Exe, ($Args -join ' '), $LASTEXITCODE)
  }
}

function Get-SafeRepoFiles {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)]
    [string] $Root,

    # e.g. *.py, *.ps1, *.md
    [string[]] $Include = @("*"),

    # FullName contains match (simple and fast)
    [string[]] $ExcludeDirNames = @(
      ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
      "node_modules", "output", ".tmp", ".cache", "dist", "build"
    )
  )

  $rootPath = (Resolve-Path -LiteralPath $Root).Path
  $exclude = @{}
  foreach ($d in $ExcludeDirNames) { $exclude[$d.ToLowerInvariant()] = $true }

  # Enumerate all files; filter out excluded dirs by path segments
  Get-ChildItem -LiteralPath $rootPath -File -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object {
      $p = $_.FullName
      # Split path into segments and see if any excluded dir appears
      $segments = $p.Split([IO.Path]::DirectorySeparatorChar, [StringSplitOptions]::RemoveEmptyEntries)
      foreach ($s in $segments) {
        if ($exclude.ContainsKey($s.ToLowerInvariant())) { return $false }
      }
      return $true
    } |
    Where-Object {
      # Include patterns (wildcards)
      foreach ($pat in $Include) {
        if ($_.Name -like $pat) { return $true }
      }
      return $false
    }
}

function Import-PsLib {
  [CmdletBinding()]
  param([Parameter(Mandatory)][string] $ScriptDir)
  $lib = Join-Path $ScriptDir "_pslib.ps1"
  . $lib
}
