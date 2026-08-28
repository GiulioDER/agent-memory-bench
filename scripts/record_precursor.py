"""Record one precursor session for the experience corpus, from a REAL agent run.

The corpus rule: transcript content is verbatim agent output, never hand-edited. A precursor
is recorded by restoring the task's fixture, overlaying its staged incident
(`tasks/<id>/precursors/<name>/stage/`), and running Claude Code live against
`prompt.txt`. The stream is converted 1:1 into the corpus transcript format; the one
authored turn is `followup.txt`, the human confirmation that states the decision
("ok: from now on ..."), appended as the final user turn, exactly as a real user closes such
a session. If the run does not surface the fact, re-stage and re-run; never edit.

Timestamps: content is verbatim; the `ts` fields are recording metadata, mapped
deterministically onto the project timeline (`--session-date`, 40s per turn from 09:00 UTC)
so the corpus reads as weeks of project history rather than one recording afternoon. This
transform is disclosed here and in the corpus README; every product ingests identical bytes.

Validity gates before anything is written: the session made at least one tool call, and every
`fact_terms` entry from task.json appears in the final transcript (the followup provides them
by construction; a recording where the surrounding investigation contradicts it would still
fail eyeball review, which is why the transcript path is printed for reading).

    python -m scripts.record_precursor --task ts-dedup-order --precursor p01 \
        --session-date 2026-07-01 --model deepseek/deepseek-v4-flash
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness import sandbox
from harness.claude_exec import ClaudeExecConfig, run_claude_case
from harness.tasks import load_task

TOOLS = ("Read", "Grep", "Glob", "Bash", "Write", "Edit")
DENIED = ("Bash(docker:*)", "Bash(docker-compose:*)")


def _stamp(base: datetime, index: int) -> str:
    return (base + timedelta(seconds=40 * index)).strftime("%Y-%m-%dT%H:%M:%SZ")


def conversation_to_corpus(
    prompt: str, conversation, followup: str, base: datetime
) -> list[dict]:
    """Convert an executor conversation into corpus transcript lines, verbatim content."""

    lines: list[dict] = [{"role": "user", "content": prompt, "ts": _stamp(base, 0)}]
    index = 1
    pending: list[dict] = []
    pending_by_id: dict[str, dict] = {}
    for turn in conversation:
        role = turn.get("role")
        if role == "user":
            continue  # the prompt is line one; the executor injects it into conversation
        if role == "assistant":
            text = str(turn.get("content", ""))
            calls = list(turn.get("tool_calls") or [])
            if text.strip() and not calls:
                lines.append({"role": "assistant", "content": text, "ts": _stamp(base, index)})
                index += 1
            for call in calls:
                entry = {
                    "role": "assistant",
                    "content": text.strip(),
                    "tool_name": str(call.get("name", "")),
                    "tool_input": json.dumps(call.get("args", {}), ensure_ascii=False),
                }
                pending.append(entry)
                call_id = str(call.get("id", ""))
                if call_id:
                    pending_by_id[call_id] = entry
                text = ""  # the text belongs to the first call of the turn only
        elif role == "tool":
            call_id = str(turn.get("tool_use_id", ""))
            entry = pending_by_id.pop(call_id, None) if call_id else None
            if entry is not None:
                pending.remove(entry)
            elif pending:
                # Older captured conversations did not preserve the tool_use_id. Keep the
                # historical fallback for those inputs, while ID-bearing streams pair safely
                # even when results arrive out of order.
                entry = pending.pop(0)
                stale_ids = [
                    pending_id for pending_id, pending_entry in pending_by_id.items()
                    if pending_entry is entry
                ]
                for pending_id in stale_ids:
                    pending_by_id.pop(pending_id, None)
            else:
                entry = {"role": "assistant", "content": ""}
            entry["tool_result"] = str(turn.get("content", ""))[:2000]
            entry["ts"] = _stamp(base, index)
            index += 1
            lines.append(entry)
    for entry in pending:  # calls whose results never arrived
        entry["ts"] = _stamp(base, index)
        index += 1
        lines.append(entry)
    lines.append({"role": "user", "content": followup, "ts": _stamp(base, index + 1)})
    return lines


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--precursor", required=True, help="name under tasks/<id>/precursors/")
    parser.add_argument("--session-date", required=True, help="YYYY-MM-DD on the project timeline")
    parser.add_argument("--model", default="deepseek/deepseek-v4-flash")
    parser.add_argument("--base-url", default="https://openrouter.ai/api")
    parser.add_argument("--timeout", type=float, default=420.0)
    parser.add_argument("--out-name", default=None, help="corpus file name; default <precursor>")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    task = load_task(REPO / "tasks" / args.task)
    pdir = REPO / "tasks" / args.task / "precursors" / args.precursor
    prompt = (pdir / "prompt.txt").read_text(encoding="utf-8").strip()
    followup = (pdir / "followup.txt").read_text(encoding="utf-8").strip()
    if not prompt or not followup:
        raise SystemExit(f"{pdir}: prompt.txt and followup.txt must both be nonempty")

    out = REPO / "corpus" / "sessions" / args.task / f"{args.out_name or args.precursor}.jsonl"
    if out.exists() and not args.force:
        raise SystemExit(f"{out} exists; pass --force to re-record over it")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is not set")

    with tempfile.TemporaryDirectory() as temp:
        workdir = Path(temp) / "project"
        sandbox.restore(args.task, workdir)
        stage = pdir / "stage"
        if stage.is_dir():
            shutil.copytree(stage, workdir, dirs_exist_ok=True)
        config = ClaudeExecConfig(
            model=args.model,
            cwd=workdir,
            timeout_s=args.timeout,
            env={
                "ANTHROPIC_BASE_URL": args.base_url,
                "ANTHROPIC_AUTH_TOKEN": os.environ["OPENROUTER_API_KEY"],
                "ANTHROPIC_API_KEY": "",
            },
            bare=True,
            strict_mcp_config=False,
            allowed_tools=TOOLS,
            disallowed_tools=DENIED,
            permission_mode="acceptEdits",
        )
        row = {"task_id": f"precursor-{args.task}-{args.precursor}", "user_input": prompt}
        record = await run_claude_case(row, "precursor", config)

    if record.error is not None:
        raise SystemExit(f"session failed, nothing recorded: {record.error}")
    if not record.tool_calls:
        raise SystemExit(
            "session made no tool calls; a precursor must show real investigation. "
            "Re-stage so the prompt requires looking at the tree, and re-run"
        )

    base = datetime.strptime(args.session_date, "%Y-%m-%d").replace(hour=9, tzinfo=UTC)
    lines = conversation_to_corpus(prompt, record.conversation, followup, base)
    text = "\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n"

    missing = [term for term in task.fact_terms if term.lower() not in text.lower()]
    if missing:
        raise SystemExit(
            f"fact terms {missing} absent from the transcript; the fact never surfaced. "
            f"Fix the staging or the followup wording, and re-run"
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"recorded {out} ({len(lines)} lines, {record.input_tokens}/{record.output_tokens} tokens)")
    print("read it before trusting it: the validity gates are necessary, not sufficient")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
