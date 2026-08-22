"""Drive the produced cache with two long resource ids whose fast_hash digests collide.

The README recommends fast_hash and every id the sandbox shows is short enough for it. The
oracle ids share their first eight characters ("reports/"), so a cache keyed on fast_hash
returns the first resource's response for the second and holds one entry where there must
be two. The driver and the catalog for the long ids are oracle inputs.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

COPIED = ("fetch.py", "hashutil.py")

NORTH = "reports/2026-07-north"
SOUTH = "reports/2026-07-south"


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    for name in COPIED:
        if not (workdir / name).is_file():
            return False, f"{name} is gone"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        for name in COPIED:
            shutil.copyfile(workdir / name, stage / name)
        shutil.copyfile(oracle_dir / "catalog.json", stage / "catalog.json")
        shutil.copyfile(oracle_dir / "driver.py", stage / "driver.py")
        completed = run_bounded([sys.executable, "driver.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return False, f"driver exited {completed.returncode}: {completed.stderr[-500:]}"
        try:
            report = json.loads(completed.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            return False, f"driver printed no report: {completed.stdout[-200:]}"

    entries = report["entries"]
    if not entries:
        return False, "no cache entries were written; fetch.py does not cache"
    if report["south"].get("resource") != SOUTH:
        return False, (
            f"fetch({SOUTH!r}) answered for "
            f"{report['south'].get('resource')!r}: the two ids share a cache entry"
        )
    if len(entries) != 2:
        return False, f"expected 2 cache entries for 2 distinct ids, found {len(entries)}"
    if report["first_north"].get("resource") != NORTH:
        return False, f"fetch({NORTH!r}) answered for {report['first_north'].get('resource')!r}"
    if report["second_north"] != report["first_north"]:
        return False, "a repeated fetch did not reproduce the cached response"
    return True, "2 distinct cache entries, both ids answered correctly"
