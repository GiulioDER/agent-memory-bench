# Preregistration 037: capability tracks

## Scope

This preregistration defines two additive capability tracks and a cheap standard subset. It does
not amend the official AMB grid, its task selection, its arm roster, or its execution-graded
headline endpoint.

## Temporal track

The temporal track uses `xs-evolve-lease`, which is already declared in AMB as an `evolve`
synthesis task with three dated revisions. `capabilities/temporal.json` names the reference times,
the expected source path, the dated candidate set, and the expected phrase. Manifest loading fails
if the task's synthesis declaration, source corpus, or supersession order no longer agrees.

The primary gates are temporal hit at one equal to one, expected phrase rate equal to one, and
future source ambiguity equal to zero. The track is a capability report, not a leaderboard result.

## Tenant isolation track

The isolation track uses the synthetic documents in `capabilities/isolation.json`. It has two
tenants, near duplicate records, and targeted foreign canaries. The primary gates are own tenant
recall equal to one, expected phrase rate equal to one, and canary leak rate equal to zero.

## Standard subset

The standard subset contains three temporal probes and four isolation probes. It is intended to
make a first adapter check cheap and reproducible. Subset artifacts are bound to a derived digest
and cannot be substituted for a full manifest artifact without changing the verification input.

## Reporting rule

Capability metrics are reported separately from AMB task success, abstention, cost, and harm
conditions. No combined score or product rank will be published from these tracks without a future
preregistration that names the systems, sample, and endpoint in advance.

## Reproduction

```bash
python -m pytest tests/test_capability_tracks.py -q
python -m scripts.capability_verify --help
```
