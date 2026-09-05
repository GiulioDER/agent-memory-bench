# 027: cognee-001, a joined pass over official-003's five conditions

Status: DRAFT until committed; a committed record is frozen above the results marker.

⚠️ **This is a JOINED PASS, not an arm of `official-003`, and the distinction is the first thing a
reader needs.** `official-003` ran eight arms over five conditions and finished on 2026-09-01 with
**317 admitted cells of 365** (`absent` 52/60, `adjacent` 57/60, `contradictory` 51/55, `present`
111/135, `superseded` 46/55). Its roster is frozen in preregistration 026 and does not contain
`cognee`. A cell is admitted only when **every** arm in the run produced a record, so an arm cannot
be added to a finished grid: `cognee` runs alone over the same five condition corpora and is joined
to official-003's records on `(task_id, seed, condition)`.

What that costs, stated now rather than discovered later: the joined set is at most official-003's
admitted set, and in practice smaller, because a cell survives only if cognee also produced a
record for it. Every contrast below is therefore computed on **pairs that exist in both passes**,
which is a different denominator from official-003's own headline and must never be printed as
though it were the same one.

## Question

On the cells where both passes produced a record, does `cognee` differ from `protocol` (the
instruction-only control) and from `recall` in task success?

## Arms and configs

| arm | adapter config sha256 | versions |
|---|---|---|
| `cognee` | recorded per session as `config_sha256` + `driver_sha256` in `environment.json` | `cognee[fastembed]==1.5.3`, `cognee-mcp==0.5.5`, extraction `openai/deepseek/deepseek-v4-flash` via OpenRouter, embedding `fastembed/BAAI/bge-small-en-v1.5` (local) |
| `protocol`, `recall`, and the other six | unchanged from `official-003` | as recorded in that run's `environment.json` |

The comparison arms are **not re-run**. Their records come from `official-003`, which is what makes
this a join rather than a new grid.

## Grid

The five corpus conditions of `official-003` (`absent`, `adjacent`, `contradictory`, `present`,
`superseded`), the same task selection per condition, **5 seeds**, model
`deepseek/deepseek-v4-flash`, `--memory-instruction protocol`, the ~4,900-document haystack
(`AMB_CORPUS_FLOOR=4000`), prices `--price-in 0.0574 --price-out 0.1148 --price-as-of 2026-08-22`
to match every prior comparable run. Run on VPS2. Run id `cognee-001`, one directory per condition.

## Endpoints, in reporting order

1. **Primary:** task success, `cognee` vs `protocol`, on jointly-admitted cells, per-task cluster
   bootstrap CI and McNemar exact.
2. Task success, `cognee` vs `recall`, same cells, same statistics.
3. Search rate for `cognee` per condition, against the 0.50 floor from preregistration 014. Below
   it the endpoints above are not interpretable and must be reported as such rather than quoted.
4. Ingest cost in TOKENS (`ingest_input_tokens` + `ingest_output_tokens`), per condition, beside
   `ingest_wall_time_ms`.
5. Joined-cell count, and the number of official-003 admitted cells lost to this join.

## Predictions

Written knowing the house prior: eleven of twelve prior predictions in this project were falsified,
every one too high by two to four times. These are hedged downward accordingly. I have seen
official-003's admitted counts (above) and **no arm-level success rate from it**, so P1 to P6 are
unseen with respect to every quantity they name.

| # | Claim | Prediction | Confidence |
|---|---|---|---|
| P1 | jointly-admitted cells | 230 to 300 of official-003's 317 | 0.65 |
| P2 | `cognee` vs `protocol`, direction | positive | 0.60 |
| P3 | `cognee` vs `protocol`, significance | p < 0.05 | **0.25** |
| P4 | `cognee` vs `recall`, direction | negative (recall ahead) | 0.65 |
| P5 | `cognee` search rate, pooled | above the 0.50 floor | 0.70 |
| P6 | `cognee`'s best condition is `present` | holds | 0.60 |
| P7 | ingest tokens, all five conditions | 8M to 45M depending on base-store reuse | 0.70 |

**P3 is deliberately low.** `official-002` measured recall as both the most useful and the most
damaging arm, and `protocol-025` found an instruction-only arm repays 17 cells before any retrieval
happens. An arm that retrieves through a knowledge graph built by an LLM has more ways to lose that
margin than to beat it, and one read tool of three is the smallest surface any arm here has had.

**P4 predicts cognee loses to recall, and I am saying so before running it.** recall serves this
corpus from a certified generation with a fitted threshold; cognee serves a graph extracted by a
cheap model from the same documents. The interesting outcome is the size of the gap, not its sign.

## Exclusion and truncation rules

- **Truncate seeds, never tasks.** If credit runs short, drop from seed 5 downward across every
  condition, and record which seeds ran. Dropping tasks would change the suite.
- A condition whose cognee ingest is refused by the token ceiling is **not** run at reduced corpus;
  it is reported as not run.
- Cells where cognee produced no record are excluded from every contrast and counted in endpoint 5.
- `cognee` search rate below 0.50 in a condition voids that condition's endpoints 1 and 2, which
  are then reported as uninterpretable rather than as a null.

## What would falsify this

P2 falsified by a negative or zero direction; P3 by p >= 0.05; P4 by cognee matching or beating
recall; P5 by a pooled search rate at or below 0.50; P7 by ingest tokens outside 8M to 45M.

## What I already know, and where it lives

- The ingest estimate is measured, not guessed: 1,616 tokens and two LLM calls per document
  (cognee's own `cognify --dry-run` over the 196-document corpus, 2026-09-01, in Docker).
- cognee's dollar figure is unusable for a ceiling: it prices from its own table and
  `deepseek-v4-flash` is absent from it, so the binding ceiling is in tokens.
- The arm has **never executed a session anywhere**. The preflight had not fully passed at the time
  this record was written; the MCP server cannot start on the development workstation because its
  Xeon X5690 has no AVX and LanceDB needs it. VPS2 is an AMD EPYC with AVX2, which is why the run
  goes there.
- The base-store reuse exists and is **unverified**; `scripts/cognee_base_store_probe.py` must pass
  on VPS2 before `COGNEE_BASE_STORE` is set for this run. If it does not, every condition ingests
  in full and P7 lands at the top of its range.

## Confounds I can name now

1. **The join is not the grid.** cognee's cells are a subset of official-003's admitted set, so a
   difference against `protocol` could come from which cells survived rather than from the arm.
   Endpoint 5 exists to make that visible; a large loss makes 1 and 2 weak whatever they say.
2. **Two passes, two moments.** official-003's arms ran on 2026-09-01 and cognee runs after, on the
   same host, same model id and same prices. A provider-side model change between the two would be
   invisible and would look like an arm effect.
3. **The extraction model is a choice we made.** cognee's graph is only as good as the model that
   built it, and we pointed it at the cheap model the benchmark itself runs on. A stronger
   extraction model is a different product configuration, and a poor result here is partly a result
   about that choice.
4. **One read tool of three.** Every arm's write surface is withheld, but cognee's read surface is
   the smallest in the benchmark. That is the product's own API shape rather than a restriction we
   invented, and it still bounds what the arm can do.
5. **Not published.** cognee's maintainers have not had the review window `VENDOR_REVIEW.md`
   promises. Numbers from this run stay unpublished and the arm stays unnamed on the site until
   they have.

<!-- results are appended below this line; everything above is frozen -->

## Post run publication amendment, 2026-09-05

This amendment was requested after `cognee-001` completed. It does not rewrite the frozen
prediction or pretend that the original search rate floor was absent before measurement.

For publication of this joined arm, search rate is a reported diagnostic rather than an
eligibility gate. A low rate remains visible in the leaderboard and in the condition breakdown,
but it no longer voids the task success endpoints. The result is still computed only on the
jointly admitted cells, with the join size, discarded cells, errors, ingestion tokens and wall
time published beside it.

The reason for this amendment is that choosing not to invoke a product's memory tool is itself
observable product behaviour. It must be exposed to readers, not silently used to discard a run
that has already consumed the declared resources. A vendor may challenge the adapter or request
a replacement run, and any replacement will be published as a separate run with its own evidence.
