# OpenRouter NextBit provider smoke test

Status: DRAFT until committed; the prediction below is frozen before live calls.

## Question

Can the NextBit endpoint for `deepseek/deepseek-v4-flash` provide a valid streamed response and
complete one Claude Code text request plus one Claude Code tool request on VPS2 through the AMB
Anthropic gateway?

## Frozen setup

The test runs on VPS2 in `/home/sentiment/amb-claude-mem-official-001` with the pinned OpenRouter
credential from `/home/sentiment/amb-secrets.env`. The gateway uses the exact model
`deepseek/deepseek-v4-flash`, provider order `nextbit`, and `allow_fallbacks=false`. The gateway
listens on loopback and does not retry requests. Claude Code uses the existing pinned runtime and
the gateway as `ANTHROPIC_BASE_URL`.

The sequence is one direct Anthropic Messages stream, one Claude Code text request, and one Claude
Code Bash tool request. The run stops on the first hard failure to avoid unnecessary API spend.

## Predictions

1. The direct stream returns HTTP 200, a nonempty response, and a terminal stream event.
2. The Claude Code text request returns a nonempty terminal result.
3. The Claude Code tool request executes the requested tool and returns a nonempty terminal result.
4. The gateway records the expected model and provider policy with no fallback or retry.

## Failure and publication rules

Any HTTP error, provider mismatch, empty completion, missing terminal event, missing tool action,
fallback, retry, or model mismatch is a smoke failure. This is a compatibility screen only. It is
not a leaderboard result and cannot authorize an official AMB run by itself.

<!-- results are appended below this line; everything above is frozen -->

