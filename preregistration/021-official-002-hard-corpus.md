# official-002: the repaired instrument, on a corpus that resists retrieval

Status: DRAFT until committed; a committed record is frozen above the results marker.

Supersedes the grid in `020-official-002.md`, which is otherwise unchanged and stays the record of
what was predicted for the standard feed. This is a **different experiment**, not an amendment:
the corpus is the independent variable.

## Question

`docs/RETRIEVAL_DIFFICULTY.md` measures `voyage` **hit@10 = 1.000** on the 195-document feed every
prior run used. Every memory arm finds the governing session, every time. A run there cannot
separate "the product retrieved badly" from "the agent never searched", so it measures judgement
given perfect retrieval rather than memory as a retrieval system.

**Does the repaired instrument still discriminate when retrieval is no longer free?**

## Why this run and not the standard-feed one

official-002 was launched against the standard feed on 2026-08-30 and stopped after six sessions,
before meaningful spend. The reason for stopping is the reason this record exists: the haystack was
built precisely because retrieval was saturated, and running on the saturated feed would have kept
the defect the tool was built to fix. Comparability with the pilots was the argument for the
standard feed, and it lost to the fact that the comparable number answers the wrong question.

⚠️ **This run is NOT comparable to `pilot-00x`, `resolution-001`, `midband-001`, `diagnostic-010`
or `official-001`.** All used the 195-document feed. No number here may be differenced against a
number there, and the `official-002` run id is kept only because the grid, arms and seeds are the
ones 020 specifies.

## The corpus

`python -m scripts.generate_haystack --scale 25 --seed 1`, generator `8dbb4e2f191c`.

| | standard feed | this run |
|---|---:|---:|
| documents per condition | 196 | **4,900** (196 real + 4,704 synthetic) |
| `bm25` hit@1 | 0.485 | **0.182** |
| `voyage` hit@1 | 0.394 | 0.333 |
| `voyage` hit@10 | **1.000** | **0.879** |
| mean competitors above the target, `voyage` | 1.79 | 10.67 |

Synthetic mix: 2,824 background, 705 topical, 705 semantic, 470 near-miss.

**Containment was verified against the artifact, not taken from the generator's claim.** The
generator reports "discarded 0 for containment"; `scripts/audit_corpus.py` audits the BASE corpus
(258 files) and never sees an assembled haystack, so its "clean" says nothing about these
documents. Checked directly: **no fact term of any of the 34 tasks appears in any of the 4,704
synthetic documents.** Had one, `absent` would be silently broken for that task, and so would
every damage number that depends on the arm not finding the answer.

## What had to change to run it at all

`CorpusManifest.build` already globs `synthetic/**/*.jsonl`, and every adapter, tenant build and
ingest path already understands a haystack root. `assemble()` was the only thing that did not: it
wrote `sessions/` and `distractors/` and nothing else, so a condition corpus could never contain
one. That single gap is why the retrieval measurement and the run had never met.

`AMB_HAYSTACK` is one switch for the whole run, threaded through all four assembler call sites,
because the tenant builder, the grid and the plant audit must see the same corpus or the tenants
serve one thing while the sessions run against another.

## Grid

Unchanged from 020's third correction. 73 task-conditions (12 `absent`, 11 `superseded`, 11
`contradictory`, 12 `adjacent`, 27 `present`), **7 arms**, **5 seeds**, **2,555 sessions**.

Arms: `bare`, `claude_md`, `placebo`, `recall`, `mempalace`, `fs_grep`, `recall_prefetch`.
Not running: `oracle_memory` (bundles carry no condition), `protocol`, and the four vendor stubs
with no `adapter.py`. Plugins and hooks OFF, every arm `--bare`.

Model `deepseek/deepseek-v4-flash`, prices `--price-in 0.0574 --price-out 0.1148 --price-as-of
2026-08-22`.

## Endpoints

Per preregistration 005 and 017, unchanged: net harm by stratum, damage rate by condition,
abstention rate, wrong-fact-applied, and the usefulness composite (Youden's J over sensitivity on
`present` and specificity on the adversarial four).

## Predictions

House prior, measured: I over-predict magnitudes by two to four times, and eleven of twelve past
predictions were too high. These are set low deliberately.

1. **`recall`'s admitted search rate stays above 0.70.** A harder corpus changes what searching
   FINDS, not whether the agent searches; the instruction is unchanged. Falsified below 0.50, at
   which point the endpoints are void and nothing is reported.
2. **At least 4 cells where a memory arm succeeds and `claude_md` fails.** Lower than 020's 8,
   because at `voyage` hit@10 = 0.879 roughly one query in eight no longer finds its target in the
   top ten, so some benefit that was free on the standard feed is now unavailable.
3. **`recall` and `recall_prefetch` differ by at least 3 cells.** This is the prediction the hard
   corpus exists to make possible: on the saturated feed the two are near-identical by
   construction. The gap is the agent's decision to search, now that searching can fail.
4. **`fs_grep` scores below both `recall` and `mempalace` on the usefulness composite.** A term
   ranker is what the near-miss tier is designed to defeat: BM25 hit@1 falls 0.485 to 0.182 against
   `voyage`'s 0.394 to 0.333. If `fs_grep` wins anyway, that is the headline and it is publishable
   against this project's own product.
5. **Damage is non-zero and below 0.20** for every memory arm.
6. **Cost between $6 and $12** for 2,555 sessions plus five tenant builds. ⚠️ The embedding half is
   genuinely unknown: no voyage spend has ever been recorded in this repository, and this run
   embeds roughly 143,000 chunks against the 5,600 the standard feed needed. This is the
   prediction I am least confident in and the one most likely to be wrong by more than 2x.

## What would falsify the run rather than a prediction

* Prediction 1 falsified (search rate below 0.50): endpoints void, nothing reported.
* `TWO_SIDED` empty again at 5 seeds: the seed argument in 020 was wrong and the answer is more
  seeds, not a harder corpus.
* Any tenant serving a generation built from a different corpus than the run assembled.
* `scripts/verify_run.py --all` failing to verify this run's own directories afterwards.

## Preconditions

1. Haystack generated and containment-verified. **Done**, above.
2. All five `bench-official-002-*` tenants rebuilt against the 4,900-document corpus. The ones
   built earlier today are from the 196-document feed and their stamps will not match; the
   adapter refuses on that, which is the guard working.
3. `AMB_ALLOW_NAMED_PATHS=1`, per 020's third correction: the serving account cannot write
   `/srv`, `/opt` or `/var/lib` and has no passwordless sudo, so the neutral root is
   unreachable without an interactive password. The account's home path already appears in
   eleven published artifacts and is on the ratchet in `tests/test_no_host_inventory.py`, so
   the marginal disclosure of this run is zero.

   ⚠️ This record deliberately does NOT write that path out. A committed preregistration
   cannot be edited, so a host named in one is permanent; 020 carries the literal path for
   exactly that reason and had to be ratcheted instead of fixed. The guard caught this record
   while it was still a draft, which is the only moment it is cheap.

<!-- results are appended below this line; everything above is frozen -->


## Amendment, 2026-08-31: the run measures recall at a pinned commit, not the released 0.11.0

Written **before** the tenant build and before any measurement, and appended rather than edited.

### What changed

The benchmark's interpreter carried `recall-rag 0.11.0` from PyPI. It now carries recall built from
a detached worktree pinned at **`8f6b5d1f414ad594c658f108057ce1c7b49e9fd5`** ("Serve every indexing
path from the content-addressed embedding cache", #549, merged 2026-08-30T21:33:46Z).

### Why

The embedding cache existed in 0.11.0 but nothing user-facing called it: `GenerationManager.build`,
the route this benchmark takes, called `embed_passages` directly. Measured on the assembled corpora
before deciding:

| | documents embedded |
|---|---:|
| five conditions, no cache | 24,510 |
| five conditions, cached | 4,945 |
| saving | **79.8%** |

The saving is that large because the cache is keyed on `(embedder identity, purpose, dim, text)`
and **not** on the tenant, while the five conditions share one 4,704-document haystack and all but
241 of their real documents.

### Why this does not change what is being measured

#409's diff touches indexing, seeding, the setup wizard and the MCP **write** path. The one hunk in
`recall_mcp/service.py` wraps `Indexer(...)` in `default_cache()`; nothing on the query path moves.
A cache hit returns the same vector the embedder would have produced, stored as float32, which is
the width `pgvector` stores anyway. **So the recall arm's retrieval behaviour is identical to
0.11.0's**, and what changed is the cost of building the corpus it retrieves from.

⚠️ Corrected inline before committing: the PR is **#549**, not #409. Left visible rather than
silently fixed, because the number above is the one a reader would use to check the claim.

### What this costs, stated plainly

**Prediction 5 is no longer a clean test and must not be scored as one.** It predicted the voyage
spend for this run, and said it was the prediction least confident and most likely to be wrong by
more than 2x. I have now changed the cost basis of the thing it predicts, in the direction that
makes it look good, *after* reading the prediction. Any agreement between prediction 5 and the
measured spend is therefore uninformative. Report the spend as an observation; do not count it in
the prediction scoring.

The other four predictions are untouched: they are about search rate, strata occupancy, damage
rates and abstention, none of which the cache can reach.

### A trap for anyone reproducing this

`pip list` in that virtualenv still reports **`recall-rag 0.11.0`**, because the project version was
never bumped past the release. It is not PyPI's 0.11.0. **The commit is the identity, the version
string is not.** Verify with the symbols rather than the version:

```
python -c "import recall.cache as c; print([n for n in ('ENV_CACHE_PATH','ENV_CACHE_MAX_MB','DEFAULT_CACHE_MAX_MB') if hasattr(c,n)])"
```

Post-549 prints all three; PyPI 0.11.0 prints none.

### Rollback

`pip install recall-rag==0.11.0` restores the released version. The pinned worktree stays on the
host so the exact tree under test can be re-read after the fact.
