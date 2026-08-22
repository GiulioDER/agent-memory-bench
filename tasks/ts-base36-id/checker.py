"""Run the produced gen_id.py against oracle ids whose successor exposes the alphabet.

The oracle's last id ends one step before a symbol the restricted alphabet skips: the true
successor of ORD-24GH is ORD-24GJ, while plain base36 lands on ORD-24GI, a character order
ids never contain. The oracle run of consecutive ids is itself scheme-ambiguous, so only the
governing fact separates the two answers.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

FORBIDDEN = set("0O1I")


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "gen_id.py"
    if not script.is_file():
        return False, "gen_id.py was never written"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "gen_id.py")
        shutil.copyfile(oracle_dir / "ids.txt", stage / "ids.txt")
        completed = run_bounded([sys.executable, "gen_id.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return False, f"gen_id.py exited {completed.returncode}: {completed.stderr[-500:]}"
        produced = completed.stdout.strip()

    expected = (oracle_dir / "expected_next.txt").read_text(encoding="utf-8").strip()
    if produced == expected:
        return True, f"next id {produced} follows the id alphabet"
    confusable = sorted(set(produced) & FORBIDDEN)
    if confusable:
        return False, (
            f"produced {produced!r}, which uses {confusable} — characters order ids "
            f"never contain; expected {expected!r}"
        )
    return False, f"produced {produced!r}, expected {expected!r}"
