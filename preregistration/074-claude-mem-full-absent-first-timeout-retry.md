# Claude Mem full AMB run, absent-first timeout retry

Status: DRAFT until committed and timestamped. This record freezes the retry before any new model
call.

## Question

Does the full guarded Claude Mem AMB run complete its large-corpus semantic preparation and then
produce valid live retrieval traces when restarted from the absent condition on VPS2?

## Frozen setup

The run executes only on VPS2 in `/home/sentiment/amb-claude-mem-official-001`, from the exact
source content and timestamp manifest recorded before launch. It uses Claude Mem v13.24.0, the
existing VPS2 condition corpora, the official frozen task selections, five seeds, four concurrent
cells, and condition order `absent`, `present`, `superseded`, `contradictory`, `adjacent`. The arm
is `claude_mem` and the model is exactly `deepseek/deepseek-v4-flash`.

The local gateway uses `http://127.0.0.1:8794`, provider order `nextbit`,
`allow_fallbacks=false`, and no gateway retry. The synchronous Claude Mem first-search guard is
enabled. The only setup change from preregistration 073 is the frozen Claude Mem Chroma semantic
readiness timeout, raised from 1,800 seconds to 7,200 seconds after the absent retry imported all
4,888 observations but exceeded the previous deadline while Chroma was still actively embedding.

The run may reuse the prepared VPS2 input corpus, but each measured cell remains isolated and may
not read observations or results from another cell. A cell is admitted only after Claude Mem
preflight, ingestion, Chroma readiness, and cleanup checks pass. Every admitted cell must record a
successful exact `mcp__mcp-search__search` call with more than zero parsed hits, normal tool use
after search, and zero hook failures.

## Prediction

The raised timeout will allow the absent corpus semantic backfill to become ready. The gateway will
route only through NextBit with fallbacks disabled. The first admitted absent cell will record
positive Claude Mem retrieval telemetry and then normal tool use. Later conditions will run only if
the preceding condition passes setup and cleanup gates.

## Stop and publication rules

Stop before further model calls if gateway routing is not pinned, preflight or ingestion fails,
Chroma readiness fails even under the raised timeout, search is not attempted, parsed hits are zero,
normal tools do not become available after search, a hook fails, or cleanup leaves a worker or
gateway alive. Any run stopped by one of these gates is not publishable as a clean Claude Mem
leaderboard result. Guard-enabled results remain explicitly labelled as guarded and must not be
pooled with unconstrained arms without a protocol decision.

<!-- results are appended below this line; everything above is frozen -->
