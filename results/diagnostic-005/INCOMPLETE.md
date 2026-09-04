# INCOMPLETE: the host crashed, the run did not fail

Ended 2026-08-26 when Windows went down under memory pressure for the second time. Do not analyse
or report this partial grid; it is not the preregistered design. Superseded by the next run, which
launches inside a Job Object cap.

## State at the crash

```
records 129 | cells 32/72 | errors 1
recall wiring: WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW
spend $0.3093
  claude_md        12/32
  recall           11/32
  oracle_memory    27/32
  recall_prefetch  14/32
```

## Why this one is worth reading anyway

Every harness-level guard held right up to the moment the machine died. Recall wired on **every
single session, 32 for 32**, there were no retries, no cells discarded, and no cell proceeded short
on the memory gate. Nothing in the data is corrupt; there is simply less of it than the protocol
needs. The failure was entirely outside the harness, which is why the fix is a kernel-enforced cap
rather than more application logic.

The arm ordering at 32 of 72 cells was the same one seen in `diagnostic-003` and `diagnostic-004`:
oracle far ahead, prefetch next, and natural recall level with the static file rather than ahead of
it. Recorded here so a later reader can see whether the completed run reproduced it or overturned
it. Thirty-two of seventy-two cells decides nothing.

## What changed after it

* `C:\Users\gde00\.wslconfig` caps Docker's WSL2 backend at 3 GB. It was previously absent, which
  means uncapped at 50% of physical RAM, and was measured between 1.2 and 2.5 GB while competing
  with the run.
* `scripts/run_diagnostic_guarded.ps1` launches the run inside a Windows Job Object through
  procgov, with `--maxjobmem=5G -r`, so the benchmark is killed instead of the host and its child
  sessions die with the job instead of being orphaned.

Verified 2026-08-26: a 400 MB allocation succeeds unguarded and raises `MemoryError` under
`procgov --maxjobmem=200M`, so the cap is enforced by the kernel rather than merely declared.
