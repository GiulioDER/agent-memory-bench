# INVALID: do not pool with any valid run

Stopped 2026-08-25 at 152 of 288 sessions, 38 of 72 cells. Actual spend $0.364, confirmed against
OpenRouter usage (610.730 to 611.094).

Rename to `diagnostic-001-invalid-shared-recall-prompt` is PENDING: orphaned `claude` processes
that outlived the killed parent still hold this directory open on Windows.

## Why

Every `recall` session, on every task, received `ts-append-only`'s README as its static project
notes: one distinct `prompt_sha256` across all 24 tasks, against 24 distinct prompts for
`claude_md`, `oracle_memory` and `recall_prefetch`. A session working on `ts-crlf-export` was told
it was working in an "ops metrics ledger" repository.

`RecallAdapter` never overrode `build_for_task`, so it fell through to `build(session_dir,
namespace)`, which resolves its prompt at `staging_root/<namespace>/prompt.md` and writes it only
`if not prompt.is_file()`. In `scripts/diagnostic.py` both the staging root and the namespace are
constant across tasks, so the first task's bundle was baked in and the other 23 silently reused it.

Nothing raised. The sessions ran, the checkers scored them, and the admission gate admitted them.

## What that voids

The `recall` arm is not comparable, so three of the five preregistered contrasts are void:
`natural_memory_lift`, `access_gap` and `prefetch_gap`. `oracle_headroom` and
`prefetch_memory_lift` are unaffected in principle but are not reported from here, because the run
was stopped at 53% and a partial grid is not the preregistered design.

## What it does NOT affect

`pilot-003-deepseek` and `pilot-004-placebo` are clean: 24 distinct prompts per arm in both,
because `scripts/pilot.py` writes its prompts per task itself rather than through the adapter.

## Fixed by

`RecallAdapter.build_for_task`, a grid level refusal (`scripts.diagnostic.refuse_shared_prompts`)
that runs inside `--dry-run` before anything is paid for, and `prompt_sha256_by_task` on the
admission signals so the gate discards a session that ran with another task's bundle.
`tests/test_task_scoped_prompts.py` holds all of it; each guard was watched go red against the
mutation named in its docstring. Superseded by run `diagnostic-002`.
