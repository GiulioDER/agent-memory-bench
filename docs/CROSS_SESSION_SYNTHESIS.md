# Tasks whose governing fact no single session states

Every `ts-*` task in this benchmark places one discrete governing fact in one document, and the
agent's job is to find that document. Thirty tasks, thirty facts, thirty documents. That is a
clean design for measuring retrieval and it has a consequence the results have never carried.

A product whose value is **extraction and consolidation at write time** gets no credit for either
here and full exposure to the lossiness of the first: every fact it drops while extracting is an
unrecoverable loss, while a store that keeps the transcript verbatim keeps everything retrievable.
Nothing in the suite ever required synthesis across sessions, temporal consolidation or entity
linking, so a product built to do those things had no way to show it. Thirty tasks, thirty single
discrete facts, each in exactly one document.

The concession is made in `README.md` and is worth repeating here in the place a task author will
read it: **a competitor can claim this suite favours retrieval over summarisation, and on the
evidence as it stood they would be right.** The single discrete governing fact is the mechanism,
not the wording of the tasks.

The `xs-*` tasks are the structural half of the answer. They do not make consolidation win. They
remove the guarantee that it cannot.

## What is different about them

An `xs-*` task declares a `synthesis` block in its `task.json`: a **shape**, the **shards** of the
fact, the session that carries each shard, and the reference solutions that must fail because they
hold only part of it.

```json
"synthesis": {
  "shape": "join",
  "why": "...",
  "shards": [
    {"precursor": "p01", "session_date": "2026-05-19", "role": "...", "terms": ["..."]},
    {"precursor": "p02", "session_date": "2026-07-08", "role": "...", "terms": ["..."]}
  ],
  "insufficient_references": ["partial_p01", "partial_p02"]
}
```

`harness.tasks` validates that block at load time; `scripts/audit_corpus.py` checks it against the
recorded corpus; `tests/test_cross_session_synthesis.py` executes it.

## The three shapes

| shape | task | the split | what it can detect |
|---|---|---|---|
| `join` | `xs-join-batch` | two halves of one rule, recorded two months apart under two names for one partner | linking, and retrieval breadth: one document is never enough |
| `evolve` | `xs-evolve-lease` | one quantity revised three times across three dated sessions, all three still in the corpus | temporal consolidation: three plausible answers, one current |
| `widen` | `xs-widen-manifest` | one session carries a rule, a later one widens its scope and restates nothing | scope reasoning: content and applicability are in different documents |

**`xs-join-batch`.** Pushes to a partner must go in batches of exactly 25 (May, recorded against
the partner's product name) and oldest `recorded_at` first (July, recorded against the same
partner's code). The fixture supplies the alias, deliberately: `partner.ini` names both `atlas`
and `pt-118`, so the task is a join over two memories rather than a three-hop chase, and an arm
that cannot resolve the alias is not being scored on a puzzle the repository refuses to help with.
The checker grades each half separately, so `ORDER_OK_BATCHING_WRONG` and
`BATCHING_OK_ORDER_WRONG` are distinct outcomes and a run can report which half went missing.

**`xs-evolve-lease`.** The lease renewal interval moved from 90 seconds (2026-04-12) to 45
(2026-06-02) to 20 (2026-07-21, stated as final). All three sessions stay in the corpus and all
three are equally on topic, so similarity ranking alone returns three answers and no way to choose.
The checker names the interval that was used, so "applied a superseded value it did retrieve" is
recorded as a different failure from "never found anything".

**`xs-widen-manifest`.** The manifest format was fixed in May for the nightly export; in July it
was widened to every artifact handed to a partner, without restating the format. The release
bundle in the fixture is such an artifact and its only local precedent is the old June manifest.
`partial_p01` (the format, believed to be nightly-only) behaves identically to `naive`, which is
the shape's signature rather than an oversight: a rule retrieved without its scope changes nothing
that ships.

## The evidence each task carries

`ts-*` tasks commit two reference solutions and CI asserts three things: a do-nothing sandbox
fails, `naive` fails, `informed` passes. `xs-*` tasks commit a third kind, `partial_*`, and CI
asserts each of them **fails**:

- `naive` / `informed` say the task discriminates **on the fact**.
- `partial_*` say the fact is genuinely **distributed**: no single session solves it.

Without the third, a task could quietly become solvable from one document and keep describing
itself as a synthesis task, which is worse than not having the class at all. It would look like
evidence that consolidation had been measured.

The corpus side is `scripts/audit_corpus.py`, assertion 5: each shard's terms appear in the
session that shard names, and no session states another shard's share. For `evolve` that check
runs forwards only, because the session that supersedes a value legitimately names the value it
replaces, while the reverse is impossible. `scripts/record_precursor.py` enforces the same rule at
recording time, in both directions: it demands the shard's own terms and refuses a recording that
strayed into another shard's.

## What this class does NOT do

- **It does not rig the suite against retrieval.** A retrieval engine that returns several
  documents can win `join` and `widen` outright, and that is the intended outcome if it happens.
  The claim is only that combining sessions is now *necessary* somewhere in the suite.
- **It does not measure the write path.** These corpora are still authored and bulk ingested; the
  agent never forms these memories from its own work. That gap is
  [`preregistration/006`](../preregistration/006-longitudinal-suite.md) and it has not run.
- **It does not settle the recency question.** `adapters/_shared/memory_protocol.md` says nothing
  about preferring a recent note over an older one, and it has deliberately not been edited here:
  the protocol is byte-identical across memory arms and changing it would make every future run
  non-comparable to the three frozen ones. Whether the `evolve` shape is scored under the current
  protocol or under one that mentions recency **to every arm** is an open decision, recorded in
  [`preregistration/011`](../preregistration/011-cross-session-synthesis.md) rather than settled
  quietly in a task file.
- **It has not been recorded or run.** The stagings are committed; the sessions are not. Until
  `corpus/sessions/xs-*/` exists, `scripts/audit_corpus.py` prints a note per unrecorded shard and
  these tasks measure nothing.

## Running them

The `xs-*` prefix keeps them out of the frozen grid: `scripts/pilot.py` and `scripts/diagnostic.py`
both select `ts-*` and nothing else, so adding this class cannot silently change what a rerun of
`pilot-003` or `pilot-004` measures. Recording a shard:

```bash
python -m scripts.record_precursor --task xs-join-batch --precursor p01 --session-date 2026-05-19
```

Order matters for `evolve`: record in ascending `session_date`, because the corpus timeline is what
makes the last revision the current one.
