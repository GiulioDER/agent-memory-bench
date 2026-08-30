# fa-dedup-key: measured difficulty, and where this task belongs

Two `bare`-only screens, 3 seeds each, `deepseek/deepseek-v4-flash`, before this task was trusted
for anything. Total spend $0.0101.

| version | `bare` | what happened |
|---|---:|---|
| records carried a `supplier` field | **3/3 = 1.000** | dead |
| `supplier` removed, identity depends on the source file | **0/3 = 0.000** | benefit-only |

## The first version was dead, and for the reason this repository already knew

Every record carried a `supplier`, so all three sessions wrote a TUPLE key including it. Keying on
`order_id` alone was never the obvious choice, which means `reference/naive.py` was not what a
memory-free agent produces and the task graded nothing.

That is exactly the defect `docs/reviews/2026-08-30-instrument-review.md` names: the naive
reference tests the CHECKER, and only `bare` tests the task. The screen cost $0.0046 and caught it
before any plant, recording or grid time was spent on it.

## The second version is BENEFIT-only, not mid-band

Removing `supplier` leaves `order_id` as the only plausible key and puts the disambiguating
information outside the record entirely, in the filename. `bare` then solves none of it.

⚠️ **Three seeds cannot distinguish 0.00 from about 0.30.** The point estimate is 0.000 and the
honest reading is "low", not "zero". A wider screen would tighten it and has not been run.

At this difficulty the task cannot measure damage, because damage is defined as failing a cell
`bare` solved and `bare` solves none. It has the whole range available for **benefit**, which puts
it with `ts-nfc-count`, `ts-round-money`, `ts-quote-shell` and the others in section 7 of the
review, and makes it a `present`-condition task rather than a harm-suite one.

It declares no plants for that reason, not because none could be authored.

## What the exemplar proves regardless of its difficulty

The class works mechanically, and that was the question it was built to answer:

* the corpus records an OUTCOME and explicitly declines to choose the replacement key, so the
  memory supplies an exclusion rather than an answer;
* the checker grades PROPERTIES, so two different correct keys both pass, where every other
  checker in this suite compares against one expected artefact and admits exactly one solution;
* the trap is real: deduplicating on the whole record also fails, because a redelivered order
  differs in `received_at`, which pushes an agent towards the id rather than away from it.

`tests/test_failed_approach_admits_alternatives.py` asserts all three.
