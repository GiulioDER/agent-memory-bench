"""Safety proofs for the isolated trusted checker image and worker."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.checker_worker import CheckerRequestError, evaluate


def _bench(tmp_path: Path, checker_source: str) -> tuple[Path, Path, Path]:
    bench = tmp_path / "bench"
    task = bench / "tasks" / "ts-example"
    task.mkdir(parents=True)
    (task / "checker.py").write_text(checker_source, encoding="utf-8")
    artifact = tmp_path / "artifact"
    oracle = tmp_path / "oracle"
    artifact.mkdir()
    oracle.mkdir()
    return bench, artifact, oracle


def test_checker_worker_executes_only_the_named_bundled_checker(tmp_path: Path) -> None:
    """The worker must grade the mounted artifact against the mounted oracle."""
    bench, artifact, oracle = _bench(
        tmp_path,
        "from pathlib import Path\n"
        "def check(workdir: Path, oracle_dir: Path):\n"
        "    return ((workdir / 'answer.txt').read_text() == "
        "(oracle_dir / 'answer.txt').read_text(), 'compared')\n",
    )
    (artifact / "answer.txt").write_text("same", encoding="utf-8")
    (oracle / "answer.txt").write_text("same", encoding="utf-8")

    result = evaluate(
        {"task_id": "ts-example", "artifact": str(artifact), "oracle_root": str(oracle)},
        bench_root=bench,
        artifact_root=artifact,
        oracle_root=oracle,
    )

    assert result == {
        "checker_status": "completed",
        "ok": True,
        "verdict": "compared",
        "timed_out": False,
    }


def test_checker_worker_rejects_path_and_task_injection(tmp_path: Path) -> None:
    bench, artifact, oracle = _bench(
        tmp_path, "def check(workdir, oracle_dir): return True, 'ok'\n"
    )

    with pytest.raises(CheckerRequestError, match="artifact"):
        evaluate(
            {"task_id": "ts-example", "artifact": "/etc", "oracle_root": str(oracle)},
            bench_root=bench,
            artifact_root=artifact,
            oracle_root=oracle,
        )
    with pytest.raises(CheckerRequestError, match="task_id"):
        evaluate(
            {"task_id": "../escape", "artifact": str(artifact), "oracle_root": str(oracle)},
            bench_root=bench,
            artifact_root=artifact,
            oracle_root=oracle,
        )


def test_checker_worker_turns_deliverable_exceptions_into_failed_scores(tmp_path: Path) -> None:
    bench, artifact, oracle = _bench(
        tmp_path, "def check(workdir, oracle_dir): raise UnicodeError('bad artifact')\n"
    )

    result = evaluate(
        {"task_id": "ts-example", "artifact": str(artifact), "oracle_root": str(oracle)},
        bench_root=bench,
        artifact_root=artifact,
        oracle_root=oracle,
    )

    assert result["checker_status"] == "completed"
    assert result["ok"] is False
    assert result["timed_out"] is False
    assert result["verdict"] == "checker raised: UnicodeError: bad artifact"


def test_checker_image_contains_only_trusted_checker_runtime() -> None:
    dockerfile = (
        Path(__file__).parents[1] / "docker" / "Dockerfile.checker"
    ).read_text(encoding="utf-8")

    assert "COPY harness /bench/harness" in dockerfile
    assert "COPY tasks /bench/tasks" in dockerfile
    assert "COPY . /bench" not in dockerfile
    assert "@anthropic-ai/claude-code" not in dockerfile
    assert "USER 65532:65532" in dockerfile
