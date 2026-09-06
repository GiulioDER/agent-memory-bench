"""Produce immutable fresh-machine smoke evidence for the public AMB surface."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.challenge_release import validate_evaluator_revision
from harness.challenge_smoke import validate_public_smoke_report
from harness.checker_run import run_bounded

_PYTEST_COUNT = re.compile(r"(?P<count>\d+)\s+(?P<kind>passed|skipped|failed|error[s]?)")
_SMOKE_ENV_ALLOWLIST = {
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "TEMP",
    "TMP",
    "TMPDIR",
    "TZ",
}


class PublicSmokeError(RuntimeError):
    """The public smoke run did not produce complete evidence."""


def _clean_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key in _SMOKE_ENV_ALLOWLIST
    }


def _repository_revision(repo: Path, env: dict[str, str]) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise PublicSmokeError(f"could not resolve repository revision: {result.stderr.strip()}")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0:
        raise PublicSmokeError(f"could not inspect repository status: {status.stderr.strip()}")
    if status.stdout.strip():
        raise PublicSmokeError("public smoke requires a clean repository")
    return result.stdout.strip()


def _assert_clean_repository(repo: Path, env: dict[str, str]) -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0:
        raise PublicSmokeError(f"could not inspect repository status: {status.stderr.strip()}")
    if status.stdout.strip():
        raise PublicSmokeError("public smoke requires a clean repository")


def _run(command: tuple[str, ...], repo: Path, env: dict[str, str], timeout: float) -> str:
    result = run_bounded(
        command,
        cwd=repo,
        env=env,
        timeout_s=timeout,
        inherit_host_environment=False,
    )
    output = result.stdout + result.stderr
    if result.timed_out:
        raise PublicSmokeError(f"command timed out: {' '.join(command)}\n{output[-4000:]}")
    if result.returncode != 0:
        raise PublicSmokeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{output[-4000:]}"
        )
    return output


def _pytest_counts(output: str) -> tuple[int, int]:
    matches = _PYTEST_COUNT.findall(output)
    counts = {kind: int(count) for count, kind in matches}
    passed = counts.get("passed", 0)
    skipped = counts.get("skipped", 0)
    if passed <= 0:
        raise PublicSmokeError("pytest output did not contain a positive passed count")
    return passed, skipped


def _write_immutable(path: Path, data: dict[str, object]) -> None:
    content = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise PublicSmokeError(f"smoke report target is not a regular file: {path}")
        if path.read_text(encoding="utf-8") == content:
            return
        raise PublicSmokeError(f"smoke report target already contains different data: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except FileExistsError as error:
        raise PublicSmokeError(f"smoke report target appeared during write: {path}") from error


def run_smoke(
    repo: Path,
    output: Path,
    *,
    repository_revision: str | None = None,
) -> dict[str, object]:
    repo = repo.expanduser().resolve()
    if not repo.is_dir():
        raise PublicSmokeError(f"repository is not a directory: {repo}")
    env = _clean_environment()
    revision = _repository_revision(repo, env)
    if repository_revision is not None:
        try:
            expected_revision = validate_evaluator_revision(repository_revision)
        except ValueError as error:
            raise PublicSmokeError(str(error)) from error
        if revision != expected_revision:
            raise PublicSmokeError(
                "supplied repository revision does not match the repository HEAD"
            )
    commands: list[dict[str, str]] = []
    tests_passed = 0
    tests_skipped = 0
    dry_run_args = ("--price-in", "0", "--price-out", "0", "--price-as-of", "2000-01-01")
    command_list = (
        ("ruff", (sys.executable, "-m", "ruff", "check", "."), 300.0),
        ("pytest", (sys.executable, "-m", "pytest", "-q"), 900.0),
        ("audit_corpus", (sys.executable, "-m", "scripts.audit_corpus"), 300.0),
        ("audit_plants", (sys.executable, "-m", "scripts.audit_plants"), 300.0),
        (
            "diagnostic_dry_run",
            (sys.executable, "-m", "scripts.diagnostic", "--dry-run", *dry_run_args),
            300.0,
        ),
        (
            "pilot_dry_run",
            (sys.executable, "-m", "scripts.pilot", "--dry-run", *dry_run_args),
            300.0,
        ),
    )
    for name, command, timeout in command_list:
        output_text = _run(command, repo, env, timeout)
        if name == "pytest":
            tests_passed, tests_skipped = _pytest_counts(output_text)
        commands.append({"name": name, "status": "pass"})

    report: dict[str, object] = {
        "schema": 1,
        "kind": "amb-challenge-public-smoke-report",
        "status": "pass",
        "repository_revision": revision,
        "python_version": platform.python_version(),
        "credentials_required": False,
        "database_required": False,
        "commands": commands,
        "tests_passed": tests_passed,
        "tests_skipped": tests_skipped,
    }
    validate_public_smoke_report(report, expected_repository_revision=revision)
    _write_immutable(output.expanduser().resolve(), report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repository-revision")
    args = parser.parse_args()
    try:
        report = run_smoke(
            args.repo,
            args.output,
            repository_revision=args.repository_revision,
        )
    except (OSError, PublicSmokeError, subprocess.TimeoutExpired, ValueError) as error:
        print(f"public smoke failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
