"""Rebuild a run's records from its saved transcripts when the runner died before writing them.

    python scripts/salvage.py --run-id <run-id> --arms recall,bare

`run_claude_case` writes each session's stream to disk **before** parsing it, so a runner that
dies mid-run loses its index but not its evidence: the transcripts are all there. This turns them
back into records, minus the cells that never finished.

**It writes `records.salvaged.jsonl`, never `records.jsonl`.** `scripts/pilot.py` appends each
CHECKER-GRADED record to `records.jsonl` with fsync as the run proceeds, exactly so a dying run
keeps every finished cell. A salvaged record has no checker verdict: `build_record` sets `success`
from "the session reached its result event", which is a different question from "the task was
solved". Writing one over the other would silently promote graded failures to successes in the
artifact that backs published numbers, so this refuses to run when `records.jsonl` exists.

Used in anger on 2026-08-21 in the source project, when a headline run's process died at 71 of
100 sessions.

**Two things are different from a completed run, and both are recorded in the artifact rather than
smoothed over.**

`wall_time_ms` normally comes from the runner timing the subprocess. That measurement died with the
process, so this uses the session's own `duration_ms` from its result event. The two are not the
same: the runner's figure includes process spawn and MCP server startup, the session's does not.
Every salvaged record carries `metadata.salvaged = true` and `metadata.wall_time_source =
"stream_duration_ms"` so a reader can tell which they are looking at, and so the two are never
silently pooled.

A cell is only usable if EVERY arm finished. Incomplete survivors are reported and excluded,
because the whole design is paired and a lone arm is not a comparison.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.claude_exec import (
    ClaudeExecConfig,
    build_record,
    parse_claude_stream_json,
    result_event,
)
from harness.io import write_jsonl
from harness.schema import DEFAULT_MEMORY_TOOL_PREFIX
from harness.tasks import discover_tasks

# `harness.gate.admit_cells` IS available (scripts/pilot.py, smoke.py and diagnostic.py all use
# it), but it needs the run's AdmissionSignal roster, which describes how the run was CONFIGURED
# and does not survive in the transcripts. So this script still writes every complete cell
# ungated, and says so in the artifact. Run the gate before analysing these records.


def split_name(name: str, arms: tuple[str, ...]) -> tuple[str, int, str] | None:
    """`ts-tz-utc.s2.recall.jsonl.gz` -> `("ts-tz-utc", 2, "recall")`.

    Matches on the arm suffix rather than splitting on dots, because a task id may legitimately
    contain a dot. `harness.claude_exec` names streams `<task>.s<seed>.<arm>.jsonl.gz`; an older
    stream with no seed segment parses as seed 0 rather than being dropped.
    """

    base = name.removesuffix(".jsonl.gz")
    for arm in arms:
        if not base.endswith(f".{arm}"):
            continue
        remainder = base[: -len(arm) - 1]
        head, _, seed_part = remainder.rpartition(".")
        if head and re.fullmatch(r"s\d+", seed_part):
            return head, int(seed_part[1:]), arm
        return remainder, 0, arm
    return None


def refuse_if_records_exist(artifacts: Path) -> None:
    """Refuse to salvage over an artifact the runner already graded.

    A salvaged record's `success` means "the session completed", not "the checker passed", so
    overwriting the runner's graded records.jsonl would rewrite failures as successes.
    """

    existing = artifacts / "records.jsonl"
    if existing.exists():
        raise SystemExit(
            f"{existing} already exists and holds checker-graded records; salvage would replace "
            "them with ungraded ones. Move it aside first if you really mean to rebuild."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--arms",
        required=True,
        help="comma-separated arm names the run used; each stream file is named "
        "<task_id>.s<seed>.<arm>.jsonl.gz",
    )
    parser.add_argument(
        "--tasks",
        default=None,
        help="optional JSONL of task rows; without it, prompts are read from tasks/<id>/task.json",
    )
    parser.add_argument("--memory-tool-prefix", default=DEFAULT_MEMORY_TOOL_PREFIX)
    args = parser.parse_args()

    arms = tuple(arm.strip() for arm in args.arms.split(",") if arm.strip())
    if len(arms) < 2:
        raise SystemExit("--arms needs at least two arm names; a lone arm is not a comparison")

    artifacts = REPO_ROOT / "results" / args.run_id
    streams = artifacts / "streams"
    if not streams.is_dir():
        raise SystemExit(f"no streams at {streams}")
    refuse_if_records_exist(artifacts)

    if args.tasks:
        tasks = {
            row["task_id"]: row
            for row in (
                json.loads(line)
                for line in Path(args.tasks).read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        }
    else:
        tasks = {
            task.task_id: {"task_id": task.task_id, "user_input": task.prompt}
            for task in discover_tasks()
        }

    records = []
    unreadable: list[str] = []
    for path in sorted(streams.iterdir()):
        parsed = split_name(path.name, arms)
        if parsed is None:
            continue
        task_id, seed, arm = parsed
        base = task_id.split("#")[0]
        row = dict(tasks.get(base, {}))
        row["task_id"] = task_id
        row["base_task_id"] = base
        row["seed"] = seed
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
            stream = handle.read()
        try:
            events = parse_claude_stream_json(stream)
            result = result_event(events)
            # The runner's own timing died with it; the session's self-reported duration is the
            # only wall time that survived, and it measures a slightly different thing.
            duration = (result or {}).get("duration_ms")
            # strict_mcp_config=False only because this config never launches anything: it
            # exists to carry the tool prefix into build_record. Leaving it strict trips a real
            # guard that refuses "strict, but no servers", which is the right guard for a launch
            # and meaningless for a parse.
            config = ClaudeExecConfig(
                model="salvaged",
                memory_tool_prefix=args.memory_tool_prefix,
                strict_mcp_config=False,
            )
            record = build_record(
                row,
                arm,
                stream=stream,
                wall_time_ms=float(duration) if duration is not None else 0.0,
                config=config,
                command=("salvaged",),
            )
            payload = record.to_dict()
            payload["metadata"] = {
                **payload.get("metadata", {}),
                "salvaged": True,
                "stream_path": path.name,
                "wall_time_source": "stream_duration_ms",
            }
            if duration is None:
                # Never 0.0: an unmeasured session must not read as an instant one.
                payload["wall_time_ms"] = None
            records.append(record.__class__.from_mapping(payload))
        except Exception as error:  # noqa: BLE001 - one bad transcript must not lose the rest
            unreadable.append(f"{path.name}: {type(error).__name__}: {error}"[:200])

    # Key on the CELL, (task_id, seed), not the task. Before the seed was parsed out of the
    # stream name it stayed inside task_id, so keying on task_id alone was accidentally per-cell;
    # once the seed moved to its own field that key would have pooled every seed of a task and
    # admitted a seed whose partner arm never finished. A lone arm is not a comparison.
    by_cell: dict[tuple[str, int], set[str]] = defaultdict(set)
    for record in records:
        by_cell[(record.task_id, record.seed)].add(record.arm)
    complete = {cell for cell, seen in by_cell.items() if set(arms) <= seen}
    orphans = sorted(f"{task}.s{seed}" for task, seed in set(by_cell) - complete)
    paired = [r for r in records if (r.task_id, r.seed) in complete]

    print(f"salvaged {len(records)} records from {len(list(streams.iterdir()))} streams")
    print(f"wrote {(artifacts / 'records.salvaged.jsonl').name} (ungraded; run the gate before analysis)")
    print(f"complete cells: {len(complete)}")
    if orphans:
        print(f"incomplete (excluded, an arm never finished): {len(orphans)} -> {orphans[:6]}")
    if unreadable:
        print(f"unreadable transcripts: {len(unreadable)}")
        for line in unreadable[:5]:
            print(f"  {line}")

    # TODO(port): the source script ran `gate.admit_pairs` here, discarding cells whose treatment
    # could not be proven applied, and then wrote summary/overhead/trap-score artifacts. Until
    # `harness.gate` and the analysis tools are ported, every complete cell is written and the
    # artifact says so.
    admitted = paired

    write_jsonl(artifacts / "records.salvaged.jsonl", admitted)
    salvage: dict[str, Any] = {
        "run_id": args.run_id,
        "salvaged": True,
        "reason": "the runner process died mid-run; records rebuilt from the saved streams",
        "arms": list(arms),
        "streams_seen": len(list(streams.iterdir())),
        "records_rebuilt": len(records),
        "complete_cells": len(complete),
        "incomplete_excluded": orphans,
        "unreadable": unreadable,
        "gate_applied": False,
        "gate_note": "harness.gate.admit_cells needs the run's AdmissionSignal roster, which "
        "does not survive in the transcripts; no availability gate was applied, run it before "
        "analysing these records",
        "success_semantics": "the session reached its result event; NO checker was re-run, so "
        "these flags are not task verdicts",
        "records_path": "records.salvaged.jsonl",
        "wall_time_source": "stream_duration_ms (the runner's own timing did not survive)",
    }
    (artifacts / "salvage.json").write_text(json.dumps(salvage, indent=2), encoding="utf-8")

    # environment.json is normally written by the runner at the end of a run, so a died run has
    # none. Most of it is recoverable from the transcripts themselves, which is better than a
    # placeholder: the CLI version and the MCP server status are recorded in every session's init
    # event. What cannot be recovered is marked null rather than guessed.
    if not (artifacts / "environment.json").exists():
        version, servers = None, None
        for record in admitted:
            meta = record.metadata or {}
            version = version or meta.get("claude_code_version")
            servers = servers or meta.get("mcp_servers")
        environment = {
            "reconstructed_from_transcripts": True,
            "note": "the runner died before writing environment.json; these fields come from the "
                    "sessions' own init events, and anything absent there is null, not guessed",
            "claude_code_version": version,
            "mcp_servers": servers,
        }
        (artifacts / "environment.json").write_text(
            json.dumps(environment, indent=2), encoding="utf-8"
        )
    print(f"\nwritten: {artifacts / 'records.jsonl'} and salvage/environment artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
