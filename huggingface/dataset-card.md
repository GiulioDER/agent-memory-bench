---
license: apache-2.0
language:
  - en
pretty_name: agent-memory-bench experience corpus
size_categories:
  - n<1K
task_categories:
  - text-generation
tags:
  - agents
  - agent-memory
  - coding-agents
  - benchmark
  - retrieval
  - preregistered
  - claude-code
configs:
  - config_name: sessions
    data_files: corpus/sessions/**/*.jsonl
  - config_name: distractors
    data_files: corpus/distractors/*.jsonl
---

# agent-memory-bench: the experience corpus

The neutral feed for a preregistered, execution-graded benchmark of **memory layers for coding
agents**. Every memory product under test ingests these same bytes through its own write path,
then an agent is given real coding work in a real repository where success depends on something
established in an earlier session, and the artifact is graded **by execution**: the task's tests
pass or they do not.

There is no LLM judge anywhere in the primary endpoint.

- **Site, method and leaderboard: https://giulioder.github.io/agent-memory-bench/**
- Code, task suite, checkers, preregistrations and results:
  https://github.com/GiulioDER/agent-memory-bench

The site states the design and how a product gets an arm; the repository is where every claim can
be re-derived. Start at the site if you want to know what this measures, at the repository if you
want to check it.

## What this dataset is

`corpus/` is a set of recorded Claude Code sessions in JSON Lines, one file per session:

```json
{"role": "user", "content": "...", "ts": "2026-07-03T14:00:00Z"}
{"role": "assistant", "content": "", "tool_name": "Bash", "tool_input": "...", "tool_result": "...", "ts": "..."}
```

Two kinds of session, in a deliberate ratio:

| split | what it is | count |
|---|---|---|
| `sessions/<task_id>/` | **signal**: a session in which a governing fact for that task is established | 40 |
| `distractors/` | **mundane** sessions establishing no governing fact | 156 |

Measured 2026-09-01: **196 files in `corpus/manifest.json`**, 40 under `sessions/` and 156 under
`distractors/`, with manifest and disk in exact agreement in both directions. Two of the 40 are
`sessions/smoke/`, which are bring-up wiring rather than signal, so the distractor to signal ratio
is **4.11:1** counting the 38 real signal sessions and 3.90:1 counting all 40. (`corpus/README.md`
is shipped in this dataset and carries both figures: 39 signal sessions and 4.00:1 as measured
2026-08-29, and a dated correction to today's counts underneath it. The corpus gained one session
between those dates, so the older figure is dated rather than wrong, and it is left standing on
purpose.)

`corpus/manifest.json` carries the sha256 of every file, and a session on disk but absent from the
manifest is invisible to every arm, which once made six tasks unwinnable by retrieval for weeks.

Three properties are enforced by tooling rather than promised:

1. **Content is verbatim agent output.** Sessions are recorded live against a staged incident. A
   recording that fails to surface the fact is re-staged and re-run, never edited.
2. **Timestamps are recording metadata mapped onto a project timeline** (40 seconds per turn from
   09:00 UTC), so the corpus reads as weeks of history rather than one afternoon. Identical bytes
   for every product.
3. **Each governing fact lives in exactly one task's sessions.** `scripts/audit_corpus.py` asserts
   presence, containment and locus. Cross-session tasks distribute one fact across several of
   their own sessions, one share each, and the audit asserts that too.

## What this dataset is not

**It does not measure the write path, and that is half of every product being tested.** The corpus
is bulk ingested once, before the grid, and never written to again. The agent never forms a memory
from its own work, so nothing here says whether a product captures what an agent learns or whether
what it captured survives to the next session. Extraction and consolidation products get no credit
for the thing they sell.

**It is not a leaderboard.** No multi-product run has happened. Four of the eight arms the harness
reserves a row for have a package docstring and no adapter, and no third-party product is named
here before it has been shown its own adapter and frozen configuration and given a right of reply.

**It is not clean of its recording environment.** Because content is verbatim, tool results carry
the recording machine's paths and usernames. Sessions recorded on a Windows development machine are
**pipeline-validation recordings**; the corpus for the preregistered run is recorded inside the
Docker harness, where paths and users are neutral by construction. See the hygiene note below.

## Loading

```python
from datasets import load_dataset

sessions = load_dataset("Gde05/agent-memory-bench-corpus", "sessions", split="train")
distractors = load_dataset("Gde05/agent-memory-bench-corpus", "distractors", split="train")
```

To verify integrity against the manifest, clone the GitHub repository and run
`python scripts/audit_corpus.py`, which asserts presence, containment and locus rather than only
checksums.

## Contamination

This corpus is the **input** to the benchmark, not its answer key. Task statements, checkers and
reference solutions live in the GitHub repository and are deliberately not mirrored here, so that
a model trained on this dataset gains exposure to the haystack without gaining the graded
artifacts.

Nothing prevents scraping the GitHub repository as well. If you are training a model and intend
this benchmark to remain informative about your model, exclude
`github.com/GiulioDER/agent-memory-bench` from your crawl.

## Standing limits on every number this corpus has produced

1. Only the read path is measured (above).
2. The instruction budget changed on 2026-08-28. Every published number predates it, and was
   measured when one arm carried 5,428 characters of behavioural instruction and others carried
   231 or none.
3. Three protocol-sensitive fixes landed on 2026-08-29: a grader that rejected correct solutions
   about 40% of the time, a checker crash that discarded a whole paired cell rather than failing
   one arm, and cost estimates that charged cache reads at the fresh-input rate. **A rerun is
   therefore not protocol-identical to the frozen runs.**
4. The corpus feed changed on 2026-08-29, 125 entries to 195. Never difference a number measured
   after that date against one measured before it.
5. Compare runs on **tokens**, never on dollars: two published runs were priced on different
   bases.

`docs/STATUS.md` in the repository is the dated statement of what has been measured, what has been
built and not measured, and what is blocked. It carries the command that re-derives each claim.

## Citation

```bibtex
@misc{agentmemorybench2026,
  title  = {agent-memory-bench: an execution-graded benchmark of memory layers for coding agents},
  author = {{GiulioDER}},
  year   = {2026},
  howpublished = {\url{https://github.com/GiulioDER/agent-memory-bench}}
}
```

## License

Apache 2.0, matching the repository.
