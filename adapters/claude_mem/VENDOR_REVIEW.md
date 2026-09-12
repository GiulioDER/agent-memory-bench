# Vendor review: Claude-Mem

Review status: adapter prepared; the first batched cache smoke found a recency window mismatch,
which is fixed and pending one cell confirmation.

The frozen integration is the official `thedotmack/claude-mem` plugin at tag `v13.24.0`, commit
`ffe75a81e71b190644195a0ae9a5b6997757317c`. The adapter copies the pinned plugin into an isolated
Claude configuration, runs the shipped worker and MCP server scripts, and records lifecycle hook
evidence without storing raw hook payloads in the ledger.

The benchmark feed is loaded through Claude-Mem's own worker import endpoint, `/api/import`, which
is the route used by the repository's shipped `scripts/import-memories.ts` utility. The adapter
uses a stable `claude_mem` project name so the imported observations are visible to the isolated
session worktrees, whose basename is also `claude_mem`.

The vendor import route writes SQLite immediately, while the pinned worker backfills Chroma
asynchronously. On the AMB corpus the upstream loop writes one observation at a time and keeps the
MCP search queue busy for hours. The adapter therefore creates a preparation-only copy of the
pinned worker that uses the same vendor formatter, document IDs, metadata, Chroma writer, and
watermark store in larger batches. Claude Code sessions always load the untouched pinned plugin.
The run metadata records this preparation path, and the adapter refuses to apply it if the pinned
worker's backfill shape changes.

The first live smoke on 2026-09-08 confirmed the cache barrier and the untouched plugin, but the
MCP search call returned no result within its 30 second tool window. Direct vendor checks showed
that Chroma was healthy and returned results when `date_start` was supplied, while the default
search window excluded the imported observations because the adapter had stamped them in 2023.
The adapter now anchors imported timestamps to the ingestion time, preserving the vendor's
default recent search behavior during the benchmark.

The lifecycle hooks remain shell-oriented and Claude-Mem has documented Windows integration failure
modes. The adapter invokes the shipped Node and Bun runner files directly in the generated hook
settings and keeps that portability change explicit in the run metadata.

Invitation log:

| date | event |
|---|---|
| 2026-09-07 | adapter prepared; vendor review not yet requested |
| 2026-09-08 | semantic cache preparation fix added; live smoke pending |
| 2026-09-08 | recency window mismatch found in the first smoke; ingestion timestamp fix added |
