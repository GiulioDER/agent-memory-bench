"""Guarantees this repository documented and did not implement, now implemented.

Each section names the claim that was in the tree, the code that did not back it, and the mutation
that would take it back out. A documented guarantee that does not exist is worse than an absent one:
a reviewer who finds one stops trusting the others, all of which happen to be real.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from harness.claude_exec import ClaudeSessionTimeout
from harness.costs import ModelPricing, efficiency, summarize
from harness.damage import Outcome, classify, harm_band
from harness.gate import AdmissionSignal, admit_cells
from harness.memory_startup import (
    DEFAULT_RETRYABLE,
    TIMEOUT,
    TRANSPORT,
    WIRING,
    classify_failure,
    run_with_memory_startup_retry,
)
from harness.reached import mechanism, reached_by_content, reached_by_evidence, reached_by_path
from harness.sandbox import REPO_ROOT, default_work_root, restore
from harness.schema import SessionRecord
from harness.stats import cluster_bootstrap, effect_concentration


def _record(arm: str, task_id: str = "t1", seed: int = 0, **kwargs) -> SessionRecord:
    metadata = {"init_present": True, **kwargs.pop("metadata", {})}
    return SessionRecord(
        task_id=task_id, arm=arm, seed=seed, success=True, metadata=metadata, **kwargs
    )


# =======================================================================================
# README.md:38 and harness/sandbox.py both said the gate refused a digest mismatch. It did not.
# =======================================================================================


def _signals(*arms: str) -> dict[str, AdmissionSignal]:
    return {arm: AdmissionSignal(arm=arm) for arm in arms}


def test_arms_that_started_from_different_sandboxes_are_discarded():
    """THE assertion. Mutation: dropping _cell_digest_reason. A difference in starting state is
    then indistinguishable from a treatment effect, and nothing in the artifact says so."""

    records = [
        _record("bare", metadata={"sandbox_digest": "aaa"}),
        _record("recall", metadata={"sandbox_digest": "bbb"}),
    ]
    report = admit_cells(records, _signals("bare", "recall"), required_arms=("bare", "recall"))
    assert report.admitted_cell_count == 0
    assert report.discarded_cells == (("t1", 0),)
    assert any("did not start from the same sandbox" in r for v in report.verdicts for r in v.reasons)


def test_matching_digests_admit():
    records = [
        _record("bare", metadata={"sandbox_digest": "aaa"}),
        _record("recall", metadata={"sandbox_digest": "aaa"}),
    ]
    report = admit_cells(records, _signals("bare", "recall"), required_arms=("bare", "recall"))
    assert report.admitted_cell_count == 1


def test_records_without_a_digest_are_not_treated_as_mismatched():
    """An older artifact has no such field. Refusing it would make the gate unable to re-admit the
    runs it was written to check."""

    records = [_record("bare"), _record("recall")]
    report = admit_cells(records, _signals("bare", "recall"), required_arms=("bare", "recall"))
    assert report.admitted_cell_count == 1


def test_the_mismatch_is_reported_against_every_arm_in_the_cell():
    records = [
        _record("bare", metadata={"sandbox_digest": "aaa"}),
        _record("recall", metadata={"sandbox_digest": "bbb"}),
    ]
    report = admit_cells(records, _signals("bare", "recall"), required_arms=("bare", "recall"))
    assert {v.arm for v in report.verdicts if not v.admitted} == {"bare", "recall"}


# =======================================================================================
# harness/memory_startup.py said the retry was "triggered by wiring alone". It retried timeouts.
# =======================================================================================


def test_a_timeout_is_classified_as_an_outcome_not_as_infrastructure():
    record = SessionRecord(
        task_id="t1",
        arm="recall",
        success=False,
        error="ClaudeSessionTimeout: claude exceeded timeout_s=600",
        metadata={"timed_out": True},
    )
    kind, reason = classify_failure(record)
    assert kind == TIMEOUT
    assert "wall-clock budget" in reason


def test_a_timeout_is_not_retried_by_default():
    """THE assertion. Mutation: putting TIMEOUT back in DEFAULT_RETRYABLE. The slowest arm then
    draws extra attempts on exactly the hard tasks, and the rule's own docstring is false again."""

    assert TIMEOUT not in DEFAULT_RETRYABLE
    attempts = []

    async def runner(row, arm, config):
        attempts.append(arm)
        raise ClaudeSessionTimeout("claude exceeded timeout_s=600")

    record = asyncio.run(
        run_with_memory_startup_retry(
            {"task_id": "t1", "seed": 0, "user_input": "x"},
            "recall",
            SimpleNamespace(stream_dir=None),
            attempts=3,
            runner=runner,
            sleep=lambda _s: asyncio.sleep(0),
        )
    )
    assert len(attempts) == 1, "a timeout must not be re-rolled"
    assert record.metadata["memory_startup"]["final_kind"] == TIMEOUT


def test_a_wiring_failure_is_still_retried():
    attempts = []

    async def runner(row, arm, config):
        attempts.append(arm)
        return SessionRecord(
            task_id="t1",
            arm=arm,
            success=False,
            metadata={"init_present": True, "session_tools": [], "mcp_servers": []},
        )

    record = asyncio.run(
        run_with_memory_startup_retry(
            {"task_id": "t1", "seed": 0, "user_input": "x"},
            "recall",
            SimpleNamespace(stream_dir=None),
            tool_prefixes=("mcp__recall__",),
            attempts=3,
            runner=runner,
            sleep=lambda _s: asyncio.sleep(0),
        )
    )
    assert len(attempts) == 3
    assert record.metadata["memory_startup"]["final_kind"] == WIRING


def test_a_transport_failure_is_retried():
    kind, _reason = classify_failure(
        SessionRecord(task_id="t1", arm="bare", success=False, error="api_error (HTTP 402)")
    )
    assert kind == TRANSPORT
    assert kind in DEFAULT_RETRYABLE


def test_the_retry_never_reads_the_outcome():
    """A failing session that WIRED correctly is not retryable, whatever the checker said."""

    wired = SessionRecord(
        task_id="t1",
        arm="claude_md",
        success=False,
        metadata={"init_present": True, "checker": "failed badly"},
    )
    assert classify_failure(wired) == (None, None)


# =======================================================================================
# The sandbox sat inside the repository, a few directories below oracles/.
# =======================================================================================


def test_the_default_work_root_is_outside_the_repository():
    root = default_work_root()
    with pytest.raises(ValueError):
        root.resolve().relative_to(REPO_ROOT)


def test_building_a_sandbox_inside_the_repository_is_refused():
    """Mutation: dropping the guard. oracles/<task>/expected_*.txt is then reachable with one
    `cd ..` from a session holding unrestricted Bash."""

    with pytest.raises(ValueError, match="inside the benchmark repository"):
        restore("ts-base36-id", REPO_ROOT / "results" / "probe" / "work")


def test_a_memory_overlay_lands_after_the_commit_and_outside_the_digest(tmp_path):
    memory = tmp_path / "notes"
    memory.mkdir()
    (memory / "a.md").write_text("note", encoding="utf-8")
    plain = tmp_path / "plain"
    withmem = tmp_path / "withmem"
    digest_a = restore("ts-base36-id", plain, allow_in_repo=True)
    digest_b = restore("ts-base36-id", withmem, overlay=memory, allow_in_repo=True)
    assert digest_a == digest_b, "an arm's own memory must not change the shared-state digest"
    assert (withmem / "memory" / "a.md").is_file()
    assert not (plain / "memory").exists()


# =======================================================================================
# Damage detectors are exact matchers, so the harm rate could only ever be under-counted.
# =======================================================================================


def test_a_failure_matching_neither_reference_is_its_own_class():
    """Mutation: folding AMBIGUOUS back into NEUTRAL. The harm rate silently becomes a floor again,
    and the error is one-directional in the sponsor's favour."""

    assert classify(False, False, naive_match=False) is Outcome.AMBIGUOUS_FAILURE
    assert classify(False, False, naive_match=True) is Outcome.NEUTRAL_FAILURE
    assert classify(False, False) is Outcome.NEUTRAL_FAILURE


def test_harm_is_reported_as_a_band():
    band = harm_band(
        [Outcome.DAMAGED, Outcome.AMBIGUOUS_FAILURE, Outcome.NEUTRAL_FAILURE, Outcome.SOLVED]
    )
    assert band["damage_rate_floor"] == 0.25
    assert band["damage_rate_ceiling"] == 0.5


def test_a_correct_answer_is_never_damaged_whatever_the_third_signal_says():
    assert classify(True, False, naive_match=False) is Outcome.SOLVED


# =======================================================================================
# The mechanism metric matched RE-call's own source filenames.
# =======================================================================================


def _searching(output: str) -> SessionRecord:
    return SessionRecord(
        task_id="ts-base36-id",
        arm="recall",
        success=False,
        memory_call_count=1,
        tool_calls=({"name": "mcp__recall__recall_search", "output": output},),
    )


def test_content_reached_ignores_the_filename():
    """Mutation: reverting to the path match. A product that returns extracted facts rather than
    source documents then scores zero with perfect retrieval."""

    hit = _searching("the decision was a restricted alphabet with no 0/O/1/I")
    ok, matched = reached_by_content(hit, ("restricted alphabet", "no 0/O/1/I"))
    assert ok and len(matched) == 2
    assert not reached_by_path(hit), "this result carries no source filename at all"


def test_path_reached_counts_a_filename_with_no_governing_content():
    """Why the two disagree on the published runs: a chunk can carry the right filename and none
    of the decision. Measured: 0.850 by path against 0.550 by content on pilot-003-deepseek."""

    hit = _searching('{"source": "sessions__ts-base36-id__p01.md", "text": "let me read ids.txt"}')
    assert reached_by_path(hit)
    assert not reached_by_content(hit, ("restricted alphabet",))[0]


def test_evidence_reached_is_the_strict_lower_bound():
    decision = "order ids move to a restricted alphabet with no confusable characters at all"
    assert reached_by_evidence(_searching(decision), decision)
    assert not reached_by_evidence(_searching("something unrelated entirely"), decision)


def test_the_mechanism_block_publishes_all_three():
    """Mutation: reporting one number. The published figure was the loosest of the three and a
    reader had no way to know."""

    records = [_searching('{"source": "sessions__ts-base36-id__p01.md"}')]
    block = mechanism(records, {"ts-base36-id": ("restricted alphabet",)})
    assert block["reached_given_searched_by_path"] == 1.0
    assert block["reached_given_searched"] == 0.0
    assert block["path_content_disagreements"] == 1
    assert block["primary"] == "reached_by_content"


# =======================================================================================
# Two bootstrap implementations, and a headline mean that hid how few tasks carried it.
# =======================================================================================


def test_a_degenerate_sample_has_no_interval():
    assert cluster_bootstrap([0.5, 0.5, 0.5]) is None


def test_effect_concentration_counts_the_tasks_that_did_nothing():
    """A +0.17 mean over 24 tasks that lives on 9 of them is a different claim from one spread
    across all 24, and the mean cannot tell them apart."""

    deltas = {"a": 1.0, "b": 0.5, "c": 0.0, "d": 0.0, "e": -0.25}
    out = effect_concentration(deltas)
    assert out["n_contributing"] == 3
    assert out["n_zero"] == 2
    assert out["n_hurt"] == 1
    assert out["top3_share_of_positive"] == 1.0


# =======================================================================================
# The cost ledger reported a local embedder's ingest as an unqualified zero.
# =======================================================================================


def test_a_local_ingest_zero_is_qualified_rather_than_bare():
    """Mutation: dropping local_model. A table showing 0 against a competitor's LLM-extraction
    bill reads as "this one ingests for free"."""

    from harness.adapters.base import IngestReport

    report = IngestReport(
        arm="recall",
        namespace="ns",
        sessions_offered=125,
        items_stored=125,
        wall_time_ms=42_000.0,
        local_model="fastembed",
    )
    summary = summarize([], [report], pricing=None)
    arm = summary["arms"]["recall"]
    assert arm["ingest_local_model"] == "fastembed"
    assert arm["ingest_wall_time_ms"] == 42_000.0
    assert any("real zero and is not a zero cost" in note for note in arm["notes"])


def test_efficiency_reports_success_per_token():
    records = [
        SessionRecord(task_id="t1", arm="recall", success=True, input_tokens=80_000,
                      output_tokens=2_000),
        SessionRecord(task_id="t1", arm="bare", success=True, input_tokens=16_000,
                      output_tokens=1_700),
    ]
    out = efficiency(records)
    assert out["bare"]["successes_per_mtok_input"] > out["recall"]["successes_per_mtok_input"]


def test_pricing_is_still_required_for_dollars():
    pricing = {"m": ModelPricing(model="m", usd_per_mtok_input=1.0, usd_per_mtok_output=2.0,
                                 as_of="2026-08-28")}
    assert summarize([], [], pricing=pricing, model="m")["estimated_usd"] == 0.0
    assert summarize([], [], pricing=None)["estimated_usd"] is None
