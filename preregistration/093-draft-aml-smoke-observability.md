# Draft 093: AML Coding Smoke query-shape observability

Status: draft planning record only. It does not authorize an AML Smoke or Full run.

## Question

Can a frozen RE-call version demonstrate that its intended retrieval mechanisms activate for the
official Coding Search request shape, without retaining private evaluation content or adapting the
submitted version to held-out questions?

## Contract interpretation

AML makes one logical Search per Coding question with the original benchmark question, exact
`user_id`, and formal `top_k`; identical transport retries remain possible. The participant returns
ranked evidence. The platform owns Answer and Eval. This is not an agent-controlled sequence of
memory searches, so no post-first-search instruction or additional tool call is part of the
official surface.

Smoke is a compatibility mode. It is private, nonpublishable, limited to one run per hour and 30
runs per track for the edition. AML says evaluation data and derived copies may be used only for
the current job, not product analytics, training, dataset reconstruction, or redistribution. The
participant must avoid unnecessary request-body logging and delete job data within 30 days.

## Required organizer clarification

Before implementation or execution, obtain written confirmation that the participant may compute
and retain content-free aggregate diagnostics from its own Add and Search endpoints during Smoke.
If that is not permitted, collect only ordinary health, contract, latency, and error telemetry and
close this lane.

## Local precondition: query-shape compatibility

Do not use private Smoke questions to design retrieval. Before Smoke, a separate local
preregistration should compare the exact committed Coding task prompt against bounded,
deterministic query facets for requested behavior, symptoms, paths and symbols, errors, tests,
commands, and architectural constraints. It should independently test grounded Add-time retrieval
aliases such as task shape and symptom wording on typed records.

Every candidate keeps an exact-query raw rescue branch. Candidate lists are fused with fixed
weights and quotas. Promotion requires broad activation, strict preservation of rank 100 coverage,
an early-rank or coverage improvement, bounded latency and returned context, and a later executable
Task Solve improvement. The mechanism still returns source-grounded evidence, never an answer.

## Frozen-before-Smoke measurements

The eventual frozen protocol may retain only run-level or distribution-level aggregates:

1. Query character count and a declared local token count.
2. Counts of path-like strings, symbols, errors, commands, tests, and configuration keys.
3. Presence of options, requested `top_k`, retries, latency, fallback, and item count.
4. Returned characters and tokens by rank bucket and an estimate of Search-candidate consumption
   within the published 117,760-token Answer input budget.
5. Raw versus typed candidate mix, source-session diversity, and exact identifier overlap between
   query and returned evidence, computed online.
6. Activation counters for every submitted retrieval mechanism and whether each changed rank or
   membership.

Do not retain raw queries, Add messages, candidate content, gold data, judge criteria, or features
from which private content can be reconstructed. A job-scoped operational trace, if required for
debugging, must be access-controlled and deleted within 30 days. No private content enters Git,
RE-call memory, documentation, tickets, or a portable result export.

## Decision rule

Smoke may validate contract compatibility, runtime stability, mechanism activation, and whether
the public query-shape assumptions were directionally correct. It may not be treated as a tuning
or training set. Any retrieval change suggested after observing Smoke requires a new version, a
new local preregistration using public or locally constructed tasks, and a fresh compatibility
decision. The observed version is not modified in place.

## Portable result envelope

GitHub issue 14 proposes a read-only EvalPort adapter for the public Textual pipelines. A later
local-only implementation may borrow the portable result shape for RE-call experiment artifacts,
including run identity, contract identity, task condition, actual output, permitted expected
output, and grader results. This is separate from Smoke observability. Private AML inputs, gold
data, and detailed evaluator content are excluded.

## Sources checked on 2026-09-19

1. https://agentmemoryleaderboard.ai/api-guide
2. https://dev.to/aml-/from-storing-to-staying-current-why-agent-memory-needs-a-shared-evaluation-4ik1
3. https://github.com/AML-memory/agent-memory-leaderboard/issues/14

<!-- No official AML run is authorized while this document remains draft. -->
