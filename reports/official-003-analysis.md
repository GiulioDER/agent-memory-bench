# Official run analysis: official-003

Generated from 2,920 records across 317 admitted cells and five corpus conditions.

## Decision

Overall winner among visible arms: `placebo`.
Best visible memory product: `recall`.

1. placebo is the highest scoring visible arm at 67.2%; this is not evidence that a memory layer won.
1. recall is the highest scoring visible memory product at 65.9%.
1. The placebo exceeds the claude_md baseline by +9.5%, so the run does not isolate a memory benefit cleanly.
1. recall shows a positive point estimate, but its published 95% interval crosses zero.
1. recall costs 3.3 times the baseline per admitted cell, including retrieval context tokens.
1. A vendor review hold suppresses one product's metrics from the public analysis until the hold is released.

The intervals are within run intervals over the admitted cells. They do not include run to run variance. The write path is not measured, so this is a retrieval comparison over a bulk ingested corpus.

## Tradeoffs by arm

| arm | success | delta vs baseline | cost per admitted cell or task | mean session seconds | tokens per admitted cell | status |
|---|---:|---:|---:|---:|---:|---|
| `recall` | 65.9% | +8.2% | $0.0044 | 80.90 | 73,844 | published |
| `mempalace` | withheld | withheld | withheld | withheld | withheld | held for vendor review |
| `fs_grep` | 63.1% | +5.4% | $0.0031 | 71.77 | 51,930 | published |
| `placebo` | 67.2% | +9.5% | $0.0014 | 53.90 | 22,128 | published |
| `claude_md` | 57.7% | +0.0% | $0.0013 | 56.77 | 21,103 | published |
| `bare` | 65.9% | +8.2% | $0.0014 | 63.50 | 21,807 | published |
| `recall_prefetch` | 61.2% | +3.5% | $0.0017 | 51.24 | 28,063 | published |
| `protocol` | 61.2% | +3.5% | $0.0019 | 62.94 | 30,013 | published |

## Condition analysis

The condition delta is measured against `claude_md` within the same condition.

| arm | present | absent | superseded | contradictory | adjacent |
|---|---:|---:|---:|---:|---:|
| `recall` | +11.7% | +17.3% | +13.0% | -3.9% | +0.0% |
| `mempalace` | withheld | withheld | withheld | withheld | withheld |
| `fs_grep` | +9.9% | +13.5% | +2.2% | -5.9% | +1.8% |
| `placebo` | +2.7% | +21.1% | +15.2% | +3.9% | +12.3% |
| `claude_md` | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| `bare` | +3.6% | +19.2% | +6.5% | +7.8% | +8.8% |
| `recall_prefetch` | +1.8% | +15.4% | +6.5% | -9.8% | +5.3% |
| `protocol` | +5.4% | +9.6% | -8.7% | -2.0% | +8.8% |

## Strengths and weaknesses

1. `recall`: strongest gains `ts-atomic-write` (+60.0%), `ts-manifest-rel` (+50.0%), `ts-json-sorted` (+50.0%); largest losses `ts-bom-merge` (-20.0%), `ts-cli-exitcode` (-20.0%), `ts-semver-pin` (-20.0%).
1. `mempalace`: metrics withheld while the vendor review hold is active.
1. `fs_grep`: strongest gains `ts-crlf-export` (+100.0%), `ts-round-money` (+66.7%), `ts-manifest-rel` (+31.8%); largest losses `ts-cli-exitcode` (-40.0%), `ts-idempotent-run` (-20.0%), `ts-semver-pin` (-8.0%).
1. `placebo`: strongest gains `ts-legacy-hash` (+82.6%), `ts-manifest-rel` (+50.0%), `ts-golden-regen` (+35.0%); largest losses `ts-cli-exitcode` (-100.0%), `ts-idempotent-run` (-80.0%), `ts-natural-order` (-12.5%).
1. `claude_md`: strongest gains none; largest losses none.
1. `bare`: strongest gains `ts-legacy-hash` (+65.2%), `ts-manifest-rel` (+36.4%), `ts-mig-name` (+27.3%); largest losses `ts-cli-exitcode` (-80.0%), `ts-idempotent-run` (-80.0%), `ts-schema-additive` (-8.0%).
1. `recall_prefetch`: strongest gains `ts-golden-regen` (+70.0%), `ts-manifest-rel` (+54.5%), `ts-bom-merge` (+10.0%); largest losses `ts-cli-exitcode` (-60.0%), `ts-ignore-gen` (-20.0%), `ts-semver-pin` (-20.0%).
1. `protocol`: strongest gains `ts-atomic-write` (+60.0%), `ts-manifest-rel` (+27.3%), `ts-mig-name` (+27.3%); largest losses `ts-schema-additive` (-20.0%), `ts-bom-merge` (-10.0%), `ts-semver-pin` (-4.0%).

## Audit status

Audit status: **warn**. See the generated audit artifact for each check and its evidence.
