from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


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

    assert (
        module.audit_record(
            record,
            messages,
            expected_source_session_id="sessions/task/p01.jsonl",
        )
        == []
    )

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
        "evidence_spans": [{"message_ordinal": 0, "start": 0, "end": 11, "quote": "WidgetError"}],
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


def test_anchor_audit_validates_an_explicit_v3_profile():
    """Mutation proof: ignoring accepted_profile marks the v3 record invalid."""
    module = importlib.import_module("scripts.recall_anchor_compiler_audit")

    assert module.compiler_record_state(
        {"compiler_profile": "anchor-v3", "compiler_fallback": False},
        accepted_profile="anchor-v3",
    ) == ("accepted", True)
    assert module.compiler_record_state(
        {"compiler_profile": "anchor-v2", "compiler_fallback": False},
        accepted_profile="anchor-v3",
    ) == ("accepted", False)


def test_vps_pilot_runs_the_database_audit_with_the_recall_runtime():
    """RED: the AMB runtime lacks psycopg and could not execute the frozen audit."""
    script = (
        Path(__file__).parents[1] / "scripts" / "recall_anchor_compiler_vps2_pilot.sh"
    ).read_text(encoding="utf-8")

    assert '"$recall_root/.venv/bin/python" -m scripts.recall_anchor_compiler_audit' in script


def test_v3_pilot_binds_the_v3_audit_and_selector_identities():
    """Mutation proof: removing the v3 profile flag fails the profile assertion."""
    script = (
        Path(__file__).parents[1]
        / "scripts"
        / "recall_anchor_compiler_v3_vps2_pilot.sh"
    ).read_text(encoding="utf-8")

    assert "--accepted-profile anchor-v3" in script
    assert "--baseline-variant V3_raw" in script
    assert "--candidate-variant V3_anchor_raw" in script
    assert "094-recall-anchor-compiler-v3-admission.md" in script


def test_anchor_audit_opens_the_exact_tenant_without_rebinding(tmp_path, monkeypatch):
    """RED on 6b384363: main bound a dummy tenant, then for_tenant refused without shared_pool."""
    module = importlib.import_module("scripts.recall_anchor_compiler_audit")
    relative = "sessions/task/p01.jsonl"
    session = tmp_path / relative
    session.parent.mkdir(parents=True)
    session.write_text(
        json.dumps({"role": "user", "content": "WidgetError", "ts": "2026-01-01T00:00:00Z"})
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"sessions": {relative: hashlib.sha256(session.read_bytes()).hexdigest()}}),
        encoding="utf-8",
    )
    opened: dict[str, object] = {}

    class FakeStore:
        def __init__(self, _dsn, _dimension, **kwargs):
            opened.update(kwargs)

        def for_tenant(self, _tenant):
            raise RuntimeError("for_tenant() requires shared-pool mode")

        def chunks_for_source(self, _source):
            return []

        def close(self):
            opened["closed"] = True

    recall_package = ModuleType("recall")
    recall_package.__path__ = []
    recall_store = ModuleType("recall.store")
    recall_store.PgVectorStore = FakeStore
    recall_aml_package = ModuleType("recall_aml")
    recall_aml_package.__path__ = []
    recall_identity = ModuleType("recall_aml.identity")
    recall_identity.tenant_for = lambda namespace: f"tenant::{namespace}"
    recall_identity.session_digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
    monkeypatch.setitem(sys.modules, "recall", recall_package)
    monkeypatch.setitem(sys.modules, "recall.store", recall_store)
    monkeypatch.setitem(sys.modules, "recall_aml", recall_aml_package)
    monkeypatch.setitem(sys.modules, "recall_aml.identity", recall_identity)
    monkeypatch.setenv("RECALL_AML_DATABASE_URL", "postgresql://unused")
    output = tmp_path / "audit.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "recall_anchor_compiler_audit",
            "--corpus",
            str(tmp_path),
            "--namespace",
            "anchor-pilot",
            "--output",
            str(output),
            "--table",
            "recall_table",
            "--generation",
            "anchor-generation",
        ],
    )

    module.main()

    assert opened["tenant"] == "tenant::anchor-pilot"
    assert opened["closed"] is True
    assert json.loads(output.read_text(encoding="utf-8"))["raw_session_count"] == 0
