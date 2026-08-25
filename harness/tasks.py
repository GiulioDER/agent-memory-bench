"""Tasks as data: one directory per task, loadable without reading any Python.

    tasks/<task_id>/
        task.json            prompt, kind, fact terms (for the leakage audit)
        tree/  (+ dirty/)    the fixture, restored by harness.sandbox
        checker.py           check(workdir, oracle_dir) -> (bool, str)
        reference/naive.py   apply(workdir): the competent solution WITHOUT the fact; must fail
        reference/informed.py  apply(workdir): the solution WITH the fact; must pass
    oracles/<task_id>/       checker inputs the sandbox never contains

The two reference solutions are the task's discrimination evidence, asserted in CI for every
task: naive fails, informed passes, and a do-nothing sandbox fails. A task that cannot show
those three has no business costing agent sessions.
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path

from .sandbox import ORACLES, WORKSPACES

KINDS = ("primary", "control")


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    prompt: str
    kind: str
    fact_terms: tuple[str, ...]
    path: Path
    memory_bundle_id: str | None = None

    @property
    def checker_path(self) -> Path:
        return self.path / "checker.py"

    @property
    def reference_dir(self) -> Path:
        return self.path / "reference"

    @property
    def oracle_dir(self) -> Path:
        return ORACLES / self.task_id


def load_task(task_dir: str | Path) -> TaskSpec:
    path = Path(task_dir)
    data = json.loads((path / "task.json").read_text(encoding="utf-8"))
    task_id = str(data["task_id"])
    if task_id != path.name:
        raise ValueError(f"task.json says {task_id!r} but the directory is {path.name!r}")
    kind = str(data.get("kind", "primary"))
    if kind not in KINDS:
        raise ValueError(f"{task_id}: kind must be one of {KINDS}, got {kind!r}")
    prompt = str(data["prompt"]).strip()
    if not prompt:
        raise ValueError(f"{task_id}: prompt must not be empty")
    if not (path / "tree").is_dir():
        raise FileNotFoundError(f"{task_id}: fixture tree/ is missing")
    if not (path / "checker.py").is_file():
        raise FileNotFoundError(f"{task_id}: checker.py is missing")
    if "memory_bundle_id" not in data:
        memory_bundle_id = None if kind == "control" else f"bundle_{task_id}"
    else:
        raw_bundle = data["memory_bundle_id"]
        if raw_bundle is not None and not isinstance(raw_bundle, str):
            raise ValueError(f"{task_id}: memory_bundle_id must be a string or null")
        memory_bundle_id = raw_bundle
    if kind == "control" and "memory_bundle_id" not in data:
        raise ValueError(f"{task_id}: controls must explicitly declare memory_bundle_id: null")
    if kind == "control" and memory_bundle_id is not None:
        raise ValueError(f"{task_id}: controls must declare memory_bundle_id: null")
    return TaskSpec(
        task_id=task_id,
        prompt=prompt,
        kind=kind,
        fact_terms=tuple(str(term) for term in data.get("fact_terms", ())),
        path=path,
        memory_bundle_id=memory_bundle_id,
    )


def discover_tasks(root: str | Path = WORKSPACES) -> list[TaskSpec]:
    """Every directory under tasks/ that carries a task.json, sorted by id."""

    tasks = []
    for candidate in sorted(Path(root).iterdir()):
        if candidate.is_dir() and (candidate / "task.json").is_file():
            tasks.append(load_task(candidate))
    return tasks


def _load_callable(py_file: Path, name: str):
    spec = importlib.util.spec_from_file_location(
        f"_task_{py_file.parent.parent.name}_{py_file.stem}", py_file
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    func = getattr(module, name, None)
    if func is None:
        raise AttributeError(f"{py_file} defines no {name}()")
    return func


def run_checker(task: TaskSpec, workdir: Path) -> tuple[bool, str]:
    """Execute the task's checker against one finished sandbox."""

    check = _load_callable(task.checker_path, "check")
    result = check(Path(workdir), task.oracle_dir)
    ok, verdict = result
    return bool(ok), str(verdict)


def apply_reference(task: TaskSpec, variant: str, workdir: Path) -> None:
    """Apply one committed reference solution (``naive`` or ``informed``) to a sandbox."""

    if variant not in ("naive", "informed"):
        raise ValueError(f"unknown reference variant {variant!r}")
    apply = _load_callable(task.reference_dir / f"{variant}.py", "apply")
    apply(Path(workdir))
