---
title: Agent Memory Bench
emoji: 🧠
colorFrom: indigo
colorTo: gray
sdk: static
app_file: index.html
pinned: false
license: apache-2.0
short_description: Execution-graded benchmark of memory for coding agents
tags:
  - leaderboard
  - agents
  - agent-memory
  - benchmark
---

# agent-memory-bench

A preregistered, execution-graded benchmark of **memory layers for coding agents**, measured by
task success on real coding tasks executed by Claude Code. Tests pass or they do not; no LLM judge
appears anywhere in the primary endpoint.

- Canonical site: **https://giulioder.github.io/agent-memory-bench/**
- Repository: **https://github.com/GiulioDER/agent-memory-bench**
- Corpus: **https://huggingface.co/datasets/Gde05/agent-memory-bench-corpus**

This Space is a mirror. The canonical site is the GitHub Pages deployment above, and the two are
built from the same `site/` directory, so if they ever disagree the Pages copy is the one to
trust.

## The board is empty on purpose

`site/data/leaderboard.config.json` carries `"official_run": null`, and a number reaches the page
only through a run's `leaderboard_summary.json`. No multi-product run has happened, so there is
nothing to show and the page says so rather than filling itself with pilots.

Two rules the page enforces in code rather than promising in prose:

- **No third-party product is named before it has been told.** A vendor is invited to review its
  own adapter and frozen configuration before any measured run. Undisclosed arms appear as
  `product_a`, `product_b` and so on, with the integration type withheld as well, because "SaaS
  API" against a short field of candidates is most of an identification on its own.
- **No multi-product ranking ships while the write path is unmeasured**, or it ships titled for
  what it actually measured: `Retrieval over a bulk-ingested corpus`. The corpus is bulk ingested
  once before the grid and never written to again, so a ranking built from it ranks retrieval and
  gives no credit to extraction or consolidation.

## What this Space is

The repository's `site/` directory, deployed verbatim with no build step. It is the same set of
static pages served from GitHub Pages, mirrored here so that the benchmark is reachable from where
people look for benchmarks. `method.html` states the design, `submit.html` states how a product
gets an arm, and `docs/STATUS.md` in the repository states the dated truth about what has actually
been measured.
