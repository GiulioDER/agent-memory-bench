# 026: official-003, the full roster under the fair instruction

⚠️ **Registered MID RUN, and that weakens it. Stated here rather than hidden.**
`official-003` launched 2026-09-01 16:09 UTC and this record is written the same evening with
roughly 500 of 2,920 sessions on disk. No comparison, no contrast, no solved count and no p value
has been computed for it, by me or by anything else, so the predictions below are unseen with
respect to every quantity they name. They are NOT unseen with respect to data collection, which a
proper preregistration would be. Treat this as weaker evidence than 020 or 021 and do not cite it
as though it were written before launch.

**Why it exists at all.** The run it re-measures, `protocol-025`, had no preregistration either,
and its numbers are already published in a public article. That is the situation this rule was
written to prevent, so the least bad remaining move is to fix the prediction before the answer
exists rather than after.

## What is being measured

The approved roster, eight arms, under `--memory-instruction protocol`:
`bare`, `placebo`, `claude_md`, `protocol`, `fs_grep`, `recall`, `mempalace`, `recall_prefetch`.
73 task-conditions x 5 seeds x 8 arms = 2,920 sessions, five corpus conditions, deepseek-v4-flash.

Every run before 2026-09-01 hardcoded `--memory-instruction skill` with no override, giving
`recall` 1,958 bytes over the shared protocol against `mempalace`'s 853. Under `protocol` every
memory arm gets one shared document plus its own capped result-schema appendix: measured at launch
as 4,021 / 4,207 / 4,325 bytes for `fs_grep` / `recall` / `mempalace`.

## ⛔ This run CANNOT reproduce protocol-025, and that is structural

A cell is admitted only when **every** arm produced a record. `protocol-025` ran four arms and
admitted 358 cells. This runs eight, so each additional arm is another way to lose a whole cell.
The admitted set will be smaller and it will be a **different set**, not a subset with noise on it.

So a numerical difference from 025 is expected and is not evidence of anything. Only **direction**
and **significance** are comparable, and only loosely.

## Predictions

Written knowing I over-predict effect magnitudes: eleven of twelve prior predictions were
falsified, every one too high by two to four times. These are deliberately hedged downward.

| # | Claim | Prediction | Confidence |
|---|---|---|---|
| P1 | admitted cells | fewer than 358; between 250 and 330 | 0.70 |
| P2 | `recall` vs `protocol`, direction | positive | 0.80 |
| P3 | `recall` vs `protocol`, significance | p < 0.05 | **0.45** |
| P4 | `recall` vs `bare`, direction | positive | **0.55** |
| P5 | `recall` vs `bare`, significance | p < 0.05 | 0.15 |
| P6 | `protocol` vs `bare`, direction | negative | 0.75 |
| P7 | `protocol` vs `bare`, significance | p < 0.05 | 0.35 |
| P8 | `mempalace` vs `protocol` | \|net\| < 10 cells, no significance | 0.70 |
| P9 | `recall` vs `mempalace`, direction | positive | 0.75 |
| P10 | `mempalace` searches more often than `recall` | holds | 0.80 |
| P11 | `present` is `recall`'s largest gain over `protocol` | holds | 0.65 |

**P4 is the one to watch and I have put it at 0.55 on purpose.** In `protocol-025` `recall` beat
`bare` by three cells of 358 at p = 0.834, which the published article itself calls "nothing". A
three-cell margin on a different admitted set is a coin flip. I expect roughly even odds of the
sign flipping, and I am saying so before I can see it.

## What counts as contradicting the published article, decided now

The article at `dev.to/gde03/...-what-it-costs-to-ask-for-one-5351` makes claims of three grades.
Handling is fixed here so it is not improvised later.

| Grade | Claim | If official-003 disagrees |
|---|---|---|
| **Hedged in the body** | `recall` vs `bare` is +3 at p = 0.834, "which is nothing" | **no correction owed.** The article already says this is not a result. A sign flip confirms the hedge rather than refuting the piece. |
| **Load bearing** | `recall` vs `protocol` is the only comparison clearing p < 0.05 | **correction owed** if the direction flips, or if it fails significance while another arm reaches it. Publish a follow-up naming the number, do not quietly amend. |
| **Framing** | "the only arm that beats doing nothing", and the banner "Only one beat having none" | **correction owed if P4 flips**, because the banner asserts what the body hedges. The banner is the least defensible artefact in the set and it is the one that would need withdrawing. |

⚠️ **The leaderboard must carry `official-003`, not `protocol-025`.** The board is currently live
with the eight-arm roster and every number null. Filling it from 025 to match the article would be
publishing the weaker run because it flatters, which is the failure this file exists to stop.

## Falsification

The run is falsified as a fair-instruction measurement, independent of any result, if the shipped
instruction sizes for the three memory arms do not match the launch-time assertion, or if
`assert_shared_protocol` did not hold. Note honestly: instruction size is **not** in the record
schema, so this is verifiable only from the launch-time dry run and the harness assertion, not
from the records. That is a gap in the harness and it should be closed by recording the
instruction digest per session.

---

## 🔁 Correction, same evening, before any result: the falsification clause above is WRONG

The section above says instruction size "is **not** in the record schema, so this is verifiable
only from the launch-time dry run and the harness assertion, not from the records", and calls that
a gap to close by recording a digest per session.

**It is already recorded, per arm, with digests.** I looked for `instruction_bytes` in
`records.jsonl`, did not find it, and concluded it was unrecorded, without opening
`environment.json`, which every condition writes at its start. That file carries
`instruction_manifest` (bytes, chars and sha256 per arm), `instruction_excess_bytes`, and
`instruction_arms_matched`.

The correction is left as an append rather than an edit, per the standing rule, and the wrong
claim above is the more informative artefact: it is the FOURTH time in this project that I have
read metadata about an artefact instead of the artefact, and the first three cost a closed
research lane and two wrong statements about instruction asymmetry.

Measured from `results/official-003-present/environment.json`, live:

| arm | total bytes | excess over shared protocol |
|---|---:|---:|
| mempalace | 4,325 | 853 |
| recall | 4,207 | **735** |
| fs_grep | 4,021 | 549 |
| protocol | 3,610 | 138 |

`instruction_arms_matched: True`. Every arm's total minus its excess is **3,472**, so the shared
protocol is byte identical across all four, which is the fairness claim and it holds.

🔑 **The direction of the old confound is reversed, not merely reduced.** Under `skill`, `recall`
carried 1,958 excess bytes against `mempalace`'s 853. Under `protocol` it carries **735 against
853**, so if any arm now holds a coaching advantage it is MemPalace, by 118 bytes of its own
result-schema appendix. The predictions above were written before I knew this and are unchanged.

---

## Appended 2026-09-02: the exact code this run executed

Recorded because it had to be DERIVED rather than read, which is itself the finding. The run's
working tree was dirty, so the launcher's own `commit : bb25d343` line describes a tree that was
modified and would not reproduce the run.

⚠️ This append changes the file's hash after `preregistration/timestamps/manifest-20260901T220358Z.json`
stamped it at `f95223d37fafaad309db0f0cf09341e617655f9e`. That is the documented and expected case:
`timestamp_prereg.py verify` reports CHANGED for a file appended below a frozen prediction, and the
stamped bytes stay provable through the recorded git blob `1d3c1d213e277d19969d885f78c5b8d6b36a42c9`.
Nothing above this line was edited.

### What ran

| component | state | on master's main line |
|---|---|---|
| harness, adapters, `pilot.py`, `abstention.py` | `bb25d343` (2026-08-31T19:13:35+02:00) | yes, ancestor |
| `scripts/launch_official.sh` | byte-identical to `a3fb01b` (2026-09-01T11:20:58+02:00) | yes, ancestor |

Established by sha256 over the LF-normalised file, not by reading the diff: VPS2's launcher hashes
to the same value as `a3fb01b:scripts/launch_official.sh`. Against current master it differs by
exactly six lines, the `AMB_CORPUS_FLOOR` export added by PR #59 **after** this run launched.

Launched 2026-09-01T16:09:46Z.

### The drift, and why it does not touch the measurement

Forty-two commits separate `bb25d343` from master; five touch the measurement path. Three landed
AFTER launch and are irrelevant by construction (`2c9dd7b`, `567fdc9`, `b143d0c`). Two existed
BEFORE launch and are genuinely absent from this run:

- **`ce292e8`**, "Add the `draft` protocol variant, and make it a protocol rather than a prompt"
- **`a7fdeba`**, "Make corpus lineage expressible"

The first is the one that could have mattered, because it refactored `harness/instructions.py`,
which composes the instruction this entire run exists to equalise. **It does not.** Measured:

```
master portable_protocol base bytes: 3472
run recorded (environment.json):     3472
git log bb25d343..master -- adapters/_shared/memory_protocol.md   ->  (empty)
```

`ce292e8` only ADDED `memory_protocol_draft.md` and widened the plumbing; the shared protocol text
was never touched, and the `protocol` variant composes identically on both. So the instruction this
run shipped is byte-identical to the one master would ship today. `a7fdeba` is corpus construction
and the corpora were built before it.

### Integrity evidence, not assertion

- `verify_run` on `official-003-present`: discard set re-derives (24 cells), admitted count
  consistent (111 against a published 111), **every admitted cell carries all 8 required arms**,
  1,080 streams for 1,080 records.
- All five conditions pass all seven setup checks with zero skips: shared protocol 3,472 bytes
  identical across every instruction-carrying arm, corpus reached the arms at 4,888 to 4,911.
- Errors 19 of 2,477 top-level (0.8%), spread across five arms including `bare` and `placebo`, so
  not systematic to any product. Arm balance spread 3.

### To reproduce

```bash
git checkout bb25d343
git checkout a3fb01b -- scripts/launch_official.sh
MEMORY_INSTRUCTION=protocol RUN_ID=official-003 bash scripts/launch_official.sh
```

🔑 **The lesson, which is the reusable part: a run's recorded commit is not its provenance while
the tree is dirty.** The launcher prints `git rev-parse --short HEAD` and says nothing about
modification, so a run executed from a patched checkout publishes a hash that misdescribes it. The
harness should refuse a dirty tree for an official run, or record `git status --porcelain` beside
the commit. It currently does neither.
