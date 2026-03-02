# tools/dev.ps1
param(
  [ValidateSet("run","smoke","fmt","all")]
  [string]$Task = "all",
  [string]$Folder = ".",
  [string]$OutJson = ".\report.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Run-Cmd($cmd) {
  Write-Host "RUN: $cmd"
  iex $cmd
  if ($LASTEXITCODE -ne 0) { throw "Command failed: $cmd" }
}

switch ($Task) {
  "fmt" {
    # varsa
    if (Get-Command ruff -ErrorAction SilentlyContinue) {
      Run-Cmd "ruff format ."
    } else {
      Write-Host "ruff not found, skipping fmt"
    }
  }
  "run" {
    Run-Cmd "workspace-inspector `"$Folder`" --json `"$OutJson`""
  }
  "smoke" {
    $tmp = Join-Path $env:TEMP "wi_smoke.json"
    Run-Cmd "workspace-inspector . --json `"$tmp`""
    if (!(Test-Path $tmp)) { throw "Smoke failed: json not created" }
    Write-Host "SMOKE_OK json=$tmp"
  }
  "all" {
    & $PSCommandPath -Task fmt
    & $PSCommandPath -Task smoke
    & $PSCommandPath -Task run -Folder $Folder -OutJson $OutJson
  }
}
