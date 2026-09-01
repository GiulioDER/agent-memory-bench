# Vendor review: cognee (`cognee`)

Status: **adapter landed, awaiting the pre-review window.** Nothing has been run and no number
exists. This file states every judgement call the adapter makes, so cognee's maintainers can
dispute any of them before a run is preregistered rather than after a number is published.

Wired against `cognee[fastembed]==1.5.3` and `cognee-mcp==0.5.5` (PyPI), read from the published
wheels on 2026-09-01. **Nothing in this file has been executed yet**: the adapter, the driver and
the preflight were written against the shipped source, and `scripts/cognee_preflight.py` exists to
turn every claim below into a check on a real install before a grid spends anything.

## How the arm is wired

| surface | what it is |
|---|---|
| **Retrieval** | the published stdio MCP server, `cognee-mcp --transport stdio`, in direct mode |
| **Ingest** | the published Python API, `cognee.add` then `cognee.cognify`, driven by `ingest_driver.py` in cognee's own venv |
| **Isolation** | one store directory per namespace (`DATA_ROOT_DIRECTORY`, `SYSTEM_ROOT_DIRECTORY`) holding its own SQLite, LanceDB and Kuzu files, plus one dataset per namespace; store and feed are deleted and rebuilt on every ingest |
| **Instruction** | `adapters/_shared/memory_protocol.md` verbatim, one sentence naming `mcp__cognee__recall`, plus `instruction_appendix.md` (977 bytes, cap 1,200) |
| **Admission** | the `mcp__cognee__` prefix must appear in the session's tool list |

The frozen config is `config.frozen.json`, and its sha256, along with `ingest_driver.py`'s, is
published in every session record.

## Six judgement calls, stated so they can be disputed

**1. The corpus is rendered to Markdown before ingest, not handed over as transcripts.**
The corpus is Claude Code session transcripts as JSONL. cognee classifies documents by extension
and has no conversation-transcript mode, so the arm renders each transcript with the harness's own
`render_corpus`, the same renderer the `fs_grep` control uses, with names mirroring corpus paths
(`sessions__ts-dedup-order__p01.md`). If cognee would rather be measured on a different
representation, say so and we will run that instead, or both as labelled variants.

**2. One of your three memory tools reaches a graded session: `recall`.**
`remember` and `forget` are withheld. This is not a judgement about cognee. The corpus is frozen
after ingest and no runner currently calls `MemoryAdapter.snapshot`/`restore`, so a session that
wrote to the store would change the store the next seed reads, and the arm would be measured
against a store that drifted under it. Every arm is treated the same way: `recall` (the product)
is allowed 2 read tools of its 16, `mempalace` 20 of its 44.

⚠️ **We note the asymmetry that leaves, because it is real and it is not in cognee's favour.**
One tool of three is the smallest surface any arm has been given, and the memory API is
deliberately small by design rather than restricted by us. If you believe that under-represents
what an agent can do with cognee, this window is exactly the place to say so.

**3. Extraction runs on the same model and provider the benchmark itself is priced on.**
`LLM_PROVIDER=custom`, a litellm `openai/`-prefixed model, and the run's own endpoint, so the
ingest bill lands in the run's price basis rather than a second one nobody agreed. The key is read
from the environment and never written into this directory. If you would rather your product be
measured with a stronger extraction model, name it, and we will run that as a labelled variant and
publish both bills.

**4. Ingest refuses above a cost ceiling, using cognee's own estimator.**
`ingest_driver.py` runs `cognify(dry_run=True)` first and stops before any LLM call when the
estimate exceeds `ingest_cost_ceiling_usd` in the frozen config. This is the single reason cognee
is the arm being built next: the hard corpus is 4,889 documents per condition, the previous
third-party arm's ingest cost was discovered by paying it, and cognee is the one candidate whose
bill can be quoted first.

We report those token counts as an **estimate** and say so in the run record, because your own
estimator's docstring is explicit that it excludes embeddings, uses output-token heuristics, and is
an upper bound on a re-run. If cognee exposes provider-billed usage for a plain `cognify` that we
have missed, tell us and we will report the measured number instead.

**5. Embeddings are local, through the `fastembed` extra.**
`EMBEDDING_PROVIDER=fastembed`, `BAAI/bge-small-en-v1.5`, 384 dimensions, set explicitly. Two
reasons, both about honesty rather than performance: it keeps the only hosted cost the one your
estimator can predict, and `EmbeddingConfig` otherwise defaults to `openai/text-embedding-3-large`
while, per your `.env` template, an unset embedding key silently reuses `LLM_API_KEY`. A partial
configuration therefore bills a provider nobody chose. If a different embedder shows cognee better,
name it.

**6. Agent scoping is turned off.**
`COGNEE_MCP_AGENT_SCOPED=false`. With it on, the server auto-names a per-client dataset and Claude
Code would search `claude_code_memory`, which is not the dataset the harness ingested into: the arm
would retrieve nothing, every session, and look like a product that finds nothing. That default is
right for a person and wrong for an experiment.

**7. The shared haystack is ingested ONCE into a base store and copied, not re-extracted per
condition.**
The run has five conditions whose corpora share ~4,704 synthetic documents. Measured 2026-09-01
via your own dry run: 1,616 tokens and two LLM calls per document, so re-extracting that haystack
per condition is roughly 7.6M tokens and 9,400 calls, five times, for an identical result each
time. The arm therefore builds one store, copies it per condition, and feeds each condition only
the documents that differ. The copy is refused unless it holds EXACTLY the shared set, in both
directions: a thinner base measures a corpus nobody described, a fatter one contaminates every
condition.

This forced one change we would otherwise not have made: **every namespace ingests into a single
dataset name** rather than one derived per namespace. Isolation is the store directory, so each
namespace still has its own SQLite, LanceDB and Kuzu files; a per-namespace dataset name simply
makes a copied store unreadable by the condition that copied it. If that is wrong about how
datasets are meant to be used, tell us.

⚠️ **We have not yet verified that the copy is equivalent to a monolithic build**, and we are
saying so rather than discovering it later. The check is written
(`scripts/cognee_base_store_probe.py`: a copy retains its contents, accepts further ingest, leaves
the original untouched, and returns identical top-k results across several queries) and has not
run, because the development host's CPU cannot execute LanceDB (see below). No run will set the
base-store variable until it passes.

## The host we developed on cannot run your vector store, and that is our problem, not yours

`import lancedb` dies with SIGILL on this workstation: it is a Xeon X5690, which has SSE4.2 and no
AVX, and the lancedb 0.38.0 / pylance 0.36.0 wheels assume more. Everything else works there,
including fastembed and onnxruntime. We mention it because it shapes what we have verified so far
and because, if you would rather the arm ran on `pgvector` (which cognee supports first-class and
which our other arms already use) than on a machine chosen for AVX, that is a configuration change
we would make on your say-so and record as such.

## Two costs we will publish, and want you to check we have them right

- **Ingest is billed per document**, because extraction is an LLM pass. This is the structural
  difference between cognee and a local-embedding memory product, and the run record will state it
  in those terms rather than printing a token count beside another arm's zero without comment.
- **Retrieval may also be billed.** `recall` auto-routes when `search_type` is unset, and the
  routes include completion types that call an LLM at query time. We are **not** pinning
  `search_type`, because the auto-routing is part of the product; the consequence is that a graded
  session can spend tokens on retrieval, and the run record will carry that separately from the
  agent's own model cost.

## What is held fixed, and is not ours to tune

Chunker, chunk size, `top_k`, ontology, structured-output framework and search-type routing are all
left at cognee's defaults. Where the adapter sets a value it is either isolation (store paths,
dataset name), a documented trap (the embedding pair, agent scoping), or the cost ceiling.

## One environment refusal you should know about

`cognee/__init__.py` calls `dotenv.load_dotenv(override=True)` at import. A `.env` in scope
therefore **beats** the configuration this arm passes in, silently, while the run record still
names the frozen config. The adapter refuses to run with such a file in scope, and the driver
checks again at import. This is a note about how the benchmark protects a comparison, not a
complaint: it is a reasonable default for a developer.

Worth stating precisely, because we got it wrong once ourselves before reading
`dotenv.find_dotenv`: the search starts at the **importing module's own directory**, so the file
that would capture this arm is one beside or above the **virtualenv**, not one beside the working
directory. The working directory applies only in a REPL, under a debugger, or when frozen. Both
roots are checked.

## What we are asking you to review

Before any preregistered run, we invite cognee's maintainers to review, with a two-week window:

1. **This arm's frozen config** (`config.frozen.json`, sha256 pinned in the preregistration) and
   `ingest_driver.py`: the integration route, its settings, and the one-line tool instruction the
   arm's system prompt carries.
2. **The corpus format** (`corpus/README.md`) and the rendering in call 1 above.
3. **Version pins**: `cognee[fastembed]==1.5.3`, `cognee-mcp==0.5.5`.

Config changes you request before the freeze are applied and re-hashed. After the freeze, disputes
go next to the published per-session streams, not to a configuration argument.

## Two offers, both cost-neutral for the benchmark's integrity

- **Sponsored credits.** This arm's API traffic (extraction at ingest, and any completion at
  retrieval) can run on keys or credits you provide. Execution stays on our harness, same host,
  same model, same admission gate as every arm; the run artifact records who funded which arm. If
  you decline, we fund it and say so.
- **A vendor-tuned variant.** If you believe a different configuration shows cognee better, submit
  it: we run it as an additional, clearly-labelled arm variant inside the same harness.

What we do not offer: vendor-executed cells in the canonical table. A number produced outside the
shared harness is not comparable and not verifiable, and this benchmark exists because the field
has enough of those.

## After publication

The one-command Docker reproduction and the full per-session artifacts are public. We invite you to
re-run your arm and publish what you find; confirmations and disputes are both engagement with the
method, and the frozen configs and streams are the referee.

## Record

| date | event |
|---|---|
| YYYY-MM-DD | invitation sent (link to public issue) |
| YYYY-MM-DD | first ping |
| YYYY-MM-DD | second ping |
| YYYY-MM-DD | response received / window closed with no response |

### Vendor response, verbatim

(unedited, or "none received by the deadline")
