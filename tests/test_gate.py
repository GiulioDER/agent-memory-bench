import pytest

from harness.gate import (
    AdmissionSignal,
    admit_cells,
    check_session,
    with_forbidden_prefixes,
)
from harness.schema import SessionRecord

MCP_SIGNAL = AdmissionSignal(arm="recall", mcp_tool_prefixes=("mcp__recall__",))
BARE_SIGNAL = AdmissionSignal(arm="bare")


def _record(arm: str, *, task: str = "t1", seed: int = 0, **kwargs) -> SessionRecord:
    return SessionRecord(task_id=task, arm=arm, seed=seed, success=True, **kwargs)


def test_forbidden_prefixes_are_every_other_arms():
    signals = with_forbidden_prefixes(
        {
            "recall": AdmissionSignal(arm="recall", mcp_tool_prefixes=("mcp__recall__",)),
            "zep": AdmissionSignal(arm="zep", mcp_tool_prefixes=("mcp__graphiti__",)),
            "bare": AdmissionSignal(arm="bare"),
        }
    )
    assert signals["recall"].forbidden_prefixes == ("mcp__graphiti__",)
    assert signals["bare"].forbidden_prefixes == ("mcp__graphiti__", "mcp__recall__")


def test_shared_prefix_between_two_arms_is_refused():
    with pytest.raises(ValueError, match="cannot tell those arms apart"):
        with_forbidden_prefixes(
            {
                "a": AdmissionSignal(arm="a", mcp_tool_prefixes=("mcp__x__",)),
                "b": AdmissionSignal(arm="b", mcp_tool_prefixes=("mcp__x__",)),
            }
        )


def test_mcp_arm_without_its_tools_is_discarded():
    record = _record("recall", metadata={"session_tools": ["Read", "Bash"]})
    verdict = check_session(record, MCP_SIGNAL)
    assert not verdict.admitted
    assert any("never available" in reason for reason in verdict.reasons)


def test_mcp_arm_with_tools_present_but_unused_is_admitted_with_note():
    record = _record(
        "recall",
        memory_call_count=0,
        metadata={
            "session_tools": ["Read", "mcp__recall__recall_search"],
            "mcp_servers": [{"name": "recall", "status": "connected"}],
        },
    )
    verdict = check_session(record, MCP_SIGNAL)
    assert verdict.admitted
    assert any("behavioural result" in note for note in verdict.notes)


def test_pending_mcp_server_is_discarded_even_with_tools_listed():
    record = _record(
        "recall",
        metadata={
            "session_tools": ["mcp__recall__recall_search"],
            "mcp_servers": [{"name": "recall", "status": "pending"}],
        },
    )
    verdict = check_session(record, MCP_SIGNAL)
    assert not verdict.admitted


def test_arm_holding_another_arms_tools_is_discarded():
    signals = with_forbidden_prefixes(
        {"bare": BARE_SIGNAL, "recall": MCP_SIGNAL}
    )
    record = _record("bare", metadata={"session_tools": ["mcp__recall__recall_search"]})
    verdict = check_session(record, signals["bare"])
    assert not verdict.admitted
    assert any("another arm's tools" in reason for reason in verdict.reasons)


def test_required_hook_missing_or_failing_is_discarded():
    signal = AdmissionSignal(arm="mem0", required_hooks=("SessionStart",))
    missing = check_session(_record("mem0"), signal)
    assert not missing.admitted
    failed = check_session(
        _record(
            "mem0",
            hook_ledger=({"event": "SessionStart", "exit_code": 1, "output_sha256": "ab"},),
        ),
        signal,
    )
    assert not failed.admitted
    empty_output = check_session(
        _record(
            "mem0",
            hook_ledger=({"event": "SessionStart", "exit_code": 0, "output_sha256": ""},),
        ),
        signal,
    )
    assert not empty_output.admitted
    ok = check_session(
        _record(
            "mem0",
            memory_call_count=1,
            hook_ledger=({"event": "SessionStart", "exit_code": 0, "output_sha256": "ab"},),
        ),
        signal,
    )
    assert ok.admitted


def test_sandbox_path_and_prompt_hash_checks():
    signal = AdmissionSignal(arm="fs_grep", sandbox_paths=("memory",))
    missing = check_session(_record("fs_grep"), signal)
    assert not missing.admitted
    present = check_session(
        _record("fs_grep", memory_call_count=1, metadata={"sandbox_paths_present": ["memory"]}),
        signal,
    )
    assert present.admitted

    hashed = AdmissionSignal(arm="claude_md", prompt_sha256="abc")
    wrong = check_session(_record("claude_md", metadata={"prompt_sha256": "zzz"}), hashed)
    assert not wrong.admitted


def test_prompt_hash_map_is_checked_per_task():
    signal = AdmissionSignal(
        arm="placebo",
        metadata={"prompt_sha256_by_task": {"t1": "abc", "t2": "def"}},
    )
    ok = check_session(_record("placebo", metadata={"prompt_sha256": "abc"}), signal)
    wrong = check_session(
        _record("placebo", task="t2", metadata={"prompt_sha256": "abc"}), signal
    )
    assert ok.admitted
    assert not wrong.admitted


def test_session_error_is_discarded():
    record = _record("bare", error="TimeoutError: 1800s")
    assert not check_session(record, BARE_SIGNAL).admitted


def test_admit_cells_requires_every_arm_and_reports_discards():
    signals = with_forbidden_prefixes({"bare": BARE_SIGNAL, "recall": MCP_SIGNAL})
    good_recall = _record(
        "recall",
        metadata={
            "session_tools": ["mcp__recall__recall_search"],
            "mcp_servers": [{"name": "recall", "status": "connected"}],
        },
    )
    good_bare = _record("bare")
    bad_recall = _record("recall", task="t2", metadata={"session_tools": []})
    bare_t2 = _record("bare", task="t2")
    report = admit_cells(
        [good_recall, good_bare, bad_recall, bare_t2],
        signals,
        required_arms=("recall", "bare"),
    )
    assert report.admitted_cell_count == 1
    assert report.discarded_cells == (("t2", 0),)
    assert report.discarded_by_arm() == {"recall": 1}
    summary = report.summary()
    assert summary["admitted_cells"] == 1


def test_admit_cells_missing_arm_record_discards_the_cell():
    report = admit_cells(
        [_record("bare")],
        with_forbidden_prefixes({"bare": BARE_SIGNAL, "recall": MCP_SIGNAL}),
        required_arms=("recall", "bare"),
    )
    assert report.admitted_cell_count == 0
    assert report.discarded_cells == (("t1", 0),)


def test_duplicate_record_for_one_cell_is_refused():
    with pytest.raises(ValueError, match="duplicate record"):
        admit_cells(
            [_record("bare"), _record("bare")],
            {"bare": BARE_SIGNAL},
            required_arms=("bare",),
        )
