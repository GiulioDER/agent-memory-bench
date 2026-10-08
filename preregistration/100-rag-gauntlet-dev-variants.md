# 100 rag-gauntlet-dev-001: do an answerability check and a wider context help, on a private dev set?

Status: frozen when committed. No pipeline variant is run on the dev set before the commit that
adds this record.

## Context

Preregistration 099 found that RE-call Lite's retrieval score cannot separate answerable from
near-miss unanswerable questions on the RAG Gauntlet corpus (separability 0.713), so abstention
must come from reading the evidence. Its half B (41 answerable, 44 unanswerable questions, written
from the corpus alone, never from `test.csv`) is the private dev set used here. The pipeline is
`answer.py` as it produced run 3 (public score 87.50): RE-call search with its evidence bundle,
abstain with no model call when RE-call abstains, one fixed precedence query, adjacent chunks
(+/-1), RE-call's generator-neutral prompt plus format rules, `anthropic/claude-opus-5.5`.

## Question

On the dev set, does either change raise the dev score over the run-3 pipeline: (V1) an
answerability check, a second model call that sees the question, the evidence and the proposed
answer and returns NOT_IN_CONTEXT unless the evidence explicitly states the answer; (V2) a wider
context, the model always sees RE-call's top 8 hits plus neighbours, not only those passing the
gate (RE-call's own abstention decision is unchanged)?

## Arms

`base` (run-3 pipeline), `V1`, `V2`, `V1+V2`, each run once on all 85 dev questions.

## Dev score, a copy of the competition's rule

Per question: unanswerable, 1.0 for exactly NOT_IN_CONTEXT; answerable, 1.0 when the answer is
equivalent to the gold answer, plus 0.5 when the cited labels share at least one label with the
gold citation (labels: slide N, page N, Amendment X-N, appendix X, clause numbers). Equivalence is
judged by `google/gemini-3-flash-preview` at temperature 0, given only the question, the gold and
the proposed answer. Dev score = 100 x points / max points. Reported with its components:
answerable accuracy, citation rate on correct answers, unanswerable abstention rate.

## Predictions

1. `base` dev score between 65 and 85.
2. V1 raises unanswerable abstention by at least 15 points over `base` and lowers answerable
   accuracy by at most 5 points; net dev score at least +3.
3. V2 raises answerable accuracy by at least 3 points over `base`, with unanswerable abstention
   within 5 points; net at least +2.
4. `V1+V2` scores highest of the four.

## Decision rule, fixed now

The arm with the highest dev score is submitted to the competition only if it beats `base` by at
least 3 points (about 2.5 dev questions); otherwise nothing new is submitted. One submission, at
most, follows this study.

## What would falsify this

Each prediction states its threshold. With 85 questions, a difference under 3 points is within
noise and is reported as no difference.

## Confounds I can name now

1. Gold answers and the judge are model outputs; the dev score is a noisy estimate, though the
   noise is shared by all four arms, which is what the comparison needs.
2. The dev questions come from the same generator as 099's calibration half, whose
   unanswerable class may be easier or harder than the competition's traps.
3. Each arm runs once; the answering model at temperature 0 can still vary between runs.

<!-- results are appended below this line; everything above is frozen -->

## Result (2026-10-08)

**Status:** measured. All four arms ran once, sequentially, on the 85 dev questions (12:41 to
13:28 UTC), and were scored together by `score_dev.py` with one shared judge cache.

| arm | dev score | answerable accuracy | citation rate on correct | unanswerable abstention | vs base |
|---|---:|---:|---:|---:|---:|
| base | 82.94 | 0.927 | 0.974 | 0.705 | |
| V1 | 83.41 | 0.902 | 0.973 | 0.750 | +0.47 |
| V2 | 84.83 | 0.927 | 0.974 | 0.750 | +1.89 |
| V1+V2 | 85.31 | 0.902 | 0.973 | 0.795 | +2.37 |

1. `base` between 65 and 85: **met** (82.94).
2. V1 abstention +15 or more: **falsified** (+4.5); answerable drop at most 5: met (-2.4);
   net +3 or more: **falsified** (+0.47).
3. V2 answerable +3 or more: **falsified** (0); abstention within 5 points: met (+4.5, at the
   edge); net +2 or more: **falsified** (+1.89).
4. `V1+V2` highest: **met**.

**Decision rule applied:** the best arm beats `base` by 2.37 points, under the 3-point bar.
Nothing new is submitted.

**The gap, and what it means.** I expected the answerability check to carry abstention and the
wider context to carry accuracy. Both moved abstention instead, by the same 4.5 points each, and
neither moved accuracy. A wider context helps the model see that the corpus does NOT state
something, which is the job I had assigned to the check. Combined they reach 79.5% abstention on
near-miss questions, against 50% for RE-call's retrieval threshold alone in 099: reading the
evidence is the better abstention signal, which is what 099 implied. The effects are within noise
for 85 questions, so this is a direction, not a finding.
Cost: about 1.66M input and 41K output tokens on `claude-opus-5.5`, roughly $7.5, plus the judge.

## Owner override (2026-10-08)

The owner asked to submit `V1+V2` despite the decision rule ("submit V1+V2 anyway"). Run on the
23 hidden questions it changed NO answer against run 3: the same 21 answers and the same two
NOT_IN_CONTEXT; only the wording of three free-text answers (hid-04, hid-14, hid-21) and some
citation lists differ. The answerability check rejected nothing and the wider context flipped
nothing. Submitted as run 4; its public score is recorded below when known. This override is not
evidence for the variants: whatever run 4 scores reflects citation-list differences, not the
mechanisms this study tested.
