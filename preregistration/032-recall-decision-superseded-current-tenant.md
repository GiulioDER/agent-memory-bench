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
## Result: 2026-09-03, completed superseded run

- Run: `recall-decision-superseded-current-tenant-20260903-superseded`
- Preparation: current feed fingerprint `0278cc651f14d9a5`; 207 sources and 1,226 chunks;
  generation built, calibrated, promoted and verified before model execution.
- Integrity: 110/110 session records and streams; the normal verifier passed. 54 of 55 paired
  cells were admitted; `(ts-base36-id, seed 3)` was discarded because the bare arm had an API
  error. Total recorded tokens: 5,439,438.
- Task outcomes among all 55 sessions per arm: bare succeeded 38/55; recall succeeded 38/55.
  On the 54 admitted paired cells, recall had 6 wins and 5 losses against bare, for a net
  success difference of +1 and no meaningful success advantage.
- RE-call mechanism: 20/55 sessions searched memory, for a search rate of 0.364. Among admitted
  recall records, 53/54 carried a structured decision, all `decision=answer`; one record had no
  observed decision.
- Decision confidence: the 53 observed recall scores ranged from 0.95 to 1.00, with mean
  0.996. The 38 successful scored sessions and 15 failed scored sessions both included only
  high-confidence answers; every failed scored session had confidence 1.00.
- Independent checker labels were used only after collection for the descriptive calibration
  analysis. On the 53 scored recall records: 38 answerable and 15 unanswerable. AUC was 0.421053
  with bootstrap 95% CI `[0.355263, 0.473684]`; Brier score was 0.283172 and ECE was 0.279057.
  The result was `uncertified`: the unanswerable class had fewer than the required 20 examples,
  and the AUC lower bound was below the 0.90 certification threshold. Runtime use is blocked.
- The observed-decision trace classified 53 recall records as `observed_only` and one as
  `not_observed`. It did not evaluate calibration, which was run separately with the checker
  labels above.

Conclusion: this run is ready for analysis and demonstrates that the benchmark records RE-call
decisions in the adversarial superseded condition. It also shows why emitting a confidence value
is not enough: this model was strongly overconfident, and the current sample is not certified for
runtime calibration or AUC use.
