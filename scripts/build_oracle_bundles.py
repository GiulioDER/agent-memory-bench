"""Build the committed development oracle manifest from the existing corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    corpus = json.loads((ROOT / "corpus" / "manifest.json").read_text(encoding="utf-8"))
    records: list[dict] = []
    for task_path in sorted((ROOT / "tasks").glob("*/task.json")):
        task = json.loads(task_path.read_text(encoding="utf-8"))
        task["memory_bundle_id"] = None if task.get("kind", "primary") == "control" else f"bundle_{task['task_id']}"
        task_path.write_text(json.dumps(task, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if task["memory_bundle_id"] is None:
            continue
        task_id = task["task_id"]
        source_path = f"sessions/{task_id}/p01.jsonl"
        source = ROOT / "corpus" / source_path
        if source_path not in corpus["sessions"]:
            raise SystemExit(f"no corpus source for {task_id}: {source_path}")
        rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        users = [row for row in rows if row.get("role") == "user" and row.get("content")]
        if not users:
            raise SystemExit(f"no user evidence in {source_path}")
        row = users[-1]
        evidence = str(row["content"])
        item = {
            "memory_id": f"mem_{task_id}",
            "source_path": source_path,
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "evidence_text": evidence,
            "recorded_at": str(row.get("ts", "unknown"))[:10],
            "validity": "current",
            "supersedes": None,
        }
        records.append({"bundle_id": task["memory_bundle_id"], "task_id": task_id, "items": [item]})
    out = ROOT / "corpus" / "oracle_memory" / "bundles.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    print(f"wrote {len(records)} development oracle bundles to {out}")


if __name__ == "__main__":
    main()
