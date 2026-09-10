"""Regression tests for bounded checker process isolation."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups are not used on Windows")
def test_timeout_does_not_kill_the_harness_process_group() -> None:
    """A timed out checker must not terminate its caller on POSIX."""

    probe = """
import sys
import time
from pathlib import Path

from harness.checker_run import run_bounded

result = run_bounded(
    [sys.executable, "-c", "import time; time.sleep(30)"],
    cwd=Path.cwd(),
    timeout_s=0.05,
)
print(result.timed_out)
"""
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        start_new_session=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "True"


@pytest.mark.parametrize("timeout_s", [True, "nan", float("nan"), float("inf"), 0, -1])
def test_bounded_runner_rejects_non_finite_or_non_positive_timeout(tmp_path: Path, timeout_s) -> None:
    from harness.checker_run import run_bounded

    with pytest.raises(ValueError, match="finite and positive"):
        run_bounded([sys.executable, "-c", "pass"], cwd=tmp_path, timeout_s=timeout_s)


def test_bounded_runner_caps_retained_output(tmp_path: Path) -> None:
    from harness.checker_run import run_bounded
    from harness.process_capture import MAX_CAPTURE_CHARS, TRUNCATION_MARKER

    result = run_bounded(
        [sys.executable, "-c", "print('x' * 2000000)"],
        cwd=tmp_path,
        timeout_s=10,
    )
    assert len(result.stdout) <= MAX_CAPTURE_CHARS + len(TRUNCATION_MARKER)
    assert result.stdout.endswith(TRUNCATION_MARKER)
