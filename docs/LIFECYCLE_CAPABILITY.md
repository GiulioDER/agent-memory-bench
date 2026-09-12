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

## RE-call production boundary

`RecallAdapter` uses the production MCP `recall_ingest` surface for this optional capability. It
requires the returned generation to be reported as activated and refuses a build that is merely
validated or acknowledged but not live. This matters for a fresh tenant, where certification can
reject a generation even though the upload itself completed.

On the current hosted API, the unchanged `p01` repeat uses the same idempotency key and is therefore
recorded as `deduplicated`. That demonstrates replay idempotence only. It does not claim that the
source was newly indexed, so it cannot qualify `stale_candidate_resolution`. The adapter records
the AMB logical source identity in the receipt; the server's current upload staging path is
request scoped, so the receipt must not pretend that a logical filename is a stable server source
identity. A future API with a stable source or job key can opt into the actual newly indexed replay
branch.

Verify an artifact with:

```text
python -m scripts.lifecycle_verify \
  --manifest capabilities/lifecycle-temporal.json \
  --artifact results/lifecycle-temporal.jsonl
```
