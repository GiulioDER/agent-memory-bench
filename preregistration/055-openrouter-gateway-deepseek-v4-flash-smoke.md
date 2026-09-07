# OpenRouter provider pinned gateway smoke test

This preregistration covers the first live smoke test of the Anthropic compatible gateway added to
the AMB harness. It is a transport reliability test, not a leaderboard result and not a test of
Claude-Mem quality.

## Frozen prediction

Using the exact benchmark model `deepseek/deepseek-v4-flash`, the gateway will accept an
Anthropic Messages request, send `provider.order` with the frozen provider list, set
`allow_fallbacks` to `false`, and return a nonempty valid Anthropic response through the local
gateway. A Claude Code request sent through the same gateway will produce a terminal result with a
nonempty user visible response or at least one tool call. The gateway will make no retry attempt.

The smoke is a hard pass only if the health check reports the expected model and provider policy,
the direct request returns HTTP 200 with a valid response, and the Claude Code request returns a
valid stream with no empty completion. Any provider routing error, transport error, silent
completion, model mismatch, or evidence that fallback remained enabled is a failure. No official
AMB run may start from this smoke alone.

## Frozen setup

The live smoke runs on VPS2 in `/home/sentiment/amb-claude-mem-official-001` using the pinned
OpenRouter credential from `/home/sentiment/amb-secrets.env`. The gateway listens only on
`127.0.0.1`, forwards to `https://openrouter.ai/api/v1/messages`, pins the provider order supplied
at launch, and keeps the benchmark model fixed at `deepseek/deepseek-v4-flash`. The first provider
candidate is `DeepInfra`, selected because the OpenRouter provider page lists it among the current
providers for this model. The first live request is a minimal direct Messages request. If it passes,
one minimal Claude Code request is sent with `ANTHROPIC_BASE_URL` pointed at the gateway.

## Evidence

The gateway log records status, provider field when present, and byte counts only. It never records
the API key or message body. The live result, request policy, exact source commit, and command are
appended below this frozen section after measurement. This file is not edited above this line.

## Measured result, appended 2026-09-07

The frozen DeepInfra attempt reached OpenRouter with fallbacks disabled but returned HTTP 429 from
DeepInfra, with `engine_overloaded` and no alternate provider selected. That provider attempt is a
failure and is not a publishable result.

The gateway then used the exact OpenRouter slug `digitalocean`, after the provider page and routing
documentation established that routing accepts slugs rather than display names. The gateway health
check reported model `deepseek/deepseek-v4-flash`, provider order `digitalocean`, and
`allow_fallbacks=false`. A direct nonstreaming Messages request returned HTTP 200, text
`gateway-ok`, and upstream provider `DigitalOcean`. A Claude Code request through the gateway also
returned a successful terminal result with the same text. A second Claude Code request executed a
Bash tool and returned `gateway-tool-ok`; the stream log recorded `terminal_event=true`.

The gateway therefore passes the transport and Claude Code compatibility smoke on DigitalOcean,
but the preregistered DeepInfra route does not pass availability. No official AMB run is authorized
by this smoke. The source commits for the implementation and fixes are `80ca9293`, `b280c828`,
`a1f7c610`, and `710e3808`. The live test ran on VPS2 in the isolated AMB worktree with the exact
model `deepseek/deepseek-v4-flash`; no gateway retry was implemented.
