# shorts_engine/tools/explain.ps1
# One-command documentation scaffolder + reconnaissance output.
# Usage:
#   pwsh -NoProfile -ExecutionPolicy Bypass -File shorts_engine/tools/explain.ps1

$ErrorActionPreference = "Stop"

function Find-ShortsEngineRoot {
  param([string]$Start = (Get-Location).Path)

  # 0) ENV override
  if ($env:SHORTS_ENGINE_ROOT -and (Test-Path -LiteralPath $env:SHORTS_ENGINE_ROOT)) {
    return (Resolve-Path -LiteralPath $env:SHORTS_ENGINE_ROOT).Path
  }

  # 1) Parent-walk: find a directory named "shorts_engine"
  try { $p = (Resolve-Path -LiteralPath $Start -ErrorAction Stop).Path }
  catch { $p = (Get-Location).Path }

  while ($true) {
    $candidate = Join-Path -Path $p -ChildPath "shorts_engine"
    if (Test-Path -LiteralPath $candidate) {
      return (Resolve-Path -LiteralPath $candidate).Path
    }
    $parent = Split-Path -Path $p -Parent
    if ($parent -eq $p -or [string]::IsNullOrWhiteSpace($parent)) { break }
    $p = $parent
  }

  throw "Could not locate shorts_engine root. Set SHORTS_ENGINE_ROOT env var or run inside repo."
}

function Ensure-Dir([string]$Path) {
  New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Has-Command([string]$Name) {
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

$se = Find-ShortsEngineRoot
$repo = Split-Path -Path $se -Parent

$docs = Join-Path $se "docs"
$gen  = Join-Path $docs "_generated"
$tasks = Join-Path $se "tasks"

Ensure-Dir $docs
Ensure-Dir $gen
Ensure-Dir $tasks

# --- A) "Tree" (depth 4) without external tools ---
$treeOut = Join-Path $gen "tree.txt"
"ROOT: $se" | Set-Content -Encoding UTF8 -NoNewline $treeOut
"`n" | Add-Content -Encoding UTF8 $treeOut

# Rough depth-limited listing (4)
$baseLen = ($se.TrimEnd('\','/')).Length
$items = Get-ChildItem -LiteralPath $se -Recurse -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName.Substring($baseLen).Split([IO.Path]::DirectorySeparatorChar).Count -le 5 } |
  Sort-Object FullName

foreach ($it in $items) {
  $rel = $it.FullName.Substring($baseLen).TrimStart('\','/')
  $depth = (($rel -split '[\\/]').Count - 1)
  $indent = ("  " * $depth)
  $marker = if ($it.PSIsContainer) { "[D]" } else { " - " }
  "$indent$marker $rel" | Add-Content -Encoding UTF8 $treeOut
}

# --- B) Grep: run_store / runs / artifacts_ok / gates ---
$grepOut = Join-Path $gen "grep_run_store.txt"
$patterns = @("run_store", "runs\/", "runs\\", "artifacts_ok", "verify\.ps1", "release_check\.ps1", "render_job\.py")

if (Has-Command "rg") {
  "Using rg" | Set-Content -Encoding UTF8 $grepOut
  foreach ($pat in $patterns) {
    "`n=== rg: $pat ===" | Add-Content -Encoding UTF8 $grepOut
    rg -n --hidden --no-ignore -S $pat $se 2>$null | Add-Content -Encoding UTF8 $grepOut
  }
} else {
  "Using Select-String" | Set-Content -Encoding UTF8 $grepOut
  foreach ($pat in $patterns) {
    "`n=== Select-String: $pat ===" | Add-Content -Encoding UTF8 $grepOut
    Get-ChildItem -LiteralPath $se -Recurse -Force -File -ErrorAction SilentlyContinue |
      Select-String -Pattern $pat -AllMatches -CaseSensitive:$false |
      ForEach-Object { "{0}:{1}:{2}" -f $_.Path, $_.LineNumber, $_.Line.Trim() } |
      Add-Content -Encoding UTF8 $grepOut
  }
}

# --- C) Entry points: layer2/cli/*.py ---
$entryOut = Join-Path $gen "entrypoints.txt"
"Layer2 CLI entry points" | Set-Content -Encoding UTF8 $entryOut

$cliDir = Join-Path $se "layer2\cli"
if (Test-Path -LiteralPath $cliDir) {
  Get-ChildItem -LiteralPath $cliDir -Filter "*.py" -File -ErrorAction SilentlyContinue |
    Sort-Object Name |
    ForEach-Object {
      "`n--- $($_.FullName) ---" | Add-Content -Encoding UTF8 $entryOut
      # Look for main() and __main__ blocks quickly
      (Select-String -LiteralPath $_.FullName -Pattern "def\s+main\s*\(|if\s+__name__\s*==\s*['""]__main__['""]" -AllMatches -ErrorAction SilentlyContinue) |
        ForEach-Object { "{0}:{1}: {2}" -f $_.Path, $_.LineNumber, $_.Line.Trim() } |
        Add-Content -Encoding UTF8 $entryOut
    }
} else {
  "WARNING: layer2/cli not found at expected path: $cliDir" | Add-Content -Encoding UTF8 $entryOut
}

# --- D) Best-effort: extract REQUIRED_ARTIFACTS from layer2/core/run_store.py ---
$requiredOut = Join-Path $gen "required_artifacts.txt"
$runStorePath = Join-Path $se "layer2\core\run_store.py"
try {
  if (-not (Test-Path -LiteralPath $runStorePath)) {
    Write-Warning "run_store.py not found at expected path: $runStorePath"
    Set-Content -Encoding UTF8 $requiredOut @()
  } else {
    $runStoreText = Get-Content -LiteralPath $runStorePath -Raw -ErrorAction Stop
    $blockMatch = [regex]::Match($runStoreText, "REQUIRED_ARTIFACTS\s*=\s*\{(?<body>[\s\S]*?)\}", [System.Text.RegularExpressions.RegexOptions]::Singleline)
    if (-not $blockMatch.Success) {
      Write-Warning "Could not parse REQUIRED_ARTIFACTS block from run_store.py"
      Set-Content -Encoding UTF8 $requiredOut @()
    } else {
      $body = $blockMatch.Groups["body"].Value
      $valueMatches = [regex]::Matches($body, ":\s*['""](?<val>[^'""]+)['""]")
      if ($valueMatches.Count -eq 0) {
        Write-Warning "REQUIRED_ARTIFACTS found but no artifact values parsed"
        Set-Content -Encoding UTF8 $requiredOut @()
      } else {
        $vals = @()
        foreach ($m in $valueMatches) {
          $vals += $m.Groups["val"].Value
        }
        $vals | Set-Content -Encoding UTF8 $requiredOut
      }
    }
  }
} catch {
  Write-Warning ("Failed to extract REQUIRED_ARTIFACTS: " + $_.Exception.Message)
  try { Set-Content -Encoding UTF8 $requiredOut @() } catch {}
}

# --- E) Codex prompt file for deep explanation ---
$promptPath = Join-Path $tasks "codex_explain_prompt.txt"
@"
# CODEX TASK: Explain shorts_engine codebase (Layer-2 focus) + produce docs

You are Codex running inside a local repo. Your job:
1) Build a concise architecture map of this codebase.
2) Identify the golden path CLI flow and the release/verify gates.
3) Output:
   - docs/ARCHITECTURE_LAYER2.md
   - docs/FLOW_RENDER_JOB.md
   - docs/RUN_STORE_CONTRACT.md
   - docs/FILES_MAP.md
   - docs/DIAGRAMS.md (Mermaid diagrams)
4) Be honest about unknowns; cite exact file paths + line ranges for key claims.

Constraints:
- Documentation-only. No refactors.

Read these files first:
- layer2/cli/render_job.py
- layer2/cli/render_status.py (if exists)
- layer2/core/run_store.py
- tools/release_check.ps1
- tools/verify.ps1

Also use:
- docs/_generated/tree.txt
- docs/_generated/grep_run_store.txt
- docs/_generated/entrypoints.txt

Deliverables requirements:
- Golden path contract: inputs/outputs/exit codes, artifacts_ok semantics
- Run store contract: required artifacts list, directory layout, failure modes
- Mermaid diagrams: component + sequence diagram for render_job
"@ | Set-Content -Encoding UTF8 $promptPath

# --- F) Create placeholder docs if missing (skeletons) ---
function Ensure-Doc([string]$Path, [string]$Content) {
  if (!(Test-Path -LiteralPath $Path)) {
    $Content | Set-Content -Encoding UTF8 $Path
  }
}

$docArchitecture = @"
# Layer-2 Architecture

## Purpose

## Layers Overview (Layer-1 vs Layer-2)

## Key Invariants
- run_id
- artifacts_ok
- ok

## Components

## Error handling & exit codes
"@

$docFlow = @"
# Flow: layer2.cli.render_job

## CLI inputs

## Step-by-step flow

## Artifacts written

## Exit codes & failure modes
"@

$docRunStore = @"
# Run Store Contract

## Directory layout

## Required artifacts

## Optional artifacts

## artifacts_ok semantics

## Cleanup / pruning
"@

$docFilesMap = @"
# Files Map

| Path | Role | Reads | Writes | Called by |
|---|---|---|---|---|
"@

$docDiagrams = @(
  '# Diagrams',
  '',
  '## Component diagram',
  '',
  '```mermaid',
  'flowchart TD',
  '  A[Layer-2 CLI] --> B[Run Store]',
  '  A --> C[Layer-1 Renderer]',
  '  B --> D[runs/<run_id>]',
  '```',
  '',
  '## Sequence diagram',
  '',
  '```mermaid',
  'sequenceDiagram',
  '  participant U as User',
  '  participant L2 as layer2.cli.render_job',
  '  participant RS as run_store',
  '  participant L1 as layer1 renderer',
  '',
  '  U->>L2: run render_job(job.json)',
  '  L2->>RS: create run_id + dirs',
  '  L2->>L1: invoke render',
  '  L1-->>L2: exit code + outputs',
  '  L2->>RS: write status/meta/trace',
  '  L2-->>U: ok + run_id',
  '```'
) -join "`n"

Ensure-Doc (Join-Path $docs "ARCHITECTURE_LAYER2.md") $docArchitecture
Ensure-Doc (Join-Path $docs "FLOW_RENDER_JOB.md") $docFlow
Ensure-Doc (Join-Path $docs "RUN_STORE_CONTRACT.md") $docRunStore
Ensure-Doc (Join-Path $docs "FILES_MAP.md") $docFilesMap
Ensure-Doc (Join-Path $docs "DIAGRAMS.md") $docDiagrams

Write-Host ""
Write-Host "OK: explain scaffolding done." -ForegroundColor Green
Write-Host "Generated:" -ForegroundColor Green
Write-Host " - $treeOut"
Write-Host " - $grepOut"
Write-Host " - $entryOut"
Write-Host " - $requiredOut"
Write-Host " - $promptPath"
Write-Host ""
Write-Host "NEXT:" -ForegroundColor Yellow
Write-Host " 1) Open tasks/codex_explain_prompt.txt and paste into Codex."
Write-Host " 2) Codex should fill docs/*.md with real content + line anchors."
Write-Host ""
Write-Host "TIP: git status -sb && git diff --stat"
