"""Minimal dependency free AMB adapter example for smoke testing the socket contract."""

from __future__ import annotations

import argparse
import json
import os
import socket
from pathlib import Path
from typing import Any

from harness.challenge_protocol import ADAPTER_API


def _load_corpus(corpus: Path) -> tuple[tuple[str, str], ...]:
    return tuple(
        (path.relative_to(corpus).as_posix(), path.read_text(encoding="utf-8", errors="replace"))
        for path in sorted(candidate for candidate in corpus.rglob("*") if candidate.is_file())
    )


def _corpus_hits(corpus: tuple[tuple[str, str], ...], query: str, limit: int) -> list[dict[str, Any]]:
    terms = {term.lower() for term in query.split() if term.strip()}
    candidates: list[tuple[int, str, str]] = []
    for source_id, text in corpus:
        score = sum(text.lower().count(term) for term in terms)
        if score:
            candidates.append((score, source_id, text))
    candidates.sort(key=lambda row: (-row[0], row[1]))
    return [
        {"source_id": source_id, "text": text, "score": float(score), "rank": rank}
        for rank, (score, source_id, text) in enumerate(candidates[:limit], start=1)
    ]


def _response(request_id: str, *, result: dict[str, Any] | None = None, error: str | None = None) -> bytes:
    payload: dict[str, Any] = {"api": ADAPTER_API, "id": request_id, "ok": error is None}
    if error is None:
        payload["result"] = result or {}
    else:
        payload["error"] = {"code": "adapter_error", "message": error}
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode()


def serve(socket_path: Path, corpus: Path, *, empty: bool = False) -> None:
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists():
        socket_path.unlink()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(socket_path))
        server.listen(16)
        cached_corpus = _load_corpus(corpus)
        while True:
            connection, _ = server.accept()
            with connection:
                request = None
                try:
                    received = bytearray()
                    while len(received) <= 1_048_576:
                        chunk = connection.recv(min(64 * 1024, 1_048_577 - len(received)))
                        if not chunk:
                            break
                        received.extend(chunk)
                        if b"\n" in chunk:
                            break
                    if len(received) > 1_048_576 or b"\n" not in received:
                        raise ValueError("request must be one newline terminated JSON message")
                    line, separator, trailing = bytes(received).partition(b"\n")
                    if not separator or trailing.strip():
                        raise ValueError("request must contain exactly one JSON message")
                    request = json.loads(line.decode("utf-8"))
                    if not isinstance(request, dict):
                        raise TypeError("request must be an object")
                    request_id = request["id"]
                    method = request["method"]
                    params = request.get("params", {})
                    if method == "health":
                        result = {"ready": True}
                    elif method == "reset":
                        result = {}
                    elif method == "search":
                        hits = [] if empty else _corpus_hits(cached_corpus, params["query"], params.get("limit", 10))
                        result = {
                            "hits": hits,
                            "abstained": not hits,
                            "usage": {"input_tokens": 0, "output_tokens": 0},
                        }
                    else:
                        raise ValueError(f"unsupported method: {method}")
                    connection.sendall(_response(request_id, result=result))
                except Exception as error:  # noqa: BLE001 - example server returns protocol errors
                    request_id = request.get("id", "unknown") if isinstance(request, dict) else "unknown"
                    connection.sendall(_response(request_id, error=str(error)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path, default=Path(os.environ.get("AMB_ADAPTER_SOCKET", "adapter.sock")))
    parser.add_argument("--corpus", type=Path, default=Path(os.environ.get("AMB_CORPUS", "corpus")))
    parser.add_argument("--empty", action="store_true", help="deliberately return no memory hits")
    args = parser.parse_args()
    serve(args.socket, args.corpus, empty=args.empty)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
