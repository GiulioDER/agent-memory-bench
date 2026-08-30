"""The two launchers must agree, and must actually launch.

These are STATIC checks on the scripts' text. That is not a compromise: running either one starts
the official run, and both properties below are textual. What cannot be checked statically is
checked in `tests/test_costs.py`, which owns the pricing contract itself.

## What happened

`scripts/launch_official.ps1` omitted `--price-in`, `--price-out` and `--price-as-of`.
`harness/costs.py::pricing_from_args` requires all three whenever `--dry-run` is absent, and
`scripts/abstention.py` calls it before the first ingest. So the PowerShell launcher did not
produce a mispriced run: it produced NO run. The child exited at argument validation in under a
second while the console printed `launched detached, pid N` and wrote a pid file, because
`Start-Process -PassThru` returns as soon as the child starts.

The bash twin has passed all three flags since the same bug cost a launch there, which is the
argument for this file: two launchers that must stay identical, and nothing comparing them.

⚠️ A dry run cannot catch this class. `pricing_from_args` is called under `if not args.dry_run`,
so `--dry-run` is exactly the path where the missing flags do not matter.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SH = REPO / "scripts" / "launch_official.sh"
PS1 = REPO / "scripts" / "launch_official.ps1"

#: Frozen by preregistration 002 and matched by every run since, so this run's scores stay
#: comparable to the pilots'. A launcher that disagrees produces a run that cannot be compared.
FROZEN_RATES = {"0.0574", "0.1148", "2026-08-22"}

REQUIRED_PRICE_FLAGS = ("--price-in", "--price-out", "--price-as-of")


def test_both_launchers_pass_every_required_price_flag() -> None:
    """RED before the fix: the ps1 carried none of the three, and died at argument validation."""

    for script in (SH, PS1):
        text = script.read_text(encoding="utf-8")
        missing = [flag for flag in REQUIRED_PRICE_FLAGS if flag not in text]
        assert not missing, (
            f"{script.name} does not pass {missing}. harness/costs.py refuses without them, "
            f"before the first ingest, so this launcher starts nothing while reporting success."
        )


def test_the_launchers_agree_on_the_frozen_rates() -> None:
    """Two launchers with different rates produce two runs that cannot be compared."""

    for script in (SH, PS1):
        text = script.read_text(encoding="utf-8")
        found = {rate for rate in FROZEN_RATES if rate in text}
        assert found == FROZEN_RATES, (
            f"{script.name} is missing {sorted(FROZEN_RATES - found)}; preregistration 002 froze "
            f"these and every published run has used them"
        )


def test_the_shell_launcher_does_not_re_split_its_argv() -> None:
    """RED before the fix: `${ARGV[*]}` reached a nested `bash -c` and was re-parsed.

    Demonstrated during the audit with MODEL='deepseek; echo INJECTED >&2', which the inner shell
    executed as its own command. Every value in ARGV is environment-overridable.
    """

    text = SH.read_text(encoding="utf-8")
    assert "${ARGV[*]}" not in text, (
        "the argv array is interpolated in star form into a shell string, so a second shell "
        "word-splits and re-parses it; use printf %q over \"${ARGV[@]}\""
    )
    assert "printf -v QUOTED_ARGV" in text, "argv reaches the inner shell without being re-quoted"


def test_the_powershell_launcher_uses_the_pinned_interpreter() -> None:
    """PATH `python` is the hazard that produced `SchemaTooNew` fourteen sessions into a run.

    A dead stdio server is not an error in a transcript: it is memory_call_count = 0, which is
    indistinguishable from a model that chose not to search.
    """

    text = PS1.read_text(encoding="utf-8")

    # ⚠️ Positive assertions. The first version was a negative regex matching one historical
    # spelling, `-FilePath "python"`, so `-FilePath python` unquoted, `-FilePath $env:PYTHON`, or
    # deleting Start-Process altogether all passed. And `".venv" in text` was satisfied by the
    # throw message. These pin the variable that is LAUNCHED to the variable that is RESOLVED.
    assert re.search(r'\$python\s*=\s*Join-Path\s+\$repo\s+"\.venv', text), (
        "the launcher does not resolve the interpreter from the repo venv"
    )
    assert re.search(r"Start-Process\s+-FilePath\s+\$python\b", text), (
        "the launcher does not START the interpreter it resolved; a PATH `python` is how "
        "abstention-002 came up on an editable worktree and refused the corpus with SchemaTooNew"
    )


def test_both_launchers_check_the_child_is_still_alive() -> None:
    """Backgrounding says nothing about whether the child SURVIVED.

    The PowerShell launcher got this check first and its twin went without it for a while, which
    is precisely the asymmetry this file's docstring names: two launchers that must stay
    identical, and nothing comparing them. The bash one is the launcher that actually starts the
    official run, and `systemd-run --user --scope` failing for want of a user session bus on a
    detached ssh login is a live failure mode, not a hypothetical.
    """

    # ⚠️ EXECUTED, not grepped. The first version asserted `'kill -0 "$PID"' in sh`, and the
    # mutation `if false; then  # kill -0 "$PID"` satisfied it -- the comment explaining the guard
    # WAS the guard, for the test's purposes. That trap caught four separate assertions in this
    # repository on 2026-08-30, so this one extracts the block and runs it against a dead pid.
    sh = SH.read_text(encoding="utf-8")
    marker = 'if ! kill -0 "$PID"'
    assert marker in sh, "the shell launcher does not test whether the child is still running"

    block = sh[sh.index(marker) : sh.index("\nfi\n", sh.index(marker)) + 4]
    script = (
        'set -e\n'
        'PID=999999\n'          # a pid that cannot be alive
        'LOG=/dev/null\n'
        'REPO=$PWD\n'
        'RUN_ID=probe\n'
        'mkdir -p "$REPO/results/logs"\n'
        'touch "$REPO/results/logs/$RUN_ID.pid"\n'
        + block
        + '\necho "REACHED THE SUCCESS PATH"\n'
    )
    # `["bash", ...]` resolves through CreateProcess on Windows, which finds WSL's bash.exe in
    # System32 before Git Bash and then cannot see the working directory. `shutil.which` finds
    # the POSIX one on PATH.
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("no POSIX shell available to execute the launcher's liveness block")
    result = subprocess.run(
        [bash, "-c", script], capture_output=True, text=True, cwd=REPO, timeout=60, check=False
    )
    assert result.returncode == 1, (
        f"the launcher's liveness block did not refuse a dead process (exit {result.returncode}); "
        f"stdout={result.stdout!r}"
    )
    assert "REACHED THE SUCCESS PATH" not in result.stdout, (
        "execution continued past a dead child, so `launched detached, pid N` would still print"
    )
    assert "THE RUN DID NOT START" in result.stderr
    assert not (REPO / "results" / "logs" / "probe.pid").exists(), (
        "a pid file for a process that never ran points an operator at nothing"
    )


def test_the_powershell_launcher_checks_the_child_is_still_alive() -> None:
    """RED before the fix: it printed a pid for a process that had already exited.

    `Start-Process -PassThru` returns when the child STARTS. Reporting "launched" on that alone is
    how a missing price flag turned into an operator leaving a dead run overnight.
    """

    text = PS1.read_text(encoding="utf-8")

    # ⚠️ Not `"HasExited" in text`, which any comment or disabled branch satisfies: replacing the
    # test with `if ($false) { # HasExited` passed. The liveness guard is four behaviours, so pin
    # the ones that matter -- it waits, it tests, and a dead child exits non-zero without leaving
    # a pid file claiming otherwise.
    assert re.search(r"Start-Sleep[^\n]*\n[^\n]*if\s*\(\$proc\.HasExited\)", text), (
        "nothing waits before testing the child, so a process that dies in under a second is "
        "still reported as launched"
    )
    block = text[text.index("HasExited"):]
    assert "exit 1" in block, "a dead child must make the launcher exit non-zero"
    assert "Remove-Item $pidFile" in block, (
        "a pid file for a process that never ran points an operator at nothing"
    )
