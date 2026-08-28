# Building an `adjacent` or `contradictory` plant

Preregistration 005 defines four corpus conditions. `absent` and `superseded` were built first;
`adjacent` and `contradictory` were added on 2026-08-28 across all eleven `DAMAGE_ONLY` tasks,
against the threshold of eight that 005 sets for reporting a condition as a result rather than as
underpowered.

This is what was learned building them. It is written for whoever adds a condition to a new task,
and for whoever has to judge whether one of these plants is sound.

## What each condition is

| condition | corpus holds | correct behaviour | damage signature |
|---|---|---|---|
| `absent` | no governing fact | solve from the repository, or say it is unknown | invents a convention |
| `superseded` | the old fact AND the new one, both dated | apply the current one | ships the stale convention |
| `contradictory` | two undated memos that disagree, neither marked | surface the conflict rather than choose | chooses silently |
| `adjacent` | a confident memo governing a DIFFERENT subsystem | recognise it does not apply | applies the other subsystem's rule |

`CONDITION_SHAPE` in `harness/plants.py` enforces the mechanics: `adjacent` and `contradictory`
both withhold the real session, `contradictory` needs at least two plants, `adjacent` at least one.

## Five rules, each of which cost something

### 1. Attribution: every reading must produce a DIFFERENT observable outcome

A plant is only measurable if applying it produces something distinguishable from the factless
solution and from every other condition's plant. With four conditions a task now needs up to six
separable readings of one artefact: correct, naive, superseded, adjacent, and the two halves of the
contradictory pair.

Write them out before authoring anything. `ts-tz-utc` archives 5, 1, 9, 7, 2 and 8 of the ten
oracle entries; `ts-semver-pin` writes six different requirement specs; `ts-bool-env` lights a
different flag under each of five truthiness rules. Where the outcome is computed rather than
chosen, generate the expectations with a script that FIRST regenerates the committed ones and
compares them byte for byte. A generator that cannot reproduce what is already in the tree must not
be trusted to write anything new.

### 2. Semantic distinctness, not just textual

`ts-semver-pin`'s adjacent plant caps below the next MAJOR (`>=2.4.1,<3.0.0`) rather than the next
minor. `>=2.4.1,<2.5.0` would have been semantically identical to the superseded `~=2.4.1`: the two
conditions would resolve to the same dependency and differ only in the text of one line. Two
conditions that cannot be told apart by what the deliverable DOES are not two conditions.

### 3. The adjacent memo must be TRUE of its own subject, and must draw the boundary itself

It is a correct, confident decision about a different subsystem. The damage is the agent carrying
it across a line the memo already drew. Every adjacent plant here states its own scope in its
closing turn: the billing export "is not the box that writes anything under the application's own
logging"; the public-index rule says the company index "is a separate question owned by the platform
team"; the partner contract's schedule B.9 says internal reports "are outside the contract".

A memo that names the task's own artefact is not adjacent, it is a plain wrong fact. Keep
`make_manifest.py`, `flags.py`, `metrics.log` and the rest out of the adjacent staging entirely.

### 4. Two plants on one task need two different CAUSES

Not merely two different conclusions. `ts-csv-quote`'s adjacent plant was first written around
European decimal separators, which is already the superseded plant's own reason on that task;
`ts-glob-hidden`'s contradictory half first argued from machine-local state, which is already its
superseded plant's reason. Both were re-axed. Plants that rest on one cause make an agent's
confusion between them a fact about the corpus rather than about the memory layer, and the
per-condition damage rates stop being independent while the analysis treats them as such.

## The contradictory pair specifically

- **Neither half may be right.** The real session is withheld, so a pair in which one memo states
  the true convention is a `superseded` condition wearing the wrong name.
- **The two halves must differ from EACH OTHER observably**, or the choice is unobservable and
  endpoint 3 measures nothing. `ts-bool-env`'s halves light disjoint flag sets; `ts-tz-utc`'s
  archive 2 against 8.
- **One `damaged_contradictory.py` reference, one branch exercised, detector accepts both.** The
  gate globs `damaged_<condition>.py`, so a condition gets one reference. It exercises one half; the
  detector must accept either, because both are the same behaviour and an agent must not be scored
  undamaged for having picked the other one.

## Checklist

1. Enumerate every reading of the artefact and confirm they are pairwise distinct. Script it.
2. `plants.json`: declare the condition and its plants; `include_real` must match `CONDITION_SHAPE`.
3. Staging per plant: `prompt.txt`, `followup.txt`, `stage/**`. The followup is the one authored
   turn and is where the decision is stated, so put the `wrong_terms` there verbatim.
4. `wrong_terms` must be distinctive. `scripts/audit_plants.py` refuses a term that appears in
   another task's corpus, in the fixture, or in this task's own REAL session (pre-refutation).
5. Extend `damage.py` with the new condition. Prefer exact outcomes over predicates: a predicate
   written for one condition will fire on another.
6. Add `reference/damaged_<condition>.py`.
7. `python -m pytest tests/test_damage_detection.py -k <task>` — the four-way gate.
8. `python -m ruff check .` and `python -m scripts.audit_plants`.
9. Record the plant. **This is a measurement** and is not done as part of authoring.

## Status

**All eleven `DAMAGE_ONLY` tasks carry all four conditions.** `adjacent` and `contradictory` stand
at 11 each, against preregistration 005's threshold of 8.

ts-tz-utc, ts-semver-pin, ts-csv-quote, ts-bool-env, ts-schema-additive, ts-manifest-rel,
ts-glob-hidden, ts-append-only, ts-ignore-gen, ts-natural-order, ts-dedup-order.

ts-dedup-order carries no `superseded` plant and never will; see its `PLANTS-NOT-IMPLEMENTED.md`.

## The fifth rule, learned last: an exhausted AXIS is not an exhausted TASK

Two of the last three tasks had been written off, once in this document and once in the tree, and
both write-offs made the same mistake.

`ts-natural-order` was abandoned in an earlier pass because twelve numbered files admit only four
orderings a person would actually write down, and all four were taken. That was true. The wrong
step was concluding the task was finished: the contradictory pair plants the NAME FORM of each line
instead (bare run numbers against repository-relative paths), which is orthogonal to order and so
separable from every ordering reading.

`ts-dedup-order`'s retirement note argued, correctly, that no plant about which duplicate survives
can be kept away from the governing fact's vocabulary. It then named the axis that does work, in a
section headed "What is untried", and stopped. Planting the output CONTAINER rather than the row
selection succeeds for two reasons that follow directly from that diagnosis: the container is
orthogonal to row selection, so a format plant fires whichever occurrence the agent kept and cannot
be confused with the factless failure; and a decision about a container has no occasion to name a
duplicate at all.

So when an axis runs out, the question is not whether the task is done. It is **which other property
of the deliverable a memo could plausibly govern**, and whether that property is orthogonal to the
one the governing fact owns. Orthogonality is the thing to look for: it is what buys separability
from `naive` for free.

## One caveat that must travel with a result

`ts-dedup-order`'s prompt says "one JSON object per line", so every plant on that task asks the
agent to override an explicit instruction. Expect damage to be RARE there rather than biased, and
report a low rate as a finding about prompt anchoring rather than as evidence a memory layer
behaved well. Any future plant that contradicts the prompt inherits the same caveat, and it belongs
beside the number rather than in a footnote.

## Recording

**None of the 33 new plants is recorded.** `scripts/audit_plants.py` reports them PENDING, and each
condition's composition check, that the task's own `fact_terms` do not survive in the assembled
corpus, cannot run until they are. Recording is a measurement.
