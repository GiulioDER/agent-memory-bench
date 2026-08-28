# Incident review 2026-06-11, engineer's working notes

Worked through the nightly reports in the order the tool listed them.

- Started at run 1, clean.
- Next listed was run 10, which showed the queue already saturated. Spent
  twenty minutes looking for what could have saturated it that early.
- Then run 11 and run 12, both degraded.
- Only then did runs 2 through 9 appear, which is where the saturation
  actually began.

Presented a timeline in which the queue was full before anything filled
it. The reviewer caught it. Rewrote the timeline by hand afterwards from
the run numbers rather than the listing.
