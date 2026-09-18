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

## Measured result, appended 2026-09-07

The first probe attempt was rejected locally with HTTP 400 because the SSH shell quoting produced
invalid JSON. The request did not reach OpenRouter and consumed no provider call. The corrected
probe then passed with HTTP 200, upstream provider `NextBit`, and a complete streamed response with
`terminal_event=true`.

The Claude Code text request passed on VPS2 with `stop_reason=end_turn`, exact result
`NEXTBIT_CLAUDE_TEXT_OK`, and no API error. The Claude Code tool request also passed with
`stop_reason=end_turn`, exact result `NEXTBIT_CLAUDE_TOOL_OK`, and a verified marker file containing
the same value. Both requests used the exact model `deepseek/deepseek-v4-flash` through the local
gateway with provider order `nextbit` and `allow_fallbacks=false`.

Claude Code still emitted its known `unrecognized_model` warning for the non-native DeepSeek model,
but the gateway, response model, provider, terminal results, and tool execution were correct. This
warning was not treated as a provider or model mismatch. The gateway was stopped after the test and
port 8794 was verified free. This is a compatibility smoke pass only and does not authorize an
official AMB run.
