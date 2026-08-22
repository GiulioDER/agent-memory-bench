"""Record one distractor session: real work on a task fixture that establishes no fact.

Same recording pipeline and verbatim rule as `record_precursor.py`, without the followup
and without the fact gate (a distractor must NOT state any task's governing fact; the corpus
audit checks that afterwards). Prompts come from `corpus/distractor_prompts.txt`, one per
line, chosen by index so a recording plan is reproducible.

    python -m scripts.record_distractor --fixture ts-dedup-order --prompt-index 0 \
        --session-date 2026-07-03 --out d001
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness import sandbox
from harness.claude_exec import ClaudeExecConfig, run_claude_case
from scripts.record_precursor import DENIED, TOOLS, conversation_to_corpus


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, help="task id whose fixture to work in")
    parser.add_argument("--prompt-index", type=int, required=True)
    parser.add_argument("--session-date", required=True)
    parser.add_argument("--out", required=True, help="file stem under corpus/distractors/")
    parser.add_argument("--model", default="deepseek/deepseek-v4-flash")
    parser.add_argument("--base-url", default="https://openrouter.ai/api")
    parser.add_argument("--timeout", type=float, default=420.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    prompts = [
        line.strip()
        for line in (REPO / "corpus" / "distractor_prompts.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.startswith("#")
    ]
    prompt = prompts[args.prompt_index]
    out = REPO / "corpus" / "distractors" / f"{args.out}.jsonl"
    if out.exists() and not args.force:
        raise SystemExit(f"{out} exists; pass --force to re-record over it")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is not set")

    with tempfile.TemporaryDirectory() as temp:
        workdir = Path(temp) / "project"
        sandbox.restore(args.fixture, workdir)
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
        row = {"task_id": f"distractor-{args.out}", "user_input": prompt}
        record = await run_claude_case(row, "distractor", config)

    if record.error is not None:
        raise SystemExit(f"session failed, nothing recorded: {record.error}")
    if not record.tool_calls:
        raise SystemExit("session made no tool calls; pick a prompt that requires the tree")

    base = datetime.strptime(args.session_date, "%Y-%m-%d").replace(hour=14, tzinfo=UTC)
    lines = conversation_to_corpus(prompt, record.conversation, "thanks, that works.", base)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"recorded {out} ({len(lines)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
