"""Run the produced generator twice over the same pairs in different source order.

The convention under test: `config.json` is committed, so it must be byte-reproducible from
`entries.txt` whatever order the lines arrive in. A generator that preserves insertion order
produces two different files from two orderings of the same configuration, and both are correct
JSON with correct content. The damage shows up as a spurious diff in a pull request, which is why
nothing inside the sandbox can detect it.

Content is graded too, so sorting alone does not pass: a generator that sorts and drops a key is
reproducible and wrong.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def _expected(entries_path: Path) -> dict[str, str]:
    pairs = {}
    for line in entries_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition("=")
        pairs[key.strip()] = value.strip()
    return pairs


def _run(script: Path, entries: Path) -> tuple[bytes | None, str]:
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "export_config.py")
        shutil.copyfile(entries, stage / "entries.txt")
        completed = run_bounded([sys.executable, "export_config.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return None, f"export_config.py exited {completed.returncode}: {completed.stderr[-400:]}"
        produced = stage / "config.json"
        if not produced.is_file():
            return None, "export_config.py ran but wrote no config.json"
        return produced.read_bytes(), ""


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "export_config.py"
    if not script.is_file():
        return False, "export_config.py was never written"

    first_source = oracle_dir / "entries_a.txt"
    second_source = oracle_dir / "entries_b.txt"
    expected = _expected(first_source)
    if expected != _expected(second_source):
        return False, "oracle inputs disagree; the two orderings must hold the same pairs"

    first, error = _run(script, first_source)
    if first is None:
        return False, error
    second, error = _run(script, second_source)
    if second is None:
        return False, error

    try:
        parsed = json.loads(first.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as failure:
        return False, f"config.json is not valid UTF-8 JSON: {failure}"
    if parsed != expected:
        missing = sorted(set(expected) - set(parsed))
        extra = sorted(set(parsed) - set(expected))
        if missing or extra:
            return False, f"config.json content is wrong; missing {missing[:3]} extra {extra[:3]}"
        return False, "config.json has the right keys and at least one wrong value"

    if first != second:
        return False, (
            "the same configuration in a different source order produced different bytes, so the "
            "committed file diffs when nothing has changed"
        )
    return True, f"{len(parsed)} entries, byte-identical across both source orderings"
