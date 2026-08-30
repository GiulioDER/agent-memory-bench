"""An archive must be labelled before it holds anything, and must never merge into another.

`scripts/archive_partial.py` parks an interrupted condition under `results/archive/` so a run can
be resumed without mixing two attempts' sessions inside one condition. The archive's README is the
only thing standing between that directory and a reader treating it as a result. Its own words:
**"It is not a result and must never be reported as one."**

It used to be written AFTER two back-to-back `shutil.move` calls. Reproduced during the 2026-08-30
audit by making the second move raise: the archive held `results/` with no README, the work root
stayed in place, `moved` was never incremented so the summary line never printed, and the operator
was left in a state where `--resume` offers to re-run a condition that
`pilot._refuse_a_dirty_work_root` then refuses. An unlabelled directory full of run output is
exactly the outcome the README exists to prevent.

`destination.mkdir(exist_ok=True)` was the second half: `shutil.move` moves a source INTO an
existing directory, so a second archive landing in the same second nested inside the first as
`.../results/<run_id>-<condition>/` and overwrote its README.

The module's one hard guarantee is that nothing is ever deleted. These tests pin that too, because
the reordering below moves the work root first and a future edit could reach for `rmtree`.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


@pytest.fixture
def partial_run(tmp_path, monkeypatch):
    """One interrupted condition: records written, no admission.json, sandboxes still present."""

    from harness import sandbox
    from scripts import archive_partial

    results = tmp_path / "results"
    run_dir = results / "run-001-absent"
    run_dir.mkdir(parents=True)
    (run_dir / "records.jsonl").write_text(
        '{"task_id": "ts-a", "seed": 0, "arm": "bare"}\n'
        '{"task_id": "ts-a", "seed": 0, "arm": "recall"}\n',
        encoding="utf-8",
    )

    work_root = tmp_path / "work"
    work_dir = work_root / "run-001-absent"
    (work_dir / "ts-a").mkdir(parents=True)
    (work_dir / "ts-a" / "sandbox.txt").write_text("evidence", encoding="utf-8")

    monkeypatch.setattr(archive_partial, "REPO", tmp_path)
    monkeypatch.setattr(sandbox, "default_work_root", lambda: work_root)
    return archive_partial, tmp_path, run_dir, work_dir


def test_a_clean_archive_is_labelled_and_complete(partial_run):
    """Control. Two record lines, both halves moved, README present and stating the count."""

    mod, root, run_dir, work_dir = partial_run
    assert mod.archive("run-001", ["absent"], dry_run=False) == 0

    archives = list((root / "results" / "archive").iterdir())
    assert len(archives) == 1
    archive = archives[0]
    readme = (archive / "README.md").read_text(encoding="utf-8")
    assert "must never be reported as one" in readme
    assert "2 record(s)" in readme, "the README must state what it holds"
    assert (archive / "results" / "records.jsonl").is_file()
    assert (archive / "work" / "ts-a" / "sandbox.txt").is_file()
    assert not run_dir.exists() and not work_dir.exists()


def test_the_archive_is_labelled_even_when_a_move_fails(partial_run, monkeypatch):
    """RED before the fix: a failure between the two moves left an archive with no README.

    The README is the only thing distinguishing this directory from a published run.
    """

    mod, root, _run_dir, _work_dir = partial_run

    calls = {"n": 0}
    real_move = shutil.move

    def flaky_move(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("cross-device link failed")
        return real_move(src, dst)

    monkeypatch.setattr(mod.shutil, "move", flaky_move)
    with pytest.raises(OSError):
        mod.archive("run-001", ["absent"], dry_run=False)

    archive = next((root / "results" / "archive").iterdir())
    readme = archive / "README.md"
    assert readme.is_file(), (
        "the archive holds run output with nothing saying it is not a result"
    )
    assert "must never be reported as one" in readme.read_text(encoding="utf-8")


def test_a_second_archive_in_the_same_second_is_refused(partial_run, monkeypatch):
    """RED before the fix: `exist_ok=True` merged the second into the first and nested the run dir."""

    mod, root, _run_dir, _work_dir = partial_run
    collision = root / "results" / "archive" / "20260830T120000Z-run-001-absent"
    collision.mkdir(parents=True)
    (collision / "README.md").write_text("the FIRST archive's label", encoding="utf-8")
    monkeypatch.setattr(mod, "datetime", _FrozenClock)

    assert mod.archive("run-001", ["absent"], dry_run=False) == 0
    assert (collision / "README.md").read_text(encoding="utf-8") == "the FIRST archive's label", (
        "the existing archive's README was overwritten"
    )
    assert not (collision / "results" / "run-001-absent").exists(), "the run dir was nested inside"


def test_nothing_is_ever_deleted(partial_run):
    """The module's one hard guarantee, pinned at the source so a future edit cannot quietly drop it."""

    import inspect

    mod, _root, _run_dir, _work_dir = partial_run
    source = inspect.getsource(mod)
    for destructive in ("rmtree", "unlink", "os.remove"):
        assert destructive not in source, (
            f"archive_partial uses {destructive}; this script's whole contract is that an "
            f"interrupted condition is the only surviving trace of what the attempt did"
        )


class _FrozenClock:
    """A `datetime` stand-in whose `now()` always lands in the same second."""

    UTC = None

    @staticmethod
    def now(_tz=None):
        import datetime as _dt

        return _dt.datetime(2026, 8, 30, 12, 0, 0, tzinfo=_dt.UTC)
