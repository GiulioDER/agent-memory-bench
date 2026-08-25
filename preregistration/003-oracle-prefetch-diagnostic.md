# Preregistration 003: Oracle and proactive retrieval diagnostic

This record freezes the diagnostic protocol before any new live measurement. The diagnostic arms
are reference tracks and will not enter the ranked product comparison.

## Frozen design

* Arms: `claude_md`, `recall`, `oracle_memory`, `recall_prefetch`.
* Task roster: every executable `ts-*` task discovered under `tasks/` at measurement start.
* Corpus: `corpus/manifest.json`, plus `corpus/oracle_memory/bundles.jsonl` and its catalog digest
  recorded in the run artifact.
* Oracle evidence: exact corpus backed excerpts, formatted by the shared formatter. The bundle is
  supplied before the agent starts, without MCP tools or filesystem access to the bundle.
* Proactive evidence: the exact task prompt is passed to the pinned `python -m recall.cli search`
  path with the frozen RE call tenant, embedder, trust mode, evidence option, and `k`.
* Model, provider, Claude Code version, timeout, permission mode, seeds, repetitions, and prices
  are written into the run environment artifact before the first session.
* Primary metrics: task success, oracle headroom, natural memory lift, prefetch memory lift,
  access gap, and prefetch gap.
* Primary uncertainty: cluster bootstrap intervals that resample tasks. Pairwise tests are
  secondary consistency checks only.

## Exclusions

A cell is excluded for missing or malformed oracle injection, a bundle digest mismatch, leaked
oracle content in a non oracle arm, failed prefetch, missing natural RE call tools, or any mismatch
in task prompt, repository digest, model, timeout, permission mode, or declared tool list. A
prefetch abstention with a valid successful prefetch record remains an admitted behavioral result.

## Interpretation

The oracle is a ceiling control. A high oracle result with a low natural result indicates an
agent invocation or query formulation bottleneck. A high oracle and prefetch result with a low
natural result indicates a discoverability bottleneck. A high oracle with a low prefetch result
indicates retrieval loss. A low oracle result means the task is not established as solvable through
memory alone. No result from this diagnostic may be described as proof of uniqueness.

No live measurement may be published until this file is committed and the run artifact records
the exact commit and all exclusion reasons.
