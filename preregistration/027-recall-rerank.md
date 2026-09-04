# 027: rerank-001, does recall's Voyage reranker change task success?

Status: DRAFT until committed; a committed record is frozen above the results marker.

## Question

`recall` has run every benchmark to date with its reranker **off**. Preregistration 014 disabled it
on a measurement (`hit@1 = 20/20` on the 121-source `absent` corpus, so there was no rank-1 headroom
to win) and on an operational failure (the Voyage path hung reproducibly on the serving host). The
first half of that reasoning was retired on 2026-08-30: on the 4,911-document haystack the correct
session is ranked first only **33%** of the time and is outside the top ten **12%** of the time
(`docs/RETRIEVAL_DIFFICULTY.md`, preregistration 015). Reranking now has work to do.

**Does turning on `voyage:rerank-2.5` change the rate at which the agent solves the task?**

Not "does it improve retrieval". Retrieval is the mechanism and is measured as one; the endpoint is
task success, because a benchmark whose headline is a retrieval metric would be answering a
different question well.

## Arms and configs

| arm | adapter config sha256 | versions |
|---|---|---|
| `bare` | none | no memory surface |
| `recall` | `ae92863ce399c46766c5b9cc566bee6cf22e39a416c8f53af5892cb7f7220a6d` | `recall-rag[fastembed,mcp,voyage]==0.11.0` |
| `recall_rerank` | `88a0a272a95e8af2efce92a3d5800743ad0be6afce6be1a68132e734df83ddf7` | `recall-rag[fastembed,mcp,voyage,rerank]==0.11.0` |

`claude_md` is deliberately **absent**, and the consequence is stated rather than discovered later:
without the baseline arm this run cannot produce a `leaderboard_summary.json`
(`scripts/build_leaderboard.py::_load_summary` requires the exact `PRODUCT_ARMS` set), so it is a
targeted contrast and never a board update. `bare` is present because the damage endpoints are
defined against it.

### The whole difference between the two recall arms, enumerated

Both arms serve the same tenant at the same active generation, with the same embedder
(`voyage:voyage-4`), the same strict trust gate, the same `production` store, the same eight tools,
the same `server_name` and `mcp__recall__` prefix, and an instruction derived from the **same
function call** rather than from a copied file. `tests/test_recall_rerank_adapter.py` asserts each of
those and asserts that the two frozen configs differ in exactly four keys: `extra_env`,
`package_pin`, `remote_python_env` and the prose in `notes`.

| | `recall` | `recall_rerank` |
|---|---|---|
| `RECALL_RERANK` | unset | `1` |
| `RECALL_RERANK_MODEL` | unset | `voyage:rerank-2.5` |
| interpreter | the bench venv | a second venv carrying the `rerank` extra |

⚠️ **Three things about the reranker configuration that a reader should not have to discover.**

1. **The `rerank` extra is required and was verified, not assumed.** Measured 2026-09-02 on the
   serving host with a valid `VOYAGE_API_KEY` present:
   `RECALL_RERANK=1 RECALL_RERANK_MODEL=voyage` raises
   `ImportError: CrossEncoderReranker requires: pip install "recall-rag[rerank]"` at construction.
   It is a loud refusal at server start, not a silently unreranked search.
2. **Voyage cannot be selected alone.** `recall_mcp.factories._new_reranker` builds
   `FallbackReranker(primary=Voyage, fallback=CrossEncoderReranker(ms-marco-MiniLM-L-6-v2))`
   **eagerly** for any Voyage model name. The local cross-encoder is downloaded and loaded whether
   or not Voyage ever fails. There is no configuration in 0.11.0 that avoids this.
3. **That eager build is the thing that hung during 014's measurement**, server idle at 0.3% CPU
   with every call timing out at 90 s and HuggingFace reachable. No root cause was found then and
   none is claimed now. It is the single most likely way this run fails, which is why M1 below is a
   mechanism check and not a footnote.

The second venv exists so that `recall`'s own artifact is untouched: torch and transformers do not
belong in the environment every published run was measured on, for an arm that never loads them.
The torch wheel is the CPU build (`download.pytorch.org/whl/cpu`) because the host has no GPU; same
version, different build, stated here because it is a deviation from a plain `pip install`.

## Grid

**73 task-conditions**, the same selection `official-002` and `official-003` ran, from
`scripts/abstention.py::selection_for` after retirement:

| condition | task-conditions |
|---|---:|
| `present` | 27 |
| `absent` | 12 |
| `superseded` | 11 |
| `contradictory` | 11 |
| `adjacent` | 12 |

**Arms (3):** `bare`, `recall`, `recall_rerank`. **Seeds: 5**, for the reason preregistration 020
gives: at 3 seeds a task measured at 0.83 collapses to a unanimous 1.000 about 57% of the time and
stops carrying two-sided information.

**1,095 sessions.** Model `deepseek/deepseek-v4-flash`, matching every prior run. Prices
`--price-in 0.0574 --price-out 0.1148 --price-as-of 2026-08-22`, the frozen preregistration 002
rates. Corpus: the 4,911-document haystack, `AMB_CORPUS_FLOOR=4000`. `--memory-instruction protocol`,
matching `official-003`; the two recall arms receive byte-identical text under it.

⚠️ **This is a THREE-arm grid, so its admitted set is not `official-003`'s and its numbers are not
differenceable against it.** A cell is admitted only when every arm in the run produced a record, so
a run with fewer arms admits a different set, not a superset with less noise. The contrast this run
is for is internal to it.

## Endpoints, in reporting order

1. **Primary: task success, `recall_rerank` against `recall`**, paired on `(task, seed, condition)`
   over all admitted cells, per-task cluster bootstrap CI, McNemar on the discordant pairs.
2. **Damage rate by condition**, each recall arm against `bare`, on `DAMAGE_ONLY` tasks.
3. **Benefit on `present`**, each recall arm against `bare`: the condition where retrieval is a
   pure identity transform and a ranking improvement has the clearest path to the outcome.
4. **Abstention rate**, on `absent` and `contradictory`, a lower bound always.

Search rate is reported per memory arm; below 0.50 the endpoints are not interpretable.

### Mechanism metrics, reported beside the outcome

- **M1 `reranking_ran`** is true on the reranked arm's searches, and the `FallbackReranker` fallback
  counter is **0**. A run where the local cross-encoder answered a material share measured a blend
  of two rerankers and reports no reranker result at all.
- **M2 hit@1** on the served corpus, both arms, measured **through the MCP server**.

⛔ **M2 cannot be measured with `scripts/retrieval_probe.py --arm`, and that is not a detail.**
recall's reranker lives entirely in `recall_mcp`; `recall.cli`, which `RecallAdapter.search` shells
out to, contains no reference to `RECALL_RERANK` and builds no reranker (verified 2026-09-02 by
grepping the installed 0.11.0). The probe would hand the CLI an environment saying the reranker is
on, receive the unreranked ranking, and report the two arms as identical, with the null being an
artefact of the probe rather than a property of the product. `RecallRerankAdapter.search` therefore
REFUSES rather than answering, so this mistake cannot be made silently.

## Predictions

House prior, recorded because it has been measured: eleven of twelve prior predictions were
falsified and every one was too high by two to four times. These are set low deliberately.

| # | Claim | Prediction | Confidence |
|---|---|---|---|
| M1 | the reranker runs, and Voyage answers | `reranking_ran` true, fallback count 0 | 0.70 |
| M2 | hit@1 through the server rises from voyage-4's measured 0.333 | to between 0.45 and 0.62 | 0.60 |
| P1 | `recall_rerank` vs `recall`, direction | positive | **0.55** |
| P2 | `recall_rerank` vs `recall`, magnitude | net under +10 cells of roughly 300 admitted, i.e. under +3.5 points | 0.75 |
| P3 | `recall_rerank` vs `recall`, significance | p < 0.05 | **0.15** |
| P4 | search rate | within ±0.05 of `recall`'s, per condition | 0.85 |
| P5 | where any gain lands | `present` is the largest of the five | 0.60 |
| P6 | `absent` and `adjacent` | reranking does not reduce damage; damage within ±5 cells of `recall`'s | 0.65 |
| P7 | latency | median session wall time on the reranked arm rises 10% to 40% | 0.60 |

**P1 and P3 are the ones to watch, and they are low on purpose.** The reason is a mechanism the
retrieval numbers do not capture: **the reranker reorders a list the agent reads in full.** M2 is a
rank-1 metric, but a session receives k hits and can read all of them, so a lift that moves the
right document from rank 4 to rank 1 changes the outcome only for a model that stopped reading. The
gap between a large predicted M2 and a near-null predicted P1 is the substantive claim of this
record, and it is the thing the run can falsify in either direction.

**P6 is the honest downside.** On `absent` the answer is not in the corpus, so a better ranker can
only promote a more convincing near-miss to the top. Preregistration 016 measured that authored
semantic near-misses cost voyage-4 hit@1 (0.394 to 0.333), which is the same surface a reranker is
now sorting. It is entirely possible this run's clearest effect is negative and lands here.

## Exclusion and truncation rules

Standard: a cell is admitted only when every arm produced an admissible record; discards are
reported per arm with the reason; the budget rule truncates seeds, never tasks. A run that spends
its OpenRouter credit part way through is **incomplete, not negative**, and must be reported the way
`pilot-003-gpt53` is: never pooled, never quoted as an arm comparison.

## What would falsify this

The run is falsified **as a reranker measurement**, independent of any result, if any of:

- `reranking_ran` is false on the reranked arm's searches, or the fallback counter is non-zero on a
  material share of them: then the arm measured no reranker, or measured a blend of two.
- The two recall arms' instruction sha256 differ in `instruction_manifest`: then an instruction
  difference is being read as a reranker effect.
- The two arms did not serve the same generation and corpus fingerprint.
- The search rate on either recall arm falls below 0.50.

The **hypothesis** P1 is falsified by a null or negative paired difference, or by a positive one
whose CI includes zero.

<!-- results are appended below this line; everything above is frozen -->

## Pre-run addendum, 2026-09-02, appended not edited

Written after committing the predictions above and **before any session runs**. It is below the
marker because nothing above a committed marker may be edited, including the numbers it reasons
from. None of it is a result.

**The arm was driven end to end against the real tenant** (`bench-official-002-present`, 55,272
chunks), by hand-building the server command this adapter emits, because the harness checkout that
holds the adapter is not deployed on the serving host yet:

| | |
|---|---|
| server up | 22.9 s to `initialize`, 20 tools, `recall_search` present |
| `reranking_ran` | **true** |
| `rerank_ms` | **377** |
| `embed_ms` | 402 |
| `candidate_pool_size` | **20** |
| `trust_state` / `calibrated` / `failure_code` | `trusted` / `true` / `None` |
| rank 1 for "how should a failed request be retried" | `sessions__ts-retry-cap__p01.md`, verdict `ok` |

**Two things this changes, and neither one may touch a prediction above.**

1. **P7's basis was the wrong number.** The record above reasons from a 1,973 ms first Voyage call
   and says so. The reranking step inside a real search is **377 ms**, so P7's predicted 10% to 40%
   latency rise is likely too high. The prediction stands as written and will be scored as written.
2. **The mechanism argument under P1 is weaker than I stated, in the direction of a larger effect.**
   P1 reasons that a reranker "reorders a list the agent reads in full". `candidate_pool_size = 20`
   against 5 returned hits says it does more than reorder: it **selects which 5 of 20 candidates the
   session ever sees**. A document promoted from rank 12 into the returned set is not a reordering
   the agent can compensate for by reading further, because it was not there to read.

   I am recording this rather than quietly benefiting from it. P1 at 0.55 and P3 at 0.15 were
   written on a mechanism I now believe understates the reranker's reach, and if the run comes in
   positive and significant, this paragraph is why the prediction was too low and not a post-hoc
   explanation of it.
