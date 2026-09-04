"""Build the committed development oracle manifest from the existing corpus.

One bundle per task: the exact evidence the `oracle_memory` ceiling arm is handed, so the run has
a number for "what if retrieval were perfect".

⚠️ **A task whose fact is DISTRIBUTED needs every shard in its bundle, not the first one.** This
script used to read `sessions/<task_id>/p01.jsonl` and nothing else, which is correct while every
task states its whole fact in one session and silently wrong the moment one does not: on
`xs-evolve-lease` it would have handed the ceiling arm the April session, whose 90-second interval
was superseded twice, and the arm with perfect retrieval would have been the arm guaranteed to
fail. A shard's `validity` and `supersedes` now come from the task's declared shard order, which is
what `harness/memory_prompt.py` renders as "Currency:" beside each item.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.tasks import load_task


def _evidence(source: Path, source_path: str) -> tuple[str, str]:
    rows = [
        json.loads(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    users = [row for row in rows if row.get("role") == "user" and row.get("content")]
    if not users:
        raise SystemExit(f"no user evidence in {source_path}")
    row = users[-1]
    return str(row["content"]), str(row.get("ts", "unknown"))[:10]


def _item(task_id: str, source_path: str, suffix: str, validity: str, supersedes: str | None):
    source = ROOT / "corpus" / source_path
    evidence, recorded_at = _evidence(source, source_path)
    return {
        "memory_id": f"mem_{task_id}{suffix}",
        "source_path": source_path,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "evidence_text": evidence,
        "recorded_at": recorded_at,
        "validity": validity,
        "supersedes": supersedes,
    }


def main() -> None:
    corpus = json.loads((ROOT / "corpus" / "manifest.json").read_text(encoding="utf-8"))
    records: list[dict] = []
    for task_path in sorted((ROOT / "tasks").glob("*/task.json")):
        raw = json.loads(task_path.read_text(encoding="utf-8"))
        raw["memory_bundle_id"] = (
            None if raw.get("kind", "primary") == "control" else f"bundle_{raw['task_id']}"
        )
        task_path.write_text(
            json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        if raw["memory_bundle_id"] is None:
            continue
        task_id = raw["task_id"]
        task = load_task(task_path.parent)

        if task.synthesis is None:
            sources = [(f"sessions/{task_id}/p01.jsonl", "", "current", None)]
        else:
            shards = task.synthesis.shards
            evolving = task.synthesis.shape == "evolve"
            sources = []
            for index, shard in enumerate(shards):
                last = index == len(shards) - 1
                previous = shards[index - 1].precursor if index else None
                sources.append(
                    (
                        f"sessions/{task_id}/{shard.precursor}.jsonl",
                        f"_{shard.precursor}",
                        # Only `evolve` retires anything: a join's two halves are both current.
                        "current" if last or not evolving else "superseded",
                        f"mem_{task_id}_{previous}" if evolving and previous else None,
                    )
                )
            present = [path for path, *_ in sources if path in corpus["sessions"]]
            if not present:
                print(f"  skip {task_id}: no shard session recorded yet")
                continue
            if len(present) != len(sources):
                raise SystemExit(
                    f"{task_id} is half recorded ({len(present)} of {len(sources)} shards). A "
                    f"bundle built from part of a distributed fact is a ceiling arm that cannot "
                    f"reach the ceiling; record the rest before rebuilding"
                )

        items = []
        for source_path, suffix, validity, supersedes in sources:
            if source_path not in corpus["sessions"]:
                raise SystemExit(f"no corpus source for {task_id}: {source_path}")
            items.append(_item(task_id, source_path, suffix, validity, supersedes))
        records.append(
            {"bundle_id": raw["memory_bundle_id"], "task_id": task_id, "items": items}
        )

    out = ROOT / "corpus" / "oracle_memory" / "bundles.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records
        ),
        encoding="utf-8",
    )
    print(f"wrote {len(records)} development oracle bundles to {out}")


if __name__ == "__main__":
    main()
