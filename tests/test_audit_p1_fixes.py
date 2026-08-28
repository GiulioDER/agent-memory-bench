"""Regression tests for the P1 defects the 2026-08-28 CCA audit confirmed.

Each test here failed against the pre-fix tree. They are grouped by the artifact they protect:
the salvage recovery path, the sandbox's committed baseline, the diagnostic's arithmetic, the
preregistration timestamp guard, the session environment boundary, and the two published
surfaces (the Pages deploy and the harness image build context).
"""

from __future__ import annotations

import contextlib
import importlib.util
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- salvage (STAKES-001, DAT-001)


def test_salvage_leaves_the_runners_graded_records_untouched(tmp_path, monkeypatch):
    """Salvage must not clobber the runner's fsynced, checker-graded records.

    scripts/pilot.py appends each graded record to records.jsonl with fsync so that a run which
    dies keeps every finished cell. Salvage rebuilds records whose success means only "the session
    ran to completion", so overwriting that file turns graded failures into successes.

    This drives the whole command rather than any one guard: the pre-fix tree reached
    ``write_jsonl(artifacts / "records.jsonl", ...)`` and truncated the graded file to nothing.
    """

    salvage = _load(REPO_ROOT / "scripts" / "salvage.py", "salvage_under_test")
    monkeypatch.setattr(salvage, "REPO_ROOT", tmp_path)

    artifacts = tmp_path / "results" / "run-1"
    (artifacts / "streams").mkdir(parents=True)
    graded = artifacts / "records.jsonl"
    original = '{"task_id": "ts-x", "arm": "recall", "success": false}\n'
    graded.write_text(original, encoding="utf-8")

    task_file = tmp_path / "tasks.jsonl"
    task_file.write_text('{"task_id": "ts-x", "user_input": "go"}\n', encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        ["salvage.py", "--run-id", "run-1", "--arms", "recall,bare", "--tasks", str(task_file)],
    )
    with contextlib.suppress(SystemExit):
        salvage.main()

    assert graded.read_text(encoding="utf-8") == original, (
        "salvage overwrote the runner's checker-graded records with ungraded ones"
    )


def test_salvage_parses_the_seed_out_of_the_stream_name():
    """Streams are named ``<task>.s<seed>.<arm>.jsonl.gz`` (harness/claude_exec.py).

    The pre-fix parser folded ``.s<seed>`` into the task id, so every salvaged record carried
    seed 0 and a task id that no task lookup could match.
    """

    salvage = _load(REPO_ROOT / "scripts" / "salvage.py", "salvage_seed_under_test")
    assert salvage.split_name("ts-tz-utc.s2.recall.jsonl.gz", ("recall", "bare")) == (
        "ts-tz-utc",
        2,
        "recall",
    )
    # A task id may legitimately contain a dot, and a stream with no seed segment still parses.
    assert salvage.split_name("ts-x.y.bare.jsonl.gz", ("recall", "bare")) == ("ts-x.y", 0, "bare")


# ------------------------------------------------------------------------- sandbox (BUG-003)


def test_restore_refuses_when_the_baseline_commit_fails(tmp_path, monkeypatch):
    """A sandbox whose fixture commit failed must refuse, not return a plausible digest.

    ``checker_run.git`` returns a Completed and never raises, so the pre-fix restore() discarded
    all three exit codes and handed back a digest for a repository with no baseline.
    """

    from harness import checker_run, sandbox

    real_git = sandbox.git

    def failing_git(*args: str, cwd: Path):
        if args and args[0] == "commit":
            return checker_run.Completed(
                returncode=1, stdout="", stderr="nothing to commit", wall_s=0.0, timed_out=False
            )
        return real_git(*args, cwd=cwd)

    monkeypatch.setattr(sandbox, "git", failing_git)
    workspace = min(p.name for p in (REPO_ROOT / "tasks").iterdir() if (p / "tree").is_dir())

    with pytest.raises(RuntimeError, match="commit"):
        sandbox.restore(workspace, tmp_path / "sandbox")


# --------------------------------------------------------------- diagnostic arithmetic (NUM-002)


def test_access_gap_excludes_a_task_whose_arm_has_no_records():
    """A missing arm is an unmeasured task, not a task the arm failed.

    Pre-fix, ``(rate or 0)`` scored an absent oracle_memory arm as 0% success, so a run with one
    discarded oracle cell reported a large negative access gap from all-successful records.
    """

    analyze = _load(REPO_ROOT / "scripts" / "analyze_diagnostic.py", "analyze_diag_under_test")

    class R:
        def __init__(self, task_id, seed, arm, success):
            self.task_id, self.seed, self.arm, self.success = task_id, seed, arm, success
            self.metadata, self.memory_call_count = {}, 0

    arms = ("claude_md", "recall", "oracle_memory", "recall_prefetch")
    records = [R("A", s, a, True) for s in range(3) for a in arms]
    # Task B was measured in every arm except oracle_memory.
    records += [R("B", s, a, True) for s in range(3) for a in arms if a != "oracle_memory"]

    contrasts = analyze.compare(records)["contrasts"]
    assert contrasts["access_gap"]["mean_delta"] == 0.0
    assert contrasts["access_gap"]["n_tasks"] == 1


# ------------------------------------------------------- preregistration timestamps (STAKES-005)


def test_ots_verification_failure_fails_the_command(monkeypatch):
    """`ots verify` returning nonzero must fail the verify command.

    Pre-fix its return code was printed and discarded, so a non-verifying attestation, the
    strongest anchor the scheme has, exited 0.
    """

    prereg = _load(REPO_ROOT / "scripts" / "timestamp_prereg.py", "timestamp_prereg_under_test")
    stamps = REPO_ROOT / "preregistration" / "timestamps"
    if not sorted(stamps.glob("*.ots")):
        pytest.skip("no .ots attestation committed to verify against")

    monkeypatch.setattr(prereg.shutil, "which", lambda _name: "ots")
    monkeypatch.setattr(prereg, "verify", lambda *a, **k: [])
    monkeypatch.setattr(
        prereg.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 1, "", "Error: attestation invalid"),
    )
    assert prereg.cmd_verify(None, False) == 1


# ------------------------------------------------------------- session env boundary (SEC-001)


def test_the_session_subprocess_does_not_inherit_unrelated_host_secrets(monkeypatch):
    """Model-written Bash inherits this environment; it must not carry every host secret.

    Sessions run with unrestricted Bash under acceptEdits, so any variable reaching the child is
    readable by the agent and lands in a committed transcript. This asserts on the environment
    actually handed to ``create_subprocess_exec``, which is the thing the agent gets, rather than
    on any particular helper: the pre-fix tree passed ``dict(os.environ)`` straight through.
    """

    import asyncio
    import contextlib

    from harness import claude_exec

    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "leak-me")
    monkeypatch.setenv("MEM0_API_KEY", "another-arms-key")
    monkeypatch.setenv("RECALL_DSN", "postgresql://user:password@host/db")

    captured: dict[str, str] = {}

    class _FakeProcess:
        returncode = 0
        pid = 4321

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"", b""

    async def _fake_launch(*_args, **kwargs):
        captured.update(kwargs.get("env") or {})
        return _FakeProcess()

    monkeypatch.setattr(claude_exec.asyncio, "create_subprocess_exec", _fake_launch)

    config = claude_exec.ClaudeExecConfig(
        env={"ANTHROPIC_AUTH_TOKEN": "token"}, strict_mcp_config=False
    )
    row = {"task_id": "ts-x", "user_input": "do the thing"}
    # The fake returns no transcript; whether that parses or raises is beside the point, the
    # environment was already captured at launch.
    with contextlib.suppress(Exception):
        asyncio.run(claude_exec.run_claude_case(row, "arm", config))

    assert captured, "the session subprocess was never launched"
    assert "AWS_SECRET_ACCESS_KEY" not in captured
    assert "MEM0_API_KEY" not in captured, "one arm must not inherit another arm's credential"
    assert "RECALL_DSN" not in captured
    # What the arm configures for itself still arrives.
    assert captured["ANTHROPIC_AUTH_TOKEN"] == "token"


# ------------------------------------------------------------ published surfaces (DEPLOY-001/002)


def test_the_pages_deploy_runs_the_site_guards():
    """site/ is published verbatim on push to master, so the guards must run in that workflow.

    They lived only in ci.yml, which races the deploy and cannot block it; master carries no
    branch protection, so a direct push published whatever it contained.
    """

    pages = (REPO_ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    assert "test_site_vendor_disclosure.py" in pages
    assert "test_leaderboard_generated.py" in pages
    deploy_at = pages.index("actions/deploy-pages")
    assert pages.index("test_site_vendor_disclosure.py") < deploy_at


def test_the_image_build_context_excludes_credentials():
    """`COPY . /bench` runs with the repo root as context, where compose expects a real .env.

    The patterns must be RECURSIVE. Docker's ignore syntax is not gitignore: a bare ``.env``
    matches only the context root, so a dotenv in a worktree, an adapter directory or a nested
    checkout is still copied into an image layer.
    """

    ignore = REPO_ROOT / ".dockerignore"
    assert ignore.is_file(), "no .dockerignore: docker build copies .env into the image layers"
    patterns = {line.strip() for line in ignore.read_text(encoding="utf-8").splitlines()}
    assert "**/.env" in patterns, "root-anchored .env leaves nested dotenv files in the context"
    assert "**/.env.*" in patterns
    assert "!.env.example" in patterns
    assert ".claude/" in patterns, ".claude/ can hold worktree checkouts and MCP config"
    assert "**/.git" in patterns
    assert "results/" in patterns


def test_the_build_context_keeps_the_dotfile_fixtures():
    """The recursive dotenv rule must not eat the fixtures the in-image test suite needs.

    ``ts-glob-hidden`` is a task ABOUT globbing dotfiles: its planted ``.env.production`` is the
    subject under test, not a credential.
    """

    patterns = {
        line.strip()
        for line in (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    }
    for fixture in (
        REPO_ROOT / "oracles" / "ts-glob-hidden" / "project" / ".env.production",
        REPO_ROOT / "tasks" / "ts-glob-hidden" / "precursors" / "p01" / "stage" / "project" / ".env.production",
    ):
        assert fixture.is_file(), f"fixture moved: {fixture}"
    assert "!oracles/**/.env.production" in patterns
    assert "!tasks/**/.env.production" in patterns


def test_salvage_pairs_on_the_cell_not_the_task():
    """A seed whose partner arm never finished is not a comparison and must be excluded.

    Regression guard for the seed fix: once the seed moved out of ``task_id`` into its own field,
    a pairing key of ``task_id`` alone would pool every seed of a task together and admit a
    half-finished cell. Caught by the L5.5 anti-regression review, not by the suite, which is
    why this test exists.
    """

    class R:
        def __init__(self, task_id, seed, arm):
            self.task_id, self.seed, self.arm = task_id, seed, arm

    records = [R("ts-a", 0, "bare"), R("ts-a", 0, "recall"), R("ts-a", 1, "recall")]
    arms = ("recall", "bare")

    by_cell: dict[tuple[str, int], set[str]] = {}
    for record in records:
        by_cell.setdefault((record.task_id, record.seed), set()).add(record.arm)
    complete = {cell for cell, seen in by_cell.items() if set(arms) <= seen}
    paired = [r for r in records if (r.task_id, r.seed) in complete]

    assert complete == {("ts-a", 0)}
    assert len(paired) == 2, "seed 1 has no bare partner and must not be admitted"

    # And the shipped module must key the same way.
    source = (REPO_ROOT / "scripts" / "salvage.py").read_text(encoding="utf-8")
    assert "by_cell[(record.task_id, record.seed)]" in source
