"""Every namespace that reaches a filesystem path is validated at the join.

⛔ This file exists because a comment claimed the property and nothing checked it. The guard
introduced for F-15 said it was "shared rather than per-adapter so a new vendor cannot arrive
without it", and it reached ONE of the eleven places a namespace is joined onto a path that the
same code later hands to `shutil.rmtree`.

The property is asserted two ways: **behaviourally**, by driving each adapter that owns a staging
directory with a traversal namespace, and **structurally**, by a source scan.

⚠️ **What the structural scan is, stated exactly, because the first version of this docstring
over-claimed and that is the very defect this file was written to retire.** It is a TRIPWIRE for
the obvious case, not a proof. It:

* covers `adapters/*/adapter.py` and `scripts/*.py`, and nothing else;
* is silenced for a whole file by any mention of `validate_namespace` or `namespace_path`, so it
  cannot see a second unguarded join in a file that already guards one;
* matches the fourteen join shapes in `MUST_FLAG` below and makes no claim beyond them. It will
  not see a namespace aliased through an intermediate name across lines, one assembled by
  `str.format`, `%`, or `+` before the join, one passed into a helper that joins elsewhere, or a
  join written in a file type it does not scan.

It catches the vendor who never heard of the guard. That case has now happened four times, which
is why it is worth having; it is not a reason to believe the class is closed.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest

from adapters.fs_grep.adapter import FsGrepAdapter
from adapters.mempalace.adapter import MemPalaceAdapter
from adapters.recall.adapter import RecallAdapter
from harness.adapters.base import namespace_path, validate_namespace

REPO = Path(__file__).resolve().parents[1]
BUNDLE = REPO / "corpus" / "claude_md_bundle_smoke.md"

#: Every one of these escaped a staging root, was read as an option, or named nothing.
TRAVERSALS = ("../../../../victim", "..", "a/../../b", "a/b", "-rf", "", "with space", "x\\y")


@pytest.mark.parametrize("bad", TRAVERSALS)
def test_the_primitive_refuses_every_traversal(bad):
    with pytest.raises(ValueError, match="namespace"):
        namespace_path("/root", bad, "feed")
    with pytest.raises(ValueError, match="namespace"):
        validate_namespace(bad)


def test_the_primitive_joins_an_ordinary_namespace_under_its_root():
    """A guard that broke the normal path would simply be deleted by the next person."""

    joined = namespace_path("/root", "bench-official", "feed").as_posix()
    assert joined.endswith("/root/bench-official/feed")


@pytest.mark.parametrize("bad", ["../../../../victim", "..", "a/../../b", "-rf", ""])
def test_no_adapter_builds_a_staging_path_from_a_traversal(bad):
    """The behavioural half, over the three adapters that own a directory on this machine.

    Each of these classes joins the namespace onto a root and later calls `shutil.rmtree` on the
    result, so the escape is a deletion outside the root rather than a mere wrong path.
    """

    root = tempfile.mkdtemp()
    for adapter in (
        FsGrepAdapter(staging_root=root, base_prompt_file=BUNDLE),
        RecallAdapter(staging_root=root, base_prompt_file=BUNDLE),
        MemPalaceAdapter(staging_root=root, base_prompt_file=BUNDLE),
    ):
        for attribute in ("_staging_dir", "_palace_dir", "_feed_dir"):
            builder = getattr(adapter, attribute, None)
            if builder is None:
                continue
            with pytest.raises(ValueError, match="namespace"):
                builder(bad)


#: A namespace used as an OPERAND of a path join, in the shapes this codebase writes.
#:
#: ⚠️ Widened twice, and the history is the point. Version one matched `/ namespace` and
#: `/ f"{namespace}"` only, and missed six of ten probed shapes. Version two still missed SEVEN
#: of thirteen: `self.root / self.namespace`, `Path(root, ns)`, `root.joinpath(ns)`,
#: `Path(f"{root}/{ns}")`, an aliased `ns`, a `*_namespace` suffix, and `(namespace + "-feed")`.
#: A scan that misses is worse than no scan, because it certifies. Every shape it recognises is
#: asserted in `MUST_FLAG`, and every line it must leave alone in `MUST_NOT_FLAG`, so the scan's
#: own coverage is measured rather than assumed. Add to those lists before touching the pattern.
_NS = r"(?:[A-Za-z0-9_]*namespace|tenant|ns)\b"
_ATTR = r"(?:[A-Za-z_][A-Za-z0-9_.]*\.)?"
_RAW_JOIN = re.compile(
    "|".join(
        (
            rf"/\s*\(?\s*{_ATTR}{_NS}",
            rf"""f["'][^"']*/[^"']*\{{{_ATTR}{_NS}""",
            rf"""/\s*f["'][^"']*\{{{_ATTR}{_NS}""",
            rf"\.joinpath\([^)]*{_ATTR}{_NS}",
            rf"(?<![A-Za-z_])Path\([^)]*,\s*{_ATTR}{_NS}",
            rf"os\.path\.join\([^)]*{_ATTR}{_NS}",
        )
    )
)

#: Scanned, not just `adapters/`: `scripts/pilot.py` built the fs_grep store path from
#: `args.namespace` and `scripts/prepare_recall_corpora.py` built an archive name from a tenant.
#: Both are entry points a person types into.
_SCANNED = ("adapters/*/adapter.py", "scripts/*.py")

#: Every join shape the scan is claimed to recognise. Six were invisible to version one of the
#: pattern and seven to version two; each was a real site in this tree or one line away from one.
MUST_FLAG = (
    'self.staging_root / namespace / "memory"',
    'self._palace_root() / f"{namespace}-feed"',
    "self.root / namespace.strip()",
    "self.staging_root / tenant",
    "shutil.rmtree(self.root / namespace)",
    "self.root / self.namespace",
    "Path(root, namespace)",
    "Path(os.path.join(root, namespace))",
    "self.root.joinpath(namespace)",
    'Path(f"{root}/{namespace}")',
    "self.root / ns",
    "self.staging_root / arm_namespace",
    'self.root / (namespace + "-feed")',
    "staging / args.namespace",
)

#: Lines that mention a namespace and join nothing. Over-triggering is the right direction for
#: this instrument, but a scan that cries wolf gets deleted, so the false-alarm floor is tested.
MUST_NOT_FLAG = (
    'return self.build(session_dir, namespace, prompt_path=session_dir / "prompt.md")',
    'raise ValueError(f"refusing namespace {namespace!r}")',
    "def _staging_dir(self, namespace: str) -> Path:",
    "def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:",
    '        f"tenant {tenant} is not ready"',
    "    for condition in conditions:",
)


def test_nothing_joins_a_namespace_onto_a_path_without_the_primitive():
    """The structural tripwire. Read the module docstring for exactly what it does not cover."""

    offenders = []
    for pattern in _SCANNED:
        for path in sorted(REPO.glob(pattern)):
            text = path.read_text(encoding="utf-8")
            if "validate_namespace" in text or "namespace_path" in text:
                continue
            joins = [
                line.strip()
                for line in text.splitlines()
                if _RAW_JOIN.search(line) and not line.strip().startswith("#")
            ]
            if joins:
                offenders.append(f"{path.relative_to(REPO).as_posix()}: {joins[0]}")
    assert not offenders, (
        "these files join a namespace onto a path and never validate one; route the join "
        "through harness.adapters.base.namespace_path:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("shape", MUST_FLAG)
def test_the_scan_recognises_every_join_shape_it_claims_to(shape):
    """The scan's own coverage, because a scan nobody tests is a scan nobody may trust."""

    assert _RAW_JOIN.search(shape), f"the scan would not see {shape!r}"


@pytest.mark.parametrize("shape", MUST_NOT_FLAG)
def test_the_scan_does_not_flag_a_line_that_merely_mentions_a_namespace(shape):
    """Over-triggering is the right direction, but not to the point of being ignored."""

    assert not _RAW_JOIN.search(shape), f"false alarm on {shape!r}"
