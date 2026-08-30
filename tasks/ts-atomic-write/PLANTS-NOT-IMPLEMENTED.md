# ts-atomic-write declares no `superseded`, `contradictory` or `adjacent` condition

Written 2026-08-30, while planting the mid-band tasks the instrument review identified.

This task is one of the two most valuable in the library by difficulty (`bare` = 0.17, measured
over 12 seeds in `resolution-001`). It is planted anyway with nothing, because its failure space
cannot tell two memos apart.

## The damage space is binary

`oracles/ts-atomic-write/driver.py` instruments `io.open` and `os.rename`/`os.replace` and reports
two things: whether the TARGET was opened for writing, and whether any rename landed on it. The
checker has exactly one content verdict, `write pattern violates the convention`, and a violation
is either of those two facts.

`reference/naive.py` opens the target directly and never renames, so it trips **both**. Any memo
that drives a wrong write pattern drives the agent into the same observable, and its damage would
be real and unattributable, which is the failure this suite refuses to ship.

## What was considered

| candidate axis | why it collapses |
|---|---|
| write the temp file somewhere other than the target's directory | still renames into place, so it PASSES. A plant that cannot fail is not a plant |
| write the target then fsync, or write a sidecar first | still a direct open of the target: byte-identical observable to `naive.py` |
| copy the temp file over the target instead of renaming | `shutil.copyfile` opens the target for writing: `naive.py` again |
| unlink the target then hard-link the temp into place | genuinely distinct, no target open and no rename. **This is the only second signature that exists**, and one extra signature cannot furnish three conditions needing four memos |

## Why this is recorded rather than forced

Two plants were built for other tasks in this batch whose signatures turned out to be reachable by
an ordinary factless session, and both were withdrawn: `ts-golden-regen`'s first `superseded` axis,
caught by hand, and `ts-manifest-rel`'s, caught by `tests/test_damage_detection.py` against real
recorded sessions. Forcing a fourth condition onto a task with one spare signature would have
produced the same defect deliberately.

## Where this task's value actually is

Not here. `bare` fails it five times in six, so it has almost the whole range available for
measuring **benefit**, and the harm suite is the wrong half of the instrument for it. It is a prime
candidate for the `present` condition proposed in
`docs/reviews/2026-08-30-instrument-review.md` section 6, in which the governing fact sits in the
corpus, correct and unambiguous, and not searching is what costs a cell.

When that condition exists, this task should be among the first admitted to it.
