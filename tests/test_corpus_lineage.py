"""Lineage frontmatter: the three tiers, and the properties that stop a silent Tier-0.

Preregistration 023. The failure this file mostly guards against is not a wrong date, it is a
render that emits NOTHING and is then reported as "lineage does not help" -- the same false-negative
shape that cost this project a day twice on 2026-08-31, once through a successful build reported as
failed and once through three wrong-field reads.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.lineage import TIERS, earliest_ts, frontmatter_for, render_frontmatter
from harness.transcripts import render_corpus, render_transcript


def _session(path: Path, day: str, text: str = "note") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"role": "user", "content": text, "ts": f"{day}T09:00:00Z"}) + "\n",
        encoding="utf-8",
    )
    return path


def _pair(root: Path, task: str = "ts-x", stale_day="2026-02-19", cur_day="2026-08-07"):
    d = root / "sessions" / task
    stale = _session(d / "stale_old_way.jsonl", stale_day, "we use the old convention")
    cur = _session(d / "p01.jsonl", cur_day, "the old convention broke production")
    return stale, cur


# --- the control must be byte-identical, or it is not a control -------------------------------


def test_no_frontmatter_by_default(tmp_path):
    """Tier 0 must be the SAME code path as production, not a reconstruction of it."""
    s = _session(tmp_path / "a.jsonl", "2026-01-01")
    assert render_transcript(s).startswith("# Session notes: a")
    assert "---" not in render_transcript(s).splitlines()[0]


def test_tier_none_returns_no_frontmatter(tmp_path):
    stale, cur = _pair(tmp_path)
    assert frontmatter_for([stale, cur], tmp_path, "none") == {}


def test_an_unknown_tier_is_refused(tmp_path):
    with pytest.raises(ValueError, match="lineage tier"):
        frontmatter_for([], tmp_path, "whatever")


# --- timestamps: real data only, never a guess ------------------------------------------------


def test_valid_from_is_the_earliest_ts(tmp_path):
    p = tmp_path / "b.jsonl"
    p.write_text(
        "\n".join(
            json.dumps({"role": "user", "content": "x", "ts": t})
            for t in ("2026-05-04T10:00:00Z", "2026-03-02T08:00:00Z", "2026-09-01T00:00:00Z")
        ),
        encoding="utf-8",
    )
    assert earliest_ts(p) == "2026-03-02"


def test_a_session_without_a_timestamp_gets_no_frontmatter(tmp_path):
    """An invented date is indistinguishable downstream from a real one."""
    p = tmp_path / "c.jsonl"
    p.write_text(json.dumps({"role": "user", "content": "no ts here"}) + "\n", encoding="utf-8")
    assert earliest_ts(p) is None
    assert frontmatter_for([p], tmp_path, "timestamps") == {}


def test_timestamps_tier_adds_no_supersession(tmp_path):
    """The whole point of this tier is that it adds NO information."""
    stale, cur = _pair(tmp_path)
    out = frontmatter_for([stale, cur], tmp_path, "timestamps")
    assert out[stale] == {"valid_from": "2026-02-19"}
    assert out[cur] == {"valid_from": "2026-08-07"}
    assert not any("supersedes" in m or "valid_until" in m for m in out.values())


# --- declared: the tier that actually marks the stale document ---------------------------------


def test_declared_marks_the_stale_side_and_points_the_current_one_at_it(tmp_path):
    stale, cur = _pair(tmp_path)
    out = frontmatter_for([stale, cur], tmp_path, "declared")
    assert out[stale]["valid_until"] == "2026-08-06", "must end the day BEFORE its successor"
    assert out[cur]["supersedes"] == "sessions__ts-x__stale_old_way.md"
    assert out[cur].get("valid_until") is None


def test_valid_until_is_the_day_before_because_the_bound_is_inclusive(tmp_path):
    """recall's `valid_until` ends at 23:59:59.999999 of that day.

    Ending the stale document on its successor's own day would leave BOTH valid simultaneously,
    which is precisely the condition this exists to remove.
    """
    stale, _ = _pair(tmp_path, cur_day="2026-03-01")
    out = frontmatter_for(list(stale.parent.glob("*.jsonl")), tmp_path, "declared")
    assert out[stale]["valid_until"] == "2026-02-28"


def test_an_ambiguous_pair_is_left_alone(tmp_path):
    """Two current candidates means the successor is a guess, and a wrong successor demotes the
    document the task actually needs."""
    d = tmp_path / "sessions" / "ts-y"
    stale = _session(d / "stale_a.jsonl", "2026-01-01")
    _session(d / "p01.jsonl", "2026-02-01")
    _session(d / "p02.jsonl", "2026-03-01")
    out = frontmatter_for(list(d.glob("*.jsonl")), tmp_path, "declared")
    assert "valid_until" not in out.get(stale, {})
    assert not any("supersedes" in m for m in out.values())


def test_a_task_with_no_stale_plant_gets_no_supersedes(tmp_path):
    d = tmp_path / "sessions" / "ts-z"
    only = _session(d / "p01.jsonl", "2026-04-04")
    out = frontmatter_for([only], tmp_path, "declared")
    assert out[only] == {"valid_from": "2026-04-04"}


# --- the rendered block, which is what recall actually parses ----------------------------------


def test_frontmatter_renders_as_a_yaml_block_recall_can_parse(tmp_path):
    stale, cur = _pair(tmp_path)
    out = frontmatter_for([stale, cur], tmp_path, "declared")
    text = render_transcript(cur, out[cur])
    lines = text.splitlines()
    assert lines[0] == "---"
    assert "valid_from: 2026-08-07" in lines
    assert "supersedes: sessions__ts-x__stale_old_way.md" in lines
    assert lines[lines.index("---", 1)] == "---"
    assert "# Session notes: p01" in text


def test_key_order_is_stable_so_the_corpus_digest_is(tmp_path):
    """An unordered dump would change the corpus fingerprint on every render, and the adapter
    would refuse a corpus that had not actually changed."""
    meta = {"supersedes": "x.md", "valid_until": "2026-01-01", "valid_from": "2025-01-01"}
    a = render_frontmatter(meta)
    b = render_frontmatter(dict(reversed(list(meta.items()))))
    assert a == b
    assert a.splitlines()[1:4] == [
        "valid_from: 2025-01-01",
        "valid_until: 2026-01-01",
        "supersedes: x.md",
    ]


def test_empty_frontmatter_renders_nothing(tmp_path):
    assert render_frontmatter(None) == ""
    assert render_frontmatter({}) == ""


# --- the guard preregistration 023 makes non-optional ------------------------------------------


def test_declared_render_actually_reaches_disk(tmp_path):
    """THE guard. A silently unparsed or unwritten block reproduces Tier 0 exactly, and would be
    reported as 'lineage does not help' rather than as a broken render."""
    stale, cur = _pair(tmp_path)
    target = tmp_path / "out"
    meta = frontmatter_for([stale, cur], tmp_path, "declared")
    n = render_corpus([stale, cur], target, root=tmp_path, lineage=meta)
    assert n == 2
    stale_md = (target / "sessions__ts-x__stale_old_way.md").read_text(encoding="utf-8")
    cur_md = (target / "sessions__ts-x__p01.md").read_text(encoding="utf-8")
    assert "valid_until: 2026-08-06" in stale_md, "the stale document carries no expiry on disk"
    assert "supersedes:" in cur_md, "the current document names no predecessor on disk"


def test_control_render_is_byte_identical_without_lineage(tmp_path):
    stale, cur = _pair(tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    render_corpus([stale, cur], a, root=tmp_path)
    render_corpus([stale, cur], b, root=tmp_path, lineage={})
    for name in ("sessions__ts-x__p01.md", "sessions__ts-x__stale_old_way.md"):
        assert (a / name).read_bytes() == (b / name).read_bytes()
        assert not (a / name).read_text(encoding="utf-8").startswith("---")


def test_every_tier_is_reachable():
    assert TIERS == ("none", "timestamps", "declared")


def test_every_render_call_site_passes_lineage():
    """All three production call sites must route through `lineage_from_env`.

    `harness/transcripts.py` states that a feed which differs between arms is not a shared feed.
    If one call site forgot lineage, recall would index annotated documents while fs_grep indexed
    bare ones, and the tiers would compare two corpora rather than two renderings. Checked against
    the AST so formatting cannot break it and deleting the argument cannot pass it.
    """
    import ast

    sites = [
        REPO / "adapters" / "recall" / "adapter.py",
        REPO / "adapters" / "fs_grep" / "adapter.py",
        REPO / "scripts" / "prepare_recall_corpora.py",
    ]
    for path in sites:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "render_corpus"
        ]
        assert calls, f"{path.name} no longer calls render_corpus"
        for call in calls:
            kwargs = {k.arg for k in call.keywords}
            assert "lineage" in kwargs, (
                f"{path.name} calls render_corpus without lineage=, so its arm would index a "
                f"different corpus than the others and the tiers would be uncomparable"
            )
