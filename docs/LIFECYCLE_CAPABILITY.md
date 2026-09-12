# Optional lifecycle capability

The official AMB adapter contract ingests a complete corpus once. It does not promise incremental
semantics. This capability is an additional, optional source event contract for products that can
demonstrate replay behavior through their own official write path.

## Fixture

`capabilities/lifecycle-temporal.json` uses `xs-evolve-lease` in one namespace. It offers `p01`,
`p02`, and `p03` in authored order, waits for the adapter's completion and visibility boundaries,
then offers unchanged `p01` again. The three temporal probes run after the initial sequence and
again after the replay, each in a fresh session.

The expected answers remain 90, 45, and 20 seconds at the three reference dates. The replay event
must retain `p01`'s authored date and content hash. A current ingestion timestamp must not replace
that authored date.

## Optional adapter surface

An adapter opts in by implementing:

```python
def ingest_event(
    self, namespace: str, event: LifecycleEvent, content: bytes
) -> LifecycleIngestReport:
    ...
```

The receipt records source identity, exact content hash, event order, authored date, outcome,
completion boundary, visibility boundary, and whether a fresh index was created. A rebuild of the
whole namespace is not source level replay and is recorded as `rebuilt`.

An adapter without this method is unsupported for this capability. That is not a failed update and
does not change its official AMB result.

## Interpretation

The report separates two outcomes:

1. `replay_idempotence` proves that an unchanged repeat was deduplicated.
2. `stale_candidate_resolution` is applicable only when the unchanged source was actually indexed
   again. A deduplicated repeat does not prove that an old source remains old after a newly indexed
   replay.

The lifecycle artifact is not accepted as an official leaderboard result.

Verify an artifact with:

```text
python -m scripts.lifecycle_verify \
  --manifest capabilities/lifecycle-temporal.json \
  --artifact results/lifecycle-temporal.jsonl
```
