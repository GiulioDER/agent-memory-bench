Why this comes first: project memory can contain prior decisions, rejected approaches, hazards,
successors and conflicts that are not derivable from the current checkout. The required one-hop
graph query is also the discovery mechanism for relevant facts or hazards you cannot name in
advance.

After the required graph call, pass every action-changing memory result through this gate:

1. Classify it as supported, abstained, stale or superseded, conflicting, or merely related.
2. Match it to the same operation, artifact or subsystem, and time horizon as the current task. A
   graph neighbour is not governing evidence by itself.
3. Use a follow-up reader only when it resolves a decision: recall_evidence for a supported claim
   that will change the action; recall_current_facts or recall_current_state for what is true now;
   recall_related or one reasoning follow-up for a successor, dependency or conflict.
4. Verify every action-changing claim against current code, configuration, tests or live state.
   Current sources win. If memory abstains, is superseded, or remains in conflict, do not apply it.

Stop after at most two materially different follow-ups. Do not use indexing, ingestion,
calibration, mutation or erasure tools during the task.
