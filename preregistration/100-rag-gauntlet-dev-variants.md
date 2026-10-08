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
