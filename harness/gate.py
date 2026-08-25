"""The admission gate: proof that each arm's treatment was applied, before anything is measured.

This module generalises a gate that exists because of a specific, reproduced failure in the
ancestor harness (recall's ``benchmarks/agent_ab/gate.py``). A session was launched with
``--mcp-config`` pointing at a memory server that needed 13 seconds to start, on a CLI one
version below the release that waits for a pending MCP server. The session ran with **no memory
tool at all**, the model answered from its own knowledge, and the run reported::

    "subtype": "success", "is_error": false, "permission_denials": [], "num_turns": 1

Nothing in the exit status, token counts, wall time or response distinguishes that from a genuine
memory-arm result. It is a null manufactured by a wiring fault, and averaged into a summary it
looks like evidence that the memory layer does nothing.

So the rule is: **a grid cell that cannot prove every arm's treatment was applied is discarded,
not recorded.** Discarding is not scoring zero, and the discarded count is published beside the
result, because a gate that quietly drops half the run is its own kind of lie.

## Available is the gate; used is a finding

The gate requires an arm's memory surface to be **present** (MCP tools listed in ``system/init``,
lifecycle hooks demonstrably fired, sandbox files in place). It does not require the agent to
have *used* it. Those are different facts:

- Surface absent  -> wiring failure. The experiment did not happen. Discard.
- Surface present, never used -> a real behavioural result about discoverability. Counted.

## N arms, three kinds of admission signal

Every adapter declares an :class:`AdmissionSignal`, and the registry computes each arm's
``forbidden_prefixes`` as the union of every *other* arm's tool prefixes, so cross-arm
contamination (arm A somehow holding arm B's tools) is checked mechanically rather than by
remembering to.

- **MCP arms** (recall, zep, cognee, supermemory): tool prefixes must appear in the session's
  tool list and every configured MCP server must be connected.
- **Hook arms** (mem0, and recall's lifecycle half): the adapter wraps each vendor hook command
  in a logging shim; admission requires the ledger to show the required events ran with exit 0
  and nonempty output. The shim is part of the frozen, vendor-reviewed config.
- **Static arms** (claude_md, fs_grep): the prompt-file hash and/or sandbox paths must match
  what the adapter built; for ``bare``, all checks are negative.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from .schema import SessionRecord

#: MCP server statuses that mean the server is usable. Anything else, including the ``pending``
#: that produced the failure described above, is treated as absent.
CONNECTED_STATUSES = frozenset({"connected", "ready"})


@dataclass(frozen=True)
class AdmissionSignal:
    """What one arm must prove before its sessions are admissible evidence.

    ``forbidden_prefixes`` is normally left empty by the adapter and filled by
    :func:`with_forbidden_prefixes`, which knows the whole arm roster.
    """

    arm: str
    mcp_tool_prefixes: tuple[str, ...] = ()
    required_hooks: tuple[str, ...] = ()
    sandbox_paths: tuple[str, ...] = ()
    prompt_sha256: str | None = None
    forbidden_prefixes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


def with_forbidden_prefixes(
    signals: Mapping[str, AdmissionSignal],
) -> dict[str, AdmissionSignal]:
    """Fill each arm's ``forbidden_prefixes`` with every other arm's tool prefixes.

    A prefix an arm claims for itself is never forbidden to it, even if another arm also claims
    it; two arms claiming the same prefix is a roster error and is refused outright, because a
    shared prefix would make the two arms indistinguishable to the gate.
    """

    claimed: dict[str, str] = {}
    for name, signal in signals.items():
        if name != signal.arm:
            raise ValueError(f"signal for {name!r} names arm {signal.arm!r}")
        for prefix in signal.mcp_tool_prefixes:
            if prefix in claimed and claimed[prefix] != name:
                raise ValueError(
                    f"tool prefix {prefix!r} is claimed by both {claimed[prefix]!r} and "
                    f"{name!r}; the gate cannot tell those arms apart"
                )
            claimed[prefix] = name

    filled: dict[str, AdmissionSignal] = {}
    for name, signal in signals.items():
        others = tuple(
            sorted(
                prefix
                for other, other_signal in signals.items()
                if other != name
                for prefix in other_signal.mcp_tool_prefixes
            )
        )
        filled[name] = replace(signal, forbidden_prefixes=others)
    return filled


@dataclass(frozen=True)
class AdmissionVerdict:
    """Why one session is or is not admissible evidence."""

    task_id: str
    seed: int
    arm: str
    admitted: bool
    reasons: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _session_tools(record: SessionRecord) -> list[str]:
    available = record.metadata.get("memory_tools_available")
    if isinstance(available, Sequence) and not isinstance(available, (str, bytes)):
        return [str(name) for name in available]
    tools = record.metadata.get("session_tools")
    if isinstance(tools, Sequence) and not isinstance(tools, (str, bytes)):
        return [str(name) for name in tools]
    return []


def _matching(tools: Iterable[str], prefix: str) -> list[str]:
    return [name for name in tools if name.startswith(prefix)]


#: Public aliases, so `harness.memory_startup` can apply the gate's OWN predicate rather than
#: a second copy of it. A retry rule that disagreed with the admission rule would either retry
#: sessions the gate would have admitted, or leave discarded ones unretried, and either way the
#: discard count would stop describing the run.
session_tools = _session_tools
matching_tools = _matching


def _ledger_events(record: SessionRecord) -> dict[str, dict[str, Any]]:
    events: dict[str, dict[str, Any]] = {}
    for entry in record.hook_ledger:
        event = str(entry.get("event", ""))
        if event and event not in events:
            events[event] = dict(entry)
    return events


def _check_diagnostic(record: SessionRecord, signal: AdmissionSignal, reasons: list[str]) -> None:
    expected = signal.metadata.get("diagnostic_kind")
    diagnostic = record.metadata.get("memory_diagnostic")
    if diagnostic is not None and not isinstance(diagnostic, Mapping):
        reasons.append("diagnostic metadata is malformed")
        return
    actual = diagnostic.get("kind") if isinstance(diagnostic, Mapping) else None
    if expected is None:
        if diagnostic is not None:
            reasons.append("non diagnostic arm contains diagnostic memory metadata")
        return
    if actual != expected:
        reasons.append(
            f"diagnostic arm {signal.arm!r} expected memory treatment {expected!r}, got {actual!r}"
        )
        return
    if expected == "oracle_memory":
        if diagnostic.get("task_id") != record.task_id:
            reasons.append("oracle injection task identity does not match the session task")
        expected_catalog = signal.metadata.get("catalog_sha256")
        if expected_catalog is not None and diagnostic.get("catalog_sha256") != expected_catalog:
            reasons.append("oracle injection catalog digest mismatch")
        expected_bundles = signal.metadata.get("bundle_digests")
        if isinstance(expected_bundles, Mapping):
            expected_bundle = expected_bundles.get(record.task_id)
            if expected_bundle is not None and diagnostic.get("bundle_sha256") != expected_bundle:
                reasons.append("oracle injection bundle digest mismatch")
        if not diagnostic.get("bundle_sha256") and diagnostic.get("bundle_id") is not None:
            reasons.append("oracle injection missing bundle digest")
        if not diagnostic.get("injected_text_sha256"):
            reasons.append("oracle injection missing injected text hash")
        if diagnostic.get("status") not in ("ok", "empty"):
            reasons.append("oracle injection malformed")
    if expected == "recall_prefetch":
        if diagnostic.get("prefetch_status") != "ok":
            reasons.append("prefetch failed")
        if not diagnostic.get("query_sha256") or not diagnostic.get("result_sha256"):
            reasons.append("prefetch record is malformed")


def check_session(record: SessionRecord, signal: AdmissionSignal) -> AdmissionVerdict:
    """Decide whether one session is admissible evidence for its arm."""

    if record.arm != signal.arm:
        raise ValueError(
            f"record for arm {record.arm!r} checked against signal for {signal.arm!r}"
        )

    reasons: list[str] = []
    notes: list[str] = []

    _check_diagnostic(record, signal, reasons)

    if not record.metadata.get("init_present", True):
        reasons.append(
            "no system/init event: the session's real tool surface was never observed, so "
            "the arm cannot be verified"
        )

    tools = _session_tools(record)
    servers = record.metadata.get("mcp_servers")
    servers = servers if isinstance(servers, Sequence) and not isinstance(servers, str) else []
    server_errors = record.metadata.get("mcp_server_errors")
    server_errors = (
        server_errors
        if isinstance(server_errors, Sequence) and not isinstance(server_errors, str)
        else []
    )

    for prefix in signal.mcp_tool_prefixes:
        if not _matching(tools, prefix):
            unhealthy = [
                f"{item.get('name')}={item.get('status')}"
                for item in servers
                if isinstance(item, Mapping)
                and str(item.get("status", "")).lower() not in CONNECTED_STATUSES
            ]
            detail = f"; servers reported {unhealthy}" if unhealthy else ""
            reasons.append(
                f"arm {signal.arm!r} had no tool matching {prefix!r} in its session tool "
                f"list, so its memory layer was never available{detail}"
            )
    if signal.mcp_tool_prefixes:
        if server_errors:
            reasons.append(f"MCP servers were skipped at startup: {list(server_errors)}")
        for item in servers:
            if not isinstance(item, Mapping):
                continue
            status = str(item.get("status", "")).lower()
            if status not in CONNECTED_STATUSES:
                reasons.append(f"MCP server {item.get('name')!r} was {status!r}, not connected")

    for prefix in signal.forbidden_prefixes:
        held = _matching(tools, prefix)
        if held:
            reasons.append(
                f"arm {signal.arm!r} held another arm's tools ({held}), so the arms differ "
                f"by less than the experiment claims"
            )
        called = [
            call
            for call in record.tool_calls
            if str(call.get("name", "")).startswith(prefix)
        ]
        if called:
            reasons.append(
                f"arm {signal.arm!r} recorded {len(called)} call(s) to another arm's tools "
                f"under {prefix!r}"
            )

    if signal.required_hooks:
        events = _ledger_events(record)
        for hook in signal.required_hooks:
            entry = events.get(hook)
            if entry is None:
                reasons.append(
                    f"required lifecycle hook {hook!r} never appeared in the hook ledger, so "
                    f"the integration cannot be shown to have run"
                )
                continue
            exit_code = entry.get("exit_code")
            if exit_code != 0:
                reasons.append(f"lifecycle hook {hook!r} exited {exit_code!r}, not 0")
            if not entry.get("output_sha256"):
                reasons.append(
                    f"lifecycle hook {hook!r} produced no output; an empty injection is "
                    f"indistinguishable from the hook not running"
                )

    if signal.sandbox_paths:
        present = record.metadata.get("sandbox_paths_present")
        present = (
            {str(item) for item in present}
            if isinstance(present, Sequence) and not isinstance(present, (str, bytes))
            else set()
        )
        for path in signal.sandbox_paths:
            if path not in present:
                reasons.append(
                    f"sandbox path {path!r} required by arm {signal.arm!r} was not recorded "
                    f"as present at session start"
                )

    expected_prompt_sha256 = signal.prompt_sha256
    prompt_hashes = signal.metadata.get("prompt_sha256_by_task")
    if isinstance(prompt_hashes, Mapping):
        expected_prompt_sha256 = prompt_hashes.get(record.task_id)
    if expected_prompt_sha256 is not None:
        actual = record.metadata.get("prompt_sha256")
        if actual != expected_prompt_sha256:
            reasons.append(
                f"system prompt hash {actual!r} does not match the arm's frozen prompt "
                f"{expected_prompt_sha256!r}"
            )

    has_memory_surface = bool(
        signal.mcp_tool_prefixes or signal.required_hooks or signal.sandbox_paths
    )
    if not reasons and has_memory_surface and record.memory_call_count == 0:
        # Deliberately a note, not a reason. See the module docstring.
        notes.append(
            "the memory layer was available and never called: a behavioural result about "
            "discoverability, not a wiring failure, and it is counted in the summary"
        )

    if record.error is not None:
        reasons.append(f"the session did not complete: {record.error}")

    return AdmissionVerdict(
        task_id=record.task_id,
        seed=record.seed,
        arm=record.arm,
        admitted=not reasons,
        reasons=tuple(reasons),
        notes=tuple(notes),
    )


@dataclass(frozen=True)
class AdmissionReport:
    """The admitted records, and a full account of everything dropped."""

    admitted: tuple[SessionRecord, ...]
    verdicts: tuple[AdmissionVerdict, ...]
    discarded_cells: tuple[tuple[str, int], ...]
    required_arms: tuple[str, ...]

    @property
    def admitted_cell_count(self) -> int:
        if not self.required_arms:
            return 0
        return len(self.admitted) // len(self.required_arms)

    def discarded_by_arm(self) -> dict[str, int]:
        """How many discards each arm caused. Published beside the result, per arm."""

        counts: dict[str, int] = {}
        for verdict in self.verdicts:
            if not verdict.admitted:
                counts[verdict.arm] = counts.get(verdict.arm, 0) + 1
        return counts

    def summary(self) -> dict[str, Any]:
        """A JSON-safe account, for the run artifact."""

        return {
            "required_arms": list(self.required_arms),
            "admitted_cells": self.admitted_cell_count,
            "discarded_cells": [list(cell) for cell in self.discarded_cells],
            "discarded_by_arm": self.discarded_by_arm(),
            "verdicts": [verdict.to_dict() for verdict in self.verdicts],
        }


def admit_cells(
    records: Iterable[SessionRecord],
    signals: Mapping[str, AdmissionSignal],
    *,
    required_arms: Sequence[str],
) -> AdmissionReport:
    """Keep only the (task, seed) cells where every required arm is admissible evidence.

    The cell is the unit, not the session: an admitted arm is useless without the arms it is
    compared against, and admitting it alone would quietly turn a paired design into an
    unpaired one partway through the grid. For a contrast over a subset of arms (one flaky
    arm must not discard seven others' data), call this again with that subset as
    ``required_arms``; the per-contrast report is the published one for that contrast.
    """

    required = tuple(required_arms)
    if not required:
        raise ValueError("required_arms must not be empty")
    missing_signals = [arm for arm in required if arm not in signals]
    if missing_signals:
        raise ValueError(f"no AdmissionSignal for arms {missing_signals}")

    by_cell: dict[tuple[str, int], dict[str, SessionRecord]] = defaultdict(dict)
    ordered_cells: list[tuple[str, int]] = []
    for record in records:
        if record.cell not in by_cell:
            ordered_cells.append(record.cell)
        if record.arm in by_cell[record.cell]:
            raise ValueError(
                f"duplicate record for arm {record.arm!r} in cell {record.cell!r}; a grid "
                f"with two records for one cell cannot be admitted deterministically"
            )
        by_cell[record.cell][record.arm] = record

    admitted: list[SessionRecord] = []
    verdicts: list[AdmissionVerdict] = []
    discarded: list[tuple[str, int]] = []
    for cell in ordered_cells:
        arms = by_cell[cell]
        cell_verdicts: list[AdmissionVerdict] = []
        for arm in required:
            record = arms.get(arm)
            if record is None:
                cell_verdicts.append(
                    AdmissionVerdict(
                        task_id=cell[0],
                        seed=cell[1],
                        arm=arm,
                        admitted=False,
                        reasons=(f"no {arm!r} record for this cell",),
                    )
                )
                continue
            cell_verdicts.append(check_session(record, signals[arm]))
        verdicts.extend(cell_verdicts)
        if all(verdict.admitted for verdict in cell_verdicts):
            admitted.extend(arms[arm] for arm in required)
        else:
            discarded.append(cell)

    return AdmissionReport(
        admitted=tuple(admitted),
        verdicts=tuple(verdicts),
        discarded_cells=tuple(discarded),
        required_arms=required,
    )
