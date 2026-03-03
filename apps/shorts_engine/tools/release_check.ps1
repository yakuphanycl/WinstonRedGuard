# BOOTSTRAP_RELEASE_CHECK_V1
# - Make dot-source / strictmode safer
# - Prevent "function not recognized" when called before definition

if (-not (Test-Path variable:AllowOldContract)) { $AllowOldContract = $false }

if (-not (Get-Command Die -ErrorAction SilentlyContinue)) {
  function Die([string]$Message, [int]$Code = 1) {
    Write-Host ("FAIL: {0}" -f $Message)
    exit $Code
  }
}

if (-not (Get-Command Print-RunSummaryLine -ErrorAction SilentlyContinue)) {
  function Print-RunSummaryLine {
    param(
      [string]$Level,
      [hashtable]$Meta,
      [string]$Status,
      [string]$RunId
    )
    Write-Host ("[{0}] run={1} status={2}" -f $Level, $RunId, $Status)
  }
}
# /BOOTSTRAP_RELEASE_CHECK_V1
if ($AllowOldContract) {
  Write-Host "[WARN] old contract allowed: run=$RunId status=$status trace=$($meta.trace_path ?? 'trace.txt')"
  exit 0
} else {
  Write-Host "[FAIL] old contract forbidden: run=$RunId status=$status trace=$($meta.trace_path ?? 'trace.txt')"
  exit 1
}

function Tail-File {
  param(
    [Parameter(Mandatory=$true)][string]$Path,
    [int]$Lines = 20
  )
  if (!(Test-Path -LiteralPath $Path)) { return @() }
  try {
    return Get-Content -LiteralPath $Path -Tail $Lines -ErrorAction Stop
  } catch {
    return @()
  }
}

function Find-LastErrorLine {
  param(
    [Parameter(Mandatory=$true)][string[]]$Lines
  )
  $pat = '(?i)\b(error|exception|traceback|failed|fatal)\b'
  for ($i = $Lines.Count - 1; $i -ge 0; $i--) {
    if ($Lines[$i] -match $pat) { return $Lines[$i] }
  }
  return $null
}

function Try-ffprobe {
  param([string]$Mp4Path)

  $ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
  if (-not $ffprobe) { return $null } # no ffprobe -> silent skip

  try {
    $out = & $ffprobe.Source -v error -show_entries format=duration `
      -of default=noprint_wrappers=1:nokey=1 $Mp4Path 2>$null
    $dur = 0.0
    [double]::TryParse(($out | Select-Object -First 1), [ref]$dur) | Out-Null
    return $dur
  } catch {
    return $null
  }
}

function Suggest-NextStep {
  param([string]$FailClass)

  if (-not $FailClass) { return $null }

  switch -Regex ($FailClass) {
    '(?i)module_path|import|cwd|workdir' {
      return "Check working directory + python -m module paths. Ensure layer1 is invoked from repo root (or set SHORTS_ENGINE_ROOT)."
    }
    '(?i)ffmpeg|ffprobe' {
      return "Verify ffmpeg is installed and on PATH. Run: ffmpeg -version"
    }
    '(?i)job_invalid|schema|validation' {
      return "Run release_check -Job on the job file; inspect schema errors; fix required fields (hook/pattern_break/loop_ending etc.)."
    }
    '(?i)io|permission|access denied' {
      return "Check output/run dir write permissions; avoid protected folders; try a writable path under repo/output or user profile."
    }
    default {
      return "Open trace tail above and search for the first real error. If unclear, add more instrumentation to meta.json (fail_class, rc, cmd)."
    }
  }
}

function Try-GetGitRoot {
  try {
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) { return $null }
    $root = (& $git.Source rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0) { return $null }
    $root = ($root | Select-Object -First 1).Trim()
    if ([string]::IsNullOrWhiteSpace($root)) { return $null }
    return $root
  } catch {
    return $null
  }
}

function Normalize-AbsPath {
  param([Parameter(Mandatory=$true)][string]$Path)
  try {
    return (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
  } catch {
    return [System.IO.Path]::GetFullPath($Path)
  }
}

function Is-Under {
  param(
    [Parameter(Mandatory=$true)][string]$Child,
    [Parameter(Mandatory=$true)][string]$Parent
  )
  $c = (Normalize-AbsPath $Child).TrimEnd('\')
  $p = (Normalize-AbsPath $Parent).TrimEnd('\')
  return $c.StartsWith($p, [System.StringComparison]::OrdinalIgnoreCase)
}

function Print-KV {
  param([string]$Key, $Value)
  if ($null -eq $Value) { return }
  $s = $Value
  if ($s -is [System.Collections.IDictionary]) {
    $s = ($s | ConvertTo-Json -Compress)
  }
  Write-Host ("{0}={1}" -f $Key, $s)
}

function Find-FirstExisting {
  param(
    [Parameter(Mandatory=$true)][string]$Dir,
    [Parameter(Mandatory=$true)][string[]]$Candidates
  )
  foreach ($c in $Candidates) {
    $p = Join-Path $Dir $c
    if (Test-Path -LiteralPath $p) { return $p }
  }
  return $null
}

function Find-Mp4InRunDir {
  param([Parameter(Mandatory=$true)][string]$Dir)

  $p = Find-FirstExisting -Dir $Dir -Candidates @("out.mp4","output.mp4","video.mp4","test.mp4")
  if ($p) { return $p }

  try {
    $mp4 = Get-ChildItem -LiteralPath $Dir -Recurse -File -Filter *.mp4 -ErrorAction Stop |
      Sort-Object Length -Descending |
      Select-Object -First 1
    if ($mp4) { return $mp4.FullName }
  } catch {}
  return $null
}

function Read-JsonFile {
  param([Parameter(Mandatory=$true)][string]$Path)

  if (!(Test-Path -LiteralPath $Path)) { return $null }
  try {
    $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
    if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
    return ($raw | ConvertFrom-Json -ErrorAction Stop)
  } catch {
    return $null
  }
}

function To-RelPathIfPossible {
  param(
    [Parameter(Mandatory=$true)][string]$Path,
    [string]$Base
  )
  try {
    if ($Base) {
      $absP = Normalize-AbsPath $Path
      $absB = (Normalize-AbsPath $Base).TrimEnd('\') + '\'
      if ($absP.StartsWith($absB, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $absP.Substring($absB.Length)
      }
    }
  } catch {}
  return $Path
}

function Heuristic-ModulePathIssue {
  param(
    [string]$Cwd,
    $CmdObj
  )

  $cmdStr = $null
  if ($CmdObj -is [string]) {
    $cmdStr = $CmdObj
  } elseif ($CmdObj -is [System.Collections.IEnumerable]) {
    try { $cmdStr = ($CmdObj -join " ") } catch { $cmdStr = $null }
  }

  $signals = @()

  if ($cmdStr) {
    if ($cmdStr -match '(?i)\bpython\b' -and $cmdStr -match '(?i)\s-m\s+layer1\.') {
      $signals += "cmd_invokes_layer1_module"
    }
    if ($cmdStr -match '(?i)\s-m\s+layer2\.') {
      $signals += "cmd_invokes_layer2_module"
    }
  }

  if ($Cwd) {
    if ($Cwd -match '(?i)\\shorts_engine(\\|$)') {
      $signals += "cwd_inside_shorts_engine"
    } else {
      $signals += "cwd_outside_shorts_engine"
    }
  }

  if ($signals.Count -eq 0) { return $null }
  return $signals
}

function Info($msg) {
  Write-Host $msg
}

function Warn($msg) {
  Write-Warning $msg
}

function Print-RunSummaryLine {
  param(
    [Parameter(Mandatory=$true)][string]$Level, # OK|FAIL|WARN
    [Parameter(Mandatory=$true)]$Meta,
    [Parameter(Mandatory=$true)]$Status,
    [string]$RunId,
    [string]$TracePath
  )

  $cv = $Meta.contract_version
  $state = $Status.state
  $rc = $Meta.rc
  if ($null -eq $rc) { $rc = $Status.rc }

  $ok = $Meta.artifacts_ok
  $bytes = $Meta.mp4_bytes
  $mp4 = $Meta.mp4_path

  $rid = $RunId
  if ([string]::IsNullOrWhiteSpace($rid)) { $rid = $Meta.run_id }
  if ([string]::IsNullOrWhiteSpace($rid)) { $rid = $Status.run_id }

  Write-Host ("{0} run_id={1} cv={2} state={3} rc={4} artifacts_ok={5} mp4_bytes={6} mp4_path={7} trace={8}" -f `
    $Level, $rid, $cv, $state, $rc, $ok, $bytes, $mp4, $TracePath)
}

function Contract-UpgradeHint {
  param([string]$Got, [string]$Expected)

  if ($Got -eq "0.4" -and $Expected -eq "0.5") {
    return "Run store contract updated. Re-render to regenerate meta/status/trace with v0.5 layout (trace.txt + contract_version)."
  }
  return "Re-render with current code, or implement backward compatibility in release_check for older runs."
}

function Normalize-RunMeta {
  param(
    [Parameter(Mandatory=$true)]$Meta
  )

  # shallow copy (PSCustomObject -> hashtable-ish)
  $m = $Meta

  # contract_version
  if (-not $m.contract_version) {
    # old runs: fallback to legacy contract
    $m | Add-Member -NotePropertyName contract_version -NotePropertyValue "0.4" -Force
  }

  # rc variants
  if ($null -eq $m.rc) {
    if ($null -ne $m.exit_code) { $m | Add-Member rc $m.exit_code -Force }
    elseif ($null -ne $m.exitCode) { $m | Add-Member rc $m.exitCode -Force }
  }

  # run_id variants
  if (-not $m.run_id) {
    if ($m.runId) { $m | Add-Member run_id $m.runId -Force }
  }

  # artifacts_ok variants
  if ($null -eq $m.artifacts_ok) {
    if ($null -ne $m.artifact_ok) { $m | Add-Member artifacts_ok $m.artifact_ok -Force }
    elseif ($null -ne $m.artifactsOK) { $m | Add-Member artifacts_ok $m.artifactsOK -Force }
  }

  # mp4_path variants
  if (-not $m.mp4_path) {
    if ($m.output_mp4) { $m | Add-Member mp4_path $m.output_mp4 -Force }
    elseif ($m.video_path) { $m | Add-Member mp4_path $m.video_path -Force }
  }

  # mp4_bytes variants
  if ($null -eq $m.mp4_bytes) {
    if ($null -ne $m.mp4_size) { $m | Add-Member mp4_bytes $m.mp4_size -Force }
    elseif ($null -ne $m.video_bytes) { $m | Add-Member mp4_bytes $m.video_bytes -Force }
  }

  # trace_path variants
  if (-not $m.trace_path) {
    if ($m.trace) { $m | Add-Member trace_path $m.trace -Force }
    elseif ($m.trace_canonical) { $m | Add-Member trace_path $m.trace_canonical -Force }
  }

  # cwd variants
  if (-not $m.cwd) {
    if ($m.workdir) { $m | Add-Member cwd $m.workdir -Force }
    elseif ($m.working_dir) { $m | Add-Member cwd $m.working_dir -Force }
  }

  # cmd variants
  if (-not $m.cmd) {
    if ($m.command) { $m | Add-Member cmd $m.command -Force }
    elseif ($m.argv) { $m | Add-Member cmd $m.argv -Force }
  }

  return $m
}

function Normalize-RunStatus {
  param(
    [Parameter(Mandatory=$true)]$Status,
    [Parameter(Mandatory=$true)]$Meta # fallback source
  )

  $s = $Status

  if (-not $s.contract_version) {
    if ($Meta.contract_version) { $s | Add-Member contract_version $Meta.contract_version -Force }
    else { $s | Add-Member contract_version "0.4" -Force }
  }

  if (-not $s.run_id) {
    if ($s.runId) { $s | Add-Member run_id $s.runId -Force }
    elseif ($Meta.run_id) { $s | Add-Member run_id $Meta.run_id -Force }
  }

  if (-not $s.state) {
    if ($s.status) { $s | Add-Member state $s.status -Force }
    else { $s | Add-Member state "unknown" -Force }
  }

  if ($null -eq $s.rc) {
    if ($null -ne $s.exit_code) { $s | Add-Member rc $s.exit_code -Force }
    elseif ($null -ne $Meta.rc) { $s | Add-Member rc $Meta.rc -Force }
  }

  if ($null -eq $s.artifacts_ok) {
    if ($null -ne $Meta.artifacts_ok) { $s | Add-Member artifacts_ok $Meta.artifacts_ok -Force }
  }

  return $s
}

function Lint-RunContract {
  param(
    [Parameter(Mandatory=$true)]$Meta,
    [Parameter(Mandatory=$true)]$Status,
    [switch]$AllowOld
  )

  $errs = New-Object System.Collections.Generic.List[string]
  $warns = New-Object System.Collections.Generic.List[string]

  if (-not $Meta.contract_version) { $errs.Add("meta.contract_version missing") }
  if (-not $Meta.run_id) { $errs.Add("meta.run_id missing") }
  if ($null -eq $Meta.rc) {
    if ($AllowOld) {
      $wv = Get-Variable -Name warns -Scope 0 -ErrorAction SilentlyContinue
      if ($null -eq $wv) { $warns = New-Object System.Collections.Generic.List[string] } else { $warns = $wv.Value }
      $warns.Add("meta.rc missing (ignored: AllowOldContract)")
    } else {
      $errs.Add("meta.rc missing")
    }
  }
  if ($null -eq $Meta.artifacts_ok) {
    if ($AllowOld) {
      $wv = Get-Variable -Name warns -Scope 0 -ErrorAction SilentlyContinue
      if ($null -eq $wv) { $warns = New-Object System.Collections.Generic.List[string] } else { $warns = $wv.Value }
      $warns.Add("meta.artifacts_ok missing (ignored: AllowOldContract)")
    } else {
      $errs.Add("meta.artifacts_ok missing")
    }
  }
  if ($null -eq $Meta.mp4_bytes) { $warns.Add("meta.mp4_bytes missing") } # legacy runs may miss it
  if (-not $Meta.mp4_path) { $warns.Add("meta.mp4_path missing") }
  if (-not $Meta.trace_path) { $warns.Add("meta.trace_path missing") }

  if (-not $Status.state) {
    $errs.Add("status.state missing")
  } else {
    if ($Status.state -notin @("started","failed","succeeded","unknown")) {
      $errs.Add("status.state invalid: $($Status.state)")
    }
    if ($AllowOld -and $Status.state -eq "unknown") {
      $warns.Add("status.state=unknown (old contract)")
    }
  }

  if (-not $Status.run_id) { $errs.Add("status.run_id missing") }
  if ($null -eq $Status.rc) { $warns.Add("status.rc missing") } # usually filled from meta fallback

  if ($Meta.run_id -and $Status.run_id -and ($Meta.run_id -ne $Status.run_id)) {
    $warns.Add("run_id mismatch: meta=$($Meta.run_id) status=$($Status.run_id)")
  }

  return @{ errs = $errs; warns = $warns }
}

function _Score-FileCandidate {
  param(
    [Parameter(Mandatory=$true)][string]$ExpectedName,
    [Parameter(Mandatory=$true)][System.IO.FileInfo]$Candidate
  )

  $exp = $ExpectedName.ToLowerInvariant()
  $candName = $Candidate.Name.ToLowerInvariant()
  $candExt = [IO.Path]::GetExtension($candName)
  $expExt = [IO.Path]::GetExtension($exp)
  $score = 0

  # 1) Extension match
  if ($expExt -and $candExt -and ($candExt -eq $expExt)) { $score += 2 }

  # 2) Keyword intent match
  $kw = @("trace","log","meta","status","error","ffmpeg","stdout","stderr","diagnosis","report","mp4","json")
  foreach ($k in $kw) {
    $expHas = ($exp -like "*$k*")
    $candHas = ($candName -like "*$k*")
    if ($expHas -and $candHas) { $score += 3 }
  }

  # 3) Shared token overlap
  $expTokens = ($exp -split "[^a-z0-9]+") | Where-Object { $_ -and $_.Length -ge 3 }
  $candTokens = ($candName -split "[^a-z0-9]+") | Where-Object { $_ -and $_.Length -ge 3 }
  if ($expTokens.Count -gt 0 -and $candTokens.Count -gt 0) {
    $overlap = ($expTokens | Where-Object { $candTokens -contains $_ }).Count
    if ($overlap -ge 1) { $score += [Math]::Min(3, $overlap) }
  }

  # 4) Non-empty file
  if ($Candidate.Length -gt 0) { $score += 1 }

  return $score
}

function Show-RunDiscoveryHint {
  param(
    [Parameter(Mandatory=$true)][string]$RunDir,
    [int]$MaxItems = 30,
    [string[]]$MissingExpected = @(),
    [int]$TopCandidatesPerMissing = 3
  )

  Write-Host ""
  Write-Host "DISCOVERY HINT (migration): run dir contents + candidate mapping" -ForegroundColor Yellow
  Write-Host ("  run_dir = {0}" -f $RunDir) -ForegroundColor Yellow

  if (-not (Test-Path -LiteralPath $RunDir -PathType Container)) {
    Write-Host "  (run dir does not exist)" -ForegroundColor DarkYellow
    return
  }

  $all = Get-ChildItem -LiteralPath $RunDir -File -Force -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending

  if (-not $all -or $all.Count -eq 0) {
    Write-Host "  (no files found in run dir)" -ForegroundColor DarkYellow
    return
  }

  # 1) Broad list (top N)
  Write-Host ""
  Write-Host ("  Top {0} newest files:" -f $MaxItems) -ForegroundColor Yellow
  $all | Select-Object -First $MaxItems Name, Length, LastWriteTime |
    ForEach-Object {
      Write-Host ("   - {0} ({1} bytes)  {2}" -f $_.Name, $_.Length, $_.LastWriteTime.ToString("s"))
    }

  # 2) Focused candidates
  $kw = @("trace","log","meta","status","error","ffmpeg","stdout","stderr","diagnosis","report")
  $cand = $all | Where-Object {
    $n = $_.Name.ToLowerInvariant()
    foreach ($k in $kw) { if ($n -like "*$k*") { return $true } }
    return $false
  }

  if ($cand -and $cand.Count -gt 0) {
    Write-Host ""
    Write-Host "  Candidate files (name matches trace/log/meta/status/...):" -ForegroundColor Yellow
    $cand | Select-Object -First $MaxItems Name, Length, LastWriteTime |
      ForEach-Object {
        Write-Host ("   * {0} ({1} bytes)  {2}" -f $_.Name, $_.Length, $_.LastWriteTime.ToString("s"))
      }
  }

  # 3) Missing -> best candidate mapping
  if ($MissingExpected -and $MissingExpected.Count -gt 0) {
    Write-Host ""
    Write-Host ("  Missing -> best candidates (Top {0}):" -f $TopCandidatesPerMissing) -ForegroundColor Yellow

    foreach ($m in $MissingExpected) {
      $scored = @()
      foreach ($f in $all) {
        $s = _Score-FileCandidate -ExpectedName $m -Candidate $f
        if ($s -gt 0) {
          $scored += [pscustomobject]@{
            Score = $s
            Name = $f.Name
            Bytes = $f.Length
            Time = $f.LastWriteTime
          }
        }
      }

      $best = $scored | Sort-Object -Property Score, Time -Descending | Select-Object -First $TopCandidatesPerMissing

      Write-Host ("   - expected: {0}" -f $m) -ForegroundColor Yellow
      if (-not $best -or $best.Count -eq 0) {
        Write-Host "     (no strong candidates found)" -ForegroundColor DarkYellow
      } else {
        foreach ($b in $best) {
          Write-Host ("     -> score={0}  {1}  ({2} bytes)  {3}" -f $b.Score, $b.Name, $b.Bytes, $b.Time.ToString("s")) -ForegroundColor DarkYellow
        }
      }
    }
  }

  Write-Host ""
  Write-Host "  Tip: If expected contract files are missing, you're likely in a naming/location mismatch during migration." -ForegroundColor DarkYellow
}

$JobInput = $Job
$root = Split-Path -Parent $PSScriptRoot

# Quick mode: inspect an existing run meta by run_id.
if ($RunId) {
  Set-Location $root
  $runCandidates = @(
    (Join-Path $root ("runs\" + $RunId)),
    (Join-Path (Split-Path -Parent $root) ("runs\" + $RunId))
  )
  $runDir = $null
  foreach ($cand in $runCandidates) {
    if (Test-Path -LiteralPath $cand) { $runDir = $cand; break }
  }
  if (-not $runDir) { Die "run folder not found for run_id: $RunId" }

  $meta = Join-Path $runDir "meta.json"
  if (!(Test-Path -LiteralPath $meta)) { Die "meta not found: $meta" }

  $m = Get-Content -Raw -LiteralPath $meta | ConvertFrom-Json

  $diagnosis = $null
  if ($m) {
    $diagnosis = $m.diagnosis
    if ($null -eq $diagnosis) { $diagnosis = $m.fail_class }
    if ($null -eq $diagnosis) { $diagnosis = $m.error_class }
    if ($null -eq $diagnosis) { $diagnosis = $m.failClass }
  }

  if ($diagnosis) {
    Write-Host ("FAIL CLASS: {0}" -f $diagnosis) -ForegroundColor Yellow
    $hint = Suggest-NextStep -FailClass ([string]$diagnosis)
    if ($hint) {
      Write-Host ""
      Write-Host ("NEXT STEP: {0}" -f $hint)
    }
  }

  if ($m.artifacts) {
    Write-Host ("artifacts_ok={0} mp4_bytes={1} mp4_path={2}" -f `
      $m.artifacts.artifacts_ok, $m.artifacts.mp4_bytes, $m.artifacts.mp4_path)
    if ($m.artifacts.mp4_path) {
      $mp4Path = [string]$m.artifacts.mp4_path
      if (![System.IO.Path]::IsPathRooted($mp4Path)) {
        $mp4Path = Join-Path (Split-Path -Parent $root) $mp4Path
      }
      if ($mp4Path -and (Test-Path -LiteralPath $mp4Path)) {
        $dur = Try-ffprobe -Mp4Path $mp4Path
        if ($dur -ne $null) {
          Write-Host ("mp4_duration_sec={0}" -f $dur)
          if ($dur -le 0.1) {
            Write-Host "WARN: mp4 duration looks too small (possible broken file)."
          }
        } else {
          Write-Host "INFO: ffprobe not available; skipped mp4 playable check."
        }
      }
    }
  }

  Write-Host ""
  Write-Host "RUN META SUMMARY:"

  $rc  = $m.rc
  if ($null -eq $rc) { $rc = $m.exit_code }
  if ($null -eq $rc) { $rc = $m.exitCode }

  $cwd = $m.cwd
  if ($null -eq $cwd) { $cwd = $m.workdir }
  if ($null -eq $cwd) { $cwd = $m.working_dir }

  $cmd = $m.cmd
  if ($null -eq $cmd) { $cmd = $m.command }
  if ($null -eq $cmd) { $cmd = $m.argv }

  Print-KV -Key "run_dir" -Value $runDir
  Print-KV -Key "rc"      -Value $rc
  Print-KV -Key "cwd"     -Value $cwd
  Print-KV -Key "cmd"     -Value $cmd
  if ($m.trace_source)     { Write-Host ("trace_source={0}" -f $m.trace_source) }
  if ($m.trace_canonical)  { Write-Host ("trace_canonical={0}" -f $m.trace_canonical) }

  $gitRoot = Try-GetGitRoot
  if ($gitRoot) {
    Print-KV -Key "git_root" -Value $gitRoot

    $repoRuns = Join-Path $gitRoot "runs"
    $seRuns   = Join-Path $gitRoot "shorts_engine\runs"

    if (Test-Path -LiteralPath $repoRuns) {
      Print-KV -Key "repo_runs_dir" -Value $repoRuns
    }
    if (Test-Path -LiteralPath $seRuns) {
      Print-KV -Key "shorts_engine_runs_dir" -Value $seRuns
    }

    if ((Test-Path -LiteralPath $repoRuns) -and (Is-Under -Child $runDir -Parent $repoRuns)) {
      Write-Host "run_location=repo-level runs/"
    } elseif ((Test-Path -LiteralPath $seRuns) -and (Is-Under -Child $runDir -Parent $seRuns)) {
      Write-Host "run_location=shorts_engine/runs/"
    } else {
      Write-Host "run_location=unknown"
    }
  }

  $metaPath   = Find-FirstExisting -Dir $runDir -Candidates @("meta.json","_meta.json","run_meta.json","_last_render_meta.json")
  $statusPath = Find-FirstExisting -Dir $runDir -Candidates @("status.json","_status.json","run_status.json","_last_render_status.json")
  $jobPath    = Find-FirstExisting -Dir $runDir -Candidates @("job.json","_job.json","run_job.json","_captured_layer1_job.json","_captured_layer2_job.json")
  $tracePathC = Find-FirstExisting -Dir $runDir -Candidates @("trace.txt","_trace.txt","render_trace.txt","_last_render_trace.txt","trace.log","render_trace.log")
  $mp4Path    = Find-Mp4InRunDir -Dir $runDir

  $metaPathRel = if ($metaPath) { To-RelPathIfPossible -Path $metaPath -Base $gitRoot } else { $null }
  $statusPathRel = if ($statusPath) { To-RelPathIfPossible -Path $statusPath -Base $gitRoot } else { $null }
  $jobPathRel = if ($jobPath) { To-RelPathIfPossible -Path $jobPath -Base $gitRoot } else { $null }
  $tracePathRel = if ($tracePathC) { To-RelPathIfPossible -Path $tracePathC -Base $gitRoot } else { $null }
  $mp4PathRel = if ($mp4Path) { To-RelPathIfPossible -Path $mp4Path -Base $gitRoot } else { $null }

  Write-Host ""
  Write-Host "RUN CONTRACT FILES:"
  Print-KV -Key "meta_path"   -Value $metaPathRel
  Print-KV -Key "status_path" -Value $statusPathRel
  Print-KV -Key "job_path"    -Value $jobPathRel
  Print-KV -Key "trace_path"  -Value $tracePathRel
  Print-KV -Key "mp4_path"    -Value $mp4PathRel

  $meta = $null
  $status = $null
  $job = $null

  if ($metaPath)   { $meta   = Read-JsonFile -Path $metaPath }
  if ($statusPath) { $status = Read-JsonFile -Path $statusPath }
  if ($jobPath)    { $job    = Read-JsonFile -Path $jobPath }

  $meta = Normalize-RunMeta -Meta $meta
  $status = Normalize-RunStatus -Status $status -Meta $meta

  $cv = $meta.contract_version
  Write-Host ("contract_version={0}" -f $cv)

  if ($cv -ne $EXPECTED_CONTRACT_VERSION) {
    if ($AllowOldContract) {
      Write-Host ("WARN: contract_version mismatch: expected {0} got {1} (AllowOldContract enabled)" -f $EXPECTED_CONTRACT_VERSION, $cv)
      Write-Host "HINT: re-render with current core, or run with -AllowOldContract for inspection only."
      $traceCanon = ($meta.trace_path ?? "trace.txt")
      Print-RunSummaryLine -Level "WARN" -Meta $meta -Status $status -RunId $RunId -TracePath $traceCanon
      exit 0
    } else {
      Write-Host ("FAIL: contract_version mismatch: expected {0} got {1}" -f $EXPECTED_CONTRACT_VERSION, $cv)
      Write-Host "HINT: re-render with current core, or run with -AllowOldContract for inspection only."
      $traceCanon = ($meta.trace_path ?? "trace.txt")
      Print-RunSummaryLine -Level "FAIL" -Meta $meta -Status $status -RunId $RunId -TracePath $traceCanon
      exit 1
    }
  }

  $res = Lint-RunContract -Meta $meta -Status $status -AllowOld:$AllowOldContract
  if ($res.warns.Count -gt 0) {
    Write-Host "WARN: run contract lint warnings:"
    $res.warns | ForEach-Object { Write-Host ("  - {0}" -f $_) }
  }
  if ($res.errs.Count -gt 0) {
# --- BEGIN: downgrade fail->warn when AllowOldContract ---
if ($AllowOldContract) {
  try {
    function _Get-ArrRef([string[]]$names) {
      foreach ($n in $names) {
        $v = Get-Variable -Name $n -Scope 0 -ErrorAction SilentlyContinue
        if ($null -ne $v -and $v.Value -is [System.Collections.IEnumerable]) {
          return $v
        }
      }
      return $null
    }

    # Scriptte fail/warn listeleri hangi isimle geçiyorsa onu yakala
    $failVar = _Get-ArrRef @("fail","lintFail","contractFail","failLint","lint_fail","contract_fail","errs","errors","lintErrs","contractErrs","lint_errors","contract_errors")
    $warnVar = _Get-ArrRef @("warn","lintWarn","contractWarn","warnLint","lint_warn","contract_warn","warns","warnings","lintWarns","contractWarns","lint_warnings","contract_warnings")
    $failList = @()
    $warnList = @()

    if ($failVar) { $failList = @($failVar.Value) }
    if ($warnVar) { $warnList = @($warnVar.Value) }

    # Eski contract kaynaklı fail satırlarını WARN'a taşı
    $oldKeys = @(
      "contract_version mismatch",
      "run contract missing field: status.contract_version",
      "status contract_version mismatch",
      "meta.rc missing",
      "meta.artifacts_ok missing",
      "meta.mp4_bytes missing",
      "meta.mp4_path missing",
      "meta.trace_path missing",
      "status.state=unknown",
      "status.rc missing"
    )

    $moved = New-Object System.Collections.Generic.List[string]
    $keep  = New-Object System.Collections.Generic.List[string]

    foreach ($f in $failList) {
      $isOld = $false
      foreach ($k in $oldKeys) { if ($f -like "*$k*") { $isOld = $true; break } }
      if ($isOld) { $moved.Add([string]$f) } else { $keep.Add([string]$f) }
    }

    if ($moved.Count -gt 0) {
      foreach ($m in $moved) { $warnList += ($m + " (ignored: AllowOldContract)") }
      $failList = @($keep)
    }

    # Değişkenlere geri yaz
    if ($failVar) { Set-Variable -Name $failVar.Name -Scope 0 -Value $failList }
    if ($warnVar) { Set-Variable -Name $warnVar.Name -Scope 0 -Value $warnList }
  } catch {}
}
# --- END: downgrade fail->warn when AllowOldContract ---
    Write-Host "WARN: run contract lint warnings:"
    $res.errs | ForEach-Object { Write-Host ("  - {0}" -f $_) }
    if ($AllowOldContract) {
      Print-RunSummaryLine -Level "WARN" -Meta $meta -Status $status -RunId $RunId -TracePath ($meta.trace_path ?? "trace.txt")
      exit 0
    } else {
      Print-RunSummaryLine -Level "FAIL" -Meta $meta -Status $status -RunId $RunId -TracePath ($meta.trace_path ?? "trace.txt")
      exit 1
    }
  }

  $scv = $null
  try { $scv = $status.contract_version } catch { $scv = $null }

  if ([string]::IsNullOrWhiteSpace($scv)) {
    Write-Host "FAIL: run contract missing field: status.contract_version"
    Write-Host ("HINT: update run_store.status_started/status write to include contract_version='{0}'" -f $EXPECTED_CONTRACT_VERSION)
    if ($AllowOldContract) { exit 0 } else { exit 1 }
  }

  if ($scv -ne $EXPECTED_CONTRACT_VERSION) {
    Write-Host ("WARN: status contract_version mismatch: expected {0} got {1}" -f $EXPECTED_CONTRACT_VERSION, $scv)
    $hint = Contract-UpgradeHint -Got $scv -Expected $EXPECTED_CONTRACT_VERSION
    Write-Host ("HINT: {0}" -f $hint)
    if ($AllowOldContract) { exit 0 } else { exit 1 }
  }

  Write-Host ""
  Write-Host "RUN DOCS LOADED:"
  Print-KV -Key "meta_loaded"   -Value ([bool]$meta)
  Print-KV -Key "status_loaded" -Value ([bool]$status)
  Print-KV -Key "job_loaded"    -Value ([bool]$job)

  # Canonical run-store contract files (strict in RunId mode).
  $expected = @(
    "status.json",
    "meta.json",
    "video.mp4",
    "trace.txt",
    "layer1_stdout.txt",
    "layer1_stderr.txt"
  )
  $missing = @()
  foreach ($e in $expected) {
    $p = Join-Path $runDir $e
    if (!(Test-Path -LiteralPath $p)) { $missing += $e }
  }

  if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host ("FAIL: run contract missing files: {0}" -f ($missing -join ", "))
    Write-Host "HINT: Ensure renderer writes canonical artifacts into run dir (meta/status/trace/video/stdout/stderr)."
    if ($RunId) {
      Show-RunDiscoveryHint -RunDir $runDir -MaxItems 30 -MissingExpected $missing -TopCandidatesPerMissing 3
    }
    if ($AllowOldContract) { exit 0 } else { exit 1 }
  }

  $signals = Heuristic-ModulePathIssue -Cwd $cwd -CmdObj $cmd
  if ($signals) {
    Write-Host ""
    Write-Host ("HEURISTICS: {0}" -f ($signals -join ", "))

    if (($signals -contains "cmd_invokes_layer1_module") -and $gitRoot) {
      $absCwd = $null
      if ($cwd) { $absCwd = Normalize-AbsPath $cwd }

      if ($absCwd -and -not (Is-Under -Child $absCwd -Parent $gitRoot)) {
        Write-Host "WARN: cwd is not under git_root; module imports may fail."
        Write-Host "SUGGEST: ensure render runs with working directory at repo root:"
        Write-Host "         Set-Location $gitRoot"
        Write-Host "         python -m layer2.cli.render_job --job <job.json>"
      }
    }
  }

  $tracePath = Join-Path $runDir "trace.txt"
  if (!(Test-Path -LiteralPath $tracePath)) {
    $tracePathAlt = Join-Path $runDir "render_trace.txt"
    if (Test-Path -LiteralPath $tracePathAlt) { $tracePath = $tracePathAlt }
  }

  # trace canonical path display
  $traceCanon = "trace.txt"
  try {
    if ($meta.trace_path) { $traceCanon = $meta.trace_path }
  } catch {}

  # if everything passed so far:
  Print-RunSummaryLine -Level "OK" -Meta $meta -Status $status -RunId $RunId -TracePath $traceCanon

  # Only print trace tail if explicitly requested.
  if ($Verbose) {
    $tail = Tail-File -Path $tracePath -Lines 20
    if ($tail.Count -gt 0) {
      Write-Host ""
      Write-Host "TRACE TAIL (last 20 lines):"
      $tail | ForEach-Object { Write-Host "  $_" }

      $lastErr = Find-LastErrorLine -Lines $tail
      if ($lastErr) {
        Write-Host ""
        Write-Host ("LAST ERROR LINE: {0}" -f $lastErr)
      }
    }
  }
  if ($AllowOldContract) { exit 0 } else { exit 1 }
}

if (-not $Job) {
  if ($AllowOldContract) { Write-Warning "ALLOW_OLD_CONTRACT: usage: -Job <job_path>  OR  -RunId <run_id>" } else { Die "usage: -Job <job_path>  OR  -RunId <run_id>" }
}

$candidates = @()
if ([System.IO.Path]::IsPathRooted($JobInput)) {
  $candidates += $JobInput
} else {
  $candidates += (Join-Path -Path (Get-Location).Path -ChildPath $JobInput)
  $candidates += (Join-Path -Path $root -ChildPath $JobInput)
  if ($JobInput -match '^[\\/]*shorts_engine[\\/]+(.+)$') {
    $candidates += (Join-Path -Path $root -ChildPath $Matches[1])
  }
}

$resolved = $null
try {
  foreach ($cand in $candidates) {
    try {
      $resolved = (Resolve-Path -LiteralPath $cand -ErrorAction Stop).Path
      if ($resolved) { break }
    } catch {
    }
  }
} catch {
}
if (-not $resolved) {
  Die "job not found: input='$JobInput' candidates='$($candidates -join "; ")'"
}
$Job = $resolved

# Resolve shorts_engine root from this script location
Set-Location $root
if (!(Test-Path -LiteralPath $Job)) {
  Die "job not found after root switch: input='$JobInput' resolved='$Job'"
}

# 0) Schema validation gate (hard fail)
$schemaPath = Join-Path $root "layer2\schemas\job_v0_5.json"
if (!(Test-Path -LiteralPath $schemaPath)) {
  Die "missing schema: $schemaPath"
}

Info "→ schema validate (job_v0_5)"
$pySchemaCheck = @"
import json
import sys
from jsonschema import Draft202012Validator

job_path = sys.argv[1]
schema_path = sys.argv[2]

with open(job_path, "r", encoding="utf-8") as f:
    job = json.load(f)
with open(schema_path, "r", encoding="utf-8") as f:
    schema = json.load(f)

v = Draft202012Validator(schema)
errors = sorted(v.iter_errors(job), key=lambda e: list(getattr(e, "absolute_path", [])))
if errors:
    e = errors[0]
    path = ".".join(str(x) for x in list(getattr(e, "absolute_path", []))) or "$"
    msg = getattr(e, "message", None) or str(e)
    print(f"schema invalid at '{path}': {msg}")
    sys.exit(2)
print("schema valid")
"@

$schemaOut = $pySchemaCheck | python - $Job $schemaPath 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host $schemaOut
  Die "schema validation failed for job: $Job"
}
Info "OK: schema"

# 1) Compile checks
$filesToCompile = @(
  ".\layer2\cli\render_job.py",
  ".\layer2\cli\render_batch.py",
  ".\layer2\cli\clean_runs.py",
  ".\layer2\cli\jobset.py",
  ".\layer2\cli\gen_jobs.py",
  ".\layer2\cli\ideas.py",
  ".\layer2\cli\plan.py",
  ".\layer2\cli\report_kpi.py",
  ".\layer2\cli\publish.py",
  ".\layer2\cli\make_thumb.py",
  ".\layer2\cli\release.py",
  ".\layer2\cli\presets.py",
  ".\layer2\cli\lint.py",
  ".\layer2\cli\render_status.py",
  ".\layer2\core\run_store.py",
  ".\layer2\core\idea_store.py",
  ".\layer2\core\version.py",
  ".\layer2\core\lint_job.py"
)
foreach ($f in $filesToCompile) {
  if (!(Test-Path $f)) { Die "missing: $f" }
}

Info "→ py_compile"
python -m py_compile @filesToCompile
if ($LASTEXITCODE -ne 0) { Die "py_compile failed" }
Info "OK: py_compile"

# Explicit batch CLI compile gate (kept separate for clearer diagnostics)
python -m py_compile .\layer2\cli\render_batch.py
if ($LASTEXITCODE -ne 0) { Die "compile fail: render_batch.py" }

# 1.1) Contract smoke: render_batch must end with JSON line
$qaContract = ".\tools\qa_render_batch_contract.ps1"
if (!(Test-Path -LiteralPath $qaContract)) {
  Die "missing contract QA script: $qaContract"
}
Info "## contract smoke (render_batch stdout JSON)"
pwsh -NoProfile -ExecutionPolicy Bypass -File $qaContract -Module "layer2.cli.render_batch" -ArgsLine "--help"
if ($LASTEXITCODE -ne 0) {
  Die "qa_render_batch_contract failed"
}
Info "OK: contract smoke"

# 1.5) Examples validate gate
Info "## examples validate gate"
$exampleJobs = Get-ChildItem -LiteralPath ".\layer2\examples" -Filter "*.json" -File -ErrorAction SilentlyContinue
if (-not $exampleJobs -or $exampleJobs.Count -eq 0) {
  Die "no jobs under layer2\\examples"
}
foreach ($f in $exampleJobs) {
  python -m layer2.cli.render_job --validate-only $f.FullName
  if ($LASTEXITCODE -ne 0) {
    Die "invalid example job: $($f.Name)"
  }
}
Info "OK: examples valid"

# 1.6) Smoke render gate
Info "## smoke render (single)"
$smokeJob = ".\layer2\examples\min_job.json"
if (!(Test-Path -LiteralPath $smokeJob)) {
  Die "missing smoke job: $smokeJob"
}
python -m layer2.cli.render_job $smokeJob
if ($LASTEXITCODE -ne 0) {
  Die "smoke render failed"
}
Info "OK: smoke render"

# 1.7) Batch smoke gate
$smokeBatch = ".\tools\smoke_batch.ps1"
if (!(Test-Path -LiteralPath $smokeBatch)) {
  Die "missing smoke batch script: $smokeBatch"
}
Info "## smoke batch"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokeBatch
if ($LASTEXITCODE -ne 0) {
  Die "smoke_batch failed"
}
Info "OK: smoke batch"

# 1.8) Trace fallback smoke gate
$smokeTraceFallback = ".\tools\smoke_trace_fallback.ps1"
if (!(Test-Path -LiteralPath $smokeTraceFallback)) {
  Die "missing smoke trace fallback script: $smokeTraceFallback"
}
Info "## smoke trace fallback"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokeTraceFallback | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_trace_fallback failed"
}
Info "OK: trace_fallback_smoke"

# 1.9) Diagnosis trace fallback smoke gate
$smokeDiagnosisTraceFallback = ".\tools\smoke_diagnosis_trace_fallback.ps1"
if (!(Test-Path -LiteralPath $smokeDiagnosisTraceFallback)) {
  Die "missing smoke diagnosis trace fallback script: $smokeDiagnosisTraceFallback"
}
Info "## smoke diagnosis trace fallback"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokeDiagnosisTraceFallback | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_diagnosis_trace_fallback failed"
}
Info "OK: diagnosis_trace_fallback_smoke"

# 1.10) Determinism smoke gate
$smokeDeterminism = ".\tools\smoke_determinism.ps1"
if (!(Test-Path -LiteralPath $smokeDeterminism)) {
  Die "missing smoke determinism script: $smokeDeterminism"
}
Info "## smoke determinism"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokeDeterminism | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_determinism failed"
}
Info "OK: determinism_smoke"

# 1.11) Meta contract smoke gate
$smokeMetaContract = ".\tools\smoke_meta_contract.ps1"
if (!(Test-Path -LiteralPath $smokeMetaContract)) {
  Die "missing smoke meta contract script: $smokeMetaContract"
}
Info "## smoke meta contract"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokeMetaContract | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_meta_contract failed"
}
Info "OK: meta_contract_smoke"

# 1.12) Cache policy smoke gate
$smokeCachePolicy = ".\tools\smoke_cache_policy.ps1"
if (!(Test-Path -LiteralPath $smokeCachePolicy)) {
  Die "missing smoke cache policy script: $smokeCachePolicy"
}
Info "## smoke cache policy"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokeCachePolicy | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_cache_policy failed"
}
Info "OK: cache_policy_smoke"

# 1.13) Batch resume smoke gate
$smokeBatchResume = ".\tools\smoke_batch_resume.ps1"
if (!(Test-Path -LiteralPath $smokeBatchResume)) {
  Die "missing smoke batch resume script: $smokeBatchResume"
}
Info "## smoke batch resume"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokeBatchResume | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_batch_resume failed"
}
Info "OK: batch_resume_smoke"

# 1.14) Cleanup smoke gate
$smokeCleanup = ".\tools\smoke_cleanup.ps1"
if (!(Test-Path -LiteralPath $smokeCleanup)) {
  Die "missing smoke cleanup script: $smokeCleanup"
}
Info "## smoke cleanup"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokeCleanup | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_cleanup failed"
}
Info "OK: cleanup_smoke"

# 1.15) Jobset smoke gate
$smokeJobset = ".\tools\smoke_jobset.ps1"
if (!(Test-Path -LiteralPath $smokeJobset)) {
  Die "missing smoke jobset script: $smokeJobset"
}
Info "## smoke jobset"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokeJobset | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_jobset failed"
}
Info "OK: jobset_smoke"

# 1.16) Gen jobs smoke gate
$smokeGenJobs = ".\tools\smoke_gen_jobs.ps1"
if (!(Test-Path -LiteralPath $smokeGenJobs)) {
  Die "missing smoke gen jobs script: $smokeGenJobs"
}
Info "## smoke gen jobs"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokeGenJobs | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_gen_jobs failed"
}
Info "OK: gen_jobs_smoke"

# 1.17) Ideas smoke gate
$smokeIdeas = ".\tools\smoke_ideas.ps1"
if (!(Test-Path -LiteralPath $smokeIdeas)) {
  Die "missing smoke ideas script: $smokeIdeas"
}
Info "## smoke ideas"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokeIdeas | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_ideas failed"
}
Info "OK: ideas_smoke"

# 1.17.1) Plan smoke gate
$smokePlan = ".\tools\smoke_plan.ps1"
if (!(Test-Path -LiteralPath $smokePlan)) {
  Die "missing smoke plan script: $smokePlan"
}
Info "## smoke plan"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokePlan | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_plan failed"
}
Info "OK: plan_smoke"

# 1.17.2) KPI smoke gate
$smokeKpi = ".\tools\smoke_kpi.ps1"
if (!(Test-Path -LiteralPath $smokeKpi)) {
  Die "missing smoke kpi script: $smokeKpi"
}
Info "## smoke kpi"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokeKpi | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_kpi failed"
}
Info "OK: kpi_smoke"

# 1.18) Publish smoke gate
$smokePublish = ".\tools\smoke_publish.ps1"
if (!(Test-Path -LiteralPath $smokePublish)) {
  Die "missing smoke publish script: $smokePublish"
}
Info "## smoke publish"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokePublish | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_publish failed"
}
Info "OK: publish_smoke"

# 1.19) Thumb smoke gate
$smokeThumb = ".\tools\smoke_thumb.ps1"
if (!(Test-Path -LiteralPath $smokeThumb)) {
  Die "missing smoke thumb script: $smokeThumb"
}
Info "## smoke thumb"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokeThumb | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_thumb failed"
}
Info "OK: thumb_smoke"

# 1.20) Release build smoke gate
$smokeReleaseBuild = ".\tools\smoke_release_build.ps1"
if (!(Test-Path -LiteralPath $smokeReleaseBuild)) {
  Die "missing smoke release build script: $smokeReleaseBuild"
}
Info "## smoke release build"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokeReleaseBuild | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_release_build failed"
}
Info "OK: release_build_smoke"

# 1.21) Presets smoke gate
$smokePresets = ".\tools\smoke_presets.ps1"
if (!(Test-Path -LiteralPath $smokePresets)) {
  Die "missing smoke presets script: $smokePresets"
}
Info "## smoke presets"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokePresets | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_presets failed"
}
Info "OK: presets_smoke"

# 1.22) Lint smoke gate
$smokeLint = ".\tools\smoke_lint.ps1"
if (!(Test-Path -LiteralPath $smokeLint)) {
  Die "missing smoke lint script: $smokeLint"
}
Info "## smoke lint"
pwsh -NoProfile -ExecutionPolicy Bypass -File $smokeLint | Out-Host
if ($LASTEXITCODE -ne 0) {
  Die "smoke_lint failed"
}
Info "OK: lint_smoke"

# 2) Verification gate (preferred): verify.ps1 -Json
$verify = ".\tools\verify.ps1"
if (!(Test-Path $verify)) {
  Die "missing verify script: $verify"
}

Info "→ verify (JSON)"
$json = pwsh $verify -Job $Job -Json
if ($LASTEXITCODE -ne 0) {
  # verify already produced JSON, print it to help debug
  Write-Host $json
  Die "verify.ps1 failed (rc=$LASTEXITCODE)"
}

try {
  $r = $json | ConvertFrom-Json
} catch {
  Write-Host $json
  Die "verify output is not valid JSON"
}

if (-not $r.ok) {
  Write-Host $json
  Die "verification failed (ok=false)"
}

Info ("OK: verify (output={0}, bytes={1}, run_id={2}, cached={3})" -f $r.output_path, $r.output_bytes, $r.run_id, $r.cached)

# Artifacts check policy (HARD):
# runs/<run_id>/ artifacts are now expected in normal operation.
# - true  => OK
# - false => FAIL
# - null  => FAIL (runs not detected / not produced)
if ($r.artifacts_ok -eq $true) {
  Info "OK: run artifacts present (artifacts_ok=true)"
} elseif ($r.artifacts_ok -eq $false) {
  Die "run artifacts missing (artifacts_ok=false) — expected meta/trace under runs/<run_id>/"
} else {
  Die "run artifacts not detected (artifacts_ok=null) — runs/<run_id>/ expected in this workspace"
}

# 3) Optional: ensure docs exist (light gate)
$docs = @(
  ".\docs\run_store.md",
  ".\docs\verification.md",
  ".\docs\cli_contract.md",
  ".\docs\CACHE_POLICY.md",
  ".\docs\BATCH_FAILURE_POLICY.md",
  ".\docs\JOBSET_CONTRACT.md",
  ".\docs\JOB_GENERATOR.md",
  ".\docs\IDEAS_PIPELINE.md",
  ".\docs\PLANNING.md",
  ".\docs\KPI_REPORTING.md",
  ".\docs\RUNS_RETENTION.md",
  ".\docs\THUMBNAILS.md",
  ".\docs\RELEASING.md",
  ".\docs\PRESETS.md",
  ".\docs\LINT_POLICY.md",
  ".\CHANGELOG.md"
)
foreach ($d in $docs) {
  if (!(Test-Path $d)) { Die "missing docs: $d" }
}

# Optional docs quality warning (non-blocking):
# If RUN_STORE_CONTRACT.md exists, expect a "Required artifacts" heading.
$runStoreContract = ".\docs\RUN_STORE_CONTRACT.md"
if (Test-Path $runStoreContract) {
  try {
    $txt = Get-Content -LiteralPath $runStoreContract -Raw
    if ($txt -notmatch '(?im)^\s{0,3}#{1,6}\s+required artifacts\b') {
      Warn "docs warning: RUN_STORE_CONTRACT.md exists but no 'Required artifacts' heading found"
    }
  } catch {
    Warn "docs warning: failed to inspect RUN_STORE_CONTRACT.md heading"
  }
}

Info "OK: docs present"

Info "OK: release_check"
if ($AllowOldContract) { exit 0 } else { exit 1 }


function Assert-QcArtifactsOk {
  param(
    [Parameter(Mandatory=$true)][string]$RunDir
  )

  $meta = Join-Path $RunDir "meta.json"
  if (-not (Test-Path -LiteralPath $meta -PathType Leaf)) {
    throw "QC FAIL: meta.json missing: $meta"
  }

  $obj = Get-Content -LiteralPath $meta -Raw | ConvertFrom-Json

  if (-not $obj.qc) { throw "QC FAIL: meta.json missing qc section" }
  if ($obj.qc.artifacts_ok -ne $true) { throw "QC FAIL: qc.artifacts_ok != true" }
  if ($obj.qc.has_audio   -ne $true) { throw "QC FAIL: qc.has_audio != true" }
  if ($obj.qc.drift_ok    -ne $true) { throw "QC FAIL: qc.drift_ok != true" }

  "QC OK: artifacts_ok=true (has_audio=$($obj.qc.has_audio) drift_s=$($obj.qc.drift_s) max=$($obj.qc.max_drift_s))"
}

# --- QC Gate (latest run) ---
try {
  $runsRoot = "C:\dev\pc_motor\runs"
  if (Test-Path -LiteralPath $runsRoot) {
    $latest = Get-ChildItem -LiteralPath $runsRoot -Directory |
      Sort-Object LastWriteTime -Descending |
      Select-Object -First 1

    if ($latest) {
      Assert-QcArtifactsOk -RunDir $latest.FullName
    } else {
      "QC WARN: no runs dir entries found"
    }
  } else {
    "QC WARN: runs root not found: $runsRoot"
  }
} catch {
  throw $_
}


# --- ALLOW_OLD_CONTRACT_FORCE_RC0 ---
# Inspection-mode policy:
# If AllowOldContract is enabled, do NOT fail the whole script with rc=1.
# This is NOT a release gate; it is for inspecting older runs safely.
if ($AllowOldContract) {
  Write-Warning "ALLOW_OLD_CONTRACT: forcing rc=0 (inspection mode)."
  if ($AllowOldContract) { exit 0 } else { exit 1 }
}











