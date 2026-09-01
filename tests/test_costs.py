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


def test_a_local_only_ingest_reports_a_real_zero_rather_than_a_free_one():
    """An arm that makes no hosted call has truthfully zero tokens, and the note has to say so.

    Printed bare beside a competitor's extraction bill, that zero reads as "this one ingests for
    free". It does not: it pays in host compute, which is in ingest_wall_time_ms.
    """

    ingest = [
        IngestReport(
            arm="mempalace",
            namespace="ns",
            sessions_offered=5,
            llm_input_tokens=0,
            llm_output_tokens=0,
            local_model="chromadb onnx all-MiniLM-L6-v2",
            wall_time_ms=30700.0,
        )
    ]
    ledger = tally([], ingest)
    assert ledger["mempalace"].ingest_local_model == "chromadb onnx all-MiniLM-L6-v2"
    assert ledger["mempalace"].ingest_unmetered == 0
    assert any("spent NO hosted tokens" in note for note in ledger["mempalace"].notes)


def test_an_arm_that_embeds_locally_and_extracts_remotely_keeps_both_costs():
    """RED before 2026-09-01, and wrong in the most expensive direction.

    `local_model` was an exclusive branch, so an arm that embeds locally AND extracts with a
    hosted LLM had its extraction tokens DROPPED from the ledger entirely, under a note asserting
    it "spent NO hosted tokens". A real bill missing from the totals, beneath a sentence saying
    there was none. The first such arm is `cognee`.
    """

    ingest = [
        IngestReport(
            arm="cognee",
            namespace="ns",
            sessions_offered=5,
            llm_input_tokens=41000,
            llm_output_tokens=9000,
            local_model="fastembed BAAI/bge-small-en-v1.5",
            wall_time_ms=120000.0,
        )
    ]
    ledger = tally([], ingest)
    costs = ledger["cognee"]
    assert costs.ingest_input_tokens == 41000
    assert costs.ingest_output_tokens == 9000
    assert costs.ingest_local_model == "fastembed BAAI/bge-small-en-v1.5"
    assert costs.ingest_unmetered == 0
    assert not any("spent NO hosted tokens" in note for note in costs.notes)
    assert any("paid on BOTH sides" in note for note in costs.notes)


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
