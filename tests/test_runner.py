import asyncio

import pytest

from harness.frozen_manifest import FrozenEvaluationManifest
from harness.runner import run_grid, run_sequences
from harness.schema import SessionRecord
from harness.sequence_plan import load_plan


def _ok(row, arm):
    return SessionRecord(
        task_id=str(row["task_id"]), arm=arm, seed=int(row.get("seed", 0)), success=True
    )


def test_run_grid_runs_every_arm_for_every_cell():
    async def runner(row, arm):
        return _ok(row, arm)

    rows = [{"task_id": "t1", "seed": 0}, {"task_id": "t1", "seed": 1}]
    records = asyncio.run(run_grid(rows, ("bare", "claude_md", "recall"), runner))
    assert len(records) == 6
    assert {(r.task_id, r.seed, r.arm) for r in records} == {
        ("t1", 0, "bare"),
        ("t1", 0, "claude_md"),
        ("t1", 0, "recall"),
        ("t1", 1, "bare"),
        ("t1", 1, "claude_md"),
        ("t1", 1, "recall"),
    }


def test_runner_exception_becomes_error_record():
    async def runner(row, arm):
        if arm == "recall":
            raise RuntimeError("server died")
        return _ok(row, arm)

    records = asyncio.run(run_grid([{"task_id": "t1"}], ("bare", "recall"), runner))
    by_arm = {r.arm: r for r in records}
    assert by_arm["bare"].success
    assert not by_arm["recall"].success
    assert "server died" in by_arm["recall"].error


def test_sequence_metadata_survives_runner_success_and_failure():
    """Mutation: omitting row metadata from error records makes failed chain sessions unscorable."""

    sequence = {
        "chain_id": "chain-1",
        "length": 2,
        "position": 1,
        "role": "target",
        "admitted": True,
    }

    async def runner(row, arm):
        if arm == "recall":
            raise RuntimeError("memory unavailable")
        return _ok(row, arm)

    records = asyncio.run(
        run_grid([{"task_id": "target", "sequence": sequence}], ("bare", "recall"), runner)
    )
    by_arm = {record.arm: record for record in records}
    assert by_arm["bare"].metadata["sequence"] == sequence
    assert by_arm["recall"].metadata["sequence"] == {**sequence, "admitted": False}


def test_runner_marks_adapter_error_sequence_as_not_admitted():
    """Mutation: retaining admitted=true on an error would let a failed session enter scoring."""

    sequence = {
        "chain_id": "chain-1",
        "length": 2,
        "position": 1,
        "role": "target",
        "admitted": True,
    }

    async def runner(row, arm):
        return SessionRecord(
            task_id=str(row["task_id"]),
            arm=arm,
            seed=int(row.get("seed", 0)),
            success=False,
            error="adapter failed",
        )

    records = asyncio.run(
        run_grid([{"task_id": "target", "sequence": sequence}], ("recall",), runner)
    )
    assert records[0].metadata["sequence"]["admitted"] is False


def test_runner_cannot_replace_row_sequence_identity():
    sequence = {
        "chain_id": "chain-1",
        "length": 2,
        "position": 0,
        "role": "source",
        "admitted": True,
    }

    async def runner(row, arm):
        return SessionRecord(
            task_id=str(row["task_id"]),
            arm=arm,
            success=True,
            metadata={"sequence": {**sequence, "chain_id": "wrong-chain"}},
        )

    records = asyncio.run(
        run_grid([{"task_id": "source", "sequence": sequence}], ("bare",), runner)
    )
    assert records[0].error is not None
    assert "different chain session" in records[0].error


def test_run_sequences_completes_each_position_before_advancing(tmp_path):
    """Mutation: submitting every row at once would let a target run before its source finished."""

    plan = load_plan(
        {
            "schema": 1,
            "plan_id": "runner-sequence-test",
            "evaluation_manifest_id": "runner-sequence-manifest",
            "evaluation_manifest_digest": "0" * 64,
            "baseline_arm": "bare",
            "arms": ["bare", "recall"],
            "chains": [
                {
                    "chain_id": "c1",
                    "seed": 0,
                    "sessions": [
                        {"task_id": "source", "position": 0, "role": "source", "user_input": "learn"},
                        {"task_id": "distance", "position": 1, "role": "distance", "user_input": "wait"},
                        {"task_id": "target", "position": 2, "role": "target", "user_input": "apply"},
                    ],
                }
            ],
        }
    )
    corpus = tmp_path / "corpus.jsonl"
    protocol = tmp_path / "protocol.md"
    corpus.write_text("corpus\n", encoding="utf-8")
    protocol.write_text("protocol\n", encoding="utf-8")
    manifest = FrozenEvaluationManifest.build(
        tmp_path,
        manifest_id="runner-sequence-manifest",
        created_at="2026-09-17T12:00:00Z",
        corpus_files=["corpus.jsonl"],
        protocol_files=["protocol.md"],
    )
    plan = load_plan({**plan.data, "evaluation_manifest_digest": manifest.digest})
    observed: list[tuple[str, int, str]] = []

    async def runner(row, arm):
        observed.append((row["sequence"]["chain_id"], row["sequence"]["position"], arm))
        return _ok(row, arm)

    records = asyncio.run(run_sequences(plan, runner, heldout_manifest=manifest))
    assert len(records) == 6
    for arm in plan.arms:
        assert [position for _chain, position, observed_arm in observed if observed_arm == arm] == [0, 1, 2]


def test_run_sequences_verifies_manifest_before_starting_a_chain(tmp_path):
    """Mutation: removing manifest preflight lets a changed heldout corpus enter a measured run."""

    corpus = tmp_path / "corpus.jsonl"
    protocol = tmp_path / "protocol.md"
    corpus.write_text("original\n", encoding="utf-8")
    protocol.write_text("protocol\n", encoding="utf-8")
    manifest = FrozenEvaluationManifest.build(
        tmp_path,
        manifest_id="manifest-gate-test",
        created_at="2026-09-17T12:00:00Z",
        corpus_files=["corpus.jsonl"],
        protocol_files=["protocol.md"],
    )
    plan = load_plan(
        {
            "schema": 1,
            "plan_id": "manifest-gate-plan",
            "evaluation_manifest_id": "manifest-gate-test",
            "evaluation_manifest_digest": manifest.digest,
            "baseline_arm": "bare",
            "arms": ["bare"],
            "chains": [
                {
                    "chain_id": "c1",
                    "seed": 0,
                    "sessions": [
                        {"task_id": "source", "position": 0, "role": "source", "user_input": "learn"},
                        {"task_id": "target", "position": 1, "role": "target", "user_input": "apply"},
                    ],
                }
            ],
        }
    )
    corpus.write_text("changed\n", encoding="utf-8")
    started = False

    async def runner(row, arm):
        nonlocal started
        started = True
        return _ok(row, arm)

    with pytest.raises(ValueError, match="hashes to"):
        asyncio.run(run_sequences(plan, runner, heldout_manifest=manifest))
    assert not started


def test_runner_returning_wrong_cell_is_an_error_record():
    async def runner(row, arm):
        return SessionRecord(task_id="other", arm=arm, success=True)

    records = asyncio.run(run_grid([{"task_id": "t1"}], ("bare",), runner))
    assert records[0].error is not None


def test_duplicate_cells_are_refused():
    async def runner(row, arm):
        return _ok(row, arm)

    with pytest.raises(ValueError, match="unique"):
        asyncio.run(
            run_grid([{"task_id": "t1"}, {"task_id": "t1"}], ("bare",), runner)
        )


def test_duplicate_arms_are_refused():
    async def runner(row, arm):
        return _ok(row, arm)

    with pytest.raises(ValueError, match="arms must be unique"):
        asyncio.run(run_grid([{"task_id": "t1"}], ("bare", "bare"), runner))
