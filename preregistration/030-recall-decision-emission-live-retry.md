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
