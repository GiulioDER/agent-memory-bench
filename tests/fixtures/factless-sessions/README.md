# Recorded factless sessions: what an agent produces with no memory

Finished sandboxes from `abstention-001`, one directory per session, taken from every `bare` and
`claude_md` cell of both conditions. `.git` is stripped; everything else is exactly as the agent
left it.

They exist because of a specific failure. `tests/test_damage_detection.py` asked each damage
detector to stay silent on `naive.py`, ONE committed factless solution written by whoever wrote
the detector. `ts-manifest-rel` passed that gate and then fired on a `claude_md` session with
`memory_call_count = 0`, in a run where its plant was not even in the corpus. Keying a manifest of
files under `release/` relative to `release/` is a perfectly natural answer that `naive.py`, which
uses absolute paths, does not represent.

A real agent produces a **distribution** of factless solutions. A plant is measurable only if its
signature lies outside all of them, and an authored `naive.py` cannot establish that. These are
real samples from that distribution.

`ts-manifest-rel`'s sandboxes are kept even though its plant is retired, so that re-adding a plant
on that axis fails immediately rather than after another run.

## Regenerating

Sandboxes live outside the repo (`harness.sandbox.default_work_root`) and survive a run. From the
work root:

    tar cf - --exclude=.git -C <run>/work/<task>/<seed>/<arm> .

Any run works. More sessions is strictly better: this gate's power is the breadth of factless
behaviour it has seen.
