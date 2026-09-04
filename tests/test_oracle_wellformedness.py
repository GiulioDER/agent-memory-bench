"""An oracle that lost its discriminating condition must be refused, not graded.

Four checkers derive what they EXPECT from the same oracle directory they hand the artifact.
That is self-consistent by construction, so thinning the oracle does not produce a mismatch: it
produces agreement. Measured 2026-09-01 before the guards landed, each of these scored the NAIVE
reference as a pass, with a verdict describing evidence it never saw:

    fa-dedup-key      "3 distinct orders, 3 expected, order preserved"
    ts-glob-hidden    "every file, hidden ones included, landed in the backup"
    ts-manifest-rel   "0 entries, root-relative POSIX keys, digests correct"
    ts-natural-order  "0 reports in numeric order, 9 before 10"

`tests/test_references.py` is the gate that would catch this, but only once the damage exists;
these tests pin the refusal itself, at the layer that has to make it. Each degradation removes
EXACTLY the property the task discriminates on and leaves the rest of the oracle intact, so a
guard that fired for some unrelated reason would not satisfy them.

The last test is the guard on the guard: a `_oracle_defect` that always returned a defect would
pass every case above while making the task unsolvable, so the real oracles are asserted clean.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from harness.sandbox import ORACLES, restore
from harness.tasks import apply_reference, load_task, run_checker

REPO = Path(__file__).resolve().parent.parent
IDENTITY = ("order_id", "sku", "qty")


def _oracle_defect(task_id: str):
    """The task's own guard, loaded from its checker."""

    path = REPO / "tasks" / task_id / "checker.py"
    spec = importlib.util.spec_from_file_location(f"_wf_{task_id}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._oracle_defect


def _drop_reports_past_nine(oracle: Path) -> None:
    """Numeric order then equals lexicographic order, so sorting the names is correct."""

    for path in (oracle / "reports").iterdir():
        if len(path.stem.split("-")[1]) > 1:
            path.unlink()


def _drop_hidden_files(oracle: Path) -> None:
    """A glob-based walk then copies every file there is, so the backup is complete."""

    project = oracle / "project"
    for path in sorted(project.rglob("*"), reverse=True):
        if any(part.startswith(".") for part in path.relative_to(project).parts):
            path.unlink() if path.is_file() else shutil.rmtree(path, ignore_errors=True)


def _empty_release_tree(oracle: Path) -> None:
    """Manifest and expectation are then both empty, so any key convention compares equal."""

    for path in (oracle / "release").rglob("*"):
        if path.is_file():
            path.unlink()


def _keep_one_supplier(oracle: Path) -> None:
    """No id is reused across files, so keying on order_id alone loses nothing."""

    for path in sorted((oracle / "orders").glob("*.jsonl"))[1:]:
        path.unlink()


def _drop_redeliveries(oracle: Path) -> None:
    """No order arrives twice, so keying on the WHOLE record duplicates nothing.

    The cross-supplier id reuse is left in place, which is what makes this a test of the second
    branch rather than a second way of tripping the first.
    """

    for path in sorted((oracle / "orders").glob("*.jsonl")):
        seen: set[tuple] = set()
        kept: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            key = tuple(json.loads(line).get(field) for field in IDENTITY)
            if key in seen:
                continue
            seen.add(key)
            kept.append(line)
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")


DEGRADATIONS = [
    ("ts-natural-order", _drop_reports_past_nine, "reports past nine removed"),
    ("ts-glob-hidden", _drop_hidden_files, "hidden files removed"),
    ("ts-manifest-rel", _empty_release_tree, "release tree emptied"),
    ("fa-dedup-key", _keep_one_supplier, "one supplier file left"),
    ("fa-dedup-key", _drop_redeliveries, "redeliveries removed"),
]

GUARDED = sorted({task_id for task_id, _degrade, _label in DEGRADATIONS})


@pytest.mark.parametrize(
    ("task_id", "degrade", "label"),
    DEGRADATIONS,
    ids=[f"{task_id}:{label}" for task_id, _degrade, label in DEGRADATIONS],
)
def test_a_degraded_oracle_is_refused(task_id, degrade, label, tmp_path, monkeypatch):
    """A checker must name the instrument once its oracle stops discriminating.

    Both assertions earn their place. `not ok` is the one that would have caught the measured
    false passes; the verdict assertion is what distinguishes a refusal for the RIGHT reason from
    a task that happens to fail for another. The `redeliveries removed` case shows why: the naive
    reference still fails there on the id reuse, and only the verdict shows that the second wrong
    answer, which has no committed reference, has stopped being caught.
    """

    oracles = tmp_path / "oracles"
    oracles.mkdir()
    shutil.copytree(ORACLES / task_id, oracles / task_id)
    degrade(oracles / task_id)
    # `TaskSpec.oracle_dir` reads this at call time, so the real checker and the real run_checker
    # are exercised rather than a hand-rolled stand-in.
    monkeypatch.setattr("harness.tasks.ORACLES", oracles)

    task = load_task(REPO / "tasks" / task_id)
    assert task.oracle_dir == oracles / task_id

    workdir = tmp_path / "sandbox"
    restore(task_id, workdir, allow_in_repo=True)
    apply_reference(task, "naive", workdir)
    ok, verdict = run_checker(task, workdir)

    assert not ok, f"{task_id} ({label}): the naive solution passed a degraded oracle: {verdict}"
    assert "oracle is not well formed" in verdict, (
        f"{task_id} ({label}): refused, but not as an instrument fault: {verdict}"
    )


@pytest.mark.parametrize("task_id", GUARDED)
def test_the_committed_oracle_is_well_formed(task_id):
    """The guard must be silent on the real oracle, or it would make the task unsolvable."""

    defect = _oracle_defect(task_id)(ORACLES / task_id)
    assert defect is None, f"{task_id}: the committed oracle is refused by its own guard: {defect}"
