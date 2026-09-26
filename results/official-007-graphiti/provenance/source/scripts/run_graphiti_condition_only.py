"""Recover and score one condition with the Graphiti arm only."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from harness.adapters.base import CorpusManifest
from scripts.abstention import selection_for


def main() -> int:
    condition = sys.argv[1] if len(sys.argv) > 1 else "superseded"
    repo = Path(__file__).resolve().parents[1]
    corpus_root = repo / "corpus" / "conditions" / condition / "seed-1"
    corpus = CorpusManifest.load(corpus_root)
    corpus.verify()
    namespace = f"amb-graphiti-official-007-{condition}"
    run_id = f"official-007-graphiti-recovered-{condition}-only-final"
    graphiti_python = Path("$HOME/graphiti/mcp_server/.venv/bin/python")
    benchmark_python = repo / ".venv" / "bin" / "python"
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
            str(benchmark_python),
            "scripts/run_recovered_pilot.py",
            "--run-id",
            run_id,
            "--arms",
            "graphiti",
            "--tasks",
            ",".join(selection_for(condition, announce=False)),
            "--seeds",
            "5",
            "--model",
            "deepseek/deepseek-v4-flash",
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
