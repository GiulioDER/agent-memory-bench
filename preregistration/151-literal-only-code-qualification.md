# 151 Pass or fail qualification for literal-only SQL code repair

**2026-11-25, Europe/Rome.** Prediction recorded before model runs.

## Decision rule

I will mark the candidate **PASS** only if it gets at least 11 of
12 exact results, adds at least two correct results over plain review,
and loses none of the cases plain review gets right. Any completed
result that misses a condition is **FAIL**. A fail closes this
qualification and keeps plain review as the default. A pass supports
this narrow repair setup on the tested snapshots.

I predict FAIL under this rule. Study 150 found one gain and zero
losses on six seeded cases. That result falls below the minimum
improvement and leaves uncertainty about absolute accuracy. This
test makes an operational decision with fixed thresholds.

## Cases and method

I wrote 12 new count questions on the California schools and financial
SQLite snapshots. They cover four school questions and eight financial
questions. The cases use charter, virtual instruction, current status,
school ownership type, account statement frequency, loan status,
transaction operation, transaction purpose, card type, and disposition
codes. They include both unstored literals and stored codes that mean
something else. The questions are checked against study records from
137 through 150 for exact normalized duplicates.

Each draft starts with an exact query and one planted wrong literal.
I checked on the snapshot that the draft produces a different count
and replacing only that literal restores the reference. I verified
that the edit validator rejects added predicates and that the decision
code accepts the pass boundary and rejects each one-condition failure.
The fixed 12 cases include the weekly account-opening question whose
one matched note slot was used by the profiler for the opening date.

Both reviewers get the same question, schema and faulty draft.
Plain review keeps the Study 150 instructions and original
snapshot-verified BM25 notes. The treatment uses the same draft
field profiler and literal edit contract as Study 150. It returns
one JSON replacement and the scorer restricts it to the single
seeded literal. The reviewer receives no marker identifying which
literal is faulty, no reference SQL, and no database result rows.

The cap is three notes in either arm. Eleven pairs use three and
one uses one. The exact SQLite scorer counts clarifications, invalid
edits, query errors and nonmatching counts as incorrect. The 24
independent reviews use isolated gpt-6.2-sol at low reasoning effort,
with alternating arm order by case. I will score every pair once.

This is a controlled qualification run with deliberately planted
errors on two familiar databases. The decision applies to this
candidate on the test. The design does not estimate the frequency
of wrong-code defects in normal drafts or performance on other
snapshots.

Frozen review manifest SHA-256
`05c543344f5d6dc9d9a420d700202454baeefc9a4d6e14413b5aa1908415de01`.

From the archived artifact directory, replay the final score:

    $pin = (Get-Content review-pin.txt).Trim()
    python -B study.py score $pin

## Decision on 2026-11-25

**PASS.** The profiled literal-only reviewer got 12 of 12 exact
results. Plain review got 9 of 12. The candidate passed all three
registered conditions.

| Condition | Required | Observed | Status |
| --- | ---: | ---: | --- |
| Exact results with literal-only profiling | At least 11 of 12 | 12 of 12 | Pass |
| Gains over plain review | At least 2 | 3 | Pass |
| Losses against plain review | 0 | 0 | Pass |

I checked the reconstructed SQL against the reference SQL in every
case. All 12 applied edits restored the exact reference statement
through one literal change. The other tokens were preserved.

| Case | Plain review | Literal-only profiling |
| --- | --- | --- |
| Q04 Public high school ownership type | Kept the unstored label | Restored the exact stored label |
| Q07 Finished loans with no payment problems | Asked for the loan status code | Used `A` |
| Q10 Insurance transactions | Asked for the transaction field and code | Used `POJISTNE` |

Both arms got the other nine cases right. The affected field was
included in seven plain prompts and 11 profiled prompts. Q04 had
the relevant field in both prompts and no enumeration of stored
codes. On Q07 and Q10, only the profiled arm received the affected
field notes. Q06 passed both reviews with one note per arm.

The forecast was FAIL. The observed result exceeded the predicted
relative improvement and the minimum exact accuracy. The pass
qualifies the bounded repair tested here on 12 newly authored count
questions with one planted error each. It depends on the evaluator
knowing the allowed literal position. Ordinary draft error detection
and broader SQL repair remain outside the measured scope.

All 24 model receipts matched the frozen prompts and recorded a
completed turn. The prediction commit is `6d074935`. The result
SHA-256 is
`6dd72bb51e7fc3ed6a31d5a9cbbcc5f343206f43c045223f247da4f5f4cb88f3`.

## Published score summary

The [case-level score summary](../results/sql-literal-code-qualification-151/result.json) contains the paired outcomes and decision checks. The archived inputs and model receipts remain in the local study artifact. The preregistration commit quoted above identifies the original local prediction.

The published JSON uses LF line endings. Its SHA-256 is
`4c55b55c403a68503ca0a6280d23916b5d682326983f31ebcb95a9231bfb6a67`.
