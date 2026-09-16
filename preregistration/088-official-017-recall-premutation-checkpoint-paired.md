# Preregistration 088: official-017 context-rich pre-mutation checkpoint

This record freezes the next experiment before its adapter, hook, admission rules or live run are
implemented. It follows the positive `official-016` oracle ceiling and deliberately does not reopen
the general initial-skill lane.

## Question

Can RE-call recover a meaningful fraction of the oracle ceiling when retrieval happens at the
first proposed repository mutation, using the task, pending mutation and current target file as the
query context, without selecting evidence from the oracle catalog?

The experiment separates three possible causes of improvement:

1. The existing autonomous RE-call protocol.
2. The mechanical effect of stopping the first mutation and asking the agent to reconsider.
3. The additional effect of trusted memory retrieved from a context-rich query at that checkpoint.

## Evidence that chose this lane

On the same nine-task family, the old harness prefetch queried with the exact task prompt and
succeeded on 28 of 44 recorded `recall_prefetch` sessions. Natural recall succeeded on 32 of 45.
That prefetch therefore did not establish that unconditional retrieval improves task quality.

`official-016` supplied the exact current task memory without retrieval. On 43 admitted paired
cells, the frozen control succeeded on 28 and the oracle on 42, with 15 oracle-only wins, one
control-only win and zero oracle wrong-fact applications. Correct memory has a large application
ceiling, but the exact-task query used by the old prefetch does not bridge it.

The new intervention changes query timing and query context together, but not the memory corpus,
model, task, seed, checker, trust mode, MCP surface or base protocol. It is an architectural
retrieval experiment, not another wording experiment.

## Frozen design

Run id: `official-017-recall-premutation-checkpoint-paired`.

Condition: `superseded` only.

Model: `deepseek/deepseek-v4-flash`.

Seeds: `0` through `4`.

Task roster, in this exact order:

1. `ts-base36-id`
2. `ts-bom-merge`
3. `ts-golden-regen`
4. `ts-ignore-gen`
5. `ts-legacy-hash`
6. `ts-mig-name`
7. `ts-schema-additive`
8. `ts-semver-pin`
9. `ts-tz-utc`

This yields 45 cells per arm and 135 participant sessions before exclusions.

The corpus is the same 206-session superseded feed and the same tenant lineage used by
`official-016`. The run must record and verify its corpus fingerprint before the first participant
session. Any changed corpus, task roster, model, checker, seed count or trust mode voids the stated
comparison.

## Arms

| Arm | Intervention |
|---|---|
| `recall_graph_fulltools_protocol` | Frozen autonomous protocol control with the 22-tool RE-call surface and no hook |
| `recall_graph_fulltools_checkpoint_placebo` | Same protocol and tool surface, plus a deny-once pre-mutation checkpoint that supplies no memory |
| `recall_graph_fulltools_checkpoint` | Same checkpoint, plus one harness-owned `recall_search` whose trusted result is shown before retry |

The two checkpoint arms use isolated Claude configuration directories containing only the frozen
hook. They are matched on hook event, first-mutation denial, retry instruction, MCP configuration,
tool surface and base prompt. The treatment may differ from placebo only in the retrieval request,
its evidence payload and the latency and tokens caused by that payload.

The standard control remains in the grid because placebo can reveal whether a forced second look
helps independently of memory. The primary comparison is treatment against placebo. Treatment
against standard and placebo against standard are secondary mechanism comparisons.

## Frozen checkpoint behavior

`Write` and `Edit` are always mutation candidates. A `Bash` call is a mutation candidate when its
command contains output redirection after diagnostic redirections are removed, a common filesystem
mutator (`tee`, `touch`, `mkdir`, `rm`, `mv`, `cp`, `install`, `chmod`, `chown`, `truncate`,
`sed -i`, `perl -i`), a known repository generator (`update_ignore.py`, `regen_golden.py`,
`new_migration.py`), or a Python file-writing operation such as `write_text`, `write_bytes` or an
explicit write, append or create mode. Read-only inspection and test commands do not trigger the
checkpoint.

At the first detected mutation only, the hook writes a per-session sentinel before returning. It
denies that mutation, so no repository change occurs. Its reason tells the agent to reconcile the
checkpoint with current code and retry. Later mutation calls proceed without another checkpoint.

The placebo reason states that no memory evidence is supplied and asks for the same reconciliation.
It makes no memory request.

The treatment issues exactly one brokered `recall_search` with `k=5`. The query is deterministic
and contains, in order:

1. Up to 1,200 characters of the exact user task.
2. The pending tool name, target path and up to 1,800 characters of its mutation input.
3. Up to 800 characters from the current target file when the target exists and is a regular file.
4. A fixed question asking for prior project decisions, failure modes, supersessions and required
   workflows that should constrain the mutation.

The complete query is capped at 4,096 characters. No oracle bundle, fact term, task id to bundle
mapping or checker information enters the query.

The hook accepts only a trusted response. It injects at most the first three hits whose verdict is
`ok`, preserving retrieval order, with at most 1,200 characters of text per hit and a total reason
cap of 4,800 characters. It also includes the server's advice and abstention state. Superseded,
expired, low-confidence, ambiguous or otherwise non-`ok` hits are never presented as usable
evidence. On abstention, the agent is explicitly told that memory does not support a change to the
plan and must rely on current code and tests.

The hook records only bounded diagnostics in the run metadata: mode, status, trigger tool, query
and result hashes, latency, hit count, admitted source paths and verdicts, abstention, injected byte
count and injection hash. Raw queries and evidence remain in the private execution evidence and are
not added to the public record.

## Admission and failure handling

The existing trusted challenge, checker, isolation and adjudication gates remain authoritative.
A cell enters the three-arm paired analysis only when all three arms are admitted.

The treatment is excluded for a transport error, malformed broker result, untrusted response,
missing or repeated checkpoint marker after a detected mutation, or a successful task mutation
with no checkpoint. The placebo is excluded for a missing or repeated marker after a detected
mutation, or a successful task mutation with no checkpoint. A session that fails before proposing
any mutation remains admitted as a behavioral failure. A valid treatment abstention remains
admitted.

Any mutation known to have executed before the first checkpoint marker excludes that session. A
checkpoint denial is not counted as a failed participant tool call in the quality endpoint; it is
reported separately as the intended intervention. Other failed tool calls remain unchanged.

The result is not interpreted if fewer than 36 complete three-arm cells are admitted, if the setup
gate does not confirm the expected arms and instruction, if the checkpoint configuration digest is
not stable within each arm, or if treatment and placebo differ in anything other than retrieval and
its payload.

## Endpoints

Primary endpoint:

1. Paired checker success for treatment versus placebo, reported as both-success, treatment-only,
   placebo-only, both-fail, net wins and paired success difference.

Secondary endpoints:

1. Treatment versus the standard control on the same paired cells.
2. Placebo versus the standard control, which estimates the effect of the forced second look.
3. Target-source reach: whether a treatment checkpoint returned the task's authored current
   session among its admitted `ok` sources. This is scored from source identity, never from answer
   text or checker outcome.
4. Success conditional on checkpoint trigger and target-source reach.
5. Wrong-fact application and damage rate by arm.
6. Autonomous memory calls, checkpoint calls, tool errors, participant errors and timeouts.
7. Input and output tokens, model turns, checkpoint latency, wall time and estimated spend.

Historical results are motivation only and will not replace the new paired comparisons.

## Predictions frozen before implementation

1. Treatment will have at least three net paired wins over placebo among admitted cells. With all
   45 cells admitted, this is a success-rate difference of at least 0.067.
2. Treatment will have at least three net paired wins over the standard control. This is the
   minimum recovery of the 14-net-win oracle headroom that justifies productizing the checkpoint.
3. Placebo will remain within two net wins of the standard control in either direction. A larger
   placebo effect means the forced second look, not memory, is a major intervention and must be
   reported as such.
4. The current authored task source will be reached in at least 50 percent of triggered treatment
   sessions and in at least seven of the nine tasks at least once.
5. At least 75 percent of treatment sessions that reach the current authored source will succeed.
6. Treatment wrong-fact application will not exceed placebo and will occur in no more than two
   admitted cells.
7. Treatment will have no more participant errors or timeouts than placebo plus one cell.
8. Treatment mean input tokens will not exceed placebo by more than 20 percent and mean wall time
   will not exceed placebo by more than 30 percent on admitted paired cells.

## Decision rule

The checkpoint lane advances only if prediction 1 passes, prediction 6 passes, at least 36 cells
are admitted, and no setup or trust invariant fails.

If target-source reach is below 50 percent, the next bottleneck is retrieval and query construction.
If reach passes but treatment does not beat placebo, the next bottleneck is evidence presentation
or application. If placebo alone beats standard by more than two net wins, the result supports a
generic pre-mutation review gate but does not attribute that gain to RE-call. If treatment beats
placebo while preserving the safety bound, the next step is to simplify and productize the hook
before widening the task set.

<!-- results and append-only corrections go below this line; everything above is frozen -->

## Pre-run wiring correction, 2026-09-16

No measured participant session had started when the smoke gate found two broker compatibility
defects. The publishable checkout still carried the old eight-tool broker allowlist even though the
live full-tools broker and frozen adapter declared 22 tools. The source allowlist was restored to
those exact 22 names and is now tested against `config.frozen.json`. Separately, the current MCP
SDK rejects `tools/list` when the optional `params` field is present as an empty object. The bridge
now omits empty parameters and turns upstream JSON-RPC errors into explicit broker failures instead
of misreporting an empty tool surface.

The failed smoke attempts stopped at generation, policy or broker setup gates and spent no model
session. This correction changes neither arm, prompt, query, retrieval limit, evidence payload,
task, seed, checker, corpus nor prediction above.
