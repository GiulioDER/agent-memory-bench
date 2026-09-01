"""The `cognee` arm: wiring, refusals, and the cost guard that is its reason for existing.

These tests do not run cognee. They pin the parts of the arm that would otherwise fail silently:
an arm registered in one place and forgotten in another, a store path too long for onnxruntime to
load its DLL from, a `.env` that beats the frozen config, a half-configured product that bills a
provider nobody chose, and the per-task prompt that `diagnostic-001` got wrong through this same
code path in the recall adapter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.cognee.adapter import CogneeAdapter, parse_driver_report
from harness import instructions
from harness.instructions import APPENDIX_MAX_BYTES

REPO = Path(__file__).resolve().parents[1]
CONFIG = json.loads(
    (REPO / "adapters" / "cognee" / "config.frozen.json").read_text(encoding="utf-8")
)


@pytest.fixture()
def base_prompt(tmp_path):
    path = tmp_path / "claude_md.md"
    path.write_text("# Fixture README\n\nStatic half, shared by every arm.\n", encoding="utf-8")
    return path


@pytest.fixture()
def adapter(tmp_path, base_prompt, monkeypatch):
    """An adapter pointed at a short store root and a venv stub, so no product is needed."""

    venv = tmp_path / "v"
    (venv / "Scripts").mkdir(parents=True)
    for stem in ("python.exe", "cognee-mcp.exe"):
        (venv / "Scripts" / stem).write_bytes(b"")
    monkeypatch.setenv(CONFIG["venv_env"], str(venv))
    monkeypatch.setenv(CONFIG["store_root_env"], str(tmp_path / "s"))
    monkeypatch.setenv(CONFIG["llm"]["api_key_env"], "test-key-not-a-real-one")
    return CogneeAdapter(tmp_path / "staging", base_prompt)


# --------------------------------------------------------------------- registration


def test_the_arm_is_registered_everywhere_a_run_reads_it():
    """An arm listed in ARMS but missing from MEMORY_ARMS carries no memory protocol.

    That is not hypothetical: `mempalace` was missing from the abstention runner's MEMORY_ARMS
    for the whole of `official-001`, so the run published endpoints for an arm whose search rate
    nobody knew.
    """

    from scripts import abstention, pilot

    assert "cognee" in pilot.ARMS
    assert "cognee" in pilot.MEMORY_ARMS
    assert "cognee" in pilot.SELF_INGESTING_ARMS
    assert "cognee" in abstention.MEMORY_ARMS
    assert "cognee" not in abstention.NON_MEMORY_ARMS


def test_adapter_for_builds_a_cognee_adapter(tmp_path, base_prompt):
    from scripts import pilot

    built = pilot.adapter_for(
        "cognee", {"claude_md": base_prompt}, tmp_path, {"cognee": ""}
    )
    assert isinstance(built, CogneeAdapter)


def test_build_bundles_gives_the_arm_its_instruction(tmp_path, base_prompt):
    """`build_bundles` iterated a literal arm list once, so a new arm's instruction was dropped."""

    from scripts import pilot

    class Task:
        path = tmp_path

    texts = {"bare": "", "claude_md": "", "cognee": "SEARCH THE GRAPH"}
    bundles = pilot.build_bundles(Task(), tmp_path / "out", texts)
    assert "cognee" in bundles
    assert "SEARCH THE GRAPH" in bundles["cognee"].read_text(encoding="utf-8")


# --------------------------------------------------------------------- instruction


def test_the_appendix_is_within_the_shared_cap():
    appendix = (REPO / "adapters" / "cognee" / "instruction_appendix.md").read_bytes()
    assert len(appendix.strip()) <= APPENDIX_MAX_BYTES


@pytest.mark.parametrize("neutral", [False, True])
def test_the_instruction_is_the_shared_protocol_plus_the_appendix(neutral):
    text = CogneeAdapter.shared_instruction(neutral=neutral)
    instructions.assert_shared_protocol({"cognee": text}, neutral=neutral)
    assert CONFIG["search_sentence"] in text


def test_the_search_sentence_names_a_tool_the_config_allows():
    """A sentence naming a tool the allow-list withholds would tell the agent to call nothing."""

    prefix = str(CONFIG["tool_prefix"])
    assert f"{prefix}recall" in CONFIG["search_sentence"]
    assert "recall" in CONFIG["allowed_tools"]


def test_no_write_tool_reaches_a_graded_session():
    """The corpus is frozen after ingest and no runner calls snapshot/restore yet, so a session
    that wrote to the store would change the store the next seed reads."""

    assert "remember" not in CONFIG["allowed_tools"]
    assert "forget" not in CONFIG["allowed_tools"]


# --------------------------------------------------------------------- refusals


def test_it_refuses_a_store_path_too_long_for_onnxruntime(tmp_path, base_prompt, monkeypatch):
    """The `mempalace` arm paid for this trap once; fastembed reaches the same DLL.

    onnxruntime's `_pybind11_state` fails to load from a deep path on Windows and the error is
    re-raised downstream as a missing package, so the arm would score zero with nothing in the
    record naming the reason.
    """

    deep = tmp_path / ("d" * 90) / ("e" * 90)
    monkeypatch.setenv(CONFIG["store_root_env"], str(deep))
    monkeypatch.setenv(CONFIG["venv_env"], str(tmp_path))
    adapter = CogneeAdapter(tmp_path / "staging", base_prompt)
    with pytest.raises(RuntimeError, match="characters, over the"):
        adapter._store_dir("bench")


@pytest.mark.parametrize("root", ["venv", "store"])
def test_it_refuses_a_stray_dotenv_that_would_beat_the_frozen_config(adapter, root):
    """cognee calls `dotenv.load_dotenv(override=True)` at import, so such a file wins.

    Both roots are refused, and which one matters is not the obvious one: `dotenv.find_dotenv`
    walks up from the IMPORTING MODULE's directory, so in a normal run the file that captures
    this arm sits beside or above the VENV. The working directory only applies in a REPL, under
    a debugger, or frozen.
    """

    directories = {"venv": adapter._venv(), "store": adapter._store_dir("bench")}
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)
    (directories[root] / ".env").write_text("LLM_MODEL=something-else\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="override=True"):
        adapter.refuse_stray_dotenv(*directories.values())


def test_it_refuses_to_run_without_the_api_key(adapter, monkeypatch):
    monkeypatch.delenv(CONFIG["llm"]["api_key_env"], raising=False)
    with pytest.raises(RuntimeError, match=CONFIG["llm"]["api_key_env"]):
        adapter.cognee_env("bench")


def test_the_api_key_is_never_written_into_the_frozen_config():
    """`config.frozen.json` is published and vendor-reviewed."""

    frozen = (REPO / "adapters" / "cognee" / "config.frozen.json").read_text(encoding="utf-8")
    assert "api_key_env" in frozen
    assert "sk-" not in frozen
    assert "LLM_API_KEY" not in json.dumps(CONFIG["server_env"])


# --------------------------------------------------------------------- configuration


def test_both_halves_of_the_model_configuration_are_set(adapter):
    """cognee defaults an unset embedding pair to OpenAI and reuses LLM_API_KEY for it.

    So a configuration that names only the LLM silently bills a provider nobody chose, which is
    the exact shape of hidden cost this arm was selected to avoid.
    """

    env = adapter.cognee_env("bench")
    for key in ("LLM_PROVIDER", "LLM_MODEL", "EMBEDDING_PROVIDER", "EMBEDDING_MODEL"):
        assert env[key], f"{key} is unset, so cognee would fall back to OpenAI"
    assert env["EMBEDDING_PROVIDER"] == "fastembed"


def test_each_namespace_gets_its_own_store(adapter):
    """Two namespaces must not share a database file. The DIRECTORY is the isolation boundary.

    ⚠️ This test used to also require two different dataset NAMES, and that requirement was
    dropped on 2026-09-02 rather than weakened by accident. A per-namespace dataset name makes a
    shared base store impossible: documents copied in under one condition's name are invisible to
    a condition that queries another, so the arm retrieves nothing while the store, the ingest and
    the gate are all individually correct. Nothing is lost, because each namespace already has its
    own SQLite, LanceDB and Kuzu files and a name inside a private database isolates nothing more.
    """

    first, second = adapter.cognee_env("run-a"), adapter.cognee_env("run-b")
    assert first["DATA_ROOT_DIRECTORY"] != second["DATA_ROOT_DIRECTORY"]
    assert first["SYSTEM_ROOT_DIRECTORY"] != second["SYSTEM_ROOT_DIRECTORY"]
    assert adapter.dataset("run-a") == adapter.dataset("run-b"), (
        "one dataset name across namespaces is what makes a shared base store possible"
    )


def test_agent_scoping_is_off(adapter):
    """With it on, the server auto-names a per-client dataset and Claude Code would search
    `claude_code_memory`, which is not the dataset the harness ingested into: the arm would
    retrieve nothing in every session and look like a product that finds nothing."""

    assert adapter.cognee_env("bench")["COGNEE_MCP_AGENT_SCOPED"] == "false"


def test_the_dataset_still_validates_the_namespace_it_is_handed(adapter):
    """The name no longer derives from the namespace, so the validation could be lost silently.

    Callers pass a namespace here expecting it to be checked, and every other path that takes one
    joins it onto a directory that is later deleted.
    """

    assert adapter.dataset("bench-official-002") == CONFIG["dataset_name"]
    with pytest.raises(ValueError, match="namespace"):
        adapter.dataset("../../../../victim")


# --------------------------------------------------------------------- gate, spec, driver


def test_the_admission_signal_names_this_arm_and_its_prefix(adapter):
    signal = adapter.admission_signal()
    assert signal.arm == "cognee"
    assert signal.mcp_tool_prefixes == (CONFIG["tool_prefix"],)


def test_build_for_task_writes_a_prompt_per_session(adapter, tmp_path):
    """`diagnostic-001` served every recall session the first task's README through this path."""

    first = adapter.build_for_task(tmp_path / "s1", "bench", "ts-one", "do the thing")
    second = adapter.build_for_task(tmp_path / "s2", "bench", "ts-two", "do the other")
    assert first.append_system_prompt_file != second.append_system_prompt_file
    assert Path(first.append_system_prompt_file).parent == tmp_path / "s1"


def test_the_digest_covers_the_driver_as_well_as_the_config(adapter, tmp_path):
    """The driver decides what the ingest spends and in what order, so a change to it is a
    change to the reviewed configuration and must move the recorded digest."""

    spec = adapter.build_for_task(tmp_path / "s", "bench", "ts-one", "do the thing")
    described = adapter.describe()
    assert spec.config_dir_digest
    assert described["config_sha256"] != described["driver_sha256"]
    assert spec.config_dir_digest not in (
        described["config_sha256"], described["driver_sha256"]
    )


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ('COGNEE_JSON {"files": 4, "probe_hits": 2}', {"files": 4, "probe_hits": 2}),
        ('noise\nCOGNEE_JSON {"files": 1}\ntrailing log line', {"files": 1}),
        ("cognee logged plenty and reported nothing", {}),
        ("COGNEE_JSON not-json", {}),
    ],
)
def test_parse_driver_report_reads_the_one_line_that_matters(stdout, expected):
    """cognee logs to stdout too, so the report has to be found rather than assumed."""

    assert parse_driver_report(stdout) == expected


def test_the_cost_ceiling_is_a_number_the_driver_can_enforce():
    """The ceiling is the arm's whole cost story: it is checked against cognee's own dry-run
    estimate before a single LLM call, so an ingest bill is quoted before it is paid."""

    assert float(CONFIG["ingest_cost_ceiling_usd"]) > 0
    driver = (REPO / "adapters" / "cognee" / "ingest_driver.py").read_text(encoding="utf-8")
    assert "dry_run=True" in driver
    assert driver.index("dry_run=True") < driver.index("await cognee.cognify(datasets=[dataset])")


def test_the_binding_ceiling_is_in_tokens_because_the_dollar_one_cannot_fire():
    """MEASURED 2026-09-01, and the reason this arm was chosen makes the defect worse.

    Running the dry run in Docker over the 196-document corpus returned 316,674 tokens with
    `estimated_cost_usd: 0.0` and the warning "no pricing entry for model
    'openai/deepseek/deepseek-v4-flash'". cognee prices from its own table, so the model this
    benchmark runs on is unpriced there and a dollar-only ceiling would wave through a bill of any
    size. The arm was selected precisely because its bill is visible in advance, so a guard that
    cannot fire is the worst possible defect to leave in it.
    """

    ceiling = int(CONFIG["ingest_token_ceiling"])
    assert ceiling > 0
    # 1,616 tokens per document measured; the hard corpus is 4,889 documents per condition.
    assert ceiling > 1616 * 4889, "the ceiling would refuse the corpus this arm exists to ingest"

    driver = (REPO / "adapters" / "cognee" / "ingest_driver.py").read_text(encoding="utf-8")
    assert "token_ceiling and tokens > token_ceiling" in driver
    # The token check must be reached before the dollar one, and a priced-at-zero estimate with
    # no token ceiling must refuse rather than proceed.
    assert driver.index("tokens > token_ceiling") < driver.index("if cost > ceiling")
    assert "tokens and not cost and not token_ceiling" in driver


def test_the_arm_exposes_no_ranked_search(adapter):
    """cognee's recall answers from a graph of extracted entities, so a hit cannot yet be mapped
    back to the corpus-relative path that makes a ranked list joinable against gold sessions.

    Raising is the contract: an empty list means "found nothing", and conflating the two would
    score an unimplemented arm as a product that ranks badly.
    """

    assert adapter.supported_gatings == ()
    with pytest.raises(NotImplementedError):
        adapter.search("bench", "anything")
