# official-019: RE-call prompt-time automatic retrieval

Status: DRAFT until committed. The question, exact arms, endpoints, predictions and analysis
above the results marker become frozen before implementation and before any participant session.

## Question

Does a non-blocking `UserPromptSubmit` retrieval hook improve coding-task quality when the agent
receives the same RE-call MCP surface and the same initial protocol? This tests the first
architectural proposal after the instruction-only lane: put a small, automatic memory reminder in
the context before the agent begins reasoning, while keeping manual retrieval available.

The experiment does not claim to test a new prompt wording. The initial instruction, model,
corpus, task inputs, checker, seeds and MCP configuration are identical in both arms. The only
causal difference is the treatment's isolated prompt-time hook and its frozen local snapshot of
the same corpus bytes.

## Fixed grid

Run id: `official-019-recall-prompt-time-auto-retrieval-paired-superseded`.

Condition: `superseded` only. Tasks, in this order: `ts-base36-id`, `ts-bom-merge`,
`ts-golden-regen`, `ts-ignore-gen`, `ts-legacy-hash`, `ts-mig-name`, `ts-natural-order`,
`ts-schema-additive`, `ts-semver-pin`, `ts-tz-utc`. Seeds are 0 through 4: 50 paired cells and
100 participant sessions before exclusions.

Model: `deepseek/deepseek-v4-flash`. The control instruction is the exact committed
`recall_graph_fulltools_protocol` instruction already used by official-015. Both arms advertise
the same 22-tool RE-call surface, the same frozen graph configuration, the same tenant lineage,
the same reranker-off setting, and the same read-only policy. No sequence plan is used: the new
longitudinal infrastructure is orthogonal to this single-session mechanism test.

## Arms

| Arm | Difference |
|---|---|
| `recall_graph_fulltools_protocol` | Current protocol, no lifecycle hook. |
| `recall_graph_fulltools_prompt_time` | Current protocol plus an isolated synchronous `UserPromptSubmit` hook. |

The treatment hook invokes the released RE-call `recall_hooks.prompt_time.user_prompt_submit`
implementation through an explicitly configured source root. It reads a private, run-frozen local
snapshot rendered from the verified benchmark corpus, ranks at most three memo summaries with the
production hook's local lexical path, and injects only its bounded context. It never calls the
database, network, embedder or a mutating memory endpoint.

The hook must fail open: every path returns exit code 0 so a memory failure cannot discard the
user's prompt. The failure remains recorded as bounded telemetry and makes the treatment exposure
diagnostic fail; it is not silently counted as a successful hook. Raw prompts, raw evidence and
credentials are private and are not published in records.

The control has no hook configuration and runs with the same `--bare`/MCP settings as official-015.
The treatment uses only its generated `CLAUDE_CONFIG_DIR`, containing the hook, its settings,
trace ledger and the local snapshot. No host Claude settings, plugins or project memory are read.

## Prerequisites and gates

Before the first participant session, the runner must verify:

1. this preregistration is committed and the run id is unused;
2. the corpus manifest verifies, its fingerprint matches the RE-call tenant generation, and the
   prompt-time snapshot has the same manifest fingerprint and a recorded file-tree digest;
3. both arms resolve to the exact same model, task roster, seed set, checker, sandbox policy,
   MCP config and 22 advertised tool names, with reranking disabled;
4. the treatment hook source, generated settings and no-matcher `UserPromptSubmit` shape pass the
   adapter tests; the control has no hook, and neither arm has a mutating memory tool;
5. the API credential and RE-call broker pass a read-only smoke test without spending a
   participant session; and
6. a bounded smoke run proves one control and one treatment session complete, the treatment emits
   exactly one prompt-time hook ledger event, the control emits none, and both sessions remain
   inside their isolated sandbox.

The live run uses `AMB_BLOCK_CONCURRENCY=3`, which means three independent cells may run at once;
the two arms within each cell remain concurrently scheduled by the runner. The concurrency value
is recorded and is not allowed to change between smoke and participant execution. If the host
cannot sustain three cells without MCP startup failures or memory pressure, the run stops rather
than lowering a gate after the fact.

## Endpoints

Primary: paired checker success on cells where both arms are admitted, reporting both-success,
treatment-only, control-only, both-fail, net wins and paired success difference.

Diagnostics, all reported separately for all-run and admitted denominators:

* prompt-time hook reach, exit/error status, emitted-context byte/hash and source-count/hash;
* manual RE-call rate and tool routing, including the existing graph/evidence/current-state/
  relation counters;
* success conditional on hook reach and manual search;
* wrong-fact application, damage and abstention under the superseded detector;
* tool errors, participant errors, timeouts, model turns, input/output tokens, wall time and
  estimated spend;
* control stability and treatment/control configuration, corpus and snapshot fingerprints.

No missing telemetry is converted to zero. A hook source or result that cannot be identified is
`NA` and blocks the corresponding exposure claim.

## Predictions frozen before implementation

1. At least 0.80 of admitted treatment sessions will reach the prompt-time hook and at least
   0.60 will receive one or more source summaries; no admitted treatment session will have a
   hook error or non-zero exit.
2. Treatment will produce at least three net paired checker wins over control. A smaller positive
   difference is suggestive only, not a demonstrated product gain.
3. Treatment will not increase wrong-fact application or damage by more than 0.02 absolute and
   will have no more than one additional participant error or timeout.
4. Manual search exposure in treatment will not fall more than 0.05 below control. Automatic
   context must complement, not suppress, the agent's appropriate use of RE-call.
5. Treatment mean input tokens will not exceed control by more than 35 percent and mean wall time
   will not exceed control by more than 25 percent.

## Decision rule

The experiment is interpretable only with at least 40 complete paired cells, stable setup and
trust receipts, and no sandbox or tool-surface violation. The prompt-time lane advances only if
prediction 2 and prediction 3 pass, with prediction 1 also passing as proof that the mechanism
was actually delivered. If hook reach passes but quality does not, the next experiment targets
evidence selection/presentation rather than adding more prompting. If quality improves but manual
search falls, the automatic context is treated as a replacement/confound and is not promoted.

All corrections are append-only below this marker.

<!-- results are appended below this line; everything above is frozen -->
