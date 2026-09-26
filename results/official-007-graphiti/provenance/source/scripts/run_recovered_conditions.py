"""Sequentially recover and score the four unfinished official-007 conditions."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from harness.adapters.base import CorpusManifest
from scripts.abstention import selection_for


CONDITIONS = ("absent", "superseded", "contradictory", "adjacent")
BASE_NAMESPACE = "amb-graphiti-official-007"
BASE_RUN_ID = "official-007-graphiti-bare-recovered"
MODEL = "deepseek/deepseek-v4-flash"


def run() -> int:
    repo = REPO
    python = repo / ".venv" / "bin" / "python"
    if not python.is_file():
        raise SystemExit(f"missing pinned benchmark interpreter: {python}")
    graphiti_python = Path("$HOME/graphiti/mcp_server/.venv/bin/python")
    if not graphiti_python.is_file():
        raise SystemExit(f"missing pinned Graphiti interpreter: {graphiti_python}")

    for condition in CONDITIONS:
        corpus_root = repo / "corpus" / "conditions" / condition / "seed-1"
        corpus = CorpusManifest.load(corpus_root)
        corpus.verify()
        tasks = selection_for(condition, announce=False)
        namespace = f"{BASE_NAMESPACE}-{condition}"
        run_id = f"{BASE_RUN_ID}-{condition}-final"

        print(
            f"[{condition}] recovering {len(corpus.sessions)} episodes, "
            f"then scoring {len(tasks)} tasks x 5 seeds x 2 arms",
            flush=True,
        )
        subprocess.run(
            [
                str(graphiti_python),
                "scripts/recover_graphiti_condition.py",
                "--corpus-root",
                str(corpus_root),
                "--namespace",
                namespace,
            ],
            cwd=repo,
            check=True,
        )

        env = os.environ.copy()
        env["AMB_CORPUS_FLOOR"] = str(len(corpus.sessions))
        env["AMB_BLOCK_CONCURRENCY"] = "1"
        subprocess.run(
            [
                str(python),
                "scripts/run_recovered_pilot.py",
                "--run-id",
                run_id,
                "--arms",
                "bare,graphiti",
                "--tasks",
                ",".join(tasks),
                "--seeds",
                "5",
                "--model",
                MODEL,
                "--namespace",
                namespace,
                "--corpus-root",
                str(corpus_root),
                "--condition",
                condition,
                "--memory-instruction",
                "protocol",
                "--price-in",
                "0.0574",
                "--price-out",
                "0.1148",
                "--price-as-of",
                "2026-08-22",
            ],
            cwd=repo,
            env=env,
            check=True,
        )
        print(f"[{condition}] complete: {run_id}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
