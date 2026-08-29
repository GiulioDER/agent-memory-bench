# Launch the diagnostic inside a Windows Job Object, so the BENCHMARK dies instead of the HOST.
#
# Four runs died of memory on this 12 GB workstation, and two of them took the whole system down
# rather than just themselves. The harness already refuses to start a session below --min-free-mb,
# but an application-level check cannot bound what it has already allocated, and it cannot bound
# the claude.exe sessions and MCP servers it spawns as children. A Job Object can, because the
# kernel enforces it. This is the Windows counterpart of the `systemd-run --scope MemoryMax=8G`
# pattern already used for the VPS2 indexer.
#
# Two limits and why each is here:
#
#   --maxjobmem   committed memory for EVERY process in the job, not just the parent. Measured
#                 peak for four parallel arms was roughly 2.1 GB of working set; committed runs
#                 higher, so 5G leaves headroom while still capping the blast radius well below
#                 what took the machine down.
#   -r            apply the limits to child processes, and wait for them. This is also what fixes
#                 the orphaned claude.exe and python.exe processes that had to be hunted by hand
#                 three times: when the job closes, its children close with it.
#
#   --max-process-count is a runaway backstop, not a tuning knob. A grid of 72 cells times 4 arms
#                 never needs 60 live processes at once; if it asks for that, something is wrong.
#
# Usage:
#   pwsh -File scripts/run_diagnostic_guarded.ps1 -RunId diagnostic-006 -Namespace bench-recall-diag006
#
# Check free memory first. The harness waits below --min-free-mb, but starting a run on a box that
# is already short only converts money into waiting.

param(
    [Parameter(Mandatory = $true)][string]$RunId,
    [Parameter(Mandatory = $true)][string]$Namespace,
    [string]$Model = "deepseek/deepseek-v4-flash",
    [int]$Seeds = 3,
    [int]$Timeout = 600,
    [int]$StartupAttempts = 3,
    [int]$MinFreeMb = 2000,
    [int]$HeadroomTimeout = 3600,
    [string]$MaxJobMem = "5G",
    [int]$MaxProcessCount = 60,
    [string]$Dsn = "postgresql://bench:bench@127.0.0.1:5564/bench",
    [string]$RecallPath = "C:\Users\gde00\Documents\recall\.claude\worktrees\heading-contextualization-latest"
)

$ErrorActionPreference = "Stop"
$bench = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command procgov -ErrorAction SilentlyContinue)) {
    throw "procgov is not on PATH. Install with: winget install LowLevelDesign.ProcessGovernor"
}
if (-not $env:OPENROUTER_API_KEY) {
    throw "OPENROUTER_API_KEY is not set in this shell"
}
if (Test-Path (Join-Path $bench "results\$RunId\records.jsonl")) {
    throw "results\$RunId already holds records; choose a fresh --RunId"
}

$os = Get-CimInstance Win32_OperatingSystem
$freeMb = [math]::Round($os.FreePhysicalMemory / 1024)
$commitFreeMb = [math]::Round($os.FreeVirtualMemory / 1024)
Write-Output ("free physical {0} MB, free commit {1} MB, job cap {2}" -f $freeMb, $commitFreeMb, $MaxJobMem)
if ($freeMb -lt $MinFreeMb) {
    Write-Warning ("only {0} MB free against a {1} MB gate: the run will WAIT before its first cell" -f $freeMb, $MinFreeMb)
}

$env:RECALL_DSN = $Dsn
$env:PYTHONPATH = $RecallPath
$env:RECALL_EMBEDDER = "fastembed"
# Both caps are load-bearing: an unbounded fastembed batch asked onnxruntime for 288 MB in one
# allocation and was refused, killing a run during ingest.
$env:RECALL_INDEX_BATCH_CHUNKS = "8"
$env:RECALL_FASTEMBED_BATCH = "8"

$procgovArgs = @(
    "--maxjobmem=$MaxJobMem",
    "--max-process-count=$MaxProcessCount",
    "-r",
    "--job-name=agent-memory-bench-$RunId",
    "python", "-m", "scripts.diagnostic",
    "--run-id", $RunId,
    "--namespace", $Namespace,
    "--model", $Model,
    "--seeds", "$Seeds",
    "--timeout", "$Timeout",
    "--startup-attempts", "$StartupAttempts",
    "--min-free-mb", "$MinFreeMb",
    "--headroom-timeout", "$HeadroomTimeout"
)

$log = Join-Path $bench "results\$RunId.log"
$err = Join-Path $bench "results\$RunId.err.log"
Write-Output ("procgov {0}" -f ($procgovArgs -join " "))
$p = Start-Process -FilePath "procgov" -ArgumentList $procgovArgs -WorkingDirectory $bench `
    -RedirectStandardOutput $log -RedirectStandardError $err -NoNewWindow -PassThru
Write-Output ("launched {0} under procgov as pid {1} at {2}" -f $RunId, $p.Id, (Get-Date -Format HH:mm:ss))
Write-Output ("logs: {0}" -f $log)
