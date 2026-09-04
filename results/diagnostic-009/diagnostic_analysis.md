# Oracle and Prefetch Diagnostic

Diagnostic arms are reference tracks, not ranked products.

## Success rates

| Arm | Successes | N | Rate |
|---|---:|---:|---:|
| claude_md | 30 | 72 | 0.417 |
| recall | 28 | 72 | 0.389 |
| oracle_memory | 66 | 72 | 0.917 |
| recall_prefetch | 30 | 72 | 0.417 |

## Primary contrasts

| Contrast | Mean delta | Cluster interval |
|---|---:|---|
| oracle_headroom | 0.500 | [0.319, 0.681] |
| natural_memory_lift | -0.028 | [-0.125, 0.069] |
| prefetch_memory_lift | 0.000 | [-0.056, 0.056] |
| access_gap | 0.528 | [0.347, 0.708] |
| prefetch_gap | 0.028 | [-0.083, 0.153] |

## Interpretation

Diagnostic arms are reference tracks and are not combined into a product ranking. Gaps are descriptive unless the preregistration states otherwise.

## Tasks with no measurable oracle headroom

* ts-append-only
* ts-bom-merge
* ts-config-layer
* ts-dedup-order
* ts-glob-hidden
* ts-ignore-gen
* ts-manifest-rel
* ts-semver-pin
* ts-tz-utc

## Negative transfer

* ts-atomic-write
* ts-dedup-order
* ts-golden-regen
* ts-mig-name
* ts-tz-utc
