"""Trusted execution receipts for benchmark runs.

The ordinary verifier proves that published numbers follow from published files.  This module
adds the missing controller owned evidence.  A trusted controller issues a fresh challenge,
writes a hash chained runtime event log, and signs a receipt only after the participant, checker,
oracle isolation, and admission signal events have been observed.

The signing key never enters a participant container or a published artifact.  Ed25519 is used so
reviewers can verify a receipt with a public key without receiving the adjudicator's private key.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import tempfile
import threading
import uuid
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
except ImportError as error:  # pragma: no cover, exercised only in an incomplete installation
    serialization = None
    Ed25519PrivateKey = Any  # type: ignore[assignment,misc]
    Ed25519PublicKey = Any  # type: ignore[assignment,misc]
    _CRYPTOGRAPHY_ERROR = error
else:
    _CRYPTOGRAPHY_ERROR = None


CHALLENGE_SCHEMA = "amb-execution-challenge-v1"
EVENT_SCHEMA = "amb-runtime-event-v1"
RECEIPT_SCHEMA = "amb-adjudication-receipt-v1"
CHALLENGE_VERSION = 1
SIGNATURE_ALGORITHM = "Ed25519"
_SHA256_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class AdjudicationError(RuntimeError):
    """A trusted execution proof could not be issued or verified."""


def canonical_bytes(value: Any) -> bytes:
    """Encode JSON deterministically, rejecting non portable numeric values."""

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise AdjudicationError(f"value is not canonical JSON: {error}") from error
    return encoded.encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    source = Path(path)
    try:
        return sha256_bytes(source.read_bytes())
    except OSError as error:
        raise AdjudicationError(f"cannot hash {source}: {error}") from error


def json_digest(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def tree_digest(root: str | Path) -> str:
    """Hash a directory's regular files by normalized relative path and content."""

    base = Path(root)
    if not base.is_dir() or base.is_symlink():
        raise AdjudicationError(f"digest root is not a real directory: {base}")
    entries: list[tuple[str, bytes]] = []
    for path in sorted(base.rglob("*")):
        if path.is_symlink():
            raise AdjudicationError(f"digest root contains a symlink: {path}")
        if path.is_file():
            entries.append((path.relative_to(base).as_posix(), path.read_bytes()))
    return json_digest([[name, base64.b64encode(data).decode("ascii")] for name, data in entries])


def _timestamp(value: datetime | None = None) -> str:
    current = value or datetime.now(UTC)
    return current.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


@dataclass(frozen=True)
class Challenge:
    challenge_id: str
    nonce: str
    run_id: str
    runner_image_digest: str
    participant_agent_digest: str
    oracle_version: str
    issued_at: str
    expires_at: str
    version: int = CHALLENGE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CHALLENGE_SCHEMA,
            "challenge_version": self.version,
            "challenge_id": self.challenge_id,
            "nonce": self.nonce,
            "run_id": self.run_id,
            "runner_image_digest": self.runner_image_digest,
            "participant_agent_digest": self.participant_agent_digest,
            "oracle_version": self.oracle_version,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Challenge":
        if value.get("schema") != CHALLENGE_SCHEMA:
            raise AdjudicationError("challenge schema is unsupported")
        try:
            challenge = cls(
                challenge_id=str(value["challenge_id"]),
                nonce=str(value["nonce"]),
                run_id=str(value["run_id"]),
                runner_image_digest=str(value["runner_image_digest"]),
                participant_agent_digest=str(value["participant_agent_digest"]),
                oracle_version=str(value["oracle_version"]),
                issued_at=str(value["issued_at"]),
                expires_at=str(value["expires_at"]),
                version=int(value["challenge_version"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise AdjudicationError("challenge is malformed") from error
        if challenge.version != CHALLENGE_VERSION or not all(
            (
                challenge.challenge_id,
                challenge.nonce,
                challenge.run_id,
                challenge.runner_image_digest,
                challenge.participant_agent_digest,
                challenge.oracle_version,
            )
        ):
            raise AdjudicationError("challenge is incomplete")
        return challenge


def issue_challenge(
    run_dir: str | Path,
    *,
    run_id: str,
    runner_image_digest: str,
    participant_agent_digest: str,
    oracle_version: str,
    ttl_s: float = 24 * 60 * 60,
) -> Challenge:
    """Issue one non reusable challenge before a run starts."""

    if ttl_s <= 0:
        raise ValueError("challenge TTL must be positive")
    if not _SHA256_DIGEST.fullmatch(runner_image_digest):
        raise AdjudicationError("runner_image_digest must be a sha256 digest")
    if not _SHA256_DIGEST.fullmatch(participant_agent_digest):
        raise AdjudicationError("participant_agent_digest must be a sha256 digest")
    target = Path(run_dir) / "challenge.json"
    if target.exists():
        raise AdjudicationError(f"challenge already exists, refusing replay: {target}")
    now = datetime.now(UTC)
    challenge = Challenge(
        challenge_id=str(uuid.uuid4()),
        nonce=secrets.token_urlsafe(32),
        run_id=run_id,
        runner_image_digest=runner_image_digest,
        participant_agent_digest=participant_agent_digest,
        oracle_version=oracle_version,
        issued_at=_timestamp(now),
        expires_at=_timestamp(now + timedelta(seconds=ttl_s)),
    )
    _atomic_write_json(target, challenge.to_dict())
    return challenge


class RuntimeEventLog:
    """A controller written, hash chained event log for one challenge."""

    def __init__(self, path: str | Path, challenge: Challenge):
        self.path = Path(path)
        self.challenge = challenge
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def append(self, kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not kind.strip():
            raise ValueError("event kind must not be empty")
        with self._lock:
            previous = ""
            lines = self.path.read_text(encoding="utf-8").splitlines()
            if lines:
                try:
                    previous = str(json.loads(lines[-1])["event_hash"])
                except (KeyError, json.JSONDecodeError) as error:
                    raise AdjudicationError("runtime event log is already malformed") from error
            event = {
                "schema": EVENT_SCHEMA,
                "challenge_version": self.challenge.version,
                "challenge_id": self.challenge.challenge_id,
                "nonce": self.challenge.nonce,
                "run_id": self.challenge.run_id,
                "sequence": len(lines),
                "event_id": str(uuid.uuid4()),
                "timestamp": _timestamp(),
                "kind": kind,
                "payload": dict(payload),
                "previous_hash": previous,
            }
            event["event_hash"] = sha256_bytes(canonical_bytes(event))
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return event


def verify_event_log(path: str | Path, challenge: Challenge) -> tuple[list[dict[str, Any]], str]:
    """Validate the chain and challenge binding of a runtime event log."""

    source = Path(path)
    if not source.is_file():
        raise AdjudicationError(f"runtime event log is missing: {source}")
    events: list[dict[str, Any]] = []
    previous = ""
    for expected_sequence, line in enumerate(source.read_text(encoding="utf-8").splitlines()):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise AdjudicationError(f"runtime event log has invalid JSON at {expected_sequence}") from error
        if not isinstance(event, dict):
            raise AdjudicationError("runtime event is not an object")
        stored_hash = event.pop("event_hash", None)
        if (
            event.get("schema") != EVENT_SCHEMA
            or event.get("challenge_version") != challenge.version
            or event.get("challenge_id") != challenge.challenge_id
            or event.get("nonce") != challenge.nonce
            or event.get("run_id") != challenge.run_id
            or event.get("sequence") != expected_sequence
            or event.get("previous_hash") != previous
            or not isinstance(stored_hash, str)
        ):
            raise AdjudicationError(f"runtime event binding failed at {expected_sequence}")
        expected_hash = sha256_bytes(canonical_bytes(event))
        if not secrets.compare_digest(stored_hash, expected_hash):
            raise AdjudicationError(f"runtime event hash failed at {expected_sequence}")
        event["event_hash"] = stored_hash
        events.append(event)
        previous = stored_hash
    if not events:
        raise AdjudicationError("runtime event log is empty")
    return events, sha256_file(source)


def admission_signal_snapshot(signals: Mapping[str, Any]) -> dict[str, Any]:
    """Convert AdmissionSignal objects into a stable, non executable snapshot."""

    result: dict[str, Any] = {}
    for arm, signal in sorted(signals.items()):
        metadata = getattr(signal, "metadata", {})
        result[arm] = {
            "arm": str(getattr(signal, "arm", arm)),
            "mcp_tool_prefixes": list(getattr(signal, "mcp_tool_prefixes", ())),
            "required_hooks": list(getattr(signal, "required_hooks", ())),
            "sandbox_paths": list(getattr(signal, "sandbox_paths", ())),
            "prompt_sha256": getattr(signal, "prompt_sha256", None),
            "forbidden_prefixes": list(getattr(signal, "forbidden_prefixes", ())),
            "metadata": dict(metadata) if isinstance(metadata, Mapping) else {},
        }
    return result


def artifact_digests(run_dir: str | Path) -> dict[str, str]:
    """Hash every required condition artifact and its stream tree."""

    base = Path(run_dir)
    required = ("environment.json", "records.final.jsonl", "admission.json", "costs.json")
    missing = [name for name in required if not (base / name).is_file()]
    if missing:
        raise AdjudicationError(f"required artifacts are missing: {missing}")
    result = {name: sha256_file(base / name) for name in required}
    streams = base / "streams"
    if not streams.is_dir():
        raise AdjudicationError("streams directory is missing")
    result["streams"] = tree_digest(streams)
    return result


def _events_by_kind(events: Sequence[Mapping[str, Any]], kind: str) -> list[Mapping[str, Any]]:
    return [event for event in events if event.get("kind") == kind]


def _require_runtime_evidence(
    events: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    artifact_count: int,
) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    signals = _events_by_kind(events, "admission_signals")
    if len(signals) != 1:
        raise AdjudicationError("runtime admission signals are missing or duplicated")
    completed = _events_by_kind(events, "participant_completed")
    final_completed = [event for event in completed if event.get("payload", {}).get("final", True)]
    if len(final_completed) != artifact_count:
        raise AdjudicationError(
            f"runtime participant count {len(final_completed)} does not match records {artifact_count}"
        )
    checker_events = _events_by_kind(events, "checker_completed")
    if len(checker_events) != artifact_count:
        raise AdjudicationError(
            f"runtime checker count {len(checker_events)} does not match records {artifact_count}"
        )
    for event in final_completed:
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            raise AdjudicationError("participant event payload is malformed")
        if payload.get("run_id", run_id) != run_id:
            raise AdjudicationError("participant event has the wrong run")
        if payload.get("participant_isolation_verified") is not True:
            raise AdjudicationError("participant isolation was not verified at runtime")
        if payload.get("oracle_visible_to_participant") is not False:
            raise AdjudicationError("oracle visibility was not proven false at runtime")
    for event in checker_events:
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            raise AdjudicationError("checker event payload is malformed")
        if payload.get("checker_network") != "none" or payload.get("oracle_read_only") is not True:
            raise AdjudicationError("checker oracle isolation was not proven at runtime")
    signal_payload = signals[0].get("payload")
    if not isinstance(signal_payload, Mapping) or not signal_payload.get("signals_sha256"):
        raise AdjudicationError("runtime admission signal digest is missing")
    checker_outcomes = [
        {
            "task_id": event.get("payload", {}).get("task_id"),
            "arm": event.get("payload", {}).get("arm"),
            "seed": event.get("payload", {}).get("seed"),
            "ok": event.get("payload", {}).get("ok"),
            "verdict_sha256": event.get("payload", {}).get("verdict_sha256"),
        }
        for event in checker_events
    ]
    return (
        dict(signal_payload),
        {"events": checker_outcomes, "count": len(checker_outcomes)},
        str(signal_payload["signals_sha256"]),
        json_digest(checker_outcomes),
    )


def _load_private_key(path: str | Path):
    if _CRYPTOGRAPHY_ERROR is not None:
        raise AdjudicationError("cryptography is required for Ed25519 receipts") from _CRYPTOGRAPHY_ERROR
    raw = Path(path).read_bytes()
    try:
        if len(raw) == 32:
            return Ed25519PrivateKey.from_private_bytes(raw)
        value = raw.decode("ascii").strip()
        decoded = _unb64(value)
        if len(decoded) != 32:
            raise ValueError
        return Ed25519PrivateKey.from_private_bytes(decoded)
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise AdjudicationError(f"adjudicator key is not a raw or base64 Ed25519 key: {path}") from error


def load_private_signer(path: str | Path, *, key_id: str = "adjudicator") -> "ReceiptSigner":
    return ReceiptSigner(_load_private_key(path), key_id=key_id)


class ReceiptSigner:
    """Ed25519 signer and verifier for the public receipt."""

    def __init__(self, private_key: Any, *, key_id: str):
        if _CRYPTOGRAPHY_ERROR is not None:
            raise AdjudicationError("cryptography is required for Ed25519 receipts") from _CRYPTOGRAPHY_ERROR
        if not key_id.strip():
            raise ValueError("key_id must not be empty")
        self.private_key = private_key
        self.key_id = key_id

    @property
    def public_key_bytes(self) -> bytes:
        return self.private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )

    def sign(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        body = dict(payload)
        body["receipt_id"] = json_digest(body)
        signature = self.private_key.sign(canonical_bytes(body))
        return {
            **body,
            "signature": {
                "algorithm": SIGNATURE_ALGORITHM,
                "key_id": self.key_id,
                "public_key": _b64(self.public_key_bytes),
                "value": _b64(signature),
            },
        }


def verify_signature(receipt: Mapping[str, Any], public_key: bytes | None = None) -> None:
    if _CRYPTOGRAPHY_ERROR is not None:
        raise AdjudicationError("cryptography is required for Ed25519 receipts") from _CRYPTOGRAPHY_ERROR
    signature = receipt.get("signature")
    if not isinstance(signature, Mapping) or signature.get("algorithm") != SIGNATURE_ALGORITHM:
        raise AdjudicationError("receipt has no Ed25519 signature")
    try:
        embedded = _unb64(str(signature["public_key"]))
        value = _unb64(str(signature["value"]))
    except (TypeError, ValueError) as error:
        raise AdjudicationError("receipt signature encoding is malformed") from error
    if public_key is not None and not secrets.compare_digest(public_key, embedded):
        raise AdjudicationError("receipt key is not the trusted adjudicator key")
    body = {key: value for key, value in receipt.items() if key != "signature"}
    receipt_id = body.pop("receipt_id", None)
    if not isinstance(receipt_id, str) or not secrets.compare_digest(receipt_id, json_digest(body)):
        raise AdjudicationError("receipt identity is invalid")
    try:
        Ed25519PublicKey.from_public_bytes(embedded).verify(value, canonical_bytes(body | {"receipt_id": receipt_id}))
    except Exception as error:  # cryptography exposes InvalidSignature without a stable base class
        raise AdjudicationError("receipt signature is invalid") from error


def adjudicate_run(
    run_dir: str | Path,
    *,
    signer: ReceiptSigner,
    ledger_path: str | Path | None = None,
) -> dict[str, Any]:
    """Issue a signed receipt after validating trusted runtime evidence."""

    base = Path(run_dir)
    receipt_path = base / "adjudication.receipt.json"
    if receipt_path.exists():
        raise AdjudicationError(f"receipt already exists, refusing replay: {receipt_path}")
    try:
        challenge = Challenge.from_mapping(json.loads((base / "challenge.json").read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise AdjudicationError("challenge is unreadable") from error
    events, event_hash = verify_event_log(base / "execution-events.jsonl", challenge)
    records = [
        line
        for line in (base / "records.final.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    signal_payload, checker_outcomes, signal_digest, checker_digest = _require_runtime_evidence(
        events, run_id=challenge.run_id, artifact_count=len(records)
    )
    artifacts = artifact_digests(base)
    try:
        admission = json.loads((base / "admission.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AdjudicationError("admission artifact is unreadable") from error
    if admission.get("runtime_signals_sha256") != signal_digest:
        raise AdjudicationError("admission signals are not bound to the runtime signal event")
    snapshot = {
        "artifact_digests": artifacts,
        "records_count": len(records),
        "signals_sha256": signal_digest,
        "checker_outcomes_sha256": checker_digest,
    }
    RuntimeEventLog(base / "execution-events.jsonl", challenge).append(
        "adjudication_snapshot", snapshot
    )
    _events, event_hash = verify_event_log(base / "execution-events.jsonl", challenge)
    payload = {
        "schema": RECEIPT_SCHEMA,
        "challenge_version": challenge.version,
        "challenge_id": challenge.challenge_id,
        "nonce": challenge.nonce,
        "run_id": challenge.run_id,
        "runner_image_digest": challenge.runner_image_digest,
        "participant_agent_digest": challenge.participant_agent_digest,
        "event_log_hash": event_hash,
        "oracle_version": challenge.oracle_version,
        "checker_outcomes": checker_outcomes,
        "checker_outcomes_sha256": checker_digest,
        "admission_signals_sha256": signal_digest,
        "artifact_digests": artifacts,
        "execution": {
            "records_count": len(records),
            "participant_isolation_verified": True,
            "oracle_visible_to_participant": False,
            "checker_network": "none",
            "oracle_read_only": True,
            "runtime_signal_event": signal_payload.get("event_id"),
        },
        "timestamps": {
            "challenge_issued_at": challenge.issued_at,
            "adjudicated_at": _timestamp(),
        },
    }
    receipt = signer.sign(payload)
    if ledger_path is not None:
        ledger = Path(ledger_path)
        ledger.parent.mkdir(parents=True, exist_ok=True)
        if ledger.exists():
            for line in ledger.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                if entry.get("nonce") == challenge.nonce or entry.get("challenge_id") == challenge.challenge_id:
                    raise AdjudicationError("challenge nonce was already adjudicated")
        with ledger.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({
                "challenge_id": challenge.challenge_id,
                "nonce": challenge.nonce,
                "receipt_id": receipt["receipt_id"],
                "adjudicated_at": receipt["timestamps"]["adjudicated_at"],
            }, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    _atomic_write_json(receipt_path, receipt)
    return receipt


def verify_receipt(
    run_dir: str | Path,
    *,
    public_key: bytes | None = None,
) -> dict[str, Any]:
    """Verify a receipt, its challenge, event log, and all bound artifacts."""

    base = Path(run_dir)
    try:
        receipt = json.loads((base / "adjudication.receipt.json").read_text(encoding="utf-8"))
        challenge = Challenge.from_mapping(json.loads((base / "challenge.json").read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise AdjudicationError("receipt or challenge is unreadable") from error
    verify_signature(receipt, public_key)
    for name in ("challenge_version", "challenge_id", "nonce", "run_id", "runner_image_digest", "participant_agent_digest", "oracle_version"):
        if receipt.get(name) != challenge.to_dict().get(name):
            raise AdjudicationError(f"receipt field {name!r} does not match the challenge")
    events, event_hash = verify_event_log(base / "execution-events.jsonl", challenge)
    if receipt.get("event_log_hash") != event_hash:
        raise AdjudicationError("receipt event log hash does not match")
    current_artifacts = artifact_digests(base)
    if receipt.get("artifact_digests") != current_artifacts:
        raise AdjudicationError("receipt artifact digest does not match")
    records_count = sum(
        1 for line in (base / "records.final.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()
    )
    if receipt.get("execution", {}).get("records_count") != records_count:
        raise AdjudicationError("receipt record count does not match")
    _signal_payload, _outcomes, signal_digest, checker_digest = _require_runtime_evidence(
        events, run_id=challenge.run_id, artifact_count=records_count
    )
    if receipt.get("admission_signals_sha256") != signal_digest:
        raise AdjudicationError("receipt admission signal digest does not match")
    if receipt.get("checker_outcomes_sha256") != checker_digest:
        raise AdjudicationError("receipt checker outcome digest does not match")
    return receipt


def generate_private_key(path: str | Path) -> str:
    """Generate a raw Ed25519 private key and return its public key in base64url form."""

    if _CRYPTOGRAPHY_ERROR is not None:
        raise AdjudicationError("cryptography is required for Ed25519 receipts") from _CRYPTOGRAPHY_ERROR
    target = Path(path)
    if target.exists():
        raise AdjudicationError(f"refusing to overwrite existing key: {target}")
    key = Ed25519PrivateKey.generate()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    ))
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return _b64(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
