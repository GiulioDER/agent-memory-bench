"""Frozen treatment and wiring checks for official-015."""

from __future__ import annotations

import hashlib
import re

import pytest

from adapters.recall_graph_fulltools.adapter import RecallGraphFullToolsAdapter
from harness.gate import AdmissionSignal, with_forbidden_prefixes
from scripts import abstention, pilot
from scripts.validate_run_setup import check_decision_protocol_pair

CONTROL_ARM = "recall_graph_fulltools_protocol"
TREATMENT_ARM = "recall_graph_fulltools_decision_protocol"
PAIRED_ARMS = (CONTROL_ARM, TREATMENT_ARM)
CONTROL_SHA256 = "aae2f2cf6fe67cac3998b1692d9173ef9ae7edcbe3263053d36025e77f2dc7d8"
TREATMENT_SHA256 = "a3ccb2af267521cc71886d999abb81cf39a29d97e6aebfd1ed5672b8022cb907"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _frozen_treatment() -> str:
    prereg = (
        pilot.REPO
        / "preregistration"
        / "026-official-015-recall-decision-protocol-paired.md"
    ).read_text(encoding="utf-8")
    match = re.search(
        r"The treatment instruction is exactly.*?```text\n(.*?)```",
        prereg,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_frozen_treatment_matches_preregistration_byte_for_byte() -> None:
    treatment = pilot.recall_decision_protocol_instruction()

    assert treatment == _frozen_treatment()
    assert len(treatment.encode("utf-8")) == 1725
    assert _sha(treatment) == TREATMENT_SHA256


def test_control_remains_the_exact_official012_instruction() -> None:
    control = pilot.recall_graph_fulltools_instruction("protocol")

    assert len(control.encode("utf-8")) == 3924
    assert _sha(control) == CONTROL_SHA256


def test_paired_variant_assigns_the_two_frozen_instructions() -> None:
    texts = pilot.memory_instructions("decision_protocol_paired", PAIRED_ARMS)

    assert texts[CONTROL_ARM] == pilot.recall_graph_fulltools_instruction("protocol")
    assert texts[TREATMENT_ARM] == _frozen_treatment()
    assert texts[TREATMENT_ARM] != texts[CONTROL_ARM]


def test_decision_protocol_variant_refuses_any_other_roster() -> None:
    with pytest.raises(ValueError, match="requires exactly"):
        pilot.validate_decision_protocol_pair("decision_protocol_paired", (TREATMENT_ARM,))

    with pytest.raises(ValueError, match="requires exactly"):
        pilot.validate_decision_protocol_pair(
            "decision_protocol_paired", (CONTROL_ARM, TREATMENT_ARM, "bare")
        )

    pilot.validate_decision_protocol_pair("decision_protocol_paired", PAIRED_ARMS)


def test_both_aliases_share_fulltools_configuration_and_memory_classification(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("RECALL_DSN", "postgresql://irrelevant/for-this-test")
    static = tmp_path / "static.md"
    static.write_text("# project notes\n", encoding="utf-8")
    texts = pilot.memory_instructions("decision_protocol_paired", PAIRED_ARMS)
    bundles = {"claude_md": static}

    for arm in PAIRED_ARMS:
        adapter = pilot.adapter_for(arm, bundles, tmp_path / "staging", texts)
        assert isinstance(adapter, RecallGraphFullToolsAdapter)
        assert arm in pilot.ARMS
        assert arm in pilot.RECALL_ARMS
        assert arm in pilot.MEMORY_ARMS
        assert arm in abstention.MEMORY_ARMS


def test_paired_aliases_register_under_distinct_names(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RECALL_DSN", "postgresql://irrelevant/for-this-test")
    static = tmp_path / "static.md"
    static.write_text("# project notes\n", encoding="utf-8")
    texts = pilot.memory_instructions("decision_protocol_paired", PAIRED_ARMS)

    registry = pilot.build_registry(
        tmp_path / "staging", {"claude_md": static}, texts, PAIRED_ARMS
    )

    assert set(registry.names()) == set(PAIRED_ARMS)


def test_preflight_routes_match_each_arm_entry_point() -> None:
    control_tool, control_arguments = pilot.recall_preflight_request(CONTROL_ARM, "task prompt")
    treatment_tool, treatment_arguments = pilot.recall_preflight_request(
        TREATMENT_ARM, "task prompt"
    )

    assert control_tool == "recall_reasoning_query"
    assert control_arguments == {
        "query": "task prompt",
        "graph_expansion": "one_hop",
        "expand_retrieval": False,
    }
    assert treatment_tool == "recall_search"
    assert treatment_arguments == {"query": "task prompt", "limit": 1}


def test_setup_gate_verifies_both_frozen_instructions() -> None:
    texts = pilot.memory_instructions("decision_protocol_paired", PAIRED_ARMS)
    env = {
        "memory_instruction": "decision_protocol_paired",
        "decision_protocol_pair": pilot.decision_protocol_pair_metadata(texts),
        "shared_tool_prefix_groups": [list(PAIRED_ARMS)],
    }

    assert check_decision_protocol_pair(env).ok is True
    env["decision_protocol_pair"]["treatment_sha256"] = "0" * 64
    assert check_decision_protocol_pair(env).ok is False


def test_preregistered_pair_may_share_only_its_recall_tool_prefix() -> None:
    signals = {
        arm: AdmissionSignal(arm=arm, mcp_tool_prefixes=("mcp__recall__",))
        for arm in PAIRED_ARMS
    }

    filled = with_forbidden_prefixes(signals, shared_prefix_groups=(PAIRED_ARMS,))

    assert set(filled) == set(PAIRED_ARMS)
    assert all(signal.forbidden_prefixes == () for signal in filled.values())
