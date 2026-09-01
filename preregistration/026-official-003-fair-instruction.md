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
