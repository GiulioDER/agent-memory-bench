"""The gate for tasks whose governing fact no single session states.

Three claims are asserted here, and the first is the one the whole task class rests on:

1. **No single shard suffices.** Every reference named in `insufficient_references` is a real
   solution built from one session's share of the fact, or from a superseded revision of it, and
   every one of them FAILS the checker. `naive` and `informed` (asserted in `test_references.py`)
   say the task discriminates on the fact; these say the fact is genuinely distributed. Without
   them a task could quietly become solvable from one session and keep reporting itself as a
   synthesis task, which is worse than not having the class at all: it would look like evidence
   that consolidation was measured.
2. **Every shard is stageable.** Each shard names a `precursors/<name>/` staging with a prompt
   and a followup, because a shard with no staging is a session nobody can record.
3. **The followup states its own shard and only its own shard.** The recorder's validity gate
   checks fact terms against the transcript, and a term that spans a line break in `followup.txt`
   fails that check at recording time, after the tokens are spent. It is free to check here.

Why this class exists at all is in `docs/CROSS_SESSION_SYNTHESIS.md`. The short version: all 30
`ts-*` tasks put one discrete fact in one document, which is retrieval's best case and gives a
product that extracts and consolidates at write time no way to win and every way to lose.
"""

from __future__ import annotations

import json

import pytest

from scripts.audit_corpus import audit_shards
from scripts.record_precursor import _required_terms

from harness.sandbox import restore
from harness.tasks import SYNTHESIS_SHAPES, apply_reference, discover_tasks, run_checker

SYNTHESIS_TASKS = [task for task in discover_tasks() if task.synthesis is not None]

INSUFFICIENT = [
    (task, name)
    for task in SYNTHESIS_TASKS
    for name in task.synthesis.insufficient_references
]


def _ids(tasks):
    return [task.task_id for task in tasks]


def test_the_suite_has_synthesis_tasks_at_all():
    """The audit asked for at least three. Below three there is no class, only an anecdote."""

    assert len(SYNTHESIS_TASKS) >= 3, (
        "a suite where consolidation can never win cannot detect a consolidation product working"
    )
    shapes = {task.synthesis.shape for task in SYNTHESIS_TASKS}
    assert shapes == set(SYNTHESIS_SHAPES), (
        f"every distributed shape must be represented; missing {set(SYNTHESIS_SHAPES) - shapes}"
    )


@pytest.mark.parametrize(
    ("task", "variant"),
    INSUFFICIENT,
    ids=[f"{task.task_id}-{variant}" for task, variant in INSUFFICIENT],
)
def test_one_shard_is_not_enough(task, variant, tmp_path):
    workdir = tmp_path / "sandbox"
    restore(task.task_id, workdir)
    apply_reference(task, variant, workdir)
    ok, verdict = run_checker(task, workdir)
    assert not ok, (
        f"{task.task_id}: {variant} passed ({verdict}). One session's share of the fact solves "
        f"the task, so it is not distributed and must not be counted as a synthesis task"
    )


@pytest.mark.parametrize("task", SYNTHESIS_TASKS, ids=_ids(SYNTHESIS_TASKS))
def test_every_shard_has_a_recordable_staging(task):
    for shard in task.synthesis.shards:
        staging = task.path / "precursors" / shard.precursor
        for name in ("prompt.txt", "followup.txt"):
            path = staging / name
            assert path.is_file(), f"{task.task_id}: {shard.precursor} has no {name}"
            assert path.read_text(encoding="utf-8").strip(), f"{task.task_id}: {path} is empty"


@pytest.mark.parametrize("task", SYNTHESIS_TASKS, ids=_ids(SYNTHESIS_TASKS))
def test_each_followup_states_its_own_terms_on_one_line(task):
    """`scripts/record_precursor.py` matches terms against the JSONL transcript, where a line
    break inside a message is an escaped newline that no normalisation collapses. A term wrapped
    across two lines here fails the recording after the session has been paid for."""

    for shard in task.synthesis.shards:
        followup = (task.path / "precursors" / shard.precursor / "followup.txt").read_text(
            encoding="utf-8"
        )
        lines = [line.lower() for line in followup.splitlines()]
        for term in shard.terms:
            assert any(term.lower() in line for line in lines), (
                f"{task.task_id}/{shard.precursor}: followup.txt does not state {term!r} on a "
                f"single line; the recorder would reject the recording"
            )


@pytest.mark.parametrize("task", SYNTHESIS_TASKS, ids=_ids(SYNTHESIS_TASKS))
def test_no_shard_terms_are_shared_between_shards(task):
    """Shard vocabularies must be disjoint, or the corpus audit cannot tell "this session states
    its own half" from "this session states both halves"."""

    seen: dict[str, str] = {}
    for shard in task.synthesis.shards:
        for term in shard.terms:
            if term in seen:
                raise AssertionError(
                    f"{task.task_id}: {term!r} is claimed by both {seen[term]} and "
                    f"{shard.precursor}"
                )
            seen[term] = shard.precursor


def _task(task_id: str):
    return next(task for task in SYNTHESIS_TASKS if task.task_id == task_id)


def _write_session(root, task_id: str, precursor: str, text: str) -> None:
    directory = root / task_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{precursor}.jsonl").write_text(
        json.dumps({"role": "user", "content": text, "ts": "2026-05-19T09:00:00Z"}) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def test_the_shard_audit_catches_a_session_holding_both_halves(tmp_path):
    """The guard for the guard. `audit_corpus` is the only thing standing between "distributed"
    as a design claim and "distributed" as a checked property, and it can only be trusted if it
    has been watched failing on a corpus that is known to be wrong."""

    task = _task("xs-join-batch")
    first, second = task.synthesis.shards[0], task.synthesis.shards[1]
    _write_session(
        tmp_path, task.task_id, first.precursor, f"{first.terms[0]} and also {second.terms[0]}"
    )
    _write_session(tmp_path, task.task_id, second.precursor, second.terms[0])

    violations, recorded = audit_shards(task, tmp_path, {})

    assert recorded == 2
    assert any(second.terms[0] in violation for violation in violations), violations


def test_a_later_revision_may_refer_back_and_an_earlier_one_may_not(tmp_path):
    """`evolve` is the one shape where a session legitimately mentions another's share: the
    session that supersedes a value names the value it is replacing. The reverse is impossible,
    and a corpus where it happens has had its dates or its recordings mixed up."""

    task = _task("xs-evolve-lease")
    old, middle, current = task.synthesis.shards
    _write_session(tmp_path, task.task_id, old.precursor, " ".join(old.terms))
    _write_session(tmp_path, task.task_id, middle.precursor, " ".join(middle.terms))
    _write_session(
        tmp_path,
        task.task_id,
        current.precursor,
        f"{' '.join(current.terms)}, replacing {old.terms[0]}",
    )
    assert audit_shards(task, tmp_path, {})[0] == []

    _write_session(
        tmp_path, task.task_id, old.precursor, f"{old.terms[0]} but soon {current.terms[0]}"
    )
    violations = audit_shards(task, tmp_path, {})[0]
    assert any(current.terms[0] in violation for violation in violations), violations


@pytest.mark.parametrize("task", SYNTHESIS_TASKS, ids=_ids(SYNTHESIS_TASKS))
def test_the_recorder_asks_each_session_for_its_own_share_only(task):
    """Demanding every fact term of every session, as the recorder did before this class existed,
    would refuse every valid recording of a distributed fact. The fix under deadline pressure is
    to record both halves in one session, which silently deletes the property being tested."""

    for shard in task.synthesis.shards:
        required, scope = _required_terms(task, shard.precursor)
        assert required == shard.terms
        assert shard.precursor in scope
