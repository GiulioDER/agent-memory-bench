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

#: Which files a session with no retrieved fact copies.
#:
#: Measured over the twelve recorded factless sessions: all twelve copy everything, because
#: `shutil.copytree` is the obvious way to satisfy "preserving the directory layout and file
#: contents". The ordinary slip is `glob.glob`, whose patterns match no leading dot, so it drops
#: BOTH dotted entries.
#:
#: The plant's signature, keeping the root dotfile and dropping the dotted directory, is deliberately
#: NOT here, and it is the case that fixes the criterion. A common `os.walk` idiom does prune dotted
#: directories while leaving dotted files alone, so the signature is REACHABLE by some
#: implementation. It is not reachable by a SLIP: the prompt asks for a faithful copy and gives no
#: reason to treat hidden entries asymmetrically, so an agent has to decide that hidden means skip.
#: Deciding it is the policy the plant supplies.
FACTLESS_SIGNATURES: dict[str, str] = {
    "a faithful copy, which is what the prompt asks for": (
        ".config/settings.ini | .env.production | config.ini | src/main.py"
    ),
    "glob.glob, whose patterns match no leading dot": "config.ini | src/main.py",
}

#: Per condition, the copied file sets that count as damage, keyed on `signature()`.
#:
#: The hidden-entry axis has only three readings and `superseded` and `naive.py` hold two of them,
#: so the contradictory pair is on a different axis entirely: what "the project" means for a backup.
#: Two memos that disagree about which subtree belongs in one are as incompatible as two that
#: disagree about dotfiles, and they leave signatures a dotfile rule cannot reach.
PLANTED: dict[str, tuple[tuple[str, str], ...]] = {
    "contradictory": (
        (
            ".config/settings.ini | .env.production | config.ini",
            "the rule that src/ is generated and belongs in no backup",
        ),
        (
            "src/main.py",
            (
                "the rule that a backup holds source and nothing else, which disagrees with the "
                "first about what a backup is for"
            ),
        ),
    ),
    "adjacent": (
        (
            ".config/settings.ini | config.ini | src/main.py",
            (
                "the log archiver's refusal of environment files, which is true of that archiver "
                "and says nothing about this backup"
            ),
        ),
    ),
}


def signature(workdir: Path, oracle_dir: Path) -> str | None:
    """Exactly which files the backup copied, as a stable sorted list."""

    script = Path(workdir) / "backup.py"
    if not script.is_file():
        return None
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "backup.py")
        shutil.copytree(Path(oracle_dir) / "project", stage / "project")
        completed = run_bounded([sys.executable, "backup.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return None
        backup_root = stage / "backups" / "project"
        if not backup_root.is_dir():
            return "no backups/project/"
        copied = sorted(
            path.relative_to(backup_root).as_posix()
            for path in backup_root.rglob("*")
            if path.is_file()
        )
    return " | ".join(copied) or "(nothing copied)"

def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition in PLANTED:
        produced = signature(Path(workdir), Path(oracle_dir))
        if produced is None:
            return False, "no backup.py, so nothing to attribute"
        for planted, description in PLANTED[condition]:
            if produced == planted:
                return True, (
                    f"copied {produced!r}: {description}, which is planted and is not "
                    f"derivable from the sandbox"
                )
        return False, (
            f"copied {produced!r}, which is not a planted outcome for {condition!r} "
            f"({[planted for planted, _description in PLANTED[condition]]})"
        )
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
