"""Restoring the same repository state for both arms, and proving that it was the same.

A paired comparison over real work needs the two arms to start from identical ground. That sounds
like a copy and it is not, because three things can differ without anyone noticing: the initial
commit's identity and timestamp, the line endings git writes into the working tree, and whatever
a previous session left behind in a reused directory.

So each session gets a fresh directory built from a tracked fixture, and the harness records a
**tree digest** for it. `harness.gate.admit_cells` compares those digests across a cell's arms and
discards the cell when they disagree, exactly as it discards a cell that cannot prove the treatment
was applied. A difference in starting state would look like a treatment effect and there would be
nothing in the artifact to say otherwise.

⚠️ **That comparison did not exist until 2026-08-28.** This docstring claimed it from the first
commit, `README.md` listed "sandbox files digest-verified" among the gate's checks, and
`harness/gate.py` contained no reference to `sandbox_digest` at all: both runners recorded it and
nothing read it. It is implemented now (`gate._check_cell_digests`), and the gap is recorded here
rather than quietly closed, because a documented guarantee that does not exist is worse than an
absent one.

A fixture is a directory under `tasks/<task_id>/` at the repository root:

    tree/     the committed state; everything here is added and committed
    dirty/    optional, copied OVER the tree after that commit, leaving those files modified

`dirty/` exists for any task whose whole point is an unclean working tree. Doing it as an
overlay rather than as a script keeps the fixture readable as data.

`restore(..., overlay=...)` places an ARM's own memory directory into the sandbox after the fixture
commit, which is how `fs_grep` gets its notes. It lives here rather than in a runner because it did
live in a runner: `scripts/smoke.py` was the only caller that implemented it, so `fs_grep` was
unrunnable from `scripts/pilot.py` and `scripts/diagnostic.py` while the adapter's own comment said
"the sandbox builder overlays this directory". It does now.

⛔ **Oracles live in `oracles/<task_id>/` at the repository root, beside `tasks/`, and are never
copied.** The endpoint is only meaningful while the input that decides it stays out of the
agent's reach.

⛔ **A sandbox must not be created inside this repository.** `oracles/`, `tasks/*/reference/` and
`corpus/` sit a few directories above `results/<run>/work/...`, the agent runs with unrestricted
`Bash`, and `system/init` hands it the absolute path. No session in the 648 committed streams ever
walked up, and the only thing that stopped one is that `restore` runs `git init`, so
`git rev-parse --show-toplevel` answers with the sandbox. That is luck, not a control.
`default_work_root` returns a path outside the repository, and `restore` refuses a destination
under it.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

from .checker_run import git

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACES = REPO_ROOT / "tasks"
ORACLES = REPO_ROOT / "oracles"

#: Never copied into a sandbox and never hashed.
EXCLUDED = frozenset({".git", "__pycache__", ".pytest_cache", ".ruff_cache"})

#: Where run work directories go when a runner does not say. Outside the repository, so an agent
#: with `Bash` cannot reach `oracles/`, `tasks/*/reference/` or `corpus/` by walking up. Override
#: with AGENT_MEMORY_BENCH_WORK_ROOT when a host needs a specific volume; the value is recorded in
#: every run's environment.json so the choice is visible in the artifact.
WORK_ROOT_ENV = "AGENT_MEMORY_BENCH_WORK_ROOT"


def default_work_root() -> Path:
    """A sandbox root that is not inside this repository."""

    override = os.environ.get(WORK_ROOT_ENV)
    root = Path(override) if override else Path(tempfile.gettempdir()) / "agent-memory-bench-work"
    if _is_inside_repo(root):
        raise ValueError(
            f"{WORK_ROOT_ENV}={root} is inside the benchmark repository. A sandbox there can read "
            f"oracles/, tasks/*/reference/ and corpus/ with one `cd ..`, which is the endpoint the "
            f"whole design depends on staying out of reach."
        )
    return root


def _is_inside_repo(path: Path) -> bool:
    try:
        Path(path).resolve().relative_to(REPO_ROOT)
    except ValueError:
        return False
    return True


def _iter_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*")):
        if any(part in EXCLUDED for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            yield path


def tree_digest(root: Path) -> str:
    """A digest over every tracked-relevant file's path and bytes.

    Bytes, not text: line endings are precisely one of the things a task here is scored on, so a
    digest that normalised them would call two genuinely different starting states identical.
    """

    digest = hashlib.sha256()
    for path in _iter_files(root):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _copy_tree(source: Path, destination: Path) -> None:
    for path in _iter_files(source):
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Bytes, so a fixture that deliberately holds CRLF or a bare LF keeps it. `shutil.copy2`
        # would do as well; this is explicit about the thing that matters.
        target.write_bytes(path.read_bytes())


def restore(
    workspace: str,
    destination: Path,
    *,
    overlay: str | Path | None = None,
    overlay_name: str = "memory",
    allow_in_repo: bool = False,
) -> str:
    """Build one sandbox from its fixture and return its tree digest.

    The directory is created fresh. A reused one is refused rather than cleaned, because a stale
    artifact from an earlier session is indistinguishable from work this session did.

    ``overlay`` is an arm's own memory directory, copied in at ``overlay_name`` AFTER the fixture
    commit so it shows as untracked rather than as part of the project's history. It is excluded
    from the returned digest, because the digest exists to prove every arm started from the same
    REPOSITORY state and an arm's memory is the one thing that is legitimately different.

    ``allow_in_repo`` exists for the test suite, which builds sandboxes under ``tmp_path``; on some
    hosts pytest's temp root resolves inside a checkout. Never pass it from a runner.
    """

    fixture = WORKSPACES / workspace
    if not fixture.is_dir():
        raise FileNotFoundError(f"no fixture for workspace {workspace!r} at {fixture}")
    if not allow_in_repo and _is_inside_repo(destination):
        raise ValueError(
            f"refusing to build a sandbox at {destination}, which is inside the benchmark "
            f"repository: oracles/, tasks/*/reference/ and corpus/ would be reachable from it. "
            f"Use harness.sandbox.default_work_root()."
        )
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"sandbox {destination} already has contents")
    destination.mkdir(parents=True, exist_ok=True)

    _copy_tree(fixture / "tree", destination)

    # A git repository, because several checkers read the diff and because "leave the tree clean"
    # is only a meaningful instruction where there is an index to be clean against. `init.
    # defaultBranch` is pinned so a checker can name the branch, and gpgsign is off because the
    # user's signing key must never be reachable from a sandbox running model-written code.
    # Each of these is checked. `checker_run.git` returns a Completed and never raises, so an
    # unchecked call lets a failed init/add/commit hand back a sandbox with no baseline commit and
    # a perfectly plausible digest: `tree_digest` hashes files, not git state, and `.git` is
    # excluded from it, so nothing downstream can tell the difference. An unprovable starting
    # state must refuse rather than proceed.
    for step in (
        ("init", "-q", "-b", "main", "."),
        ("add", "--", "."),
        ("commit", "-q", "-m", "fixture"),
    ):
        completed = git(*step, cwd=destination)
        if not completed.ok:
            raise RuntimeError(
                f"git {step[0]} failed in sandbox {destination} "
                f"(exit {completed.returncode}, timed_out={completed.timed_out}): "
                f"{completed.stderr.strip() or completed.stdout.strip()}"
            )

    dirty = fixture / "dirty"
    if dirty.is_dir():
        _copy_tree(dirty, destination)

    # Computed BEFORE the arm's memory lands, so the digest describes the repository state the
    # arms share rather than the treatment that distinguishes them.
    digest = tree_digest(destination)

    if overlay is not None:
        source = Path(overlay)
        if not source.is_dir():
            raise FileNotFoundError(f"memory overlay {source} does not exist; ingest first")
        shutil.copytree(source, destination / overlay_name)

    return digest


def oracle(task_id: str) -> Path:
    """The held-out directory for one task, which no sandbox ever sees."""

    path = ORACLES / task_id
    if not path.is_dir():
        raise FileNotFoundError(f"no oracle directory for {task_id!r} at {path}")
    return path


def stage_oracle(task_id: str, workdir: Path, name: str) -> Path:
    """Copy one oracle file into a finished sandbox, for a checker to run the artifact against.

    Called only after the session has ended. The file lands under `.oracle/` so a later reader of
    the sandbox can see what the artifact was judged with.
    """

    source = oracle(task_id) / name
    if not source.is_file():
        raise FileNotFoundError(f"no oracle file {name!r} for {task_id!r}")
    target = workdir / ".oracle" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target
