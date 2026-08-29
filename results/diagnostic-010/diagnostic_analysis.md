# Oracle and Prefetch Diagnostic

Diagnostic arms are reference tracks, not ranked products.

## Success rates

| Arm | Successes | N | Rate |
|---|---:|---:|---:|
| claude_md | 27 | 70 | 0.386 |
| recall | 40 | 70 | 0.571 |
| oracle_memory | 60 | 70 | 0.857 |
| recall_prefetch | 28 | 70 | 0.400 |

## Primary contrasts

| Contrast | Mean delta | Cluster interval |
|---|---:|---|
| oracle_headroom | 0.486 | [0.306, 0.667] |
| natural_memory_lift | 0.208 | [0.083, 0.347] |
| prefetch_memory_lift | 0.014 | [-0.083, 0.125] |
| access_gap | 0.278 | [0.139, 0.431] |
| prefetch_gap | -0.194 | [-0.347, -0.042] |

## Interpretation

Diagnostic arms are reference tracks and are not combined into a product ranking. Gaps are descriptive unless the preregistration states otherwise.

## Tasks with no measurable oracle headroom

* ts-append-only
* ts-bom-merge
* ts-config-layer
* ts-dedup-order
* ts-glob-hidden
* ts-ignore-gen
* ts-schema-additive
* ts-semver-pin
* ts-tz-utc

## Negative transfer

* ts-bom-merge
* ts-schema-additive
