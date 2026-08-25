"""Validate the pilot-004 placebo bundles without making model calls.

    python -m scripts.placebo_preflight
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.placebo import length_metadata  # noqa: E402
from harness.tasks import discover_tasks  # noqa: E402
from scripts.pilot import build_bundles, recall_instruction  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="optional JSON report path")
    args = parser.parse_args()

    tasks = [task for task in discover_tasks() if task.task_id.startswith("ts-")]
    report: dict[str, object] = {
        "tasks": len(tasks),
        "seeds": 3,
        "arms": ["bare", "placebo", "claude_md", "recall"],
        "sessions": len(tasks) * 3 * 4,
        "placebo_generator": hashlib.sha256(
            (REPO / "harness" / "placebo.py").read_bytes()
        ).hexdigest(),
        "tasks_by_id": {},
    }
    mismatches: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agent-memory-bench-placebo-") as temp:
        root = Path(temp)
        instruction = recall_instruction("skill")
        for task in tasks:
            bundles = build_bundles(task, root / task.task_id, instruction)
            reference = bundles["claude_md"].read_text(encoding="utf-8")
            placebo = bundles["placebo"].read_text(encoding="utf-8")
            metadata = length_metadata(reference, placebo)
            if not metadata["match"]:
                mismatches.append(task.task_id)
            report["tasks_by_id"][task.task_id] = {
                **metadata,
                "reference_sha256": hashlib.sha256(reference.encode("utf-8")).hexdigest(),
                "placebo_sha256": hashlib.sha256(placebo.encode("utf-8")).hexdigest(),
            }

    report["all_match"] = not mismatches
    report["mismatches"] = mismatches
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
