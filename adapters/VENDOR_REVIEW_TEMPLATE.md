# Vendor review: <product> (<arm name>)

Copied into `adapters/<name>/VENDOR_REVIEW.md` when the adapter lands (Phase 3), filled in
during the pre-review window (Phase 4), and frozen into the full-run preregistration. Every
section below is published verbatim, including silence.

## What we are asking you to review

Before any preregistered run, we invite <vendor> to review, with a two-week window:

1. **Your adapter's frozen config** (`config.frozen.json`, sha256 pinned in the
   preregistration): the integration route (your official Claude Code plugin / MCP server),
   its settings, and the one-line tool instruction your arm's system prompt carries.
2. **The corpus format** (`corpus/README.md`): verbatim session transcripts with structured
   timestamps, ingested through your own write path, one namespace per (arm, seed).
3. **Version pins** (`versions.lock`): the exact package/API version the run will name.

Config changes you request before the freeze are applied and re-hashed. After the freeze,
disputes go next to the published per-session streams, not to a configuration argument.

## Two offers, both cost-neutral for the benchmark's integrity

- **Sponsored credits.** Your arm's API traffic (ingestion and retrieval) can run on keys or
  credits you provide. Execution stays on our harness, same host, same model, same admission
  gate as every arm; the run artifact records who funded which arm. If you decline, we fund
  it and say so.
- **A vendor-tuned variant.** If you believe a different configuration shows your product
  better, submit it: we run it as an additional, clearly-labelled arm variant inside the same
  harness. Best foot forward, without giving up the controlled comparison.

What we do not offer: vendor-executed cells in the canonical table. A number produced outside
the shared harness is not comparable and not verifiable, and this benchmark exists because
the field has enough of those.

## After publication

The one-command Docker reproduction and the full per-session artifacts are public. We invite
you to re-run your arm and publish what you find; confirmations and disputes are both
engagement with the method, and the frozen configs and streams are the referee.

## Record

| date | event |
|---|---|
| YYYY-MM-DD | invitation sent (link to public issue) |
| YYYY-MM-DD | first ping |
| YYYY-MM-DD | second ping |
| YYYY-MM-DD | response received / window closed with no response |

### Vendor response, verbatim

(unedited, or "none received by the deadline")
