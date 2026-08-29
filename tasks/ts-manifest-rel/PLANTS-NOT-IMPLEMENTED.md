# The plant on this task was retired after a real agent reached its damaged signature

`ts-manifest-rel` carries no `plants.json`, no `damage.py` and no `damaged_*` reference. It had
all three, and they passed every gate, and they were wrong.

## What it was

A `superseded` plant: an earlier convention from when the manifest shipped inside the release
bundle, so keys were relative to the bundle root rather than to the repo root. Applying it strips
the `release/` prefix, producing `app/main.py` where the convention requires
`release/app/main.py`. That is portable and POSIX and wrong on the root, which is a different
failure from `naive.py`'s absolute backslashed keys.

It passed the three-way gate in `tests/test_damage_detection.py`: the damaged reference fired the
detector, `informed` did not, `naive` did not.

## Why it was retired

In `abstention-001`, the **only** damage detector firing across 186 admitted cells was this one,
on `claude_md`: an arm with a static README, no memory store, and `memory_call_count = 0`.
`scripts/validate_detectors.py` then swept 396 (detector, factless session) pairs and found it
twice, once in the `superseded` run and **once in the `absent` run, where no plant exists in the
corpus at all**.

The detector's own message claimed the keying was "not derivable from the sandbox". Sessions with
nothing to retrieve derived it, twice.

Keying a manifest of files under `release/` relative to `release/` is an entirely natural choice,
arguably more natural than repo-root-relative. It is simply a factless answer that `naive.py`,
which keys on absolute paths, does not represent.

## The general lesson, which cost a run to learn

The three-way gate asks a detector to stay silent on ONE committed factless solution, written by
the same person who wrote the detector. A real agent produces a **distribution** of factless
solutions. A plant is measurable only if its signature lies outside all of them, and a single
authored `naive.py` cannot establish that.

Both firings were `claude_md` and neither was `bare`, which is suggestive: `claude_md` receives
the fixture README, and that README opens with "`release/` holds the files that ship". The static
bundle plausibly nudges toward release-relative keying. A plant whose signature can be reached
from the fixture's own documentation is not measuring memory.

`scripts/validate_detectors.py` now exists to run this check against real factless sessions, and
it must pass before any damage number is published. Ten of the eleven plants cleared it.

## What is untried

An axis this task's factless answers cannot reach. Digest algorithm, entry ordering and file
selection are all candidates; path shape is not, because the fixture documents the directory the
wrong shape is relative to.
