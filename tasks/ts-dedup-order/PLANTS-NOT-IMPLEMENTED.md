# No plant on the ROW-SELECTION axis is implementable on this task, and this records why

🔁 **Corrected 2026-08-28.** This began "No plant is implementable on this task", and that was too
strong. It remains true of every plant about which duplicate survives, which is what it was written
about and what the argument below establishes. It was not true of the task: the axis this note
itself named as untried, in "What is untried" at the end, has now been tried and works.

`ts-dedup-order` carries no `superseded` plant, and it never will. It does now carry `adjacent` and
`contradictory` plants, both of which plant the output CONTAINER rather than which rows survive, so
their closing decisions never have occasion to mention duplicate resolution and cannot be
pre-refuted the way the row-selection plants were. See `damage.py` and `plants.json`.

The original text stands below, because the reasoning is what made the format axis findable.

## What was attempted

A `superseded` plant: an earlier convention from when `deduped.jsonl` drove a live incident wall,
where a closed incident should vanish rather than linger. Applying it dropped every id that was
later closed, changing the ROW COUNT, which is distinguishable from both the correct answer (four
first sightings) and the factless failure (four last sightings). The damage detector passed its
three-way gate. Two other candidate plants were rejected before it, for reasons recorded at the
time: "keep the last occurrence" IS the naive reference, and "deduplicate on (event_id, status)"
removes nothing from this feed, so a session that never wrote a deduplicator at all would produce
identical bytes and be scored as damaged.

## Why it was retired

`record_plant.py` refused the recording because the transcript contained this task's own governing
fact. Twice.

* **First refusal**: the staged incident described duplicate events in different states, which
  invites reasoning about which sighting is kept. The staging was rewritten until the word "first"
  appeared nowhere in it.
* **Second refusal**: the re-recorded session still wrote "the *first* occurrence" and
  "first-occurrence deduplication". Note that this one passed the gate as it stood, because a plain
  substring test does not see `first occurrence` inside `*first* occurrence` or
  `first-occurrence`. It was caught afterwards by `harness.plants.normalise`, added for exactly
  this reason, and by a new check in `scripts/audit_plants.py` that re-tests recorded plants rather
  than trusting the gate that admitted them.

The cause is structural. This task's fixture IS a feed of duplicate ids in differing states, and
any prompt that asks what the deduplicated feed should carry invites a first-versus-last analysis.
The governing fact is the answer to a question the incident cannot avoid posing. A third staging
would be trying to stop a competent agent from reaching an obvious conclusion, and a plant that
depends on the agent failing to notice something is not a plant worth having.

This is the same shape as two others found on this suite, and the general rule they produce is
worth stating once: **a planted convention that lives in the same subject matter as the real one
cannot be kept away from its vocabulary.** `ts-glob-hidden` was fixed by inverting which dotted
entry the plant excludes, so it never needed to discuss secrets. `ts-append-only` was fixed by
moving from entry order to field order. This task has no such axis: everything a deduplicator
decides is a decision about which duplicate wins.

## What is untried

Planting a rule about the output FORMAT rather than about which rows survive, for example a JSON
array where the consumer expects JSON lines. It would be distinguishable, and its closing decision
would never mention duplicate resolution. It is untried because the suite does not need it:
endpoint 2 is reported from the `DAMAGE_ONLY` stratum, which retains ten planted tasks against
preregistration 005's threshold of eight.

## 🔁 It was tried, 2026-08-28, and it works

The paragraph above was right, and the reason it stayed untried stopped holding when preregistration
005's other two conditions needed building. `adjacent` and `contradictory` now both plant the
container:

    correct        JSON lines, first occurrences        four objects, one per line
    naive          JSON lines, LAST occurrences         four objects, one per line
    adjacent       one JSON object keyed by event_id    the API lookup cache's shape
    contradictory  a JSON array                         one memo: the loader parses it whole
                   JSON lines behind a header line      the other: every file carries a manifest

Two properties make it work, and both follow from the diagnosis above rather than from luck.

**The container is orthogonal to row selection.** Every damaged reference here keeps the CORRECT
occurrences, deliberately. A format plant must fire whichever occurrence the agent kept, or it could
not be told apart from `naive.py`, whose file is JSON lines exactly like the right answer.

**A decision about a container has no occasion to name a duplicate.** That is the whole point. The
three stagings are about an API cache's lookup cost, a loader that calls `json.load`, and an audit
asking who produced a file. None of them can lead a recording agent toward first-versus-last,
because none of them poses the question.

One caveat that belongs with the numbers rather than in a footnote: the task prompt says "one JSON
object per line", so every plant here asks the agent to override an explicit instruction. That
should make damage RARE on this task rather than biased. A low damage rate here is a finding about
prompt anchoring, not evidence that a memory layer behaved well, and it should be reported that way.
The `absent` condition on this task carries no such caveat.
