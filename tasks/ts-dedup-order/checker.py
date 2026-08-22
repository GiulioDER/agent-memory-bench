"""Run the produced dedupe.py against oracle events the sandbox never saw.

Content comparison is parsed, not byte-wise: the convention under test is WHICH occurrence
survives (the first) and in what order, not how the script formats its JSON.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def _parse_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "dedupe.py"
    if not script.is_file():
        return False, "dedupe.py was never written"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "dedupe.py")
        shutil.copyfile(oracle_dir / "events.jsonl", stage / "events.jsonl")
        completed = run_bounded(
            [sys.executable, "dedupe.py"], cwd=stage, timeout_s=60.0
        )
        if completed.returncode != 0:
            return False, f"dedupe.py exited {completed.returncode}: {completed.stderr[-500:]}"
        produced_path = stage / "deduped.jsonl"
        if not produced_path.is_file():
            return False, "dedupe.py ran but wrote no deduped.jsonl"
        try:
            produced = _parse_jsonl(produced_path)
        except json.JSONDecodeError as error:
            return False, f"deduped.jsonl is not JSON lines: {error}"

    expected = _parse_jsonl(oracle_dir / "expected_deduped.jsonl")
    if produced == expected:
        return True, f"{len(produced)} events, first occurrences kept in order"
    kept = {event.get("event_id"): event.get("status") for event in produced}
    want = {event.get("event_id"): event.get("status") for event in expected}
    return False, f"kept occurrences differ from the convention: got {kept}, expected {want}"
