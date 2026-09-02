"""The `recall_rerank` arm: one setting different from `recall`, and provably only one.

The whole value of pairing these two arms in one grid is that every difference between them is
declared. These tests are what makes that a property rather than an intention: they pin the set of
keys that differ, they pin the instruction to be byte-identical, and they check that the base arm's
server command did not move when the variant was added.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.recall.adapter import RecallAdapter
from adapters.recall_rerank.adapter import RecallRerankAdapter
from scripts import abstention, pilot

REPO = Path(__file__).resolve().parents[1]
RECALL_CONFIG = json.loads(
    (REPO / "adapters" / "recall" / "config.frozen.json").read_text(encoding="utf-8")
)
RERANK_CONFIG = json.loads(
    (REPO / "adapters" / "recall_rerank" / "config.frozen.json").read_text(encoding="utf-8")
)

#: The complete list of what this arm is allowed to change, and the reason each is on it.
#:
#: `notes` is prose about the other three. If a fourth setting ever needs to move, it belongs in
#: this tuple with a stated reason, in a diff a reviewer sees -- which is the point of asserting
#: the set rather than asserting each member.
DECLARED_DIFFERENCES = {"extra_env", "package_pin", "remote_python_env", "notes"}


def test_the_two_configs_differ_in_exactly_the_declared_keys():
    assert set(RECALL_CONFIG) | {"extra_env"} == set(RERANK_CONFIG)
    differing = {
        key
        for key in set(RECALL_CONFIG) | set(RERANK_CONFIG)
        if RECALL_CONFIG.get(key) != RERANK_CONFIG.get(key)
    }
    assert differing == DECLARED_DIFFERENCES


def test_the_reranker_is_on_and_names_its_model():
    # The bare alias `voyage` resolves to whatever DEFAULT_VOYAGE_RERANK_MODEL points at, which can
    # move under a wheel. A published record names the model that ran.
    assert RERANK_CONFIG["extra_env"] == {
        "RECALL_RERANK": "1",
        "RECALL_RERANK_MODEL": "voyage:rerank-2.5",
    }
    assert "rerank" in RERANK_CONFIG["package_pin"]
    assert "rerank" not in RECALL_CONFIG["package_pin"]


def test_recall_declares_no_extra_env_so_its_server_command_is_unchanged(recall_location):
    """The base arm must be byte-identical to what every published run served.

    `extra_env` is applied by the SHARED adapter, so the way this refactor could break the four
    published runs is by adding an assignment to `recall`'s own command string.
    """

    adapter = RecallAdapter("staging", REPO / "corpus" / "README.md")
    assert "extra_env" not in RECALL_CONFIG
    assert adapter._extra_env() == {}
    command = adapter._remote_command("bench-official")
    assert "RECALL_RERANK" not in command
    assert command.count("export ") == 1


def test_the_variant_exports_its_reranker_to_the_server(recall_location):
    adapter = RecallRerankAdapter("staging", REPO / "corpus" / "README.md")
    command = adapter._remote_command("bench-official")
    assert "RECALL_RERANK=1" in command
    assert "RECALL_RERANK_MODEL=voyage:rerank-2.5" in command
    # Still strict, still production, still this tenant: the variant adds, it does not repoint.
    assert "unset RECALL_TRUST_MODE" in command
    assert "RECALL_TENANT=bench-official" in command
    assert "RECALL_ENV=production" in command


def test_the_variant_runs_its_own_interpreter(recall_location):
    recall = RecallAdapter("staging", REPO / "corpus" / "README.md")
    rerank = RecallRerankAdapter("staging", REPO / "corpus" / "README.md")
    assert recall._location("remote_python") != rerank._location("remote_python")


def test_a_variant_may_not_repoint_what_is_served(recall_location, tmp_path):
    """The guard that keeps a variant from becoming a different experiment under this name.

    Both arms publish `mcp__recall__` and the same server name, so a variant that could move the
    tenant or relax the trust gate would be invisible in the records: same prefix, same tools, same
    admission signal, different corpus.
    """

    adapter = RecallRerankAdapter("staging", REPO / "corpus" / "README.md")
    adapter.config["extra_env"] = {"RECALL_TENANT": "somebody-elses-corpus"}
    with pytest.raises(RuntimeError, match="RECALL_TENANT"):
        adapter._remote_command("bench-official")


def test_each_arm_publishes_a_digest_of_its_own_config(recall_location):
    """Two arms whose records claim one configuration are two arms a reader cannot tell apart."""

    recall = RecallAdapter("staging", REPO / "corpus" / "README.md")
    rerank = RecallRerankAdapter("staging", REPO / "corpus" / "README.md")
    assert recall.describe()["config_sha256"] != rerank.describe()["config_sha256"]
    assert rerank.describe()["arm"] == "recall_rerank"


def test_the_arm_is_registered_everywhere_a_roster_is_held():
    assert "recall_rerank" in pilot.ARMS
    assert "recall_rerank" in pilot.MEMORY_ARMS
    # Its tenant is indexed out of band against the frozen manifest, exactly as `recall`'s is.
    assert "recall_rerank" not in pilot.SELF_INGESTING_ARMS
    # Unclassified here, an arm runs and is silently exempted from the search-rate floor.
    assert "recall_rerank" in abstention.MEMORY_ARMS
    abstention._classify_arms(["bare", "recall", "recall_rerank"])  # must not raise


def test_the_runner_builds_the_variant_adapter(tmp_path, recall_location):
    adapter = pilot.adapter_for(
        "recall_rerank",
        {"claude_md": REPO / "corpus" / "README.md"},
        tmp_path,
        {"recall_rerank": ""},
    )
    assert isinstance(adapter, RecallRerankAdapter)
    assert adapter.name == "recall_rerank"


@pytest.mark.parametrize("variant", ["protocol", "skill", "oneliner"])
def test_the_two_arms_receive_a_byte_identical_instruction(variant):
    """The reranker is the treatment. An instruction difference would be measured as one."""

    texts = pilot.memory_instructions(variant, ("bare", "recall", "recall_rerank"))
    assert texts["recall_rerank"] == texts["recall"]
    assert texts["recall"].strip()
