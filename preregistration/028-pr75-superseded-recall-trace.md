# 028: pr75-superseded-recall-trace, does the live recall arm emit usable runtime decisions?

Status: DRAFT until committed; a committed record is frozen above the results marker.

Written 2026-09-03, before the first session.

## Question

Can the merged PR75 instrumentation run on VPS2 for the retained `superseded` condition, and do
the live recall sessions expose explicit structured decisions that the trace evaluator can use?

This is a plumbing and observability probe. It is not a paired outcome comparison, because it runs
only the `recall` arm and therefore cannot compute damage against `bare`.

## Frozen run shape

The run uses the current `origin/master` commit, the `recall` arm only, the `superseded` condition,
the `skill` instruction, model `deepseek/deepseek-v4-flash`, corpus seed 1 and three session seeds.
The current task selector retains 11 tasks after the recorded superseded retirements, for 33
sessions. The run uses a new namespace and result directory, separate from official-003.

## Predictions

1. The remote recall preflight succeeds and all 33 sessions complete without a dead MCP server.
2. The recall search rate is at least 0.65, matching the prior mechanism threshold recorded for
   this instruction.
3. Most sessions have `runtime_decisions` with status `not_observed`. The current benchmark prompt
   does not require the model or recall search payload to emit an explicit `{"decision": ...}`
   event, and PR75 deliberately does not infer decisions from final prose or from
   `abstained: true` alone. If this prediction holds, PR75 is wired correctly but the current
   benchmark is not yet a calibration dataset.
4. No session reports a calibration result as certified. Calibration requires externally supplied
   answerability labels and a held out labelled set, which this single arm run does not provide.

## Analysis rules

Report session completion, MCP search rate, the recorded runtime decision statuses, and the PR75
contract output. Do not call `not_observed` a behavioral failure, do not estimate AUC from this
run, and do not use the recall only success rate as a replacement for the preregistered paired
endpoints.

<!-- results are appended below this line; everything above is frozen -->
