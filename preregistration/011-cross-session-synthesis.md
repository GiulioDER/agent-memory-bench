# synthesis-001: what happens when the governing fact is not in any one session?

Status: DRAFT until committed; a committed record is frozen above the results marker.

## Question

On tasks whose governing fact is distributed across two or three sessions, how does each arm's
success rate compare to its rate on the single-document `ts-*` suite, and what does it do wrong:
find one shard and stop, or find a superseded revision and apply it?

## Why this record exists before the tasks are recorded

The `ts-*` suite states each governing fact once, in one document, in one paragraph. Every number
published from it is therefore a number about **retrieval**: the design gives a product that
extracts and consolidates at write time no way to win and every way to lose, which is a sentence a
competitor can write without help. Three tasks now exist that a single retrieved document cannot
solve (`docs/CROSS_SESSION_SYNTHESIS.md`). Nothing has been measured with them.

⚠️ **Three tasks is a diagnostic, not a headline.** With per-task cluster bootstrap intervals over
three clusters, no interval this suite produces is publishable as a product comparison, and none
will be published as one. What it can do is show a mechanism: which failure the arms actually make.
The threshold for treating this as a scored suite is **ten tasks**, at least three per shape.

## Arms and configs

| arm | adapter config sha256 | versions |
|---|---|---|
| `bare` | n/a | the floor. These facts are arbitrary by construction, so a `bare` rate much above zero means a shard was guessable and the task is void |
| `claude_md` | fixture README bundle | the designated baseline, as in every other run |
| `protocol` | n/a | the shared memory protocol with no memory layer: separates coaching from retrieval, exactly as in `pilot-004` |
| `fs_grep` | n/a | transcripts on disk plus grep. On a distributed fact this is the informative control: grep returns whatever matches, so it is retrieval breadth with no consolidation at all |
| `recall` | `adapters/recall/config.frozen.json` | verbatim indexed retrieval |

The four third-party products are the arms this suite was built for and **none of them is wired
yet**. Running it without them answers a narrower question than the one this suite exists for, and
any writeup must say which question it answered.

## Grid

Tasks: `xs-join-batch`, `xs-evolve-lease`, `xs-widen-manifest`. Seeds: 3. Model, CLI version,
timeout, permission mode and denied tools recorded in `environment.json` before the first session,
as in every other run. The `xs-*` prefix keeps these out of the `ts-*` grid, so this suite cannot
change what a rerun of `pilot-003` or `pilot-004` measures.

⛔ **The corpus must be recorded first, and recorded shard by shard.** A session that states two
shards voids its task; `scripts/record_precursor.py` refuses one and `scripts/audit_corpus.py`
re-checks the whole corpus afterwards.

## Open decision, to be settled before the first session and not after

`adapters/_shared/memory_protocol.md` says nothing about preferring a recent note to an older one.
The `evolve` shape turns on exactly that. Either the protocol stays byte-identical to the frozen
runs and the suite measures what the arms do unprompted, or a recency sentence is added **to every
memory arm at once** and the suite is explicitly non-comparable to `pilot-002` through `pilot-004`.
Whichever is chosen goes in this file, with its character count, before anything runs. The one
outcome that must not happen is the sentence reaching one arm.

## Endpoints, in reporting order

1. **Primary: task success per arm per task**, with the per-task verdict string retained. Three
   clusters, so the interval is reported and labelled as uninformative rather than omitted.
2. **The shard funnel, per memory arm per task**: what fraction of sessions retrieved shard A,
   shard B, both, and applied both. Retrieval is read from the transcript; application from the
   checker verdict. This is the endpoint the suite exists for, because it separates "the store did
   not hold it" from "the agent held both halves and combined neither".
3. **Superseded application rate**, `xs-evolve-lease` only: the fraction of sessions that renewed
   at 90 or 45 seconds. Those values exist nowhere except the corpus, so this is the one endpoint
   here that can only be caused by memory.
4. **One-half rate**, `xs-join-batch` only: `ORDER_OK_BATCHING_WRONG` plus
   `BATCHING_OK_ORDER_WRONG` over admitted cells.
5. Secondary: cost and wall time per task, beside the `ts-*` figures for the same arms.

## Predictions

House prior: effects at a quarter to a half of intuition, costs at five times. My record on this
benchmark is eleven falsified out of twelve, all too optimistic. These are deliberately low.

1. **Every arm scores lower here than on `ts-*`.** `recall` on `xs-*` lands **15 to 35 points
   below** its own `ts-*` rate. Two facts to find instead of one, and the second is not a second
   chance at the first.
2. **`recall` minus `claude_md` is smaller than the `+22.2` of `pilot-003`**: **+2 to +12 points**
   pooled over the three tasks.
3. **On `xs-evolve-lease` the memory arms do not beat `claude_md`, and may lose to it.** Predicted
   delta **-10 to +5 points**. A store that returns three dated values with no resolution hands the
   agent a wrong answer it would not otherwise have had.
4. **Superseded application is the modal memory failure on `evolve`**: **20% to 50%** of `recall`
   and `fs_grep` sessions renew at 90 or 45 seconds, against **0%** for `bare` and `claude_md`,
   where those numbers do not exist.
5. **On `xs-join-batch`, one half beats both halves.** The combined one-half rate exceeds the
   success rate for every memory arm.
6. **`bare` is at or below 5%** on all three tasks. Above 15% on any of them means a shard was
   derivable and that task is void, not hard.
7. **`fs_grep` is not far behind `recall` here**, within 10 points. Grep over 130 rendered
   transcripts is breadth without consolidation, and breadth is most of what `join` and `widen`
   reward.
8. **Recording will not be clean the first time.** At least one of the seven shard recordings is
   refused by the cross-shard gate or the term gate and needs re-staging.

## Exclusion and truncation rules

- The admission gate is unchanged: a cell is discarded, not scored, unless every arm can prove its
  treatment was applied, and discard counts are published per arm.
- A task is **void, not merely hard**, if `bare` exceeds 15% or if `informed` and `partial_*` stop
  behaving as CI asserts. Void tasks are reported and excluded, and the exclusion is stated in the
  writeup rather than in a commit message.
- If the budget binds: cut seeds, never tasks. Three tasks is already the floor of the design.
- Retries are triggered by wiring only, never by outcome.

## What would falsify this

- Prediction 3 falsified if a memory arm beats `claude_md` on `xs-evolve-lease` by more than 10
  points, which would mean the arms resolve recency unprompted and the shape is easier than it
  looks. Report it loudly; it is the most surprising outcome available here.
- Prediction 4 falsified if superseded application is near zero. Then the arms are either not
  retrieving the older sessions at all, which is a retrieval finding rather than a consolidation
  one, or they are resolving them correctly, which is prediction 3's falsification twice over.
- Prediction 6 falsified by a high `bare` rate, which voids the task rather than the prediction.
- The whole suite is void if `scripts/audit_corpus.py` reports a shard violation on the recorded
  corpus and the recording is edited rather than re-run.

## Confounds I can name now

- **These tasks are harder in an absolute sense**, and a lower rate is not by itself evidence about
  consolidation. What separates the two is endpoint 2 and the committed `partial_*` references: the
  ceiling is known by construction, so "found one half" is measurable rather than inferred.
- **Three tasks, three shapes, one task per shape.** Any per-shape statement is a statement about a
  single fixture. This is the reason the ten-task threshold above exists.
- **The alias in `xs-join-batch` is in the fixture**, so that task measures joining two memories
  rather than entity resolution across a corpus. A design where the alias is itself a third
  memory would measure more and would confound "could not link" with "could not retrieve".
- **`fs_grep` sees the corpus verbatim** and an extraction product does not. That asymmetry is the
  thing under test, not a flaw, but it means a low extraction-arm score has two readings (dropped
  at write time, or stored and not retrieved) and only a store probe can separate them. There is
  no store probe in this suite; `preregistration/006` endpoint 3b is where it belongs.

## What I already know

Nothing measured. The three tasks pass their discrimination assertions in CI (do-nothing fails,
`naive` fails, every `partial_*` fails, `informed` passes) and no session has been run against any
of them. `pilot-003-deepseek` measured `recall` `+22.2` over `claude_md` on the single-document
suite; that number is the thing this suite exists to put in context, not to confirm.

<!-- results are appended below this line; everything above is frozen -->
