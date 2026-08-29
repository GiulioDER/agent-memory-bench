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
import traceback
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .sandbox import ORACLES, WORKSPACES

KINDS = ("primary", "control")

#: How a distributed governing fact is spread across the sessions that carry it.
#:
#: ``join``   two halves of one rule, recorded separately, both needed.
#: ``evolve`` one quantity revised across dated sessions; the latest is the only correct one.
#: ``widen``  one session carries the rule, a later one widens its scope without restating it.
#:
#: Every ``ts-*`` task states its whole fact in one session, which is why no result published so
#: far says anything about consolidation: a suite where combining sessions can never be necessary
#: cannot detect a product that combines them. These shapes exist so it can.
SYNTHESIS_SHAPES = ("join", "evolve", "widen")


@dataclass(frozen=True)
class FactShard:
    """One session's share of a distributed governing fact."""

    precursor: str
    session_date: str
    role: str
    terms: tuple[str, ...]


@dataclass(frozen=True)
class Synthesis:
    """A task whose governing fact no single session states.

    ``insufficient_references`` names the committed reference solutions that encode a PROPER
    SUBSET of the fact: one shard, or a superseded revision of it. CI asserts each of them fails
    the checker, which is the executable form of "no single session suffices". Without it the
    claim is a comment, and a task that quietly became solvable from one session would keep
    reporting itself as a synthesis task.
    """

    shape: str
    why: str
    shards: tuple[FactShard, ...]
    insufficient_references: tuple[str, ...]

    @property
    def precursors(self) -> tuple[str, ...]:
        return tuple(shard.precursor for shard in self.shards)


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    prompt: str
    kind: str
    fact_terms: tuple[str, ...]
    path: Path
    memory_bundle_id: str | None = None
    #: Present only on tasks whose governing fact is distributed across sessions.
    synthesis: Synthesis | None = field(default=None)

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
    fact_terms = tuple(str(term) for term in data.get("fact_terms", ()))
    return TaskSpec(
        task_id=task_id,
        prompt=prompt,
        kind=kind,
        fact_terms=fact_terms,
        path=path,
        memory_bundle_id=memory_bundle_id,
        synthesis=_load_synthesis(task_id, path, data.get("synthesis"), fact_terms),
    )


def _load_synthesis(
    task_id: str, path: Path, raw: object, fact_terms: tuple[str, ...]
) -> Synthesis | None:
    """Validate a distributed fact's declaration, or return None for an ordinary task.

    Everything here is checked at load time rather than in the audit, because a malformed
    declaration must never be able to reach a run: a shard list that does not match the recorded
    sessions turns "no single session suffices" into an unverified claim, and the sessions it
    names are what the corpus audit then reads.
    """

    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"{task_id}: synthesis must be an object")
    shape = str(raw.get("shape", ""))
    if shape not in SYNTHESIS_SHAPES:
        raise ValueError(f"{task_id}: synthesis.shape must be one of {SYNTHESIS_SHAPES}")
    why = str(raw.get("why", "")).strip()
    if not why:
        raise ValueError(f"{task_id}: synthesis.why must say what the split is and why")

    shards: list[FactShard] = []
    previous: date | None = None
    for entry in raw.get("shards", ()):
        precursor = str(entry["precursor"])
        if not (path / "precursors" / precursor).is_dir():
            raise FileNotFoundError(
                f"{task_id}: shard {precursor!r} has no staging under precursors/{precursor}/"
            )
        try:
            when = date.fromisoformat(str(entry["session_date"]))
        except ValueError as error:
            raise ValueError(f"{task_id}: shard {precursor!r} session_date: {error}") from None
        if previous is not None and when <= previous:
            # Order is load bearing for `evolve` (the last revision is the correct one) and it is
            # what the corpus audit compares when it checks that an earlier session cannot state
            # a later session's fact. Declaring them out of order would silently invert both.
            raise ValueError(
                f"{task_id}: shard session_dates must increase; {entry['session_date']} follows "
                f"{previous.isoformat()}"
            )
        previous = when
        terms = tuple(str(term) for term in entry.get("terms", ()))
        if not terms:
            raise ValueError(f"{task_id}: shard {precursor!r} declares no terms")
        unknown = [term for term in terms if term not in fact_terms]
        if unknown:
            raise ValueError(
                f"{task_id}: shard {precursor!r} terms {unknown} are not in fact_terms, so the "
                f"leakage audit never checks them"
            )
        shards.append(
            FactShard(
                precursor=precursor,
                session_date=str(entry["session_date"]),
                role=str(entry.get("role", "")).strip(),
                terms=terms,
            )
        )

    if len(shards) < 2:
        raise ValueError(f"{task_id}: a distributed fact needs at least two shards")
    if len({shard.precursor for shard in shards}) != len(shards):
        raise ValueError(f"{task_id}: two shards name the same precursor")
    covered = {term for shard in shards for term in shard.terms}
    orphans = [term for term in fact_terms if term not in covered]
    if orphans:
        raise ValueError(
            f"{task_id}: fact terms {orphans} belong to no shard; every term of a distributed "
            f"fact must say which session carries it"
        )

    references = tuple(str(name) for name in raw.get("insufficient_references", ()))
    if not references:
        raise ValueError(
            f"{task_id}: declare the reference solutions that must FAIL, or nothing proves the "
            f"fact is distributed"
        )
    for name in references:
        if not name.startswith("partial_"):
            raise ValueError(f"{task_id}: insufficient reference {name!r} must be named partial_*")
        if not (path / "reference" / f"{name}.py").is_file():
            raise FileNotFoundError(f"{task_id}: reference/{name}.py is missing")
    return Synthesis(shape=shape, why=why, shards=tuple(shards), insufficient_references=references)


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
    """Execute the task's checker against one finished sandbox.

    A checker that RAISES grades the session as a failure, with the traceback as its verdict. It
    does not propagate.

    The distinction matters because of where the exception used to land: `harness.runner` turned it
    into an error record, and `harness.gate` then discarded the cell for "the session did not
    complete" — taking every OTHER arm's paid session in that cell with it. The trigger is
    agent-controlled, which is what makes it a scoring hole rather than an infrastructure one:
    several checkers read an agent-written file with a strict UTF-8 decode (for example
    `tasks/ts-nfc-count/checker.py`), so an artifact written in cp1252 on Windows raised, and a
    task whose deliverable the grader cannot read is a task that was not solved. Scoring it as a
    discard let a bad deliverable delete the evidence for its own cell.

    A genuine harness fault (a missing checker file, a syntax error in one) still raises, because
    `_load_callable` runs outside this guard: that is a defect in the instrument, not an outcome,
    and it must stop the run rather than score every session as a failure.
    """

    check = _load_callable(task.checker_path, "check")
    try:
        result = check(Path(workdir), task.oracle_dir)
        ok, verdict = result
    except Exception as error:  # noqa: BLE001 - an unreadable deliverable is a failed task
        detail = "".join(traceback.format_exception_only(type(error), error)).strip()
        return False, f"checker raised: {detail}"
    return bool(ok), str(verdict)


def apply_reference(task: TaskSpec, variant: str, workdir: Path) -> None:
    """Apply one committed reference solution to a sandbox.

    ``naive`` and ``informed`` are the discrimination pair every task carries. A ``damaged_*``
    variant is the third leg, added for preregistration 005: a solution that retrieved a PLANTED
    WRONG fact and applied it. It exists so a damage detector can be watched firing on a sandbox
    whose damage is known by construction, exactly as the other two let the checker be watched
    failing and passing.

    A ``partial_*`` variant is the fourth, added with the cross-session synthesis tasks: a
    solution built from ONE shard of a distributed fact, or from a superseded revision of it. It
    must fail, and CI asserts that it does.
    """

    if variant not in ("naive", "informed") and not variant.startswith(("damaged_", "partial_")):
        raise ValueError(f"unknown reference variant {variant!r}")
    apply = _load_callable(task.reference_dir / f"{variant}.py", "apply")
    apply(Path(workdir))
