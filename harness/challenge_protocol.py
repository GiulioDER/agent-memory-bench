"""The JSON line protocol between the fixed evaluator and an AMB memory sidecar."""

from __future__ import annotations

import json
import socket
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ADAPTER_API = "amb-challenge-adapter-v1"
METHODS = frozenset({"health", "search", "reset"})
MAX_MESSAGE_BYTES = 1_048_576
MAX_QUERY_CHARS = 32_768


class ChallengeProtocolError(ValueError):
    """A sidecar request or response violates the public adapter protocol."""


def make_request(request_id: str, method: str, params: Mapping[str, Any] | None = None) -> bytes:
    """Encode one bounded request line for the adapter socket."""

    if not request_id or not isinstance(request_id, str):
        raise ChallengeProtocolError("request id must be a non empty string")
    if method not in METHODS:
        raise ChallengeProtocolError(f"unsupported adapter method: {method!r}")
    if params is not None and not isinstance(params, Mapping):
        raise ChallengeProtocolError("adapter request params must be an object")
    normalized = dict(params or {})
    if method == "search":
        query = normalized.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ChallengeProtocolError("search params need a non empty query")
        if len(query) > MAX_QUERY_CHARS:
            raise ChallengeProtocolError("search query exceeds the character limit")
        task_id = normalized.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ChallengeProtocolError("search params need a non empty task_id")
        limit = normalized.get("limit", 10)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ChallengeProtocolError("search limit must be an integer from 1 to 100")
    elif method == "reset":
        task_id = normalized.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ChallengeProtocolError("reset params need a non empty task_id")

    payload: dict[str, Any] = {
        "api": ADAPTER_API,
        "id": request_id,
        "method": method,
        "params": normalized,
    }
    encoded = (json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    if len(encoded) > MAX_MESSAGE_BYTES:
        raise ChallengeProtocolError("adapter request exceeds the message size limit")
    return encoded


def parse_response(raw: bytes | str, request_id: str) -> dict[str, Any]:
    """Decode one response and require it to match the request id and API version."""

    if isinstance(raw, bytes):
        if len(raw) > MAX_MESSAGE_BYTES:
            raise ChallengeProtocolError("adapter response exceeds the message size limit")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ChallengeProtocolError("adapter response is not UTF-8") from error
    else:
        text = raw
        if len(text.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise ChallengeProtocolError("adapter response exceeds the message size limit")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ChallengeProtocolError("adapter response is not valid JSON") from error
    if not isinstance(payload, dict):
        raise ChallengeProtocolError("adapter response must be an object")
    if payload.get("api") != ADAPTER_API:
        raise ChallengeProtocolError("adapter response has the wrong API version")
    if payload.get("id") != request_id:
        raise ChallengeProtocolError("adapter response id does not match the request")
    if not isinstance(payload.get("ok"), bool):
        raise ChallengeProtocolError("adapter response must contain a boolean ok field")
    if payload["ok"]:
        if not isinstance(payload.get("result"), dict):
            raise ChallengeProtocolError("successful adapter response needs an object result")
    elif not isinstance(payload.get("error"), dict):
        raise ChallengeProtocolError("failed adapter response needs an object error")
    return payload


def request_unix_socket(
    socket_path: str,
    request_id: str,
    method: str,
    params: Mapping[str, Any] | None = None,
    *,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """Send one request over one Unix socket connection and parse its response."""

    if timeout_seconds <= 0:
        raise ChallengeProtocolError("timeout_seconds must be positive")
    if not hasattr(socket, "AF_UNIX"):
        raise ChallengeProtocolError("Unix sockets are unavailable on this host")
    request = make_request(request_id, method, params)
    try:
        socket_stat = Path(socket_path).lstat()
        if stat.S_ISLNK(socket_stat.st_mode) or not stat.S_ISSOCK(socket_stat.st_mode):
            raise ChallengeProtocolError("adapter socket path is not a Unix socket")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
            channel.settimeout(timeout_seconds)
            channel.connect(socket_path)
            channel.sendall(request)
            response = bytearray()
            while len(response) <= MAX_MESSAGE_BYTES:
                chunk = channel.recv(min(65_536, MAX_MESSAGE_BYTES + 1 - len(response)))
                if not chunk:
                    break
                response.extend(chunk)
                if b"\n" in chunk:
                    break
    except OSError as error:
        raise ChallengeProtocolError(f"could not contact adapter socket: {error}") from error
    if len(response) > MAX_MESSAGE_BYTES:
        raise ChallengeProtocolError("adapter response exceeds the message size limit")
    return parse_response(bytes(response), request_id)
