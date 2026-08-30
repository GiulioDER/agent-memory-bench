"""A corpus that did not fully arrive must refuse, not stamp itself as correct.

`scripts/prepare_recall_corpora.py` ships a rendered corpus to the serving host, builds a
generation from it, calibrates, promotes, and writes a fingerprint stamp that the adapter later
reads to confirm the tenant is serving THIS corpus.

The ship step printed its remote file count and checked nothing:

    r = ssh(f"cd ... && rm -rf {tenant} && tar -xzf {archive} && ls {tenant} | wc -l")
    print(f"  shipped {r.stdout.strip()} file(s)")

Reproduced during the 2026-08-30 audit against a deliberately truncated archive: 12 of 60 files
extracted, returncode 2, and the operator saw `shipped  file(s)` with a blank count. Everything
downstream then succeeds over the partial feed, because `manifest inventory` inventories whatever
is on disk and `generation build --manifest-sha256` hashes the manifest that was just built from
it, i.e. against itself.

⚠️ **The adapter's later identity check cannot catch this, which is why the guard has to be here.**
`RecallAdapter._verify_remote_generation` compares the stamp against `corpus_fingerprint(corpus)`
computed from the LOCAL manifest, and the stamp was written from that same local fingerprint. The
comparison is circular. This is the only point in the pipeline where the rendered count and the
arrived count both exist, so it is the only point where a truncation is visible at all.

The `rm -rf {tenant}` runs FIRST, so by the time a short extraction is detectable the previous
good corpus is already gone. Refusing loudly is the whole fix: there is nothing to fall back to.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _result(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["ssh"], returncode=returncode, stdout=stdout, stderr=stderr
    )


@pytest.fixture
def mod(monkeypatch):
    """The module under test, with host locations supplied so `_location` does not refuse."""

    monkeypatch.setenv("RECALL_DSN", "postgresql://unused.invalid/bench")
    monkeypatch.setenv("AMB_RECALL_SSH_HOST", "unused.invalid")
    monkeypatch.setenv("AMB_RECALL_REMOTE_ROOT", "/nonexistent/bench")
    monkeypatch.setenv("AMB_RECALL_REMOTE_PYTHON", "/nonexistent/bench/.venv/bin/python")
    monkeypatch.setenv("AMB_RECALL_REMOTE_ENV_FILE", "/nonexistent/recall/.env")

    from scripts import prepare_recall_corpora

    return prepare_recall_corpora


def _stub_everything_remote(mod, monkeypatch, *, ship_rc: int, ship_out: str, rendered: int):
    """Let `prepare()` reach the ship check with nothing touching a host or the real corpus."""

    calls: list[str] = []

    def fake_ssh(command: str, **_kw):
        calls.append(command)
        if "rm -rf" in command and "tar -xzf" in command:
            return _result(ship_rc, ship_out, "tar: unexpected end of file")
        if command.startswith("cat "):
            return _result(1, "", "no such file")  # no prior stamp, so nothing short-circuits
        return _result(0, "", "")

    def fake_recall(_tenant, args, **_kw):
        calls.append(f"recall {args}")
        return _result(0, "ok", "")

    class _Corpus:
        def __init__(self) -> None:
            self.sessions = [f"s{i}.jsonl" for i in range(rendered)]

        def verify(self) -> None:
            return None

    monkeypatch.setattr(mod, "ssh", fake_ssh)
    monkeypatch.setattr(mod, "recall", fake_recall)
    monkeypatch.setattr(mod, "assemble", lambda *a, **k: None)
    monkeypatch.setattr(mod, "selection_for", lambda *a, **k: ["ts-a"])
    monkeypatch.setattr(mod.CorpusManifest, "load", classmethod(lambda cls, root: _Corpus()))
    monkeypatch.setattr(mod, "corpus_fingerprint", lambda c: "f" * 64)
    monkeypatch.setattr(mod, "render_corpus", lambda *a, **k: rendered)
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _result(0, "", ""))
    return calls


def _run(mod, calls_holder):
    return mod.prepare("absent", 1, "bench-test", force=True)


def test_a_short_ship_refuses_before_building(mod, monkeypatch):
    """RED before the fix: 3 arriving where 5 were rendered printed `shipped 3` and built anyway.

    This is the silent case and the dangerous one: a truncated feed inventories, builds,
    calibrates and promotes without a single non-zero exit code anywhere.
    """

    calls = _stub_everything_remote(mod, monkeypatch, ship_rc=0, ship_out="3", rendered=5)
    with pytest.raises(SystemExit) as excinfo:
        _run(mod, calls)
    message = str(excinfo.value)
    assert "5" in message and "3" in message, message
    assert not any("generation build" in c for c in calls), (
        "reached `generation build` over a corpus that never fully arrived"
    )


def test_a_failed_ship_refuses(mod, monkeypatch):
    """RED before the fix: the returncode was never read, so it printed and ran on.

    ⚠️ `ship_out="5"`, matching `rendered`, on purpose. The first version of this test used
    `ship_out=""`, so `int("")` raised and the refusal came from the unparseable-count branch
    instead: deleting the returncode check left all five tests in this file green. A non-zero exit
    with a plausible count is the only input that can ONLY be caught by the returncode.
    """

    calls = _stub_everything_remote(mod, monkeypatch, ship_rc=2, ship_out="5", rendered=5)
    with pytest.raises(SystemExit) as excinfo:
        _run(mod, calls)
    message = str(excinfo.value)
    assert "ship FAILED" in message
    assert "unexpected end of file" in message, (
        "the refusal must carry the remote stderr, which is what identifies the returncode "
        "branch rather than the count branch"
    )
    assert not any("generation build" in c for c in calls)


def test_a_ship_that_returns_no_count_refuses(mod, monkeypatch):
    """A zero exit with unparseable stdout is a failed ship, not a count of zero."""

    calls = _stub_everything_remote(mod, monkeypatch, ship_rc=0, ship_out="", rendered=5)
    with pytest.raises(SystemExit) as excinfo:
        _run(mod, calls)
    assert "ship FAILED" in str(excinfo.value)


def test_a_matching_ship_gets_past_the_check(mod, monkeypatch):
    """Control: the honest case must proceed, or the three above pass by refusing everything."""

    calls = _stub_everything_remote(mod, monkeypatch, ship_rc=0, ship_out="5", rendered=5)
    try:
        _run(mod, calls)
    except SystemExit:
        pass  # it exits later on a stubbed step; what matters is that it got past the ship check
    assert any("manifest inventory" in c for c in calls), (
        "a ship whose count matches what was rendered was refused"
    )


def test_an_unset_location_refuses_rather_than_guessing(mod, monkeypatch):
    """The frozen config names the variable; an unset one must refuse, never default to a host."""

    monkeypatch.delenv("AMB_RECALL_REMOTE_ROOT", raising=False)
    with pytest.raises(SystemExit) as excinfo:
        mod._location("remote_root")
    assert "AMB_RECALL_REMOTE_ROOT" in str(excinfo.value)
