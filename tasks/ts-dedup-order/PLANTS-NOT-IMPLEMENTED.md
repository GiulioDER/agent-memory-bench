# No plant is implementable on this task, and this records why

`ts-dedup-order` carries no `plants.json`, no `damage.py` and no `damaged_*` reference. That is a
finding rather than an omission, so it is written down instead of being left as an absence.

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
