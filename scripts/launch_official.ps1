<#
.SYNOPSIS
  Launch the official run detached, so an interactive session ending cannot kill it.

.DESCRIPTION
  `abstention-002` lost 86 sessions when the session that launched it ended, which is why this
  exists and why it uses Start-Process rather than a background job: a job dies with its parent
  runspace, a started process does not. `setsid` and `nohup` are the equivalents on Linux and
  neither is available in Git Bash on this host, so the detachment is done here.

  Resume is the DEFAULT. A condition that already wrote admission.json is skipped; a condition
  interrupted mid-flight is refused by the runner and must be archived first with
  scripts/archive_partial.py, deliberately, because resuming a partial condition would mix two
  runs' sessions inside one condition.

  The two MemPalace variables are passed explicitly. They are never guessed by the adapter, and a
  detached process inherits only what this script sets, so omitting them would fail the MemPalace
  arm at its first cell with every other arm running normally.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/launch_official.ps1
#>

param(
  [string]$RunId       = "official-001",
  [string]$Namespace   = "bench-official",
  [string]$Conditions  = "absent,superseded,contradictory,adjacent",
  [string]$Arms        = "bare,placebo,claude_md,recall,mempalace",
  [int]   $Seeds       = 3,
  [string]$Model       = "deepseek/deepseek-v4-flash",
  # Frozen by preregistration 002 and matched by the bash launcher. Without these the run does
  # not start at all: pricing_from_args refuses before the first ingest, and Start-Process has
  # already reported success by then.
  [string]$PriceIn     = "0.0574",
  [string]$PriceOut    = "0.1148",
  [string]$PriceAsOf   = "2026-08-22",
  [string]$MemPalaceVenv = "C:/mpb/v",
  [string]$PalaceRoot    = "C:/mpb/palaces",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

# Refuse to launch rather than fail at the first cell. Each of these has cost a run.
if (-not $env:OPENROUTER_API_KEY) { throw "OPENROUTER_API_KEY is not set; the model calls would all fail." }
if (-not (Test-Path "$MemPalaceVenv/Scripts/python.exe")) { throw "no MemPalace venv at $MemPalaceVenv" }
if (-not (Test-Path $PalaceRoot)) { throw "no palace root at $PalaceRoot" }
if ($PalaceRoot.Length -gt 60) { throw "palace root is too long; onnxruntime fails to load from a deep path on Windows." }

$env:MEMPALACE_VENV        = $MemPalaceVenv
$env:MEMPALACE_PALACE_ROOT = $PalaceRoot
$env:PYTHONUNBUFFERED      = "1"   # so the log is readable while it runs, not only afterwards
# The official corpus is the ~4,900 document haystack, always. scripts/pilot.py refuses the
# run if what actually reached the arms is below this, BEFORE spending a session: corpora
# built without AMB_HAYSTACK published `sessions_offered: 207` and cost 94 discarded
# sessions and a rebuild. Unset means the check reports SKIP, which is right for a pilot
# (diagnostic-010 ran 125 sessions deliberately) and wrong for an official run.
if (-not $env:AMB_CORPUS_FLOOR) { $env:AMB_CORPUS_FLOOR = "4000" }

$logDir = Join-Path $repo "results/logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp  = Get-Date -Format "yyyyMMdd-HHmmss"
$out    = Join-Path $logDir "$RunId-$stamp.out.log"
$err    = Join-Path $logDir "$RunId-$stamp.err.log"

$argv = @(
  "-m", "scripts.abstention",
  "--run-id",     $RunId,
  "--namespace",  $Namespace,
  "--conditions", $Conditions,
  "--arms",       $Arms,
  "--seeds",      "$Seeds",
  "--model",      $Model,
  "--memory-instruction", "skill",
  "--resume",
  "--price-in",     $PriceIn,
  "--price-out",    $PriceOut,
  "--price-as-of",  $PriceAsOf
)
if ($DryRun) { $argv += "--dry-run" }

Write-Host "run id     : $RunId"
Write-Host "arms       : $Arms"
Write-Host "conditions : $Conditions x $Seeds seed(s)"
Write-Host "stdout     : $out"

# The PINNED interpreter, not PATH `python`. The read path and the write path must be one build
# of every dependency: `abstention-002` came up on a PATH python holding an editable worktree and
# refused the corpus with SchemaTooNew, which in a transcript is memory_call_count = 0 and is
# indistinguishable from a model that chose not to search.
$python = Join-Path $repo ".venv/Scripts/python.exe"
if (-not (Test-Path $python)) { $python = Join-Path $repo ".venv/bin/python" }
if (-not (Test-Path $python)) { throw "no bench venv at $repo/.venv; refusing to launch a run on PATH python" }

$proc = Start-Process -FilePath $python -ArgumentList $argv `
        -RedirectStandardOutput $out -RedirectStandardError $err `
        -WindowStyle Hidden -PassThru

$pidFile = Join-Path $logDir "$RunId.pid"
"$($proc.Id)" | Set-Content -Path $pidFile -Encoding ascii

# ⚠️ Start-Process returns as soon as the child STARTS, so "launched" is not evidence it is
# running. A missing price flag killed it at argument validation in under a second while this
# script printed a pid and an operator went away for the night. Look before reporting success.
Start-Sleep -Seconds 3
if ($proc.HasExited) {
  Write-Host ""
  Write-Host "THE RUN DID NOT START. It exited $($proc.ExitCode) within 3 seconds." -ForegroundColor Red
  if (Test-Path $err) { Get-Content $err -Tail 20 | ForEach-Object { Write-Host "  $_" } }
  Remove-Item $pidFile -ErrorAction SilentlyContinue
  exit 1
}

Write-Host ""
Write-Host "launched detached, pid $($proc.Id) (recorded in $pidFile)"
Write-Host "follow with : Get-Content '$out' -Wait -Tail 40"
Write-Host "stop with   : Stop-Process -Id $($proc.Id)"
