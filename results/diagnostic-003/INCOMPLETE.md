# INCOMPLETE: killed by the host, not by the harness

Killed 2026-08-26 at 67 of 288 session records, 15 of 72 cells. Spend $0.145. Superseded by
`diagnostic-004`. Do not analyse or report this partial grid; it is not the preregistered design.

## Cause

Windows terminated the run under low virtual memory. Both redirected log files are zero bytes,
which is the signature: the process died without flushing, so it was killed rather than raising.
The System log recorded five low-memory diagnostics between 09:40 and 10:12 naming `vmmemWSL`
(2.4 GB), `python.exe` (up to 1.6 GB), several `claude.exe` (~800 MB each), `ChatGPT.exe` (935 MB)
and `MsMpEng.exe` (709 MB).

Re-read them with:

    Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=(Get-Date).AddHours(-6)} |
      Where-Object { $_.ProviderName -match 'Resource-Exhaustion' } | Select-Object TimeCreated, Message

## What the data does say, and it is not nothing

The guards added after `diagnostic-001` and `diagnostic-002` all held right up to the kill:

* recall wiring `WWXWWWWWWWWWWWWXWW`: two startup failures in eighteen sessions, **both recovered
  by the retry** rather than costing a cell.
* One cell waited on the memory gate and **none proceeded short**.
* **Zero cells discarded**, against nine in pilot-004.
* Every arm carried its own per-task prompt.

So the harness converted a hostile host into a truncated run rather than a corrupted one. That is
the outcome the three guards were built for, and it is the reason this directory is marked
incomplete rather than invalid.

## Provisional arm counts, 15 cells, NOT a result

| arm | so far |
|---|---|
| oracle_memory | 15/16 |
| recall_prefetch | 9/16 |
| claude_md | 6/16 |
| recall | 4/15 |

Recorded only so that a later reader can see whether `diagnostic-004` reproduced the ordering or
overturned it. Fifteen of seventy-two cells decides nothing.
