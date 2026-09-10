"""Privacy boundary tests.

The red proof for these tests is a deliberate mutation of ``public_receipt`` that returns
``record.to_dict()``.  That mutation makes ``test_public_receipt_contains_no_raw_transcript`` fail
on its intended forbidden field assertion, rather than failing during collection or setup.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.privacy import (
    PrivacyError,
    assert_public_receipt,
    load_provider_policy,
    public_receipt,
    redact_log_text,
    write_public_jsonl,
)
from harness.schema import SessionRecord


def _record(**overrides) -> SessionRecord:
    values = {
        "task_id": "t1",
        "arm": "bare",
        "success": True,
        "user_input": "private task",
        "response": "private answer",
        "conversation": ({"role": "user", "content": "private task"},),
        "tool_calls": ({"name": "Read", "args": {"file_path": "private.txt"}, "output": "secret"},),
        "metadata": {"outcome": "solved", "command": ["must not publish"]},
    }
    values.update(overrides)
    return SessionRecord(**values)


def test_public_receipt_contains_no_raw_transcript() -> None:
    """Mutation: returning ``to_dict`` would publish the user prompt and tool output."""

    receipt = public_receipt(_record())
    encoded = json.dumps(receipt)
    assert "private task" not in encoded
    assert "private answer" not in encoded
    assert "private.txt" not in encoded
    assert receipt["receipt"]["response_sha256"]
    assert receipt["metadata"]["privacy"]["hash_algorithm"] == "sha256"


def test_public_jsonl_writer_emits_receipts_only(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    write_public_jsonl(path, [_record()])
    value = json.loads(path.read_text(encoding="utf-8"))
    assert value["record_version"] == 4
    assert "conversation" not in value
    assert "response" not in value
    assert_public_receipt(value)


def test_public_receipt_rejects_a_reintroduced_raw_field() -> None:
    with pytest.raises(PrivacyError, match="raw field"):
        assert_public_receipt({"task_id": "t1", "response": "leak"})


def test_log_redaction_removes_secrets_and_host_paths() -> None:
    result = redact_log_text(
        "key=sk-secret-value path=C:\\private\\run output",
        secrets=("sk-secret-value",),
        paths=(r"C:\private\run",),
    )
    assert "sk-secret-value" not in result
    assert r"C:\private\run" not in result
    assert "[REDACTED_SECRET]" in result
    assert "[REDACTED_PATH]" in result


def test_provider_policy_requires_zero_retention_and_no_reuse(tmp_path: Path) -> None:
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "data_classification": "synthetic-only",
                "hosted_processing": {"retention": "some", "training": False, "reuse": False},
                "providers": ["test"],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PrivacyError, match="zero retention"):
        load_provider_policy(path)


def test_default_corpus_data_safety_audit_passes() -> None:
    from scripts.audit_data_safety import main

    assert main([]) == 0
