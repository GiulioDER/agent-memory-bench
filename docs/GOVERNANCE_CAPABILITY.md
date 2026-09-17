# Applicability and replacement governance capability

This is an additive capability track for the next layer of AMB. It does not change the official
task grid or produce a leaderboard score.

The track tests whether a memory system can keep four distinctions separate:

1. A finding can be well supported but outside the current scope.
2. Two findings can be plausible replacements and still be genuinely contradictory.
3. An explicit successor should replace an older finding for the current context.
4. An old finding can remain the right answer when the query is pinned to its historical context.

## Artifact contract

The system returns one JSONL row per probe after querying its own memory surface:

```json
{
  "probe_id": "governance-current-supersession",
  "decision": "apply",
  "candidate_finding_ids": ["finding-alpha-lease-v1", "finding-alpha-lease-v2"],
  "selected_finding_ids": ["finding-alpha-lease-v2"],
  "conflict_finding_ids": [],
  "answer_text": "Apply the 20 second interval."
}
```

The stable ids make candidate retrieval, selection, conflict handling, and later reuse observable
as separate events. A cited id is telemetry, not proof that the task was improved.

## Metrics

The verifier reports decision accuracy, replacement candidate recall, safe application rate,
conflict identification, evidence term coverage, candidate pool size, and the rate at which
nonreplacement findings entered a candidate pool. Only decision accuracy, candidate recall, safe
application, and evidence coverage are qualification gates.

Use:

```text
python -m scripts.governance_verify \
  --manifest capabilities/governance.json \
  --artifact results/governance.jsonl
```

The track intentionally does not collapse candidate pool breadth into a pass or fail decision.
An adjacent finding may be worth showing for human review, but it must not be silently applied.
