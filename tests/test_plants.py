"""The gate a planted corpus must pass before any damage rate built on it is worth reading.

Three families here, and they fail in three different ways:

* **shape** — a condition that does not hold what its name says. `superseded` without the current
  fact is `absent`; `contradictory` with one memo is `adjacent`. Both would run and be reported
  under the wrong name, which is the worst kind of bug in a benchmark because the number looks
  fine.
* **composition** — the assembler quietly dropping sessions, which would shrink the feed and
  benchmark an easier retrieval problem than every published run.
* **timestamps** — the mitigation for `contradictory` being undated. If the permutation is
  constant, recording order decides the tie in every seed and a recency-weighted system is handed
  a signal the design never meant to give it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.assemble_condition_corpus as assembler
from harness.plants import (
    CONDITION_SHAPE,
    PlantSpecError,
    assign_contradiction_dates,
    load_plants,
    sources_for,
)
from harness.tasks import discover_tasks
from scripts.assemble_condition_corpus import assemble, restamp

TASKS = {task.task_id: task for task in discover_tasks()}


def write_spec(tmp_path: Path, body: dict) -> Path:
    task_dir = tmp_path / "ts-example"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "plants.json").write_text(json.dumps(body), encoding="utf-8")
    return task_dir


ONE_PLANT = {"wrong_terms": ["emitted lowercase"], "rationale": "worked example"}


# ---------------------------------------------------------------------------------------
# shape: a condition must hold what its name says
# ---------------------------------------------------------------------------------------


def test_superseded_without_the_current_fact_is_refused(tmp_path):
    """Mutation: dropping the include_real comparison. The corpus then holds only the stale memo,
    which is the `absent` condition reported as `superseded`."""

    task_dir = write_spec(
        tmp_path,
        {
            "conditions": {"superseded": {"include_real": False, "plants": ["stale"]}},
            "plants": {"stale": ONE_PLANT},
        },
    )
    with pytest.raises(PlantSpecError, match="different condition reported under the wrong name"):
        load_plants(task_dir)


def test_contradictory_needs_two_memos(tmp_path):
    """One memo that disagrees with nothing is the `adjacent` condition."""

    task_dir = write_spec(
        tmp_path,
        {
            "conditions": {"contradictory": {"include_real": False, "plants": ["one"]}},
            "plants": {"one": ONE_PLANT},
        },
    )
    with pytest.raises(PlantSpecError, match="needs at least 2 plant"):
        load_plants(task_dir)


def test_absent_may_not_plant_anything(tmp_path):
    task_dir = write_spec(
        tmp_path,
        {
            "conditions": {"absent": {"include_real": False, "plants": ["stale"]}},
            "plants": {"stale": ONE_PLANT},
        },
    )
    with pytest.raises(PlantSpecError, match="at most 0 plant"):
        load_plants(task_dir)


def test_a_plant_with_no_wrong_terms_is_refused(tmp_path):
    """Without wrong_terms the leakage audit has nothing to check and endpoint 4 cannot attribute
    a failure to the plant, so the plant is unmeasurable while looking configured."""

    task_dir = write_spec(
        tmp_path,
        {
            "conditions": {"superseded": {"include_real": True, "plants": ["stale"]}},
            "plants": {"stale": {"rationale": "no terms"}},
        },
    )
    with pytest.raises(PlantSpecError, match="declares no wrong_terms"):
        load_plants(task_dir)


def test_a_condition_naming_an_undeclared_plant_is_refused(tmp_path):
    task_dir = write_spec(
        tmp_path,
        {
            "conditions": {"superseded": {"include_real": True, "plants": ["ghost"]}},
            "plants": {"stale": ONE_PLANT},
        },
    )
    with pytest.raises(PlantSpecError, match="which is not declared"):
        load_plants(task_dir)


def test_an_unknown_condition_is_refused(tmp_path):
    task_dir = write_spec(
        tmp_path,
        {"conditions": {"stale-ish": {"plants": []}}, "plants": {}},
    )
    with pytest.raises(PlantSpecError, match="unknown condition"):
        load_plants(task_dir)


def test_a_task_with_no_plants_json_is_none(tmp_path):
    assert load_plants(tmp_path) is None


def test_every_shape_matches_the_preregistered_table():
    """Preregistration 005's four adversarial conditions, unchanged, plus `present` from 017.

    This test fired when `present` was added, which is exactly what it is for: the four shapes
    below are a frozen record and a fifth entry appearing beside them has to be a deliberate,
    attributable act rather than a drift. So the assertion is split rather than widened.

    005's four are asserted by identity against `CONDITIONS`, so nothing can be added to, removed
    from or reshaped inside that record without this failing again. `present` is asserted
    separately, named to its own record, and it carries no plant by construction: it is the
    identity transform on the corpus and the only condition in which abstaining is a LOSS.
    """

    from harness.damage import CONDITIONS, PRESENT

    assert set(CONDITION_SHAPE) == {*CONDITIONS, PRESENT}
    assert set(CONDITIONS) == {"absent", "superseded", "contradictory", "adjacent"}
    assert CONDITION_SHAPE["superseded"]["include_real"] is True
    for condition in ("absent", "contradictory", "adjacent"):
        assert CONDITION_SHAPE[condition]["include_real"] is False

    # `present` (preregistration 017): the real session and nothing else.
    assert CONDITION_SHAPE[PRESENT] == {
        "include_real": True,
        "min_plants": 0,
        "max_plants": 0,
    }


# ---------------------------------------------------------------------------------------
# the shipped spec
# ---------------------------------------------------------------------------------------


def test_the_shipped_specs_load_and_name_real_conditions():
    for task_id, task in sorted(TASKS.items()):
        spec = load_plants(task.path)
        if spec is None:
            continue
        assert spec.conditions, f"{task_id}: plants.json declares no conditions"
        for condition, plan in spec.conditions.items():
            assert plan.condition == condition
            for plant in plan.plants:
                assert plant.wrong_terms, f"{task_id}/{plant.name}: no wrong terms"


def test_an_unrecorded_plant_refuses_rather_than_composing_a_short_corpus(tmp_path):
    """Mutation: skipping the is_file() check. The condition then assembles without its plant and
    scores as `absent` while being reported as whatever it declared."""

    spec = load_plants(TASKS["ts-base36-id"].path)
    plan = spec.plan("superseded")
    # The real session must exist, or the earlier include_real guard fires instead and this test
    # would pass while proving nothing about the plant.
    real = tmp_path / "sessions" / "ts-base36-id"
    real.mkdir(parents=True)
    (real / "p01.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(PlantSpecError, match="has not been recorded yet"):
        sources_for(plan, "ts-base36-id", tmp_path)


# ---------------------------------------------------------------------------------------
# composition
# ---------------------------------------------------------------------------------------


@pytest.fixture
def fake_corpus(tmp_path, monkeypatch):
    """A miniature corpus: one selected task with a recorded plant, one untouched task."""

    root = tmp_path / "corpus"
    (root / "sessions" / "ts-base36-id").mkdir(parents=True)
    (root / "sessions" / "ts-casefold-sort").mkdir(parents=True)
    (root / "plants" / "ts-base36-id").mkdir(parents=True)
    (root / "distractors").mkdir(parents=True)

    def jsonl(path: Path, content: str) -> None:
        path.write_text(
            json.dumps({"role": "user", "content": content, "ts": "2026-01-01T09:00:00Z"}) + "\n",
            encoding="utf-8",
        )

    jsonl(root / "sessions" / "ts-base36-id" / "p01.jsonl", "the true restricted alphabet memo")
    jsonl(root / "sessions" / "ts-casefold-sort" / "p01.jsonl", "an unrelated roster memo")
    jsonl(root / "plants" / "ts-base36-id" / "stale_lowercase.jsonl", "ids are emitted lowercase")
    jsonl(root / "distractors" / "d001.jsonl", "a mundane session")

    monkeypatch.setattr(assembler, "BASE_CORPUS", root)
    return root


def test_a_condition_corpus_keeps_every_untouched_session(fake_corpus, tmp_path):
    """Mutation: dropping the non-selected branch. The feed shrinks to the tasks under test, the
    retrieval problem gets easier, and the damage rate stops being comparable with any published
    run."""

    out = tmp_path / "out"
    provenance = assemble("superseded", 1, ["ts-base36-id"], out)

    assert (out / "sessions" / "ts-casefold-sort" / "p01.jsonl").is_file()
    assert "ts-casefold-sort" in provenance["tasks_untouched"]
    assert (out / "distractors" / "d001.jsonl").is_file()
    # real + plant for the selected task, plus the untouched task and the distractor
    assert provenance["sessions_total"] == 4


def test_a_session_directory_that_is_not_a_task_survives(fake_corpus, tmp_path):
    """Mutation: iterating discovered tasks instead of the directories on disk.

    `corpus/sessions/smoke/` holds two sessions belonging to no task, and CorpusManifest globs
    `sessions/**/*.jsonl`, so the published runs ingested them. Iterating tasks alone dropped both,
    and the loss was invisible in the count because the same pass added two plants and the total
    came back to exactly 125. That is the shape of bug this whole file exists for: the feed silently
    stops being the one every published run used, and nothing looks wrong.
    """

    orphan = fake_corpus / "sessions" / "smoke"
    orphan.mkdir(parents=True)
    (orphan / "s01.jsonl").write_text(
        json.dumps({"role": "user", "content": "a smoke session", "ts": "2026-01-01T09:00:00Z"})
        + "\n",
        encoding="utf-8",
    )

    out = tmp_path / "out"
    assemble("superseded", 1, ["ts-base36-id"], out)
    assert (out / "sessions" / "smoke" / "s01.jsonl").is_file(), (
        "a session directory that is not a task was dropped from the feed"
    )


def test_superseded_keeps_the_real_session_beside_the_plant(fake_corpus, tmp_path):
    out = tmp_path / "out"
    assemble("superseded", 1, ["ts-base36-id"], out)
    present = sorted(p.name for p in (out / "sessions" / "ts-base36-id").glob("*.jsonl"))
    assert present == ["p01.jsonl", "stale_lowercase.jsonl"]


def test_a_selected_task_with_no_plan_is_refused(fake_corpus, tmp_path):
    """Silently keeping the true fact would score the cell as fact-present under a condition name
    that promises the opposite."""

    with pytest.raises(SystemExit, match="declares no 'absent' condition"):
        assemble("absent", 1, ["ts-casefold-sort"], tmp_path / "out")


def test_the_manifest_matches_the_bytes(fake_corpus, tmp_path):
    from harness.adapters.base import CorpusManifest

    out = tmp_path / "out"
    assemble("superseded", 1, ["ts-base36-id"], out)
    CorpusManifest.load(out).verify()


def test_rebuilding_a_condition_does_not_accumulate_stale_files(fake_corpus, tmp_path):
    out = tmp_path / "out"
    assemble("superseded", 1, ["ts-base36-id"], out)
    (out / "sessions" / "ts-base36-id" / "left_over.jsonl").write_text("{}\n", encoding="utf-8")
    assemble("superseded", 1, ["ts-base36-id"], out)
    assert not (out / "sessions" / "ts-base36-id" / "left_over.jsonl").exists()


# ---------------------------------------------------------------------------------------
# timestamps: the mitigation for "undated"
# ---------------------------------------------------------------------------------------


def test_a_restamped_session_is_written_with_the_same_line_endings_as_the_feed(tmp_path):
    """Mutation: dropping newline="\\n". On Windows the re-stamped memos become the only CRLF
    files among 125 LF ones, so they can chunk differently from the sessions they compete with,
    and the corpus hashes differently depending on where it was assembled."""

    from scripts.assemble_condition_corpus import _write_jsonl

    target = tmp_path / "memo.jsonl"
    _write_jsonl(target, [{"role": "user", "content": "one"}, {"role": "user", "content": "two"}])
    raw = target.read_bytes()
    assert b"\r\n" not in raw
    assert raw.count(b"\n") == 2

    corpus_sample = (
        Path(__file__).resolve().parents[1] / "corpus" / "sessions" / "ts-base36-id" / "p01.jsonl"
    )
    assert b"\r\n" not in corpus_sample.read_bytes(), "the base corpus is LF; this test assumes it"


def test_another_task_s_plant_is_inside_the_containment_net(tmp_path):
    """Mutation: dropping the plants/ sweep from outside_texts. Two plants could then share a
    wrong term, their damage rates would be dependent, and because the per-condition analysis
    clusters on the task the interval would be narrower than the evidence supports rather than
    visibly wrong."""

    from scripts.audit_plants import outside_texts

    root = tmp_path / "corpus"
    (root / "plants" / "ts-other").mkdir(parents=True)
    (root / "sessions" / "ts-other").mkdir(parents=True)
    (root / "distractors").mkdir(parents=True)
    theirs = root / "plants" / "ts-other" / "their_plant.jsonl"
    theirs.write_text('{"content": "emitted lowercase"}\n', encoding="utf-8")

    texts = outside_texts("ts-mine", tmp_path / "nonexistent", ["ts-mine", "ts-other"], root)
    assert theirs in texts, "another task's plant was not checked for term collisions"
    assert "emitted lowercase" in texts[theirs]


def test_restamp_moves_time_and_leaves_content_alone():
    lines = [
        {"role": "user", "content": "first", "ts": "2020-01-01T00:00:00Z"},
        {"role": "assistant", "content": "second", "ts": "2020-01-01T00:00:00Z"},
    ]
    moved = restamp(lines, "2026-05-06")
    assert [line["content"] for line in moved] == ["first", "second"]
    assert moved[0]["ts"] == "2026-05-06T09:00:00Z"
    assert moved[1]["ts"] == "2026-05-06T09:00:40Z"
    assert lines[0]["ts"] == "2020-01-01T00:00:00Z", "restamp must not mutate its input"


def test_which_contradictory_memo_is_newer_changes_with_the_seed():
    """THE assertion the contradictory condition rests on. Mutation: returning a constant mapping.
    Recording order then decides the tie in every seed, and a recency-weighted system is handed a
    constant answer instead of a coin flip."""

    from harness.plants import Plant

    pair = (Plant("memo_a", ("x",), ""), Plant("memo_b", ("y",), ""))
    orderings = {
        tuple(sorted(assign_contradiction_dates(pair, seed).items())) for seed in range(12)
    }
    assert len(orderings) > 1, "the permutation is constant across seeds"


def test_the_permutation_is_reproducible_from_the_seed():
    from harness.plants import Plant

    pair = (Plant("memo_a", ("x",), ""), Plant("memo_b", ("y",), ""))
    assert assign_contradiction_dates(pair, 7) == assign_contradiction_dates(pair, 7)
