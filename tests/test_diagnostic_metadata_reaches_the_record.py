"""A diagnostic arm's `memory_diagnostic` must reach the session record.

`harness.gate._check_diagnostic` compares the adapter's `AdmissionSignal.metadata["diagnostic_kind"]`
against `record.metadata["memory_diagnostic"]["kind"]` and refuses when they disagree. A cell is
admitted only when EVERY arm is admitted, so a single arm whose metadata is not carried across
voids the entire grid.

Measured 2026-08-31 on official-002, and this is the cost these tests exist to prevent: 360
sessions ran, 44 of 60 `recall_prefetch` sessions succeeded, and **0 cells were admitted**. All 60
were discarded with

    diagnostic arm 'recall_prefetch' expected memory treatment 'recall_prefetch', got None

`scripts/diagnostic.py` copied the spec metadata into the record and `scripts/pilot.py` never did,
which is why the same arm admitted 70 of 72 cells in `diagnostic-010` and produced nothing here.
The two runners disagreed about a contract neither of them stated.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.adapters.base import AdmissionSignal, ArmSpec
from harness.gate import _check_diagnostic
from harness.schema import SessionRecord
from scripts.pilot import diagnostic_metadata

PREFETCH = {
    "kind": "recall_prefetch",
    "prefetch_status": "ok",
    "abstained": False,
    "hit_count": 5,
    "query_sha256": "a" * 64,
    "result_sha256": "b" * 64,
}


def _spec(metadata: dict | None) -> ArmSpec:
    return ArmSpec(arm="recall_prefetch", metadata=metadata)


def test_the_diagnostic_payload_is_carried():
    assert diagnostic_metadata(_spec({"memory_diagnostic": PREFETCH})) == {
        "memory_diagnostic": PREFETCH
    }


def test_a_non_diagnostic_arm_carries_nothing():
    """`_check_diagnostic` REJECTS a non-diagnostic arm that carries diagnostic metadata."""
    assert diagnostic_metadata(_spec({"memory": "served"})) == {}
    assert diagnostic_metadata(_spec(None)) == {}
    assert diagnostic_metadata(object()) == {}


def test_the_runners_prompt_hash_is_not_clobbered():
    """The adapter also sets `prompt_sha256`; the runner computes its own from the real file."""
    carried = diagnostic_metadata(
        _spec({"memory_diagnostic": PREFETCH, "prompt_sha256": "adapter-value"})
    )
    assert "prompt_sha256" not in carried


def _reasons(metadata: dict) -> list[str]:
    signal = AdmissionSignal(arm="recall_prefetch", metadata={"diagnostic_kind": "recall_prefetch"})
    record = SessionRecord(
        task_id="t", arm="recall_prefetch", seed=0, success=True, user_input="x", metadata=metadata
    )
    reasons: list[str] = []
    _check_diagnostic(record, signal, reasons)
    return reasons


def test_the_gate_admits_what_this_function_produces():
    """End to end: what the runner stamps is exactly what the gate demands.

    This is the test that would have caught the defect. Both halves were individually correct; only
    the join between them was missing, and nothing asserted the join.
    """
    assert _reasons(diagnostic_metadata(_spec({"memory_diagnostic": PREFETCH}))) == []


def test_the_gate_refuses_when_nothing_is_carried():
    """The exact failure official-002 hit, pinned so it cannot come back silently."""
    reasons = _reasons({})
    assert reasons and "expected memory treatment" in reasons[0]


def test_a_legitimate_abstention_is_still_admitted():
    """Abstaining is a valid outcome for a memory arm and must not be read as a broken session."""
    assert _reasons({"memory_diagnostic": {**PREFETCH, "abstained": True}}) == []


def test_a_genuinely_failed_prefetch_is_still_refused():
    """The gate must keep rejecting a real failure; the fix must not weaken it."""
    reasons = _reasons({"memory_diagnostic": {**PREFETCH, "prefetch_status": "error"}})
    assert reasons and "prefetch failed" in reasons[0]


def test_the_runner_actually_merges_it_into_the_record():
    """The JOIN, not the halves. This is the mutation that survived the first version.

    `diagnostic_metadata` can be perfect and the record still unstamped if the runner never merges
    its result, which is precisely the shape of the original defect: `scripts/diagnostic.py` did
    the merge, `scripts/pilot.py` did not, and both files were individually reasonable.

    Checked against the AST rather than the source text, so reformatting cannot break it and
    deleting the merge cannot pass it.
    """
    import ast

    tree = ast.parse((REPO / "scripts" / "pilot.py").read_text(encoding="utf-8"))

    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "extra" for t in node.targets)
        and isinstance(node.value, ast.Dict)
    ]
    assert assignments, "scripts/pilot.py no longer builds an `extra` dict for the record"

    unpacked = {
        ast.unparse(value)
        for node in assignments
        for key, value in zip(node.value.keys, node.value.values)
        if key is None  # a None key is `**something` in a dict literal
    }
    assert "diagnostic_extra" in unpacked, (
        "the runner builds `extra` without unpacking `diagnostic_extra`, so a diagnostic arm's "
        "memory_diagnostic never reaches the record and the admission gate will discard every "
        "cell of every condition"
    )
