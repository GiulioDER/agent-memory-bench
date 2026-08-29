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
  "--resume"
)
if ($DryRun) { $argv += "--dry-run" }

Write-Host "run id     : $RunId"
Write-Host "arms       : $Arms"
Write-Host "conditions : $Conditions x $Seeds seed(s)"
Write-Host "stdout     : $out"

$proc = Start-Process -FilePath "python" -ArgumentList $argv `
        -RedirectStandardOutput $out -RedirectStandardError $err `
        -WindowStyle Hidden -PassThru

$pidFile = Join-Path $logDir "$RunId.pid"
"$($proc.Id)" | Set-Content -Path $pidFile -Encoding ascii

Write-Host ""
Write-Host "launched detached, pid $($proc.Id) (recorded in $pidFile)"
Write-Host "follow with : Get-Content '$out' -Wait -Tail 40"
Write-Host "stop with   : Stop-Process -Id $($proc.Id)"
