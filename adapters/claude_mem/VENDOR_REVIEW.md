# Vendor review: Claude-Mem

Review status: adapter prepared; measurement not started.

The frozen integration is the official `thedotmack/claude-mem` plugin at tag `v13.24.0`, commit
`ffe75a81e71b190644195a0ae9a5b6997757317c`. The adapter copies the pinned plugin into an isolated
Claude configuration, runs the shipped worker and MCP server scripts, and records lifecycle hook
evidence without storing raw hook payloads in the ledger.

The benchmark feed is loaded through Claude-Mem's own worker import endpoint, `/api/import`, which
is the route used by the repository's shipped `scripts/import-memories.ts` utility. The adapter
uses a stable `claude_mem` project name so the imported observations are visible to the isolated
session worktrees, whose basename is also `claude_mem`.

Known qualification risk: upstream lifecycle hooks are shell-oriented and Claude-Mem has documented
Windows integration failure modes. The adapter therefore invokes the shipped Node and Bun runner
files directly in the generated hook settings and keeps that portability change explicit in the
run metadata.

Invitation log:

| date | event |
|---|---|
| 2026-09-07 | adapter prepared; vendor review not yet requested |
