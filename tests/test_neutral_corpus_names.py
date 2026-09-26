"""No name an arm can read may say what a corpus document is.

Invariant: every rendered file name is `notes__<16 hex>.md`, the heading carries no stem, and
neither mentions the plant role (`stale_`, `rival_`), the task id, or the corpus origin
(`sessions`, `plants`, `synthetic`, `distractors`). Failure mode: until 2026-09-26 the renderer
named files from their corpus path and titled them with their stem, so a planted document told the
agent its role. recall returned the name as `source` in 112 of 112 rival and 80 of 80 stale hits in
the published runs, and fs_grep and mempalace showed it too.

The fixtures are the REAL planted sessions under `corpus/plants`, not invented names, so a new
plant whose name leaks is caught as well.

Red proof, 2026-09-26. `harness/corpus_names.py` is new, so running these against dafe4c10 would
only fail on import, which proves nothing. Each production line was instead reverted to its
dafe4c10 behaviour, the named test run, and the line restored:

| mutation | test | intended failure |
|---|---|---|
| `render_corpus` names from the corpus path | `..._reveal_no_role_task_or_origin` | `plants__ts-append-only__deploy_log_rfc3339.md` |
| heading carries the stem | `..._reveal_no_role_task_or_origin` | `# Session notes: p01` |
| lineage computes the path name | `..._names_a_document_the_same_way` | `['plants__ts-base36-id__stale_lowercase.md']` |
| recall decodes a neutral name | `..._instead_of_inventing_a_path` | `'notes/d0a0a960074dd1b2.jsonl' == 'notes__...md'` |
| mempalace accepts any base name | `..._legacy_names_is_refused` | `DID NOT RAISE RuntimeError` |
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from harness.corpus_names import NEUTRAL_NAME, neutral_key_map, neutral_stem, rendered_name
from harness.graph_metadata import structural_graph_metadata
from harness.lineage import frontmatter_for
from harness.transcripts import render_corpus

REPO = Path(__file__).resolve().parents[1]
PLANTS = REPO / "corpus" / "plants"
REVEALING = re.compile(r"stale|rival|synthetic|distractor|sessions|plants|ts-[a-z]", re.IGNORECASE)


def _real_corpus(tmp_path: Path) -> tuple[Path, list[Path]]:
    """Copy every real plant, plus one precursor per task, into a corpus-shaped tree."""

    root = tmp_path / "corpus"
    paths: list[Path] = []
    for plant in sorted(PLANTS.glob("*/*.jsonl")):
        task = plant.parent.name
        dest = root / "plants" / task / plant.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(plant, dest)
        paths.append(dest)
        precursor = root / "sessions" / task / "p01.jsonl"
        if not precursor.exists():
            precursor.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(plant, precursor)
            paths.append(precursor)
    assert any("stale_" in p.name for p in paths) and any("rival_" in p.name for p in paths)
    return root, paths


def test_rendered_names_and_headings_reveal_no_role_task_or_origin(tmp_path):
    root, paths = _real_corpus(tmp_path)
    out = tmp_path / "feed"
    assert render_corpus(paths, out, root=root) == len(paths)

    for rendered in sorted(out.iterdir()):
        assert NEUTRAL_NAME.match(rendered.name), rendered.name
        assert not REVEALING.search(rendered.name), rendered.name
        heading = next(
            line for line in rendered.read_text(encoding="utf-8").splitlines()
            if line.startswith("# ")
        )
        assert heading == "# Session notes", heading


def test_every_consumer_names_a_document_the_same_way(tmp_path):
    """Lineage `supersedes` and graph targets must point at files the renderer actually wrote."""

    root, paths = _real_corpus(tmp_path)
    out = tmp_path / "feed"
    render_corpus(paths, out, root=root)
    written = {p.name for p in out.iterdir()}

    targets: set[str] = set()
    for meta in frontmatter_for(paths, root, tier="declared").values():
        targets.update(v.strip() for v in meta.get("supersedes", "").split(",") if v.strip())
    for meta in structural_graph_metadata(paths, root).values():
        targets.update(re.findall(r"notes__[0-9a-f]{16}\.md", str(meta)))
    assert targets, "no lineage or graph target was produced, so this checked nothing"
    assert targets <= written, sorted(targets - written)[:3]


def test_a_neutral_name_joins_back_to_its_corpus_key():
    keys = ["plants/ts-tz-utc/stale_dubai_local.jsonl", "sessions/ts-tz-utc/p01.jsonl"]
    names = neutral_key_map(keys)
    for key in keys:
        assert names[neutral_stem(key) + ".md"] == key
    assert rendered_name(Path("c") / keys[0], Path("c")) == neutral_stem(keys[0]) + ".md"
    assert len(set(names)) == len(keys)


def test_recall_returns_a_neutral_source_bare_instead_of_inventing_a_path():
    """Decoding `__` in a neutral name would invent `notes/<digest>.jsonl`, a key that joins to
    nothing and reads exactly like a product retrieving nothing."""

    from adapters.recall.adapter import manifest_key

    name = neutral_stem("sessions/ts-tz-utc/p01.jsonl") + ".md"
    assert manifest_key(f"feed/{name}") == name
    # The legacy decode is kept for re-analysing the published runs.
    assert manifest_key("sessions__ts-tz-utc__p01.md") == "sessions/ts-tz-utc/p01.jsonl"


def test_a_base_palace_filed_under_legacy_names_is_refused(tmp_path):
    from adapters.mempalace.adapter import MemPalaceAdapter

    neutral = [neutral_stem("synthetic/s1.jsonl") + ".jsonl"]
    MemPalaceAdapter.check_base_names_are_neutral(tmp_path, neutral)
    with pytest.raises(RuntimeError, match="non-neutral names"):
        MemPalaceAdapter.check_base_names_are_neutral(
            tmp_path, neutral + ["synthetic__s2.jsonl"]
        )
