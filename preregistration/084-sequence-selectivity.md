# sequence-selectivity-001: linked outcomes without false memory accumulation

Status: **COMMITTED before measurement**. No measurement has been run under this record.

## Scope

This record extends [`006-longitudinal-suite.md`](006-longitudinal-suite.md). The existing chain
lengths, fresh sandbox rule, arm neutrality rule, and whole chain admission rule remain in force.
The purpose of this extension is to score not only whether a memory layer rescues a target task,
but whether it writes and retrieves selectively across the entire chain.

## Primary outcomes

The primary outcome is target success among admitted chains, reported by arm and chain length.
`all_sessions_success_rate` is secondary and reports whether every session in a chain succeeded.
The two must not be combined: a target can succeed after an intermediate session fails.

The paired harm measure is descriptive, not causal. For a memory arm, its denominator is matched
admitted chains whose baseline target succeeds. Its numerator is the subset where the memory arm's
target fails. A stronger event level measure is also reported when the oracle labels a retrieval
as harmful.

## Selectivity outcomes

Every memory decision is represented as an event in `metadata.memory_events`:

* a write event has decision `write` or `skip`;
* a retrieval event has decision `retrieve` or `abstain`;
* `useful`, `harmful`, and `applied` are optional oracle labels, and missing labels remain unknown.

The producer is conservative. Each adapter declares exact fully qualified memory tools and their
event kind. An observed call produces the positive action for that kind, unless its structured
result explicitly says `skip` or `abstain`. An undeclared tool produces no event, and the absence
of a call never produces an abstention event. Therefore an arm with no event producer is
unobserved for selectivity, not automatically selective.

Write precision is useful labelled writes divided by all labelled writes. Retrieval precision is
useful labelled retrievals divided by all labelled retrievals. Write skip rate and retrieval
abstention rate measure the decision to remain quiet. Useful abstentions and harmful retrievals
are reported separately so abstention is not treated as automatically good.

## Overhead

Each sequence record may carry `memory_input_tokens`, `memory_output_tokens`, and
`memory_storage_bytes` in metadata. The scorer also sums the canonical session input and output
tokens. Missing measurements remain unknown. For memory arms, total token delta is calculated
against the matched baseline chain when both chains are metered.

## Held out evaluation gate

Before any vendor run, a held out manifest must be created with
`python -m scripts.freeze_evaluation`. The manifest hashes every corpus and protocol file, records
the creation time and a manifest digest, and is verified immediately before execution. The vendor
may use a separate development corpus for integration work, but the held out manifest, labels,
checkers, and run outcomes must not be used for tuning.

A sequence plan must carry both the held out manifest ID and its SHA256 digest. The sequential
executor refuses to invoke the runner until the supplied manifest verifies and matches both plan
fields.

The manifest is a separate artifact from `corpus/manifest.json`. It must not mutate the published
read benchmark or silently enlarge an existing run.

## Analysis artifact

The implementation writes `sequence_analysis.json` and `sequence_analysis.md` through:

    python -m scripts.score_sequence records.final.jsonl --out-dir analysis

The scorer refuses records without sequence metadata, duplicate chain positions, inconsistent
chain lengths, missing targets, and a missing baseline arm. It never scores a partial chain as an
admitted chain.
