"""Deny the first repository mutation and return a bounded RE-call checkpoint."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

MARKER = "AMB_RECALL_CHECKPOINT:"
QUERY_LIMIT = 4096
REASON_LIMIT = 4800
TASK_LIMIT = 1200
MUTATION_LIMIT = 1800
TARGET_LIMIT = 800
HIT_TEXT_LIMIT = 1200
MAX_HITS = 3

_DIAGNOSTIC_REDIRECTION = re.compile(
    r"(?:^|\s)(?:[12]?>/dev/null|2>&1|1>&2)(?=\s|$)", re.IGNORECASE
)
_SHELL_MUTATOR = re.compile(
    r"(?:^|[;&|]\s*|\s)(?:tee|touch|mkdir|rm|mv|cp|install|chmod|chown|truncate)\b"
    r"|\b(?:sed|perl)\s+-[^\s]*i\b",
    re.IGNORECASE,
)
_KNOWN_GENERATOR = re.compile(
    r"(?:update_ignore|regen_golden|new_migration)\.py\b", re.IGNORECASE
)
_PYTHON_WRITER = re.compile(
    r"\b(?:write_text|write_bytes)\s*\(|\bopen\s*\([^\n]{0,240},\s*['\"](?:w|a|x|r\+|w\+|a\+)",
    re.IGNORECASE,
)
_OUTPUT_REDIRECTION = re.compile(r"(?<![0-9])>{1,2}(?![>&])")


class CheckpointError(RuntimeError):
    pass


def _clip(value: object, limit: int) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 16)] + "\n...[truncated]"


def is_mutation_candidate(tool_name: str, tool_input: Mapping[str, Any]) -> bool:
    """Return whether this call can change the repository under the frozen detector."""

    if tool_name in {"Write", "Edit"}:
        return True
    if tool_name != "Bash":
        return False
    command = str(tool_input.get("command", ""))
    cleaned = _DIAGNOSTIC_REDIRECTION.sub(" ", command)
    return bool(
        _OUTPUT_REDIRECTION.search(cleaned)
        or _SHELL_MUTATOR.search(cleaned)
        or _KNOWN_GENERATOR.search(cleaned)
        or _PYTHON_WRITER.search(cleaned)
    )


def _target_path(tool_input: Mapping[str, Any], cwd: Path) -> tuple[str, Path | None]:
    raw = tool_input.get("file_path") or tool_input.get("path")
    if not raw:
        return "", None
    value = Path(str(raw))
    candidate = value if value.is_absolute() else cwd / value
    try:
        resolved = candidate.resolve()
        root = cwd.resolve()
    except OSError:
        return str(value), None
    if resolved != root and root not in resolved.parents:
        return str(value), None
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError:
        relative = str(value)
    return relative, resolved


def build_checkpoint_query(
    *,
    task: str,
    tool_name: str,
    tool_input: Mapping[str, Any],
    cwd: str | Path,
) -> str:
    """Build the preregistered task plus pending mutation query."""

    root = Path(cwd)
    target_label, target = _target_path(tool_input, root)
    try:
        pending = json.dumps(tool_input, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        pending = repr(dict(tool_input))
    current = ""
    if target is not None:
        try:
            if target.is_file() and target.stat().st_size <= 64 * 1024:
                current = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            current = ""
    sections = [
        "Task:\n" + _clip(task, TASK_LIMIT),
        (
            "Pending repository mutation:\n"
            f"Tool: {tool_name}\n"
            f"Target: {target_label or '(not explicit)'}\n"
            + _clip(pending, MUTATION_LIMIT)
        ),
    ]
    if current:
        sections.append("Current target context:\n" + _clip(current, TARGET_LIMIT))
    sections.append(
        "Question: What prior project decisions, failure modes, supersessions, or required "
        "workflows should constrain this mutation? Return only evidence supported by project "
        "memory."
    )
    return _clip("\n\n".join(sections), QUERY_LIMIT)


def _json_from_tool_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("error"):
        raise CheckpointError(f"memory broker error: {payload['error']}")
    result = payload.get("result")
    if not isinstance(result, Mapping):
        raise CheckpointError("memory broker returned no MCP result")
    if result.get("isError"):
        raise CheckpointError("recall_search returned an MCP error")
    content = result.get("content")
    if not isinstance(content, list):
        raise CheckpointError("recall_search returned no content list")
    for block in content:
        if not isinstance(block, Mapping) or not isinstance(block.get("text"), str):
            continue
        try:
            parsed = json.loads(str(block["text"]))
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise CheckpointError("recall_search content contained no JSON object")


def broker_search(query: str) -> tuple[dict[str, Any], str, float]:
    """Call the existing capability broker from inside the participant container."""

    token = os.environ.get("AMB_CAPABILITY_MEMORY", "")
    if not token:
        raise CheckpointError("memory capability is unavailable")
    endpoint = os.environ.get(
        "AMB_PUBLIC_CHECKPOINT_BROKER_URL", "http://memory-broker:8080"
    )
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "recall_search",
            "arguments": {"query": query, "k": 5},
        },
    }
    encoded = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    call = urllib.request.Request(
        endpoint,
        data=encoded,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.monotonic()
    with urllib.request.urlopen(call, timeout=120) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
    elapsed_ms = (time.monotonic() - started) * 1000.0
    if len(raw) > 4 * 1024 * 1024:
        raise CheckpointError("memory broker response exceeded the checkpoint limit")
    text = raw.decode("utf-8", errors="replace")
    try:
        outer = json.loads(text)
    except json.JSONDecodeError as error:
        raise CheckpointError("memory broker response was not JSON") from error
    if not isinstance(outer, Mapping):
        raise CheckpointError("memory broker response was not an object")
    return _json_from_tool_result(outer), text, elapsed_ms


def _marker(diagnostic: Mapping[str, Any]) -> str:
    raw = json.dumps(diagnostic, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return MARKER + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def parse_checkpoint_marker(text: str) -> dict[str, Any]:
    match = re.search(re.escape(MARKER) + r"([A-Za-z0-9_-]+)", text)
    if not match:
        raise CheckpointError("checkpoint marker missing")
    encoded = match.group(1)
    try:
        data = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        parsed = json.loads(data)
    except (ValueError, json.JSONDecodeError) as error:
        raise CheckpointError("checkpoint marker malformed") from error
    if not isinstance(parsed, dict):
        raise CheckpointError("checkpoint marker is not an object")
    return parsed


def _reason_with_marker(diagnostic: dict[str, Any], body: str) -> str:
    body = _clip(body, 3800)
    for _ in range(4):
        diagnostic["injected_bytes"] = len(body.encode("utf-8"))
        diagnostic["injected_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
        marker = _marker(diagnostic)
        if len(marker) + 1 >= REASON_LIMIT:
            raise CheckpointError("checkpoint diagnostic exceeded the reason limit")
        clipped = _clip(body, REASON_LIMIT - len(marker) - 1)
        if clipped == body:
            return marker + "\n" + body
        body = clipped
    raise CheckpointError("checkpoint reason did not converge to its frozen limit")


def run_checkpoint(
    payload: Mapping[str, Any],
    *,
    mode: str,
    task: str,
    sentinel: str | Path,
    broker_call: Callable[[str], tuple[dict[str, Any], str, float]],
) -> dict[str, Any] | None:
    """Return one structured deny response, or None when the call should proceed."""

    tool_name = str(payload.get("tool_name") or payload.get("toolName") or "")
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    if not isinstance(tool_input, Mapping) or not is_mutation_candidate(tool_name, tool_input):
        return None
    sentinel_path = Path(sentinel)
    if sentinel_path.exists():
        return None
    sentinel_path.parent.mkdir(parents=True, exist_ok=True)
    sentinel_path.write_text("checkpoint attempted\n", encoding="utf-8")
    cwd = Path(str(payload.get("cwd") or os.getcwd()))
    base = {
        "version": 1,
        "mode": mode,
        "trigger_tool": tool_name,
        "status": "placebo" if mode == "placebo" else "error",
        "marker_count": 1,
        "query_sha256": None,
        "result_sha256": None,
        "latency_ms": 0.0,
        "hit_count": 0,
        "ok_hit_count": 0,
        "sources": [],
        "verdicts": [],
        "abstained": None,
    }
    if mode == "placebo":
        body = (
            "Pre-mutation checkpoint. The proposed mutation has not run. No memory evidence is "
            "supplied by this arm. Reconcile the proposed change with the current code and tests, "
            "then retry only if it remains justified."
        )
    elif mode == "treatment":
        query = build_checkpoint_query(
            task=task,
            tool_name=tool_name,
            tool_input=tool_input,
            cwd=cwd,
        )
        base["query_sha256"] = hashlib.sha256(query.encode("utf-8")).hexdigest()
        try:
            result, raw, latency_ms = broker_call(query)
            base["result_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            base["latency_ms"] = round(float(latency_ms), 3)
            if result.get("trust_state") != "trusted":
                raise CheckpointError(
                    f"recall_search trust state is {result.get('trust_state')!r}, not 'trusted'"
                )
            hits = result.get("hits") or []
            if not isinstance(hits, list):
                raise CheckpointError("recall_search hits is not a list")
            base["hit_count"] = len(hits)
            base["verdicts"] = [
                _clip(hit.get("verdict", ""), 64)
                for hit in hits
                if isinstance(hit, Mapping)
            ]
            ok_hits = [
                hit for hit in hits
                if isinstance(hit, Mapping) and str(hit.get("verdict")) == "ok"
            ][:MAX_HITS]
            base["ok_hit_count"] = len(ok_hits)
            base["sources"] = [_clip(hit.get("source", ""), 300) for hit in ok_hits]
            base["abstained"] = bool(result.get("abstained"))
            base["status"] = "abstained" if base["abstained"] else "ok"
            lines = [
                "RE-call pre-mutation checkpoint. The proposed mutation has not run.",
                (
                    "Use only the current trusted evidence below. Reconcile it with current code "
                    "and tests before retrying; current code and tests win if they conflict."
                ),
                f"Memory advice: {_clip(result.get('advice', ''), 500)}",
            ]
            if base["abstained"] or not ok_hits:
                lines.append(
                    "Memory abstained or supplied no usable evidence. It does not support changing "
                    "the plan; inspect current code and tests rather than guessing."
                )
            else:
                lines.append("Trusted evidence:")
                for index, hit in enumerate(ok_hits, 1):
                    lines.extend(
                        [
                            f"[{index}] {_clip(hit.get('text', ''), HIT_TEXT_LIMIT)}",
                            f"Source: {hit.get('source', '')}",
                        ]
                    )
            body = "\n".join(lines)
        except Exception as error:  # noqa: BLE001 - any retrieval failure must fail closed
            base["status"] = "error"
            base["error_type"] = type(error).__name__
            body = (
                "RE-call pre-mutation checkpoint failed before the proposed mutation ran. "
                "No memory claim is supported. Inspect current code and tests before retrying."
            )
    else:
        raise ValueError(f"unknown checkpoint mode {mode!r}")
    reason = _reason_with_marker(base, body)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            raise TypeError("hook input is not an object")
        output = run_checkpoint(
            payload,
            mode=os.environ.get("AMB_PUBLIC_CHECKPOINT_MODE", ""),
            task=os.environ.get("AMB_PUBLIC_CHECKPOINT_TASK", ""),
            sentinel=os.environ.get(
                "AMB_PUBLIC_CHECKPOINT_SENTINEL", "/tmp/amb-recall-checkpoint.done"
            ),
            broker_call=broker_search,
        )
        if output is not None:
            sys.stdout.write(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
        return 0
    except Exception as error:  # noqa: BLE001 - a hook must report failure, never crash silently
        sys.stderr.write(f"checkpoint hook failed: {type(error).__name__}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
