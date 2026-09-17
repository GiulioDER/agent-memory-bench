"""Frozen treatment and wiring checks for official-014."""

from __future__ import annotations

import hashlib

import pytest

from adapters.recall_graph_fulltools.adapter import RecallGraphFullToolsAdapter
from harness.gate import AdmissionSignal, with_forbidden_prefixes
from scripts import abstention, pilot
from scripts.validate_run_setup import check_quality_gate_pair

CONTROL_ARM = "recall_graph_fulltools_protocol"
TREATMENT_ARM = "recall_graph_fulltools_quality_gate"
PAIRED_ARMS = (CONTROL_ARM, TREATMENT_ARM)
CONTROL_SHA256 = "aae2f2cf6fe67cac3998b1692d9173ef9ae7edcbe3263053d36025e77f2dc7d8"
APPENDIX_SHA256 = "fb8295ddf00d2b4573c7f622cc2086688e418124d8cb294de972ae18cd1a5a07"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_control_is_the_exact_official012_instruction() -> None:
    control = pilot.recall_graph_fulltools_instruction("protocol")

    assert len(control.encode("utf-8")) == 3924
    assert _sha(control) == CONTROL_SHA256


def test_quality_gate_is_only_the_frozen_appendix_after_control() -> None:
    control = pilot.recall_graph_fulltools_instruction("protocol")
    treatment = pilot.recall_graph_quality_gate_instruction()

    assert treatment.startswith(control + "\n")
    appendix = treatment.removeprefix(control + "\n")
    assert _sha(appendix) == APPENDIX_SHA256
    assert "discovery mechanism for relevant facts" in appendix
    assert "Stop after at most two materially different follow-ups" in appendix


def test_paired_variant_assigns_one_instruction_per_preregistered_arm() -> None:
    texts = pilot.memory_instructions("quality_gate_paired", PAIRED_ARMS)
    control = pilot.recall_graph_fulltools_instruction("protocol")

    assert texts[CONTROL_ARM] == control
    assert texts[TREATMENT_ARM] == pilot.recall_graph_quality_gate_instruction()
    assert texts[TREATMENT_ARM].startswith(texts[CONTROL_ARM] + "\n")


def test_quality_gate_variant_refuses_any_other_roster() -> None:
    with pytest.raises(ValueError, match="requires exactly"):
        pilot.validate_quality_gate_pair("quality_gate_paired", (TREATMENT_ARM,))

    with pytest.raises(ValueError, match="requires exactly"):
        pilot.validate_quality_gate_pair(
            "quality_gate_paired", (CONTROL_ARM, TREATMENT_ARM, "bare")
        )

    pilot.validate_quality_gate_pair("quality_gate_paired", PAIRED_ARMS)


def test_both_aliases_share_the_fulltools_adapter_and_memory_classification(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("RECALL_DSN", "postgresql://irrelevant/for-this-test")
    static = tmp_path / "static.md"
    static.write_text("# project notes\n", encoding="utf-8")
    texts = pilot.memory_instructions("quality_gate_paired", PAIRED_ARMS)
    bundles = {"claude_md": static}

    for arm in PAIRED_ARMS:
        adapter = pilot.adapter_for(arm, bundles, tmp_path / "staging", texts)
        assert isinstance(adapter, RecallGraphFullToolsAdapter)
        assert arm in pilot.ARMS
        assert arm in pilot.RECALL_ARMS
        assert arm in pilot.MEMORY_ARMS
        assert arm in abstention.MEMORY_ARMS


def test_paired_aliases_register_under_distinct_arm_names(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RECALL_DSN", "postgresql://irrelevant/for-this-test")
    static = tmp_path / "static.md"
    static.write_text("# project notes\n", encoding="utf-8")
    texts = pilot.memory_instructions("quality_gate_paired", PAIRED_ARMS)

    registry = pilot.build_registry(
        tmp_path / "staging", {"claude_md": static}, texts, PAIRED_ARMS
    )

    assert set(registry.names()) == set(PAIRED_ARMS)


def test_graph_preflight_route_includes_both_aliases() -> None:
    for arm in PAIRED_ARMS:
        tool, arguments = pilot.recall_preflight_request(arm, "task prompt")
        assert tool == "recall_reasoning_query"
        assert arguments == {
            "query": "task prompt",
            "graph_expansion": "one_hop",
            "expand_retrieval": False,
        }


def test_setup_gate_verifies_the_frozen_prefix_and_appendix() -> None:
    texts = pilot.memory_instructions("quality_gate_paired", PAIRED_ARMS)
    env = {
        "memory_instruction": "quality_gate_paired",
        "quality_gate_pair": pilot.quality_gate_pair_metadata(texts),
        "shared_tool_prefix_groups": [list(PAIRED_ARMS)],
    }

    assert check_quality_gate_pair(env).ok is True
    env["quality_gate_pair"]["treatment_prefix_matches_control"] = False
    assert check_quality_gate_pair(env).ok is False


def test_preregistered_pair_may_share_only_its_recall_tool_prefix() -> None:
    signals = {
        arm: AdmissionSignal(arm=arm, mcp_tool_prefixes=("mcp__recall__",))
        for arm in PAIRED_ARMS
    }

    filled = with_forbidden_prefixes(signals, shared_prefix_groups=(PAIRED_ARMS,))

    assert set(filled) == set(PAIRED_ARMS)
    assert all(signal.forbidden_prefixes == () for signal in filled.values())
