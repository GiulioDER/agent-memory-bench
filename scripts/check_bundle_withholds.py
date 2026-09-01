"""Apparatus check 3 of preregistration 025: does `recall_evidence` withhold anything HERE?

Preregistration 025's treatment is that a gate which WITHHOLDS beats one that ANNOTATES.
`recall_search` returns hits each carrying a trust verdict; `recall_evidence` returns only the
passages the trust layer cleared, and an empty bundle when it abstains.

⚠️ **On a corpus with no lineage the difference can be nothing.** `bench-official-002` declares no
successors, so no hit can be marked `superseded` and the only filter left is `low_confidence`. If
the bundle turns out to equal the hits on every query, the treatment is INERT on this corpus and
every endpoint downstream is uninterpretable: the run would compare an arm against itself and
produce a clean, plausible null. Amendment 1 registers that as the cancel condition, and this
script is what decides it, before any credit is spent.

That is the `the-apparatus-fails-toward-a-finding` shape. A null is the cheapest result an
instrument can fabricate, so the treatment is asserted LIVE rather than the baseline reproduced.

## The queries

Real agent queries, read from a completed run's records, not authored ones.
`recall-abstention-is-calibrated-out-of-distribution` measured why that matters: authored questions
average 10.8 words and agent queries 7.1, they are different distributions, and the whole
abstention inversion lives in the gap. An authored probe here would test a query shape this run
will never issue.

Exit 0 when the bundle withholds at least one returned hit on more than `--min-rate` of the probe
queries (registered prediction 5b: 0.30). Non-zero otherwise, which means CANCEL.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def agent_queries(records: Path, limit: int) -> list[str]:
    """Distinct recall_search queries the agent actually issued, in first-seen order."""

    seen: list[str] = []
    if not records.is_file():
        return seen
    for line in records.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        # `tool_calls`, keyed on the tool PREFIX, exactly as harness/reached.py reads them. There
        # is no `memory_calls` field: I guessed one, and the guess returned an empty list rather
        # than an error, which is the shape `my-parse-error-is-indistinguishable-from-a-product-
        # defect` warns about. Verified against a real record before this was written.
        for call in row.get("tool_calls") or []:
            if "recall_search" not in str(call.get("name") or ""):
                continue
            text = str((call.get("args") or {}).get("query") or "").strip()
            if text and text not in seen:
                seen.append(text)
                if len(seen) >= limit:
                    return seen
    return seen


class Server:
    """One stdio MCP session. Deliberately not reusing harness.mcp_probe: that lists tools and
    stops, and the question here is what two tools RETURN."""

    def __init__(self, config_path: Path, server_name: str) -> None:
        server = json.loads(config_path.read_text(encoding="utf-8"))["mcpServers"][server_name]
        self.proc = subprocess.Popen(
            [str(server["command"]), *[str(a) for a in server["args"]]],
            env={str(k): str(v) for k, v in server.get("env", {}).items()},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._id = 0

    def call(self, method: str, params: dict, timeout_s: float = 180.0) -> dict:
        self._id += 1
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}) + "\n"
        )
        self.proc.stdin.flush()
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError(f"server closed during {method}")
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == self._id:
                return msg
        raise RuntimeError(f"timed out waiting for {method}")

    def tool(self, name: str, arguments: dict) -> dict:
        msg = self.call("tools/call", {"name": name, "arguments": arguments})
        if "error" in msg:
            raise RuntimeError(f"{name}: {msg['error']}")
        content = msg["result"]["content"]
        return json.loads(content[0]["text"])

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.wait(timeout=15)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            self.proc.kill()


def ids(items) -> set[str]:
    out = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        key = item.get("chunk_id") or item.get("id") or str(item.get("text", ""))[:120]
        if key:
            out.add(str(key))
    return out


def bundle_items(response: dict) -> list:
    """The cleared passages, wherever this server version puts them.

    Tried in order rather than assumed: `recall_evidence`'s exact field was NOT verified against a
    live response when this was written, only its documented contract ("returns only passages the
    trust layer cleared"). So the shape is discovered, and the real keys are printed on
    the first call so the run log records what was actually there.
    """

    for path in (("trusted_evidence", "items"), ("items",), ("evidence", "items"), ("hits",)):
        node = response
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, list):
            return node
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--namespace", required=True)
    ap.add_argument("--records", default="")
    ap.add_argument("--queries", type=int, default=12)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--min-rate", type=float, default=0.30)
    args = ap.parse_args()

    records = Path(args.records) if args.records else (
        Path.home() / "amb-repo" / "results" / "protocol-025-superseded" / "records.jsonl"
    )
    queries = agent_queries(records, args.queries)
    if not queries:
        print(f"REFUSE: no agent queries found in {records}")
        print("  An authored fallback is deliberately NOT used: it would probe a query shape this")
        print("  run never issues, which is the distribution error this project already measured.")
        return 2
    print(f"probe queries: {len(queries)} distinct, from {records.name}")

    from adapters.recall.adapter import RecallAdapter

    staging = REPO / "results" / ".ingest-staging"
    adapter = RecallAdapter(staging, REPO / "adapters" / "_shared" / "memory_protocol.md")
    withheld_queries = 0
    abstained = 0
    examined = 0
    with tempfile.TemporaryDirectory() as temp:
        spec = adapter.build(Path(temp) / "check", args.namespace)
        server = Server(Path(spec.mcp_config), str(adapter.config["server_name"]))
        try:
            server.call(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "amb-bundle-check", "version": "1"},
                },
            )
            for query in queries:
                try:
                    hits = server.tool("recall_search", {"query": query, "k": args.k})
                    bundle = server.tool("recall_evidence", {"query": query, "k": args.k})
                except RuntimeError as error:
                    print(f"  ! {query[:56]!r}: {error}")
                    continue
                examined += 1
                hit_ids = ids(hits.get("hits"))
                if examined == 1:
                    print(f"  [shape] recall_evidence keys: {sorted(bundle)}")
                item_ids = ids(bundle_items(bundle))
                missing = hit_ids - item_ids
                decision = bundle.get("decision")
                if decision == "abstain" or not item_ids:
                    abstained += 1
                if missing:
                    withheld_queries += 1
                print(
                    f"  {len(hit_ids)} hits -> {len(item_ids)} items"
                    f"  withheld {len(missing)}  decision {decision!r}"
                    f"  | {query[:48]!r}"
                )
        finally:
            server.close()

    if not examined:
        print("REFUSE: no query was answered by both tools")
        return 3

    rate = withheld_queries / examined
    print(
        f"\nwithheld on {withheld_queries}/{examined} = {rate:.3f} of queries "
        f"(registered floor {args.min_rate}); bundle empty or abstained on {abstained}"
    )
    if rate > args.min_rate:
        print("APPARATUS CHECK 3: PASS. The treatment is live on this corpus.")
        return 0
    print("APPARATUS CHECK 3: FAIL. The bundle does not withhold enough for the arms to differ.")
    print("  Amendment 1 registers this as CANCEL: with no lineage the only filter is")
    print("  low_confidence, and if it rarely fires the evidence arm is the protocol arm.")
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
