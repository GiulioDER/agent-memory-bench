"""Tests for the trusted execution receipt boundary.

Each security test names the invariant and the mutation it catches.  Red proof is established by
applying the stated mutation to the production verifier, running the exact test node, observing
the intended assertion fail, then restoring the production implementation before the green run.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from harness.adjudication import (
    AdjudicationError,
    ReceiptSigner,
    RuntimeEventLog,
    adjudicate_run,
    issue_challenge,
    json_digest,
    verify_receipt,
)


def _fixture_run(tmp_path: Path):
    run = tmp_path / "run-condition"
    run.mkdir()
    challenge = issue_challenge(
        run,
        run_id="run-condition",
        runner_image_digest="sha256:" + "1" * 64,
        participant_agent_digest="sha256:" + "2" * 64,
        oracle_version="sha256:oracle",
    )
    log = RuntimeEventLog(run / "execution-events.jsonl", challenge)
    signal_digest = json_digest({"bare": {"arm": "bare", "mcp_tool_prefixes": []}})
    log.append("run_started", {"task_count": 1, "seed_count": 1, "arms": ["bare"]})
    log.append("admission_signals", {"signals_sha256": signal_digest, "arms": ["bare"]})
    log.append(
        "participant_completed",
        {
            "task_id": "ts-a",
            "arm": "bare",
            "seed": 0,
            "final": True,
            "participant_isolation_verified": True,
            "oracle_visible_to_participant": False,
        },
    )
    checker_payload = {
        "task_id": "ts-a",
        "arm": "bare",
        "seed": 0,
        "ok": True,
        "verdict_sha256": "v" * 64,
        "checker_network": "none",
        "oracle_read_only": True,
    }
    log.append("checker_completed", checker_payload)
    (run / "environment.json").write_text(
        json.dumps({"adjudication": {"schema": "amb-adjudication-receipt-v1"}}),
        encoding="utf-8",
    )
    (run / "records.final.jsonl").write_text('{"task_id":"ts-a","arm":"bare"}\n', encoding="utf-8")
    (run / "admission.json").write_text(
        json.dumps({"runtime_signals_sha256": signal_digest}), encoding="utf-8"
    )
    (run / "costs.json").write_text(json.dumps({"total_sessions": 1}), encoding="utf-8")
    (run / "streams").mkdir()
    (run / "streams" / "ts-a.s0.bare.jsonl.gz").write_bytes(b"stream")
    signer = ReceiptSigner(Ed25519PrivateKey.generate(), key_id="test")
    adjudicate_run(run, signer=signer)
    return run, signer


def test_a_clean_runtime_receipt_verifies_with_the_trusted_public_key(tmp_path: Path):
    """Control: challenge, event chain, signature, and artifacts all bind successfully."""

    run, signer = _fixture_run(tmp_path)
    receipt = verify_receipt(run, public_key=signer.public_key_bytes)
    assert receipt["schema"] == "amb-adjudication-receipt-v1"
    assert receipt["execution"]["oracle_visible_to_participant"] is False


def test_a_artifact_mutation_is_caught(tmp_path: Path):
    """Mutation: changing records after signing must fail at the artifact digest boundary."""

    run, signer = _fixture_run(tmp_path)
    (run / "records.final.jsonl").write_text('{"task_id":"changed","arm":"bare"}\n', encoding="utf-8")
    with pytest.raises(AdjudicationError, match="artifact digest"):
        verify_receipt(run, public_key=signer.public_key_bytes)


def test_a_event_log_mutation_is_caught(tmp_path: Path):
    """Mutation: changing a runtime outcome must fail at the hash chain or receipt hash."""

    run, signer = _fixture_run(tmp_path)
    path = run / "execution-events.jsonl"
    text = path.read_text(encoding="utf-8").replace('"ok": true', '"ok": false')
    path.write_text(text, encoding="utf-8")
    with pytest.raises(AdjudicationError, match="event"):
        verify_receipt(run, public_key=signer.public_key_bytes)


def test_a_untrusted_signing_key_is_caught(tmp_path: Path):
    """Mutation: a receipt signed by another key is not reviewer confirmation."""

    run, signer = _fixture_run(tmp_path)
    wrong_key = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    with pytest.raises(AdjudicationError, match="trusted adjudicator key"):
        verify_receipt(run, public_key=wrong_key)
    assert signer.public_key_bytes != wrong_key


def test_a_challenge_and_receipt_are_single_use(tmp_path: Path):
    """Mutation: replaying either the pre-run challenge or completed receipt is refused."""

    run, signer = _fixture_run(tmp_path)
    with pytest.raises(AdjudicationError, match="receipt already exists"):
        adjudicate_run(run, signer=signer)
    with pytest.raises(AdjudicationError, match="challenge already exists"):
        issue_challenge(
            run,
            run_id="run-condition",
            runner_image_digest="sha256:" + "1" * 64,
            participant_agent_digest="sha256:" + "2" * 64,
            oracle_version="sha256:oracle",
        )


def test_a_durable_ledger_rejects_the_same_nonce_in_another_directory(tmp_path: Path):
    """Mutation: copying a completed challenge into another directory must not be replayable."""

    run, signer = _fixture_run(tmp_path)
    receipt = json.loads((run / "adjudication.receipt.json").read_text(encoding="utf-8"))
    ledger = tmp_path / "adjudicator-ledger.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "challenge_id": receipt["challenge_id"],
                "nonce": receipt["nonce"],
                "receipt_id": receipt["receipt_id"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    replay = tmp_path / "replay"
    shutil.copytree(run, replay)
    (replay / "adjudication.receipt.json").unlink()
    with pytest.raises(AdjudicationError, match="already adjudicated"):
        adjudicate_run(replay, signer=signer, ledger_path=ledger)
