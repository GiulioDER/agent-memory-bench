"""Validated plans for sequential longitudinal benchmark chains.

``harness.runner.run_grid`` is deliberately cell parallel. A longitudinal chain needs a different
execution boundary: sessions in one chain run in order and share one memory namespace, while
different chains may be scheduled independently. This module only validates and expands the plan;
it does not start a model or a vendor process.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PLAN_SCHEMA = 1
ALLOWED_ROLES = ("source", "distance", "target")


@dataclass(frozen=True)
class SequenceSession:
    task_id: str
    position: int
    length: int
    role: str
    user_input: str

    def row(self, *, chain_id: str, seed: int) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "seed": seed,
            "user_input": self.user_input,
            "sequence": {
                "chain_id": chain_id,
                "length": self.length,
                "position": self.position,
                "role": self.role,
                "admitted": True,
            },
        }


@dataclass(frozen=True)
class SequenceChain:
    chain_id: str
    seed: int
    sessions: tuple[SequenceSession, ...]

    @property
    def length(self) -> int:
        return len(self.sessions)

    def rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(session.row(chain_id=self.chain_id, seed=self.seed) for session in self.sessions)


@dataclass(frozen=True)
class SequencePlan:
    plan_id: str
    baseline_arm: str
    evaluation_manifest_id: str
    evaluation_manifest_digest: str
    arms: tuple[str, ...]
    chains: tuple[SequenceChain, ...]
    data: dict[str, Any]

    def rows(self) -> tuple[dict[str, Any], ...]:
        """Expand chains into runner rows in chain order.

        The rows carry runner owned sequence identity. A sequential executor must consume one
        chain's rows in order and must not pass all rows to ``run_grid`` as one parallel batch.
        """

        return tuple(row for chain in self.chains for row in chain.rows())


def _positive_int(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an int of at least {minimum}")
    return value


def _load_session(raw: Any, *, index: int, length: int) -> SequenceSession:
    if not isinstance(raw, dict):
        raise TypeError(f"sequence session {index} must be an object")
    task_id = str(raw.get("task_id", "")).strip()
    if not task_id:
        raise ValueError(f"sequence session {index} needs a task_id")
    position = _positive_int(raw.get("position"), f"sequence session {index}.position")
    if position >= length:
        raise ValueError(f"sequence session {index}.position must be below chain length")
    role = str(raw.get("role", ""))
    if role not in ALLOWED_ROLES:
        raise ValueError(f"sequence session {index}.role must be one of {ALLOWED_ROLES}")
    user_input = str(raw.get("user_input", "")).strip()
    if not user_input:
        raise ValueError(f"sequence session {index} needs user_input")
    return SequenceSession(task_id, position, length, role, user_input)


def load_plan(data: dict[str, Any]) -> SequencePlan:
    """Validate a longitudinal plan before any session is launched."""

    if data.get("schema") != PLAN_SCHEMA:
        raise ValueError(f"unsupported sequence plan schema {data.get('schema')!r}")
    plan_id = str(data.get("plan_id", "")).strip()
    if not plan_id:
        raise ValueError("sequence plan needs a plan_id")
    manifest_id = str(data.get("evaluation_manifest_id", "")).strip()
    manifest_digest = str(data.get("evaluation_manifest_digest", "")).strip()
    if not manifest_id:
        raise ValueError("sequence plan needs an evaluation_manifest_id")
    if not re.fullmatch(r"[0-9a-f]{64}", manifest_digest):
        raise ValueError("sequence plan needs a lowercase SHA256 evaluation_manifest_digest")
    arms_raw = data.get("arms")
    if isinstance(arms_raw, (str, bytes)) or not isinstance(arms_raw, list) or not arms_raw:
        raise ValueError("sequence plan arms must be a nonempty list")
    arms = tuple(str(arm).strip() for arm in arms_raw)
    if any(not arm for arm in arms) or len(set(arms)) != len(arms):
        raise ValueError("sequence plan arms must be nonempty and unique")
    baseline_arm = str(data.get("baseline_arm", "")).strip()
    if baseline_arm not in arms:
        raise ValueError("sequence plan baseline_arm must name one of its arms")

    chains_raw = data.get("chains")
    if isinstance(chains_raw, (str, bytes)) or not isinstance(chains_raw, list) or not chains_raw:
        raise ValueError("sequence plan chains must be a nonempty list")
    chains: list[SequenceChain] = []
    seen_chain_ids: set[str] = set()
    seen_cells: set[tuple[str, int]] = set()
    seen_task_cells: set[tuple[str, int]] = set()
    for chain_index, raw_chain in enumerate(chains_raw):
        if not isinstance(raw_chain, dict):
            raise TypeError(f"sequence chain {chain_index} must be an object")
        chain_id = str(raw_chain.get("chain_id", "")).strip()
        if not chain_id:
            raise ValueError(f"sequence chain {chain_index} needs a chain_id")
        if chain_id in seen_chain_ids:
            raise ValueError(f"sequence chain {chain_id!r} appears more than once")
        seen_chain_ids.add(chain_id)
        seed = _positive_int(raw_chain.get("seed"), f"sequence chain {chain_id}.seed")
        if (chain_id, seed) in seen_cells:
            raise ValueError(f"sequence chain {chain_id!r}, seed {seed} appears more than once")
        seen_cells.add((chain_id, seed))
        sessions_raw = raw_chain.get("sessions")
        if isinstance(sessions_raw, (str, bytes)) or not isinstance(sessions_raw, list):
            raise ValueError(  # noqa: TRY004 - malformed plans use one stable validation error
                f"sequence chain {chain_id!r}.sessions must be a list"
            )
        length = len(sessions_raw)
        if length < 2:
            raise ValueError(f"sequence chain {chain_id!r} needs at least two sessions")
        sessions = tuple(
            _load_session(raw, index=index, length=length)
            for index, raw in enumerate(sessions_raw)
        )
        positions = [session.position for session in sessions]
        if positions != list(range(length)):
            raise ValueError(f"sequence chain {chain_id!r} positions must be ordered 0 through {length - 1}")
        if sessions[0].role != "source" or sessions[-1].role != "target":
            raise ValueError(f"sequence chain {chain_id!r} must start with source and end with target")
        if any(session.role != "distance" for session in sessions[1:-1]):
            raise ValueError(f"sequence chain {chain_id!r} middle sessions must be distance sessions")
        if len({session.task_id for session in sessions}) != length:
            raise ValueError(f"sequence chain {chain_id!r} must use a distinct task per session")
        for session in sessions:
            task_cell = (session.task_id, seed)
            if task_cell in seen_task_cells:
                raise ValueError(
                    f"sequence plan reuses task {session.task_id!r} at seed {seed}; "
                    "each task and seed cell must belong to one chain"
                )
            seen_task_cells.add(task_cell)
        chains.append(SequenceChain(chain_id, seed, sessions))

    return SequencePlan(
        plan_id,
        baseline_arm,
        manifest_id,
        manifest_digest,
        arms,
        tuple(chains),
        dict(data),
    )


def load_plan_file(path: str | Path) -> SequencePlan:
    plan_path = Path(path)
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("sequence plan root must be a JSON object")
    return load_plan(data)
