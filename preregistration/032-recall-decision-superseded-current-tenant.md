# 032: RE-call decision data on a freshly prepared superseded tenant

Status: DRAFT until committed; a committed record is frozen above the results marker.

## Question

Can the full `superseded` condition be rerun with RE-call decision emission after preparing a
tenant whose generation is fingerprint-matched to the current benchmark feed?

## Preregistered grid

- Run ID: `recall-decision-superseded-current-tenant-20260903`
- Code: the committed benchmark checkout at `86af0ea`
- Condition: `superseded`, corpus assembly seed `1`
- Selection: the official post-retirement 11 task-conditions
- Arms: `bare,recall`
- Seeds: `5`, giving 55 paired cells and 110 sessions before discards
- Model: `deepseek/deepseek-v4-flash`
- Instruction: `protocol`
- Tenant: `bench-recall-decision-current-20260903-superseded`
- Decision emission: enabled with `--emit-decisions`
- Prices: input `0.0574`, output `0.1148` USD per million tokens, as of `2026-08-22`

The tenant is new and isolated. Its generation must be built, calibrated, promoted and stamped
against the current feed fingerprint before any model session starts.

## Endpoints

1. Paired task success and damage outcomes for `recall` against `bare`.
2. Per-session decision, confidence and reason fields from `runtime_decisions`.
3. RE-call search rate, call count and retrieval metadata.
4. Descriptive relationship between confidence and the deterministic checker, without treating
   this run as a calibrated AUC estimate.
5. Artifact integrity through the normal verifier.

## Prediction

Tenant preparation and preflight will pass. The run will admit a substantial paired subset, and
most completed RE-call sessions will emit a terminal structured `answer` decision with numeric
confidence. The verifier will pass. Outcome and confidence distributions are left as measurements.

<!-- results are appended below this line; everything above is frozen -->
