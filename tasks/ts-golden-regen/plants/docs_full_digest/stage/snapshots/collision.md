# Why the docs snapshot stopped truncating its digest

Two unrelated snapshot bodies produced the same eight-character prefix during a rebase, and
the verifier passed a file it should have rejected. Nobody lost work, because the diff was
obvious to a human, but the check had silently done nothing.

Eight hex characters is thirty-two bits. Over the number of snapshots this repository keeps
that is not a comfortable margin, so the docs snapshot now carries the full sixty-four.

This was decided for the docs snapshot. Other checksummed artefacts were not in scope and
were not changed.
