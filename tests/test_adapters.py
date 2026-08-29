import hashlib
import json
from pathlib import Path

import pytest

from adapters.bare.adapter import BareAdapter
from adapters.claude_md.adapter import ClaudeMdAdapter
from adapters.fs_grep.adapter import FsGrepAdapter
from harness.adapters.base import CorpusManifest, resolve_corpus_path
from harness.adapters.registry import AdapterRegistry


@pytest.fixture()
def corpus(tmp_path):
    root = tmp_path / "corpus"
    sessions_dir = root / "sessions" / "t1"
    sessions_dir.mkdir(parents=True)
    transcript = sessions_dir / "s01.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "content": "why does CI fail?", "ts": 1}),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": "found it: mig.sh truncates names",
                        "tool_name": "Bash",
                        "tool_result": "exit 0",
                        "ts": 2,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    rel = "sessions/t1/s01.jsonl"
    manifest = {
        "sessions": {rel: hashlib.sha256(transcript.read_bytes()).hexdigest()}
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return CorpusManifest.load(root)


@pytest.fixture()
def base_prompt(tmp_path):
    prompt = tmp_path / "claude_md_bundle.md"
    prompt.write_text("# CLAUDE.md\n\nproject notes\n", encoding="utf-8")
    return prompt


def test_corpus_manifest_verify_refuses_drifted_bytes(corpus):
    corpus.verify()
    (corpus.root / "sessions" / "t1" / "s01.jsonl").write_text("tampered", "utf-8")
    with pytest.raises(ValueError, match="identical across arms"):
        corpus.verify()


@pytest.mark.parametrize("relative_path", ["../outside.jsonl", "C:/outside.jsonl"])
def test_corpus_manifest_rejects_paths_outside_root(tmp_path, relative_path):
    with pytest.raises(ValueError, match="escapes its root"):
        resolve_corpus_path(tmp_path / "corpus", relative_path)


def test_bare_adapter_builds_a_memoryless_spec(tmp_path):
    spec = BareAdapter().build(tmp_path, "bench-bare-0")
    assert spec.mcp_config is None
    assert spec.append_system_prompt_file is None
    assert BareAdapter().admission_signal().mcp_tool_prefixes == ()


def test_claude_md_adapter_freezes_the_prompt_hash(tmp_path, base_prompt):
    adapter = ClaudeMdAdapter(base_prompt)
    spec = adapter.build(tmp_path, "bench-claude_md-0")
    expected = hashlib.sha256(base_prompt.read_bytes()).hexdigest()
    assert spec.metadata["prompt_sha256"] == expected
    assert adapter.admission_signal().prompt_sha256 == expected


def test_fs_grep_ingest_renders_verbatim_markdown(tmp_path, corpus, base_prompt):
    adapter = FsGrepAdapter(tmp_path / "staging", base_prompt)
    report = adapter.ingest(corpus, "bench-fs_grep-0")
    assert report.items_stored == 1
    assert report.llm_input_tokens == 0
    rendered = (
        tmp_path / "staging" / "bench-fs_grep-0" / "memory" / "sessions__t1__s01.md"
    ).read_text(encoding="utf-8")
    assert "mig.sh truncates names" in rendered
    spec = adapter.build(tmp_path, "bench-fs_grep-0")
    assert spec.metadata["sandbox_overlay"].endswith("memory")
    prompt_text = (tmp_path / "staging" / "bench-fs_grep-0" / "prompt.md").read_text(
        encoding="utf-8"
    )
    # The nudge sits at the TOP, ahead of the static bundle: buried instructions measured
    # a 0% usage rate in the ancestor harness.
    assert prompt_text.index("memory/") < prompt_text.index("# CLAUDE.md")


def test_fs_grep_build_refuses_an_uningested_namespace(tmp_path, base_prompt):
    adapter = FsGrepAdapter(tmp_path / "staging", base_prompt)
    with pytest.raises(FileNotFoundError, match="not been ingested"):
        adapter.build(tmp_path, "bench-fs_grep-9")


def test_registry_fills_forbidden_prefixes_for_the_run_roster(tmp_path, base_prompt):
    from adapters.recall.adapter import RecallAdapter

    registry = AdapterRegistry()
    registry.register(BareAdapter())
    registry.register(ClaudeMdAdapter(base_prompt))
    registry.register(RecallAdapter(tmp_path / "staging", base_prompt))
    signals = registry.signals(("bare", "recall"))
    assert signals["bare"].forbidden_prefixes == ("mcp__recall__",)
    assert signals["recall"].forbidden_prefixes == ()
    with pytest.raises(KeyError):
        registry.get("mem0")


def test_the_mcp_server_runs_the_pinned_build_whatever_the_transport(tmp_path, base_prompt, monkeypatch):
    """The read path and the write path must be ONE build of recall, on either transport.

    Measured 2026-08-29, fourteen sessions into `abstention-002`: the ingest wrote through a pinned
    0.10.0 and applied schema migration 0015, while the server came up on a PATH `python` holding
    an editable development worktree and refused the corpus with
    ``SchemaTooNew: unknown migration(s) ['0015']``. A dead stdio server is not an error in the
    transcript: it is `memory_call_count = 0`, indistinguishable from a model that chose not to
    search.

    The invariant survives the move to SSH, it is just enforced differently. Locally the config's
    `"python"` resolves to `sys.executable`. Over SSH the server is started by the interpreter the
    config PINS as `remote_python`, and that path must appear in the remote command, because SSH
    forwards no environment and a bare `python` there would resolve against the remote PATH.

    Mutation: dropping `remote_python` from the remote command, or returning
    ``str(self.config["command"])`` on the local path.
    """

    import sys

    from adapters.recall.adapter import RecallAdapter

    monkeypatch.setenv("RECALL_DSN", "postgresql://unused.invalid/bench")
    adapter = RecallAdapter(tmp_path / "staging", base_prompt)
    spec = adapter.build(tmp_path / "session", "ns")
    server = json.loads(Path(spec.mcp_config).read_text(encoding="utf-8"))["mcpServers"]["recall"]

    transport = str(adapter.config.get("transport", "local"))
    if transport in ("ssh", "host"):
        if transport == "ssh":
            assert server["command"] == "ssh"
            assert server["args"][-2] == str(adapter.config["ssh_host"])
        else:
            # `host` means the harness runs ON the serving host, so the same command string is
            # handed to a shell rather than to ssh. The invariant this test exists for is
            # untouched: the PINNED interpreter must still be named in it.
            assert server["command"] == "/bin/bash"
            assert server["args"][0] == "-lc"
        remote = server["args"][-1]
        assert str(adapter.config["remote_python"]) in remote, (
            "the remote command must name the PINNED interpreter; a bare `python` would resolve "
            "against the remote PATH and could be a different build than the ingest used"
        )
        assert "recall_mcp.server" in remote
        assert "unset RECALL_TRUST_MODE" in remote, (
            "strict is expressed by ABSENCE; setting the variable to any string is how a corpus "
            "ends up served relaxed while the config claims otherwise"
        )
    else:
        assert server["command"] == sys.executable


def test_a_local_config_naming_a_real_executable_is_passed_through(tmp_path, base_prompt, monkeypatch):
    """Resolving the interpreter must not seize a config that names a specific binary.

    `"python"` is a placeholder and gets resolved. Anything else is a deliberate choice about which
    executable to run, and a benchmark that silently overrode it would be lying about the wiring a
    vendor reviewed.
    """

    from adapters.recall.adapter import RecallAdapter

    monkeypatch.setenv("RECALL_DSN", "postgresql://unused.invalid/bench")
    adapter = RecallAdapter(tmp_path / "staging", base_prompt)
    adapter.config["transport"] = "local"
    adapter.config["command"] = "/opt/vendor/bin/recall-server"
    spec = adapter.build(tmp_path / "session", "ns")
    command = json.loads(Path(spec.mcp_config).read_text(encoding="utf-8"))["mcpServers"]["recall"][
        "command"
    ]
    assert command == "/opt/vendor/bin/recall-server"


def test_registry_refuses_duplicate_names():
    registry = AdapterRegistry()
    registry.register(BareAdapter())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(BareAdapter())


def test_render_corpus_refuses_or_disambiguates_name_collisions(tmp_path):
    from harness.transcripts import render_corpus

    root = tmp_path / "corpus"
    for sub in ("sessions/task-a", "sessions/task-b"):
        d = root / sub
        d.mkdir(parents=True)
        (d / "p01.jsonl").write_text('{"role": "user", "content": "x", "ts": "1"}\n', "utf-8")
    paths = sorted(root.rglob("*.jsonl"))

    # Without a root, the collision must RAISE (the silent overwrite shipped a corpus
    # holding one precursor out of twenty-four).
    with pytest.raises(ValueError, match="collision"):
        render_corpus(paths, tmp_path / "flat")

    # With a root, both survive under self-identifying names.
    count = render_corpus(paths, tmp_path / "mirrored", root=root)
    names = sorted(p.name for p in (tmp_path / "mirrored").glob("*.md"))
    assert count == 2
    assert names == ["sessions__task-a__p01.md", "sessions__task-b__p01.md"]
