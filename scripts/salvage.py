"""Rebuild a run's records from its saved transcripts when the runner died before writing them.

    python scripts/salvage.py --run-id <run-id> --arms recall,bare

`run_claude_case` writes each session's stream to disk **before** parsing it, and the runner only
writes `records.jsonl` at the very end. So a runner that dies mid-run loses its index but not its
evidence: the transcripts are all there. This turns them back into records and writes the same
records artifact a completed run would, minus the cells that never finished.

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

# TODO(port): the source script also imported `arms.BASE_TOOLS` (only fed
# `ClaudeExecConfig.allowed_tools` on a parse-only config, where it changes nothing),
# `gate.admit_pairs` (the availability gate), `summarize.summarize_pairs` /
# `summarize_recall_overhead` and `traps.score_record`. None of those modules are ported yet, so
# this script admits every complete cell without the gate and writes only `records.jsonl` and
# `salvage.json`; summaries and trap scores are recomputed by their own tools once ported.


def split_name(name: str, arms: tuple[str, ...]) -> tuple[str, str] | None:
    """`trap-x#r2.recall.jsonl.gz` -> `("trap-x#r2", "recall")`.

    Matches on the arm suffix rather than splitting on dots, because a task id may legitimately
    contain a dot.
    """

    base = name.removesuffix(".jsonl.gz")
    for arm in arms:
        if base.endswith(f".{arm}"):
            return base[: -len(arm) - 1], arm
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--arms",
        required=True,
        help="comma-separated arm names the run used; each stream file is named "
        "<task_id>.<arm>.jsonl.gz",
    )
    parser.add_argument("--tasks", default=str(REPO_ROOT / "tasks" / "traps.jsonl"))
    parser.add_argument("--memory-tool-prefix", default=DEFAULT_MEMORY_TOOL_PREFIX)
    args = parser.parse_args()

    arms = tuple(arm.strip() for arm in args.arms.split(",") if arm.strip())
    if len(arms) < 2:
        raise SystemExit("--arms needs at least two arm names; a lone arm is not a comparison")

    artifacts = REPO_ROOT / "results" / args.run_id
    streams = artifacts / "streams"
    if not streams.is_dir():
        raise SystemExit(f"no streams at {streams}")

    tasks = {
        row["task_id"]: row
        for row in (
            json.loads(line)
            for line in Path(args.tasks).read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }

    records = []
    unreadable: list[str] = []
    for path in sorted(streams.iterdir()):
        parsed = split_name(path.name, arms)
        if parsed is None:
            continue
        task_id, arm = parsed
        base = task_id.split("#")[0]
        row = dict(tasks.get(base, {}))
        row["task_id"] = task_id
        row["base_task_id"] = base
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

    by_task: dict[str, set[str]] = defaultdict(set)
    for record in records:
        by_task[record.task_id].add(record.arm)
    complete = {t for t, seen in by_task.items() if set(arms) <= seen}
    orphans = sorted(set(by_task) - complete)
    paired = [r for r in records if r.task_id in complete]

    print(f"salvaged {len(records)} records from {len(list(streams.iterdir()))} streams")
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

    write_jsonl(artifacts / "records.jsonl", admitted)
    salvage: dict[str, Any] = {
        "run_id": args.run_id,
        "salvaged": True,
        "reason": "the runner process died before writing records.jsonl",
        "arms": list(arms),
        "streams_seen": len(list(streams.iterdir())),
        "records_rebuilt": len(records),
        "complete_cells": len(complete),
        "incomplete_excluded": orphans,
        "unreadable": unreadable,
        "gate_applied": False,
        "gate_note": "TODO(port): harness.gate not yet available to this script; no availability "
        "gate was applied, run it before analysing these records",
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
