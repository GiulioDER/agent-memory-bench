# 031: RE-call decision data on the superseded condition

Status: DRAFT until committed; a committed record is frozen above the results marker.

## Question

On the official adversarial `superseded` condition, what decision, confidence, memory-call and
task-outcome data does the RE-call arm emit when the benchmark enables structured decisions?

## Preregistered grid

- Run ID: `recall-decision-superseded-20260903`
- Code: the committed benchmark checkout at `800917d`
- Condition: `superseded`, assembled with corpus seed `1`
- Selection: the official post-retirement selection, expected to contain 11 task-conditions
- Arms: `bare,recall` (bare is mandatory because damage is defined relative to it)
- Seeds: `5`, giving 55 paired cells and 110 sessions before discards
- Model: `deepseek/deepseek-v4-flash`
- Instruction: `protocol`
- Tenant: `bench-official-002-superseded`, the active official superseded generation
- Decision emission: enabled with `--emit-decisions`
- Prices: input `0.0574`, output `0.1148` USD per million tokens, as of `2026-08-22`

## Endpoints

1. Paired task success and damage outcomes for `recall` against `bare`.
2. The rate and distribution of explicit runtime decisions and numeric confidences.
3. RE-call search rate, memory-call count and retrieved-memory metadata.
4. Decision confidence versus the deterministic task checker, reported descriptively. This run
   is not by itself a calibration or AUC estimate.
5. Artifact integrity through the normal verifier.

## Prediction

The active tenant will pass preflight and the run will admit a substantial paired subset. RE-call
will emit structured decisions in most completed sessions that reach the end turn, with `answer`
and a numeric confidence. The decision fields will be persisted without using prose as evidence,
and the verifier will pass. The confidence distribution and correctness relationship are left as
measurements rather than predicted numerically.

<!-- results are appended below this line; everything above is frozen -->
