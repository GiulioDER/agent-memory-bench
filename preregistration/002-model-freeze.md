# pilot-003: freeze the model for the multi-product benchmark

Status: FROZEN above the results marker once committed.

## Question

Pilot 002 showed that the shipped check-memory-before-acting skill repaired the
discoverability failure on `deepseek/deepseek-v4-flash`. The next uncertainty is model
choice. This run selects the model for the production comparison before any competitor
result is collected.

## Candidate models

The candidates are fixed from the OpenRouter models endpoint read on 2026-08-24.

1. `deepseek/deepseek-v4-flash`, input price `0.0574` USD per million tokens and
   output price `0.1148` USD per million tokens. This is the pilot 002 control.
2. `openai/gpt-5.3-codex`, input price `1.75` USD per million tokens and output price
   `14.00` USD per million tokens. The one cell compatibility smoke passed for both
   `claude_md` and `recall` before this preregistration.

The model ID, endpoint, prices, CLI version, corpus manifest, task files, and recall
instruction remain fixed during both runs.

## Grid

Each candidate runs 3 arms (`bare`, `claude_md`, `recall`), 24 tasks, and 3 seeds:
`3 x 24 x 3 = 216` sessions per model and 432 sessions overall. The recall arm uses
the shipped skill from pilot 002. The `claude_md` arm receives the same static bundle
without the skill. The `bare` arm receives neither. The runner uses Claude Code 2.1.238,
600 second session timeouts, one cell at a time, and the same executable checker.

Run IDs are `pilot-003-deepseek` and `pilot-003-gpt53`.

## Endpoints

1. Eligibility: paired cell admission, search rate, reached-given-searched, and reached
   overall for the recall arm.
2. Capability: per arm task success, per-task rates, and the same ceiling and floor
   screening rules used by pilot 001.
3. Memory effect: recall versus `claude_md`, per-task cluster bootstrap interval and
   cell McNemar test. This is descriptive model selection evidence, not the final
   competitor claim.
4. Cost and latency: input tokens, output tokens, estimated USD, wall time, and
   discarded cells.

## Eligibility and selection rule

A model is eligible only when at least 95 percent of its cells admit as complete paired
cells, recall search rate is at least `0.50`, and reached-given-searched is at least
`0.50`. If neither model is eligible, the competitor run does not start. The failure
is reported as an infrastructure or model integration result and the protocol is
revised in a new preregistration.

Among eligible models, select the model with the higher `claude_md` success rate. This
chooses the more useful production capability level without selecting on the observed
memory delta. If the success rates differ by less than `0.05`, select the model with
the lower estimated USD per admitted `claude_md` success. The selected model is then
frozen for the full multi-product comparison.

## Predictions

1. `deepseek/deepseek-v4-flash` search rate: `0.80`, reached-given-searched: `0.88`,
   reached overall: `0.70`, `claude_md` success: `0.40`, recall success: `0.64`.
2. `openai/gpt-5.3-codex` search rate: `0.70`, reached-given-searched: `0.80`, reached
   overall: `0.56`, `claude_md` success: `0.55`, recall success: `0.68`.
3. The stronger model will have the higher `claude_md` success rate and will therefore
   be selected, even if its recall delta is smaller.
4. Each model will discard fewer than 15 of its 216 sessions after the fresh database
   migration and startup preflight.
5. Total spend will be about `$15`, with a hard cap of `$40`. If the cap is reached,
   truncate seeds in reverse order and never truncate tasks.
6. Total wall time will be between 3 and 7 hours.

## Operational controls

The model runs use a fresh disposable PostgreSQL database whose migration ledger is
verified before launch. The recall tenant is indexed from the committed corpus manifest
using the adapter write path. A startup check must report the current migration checksum,
721 corpus chunks, and a connected recall MCP server before the first model session.

<!-- results are appended below this line; everything above is frozen -->
