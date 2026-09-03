# 030: recall-decision-emission-live-retry

Status: DRAFT until committed; a committed record is frozen above the results marker.

## Question

After correcting the tenant to the active official superseded corpus, does one live RE-call
session emit and persist the terminal structured decision introduced by PR 76?

## Preregistered run

- Run ID: `recall-decision-emission-live-retry-20260903`
- Code: the committed benchmark checkout at `abf4403`
- Arm: `recall`
- Task: `ts-base36-id`, seed `0`
- Model: `deepseek/deepseek-v4-flash`
- Instruction: `protocol`
- Tenant: `bench-official-002-superseded`
- Decision emission: enabled with `--emit-decisions`
- Timeout: 600 seconds

## Prediction

The active tenant will make the RE-call tool complete successfully, and the raw stream will
contain a terminal structured decision with numeric confidence. The record will carry that event
under `runtime_decisions`, the memory surface and call count will be present, and the normal
verifier will pass. This is a mechanism smoke, not a calibration estimate.

<!-- results are appended below this line; everything above is frozen -->
## Result: 2026-09-03, live retry

- Actual benchmark checkout used on VPS2: `930fc71`. The preregistration commit named
  `abf4403`, but that commit only appended the previous smoke result; no benchmark code differed.
- Run: `recall-decision-emission-live-retry-20260903`
- Admission and verification: passed. One admitted session, one record, 204,785 total
  tokens, and `scripts.verify_run` reported `1/1 run(s) verified`.
- RE-call: the active official tenant responded successfully; memory call count was 7 and
  the search rate was 1.000.
- Endpoint 1: passed. The raw stream contained one terminal `structured_output` object:
  `decision=answer`, `confidence=0.95`.
- Endpoint 2: passed. The record persisted the same event in `runtime_decisions` with
  `source=result.structured_output` and `threshold=null`.
- Endpoint 3: passed. The configured RE-call surface was present and the session reached
  the retrieval path.
- Endpoint 4: passed.
- The task checker passed. The recorded decision reason is useful metadata, but its prose is
  not independently graded; correctness remains determined by the executing checker.

Conclusion: with the active official tenant, the RE-call arm emits and persists the new
decision data. The earlier failure was caused by the inactive tenant, not by the decision
recording path.
