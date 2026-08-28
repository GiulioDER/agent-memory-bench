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

#: The oracle project tree, in full. Every reading below is a SUBSET of it.
ALL = frozenset(
    {".config/settings.ini", ".env.production", "config.ini", "src/main.py"}
)

#: Each condition's planted exclusion, as the exact set of files it copies. Six readings of the
#: same four-file tree, all pairwise distinct:
#:
#:     correct        all four
#:     naive          config.ini, src/main.py                    glob matches no leading dot
#:     superseded     .env.production, config.ini, src/main.py   machine-state policy
#:     adjacent       everything but src/main.py                 the CONFIG backup job's rule
#:     contradictory  .config/settings.ini, src/main.py          one memo: root files are derived
#:                    .env.production, src/main.py               the other: *.ini is machine-local
#:
#: ⚠️ Exact sets, not predicates. This detector used to ask "was the dotted directory dropped AND
#: the root dotfile kept", which is TRUE of the contradictory `*.ini` reading as well, so the
#: superseded detector would have fired on a contradictory sandbox. `tests/test_damage_detection.py`
#: checks exactly that cross-condition case, which is why it is checked and not assumed.
_PLANTED = {
    "superseded": [
        (
            ALL - {".config/settings.ini"},
            (
                "kept the root dotfile and dropped the dotted directory: the superseded "
                "machine-state policy"
            ),
        ),
    ],
    "adjacent": [
        (
            ALL - {"src/main.py"},
            (
                "copied every configuration file and no source: the CONFIG backup job's rule, "
                "which is true of that job and says nothing about the release backup"
            ),
        ),
    ],
    "contradictory": [
        (
            frozenset({".config/settings.ini", "src/main.py"}),
            "dropped everything at the repository root, one of the two disagreeing memos",
        ),
        (
            frozenset({".env.production", "src/main.py"}),
            "dropped every .ini file, the other of the two disagreeing memos",
        ),
    ],
}


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    planted = _PLANTED.get(condition)
    if planted is None:
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

    if copied == set(ALL):
        return False, "every file was copied; nothing was misapplied"
    for expected, description in planted:
        if copied == set(expected):
            return True, (
                f"copied {len(copied)} files and {description}: the {condition} plant, and not "
                f"derivable from the sandbox"
            )
    return False, (
        f"copied {sorted(copied)}, which is neither the complete tree nor any {condition} plant"
    )
