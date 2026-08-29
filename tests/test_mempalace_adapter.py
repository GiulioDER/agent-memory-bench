"""The `mempalace` arm: wiring, refusals, and the two defects it must not repeat.

These tests do not run MemPalace. They pin the parts of the arm that would otherwise fail
silently: an arm registered in one place and forgotten in another, a store that ingested nothing,
a palace path too long for onnxruntime to load its DLL from, and the per-task prompt that
`diagnostic-001` got wrong through this same code path in the recall adapter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.mempalace.adapter import MemPalaceAdapter, drawers_filed
from harness import instructions
from harness.instructions import APPENDIX_MAX_BYTES

REPO = Path(__file__).resolve().parents[1]
CONFIG = json.loads(
    (REPO / "adapters" / "mempalace" / "config.frozen.json").read_text(encoding="utf-8")
)


@pytest.fixture()
def base_prompt(tmp_path):
    path = tmp_path / "claude_md.md"
    path.write_text("# Fixture README\n\nStatic half, shared by every arm.\n", encoding="utf-8")
    return path


@pytest.fixture()
def adapter(tmp_path, base_prompt, monkeypatch):
    """An adapter pointed at a short palace root and a venv stub, so no product is needed."""

    venv = tmp_path / "v"
    (venv / "Scripts").mkdir(parents=True)
    for stem in ("python.exe", "mempalace-mcp.exe"):
        (venv / "Scripts" / stem).write_bytes(b"")
    monkeypatch.setenv(CONFIG["venv_env"], str(venv))
    monkeypatch.setenv(CONFIG["palace_root_env"], str(tmp_path / "p"))
    return MemPalaceAdapter(tmp_path / "staging", base_prompt)


# --------------------------------------------------------------------- registration


def test_the_arm_is_registered_everywhere_a_run_reads_it():
    """An arm listed in ARMS but missing from MEMORY_ARMS carries no memory protocol."""

    import scripts.pilot as pilot

    assert "mempalace" in pilot.ARMS
    assert "mempalace" in pilot.MEMORY_ARMS
    assert "mempalace" in pilot.SELF_INGESTING_ARMS
    # recall is ingested out of band and must never be ingested by the runner.
    assert "recall" not in pilot.SELF_INGESTING_ARMS


def test_adapter_for_builds_a_mempalace_adapter(tmp_path, base_prompt):
    import scripts.pilot as pilot

    built = pilot.adapter_for(
        "mempalace", {"claude_md": base_prompt}, tmp_path, {"mempalace": ""}
    )
    assert isinstance(built, MemPalaceAdapter)


def test_build_bundles_writes_a_bundle_for_every_instructed_arm(tmp_path, base_prompt):
    """The regression the derived loop fixes: a new arm's instruction was silently dropped.

    `build_bundles` used to iterate a literal ("protocol", "fs_grep", "recall"), so an arm wired
    into ARMS, MEMORY_ARMS and `adapter_for` still received a prompt with no memory instruction in
    it, and the run would have measured an arm that was never told it had a memory.
    """

    import scripts.pilot as pilot

    task = type("T", (), {"path": tmp_path / "nonexistent-fixture"})()
    texts = {"bare": "", "claude_md": "", "mempalace": "SEARCH THE PALACE"}
    bundles = pilot.build_bundles(task, tmp_path / "cfg", texts)

    assert "mempalace" in bundles
    assert "SEARCH THE PALACE" in bundles["mempalace"].read_text(encoding="utf-8")


# --------------------------------------------------------------------- instruction fairness


def test_the_appendix_is_within_the_shared_cap():
    appendix = (REPO / "adapters" / "mempalace" / "instruction_appendix.md").read_bytes()
    assert 0 < len(appendix) <= APPENDIX_MAX_BYTES


def test_the_arm_carries_the_shared_protocol_verbatim():
    """Whatever else it says, it may not carry coaching the other memory arms do not get."""

    for neutral in (False, True):
        text = MemPalaceAdapter.shared_instruction(neutral=neutral)
        instructions.assert_shared_protocol({"mempalace": text}, neutral=neutral)


def test_it_shares_the_protocol_with_the_other_memory_arms():
    from adapters.fs_grep.adapter import FS_GREP_SEARCH_SENTENCE, FsGrepAdapter

    texts = {
        "mempalace": MemPalaceAdapter.shared_instruction(),
        "fs_grep": instructions.compose("fs_grep", FS_GREP_SEARCH_SENTENCE),
    }
    instructions.assert_shared_protocol(texts)


def test_the_search_sentence_names_the_tool_the_gate_admits():
    prefix = CONFIG["tool_prefix"]
    assert f"{prefix}mempalace_search" in CONFIG["search_sentence"]
    assert "mempalace_search" in CONFIG["allowed_tools"]


# --------------------------------------------------------------------- the frozen config


def test_no_write_tool_is_allowed_into_a_graded_session():
    """No runner calls MemoryAdapter.restore, so a session that wrote would poison later seeds."""

    forbidden = ("add_", "update_", "delete_", "kg_add", "kg_invalidate", "kg_supersede",
                 "create_", "checkpoint", "mine", "sync", "diary_write", "patch_submit")
    offenders = [
        tool
        for tool in CONFIG["allowed_tools"]
        if any(marker in tool for marker in forbidden)
    ]
    assert offenders == []


def test_the_tool_prefix_is_not_shared_with_another_arm():
    """Two arms claiming one prefix makes them indistinguishable to the admission gate."""

    recall = json.loads(
        (REPO / "adapters" / "recall" / "config.frozen.json").read_text(encoding="utf-8")
    )
    assert CONFIG["tool_prefix"] != recall["tool_prefix"]


def test_admission_signal_claims_the_mcp_prefix(adapter):
    signal = adapter.admission_signal()
    assert signal.arm == "mempalace"
    assert signal.mcp_tool_prefixes == (CONFIG["tool_prefix"],)


def test_describe_publishes_the_pin_and_the_config_hash(adapter):
    described = adapter.describe()
    assert described["package_pin"] == CONFIG["package_pin"]
    assert described["ingest_mode"] == "convos"
    assert len(described["config_sha256"]) == 64


# --------------------------------------------------------------------- refusals


def test_it_refuses_without_a_named_virtualenv(tmp_path, base_prompt, monkeypatch):
    monkeypatch.delenv(CONFIG["venv_env"], raising=False)
    monkeypatch.setenv(CONFIG["palace_root_env"], str(tmp_path / "p"))
    bare = MemPalaceAdapter(tmp_path / "staging", base_prompt)
    with pytest.raises(RuntimeError, match=CONFIG["venv_env"]):
        bare.build(tmp_path / "session", "ns")


def test_it_refuses_a_palace_path_too_long_for_onnxruntime(tmp_path, base_prompt, monkeypatch):
    """The measured failure this guard exists for reports itself as 'onnxruntime is not installed'.

    chromadb catches the DLL ImportError and re-raises it with that text, so without this refusal
    the arm scores zero and nothing in the record names the reason.
    """

    deep = tmp_path / ("d" * 80) / ("e" * 80)
    monkeypatch.setenv(CONFIG["venv_env"], str(tmp_path))
    monkeypatch.setenv(CONFIG["palace_root_env"], str(deep))
    long_path = MemPalaceAdapter(tmp_path / "staging", base_prompt)
    with pytest.raises(RuntimeError, match="onnxruntime"):
        long_path._palace_dir("ns")


def test_a_short_palace_path_is_accepted(adapter):
    assert adapter._palace_dir("ns").name == "ns"


# --------------------------------------------------------------------- ingest accounting


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("  Files processed: 6\n  Drawers filed: 44\n\n  By room:\n", 44),
        ("Drawers filed: 0", 0),
        ("no such line anywhere", 0),
        ("Drawers filed: not-a-number", 0),
    ],
)
def test_drawers_filed_reads_the_count_mempalace_prints(stdout, expected):
    assert drawers_filed(stdout) == expected


def test_an_ingest_that_filed_nothing_is_a_failure_not_an_empty_store(monkeypatch, adapter):
    """`mine` exits 0 having filed nothing when every file was already filed.

    Trusting the exit code would publish a silent, empty store as a product that found nothing.
    """

    class Result:
        returncode = 0
        stdout = "  Files skipped (already filed): 6\n  Drawers filed: 0\n"
        stderr = ""

    monkeypatch.setattr("adapters.mempalace.adapter.subprocess.run", lambda *a, **k: Result())

    class Corpus:
        root = Path(".")
        sessions: dict[str, str] = {}

        def verify(self):
            return None

    with pytest.raises(RuntimeError, match="no drawers filed"):
        adapter.ingest(Corpus(), "ns")


# --------------------------------------------------------------------- per-task prompts


def test_each_task_gets_its_own_prompt(tmp_path, adapter):
    """`diagnostic-001` served task one's README to all 24 recall sessions through this path."""

    first = adapter.build_for_task(tmp_path / "s1", "ns", "task-one", "do a thing")
    second = adapter.build_for_task(tmp_path / "s2", "ns", "task-two", "do another")

    assert first.append_system_prompt_file != second.append_system_prompt_file
    assert Path(first.append_system_prompt_file).parent == tmp_path / "s1"
    assert Path(second.append_system_prompt_file).parent == tmp_path / "s2"


def test_the_instruction_sits_above_the_static_half(tmp_path, adapter, base_prompt):
    spec = adapter.build_for_task(tmp_path / "s", "ns", "t", "prompt")
    text = Path(spec.append_system_prompt_file).read_text(encoding="utf-8")
    # Measured on the recall arm: an instruction buried under the bundle produced a 0% search rate.
    assert text.index("Using this project's memory") < text.index("Fixture README")


def test_the_mcp_config_points_at_this_namespace_palace(tmp_path, adapter):
    spec = adapter.build_for_task(tmp_path / "s", "ns", "t", "prompt")
    config = json.loads(Path(spec.mcp_config).read_text(encoding="utf-8"))
    server = config["mcpServers"][CONFIG["server_name"]]
    assert server["args"] == ["--palace", str(adapter._palace_dir("ns"))]
    # An MCP env block REPLACES the environment; without SystemRoot the server dies in Winsock.
    assert "PATH" in server["env"]


def test_every_allowed_tool_reaches_the_session_prefixed(tmp_path, adapter):
    spec = adapter.build_for_task(tmp_path / "s", "ns", "t", "prompt")
    assert len(spec.extra_allowed_tools) == len(CONFIG["allowed_tools"])
    assert all(tool.startswith(CONFIG["tool_prefix"]) for tool in spec.extra_allowed_tools)
