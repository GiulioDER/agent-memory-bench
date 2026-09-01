"""The leaderboard page promises no number is typed in by hand. This is the enforcement."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_leaderboard.py"


def _generator():
    """The script, imported by path: ``scripts/`` is not a package."""
    spec = importlib.util.spec_from_file_location("build_leaderboard", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The INTERNAL names: what a run summary carries, what the harness and the adapters use.
# DERIVED from the generator, not restated. Both lists below were literals until 2026-08-29, and
# adding one arm to PRODUCT_ARMS then failed seven tests here for no reason connected to what any
# of them asserts. A fixture that has to be edited in step with the source is a fixture that will
# one day be edited to match a bug.
ARMS = [name for name, *_ in _generator().PRODUCT_ARMS]

# What the PAGE is allowed to print. The third-party arms are unannounced, so they reach the
# site as neutral placeholders; the mapping lives in the generator's PRODUCT_ARMS.
def _public_arms() -> list[str]:
    names, anonymous = [], 0
    for *_, public in _generator().PRODUCT_ARMS:
        if public is None:
            names.append("product_" + chr(ord("a") + anonymous))
            anonymous += 1
        else:
            names.append(public)
    return names


PUBLIC_ARMS = _public_arms()


def _run(*args, root=None):
    cmd = [sys.executable, str(SCRIPT), *args]
    if root is not None:
        cmd += ["--root", str(root)]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _summary():
    arm = {
        "success": 0.5,
        "delta": 0.1,
        "ci": [0.0, 0.2],
        "discarded": 1,
        "tokensPerTask": 200,
        "costPerTask": 1.25,
    }
    arms = {name: dict(arm) for name in ARMS}
    arms["claude_md"]["delta"] = 0
    return {
        "run": {
            "id": "run-x",
            "date": "2026-09-01",
            "cli": "2.1.230",
            "model": "test-model",
            "tasks": 24,
            "sessionsPerCell": 3,
            "prereg": "preregistration/005-run-x.md",
        },
        "arms": arms,
        # Derived, for the reason stated above ARMS: a hardcoded track list broke five tests
        # here on 2026-09-01 when `protocol` joined REFERENCE_TRACKS, none of them about tracks.
        "reference": {
            name: {"success": 0.6, "delta": 0.2}
            for name, _ in _generator().REFERENCE_TRACKS
        },
    }


def _scaffold(tmp_path, summary=None, official_run=None):
    data = tmp_path / "site" / "data"
    data.mkdir(parents=True)
    (data / "leaderboard.config.json").write_text(
        json.dumps({"official_run": official_run, "updated": "2026-08-26"}),
        encoding="utf-8",
    )
    if summary is not None:
        run_dir = tmp_path / "results" / official_run
        run_dir.mkdir(parents=True)
        (run_dir / "leaderboard_summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )
    return tmp_path


def _payload(root):
    text = (root / "site" / "data" / "leaderboard.js").read_text(encoding="utf-8")
    return json.loads(text.split("window.AMB_LEADERBOARD = ", 1)[1].rstrip().rstrip(";"))


def test_committed_leaderboard_matches_its_regeneration():
    result = _run("--check")
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_hand_edited_number_fails_the_check(tmp_path):
    root = _scaffold(tmp_path)
    assert _run(root=root).returncode == 0
    out = root / "site" / "data" / "leaderboard.js"
    out.write_text(
        out.read_text(encoding="utf-8").replace('"success": null', '"success": 0.99', 1),
        encoding="utf-8",
    )
    result = _run("--check", root=root)
    assert result.returncode == 1
    assert "Never edit it by hand" in result.stdout


def test_phase0_emits_null_run_and_pending_numbers(tmp_path):
    root = _scaffold(tmp_path)
    assert _run(root=root).returncode == 0
    data = _payload(root)
    assert data["run"] is None
    assert [a["name"] for a in data["arms"]] == PUBLIC_ARMS
    baseline = next(a for a in data["arms"] if a["name"] == "claude_md")
    assert baseline["delta"] == 0 and baseline["success"] is None


def test_official_summary_fills_the_page(tmp_path):
    root = _scaffold(tmp_path, summary=_summary(), official_run="run-x")
    result = _run(root=root)
    assert result.returncode == 0, result.stdout + result.stderr
    data = _payload(root)
    assert data["run"]["id"] == "run-x"
    recall = next(a for a in data["arms"] if a["name"] == "recall")
    assert recall["success"] == 0.5 and recall["costPerTask"] == 1.25


def test_a_summary_missing_an_arm_is_refused(tmp_path):
    summary = _summary()
    del summary["arms"]["bare"]
    root = _scaffold(tmp_path, summary=summary, official_run="run-x")
    result = _run(root=root)
    assert result.returncode != 0
    assert "bare" in result.stderr


def test_a_moved_baseline_is_refused(tmp_path):
    summary = _summary()
    summary["arms"]["claude_md"]["delta"] = 0.01
    root = _scaffold(tmp_path, summary=summary, official_run="run-x")
    result = _run(root=root)
    assert result.returncode != 0
    assert "baseline" in result.stderr


def test_an_undisclosed_arm_never_reaches_the_page(tmp_path):
    """The point of the disclosure layer, asserted with numbers present.

    An arm is easy to anonymise while it is empty, so this fills every arm from a summary
    and checks the page in the state it will actually ship in: a generator that passed the
    internal name through anywhere, the label, the type or a stray key, is caught.

    The roster carries no undisclosed arm today, and the mechanism still has to work the
    day one arrives. So the arm is INJECTED rather than borrowed from the live list: a
    guard that only runs while somebody happens to be undisclosed is a guard that rots
    unwatched, and skipping here would have been a vacuous pass by another name. Injection
    means calling ``build`` in process, since the generator otherwise runs in a subprocess
    no monkeypatch reaches.
    """
    generator = _generator()
    secret = "acme_memory"
    generator.PRODUCT_ARMS = [
        (secret, "SaaS API", None, None),
        *generator.PRODUCT_ARMS,
    ]

    summary = _summary()
    summary["arms"][secret] = dict(next(iter(summary["arms"].values())))
    root = _scaffold(tmp_path, summary=summary, official_run="run-x")

    text = generator.build(root)
    assert secret not in text, f"{secret!r} leaked into the generated page"
    assert "SaaS API" not in text, "the integration description identifies the arm on its own"

    data = json.loads(text.split("window.AMB_LEADERBOARD = ", 1)[1].rstrip().rstrip(";"))
    assert [a["name"] for a in data["arms"]] == ["product_a", *PUBLIC_ARMS]
    anonymous = next(a for a in data["arms"] if a["name"] == "product_a")
    assert anonymous["success"] == 0.5, "an undisclosed arm still carries its real numbers"


def _config(root, **extra):
    path = root / "site" / "data" / "leaderboard.config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config.update(extra)
    path.write_text(json.dumps(config), encoding="utf-8")


def test_a_ranking_is_titled_for_the_path_it_measured(tmp_path):
    """F2's second remedy, as a build step rather than as a promise.

    The corpus is bulk ingested once and never written to again, so a ranking built from it ranks
    retrieval: a product that sells extraction and consolidation at write time is credited for
    neither. The page has to say that itself, next to the table, and the generator is what puts
    it there. A README paragraph is the first thing a launch edits.
    """

    root = _scaffold(tmp_path, summary=_summary(), official_run="run-x")
    assert _run(root=root).returncode == 0
    scope = _payload(root)["scope"]
    assert scope["writePathMeasured"] is False
    assert scope["title"] == "Retrieval over a bulk-ingested corpus"
    assert "write path is not measured" in scope["qualification"].lower()


def test_dropping_the_qualification_requires_naming_the_run_that_earned_it(tmp_path):
    """The switch and its evidence move together. Setting the flag alone fails the build rather
    than quietly retitling the page."""

    root = _scaffold(tmp_path, summary=_summary(), official_run="run-x")
    _config(root, write_path_measured=True)
    result = _run(root=root)
    assert result.returncode != 0
    assert "longitudinal_run" in (result.stdout + result.stderr)

    _config(root, longitudinal_run="longitudinal-001")
    assert _run(root=root).returncode == 0
    scope = _payload(root)["scope"]
    assert scope["writePathMeasured"] is True
    assert scope["longitudinalRun"] == "longitudinal-001"


def test_the_scope_note_is_rendered_by_the_page(tmp_path):
    """A generated qualification nothing renders is a qualification nobody reads."""

    html = (REPO_ROOT / "site" / "leaderboard.html").read_text(encoding="utf-8")
    js = (REPO_ROOT / "site" / "site.js").read_text(encoding="utf-8")
    assert 'id="scope-note"' in html
    assert "scope-note" in js and "D.scope.qualification" in js


# --- the vendor review hold, which is a PUBLIC COMMITMENT and therefore a mechanism ----------


def test_a_held_arm_publishes_no_numbers_even_when_the_summary_has_them(tmp_path):
    """The promise made in the vendor's own issue thread, enforced rather than remembered."""

    held = sorted(_generator().VENDOR_REVIEW_HOLDS)
    assert held, "no arm is held; this test is vacuous and should be deleted with the last hold"
    root = _scaffold(tmp_path, summary=_summary(), official_run="run-x")
    assert _run(root=root).returncode == 0
    public = dict(zip([a for a, *_ in _generator().PRODUCT_ARMS], _public_arms()))
    for internal in held:
        row = next(a for a in _payload(root)["arms"] if a["name"] == public[internal])
        assert row["success"] is None, f"{internal} published a success while held"
        assert row["delta"] is None and row["ci"] is None
        assert row["costPerTask"] is None


def test_a_held_arm_says_why_and_links_the_thread(tmp_path):
    """A blank row with no reason reads as "measured nothing", the opposite of a hold."""

    root = _scaffold(tmp_path, summary=_summary(), official_run="run-x")
    _run(root=root)
    holds = _generator().VENDOR_REVIEW_HOLDS
    public = dict(zip([a for a, *_ in _generator().PRODUCT_ARMS], _public_arms()))
    for internal, hold in holds.items():
        row = next(a for a in _payload(root)["arms"] if a["name"] == public[internal])
        assert row["held"] == hold["reason"]
        assert row["heldUntil"] == hold["until"]
        assert row["heldIssue"].startswith("http"), "the promise must be checkable by a reader"


def test_a_hold_cannot_smuggle_a_missing_arm_past_the_summary_check(tmp_path):
    """Blanking happens AFTER the read, so a held arm still has to be in the summary."""

    internal = min(_generator().VENDOR_REVIEW_HOLDS)
    summary = _summary()
    del summary["arms"][internal]
    root = _scaffold(tmp_path, summary=summary, official_run="run-x")
    result = _run(root=root)
    assert result.returncode != 0, "a held arm absent from the summary was accepted"


def test_the_hold_is_keyed_on_presence_not_on_a_date(tmp_path):
    """Two builds must agree. A date-computed hold would make the generated file drift.

    It would also expire SILENTLY, where deleting an entry is a deliberate act performed at
    exactly the moment somebody should confirm the window closed rather than merely elapsed.
    """

    root = _scaffold(tmp_path, summary=_summary(), official_run="run-x")
    _run(root=root)
    first = (root / "site" / "data" / "leaderboard.js").read_text(encoding="utf-8")
    _run(root=root)
    second = (root / "site" / "data" / "leaderboard.js").read_text(encoding="utf-8")
    assert first == second

    source = (REPO_ROOT / "scripts" / "build_leaderboard.py").read_text(encoding="utf-8")
    hold_block = source[source.index("VENDOR_REVIEW_HOLDS") :][:2000]
    for forbidden in ("date.today", "datetime.now", "time.time"):
        assert forbidden not in hold_block, f"the hold consults the clock via {forbidden}"


def test_the_page_does_not_rank_a_held_arm():
    """A withheld row must not carry a rank number implying it placed there."""

    js = (REPO_ROOT / "site" / "site.js").read_text(encoding="utf-8")
    assert "!a.held" in js, "site.js ranks held arms"
    assert "a.held" in js and "heldUntil" in js, "site.js does not render the hold reason"


def test_the_front_page_arm_count_matches_the_generator():
    """The hand-written stat tile on index.html must agree with `public_arms()`.

    Everything on leaderboard.html is generated, which is why this file exists. The stat band on
    index.html is not: it is four numbers typed into HTML, and one of them counts arms. It read
    "6 arms in the official run" until 2026-09-01, which was wrong twice over. There is no
    official run (`site/data/leaderboard.config.json` carries `"official_run": null`, and the
    methods table on the same page calls every run so far bring-up rather than result), and no
    run has ever had exactly that set: official-002 paired six arms but a DIFFERENT six,
    including `recall_prefetch` and excluding `mempalace`, which ran as a separate two-arm pass.

    The number was right and the sentence around it was not, which is the hard case: nothing
    fails, and a reader who counts the eight arms in the strip below it gets no explanation of
    the gap. So the tile now names what it counts, and this pins it to the source that decides
    the count rather than to a literal.
    """
    import re

    index = (REPO_ROOT / "site" / "index.html").read_text(encoding="utf-8")
    tiles = re.findall(
        r'<div class="n">(\d+)</div><div class="l">([^<]*arms[^<]*)</div>', index
    )
    assert len(tiles) == 1, f"expected exactly one arm tile in the stat band, found {tiles}"

    count, label = tiles[0]
    expected = len(_public_arms())
    assert int(count) == expected, (
        f"index.html says {count} arms, public_arms() has {expected}"
    )
    assert "official run" not in label, (
        f"the tile claims an official run, which does not exist: {label!r}"
    )
