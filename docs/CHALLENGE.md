# AMB Challenge

Status: design contract, not yet open for entries.

The challenge is a separate layer from the scientific leaderboard. The leaderboard measures
published product integrations against a public benchmark. The challenge must measure submitted
memory adapters against tasks and oracles that the entrants cannot inspect.

## Non negotiable boundary

The public repository is a development and smoke testing surface. It is not the scoring surface.
It currently contains task prompts, checkers, 101 oracle files and 135 reference implementations.
That is useful for auditing AMB, but it allows task specific lookup tables and answer reconstruction.
No public checkout may be used as the source of truth for a prize score.

The challenge evaluator owns a private pack containing:

* held out task prompts and fixtures;
* private oracle inputs and reference solutions;
* the frozen corpus manifest and challenge configuration;
* the scoring and admission code version.

Entrants receive only the public smoke pack and the adapter contract. The evaluator mounts private
files only for the checker after the agent session has ended. The submitted adapter and agent must
not be able to read the evaluator checkout, oracle pack, reference solutions or other entrants'
artifacts.

## Submission

An entry submits one reproducible adapter bundle or OCI image. It does not modify tasks, checkers,
scoring code or the private evaluator. The submission includes:

1. a name, version, source revision and contact;
2. a license and a short description of the memory integration;
3. exact dependency and model configuration pins;
4. a declared network requirement;
5. a smoke test result produced by the public harness.

The evaluator freezes the submitted bytes by digest before running them. A changed digest is a new
entry, not a revised score.

The private pack has a machine checked marker and manifest. Before any entry runs, the organizer
should validate it with:

```bash
python -m scripts.validate_challenge_pack --pack /private/amb-challenge-pack
```

That check proves the pack is separate from the public repository and that every declared fixture,
prompt, checker, oracle and reference path exists inside it without symlink escapes. It does not
replace the process sandbox required when executing an untrusted submission.

The manifest shape is intentionally small and explicit:

```json
{
  "schema": 1,
  "kind": "amb-private-evaluation-pack",
  "visibility": "private",
  "pack_id": "challenge-001",
  "source_public_commit": "public-commit-sha",
  "scoring_version": "score-1",
  "corpus": "corpus",
  "tasks": [
    {
      "task_id": "heldout-task-001",
      "fixture": "fixtures/heldout-task-001",
      "prompt": "prompts/heldout-task-001.txt",
      "checker": "checkers/heldout-task-001/checker.py",
      "oracle": "oracles/heldout-task-001",
      "reference": "references/heldout-task-001"
    }
  ]
}
```

The example is a schema illustration only. It is not a challenge task and must not be copied into
the public repository with real answers.

An entry descriptor is validated separately. It must use an immutable image digest and declare the
adapter API, configuration digest, entrypoint and network mode. The evaluator turns it into one
plan per task. Each plan mounts only that task's fixture and prompt, the shared corpus, and that
task's writable output directory. It never mounts the complete held out prompt or fixture roster:

```bash
python -m scripts.validate_challenge_submission \
  --pack /private/amb-challenge-pack \
  --submission submission.json \
  --json
```

The plan is not an executor. The eventual evaluator must enforce its read only root, dropped
capabilities, no new privileges, network policy and private path exclusions in the container
runtime.

The repository includes a conservative Docker runner for one task. It defaults to a dry run and
uses an explicit execute flag. The image must already be present locally, because the runner uses
`--pull=never`:

```bash
python -m scripts.run_challenge_task \
  --pack /private/amb-challenge-pack \
  --submission submission.json \
  --task heldout-task-001 \
  --output-root /private/amb-challenge-output

python -m scripts.run_challenge_task \
  --pack /private/amb-challenge-pack \
  --submission submission.json \
  --task heldout-task-001 \
  --output-root /private/amb-challenge-output \
  --execute
```

Execution uses no host network, a read only root, dropped capabilities, no new privileges,
resource limits and no evaluator mounts. A submission declaring `model-only` must use an
evaluator managed model proxy socket. Direct outbound network access is never granted.

This runner is currently a container smoke harness, not the final prize evaluator for the
adapter track. The adapter API still has to specify how a fixed model runner calls the submitted
memory layer, how task context is mediated, and how reset and usage events are recorded. Until
that protocol is frozen, a one shot image must not be compared as an adapter only result because
its prompt construction, model calls or agent loop could become an unrecorded advantage.

The final evaluator shape is a sidecar service. The fixed evaluator owns the model and task agent.
The submitted image receives only the shared corpus and an empty runtime directory, then serves the
evaluator over `/challenge/runtime/adapter.sock`. The task fixture and prompt stay in the
evaluator's task process and are never mounted into the memory sidecar.

The proposed protocol is intentionally small. Each socket connection carries one newline delimited
JSON request and one response using API `amb-challenge-adapter-v1`:

```json
{"api":"amb-challenge-adapter-v1","id":"req-1","method":"search","params":{"task_id":"heldout-task-001","query":"...","limit":10}}
```

The allowed methods are `health`, `search` and `reset`. The adapter starts with the mounted corpus
and must report readiness through `health`, whose result includes `{"ready":true}`. `search`
returns ranked memory results. `reset` clears task session state and is called before every new
session. The evaluator validates every response,
applies the fixed timeout and records protocol errors as run outcomes. An `ingest` method is not
exposed to the agent protocol because corpus ingestion belongs to sidecar startup.

A successful `search` response has this result shape:

```json
{
  "hits": [
    {"source_id":"sessions/example.jsonl","text":"...","score":0.91,"rank":1}
  ],
  "abstained": false,
  "usage": {"input_tokens":0,"output_tokens":0}
}
```

The evaluator treats returned text as untrusted model context and records the raw response. The
adapter cannot report correctness, checker verdicts or oracle data through this protocol.

After the sidecar and fixed agent finish, the evaluator runs the private checker in a separate
bounded host process. The checker receives the finished task directory and its private oracle
directory. It never runs in the entrant container. A public score manifest contains task ids and
pass or fail outcomes, but not private checker messages, oracle paths or oracle explanations.
The aggregate is deterministic and must contain exactly one result for every task.

The coordinator enforces this order independently for every task:

1. Create a fresh task output directory and empty sidecar runtime directory.
2. Start the submitted sidecar with only its corpus and runtime socket mounts.
3. Wait for `health`, then send `reset` before the fixed agent begins.
4. Run the fixed agent with only the current fixture, prompt, output directory and adapter client.
5. Stop and remove the sidecar before starting the private checker.
6. Run the private checker and add exactly one task score to the aggregate manifest.

The fixed agent callback receives a narrow task context and cannot access the pack object. It gets a
search-only adapter view for memory operations. `health` and `reset` remain evaluator-only calls, so
the agent cannot reset state mid task. Provider credentials, model settings and the model proxy
remain evaluator configuration and are never loaded from a submission descriptor. The adapter call
budget is fixed before entries open and is identical for every submission.

Task specific hardcoding, private answer maps, oracle access, evaluator path discovery and manual
intervention are disallowed. The private task set is the primary technical defence against these
behaviours. The evaluator also runs a red team check for filesystem, environment, network and
output side channels before accepting a score.

## Fixed conditions

Every accepted entry receives the same:

* model, provider, model version, temperature settings and context limits;
* task roster, seeds, corpus bytes, conditions and prompt;
* timeout, permission mode, non memory tools and sandbox policy;
* retry policy, admission rule and scoring version;
* compute budget and API credits.

The organizer should provide the model credits or run the sessions centrally. Requiring entrants
to pay for different providers makes the prize partly a contest in access to credits, latency and
rate limits.

The default challenge track measures the adapter, not prompt engineering. It therefore uses one
frozen shared system instruction and permits the entry to provide only its memory integration.
A separate integration track may allow a product's shipped instruction, but it must publish that
instruction before the deadline and must not be compared directly with the adapter track.

## Scoring

The primary score is execution success on the private held out tasks. The checker returns pass or
fail; there is no LLM judge and no manual partial credit.

Secondary metrics are published but do not silently replace the primary score:

* harm rate under absent, superseded, contradictory and adjacent information;
* abstention or uncertainty behaviour where the task supports it;
* input and output tokens, wall time and infrastructure cost, published as run telemetry separate
  from the deterministic score manifest;
* admitted cells, discarded cells and every discard reason;
* per task results and paired deltas against the fixed baseline.

The minimum admitted cell coverage and the tie breaker are preregistered before entries open. A
candidate with insufficient coverage is ineligible rather than ranked with a favourable subset.
Infrastructure retries are allowed only for a preregistered wiring failure predicate. Timeouts,
checker failures and incorrect artifacts remain outcomes.

The winner is the highest eligible primary score on the private set. If scores tie, the frozen tie
breaker tasks decide. If the evaluator changes after a submission is run, every affected entry is
rerun under the new version or all affected scores are withdrawn.

## Publication and adjudication

Before entries open, the organizer publishes:

* this rule version and its sha256 digest;
* the public smoke pack and the adapter contract;
* the private evaluator version hash, held by an independent reviewer;
* the model, budget, seeds, scoring endpoints and exclusion rules;
* the prize split, deadline, tie breaker and appeal window.

The sponsor's own product, including RE-call, is ineligible for the prize. It may appear as a
clearly labelled reference run, but it must not determine eligibility, approve its own exception,
or be the only party holding the private evaluator. A reviewer who did not implement the winning
entry signs the final score manifest.

After the deadline, the evaluator publishes the winning submission digest, the complete score
manifest, aggregate results for every entry, discard counts, costs, checker version and any
withdrawn or disqualified entries with the reason. A failed entry is still reported as a failed
entry; it is not silently removed.

## Readiness gates

The challenge is not ready until all of these are true:

1. The private task and oracle pack exists outside the public repository.
2. A fresh machine can run the public smoke suite without credentials or a database.
3. The evaluator can run one adapter against private tasks without exposing private files.
4. A malicious adapter cannot read evaluator files, task answers, host credentials or another run.
5. The task roster has passed capacity, leakage, overlap and findability review.
6. A baseline and at least one deliberately bad adapter produce the expected score ordering.
7. The scoring manifest is reproducible from the frozen evaluator version.
8. The preregistration, reviewer and appeal process are in place before the first entry.

Until these gates pass, AMB can advertise a public benchmark and invite adapter development, but it
should not advertise a competitive ranking or prize result.
