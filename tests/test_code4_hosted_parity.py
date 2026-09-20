from scripts.code4_hosted_parity import (
    canonical_digest,
    expected_chunk_id,
    first_gold_rank,
    percentile,
    postgres_safe_window,
    tenant_for,
)
from scripts.retrieval_probe import Window


def test_hosted_identities_match_frozen_canonical_shape() -> None:
    payload = {
        "source_session_id": "sessions/ts-example/precursor.jsonl",
        "segment": 2,
        "content": "stable window content",
    }
    assert expected_chunk_id(
        payload["source_session_id"], payload["segment"], payload["content"]
    ) == "raw_" + canonical_digest(payload)
    assert tenant_for("user") == (
        "aml_04f8996da763b7a969b1028ee3007569eaf3a635486ddab211d512c85b9df8fb"
    )


def test_parity_metrics_helpers_are_deterministic() -> None:
    assert first_gold_rank([4, 2, 9], {2, 8}) == 2
    assert first_gold_rank([4, 2, 9], {8}) is None
    assert percentile([40.0, 10.0, 30.0, 20.0], 0.50) == 20.0
    assert percentile([40.0, 10.0, 30.0, 20.0], 0.95) == 40.0


def test_postgres_safe_window_preserves_order_and_replaces_only_nul() -> None:
    window = postgres_safe_window(Window(doc="d.jsonl", text="one\x00two"))
    assert window == Window(doc="d.jsonl", text="one␀two")
