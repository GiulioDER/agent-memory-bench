from harness.adapters.base import IngestReport
from harness.costs import ModelPricing, summarize, tally
from harness.schema import SessionRecord


def _record(arm: str, task: str = "t1", seed: int = 0, tokens: tuple | None = (1000, 200)):
    kwargs = {}
    if tokens is not None:
        kwargs = {"input_tokens": tokens[0], "output_tokens": tokens[1]}
    return SessionRecord(
        task_id=task, arm=arm, seed=seed, success=True, wall_time_ms=1500.0, **kwargs
    )


def test_tally_sums_sessions_and_ingest_per_arm():
    records = [_record("recall"), _record("recall", seed=1), _record("bare")]
    ingest = [
        IngestReport(
            arm="recall",
            namespace="bench-recall-0",
            sessions_offered=10,
            llm_input_tokens=5000,
            llm_output_tokens=700,
            wall_time_ms=9000.0,
        )
    ]
    ledger = tally(records, ingest)
    recall = ledger["recall"]
    assert recall.sessions == 2
    assert recall.session_input_tokens == 2000
    assert recall.ingest_input_tokens == 5000
    assert recall.total_tokens == 2000 + 400 + 5000 + 700
    assert ledger["bare"].total_tokens == 1200


def test_unmetered_sessions_are_counted_not_zeroed():
    ledger = tally([_record("mem0", tokens=None)])
    assert ledger["mem0"].sessions_unmetered == 1
    assert ledger["mem0"].session_input_tokens == 0


def test_unmetered_ingest_is_flagged_in_notes():
    ingest = [IngestReport(arm="supermemory", namespace="ns", sessions_offered=5)]
    ledger = tally([], ingest)
    assert ledger["supermemory"].ingest_unmetered == 1
    assert any("missing from the totals" in note for note in ledger["supermemory"].notes)


def test_summarize_without_pricing_reports_tokens_and_says_why_no_dollars():
    summary = summarize([_record("bare")])
    assert summary["total_tokens"] == 1200
    assert summary["estimated_usd"] is None
    assert "pricing_note" in summary


def test_summarize_with_pricing_estimates_usd():
    pricing = {
        "m": ModelPricing(
            model="m",
            usd_per_mtok_input=3.0,
            usd_per_mtok_output=15.0,
            as_of="2026-08-22",
        )
    }
    summary = summarize([_record("bare")], pricing=pricing, model="m")
    assert summary["estimated_usd"] == round((1000 * 3.0 + 200 * 15.0) / 1e6, 4)
    assert summary["pricing_as_of"] == "2026-08-22"
