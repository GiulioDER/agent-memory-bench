"""Run the produced generator against an oracle release tree and validate every path key.

The convention under test: manifest keys are paths relative to the repo root, forward-slashed
(``release/app/main.py``), whatever the walk produced. Digests are recomputed here from the
staged tree, so content correctness and key convention are graded together; absolute or
backslashed keys are well-formed JSON and wrong.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "make_manifest.py"
    if not script.is_file():
        return False, "make_manifest.py was never written"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "make_manifest.py")
        shutil.copytree(oracle_dir / "release", stage / "release")
        completed = run_bounded([sys.executable, "make_manifest.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return (
                False,
                f"make_manifest.py exited {completed.returncode}: {completed.stderr[-500:]}",
            )
        manifest_path = stage / "manifest.json"
        if not manifest_path.is_file():
            return False, "make_manifest.py ran but wrote no manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            return False, f"manifest.json is not JSON: {error}"
        if not isinstance(manifest, dict):
            return False, "manifest.json is not a JSON object"

        expected = {}
        release_root = stage / "release"
        for path in sorted(release_root.rglob("*")):
            if path.is_file():
                key = path.relative_to(stage).as_posix()
                expected[key] = hashlib.sha256(path.read_bytes()).hexdigest()

    if manifest == expected:
        return True, f"{len(manifest)} entries, root-relative POSIX keys, digests correct"
    bad_keys = sorted(set(manifest) - set(expected))
    if bad_keys:
        return False, f"path keys violate the convention, e.g. {bad_keys[:3]}"
    missing = sorted(set(expected) - set(manifest))
    if missing:
        return False, f"manifest is missing entries: {missing[:3]}"
    return False, "keys match but digests differ"
