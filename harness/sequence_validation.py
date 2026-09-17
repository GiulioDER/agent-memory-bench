"""Validate a longitudinal plan against the task and leakage boundaries.

The sequence runner can enforce ordering, but it cannot know whether a plan names a real task,
silently changes a task prompt, or puts the source fact in a later fixture.  Those are design
errors rather than runtime outcomes, so they are rejected before the first model call.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .plants import normalise
from .sequence_plan import SequencePlan
from .tasks import TaskSpec, discover_tasks

ALLOWED_CHAIN_LENGTHS = (2, 4, 8)


@dataclass(frozen=True)
class SequencePlanValidation:
    """The checked plan dimensions, suitable for a preflight artifact."""

    plan_id: str
    chains: int
    chains_by_length: Mapping[int, int]
    task_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "chains": self.chains,
            "chains_by_length": dict(sorted(self.chains_by_length.items())),
            "task_ids": list(self.task_ids),
        }


def _visible_task_text(task: TaskSpec) -> str:
    """Return the text available in a task's prompt and fresh fixture.

    Oracle and reference files are deliberately excluded.  They are grader inputs, not material
    available to an agent in a fresh sandbox, and including them would reject legitimate plans
    merely because the checker names the hidden convention.
    """

    parts = [task.prompt]
    tree = task.path / "tree"
    for path in sorted(item for item in tree.rglob("*") if item.is_file()):
        parts.append(path.relative_to(tree).as_posix())
        parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return normalise(" ".join(parts))


def _shared_text(paths: Iterable[str | Path]) -> str:
    parts: list[str] = []
    for value in paths:
        path = Path(value)
        if not path.is_file():
            raise FileNotFoundError(f"sequence validation shared file does not exist: {path}")
        parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return normalise(" ".join(parts))


def sequence_input_files(
    plan: SequencePlan, *, repo_root: str | Path, tasks_root: str | Path
) -> tuple[str, ...]:
    """List task and oracle files whose bytes can affect a sequence evaluation.

    The ordinary corpus manifest does not include executable task fixtures. A longitudinal
    manifest must bind those inputs too, or changing a checker or fresh tree after freezing would
    change the evaluation while leaving the manifest digest untouched.
    """

    repository = Path(repo_root).resolve()
    tasks_directory = Path(tasks_root).resolve()
    try:
        tasks_directory.relative_to(repository)
    except ValueError as error:
        raise ValueError("tasks_root must be inside repo_root") from error

    tasks = {task.task_id: task for task in discover_tasks(tasks_directory)}
    task_ids = {session.task_id for chain in plan.chains for session in chain.sessions}
    missing = sorted(task_ids - set(tasks))
    if missing:
        raise ValueError(f"sequence plan names unknown task(s) {missing}")

    files: set[str] = set()

    def add_tree(root: Path) -> None:
        if not root.is_dir():
            raise FileNotFoundError(f"sequence evaluation input directory does not exist: {root}")
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            if "__pycache__" in path.parts:
                continue
            try:
                relative = path.resolve().relative_to(repository).as_posix()
            except ValueError as error:
                raise ValueError(f"sequence evaluation input escapes repo_root: {path}") from error
            files.add(relative)

    for task_id in sorted(task_ids):
        task = tasks[task_id]
        for path in (task.path / "task.json", task.checker_path):
            if not path.is_file():
                raise FileNotFoundError(f"sequence evaluation input file does not exist: {path}")
            files.add(path.resolve().relative_to(repository).as_posix())
        add_tree(task.path / "tree")
        add_tree(repository / "oracles" / task_id)
    return tuple(sorted(files))


def validate_plan(
    plan: SequencePlan,
    *,
    tasks_root: str | Path,
    shared_files: Iterable[str | Path] = (),
    expected_chains_per_length: int | None = None,
) -> SequencePlanValidation:
    """Reject an executable plan that violates the task or fact-locus contract.

    ``user_input`` is compared byte-for-byte after the task loader's normal trim.  The plan is
    therefore a frozen execution record, not a second place where a prompt can drift.  For each
    chain, every source fact term must be absent from later prompts, fixture trees, and the
    supplied shared instruction files.  A fact appearing in a distance fixture would also leak
    into the target through the fresh sandbox sequence and is refused for the same reason.
    """

    tasks = {task.task_id: task for task in discover_tasks(tasks_root)}
    shared = _shared_text(shared_files)
    errors: list[str] = []
    counts: dict[int, int] = {}
    referenced: set[str] = set()

    if expected_chains_per_length is not None and expected_chains_per_length < 1:
        raise ValueError("expected_chains_per_length must be positive")

    for chain in plan.chains:
        length = chain.length
        counts[length] = counts.get(length, 0) + 1
        if length not in ALLOWED_CHAIN_LENGTHS:
            errors.append(
                f"chain {chain.chain_id!r} has length {length}; allowed lengths are "
                f"{ALLOWED_CHAIN_LENGTHS}"
            )
        chain_tasks: list[TaskSpec] = []
        for session in chain.sessions:
            referenced.add(session.task_id)
            task = tasks.get(session.task_id)
            if task is None:
                errors.append(f"chain {chain.chain_id!r} names unknown task {session.task_id!r}")
                continue
            chain_tasks.append(task)
            if task.kind != "primary":
                errors.append(
                    f"chain {chain.chain_id!r}, position {session.position} uses non-primary "
                    f"task {task.task_id!r}"
                )
            if session.user_input != task.prompt:
                errors.append(
                    f"chain {chain.chain_id!r}, position {session.position} has a prompt that "
                    f"does not match tasks/{task.task_id}/task.json"
                )

        if not chain_tasks:
            continue
        source = chain_tasks[0]
        if not source.fact_terms:
            errors.append(
                f"chain {chain.chain_id!r} source task {source.task_id!r} declares no fact_terms"
            )
            continue
        later_text = " ".join(_visible_task_text(task) for task in chain_tasks[1:])
        for term in source.fact_terms:
            needle = normalise(term)
            if needle in later_text:
                errors.append(
                    f"chain {chain.chain_id!r} source fact term {term!r} leaks into a later "
                    "prompt or fixture"
                )
            if needle in shared:
                errors.append(
                    f"chain {chain.chain_id!r} source fact term {term!r} leaks into shared "
                    "instructions"
                )

    if expected_chains_per_length is not None:
        for length in ALLOWED_CHAIN_LENGTHS:
            actual = counts.get(length, 0)
            if actual != expected_chains_per_length:
                errors.append(
                    f"length {length} has {actual} chain(s), expected "
                    f"{expected_chains_per_length}"
                )

    if errors:
        raise ValueError("invalid longitudinal sequence plan:\n" + "\n".join(errors))
    return SequencePlanValidation(
        plan_id=plan.plan_id,
        chains=len(plan.chains),
        chains_by_length=dict(counts),
        task_ids=tuple(sorted(referenced)),
    )
