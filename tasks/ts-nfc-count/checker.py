"""Run the produced count_words.py against oracle docs that mix composed and decomposed accents.

The convention under test: text is normalised to NFC before counting, so a composed é and an
e-plus-combining-accent are one word. The comparison parses the produced counts and compares
the NFC-normalised mapping, so formatting is free and normalisation is exactly what is graded.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path

from harness.checker_run import run_bounded


def _parse_counts(text: str) -> dict[str, int] | None:
    counts: dict[str, int] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.rsplit(None, 1)
        if len(parts) != 2 or not parts[1].isdigit():
            return None
        counts[parts[0]] = int(parts[1])
    return counts


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "count_words.py"
    if not script.is_file():
        return False, "count_words.py was never written"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "count_words.py")
        shutil.copytree(oracle_dir / "docs", stage / "docs")
        completed = run_bounded(
            [sys.executable, "count_words.py"], cwd=stage, timeout_s=60.0
        )
        if completed.returncode != 0:
            return (
                False,
                f"count_words.py exited {completed.returncode}: {completed.stderr[-500:]}",
            )
        produced_path = stage / "counts.txt"
        if not produced_path.is_file():
            return False, "count_words.py ran but wrote no counts.txt"
        produced = _parse_counts(produced_path.read_text(encoding="utf-8"))
        if produced is None:
            return False, "counts.txt is not 'word count' lines"

    expected = _parse_counts((oracle_dir / "expected_counts.txt").read_text(encoding="utf-8"))
    if produced == expected:
        return True, f"{len(produced)} distinct words, normalisation respected"
    # The diagnostic that matters: did the two spellings of one word stay separate?
    split_words = sorted(
        word
        for word in produced
        if unicodedata.normalize("NFC", word) != word
    )
    if split_words:
        return False, f"decomposed spellings survived as separate words: {split_words}"
    return False, f"counts differ: got {len(produced)} words, expected {len(expected)}"
