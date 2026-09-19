from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path


def test_anchor_audit_rechecks_every_claim_against_original_source_bytes():
    """RED on pre-fix: no independent source audit existed for compiler v2."""
    spec = importlib.util.find_spec("scripts.recall_anchor_compiler_audit")
    assert spec is not None, "compiler v2 needs an independent source audit"
    module = importlib.import_module("scripts.recall_anchor_compiler_audit")
    content = "WidgetError in src/widget.py was repaired with CONFIG_KEY."
    record = {
        "kind": "successful repair",
        "task_shape": "",
        "problem": "",
        "action": "repaired with CONFIG_KEY",
        "outcome": "",
        "validation": "",
        "entities": ["WidgetError", "src/widget.py", "CONFIG_KEY"],
        "evidence_spans": [
            {
                "message_ordinal": 0,
                "start": 0,
                "end": len(content),
                "quote": content,
            }
        ],
        "evidence_quotes": [content],
        "event_time": None,
        "source_session_id": "sessions/task/p01.jsonl",
        "supersedes": [],
    }

    messages = [
        {
            "role": "assistant",
            "content": content,
            "timestamp": 1_725_177_600_000,
        }
    ]
    record["event_time"] = "2024-09-01T08:00:00Z"

    assert module.audit_record(
        record,
        messages,
        expected_source_session_id="sessions/task/p01.jsonl",
    ) == []

    record["outcome"] = "invented success"
    record["event_time"] = "2035-01-01T00:00:00Z"
    record["source_session_id"] = "sessions/other/p01.jsonl"
    assert module.audit_record(
        record,
        messages,
        expected_source_session_id="sessions/task/p01.jsonl",
    ) == [
        "unsupported_field:outcome",
        "unsupported_event_time",
        "source_session_mismatch",
    ]


def test_anchor_audit_rejects_fabricated_or_misaligned_spans():
    """The independent audit must not trust stored offsets or quotes."""
    spec = importlib.util.find_spec("scripts.recall_anchor_compiler_audit")
    assert spec is not None, "compiler v2 needs an independent source audit"
    module = importlib.import_module("scripts.recall_anchor_compiler_audit")
    record = {
        "kind": "repository fact",
        "problem": "WidgetError",
        "entities": [],
        "evidence_spans": [
            {"message_ordinal": 0, "start": 0, "end": 11, "quote": "WidgetError"}
        ],
        "source_session_id": "sessions/task/p01.jsonl",
    }

    issues = module.audit_record(
        record,
        [{"role": "assistant", "content": "Different text"}],
    )

    assert issues == ["invalid_evidence_span:0", "unsupported_field:problem"]


def test_anchor_audit_distinguishes_accepted_records_from_deterministic_fallbacks():
    """RED: the auditor had no stored fallback classification boundary."""
    module = importlib.import_module("scripts.recall_anchor_compiler_audit")

    assert module.compiler_record_state(
        {"compiler_profile": "anchor-v2", "compiler_fallback": False}
    ) == ("accepted", True)
    assert module.compiler_record_state(
        {"compiler_profile": "deterministic-fallback", "compiler_fallback": True}
    ) == ("fallback", True)
    assert module.compiler_record_state(
        {"compiler_profile": "anchor-v2", "compiler_fallback": True}
    ) == ("fallback", False)


def test_vps_pilot_runs_the_database_audit_with_the_recall_runtime():
    """RED: the AMB runtime lacks psycopg and could not execute the frozen audit."""
    script = (
        Path(__file__).parents[1] / "scripts" / "recall_anchor_compiler_vps2_pilot.sh"
    ).read_text(encoding="utf-8")

    assert '"$recall_root/.venv/bin/python" -m scripts.recall_anchor_compiler_audit' in script
