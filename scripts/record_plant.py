"""Record one PLANTED session for the abstention suite, from a REAL agent run.

Same pipeline as `scripts/record_precursor.py`, and deliberately so: preregistration 005 names
planted-memo salience as a confound, and an authored memo dropped among 125 recorded ones measures
writing style rather than retrieval. A plant is staged as an incident under
`tasks/<id>/plants/<name>/` (`prompt.txt`, `followup.txt`, `stage/`), recorded live, and converted
by the same `conversation_to_corpus` the real sessions go through.

## The validity gate is INVERTED, which is why this is a separate script

`record_precursor.py` refuses a recording in which the task's `fact_terms` never surfaced. A plant
must satisfy the opposite pair:

* every `wrong_terms` entry from `plants.json` IS present, or nothing can retrieve the plant and
  it will be scored as an ordinary miss;
* every `fact_terms` entry from `task.json` is ABSENT, or the planted session states the true fact
  as well and the condition answers its own question.

The second is the one that matters. A recording that wanders into the real convention while
reasoning about the staged incident looks fine, reads fine, and quietly turns `adjacent` into
`fact-present`. Running that gate is the whole reason a plant is not simply hand-written.

Output goes to `corpus/plants/<task_id>/<name>.jsonl`, which is NOT part of the base corpus feed;
`scripts/assemble_condition_corpus.py` composes it into a condition corpus, and
`scripts/audit_plants.py` checks it for leakage and salience.

    python -m scripts.record_plant --task ts-base36-id --plant stale_lowercase
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness import sandbox
from harness.claude_exec import ClaudeExecConfig, run_claude_case
from harness.plants import load_plants, normalise
from harness.tasks import load_task
from scripts.record_precursor import DENIED, TOOLS, conversation_to_corpus


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--plant", required=True, help="name under tasks/<id>/plants/")
    parser.add_argument(
        "--session-date",
        default=None,
        help="YYYY-MM-DD; default is the plant's session_date in plants.json",
    )
    parser.add_argument("--model", default="deepseek/deepseek-v4-flash")
    parser.add_argument("--base-url", default="https://openrouter.ai/api")
    parser.add_argument("--timeout", type=float, default=420.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    task_dir = REPO / "tasks" / args.task
    task = load_task(task_dir)
    spec = load_plants(task_dir)
    if spec is None:
        raise SystemExit(f"{args.task}: no plants.json, so there is no plant to record")

    declared = json.loads((task_dir / "plants.json").read_text(encoding="utf-8"))
    body = declared.get("plants", {}).get(args.plant)
    if body is None:
        raise SystemExit(
            f"{args.task}: plants.json declares no plant named {args.plant!r}. Declaring it first "
            f"is what puts its wrong_terms under the leakage audit."
        )
    wrong_terms = [str(term) for term in body.get("wrong_terms", ())]
    session_date = args.session_date or body.get("session_date")
    if not session_date:
        raise SystemExit(
            f"{args.task}/{args.plant}: no session_date in plants.json and none passed. A plant "
            f"with no place on the timeline cannot be superseded by anything."
        )

    pdir = task_dir / "plants" / args.plant
    prompt = (pdir / "prompt.txt").read_text(encoding="utf-8").strip()
    followup = (pdir / "followup.txt").read_text(encoding="utf-8").strip()
    if not prompt or not followup:
        raise SystemExit(f"{pdir}: prompt.txt and followup.txt must both be nonempty")

    out = REPO / "corpus" / "plants" / args.task / f"{args.plant}.jsonl"
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
        row = {"task_id": f"plant-{args.task}-{args.plant}", "user_input": prompt}
        record = await run_claude_case(row, "plant", config)

    if record.error is not None:
        raise SystemExit(f"session failed, nothing recorded: {record.error}")
    if not record.tool_calls:
        raise SystemExit(
            "session made no tool calls; a plant must show the same investigation a real "
            "precursor shows, or it reads as a different kind of document. Re-stage and re-run"
        )

    base = datetime.strptime(session_date, "%Y-%m-%d").replace(hour=9, tzinfo=UTC)
    lines = conversation_to_corpus(prompt, record.conversation, followup, base)
    text = "\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n"
    # normalise(), not .lower(): a plain substring test is defeated by markdown emphasis and
    # by hyphens, and one plant already slipped its task's governing fact through that gap.
    haystack = normalise(text)

    missing = [term for term in wrong_terms if normalise(term) not in haystack]
    if missing:
        raise SystemExit(
            f"wrong terms {missing} absent from the transcript; nothing will retrieve this plant, "
            f"and a cell that misses it scores as an ordinary failure. Fix the followup wording "
            f"or the staging, and re-run"
        )
    leaked = [term for term in task.fact_terms if normalise(term) in haystack]
    if leaked:
        raise SystemExit(
            f"the TRUE fact terms {leaked} appear in this planted session. The plant states the "
            f"real convention as well as the wrong one, so the condition answers its own "
            f"question. Re-stage so the incident cannot reach the real fact, and re-run"
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"recorded {out} ({len(lines)} lines, {record.input_tokens}/{record.output_tokens} tokens)")
    print("now run: python -m scripts.audit_plants")
    print("read it before trusting it: the validity gates are necessary, not sufficient")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
