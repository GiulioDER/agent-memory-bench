"""Data minimisation and publication boundaries for benchmark artifacts.

Raw session streams are useful during a run, but they are not public evidence.  Public evidence
contains the outcome and bounded telemetry needed to reproduce aggregate numbers, plus digests of
the omitted text.  This module is deliberately stdlib only so the publication boundary is usable
before any optional adapter is installed.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .schema import SessionRecord


class PrivacyError(ValueError):
    """A run or artifact does not meet the declared data safety policy."""


RAW_RECORD_FIELDS = frozenset(
    {
        "user_input",
        "response",
        "reference",
        "retrieved_contexts",
        "reference_contexts",
        "conversation",
        "reference_tool_calls",
        "runtime_decisions",
    }
)
_RAW_TOOL_FIELDS = frozenset(
    {"args", "output", "file_path", "command", "old_string", "new_string", "stderr"}
)
_SAFE_METADATA_FIELDS = frozenset(
    {
        "abstain_marker",
        "abstained",
        "api_retries",
        "arm_concurrency",
        "arm_order",
        "attempt",
        "condition",
        "diagnostic_kind",
        "failed_tool_calls",
        "fresh_input_tokens",
        "host_headroom",
        "init_present",
        "instruction_bytes",
        "memory_error_codes",
        "memory_retrieval",
        "memory_tools_available",
        "memory_trust_states",
        "model",
        "mcp_servers",
        "model_turns",
        "network_policy_digest",
        "outcome",
        "participant_isolation_verified",
        "permission_denial_count",
        "prompt_sha256",
        "sandbox_digest",
        "sandbox_paths_present",
        "session_tools",
        "silent_completion_retries",
        "stop_reason",
        "stream_duration_api_ms",
        "stream_duration_ms",
        "subagent_tool_calls",
        "workspace_input_digest",
        "workspace_output_digest",
    }
)
_SECRET_RE = re.compile(
    r"(?i)(?:bearer\s+|sk-|rk-|or-)[A-Za-z0-9._~+/=-]{12,}"
)


def _digest(value: Any) -> str | None:
    if value is None or value == "" or value == [] or value == {}:
        return None
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_value(value: Any) -> Any:
    """Copy JSON data while excluding strings that could carry an omitted transcript."""

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(key): _safe_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_safe_value(item) for item in value]
    return str(value)


def _safe_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): _safe_value(value)
        for key, value in metadata.items()
        if str(key) in _SAFE_METADATA_FIELDS
    }


def _tool_receipt(call: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": str(call.get("name", "")),
        "is_error": bool(call.get("is_error", False)),
        "latency_ms": call.get("latency_ms"),
        "content_sha256": _digest(call),
    }


def public_receipt(record: SessionRecord) -> dict[str, Any]:
    """Return the only record shape allowed in a published run.

    The hashes are over canonical JSON, not over a redacted preview.  A reviewer can therefore
    bind a private audit copy to the public receipt without the public artifact carrying the data.
    """

    metadata = _safe_metadata(record.metadata)
    metadata["privacy"] = {
        "schema": "amb-public-receipt-v1",
        "redacted_fields": sorted(RAW_RECORD_FIELDS),
        "hash_algorithm": "sha256",
    }
    if record.error:
        metadata["error_sha256"] = _digest(record.error)
    receipt = {
        "record_version": 4,
        "task_id": record.task_id,
        "arm": record.arm,
        "seed": record.seed,
        "success": record.success,
        "memory_call_count": record.memory_call_count,
        "memory_calls_attempted": record.memory_calls_attempted,
        "memory_calls_succeeded": record.memory_calls_succeeded,
        "memory_calls_failed": record.memory_calls_failed,
        "memory_search_abstained": record.memory_search_abstained,
        "memory_hits_returned": record.memory_hits_returned,
        "memory_trust_states": list(record.memory_trust_states),
        "memory_error_codes": list(record.memory_error_codes),
        "memory_latency_ms": record.memory_latency_ms,
        "input_tokens": record.input_tokens,
        "output_tokens": record.output_tokens,
        "model_turns": record.model_turns,
        "wall_time_ms": record.wall_time_ms,
        "system_cost_usd": record.system_cost_usd,
        "evaluator_cost_usd": record.evaluator_cost_usd,
        "abstained": record.abstained,
        "trust_verdicts": list(record.trust_verdicts),
        "config_dir_digest": record.config_dir_digest,
        "error": "redacted" if record.error else None,
        "tool_calls": [_tool_receipt(call) for call in record.tool_calls],
        "metadata": metadata,
        "receipt": {
            "user_input_sha256": _digest(record.user_input),
            "response_sha256": _digest(record.response),
            "reference_sha256": _digest(record.reference),
            "retrieved_contexts_sha256": _digest(record.retrieved_contexts),
            "reference_contexts_sha256": _digest(record.reference_contexts),
            "conversation_sha256": _digest(record.conversation),
            "reference_tool_calls_sha256": _digest(record.reference_tool_calls),
            "runtime_decisions_sha256": _digest(record.runtime_decisions),
            "hook_ledger_sha256": _digest(record.hook_ledger),
            "tool_calls_sha256": _digest(record.tool_calls),
        },
    }
    assert_public_receipt(receipt)
    return receipt


def assert_public_receipt(value: Mapping[str, Any]) -> None:
    """Fail closed if a receipt accidentally regains a raw transcript field."""

    forbidden = RAW_RECORD_FIELDS | _RAW_TOOL_FIELDS

    def walk(item: Any, path: str = "") -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                name = str(key)
                if name in forbidden:
                    raise PrivacyError(f"public receipt contains raw field {path + name!r}")
                walk(child, path + name + ".")
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for index, child in enumerate(item):
                walk(child, f"{path}[{index}].")
        elif isinstance(item, str) and _SECRET_RE.search(item):
            raise PrivacyError(f"public receipt contains a credential shaped value at {path}")

    walk(value)


def write_public_jsonl(path: str | Path, records: Iterable[SessionRecord]) -> None:
    """Write redacted receipts, never canonical records, to a publication path."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(public_receipt(record), sort_keys=True) for record in records]
    target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8", newline="\n")


def redact_log_text(text: str, *, secrets: Iterable[str] = (), paths: Iterable[str] = ()) -> str:
    """Redact known credentials and host paths before a log is made public."""

    result = text
    for value in sorted((str(item) for item in secrets if item), key=len, reverse=True):
        result = result.replace(value, "[REDACTED_SECRET]")
    for value in sorted((str(item) for item in paths if item), key=len, reverse=True):
        result = result.replace(value, "[REDACTED_PATH]")
    return _SECRET_RE.sub("[REDACTED_SECRET]", result)


def load_provider_policy(path: str | Path | None) -> dict[str, Any]:
    """Load the operator's explicit hosted data handling attestation."""

    if not path:
        raise PrivacyError("AMB_DATA_POLICY_FILE is required for a live run")
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PrivacyError(f"provider data policy is unreadable: {source}") from error
    if not isinstance(value, dict):
        raise PrivacyError("provider data policy must be a JSON object")
    if value.get("schema_version") != 1:
        raise PrivacyError("provider data policy schema_version must be 1")
    if value.get("data_classification") != "synthetic-only":
        raise PrivacyError("live benchmark data policy must declare synthetic-only data")
    hosted = value.get("hosted_processing")
    if not isinstance(hosted, dict):
        raise PrivacyError("provider data policy has no hosted_processing object")
    if hosted.get("retention") != "zero" or hosted.get("training") is not False:
        raise PrivacyError("hosted processing must declare zero retention and training=false")
    if hosted.get("reuse") is not False:
        raise PrivacyError("hosted processing must declare reuse=false")
    providers = value.get("providers")
    if not isinstance(providers, list) or not providers or not all(
        isinstance(item, str) and item.strip() for item in providers
    ):
        raise PrivacyError("provider data policy must name at least one provider")
    return value


def provider_policy_metadata(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return non-sensitive policy provenance for environment.json."""

    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    hosted = value["hosted_processing"]
    return {
        "schema_version": value["schema_version"],
        "data_classification": value["data_classification"],
        "providers": list(value["providers"]),
        "retention": hosted["retention"],
        "training": hosted["training"],
        "reuse": hosted["reuse"],
        "policy_sha256": hashlib.sha256(canonical).hexdigest(),
    }
