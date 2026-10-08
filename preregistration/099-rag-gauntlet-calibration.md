# 099 rag-gauntlet-calibration-001: can RE-call Lite certify an abstention threshold on a 47 KB corpus?

Status: frozen when committed. No calibration question is generated, and no calibration is fitted,
before the commit that adds this record.

## Context

RE-call Lite (branch `claude/lite-phase7`, `b85391ad`) indexed the four documents of the Kaggle
RAG Gauntlet (`rag-gauntlet-acme-rulebook-retrieval-challenge`) into 81 chunks on 2026-10-08 and
auto-calibrated on its own offline question set: 40 answerable and 40 unanswerable probes,
separability 0.906, 95% interval [0.838, 0.975], NOT certified (the bar, `MIN_SEPARABILITY` 0.90,
applies to the interval's lower bound). This study asks whether a realistic labelled question set
changes that, and builds the private dev set used to judge pipeline changes away from the public
leaderboard.

## Question

With the corpus and the embedder unchanged (81 chunks, `voyage:voyage-4`), does RE-call Lite's
`auto_calibrate` certify when it is given a realistic labelled set instead of its offline one?

## The question set, fixed before generation

- Written by ONE model call per batch to `google/gemini-3-flash-preview` (a different family from
  the answering model `anthropic/claude-opus-5.5`), whose input is the four corpus documents and
  the instructions, and NEVER `test.csv`.
- Target 90 answerable questions with a gold answer and the corpus label of the evidence, spread
  over all four documents and including multi-document and precedence questions; and 90
  unanswerable questions that are on topic and plausible but not answerable from the corpus,
  including near-miss codes, dates and numbers.
- Contamination filter, applied before any use: every generated question whose `voyage-4` cosine
  to ANY of the 23 hidden questions exceeds 0.85 is dropped, and duplicates within the set are
  dropped. The filter's counts are reported.
- Split: stratified by label and document, seed 20261008, into half A (calibration) and half B
  (private dev set). Half B is never used to fit anything.

## Endpoints

1. Primary: certification (yes or no), separability and its 95% interval, from
   `recall.lite.calibration.auto_calibrate(store, embedder, queries=half_A)`.
2. The fitted threshold, against 0.282 (offline set) and the 0.5 demonstration threshold.
3. Secondary, descriptive: the same calibration measured on half B as a held-out check of the
   threshold (answerable recall and unanswerable rejection at the half-A threshold).

## Predictions

1. Separability on half A is at least 0.93, and the interval's lower bound clears 0.90:
   CERTIFIED. Moderate confidence: realistic questions should separate better than templated
   probes, but the corpus is small and noisy (OCR, auto-transcript).
2. The certified threshold falls between 0.30 and 0.45.
3. On half B, at the half-A threshold, at least 85% of answerable questions pass and at least 70%
   of unanswerable ones are rejected.

## What would falsify this

Prediction 1 is falsified by separability below 0.93 or a lower bound below 0.90. Each
prediction is scored separately, and a miss stays in the record. If generation yields fewer than
60 questions per class after filtering, the run is reported as underpowered, not as a result.

## Confounds I can name now

1. Both question classes come from one generator, and its notion of "plausible but absent" may be
   easier or harder than the competition's traps.
2. I (the assistant running this) have read the 23 hidden questions. The generator has not, and
   the cosine filter is the guard; it cannot remove influence through the instructions, which are
   written to describe the corpus, not the hidden set.
3. Gold answers in half B are model-written and can be wrong; dev scores are noisy estimates.

<!-- results are appended below this line; everything above is frozen -->

## Result (2026-10-08)

**Status:** measured.

**The question set.** 180 questions from `google/gemini-3-flash-preview` (cost about $0.04),
4 dropped for cosine above 0.85 to a hidden question, 1 near-duplicate dropped, 175 kept (closest
kept question to any hidden one: 0.845). Half A: 44 answerable, 46 unanswerable. Half B: 41 and
44. A spot check of six per class found the labels sound; the unanswerable ones are hard
near-misses (details the corpus mentions but never states, such as a portal's URL).

| | predicted | measured |
|---|---|---|
| 1. separability on half A | at least 0.93, lower bound at least 0.90, certified | **0.713, interval [0.607, 0.820], NOT certified** |
| 2. threshold | 0.30 to 0.45 | **0.530** |
| 3a. half B answerable pass rate at the half-A threshold | at least 85% | **87.8%** (36/41) |
| 3b. half B unanswerable reject rate | at least 70% | **50.0%** (22/44) |

Held-out separability on half B was 0.790; median top cosine 0.641 for answerable questions
against 0.535 for unanswerable ones. Prediction 1 is falsified, prediction 2 is falsified,
prediction 3 is half met.

**The gap, and what it means.** I predicted that realistic questions would separate BETTER than
RE-call's offline probes (0.906). They separated far worse. The mechanism is visible in the
questions: a near-miss unanswerable question is built from the corpus's own vocabulary, so its
best match scores almost as high as an answerable question's. A top-cosine threshold measures
whether the corpus is ABOUT the question, not whether it STATES the answer, and on this set no
threshold separates the two. RE-call refused to certify, which is the right behaviour: its message
says no threshold separates the classes and moving one only trades one error for the other.
RE-call's own offline probes overstate separability on this kind of corpus, because their
unanswerable class is easier than real traps.

Consequence for the pipeline: abstention on near-miss questions cannot come from the retrieval
score; it has to come from reading the evidence (the answering model's insufficient_evidence
flag, or an entailment check). The store's calibration was replaced by this uncertified one; the
pre-099 store is kept as `~/rag-gauntlet/store.before-099.sqlite` on VPS2. Artefacts:
`~/rag-gauntlet/qset/` (generated.json, half_A.json, half_B.json, filter_report.json,
calibration_result.json, heldout_result.json).
