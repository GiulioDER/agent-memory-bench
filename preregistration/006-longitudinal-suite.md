# longitudinal-001: does a memory layer accumulate what an agent learns, and still have it later?

Status: DRAFT until committed; a committed record is frozen above the results marker.

## Question

When a governing fact is discoverable **only** by doing session 1, and session 2 runs in a fresh
sandbox where that fact is absent from the repository, what fraction of chains does each arm solve
at session 2, and how does that fraction decay as unrelated sessions are interposed between them?

## Why this suite has to exist

Every memory product sells **accumulation**: the agent gets better because it remembers what it
learned. This benchmark has never tested that. `corpus/` is 125 pre-authored transcripts, bulk
ingested through each adapter's write path before the grid starts, and read once. The agent never
forms a memory from its own work, so **half of every product under test, the write path, is
currently unmeasured**, and the claim the products actually make has never been put to a number.

⛔ **Neutrality, in the same form as preregistration 005.** Products differ in how memories get
written: some capture sessions automatically through a lifecycle hook, some require the agent to
call a write tool, some do both. Each arm is wired through **its own official integration** and
nothing else, and the benchmark measures the outcome rather than prescribing the route. A design
that required an explicit write call would hand the win to products built that way, and a design
that required silent auto-capture would hand it to the others.

## Design: chains

A **chain** is an ordered sequence of sessions sharing one memory namespace and one arm, each in a
fresh sandbox.

* **Session 1 (the source).** An ordinary task whose completion requires discovering a governing
  fact that is not written anywhere in the repository. The fact is discoverable by doing the work,
  for example a test whose failure message reveals the project's convention. It is NOT stated in
  the prompt: a prompt-stated fact tests copying, not learning.
* **Sessions 2..N-1 (the distance).** Unrelated tasks on unrelated fixtures, present only to put
  distance and interference between source and target. Count is the independent variable.
* **Session N (the target).** A task in a fresh sandbox whose correct solution requires the fact
  from session 1, where the fact is absent from that sandbox by the same locus discipline
  `scripts/audit_corpus.py` already enforces.

Chain lengths: **2, 4 and 8**, so decay is measured rather than assumed.

## Arms and configs

| arm | adapter config sha256 | versions |
|---|---|---|
| `bare` | n/a | the floor: with no memory, session N can only succeed by luck, and that luck rate is the number every other arm must beat |
| `claude_md` | fixture README bundle | static control; it cannot accumulate by construction, so it is the second floor |
| `recall` | `adapters/recall/config.frozen.json` | `--recall-instruction skill`, sha256 pinned |

`bare` is mandatory. Without it, "the agent rediscovered the fact unaided" is indistinguishable
from "memory delivered it".

## Grid

12 chains per length, 3 lengths, 3 arms, 3 seeds: 36 chains per arm per seed. Total sessions is
`3 arms x 3 seeds x 12 chains x (2 + 4 + 8) = 1,512`, which is five times any run to date and needs
its own budget decision before it is scheduled. If that is too large, cut chain **count** before
cutting chain **lengths**, because the decay curve is the point.

Model, CLI version, timeout, permission mode, denied tools: recorded in `environment.json` before
the first session, as now.

## Endpoints, in reporting order

1. **Primary: chain success**, the fraction of chains whose session N passes its checker, per arm
   per chain length, with per-chain cluster bootstrap intervals. The denominator is **admitted
   chains**, and a chain is admitted only if every one of its sessions was admitted.
2. **Decay**: chain success at length 8 minus chain success at length 2, per arm. A memory layer
   whose value survives two sessions but not eight is a different product from one whose value
   holds, and today nothing distinguishes them.
3. **The accumulation funnel**, per chain, each stage a rate over the stage above it:
   a. **encountered**: session 1's transcript shows the agent met the fact
   b. **retained**: the fact is present in the arm's store after session 1, checked directly
      against the store rather than inferred from behaviour
   c. **retrieved**: session N's transcript shows the fact surfaced
   d. **applied**: session N's deliverable embodies it
4. Secondary: session 1 success rate, cost and wall time per chain.

Stage (b) needs a read-only store probe per adapter. It is the stage that separates "never wrote
it" from "wrote it and could not find it", which is the whole question, and no existing metric can
tell those apart.

## Predictions

House prior: effects at a quarter to a half of intuition, costs at five times. My record on this
benchmark is eleven falsified out of twelve, all too optimistic, and `diagnostic-009` is a twelfth
where I read a confound as a finding. These are deliberately low.

1. **Retention is high and retrieval is the bottleneck**, mirroring the single-session result.
   `retained` above **80%**, `retrieved | retained` below **50%**.
2. **Chain success at length 2 is well below the single-session lift.** `recall` minus `claude_md`
   at length 2: **+5 to +15 points**, against the +19 `diagnostic-010` is showing when the corpus
   was authored and ingested in bulk.
3. **Decay is real and mostly interference, not time.** Chain success at length 8 is **10 to 25
   points below** length 2 for every arm that has any lift at all.
4. **`bare` succeeds at session N more often than zero**, somewhere **5 to 20%**, because some
   facts are rediscoverable. If `bare` is at zero the targets are too hard to be informative; if
   `bare` is above 40% the fact was not really absent and the locus audit failed.
5. **`claude_md` shows no decay**, within noise, because it cannot accumulate. This is the
   apparatus check, not a finding: if the static arm decays with chain length, the design is
   measuring session-ordering effects and the suite is void.

## Exclusion and truncation rules

* A chain is **discarded whole** if any session in it fails admission. Partial chains are not
  scored, and the discarded count is published with reasons, per arm and per length.
* **A failed write is a RESULT, not an exclusion.** Admission requires the memory surface to be
  present, exactly as now; it must never require that anything was successfully stored, or the gate
  would discard precisely the failures this suite exists to measure.
* Chains whose **session 1 failed** are reported separately and excluded from the primary. If the
  agent never solved the source task it may never have met the fact, so the chain tests nothing.
  This conditioning is fixed here, before any data exists.
* Retries are triggered by wiring only, never by outcome, as in every other run.
* If the budget binds: cut chains per length, never lengths, never arms.

## What would falsify this

- Prediction 1 falsified if `retained` is below 50%, which would mean the write path fails rather
  than the read path, and would relocate the whole problem.
- Prediction 3 falsified if length 8 is within noise of length 2, i.e. no decay, which would be a
  stronger result for memory products than I expect and should be reported loudly.
- Prediction 5 falsified if `claude_md` decays with chain length. The suite is then void and must
  not be published, because it is measuring ordering rather than memory.
- The whole suite is void if session-to-session context leaks by any route other than the memory
  layer. Every session already runs `--bare` in a fresh sandbox; this must be verified per chain by
  confirming the fact is absent from session N's prompt, sandbox and system prompt before the run.

## Confounds I can name now

- **Context leakage** is the fatal one. If any part of session 1 reaches session N except through
  the memory layer, every number is inflated. Verified by construction and re-checked per chain.
- **The agent may never meet the fact in session 1.** Endpoint 3a exists to measure that rather
  than assume it, and chains where it did not happen are reported separately.
- **Rediscovery, not recall.** An agent may solve session N by working the fact out again. Endpoint
  3c separates "surfaced from memory" from "derived in session"; `bare` bounds it.
- **Interference and time are entangled.** Chain length adds both distance and unrelated content.
  This suite cannot separate them, and I am not claiming it can. A later design with time held
  constant and content varied would be needed, and that is out of scope here.
- **Auto-capture products write everything, including the distance sessions.** That is a real
  product difference in both directions: better recall, more noise. It is measured, not corrected.

## What I already know

`diagnostic-010` (skill instruction, still running at 69/72 when this was written): `recall` 54%
against `claude_md` 35%, search rate 86%. `diagnostic-009` (one-line instruction): `recall` 38.9%
against `claude_md` 41.7%, search rate 11%, and I misread that as retrieval loss when it was an
instruction confound. pilot-004: `recall` +17.4 over `claude_md` on the bulk-ingested corpus.

Every one of those numbers comes from a corpus somebody else authored and bulk loaded. None of them
says anything about whether an agent's own memories survive to the next session.

<!-- results are appended below this line; everything above is frozen -->
