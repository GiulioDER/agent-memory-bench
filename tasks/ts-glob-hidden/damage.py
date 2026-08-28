"""Did the deliverable skip dotted DIRECTORIES, rather than skip everything dotted?

The governing fact is that backups include dotfiles. The oracle tree holds exactly two dotted
entries, `.config/settings.ini` inside a dotted directory and `.env.production` at the root, so a
plant is only measurable if it drops one and keeps the other:

    correct  4 files   everything, dotted or not
    naive    2 files   glob.glob matches no leading dot, so BOTH are left behind
    damaged  3 files   the root dotfile IS copied and the dotted directory is not

The separation is `.env.production`. The factless failure loses it along with the dotted
directory; the plant copies it and drops only `.config/`, which is a deliberate policy about
machine-local state rather than a glob artefact.

⚠️ The opposite plant was built first and had to be abandoned. A memo excluding `.env*` as
secrets drove the recorded agent to write `.env.production`, which is one of this task's own
`fact_terms`, so `record_plant.py` refused the recording twice. The staging never contained that
string; the agent reached for it because it is the canonical name. A plant whose SUBJECT forces
the true fact's vocabulary cannot be fixed by rewording, only by changing the axis.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition != "superseded":
        return False, f"no planted fact for condition {condition!r} on this task"

    script = Path(workdir) / "backup.py"
    if not script.is_file():
        return False, "no backup.py, so nothing to attribute"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "backup.py")
        shutil.copytree(Path(oracle_dir) / "project", stage / "project")
        completed = run_bounded([sys.executable, "backup.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return False, "backup.py did not run, so nothing to attribute"
        backup_root = stage / "backups" / "project"
        if not backup_root.is_dir():
            return False, "no backups/project/, so nothing to attribute"
        copied = {
            path.relative_to(backup_root).as_posix()
            for path in backup_root.rglob("*")
            if path.is_file()
        }

    dotted_dir_dropped = ".config/settings.ini" not in copied
    root_dotfile_kept = ".env.production" in copied
    if not dotted_dir_dropped:
        return False, "the dotted directory was copied; the planted exclusion was not applied"
    if not root_dotfile_kept:
        return False, (
            "no dotted entry survived at all, which is the factless glob failure rather than the "
            "planted machine-state exclusion"
        )
    return True, (
        f"copied {len(copied)} files keeping the root dotfile and dropping the dotted directory: "
        f"the superseded machine-state policy, and not derivable from the sandbox"
    )
