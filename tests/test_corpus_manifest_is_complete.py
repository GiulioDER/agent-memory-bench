"""A recorded session that is not in the manifest is invisible to every arm.

`CorpusManifest.load` reads `corpus/manifest.json`, and every adapter ingests exactly what that
file lists. A transcript sitting on disk and missing from it is therefore not in the feed at all:
no arm can retrieve it, the task it belongs to is unwinnable by memory, and nothing anywhere
raises. The failure is silent in both directions, which is why it needs a test rather than care.

This has already happened once at scale. Six tasks were unwinnable for weeks because their
recorded sessions were on disk and unlisted, and it was found by accident rather than by a gate.
It happened again on 2026-08-30: `sessions/fa-dedup-key/p01.jsonl` was committed with its task
and the manifest was not rebuilt, so a brand new task was unwinnable by retrieval from the
moment it landed.

Nothing caught either one. `scripts/audit_corpus.py` iterates task directories and checks
containment, `tests/test_grid_prefixes.py` checks that a task CLASS is accounted for, and
neither compares the manifest against the tree. This does.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness.adapters.base import CORPUS_GLOBS

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "corpus"


def _on_disk() -> set[str]:
    """Exactly what `CorpusManifest.build` globs, IMPORTED so the two cannot drift apart.

    This used to copy the tuple while the docstring claimed the drift was impossible. Adding a
    fourth pattern to `base.py` would have left this test asserting the old three, which is the
    one moment the test exists for.
    """

    found: set[str] = set()
    for pattern in CORPUS_GLOBS:
        for path in CORPUS.glob(pattern):
            found.add(path.relative_to(CORPUS).as_posix())
    return found


def test_every_recorded_session_is_in_the_manifest():
    """The direction that makes a task unwinnable, silently."""

    listed = set(json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))["sessions"])
    unlisted = sorted(_on_disk() - listed)
    assert not unlisted, (
        f"{len(unlisted)} recorded session(s) are on disk and absent from corpus/manifest.json, "
        f"so no arm can retrieve them and whatever task they govern is unwinnable by memory: "
        f"{unlisted}. Rebuild with `python -c \"from harness.adapters.base import "
        f"CorpusManifest; CorpusManifest.build('corpus')\"`, and record the feed change: "
        f"adding a signal session moves the feed and breaks comparability with published runs."
    )


def test_the_manifest_lists_nothing_that_is_gone():
    """The other direction, which fails loudly at ingest instead of quietly, but still fails."""

    listed = set(json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))["sessions"])
    missing = sorted(listed - _on_disk())
    assert not missing, (
        f"corpus/manifest.json lists {len(missing)} file(s) that no longer exist: {missing}. "
        f"Every ingest will fail on the hash check until the manifest is rebuilt."
    )


def test_the_manifest_hashes_match_the_bytes():
    """A stale hash is the third way this can be wrong, and `verify()` is what catches it."""

    from harness.adapters.base import CorpusManifest

    CorpusManifest.load(CORPUS).verify()
