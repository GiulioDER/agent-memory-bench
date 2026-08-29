"""Check the labelled query set against the live corpus, through the arm's own MCP server.

A mislabelled NEGATIVE is the dangerous kind. Calibration fits the threshold on the gap between
answerable and unanswerable scores, so a "unanswerable" query the corpus can actually answer pulls
the threshold DOWN and makes the arm answer where it should abstain. There is no way to find one by
reading the query; the corpus has to be asked.

This asks through `recall_search` on the MCP server, not through a Python API, because that is the
path the benchmark's recall arm uses and a score measured anywhere else is a different number.

    python calibration/validate_queryset.py <path-to-recall.mcp.json>

It writes nothing and changes nothing.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QUERY_SET = REPO / "calibration" / "abstention-queryset-v1.json"


def _top_score(payload: object) -> float | None:
    """The best cosine in a recall_search reply, whatever shape it arrived in."""

    text = payload if isinstance(payload, str) else json.dumps(payload)
    best: float | None = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    stack = [parsed]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key in ("cosine", "score", "similarity"):
                value = node.get(key)
                if isinstance(value, (int, float)):
                    best = float(value) if best is None else max(best, float(value))
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return best


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    server = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["mcpServers"]["recall"]
    entries = json.loads(QUERY_SET.read_text(encoding="utf-8"))

    proc = subprocess.Popen(
        [str(server["command"]), *[str(a) for a in server["args"]]],
        env={str(k): str(v) for k, v in server["env"].items()},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        # Explicit, because Popen defaults to the locale codec and that is cp1252 on
        # Windows: a single non-ASCII byte from the server raises UnicodeDecodeError
        # inside readline and looks like a dead server.
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def call(payload: dict) -> dict:
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()
        while True:
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("server closed stdout")
            if line.strip():
                return json.loads(line)

    call(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "queryset-validator", "version": "1"},
            },
        }
    )
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    proc.stdin.flush()

    scored: list[tuple[dict, float | None]] = []
    for index, entry in enumerate(entries, start=2):
        reply = call(
            {
                "jsonrpc": "2.0",
                "id": index,
                "method": "tools/call",
                "params": {"name": "recall_search", "arguments": {"query": entry["query"]}},
            }
        )
        content = reply.get("result", {}).get("content", [])
        text = content[0].get("text") if content else None
        scored.append((entry, _top_score(text)))

    proc.terminate()

    pos = [s for e, s in scored if e["answerable"] and s is not None]
    neg = [s for e, s in scored if not e["answerable"] and s is not None]
    print(f"answerable   n={len(pos)}  median {statistics.median(pos):.3f}  min {min(pos):.3f}")
    print(f"unanswerable n={len(neg)}  median {statistics.median(neg):.3f}  max {max(neg):.3f}")
    overlap = [
        (e["id"], e["query"], s)
        for e, s in scored
        if s is not None and not e["answerable"] and s >= min(pos)
    ]
    print(f"\nnegatives scoring at or above the WEAKEST positive: {len(overlap)}")
    for qid, query, score in sorted(overlap, key=lambda r: -r[2]):
        print(f"  {qid} {score:.3f}  {query}")
    weak = [
        (e["id"], e["query"], s)
        for e, s in scored
        if s is not None and e["answerable"] and s <= max(neg)
    ]
    print(f"\npositives scoring at or below the STRONGEST negative: {len(weak)}")
    for qid, query, score in sorted(weak, key=lambda r: r[2]):
        print(f"  {qid} {score:.3f}  {query}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
