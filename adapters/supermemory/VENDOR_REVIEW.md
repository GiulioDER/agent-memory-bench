# Vendor review: Supermemory

Review status: measurement completed; invitation pending.

The frozen integration is the official `supermemoryai/claude-supermemory` plugin at commit
`e6227edc4f33b83317cfde2e7cd9790c794d22d1`. AMB copies the vendor plugin files into an isolated
Claude configuration and wraps the unchanged hook entry points only to record hook execution for
the admission gate. The default service URL is Supermemory Local at `http://localhost:6767`.

Invitation log:

| date | event |
|---|---|
| 2026-09-03 | adapter prepared; vendor review not yet requested |
| 2026-09-05 | official additive run `supermemory-003` completed and passed the repository verification and submission checks |

Measurement update:

The run contains 730 sessions, 361 admitted cells, and 4 discarded cells. It joins 313 cells to
the frozen `official-003` base run. Supermemory's task success is 20.77%, with a delta of -37.06
percentage points against the joined `claude_md` baseline and a cluster bootstrap interval of
-34.65 to -11.49 points. The full comparison with RE-call is in
`reports/supermemory-003-vs-recall.md`.

The leaderboard keeps the arm anonymous as `product_a` until the vendor review window has been
opened and the disclosure decision is made.

Vendor response: none received.
