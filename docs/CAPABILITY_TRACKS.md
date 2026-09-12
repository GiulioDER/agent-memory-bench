# Capability tracks

These tracks add coverage without changing the official AMB task grid or its headline score. They
are deliberately small, deterministic qualification checks for a memory adapter. The optional
source replay capability is documented separately in `docs/LIFECYCLE_CAPABILITY.md` because the
ordinary adapter contract does not promise incremental ingestion.

## Temporal selection

`capabilities/temporal.json` is derived from the existing `xs-evolve-lease` task. Its loader checks
the committed `synthesis.shape == "evolve"`, the three dated shards, the source paths in
`corpus/manifest.json`, and the expected latest shard at each reference time. This makes the track
reuse AMB's supersession and cross session synthesis machinery rather than inventing a second fact
format.

The three probes ask the same kind of question at three points in time. A result must return the
right dated source first, include the expected settled phrase in `answer_text`, and avoid citing a
revision that was still in the future at that reference time. The verifier uses exact source paths
and phrase matching. It does not use an LLM judge.

## Tenant isolation

`capabilities/isolation.json` contains four synthetic probes over two tenants. Each tenant has a
near duplicate of the other tenant's record, and each targeted probe includes a foreign canary
whose wording is intentionally attractive. A result must cite a document owned by the requested
tenant, include the expected phrase, and cite none of the foreign canaries.

The primary metrics are `own_tenant_recall`, `canary_leak_rate`, and `answer_term_rate`. Leakage is
reported alongside usefulness. A system that abstains or returns nothing cannot pass by avoiding
the canary and missing the tenant's own record.

## Standard subset

The standard subset is seven probes total: three temporal probes and four isolation probes. It is
intended for vendor self qualification and adapter development, not for ranking products. A
subset artifact is bound to a derived manifest digest, so a result from a different probe list is
rejected.

For a submitted JSONL artifact, the first line is a header:

```json
{"artifact_type":"amb-capability-results","schema_version":1,"track":"temporal","manifest_digest":"...","system":"vendor-name"}
```

Each following line contains one `probe_id`, an `answer_text`, and an ordered
`ranked_source_paths` list. The list must use the source identifiers in the manifest. The same
shape is used by both tracks.

Verify a full manifest:

```bash
python -m scripts.capability_verify \
  --manifest capabilities/temporal.json \
  --artifact results/temporal.jsonl
```

Verify the cheap qualification subset:

```bash
python -m scripts.capability_verify \
  --manifest capabilities/temporal.json \
  --standard-subset capabilities/standard-subset-temporal.json \
  --artifact results/temporal-standard.jsonl
```

The verifier returns exit code `0` only when every gate passes. It returns `1` for a valid but
failing result and `2` for malformed, incomplete, or digest-mismatched input.

These artifacts must remain separate from `results/<run_id>/` and from the official leaderboard.
They measure selected capabilities, not overall memory quality, and they must not be combined with
execution-graded task success into one score.
