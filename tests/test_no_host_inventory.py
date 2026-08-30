"""No tracked configuration or script may name a host, an account, or a remote path.

This repository is public, and its `.gitignore` opens with the rule this guards:

    Secrets and local environment. Both halves of a server config are disclosure: tokens
    obviously, host inventories too. Neither ever lives in this tree.

That rule was broken between 2026-08-29 and 2026-08-30 by `adapters/recall/config.frozen.json`,
which carried an ssh alias, two paths under a named service account, the absolute path of a live
production `.env`, and a DSN naming another project's unix socket; and by
`scripts/launch_official.sh`, which hard-coded the same DSN as a default. No credential leaked,
because the DSN authenticates peer-over-socket. A host inventory is worth something anyway: it
tells a reader which machines exist and what runs on them.

## Two scopes, deliberately different

**Configuration and scripts must be CLEAN.** A fix controls these completely, so the assertion is
that the match set is empty.

**Published results are a RATCHET, not a clean sheet.** Eleven files under `results/` already
carry `/home/sentiment` from runs that predate the config leak, because the harness records the
absolute path a session ran under. Deleting them would retract published evidence, which is not a
test's decision to make. So this pins the known set: a new run may not ADD a file to it, and a
file may leave it, but the count may not grow without somebody editing this list and saying why.

## ⚠️ How to measure this on Windows, because the obvious command lies

`git grep '/home/sentiment'` from Git Bash reports ZERO matches on a tree that contains thousands.
MSYS rewrites any argument that looks like a Unix absolute path before git ever sees it, so the
pattern searched for is something like `C:/Program Files/Git/home/sentiment`. It fails silently
and in the reassuring direction. That artifact cost a wrong conclusion during the audit that found
this, twice, and it is why every check here reads bytes in Python instead of shelling out.

    MSYS_NO_PATHCONV=1 git grep -l '/home/sentiment' HEAD -- .    # the shell form that works
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: Strings that identify a machine, an account, or a location on one. Deliberately literal: a
#: cleverer pattern would drift from what a reader would actually grep for.
INVENTORY = (
    "/home/sentiment",
    "enterprise-rag-run",
    "pgsock",
    "amb-recall-pin",
    "recall-repos",
)

#: The serving host's alias. Kept apart from INVENTORY because it behaves differently: it appears
#: in PROSE across ten tracked files (comments explaining the transport, a preregistration's
#: method section, a report) where it is documentation rather than disclosure, and three of those
#: are preregistrations that must never be edited. What must never happen is the alias returning
#: as a configuration VALUE, which is what `test_no_config_value_names_a_machine` below checks.
#:
#: ⚠️ Added 2026-08-30 after a mutation test: re-adding `"ssh_host": "vps2"` to the frozen config
#: left every test in this file green, because INVENTORY held only path-shaped strings. The file
#: claimed "no tracked configuration or script may name a host" and enforced something narrower.
HOST_ALIAS = "vps2"

#: Tracked files that mention the alias in prose today, measured 2026-08-30. A ratchet, like
#: KNOWN_RESULT_ARTIFACTS: this set may shrink, and a NEW file mentioning the host is a finding.
KNOWN_PROSE_MENTIONS = frozenset(
    {
        "adapters/recall/adapter.py",
        "adapters/recall/config.frozen.json",
        "harness/mcp_probe.py",
        "preregistration/008-midband-task-calibration.md",
        "preregistration/009-bare-resolution-remeasure.md",
        "preregistration/014-official-run-recall-vs-mempalace.md",
        "reports/pilot-004-placebo-report.md",
        "scripts/launch_official.sh",
        "scripts/run_diagnostic_guarded.ps1",
        "tests/test_mcp_probe.py",
    }
)

#: `results/` files that already carry an absolute path, measured 2026-08-30 at commit 1cf4bde.
#: These are published run artifacts and predate the configuration leak. The set may SHRINK.
#: If it grows, a run has started recording host paths again and the harness needs the fix, not
#: this list.
KNOWN_RESULT_ARTIFACTS = frozenset(
    {
        "results/abstention-001-absent-records.jsonl",
        "results/abstention-001-superseded-records.jsonl",
        "results/diagnostic-010/environment.json",
        "results/diagnostic-010/records.final.jsonl",
        "results/diagnostic-010/records.jsonl",
        "results/midband-001/records.final.jsonl",
        "results/midband-001/records.jsonl",
        "results/resolution-001/records.final.jsonl",
        "results/resolution-001/records.jsonl",
        "results/smoke-abstention-absent/records.final.jsonl",
        "results/smoke-sup2-superseded/records.final.jsonl",
    }
)

#: The corpus is synthetic transcripts about a fictional company; "sentiment" appears in prose
#: there and means nothing. Only the PATH forms above are inventory, which is why this file never
#: matches on the bare account name.
_EXEMPT_PREFIXES = (".claude/", "scratch/", "tests/test_no_host_inventory.py")


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return [p for p in out.stdout.split("\0") if p]


def _files_naming_a_host() -> dict[str, list[str]]:
    """Path -> the inventory strings it contains. Reads bytes; see the MSYS note above."""

    hits: dict[str, list[str]] = {}
    for rel in _tracked_files():
        if rel.startswith(_EXEMPT_PREFIXES):
            continue
        path = REPO / rel
        try:
            blob = path.read_bytes()
        except (OSError, ValueError):
            continue
        found = [s for s in INVENTORY if s.encode("utf-8") in blob]
        if found:
            hits[rel] = found
    return hits


def test_no_tracked_config_or_script_names_a_host_or_a_remote_path() -> None:
    """RED before the fix: config.frozen.json and launch_official.sh both matched."""

    offenders = {
        rel: found
        for rel, found in _files_naming_a_host().items()
        if not rel.startswith("results/")
    }
    assert offenders == {}, (
        "a tracked file names a host, an account or a remote path, which .gitignore's first "
        "three lines forbid in this public tree:\n"
        + "\n".join(f"  {rel}: {', '.join(found)}" for rel, found in sorted(offenders.items()))
        + "\nName the variable in the frozen config and supply the value from the environment, "
        "the way adapters/mempalace/config.frozen.json always has. See "
        "adapters/recall/location.example.env."
    )


def test_no_new_published_artifact_records_an_absolute_host_path() -> None:
    """A ratchet on already-published runs: the set may shrink, never grow."""

    current = {rel for rel in _files_naming_a_host() if rel.startswith("results/")}
    added = current - KNOWN_RESULT_ARTIFACTS
    assert added == set(), (
        "a run has recorded absolute host paths into a published artifact:\n"
        + "\n".join(f"  {rel}" for rel in sorted(added))
        + "\nThese files are published. Fix what writes the path rather than adding them to "
        "KNOWN_RESULT_ARTIFACTS, unless a person has decided to accept the disclosure."
    )


def test_the_frozen_config_names_its_locations_rather_than_storing_them() -> None:
    """The positive form: every location key is an env var NAME, and no value is present."""

    import json

    cfg = json.loads(
        (REPO / "adapters" / "recall" / "config.frozen.json").read_text(encoding="utf-8")
    )
    for key in ("dsn_env", "ssh_host_env", "remote_root_env", "remote_python_env",
                "remote_env_file_env"):
        assert key in cfg, f"{key} is missing, so the adapter cannot resolve that location"
        assert cfg[key].isupper(), f"{key} should name an environment variable, got {cfg[key]!r}"
    for dead in ("dsn", "ssh_host", "remote_root", "remote_python", "remote_env_file"):
        assert dead not in cfg, (
            f"{dead!r} holds a VALUE in a file published with every run; it belongs in the "
            f"operator's untracked secrets file, named by {dead}_env"
        )


@pytest.mark.parametrize("key", ["ssh_host", "remote_root", "remote_python", "remote_env_file"])
def test_a_missing_location_refuses_rather_than_guessing(key: str, monkeypatch) -> None:
    """An unset location must raise and name the variable, never default to a host."""

    from adapters.recall.adapter import RecallAdapter

    adapter = RecallAdapter.__new__(RecallAdapter)
    import json

    adapter.config = json.loads(
        (REPO / "adapters" / "recall" / "config.frozen.json").read_text(encoding="utf-8")
    )
    monkeypatch.delenv(adapter.config[f"{key}_env"], raising=False)
    with pytest.raises(RuntimeError) as excinfo:
        adapter._location(key)
    assert adapter.config[f"{key}_env"] in str(excinfo.value)



def _machine_valued_paths(node, path: str = "") -> list[str]:
    """Every leaf STRING in a parsed config that names a machine or a location on one.

    `notes` is skipped: it is prose by design, the block that explains the configuration in
    words, and the alias is legitimately documented there. The prose ratchet above covers it.
    """

    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "notes":
                continue
            found.extend(_machine_valued_paths(value, f"{path}.{key}" if path else str(key)))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found.extend(_machine_valued_paths(value, f"{path}[{i}]"))
    elif isinstance(node, str):
        lowered = node.lower()
        if HOST_ALIAS in lowered or any(s in lowered for s in INVENTORY):
            found.append(f"{path} = {node!r}")
    return found


def test_no_new_file_names_the_serving_host() -> None:
    """A ratchet on prose. The alias is documentation where it stands; a NEW mention is a finding."""

    current = set()
    for rel in _tracked_files():
        if rel.startswith(_EXEMPT_PREFIXES) or rel.startswith("results/"):
            continue
        try:
            blob = (REPO / rel).read_bytes()
        except (OSError, ValueError):
            continue
        if HOST_ALIAS.encode("utf-8") in blob.lower():
            current.add(rel)
    added = current - KNOWN_PROSE_MENTIONS
    assert added == set(), (
        "a new tracked file names the serving host:\n"
        + "\n".join(f"  {rel}" for rel in sorted(added))
        + "\nIf it is prose, add it to KNOWN_PROSE_MENTIONS and say why. If it is a VALUE, it "
        "belongs in the operator's untracked secrets file."
    )


def test_no_config_value_names_a_machine() -> None:
    """The alias must never return as a configuration VALUE, only as prose.

    RED under the mutation that started this: re-adding `"ssh_host": "vps2"` to the frozen config
    was invisible to every other test in this file, because they scan file TEXT and the config
    already mentions the host in its `notes`. This walks the parsed object instead, skipping
    `notes`, which is the block that exists to explain the configuration in words.
    """

    import json

    for config in sorted(REPO.glob("adapters/*/config.frozen.json")):
        data = json.loads(config.read_text(encoding="utf-8"))
        suspect = _machine_valued_paths(data)
        assert not suspect, (
            f"{config.relative_to(REPO)} stores a machine or a path as a VALUE:\n"
            + "\n".join(f"  {s}" for s in suspect)
            + "\nName the environment variable instead, the way the *_env keys do."
        )


def test_one_resolver_serves_every_location_consumer() -> None:
    """Two copies of a rule drift, and the drift is invisible until one of them defaults.

    `adapters/recall/adapter.py` and `scripts/prepare_recall_corpora.py` both resolve host
    locations. They used to carry near-identical bodies, so adding a sixth location key could
    leave one refusing and the other guessing. They now wrap ONE resolver, differing only in the
    exception each layer wants, and this pins that plus the invariant that every key the config
    names is a key the resolver can serve.
    """

    import inspect
    import json

    from adapters.recall import adapter as recall_adapter
    from adapters.recall.adapter import RecallAdapter
    from scripts import prepare_recall_corpora

    # By OBJECT, not by scanning text for the next `def`: `_location` is a method on the adapter
    # and a module-level function in the prepare script, so a text scan ran past the method
    # boundary and swept up `os.environ.get` from four unrelated methods.
    consumers = {
        "adapters/recall/adapter.py": RecallAdapter._location,
        "scripts/prepare_recall_corpora.py": prepare_recall_corpora._location,
    }
    for module_path, accessor in consumers.items():
        body = inspect.getsource(accessor)
        assert "resolve_location(" in body, (
            f"{module_path}'s _location does not delegate to the shared resolver"
        )
        assert "os.environ" not in body, (
            f"{module_path}'s _location reads the environment itself instead of delegating; that "
            f"duplication is what this test exists to prevent, because two copies of a rule "
            f"drift and the drift is invisible until one of them defaults"
        )

    # every *_env key the frozen config names must be resolvable, and vice versa
    cfg = json.loads(
        (REPO / "adapters" / "recall" / "config.frozen.json").read_text(encoding="utf-8")
    )
    named = {k[: -len("_env")] for k in cfg if k.endswith("_env")}
    signature = inspect.signature(recall_adapter.resolve_location)
    assert list(signature.parameters) == ["config", "key"]
    for key in sorted(named):
        try:
            recall_adapter.resolve_location(cfg, key)
        except LookupError:
            pass  # unset in this environment, which is the refusal working
        except KeyError:  # pragma: no cover - would mean the config and resolver disagree
            raise AssertionError(f"the config names {key}_env but the resolver cannot use it")
