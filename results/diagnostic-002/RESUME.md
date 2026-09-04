# diagnostic-002: stopped incomplete, resume tomorrow

Stopped 2026-08-26 at 00:20 local, 50 of 288 session records, 10 of 72 cells. Spend $0.092.
Do not analyse or report this partial grid; it is not the preregistered design.

## Why it was stopped

Host memory, not the harness. Free physical memory was **421 MB of 12,279**. The recall MCP server
loads fastembed before it can answer `initialize`, and on a starved host that start fails with
`{"name": "recall", "status": "failed"}` and an EMPTY `mcp_server_errors`, so the session runs with
no memory tools and the gate discards the cell.

Recall arm wiring in run order: `WWWWWW` then `X` almost continuously. Two cells
(`ts-base36-id` seeds 1 and 2) burned all three retry attempts without ever seeing a tool.

Killing every process the run owned recovered nothing, 471 MB to 422 MB, because the ~2 GB in
flight belonged to other work on the same box, including another session's pytest run. The run was
a victim of contention rather than its cause.

## What was learned that is worth keeping

The retry in `harness/memory_startup.py` is the right mechanism for a TRANSIENT and the wrong one
for a SHORTAGE: it triples the sessions spent on a cell that cannot succeed. Worse, the diagnostic
probe started another MCP server at the moment memory was scarcest, which is a feedback loop the
fix had to break.

It also worked, once, on the class it was built for: `ts-append-only` seed 1 `oracle_memory` hit a
provider `api_error` on attempt 1 and succeeded on attempt 2. Under the pilot-004 protocol that
cell would have been discarded.

## Fixed since

* `harness/host_memory.py` and `--min-free-mb` (default 1200): the runner waits for physical memory
  before each cell, records the wait in each record's `host_headroom`, and prints a line when it
  proceeds short rather than proceeding silently.
* The probe is skipped below the same threshold and records `probe_skipped` instead.
* `environment.json` now carries `min_free_mb` and `free_mb_at_start`.

## To resume

Free memory was back to ~2.4 GB once the other work finished. Check it first, then launch a fresh
run id. The database container `amb-diag-db` on `127.0.0.1:5564` is still up and both tenants of
namespace `bench-recall-diag002` hold 721 chunks each, so a re-ingest is only needed if a new
namespace is used.

    powershell -NoProfile -Command "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024)"

    $env:RECALL_DSN="postgresql://bench:bench@127.0.0.1:5564/bench"
    $env:PYTHONPATH="C:\Users\gde00\Documents\recall\.claude\worktrees\heading-contextualization-latest"
    python -m scripts.diagnostic --run-id diagnostic-003 --namespace bench-recall-diag003 \
        --model deepseek/deepseek-v4-flash --seeds 3 --timeout 600 --startup-attempts 3

Budget so far: $0.364 on `diagnostic-001` (invalid, shared prompt bug) plus $0.092 here, against a
$2.00 cap. A clean 288-session run is about $0.69.
