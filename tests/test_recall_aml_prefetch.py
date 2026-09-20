from __future__ import annotations

import json
from pathlib import Path

from adapters.recall_aml_prefetch.adapter import (
    HostedAmlPrefetchAdapter,
    HostedResult,
)
from harness.adapters.base import CorpusManifest
from scripts import pilot


class _Client:
    def __init__(self, variant: str) -> None:
        self.variant = variant
        self.calls = []
        self.search_data = [
            {
                "id": "rank-two-lexically",
                "content": "first ranked evidence",
                "session_id": "sessions/ts-a/p01.jsonl",
            },
            {
                "id": "a-sorts-first",
                "content": "second ranked evidence",
                "session_id": "distractors/d001.jsonl",
            },
        ]

    def get(self, path):
        self.calls.append(("GET", path, None))
        return HostedResult(
            {
                "variant": self.variant,
                "git_commit": "candidate",
                "generation_id": "candidate-generation",
            },
            {},
            1.0,
        )

    def request(self, path, payload):
        self.calls.append(("POST", path, payload))
        if path == "/v1/delete":
            return HostedResult({"success": True, "deleted_count": 0}, {}, 1.0)
        if path == "/v1/add":
            return HostedResult({"success": True, "raw_count": 2}, {}, 2.0)
        if path == "/v1/search":
            return HostedResult(
                {"data": list(self.search_data)},
                {"x-recall-search-ms": "3.000"},
                3.0,
            )
        raise AssertionError(path)


def _corpus(tmp_path: Path) -> CorpusManifest:
    root = tmp_path / "corpus"
    session = root / "sessions" / "ts-a" / "p01.jsonl"
    distractor = root / "distractors" / "d001.jsonl"
    session.parent.mkdir(parents=True)
    distractor.parent.mkdir(parents=True)
    session.write_text(
        json.dumps({"role": "user", "content": "governing fact"}) + "\n",
        encoding="utf-8",
    )
    distractor.write_text(
        json.dumps({"role": "user", "content": "noise"}) + "\n",
        encoding="utf-8",
    )
    return CorpusManifest.build(root)


def _adapter(tmp_path: Path, client: _Client) -> HostedAmlPrefetchAdapter:
    static = tmp_path / "static.md"
    static.write_text("Repository instructions", encoding="utf-8")
    return HostedAmlPrefetchAdapter(
        name="aml_c7_prefetch",
        expected_variant="C7_routed_specialists",
        base_url_env="RECALL_AML_C7_BASE_URL",
        staging_root=tmp_path / "stage",
        base_prompt_file=static,
        client=client,
        add_workers=1,
    )


def test_hosted_prefetch_ingests_the_verified_corpus_through_public_add(tmp_path: Path) -> None:
    """The adapter must clear only its namespace and offer every manifest session to Add.

    Red proof: mutating the ingest loop to slice off the last session makes both the offered Add
    count and ``items_stored`` assertions fail at the public client boundary.
    """
    client = _Client("C7_routed_specialists")
    corpus = _corpus(tmp_path)
    report = _adapter(tmp_path, client).ingest(corpus, "amb-specialist-full")

    assert report.sessions_offered == 2
    assert report.items_stored == 4
    assert client.calls[1] == (
        "POST",
        "/v1/delete",
        {"user_id": "amb-specialist-full"},
    )
    adds = [call for call in client.calls if call[1] == "/v1/add"]
    assert len(adds) == 2
    assert {call[2]["session_id"] for call in adds} == set(corpus.sessions)
    assert all(call[2]["user_id"] == "amb-specialist-full" for call in adds)


def test_hosted_prefetch_preserves_search_rank_in_the_injected_prompt(tmp_path: Path) -> None:
    """Task Solve must see Search order, not an id sorted rewrite of the evidence.

    Red proof: sorting ``data`` by id inside ``_ranked_evidence`` places the second ranked item
    first and fails the relative position assertion.
    """
    client = _Client("C7_routed_specialists")
    spec = _adapter(tmp_path, client).build_for_task(
        tmp_path / "unused",
        "amb-specialist-full",
        "ts-a",
        "Fix the parser",
    )

    prompt = Path(spec.append_system_prompt_file).read_text(encoding="utf-8")
    assert prompt.index("first ranked evidence") < prompt.index("second ranked evidence")
    assert prompt.rstrip().endswith("Repository instructions")
    diagnostic = spec.metadata["memory_diagnostic"]
    assert diagnostic["hit_count"] == 2
    assert diagnostic["kind"] == "aml_c7_prefetch"
    assert diagnostic["query_text"] is None


def test_hosted_prefetch_refuses_the_wrong_deployed_variant(tmp_path: Path) -> None:
    """An endpoint label mismatch must stop before destructive namespace cleanup.

    Red proof: removing the version comparison lets ingest reach Delete and makes the expected
    exception disappear.
    """
    import pytest

    client = _Client("C6_code4_exact_bm25")
    adapter = _adapter(tmp_path, client)
    with pytest.raises(RuntimeError, match="expected C7_routed_specialists"):
        adapter.ingest(_corpus(tmp_path), "amb-specialist-full")
    assert all(call[1] != "/v1/delete" for call in client.calls)


def test_synthesis_opt_in_expands_only_the_explicit_task_boundary() -> None:
    """The full candidate run may name xs tasks without changing ordinary AMB runs.

    Red proof: changing the opt in branch to return only ``SELECTABLE_PREFIXES`` makes the final
    assertion fail because ``xs-`` remains excluded.
    """
    assert pilot.task_prefixes(explicit=False, include_synthesis=False) == ("ts-",)
    assert pilot.task_prefixes(explicit=False, include_synthesis=True) == ("ts-",)
    assert "xs-" not in pilot.task_prefixes(explicit=True, include_synthesis=False)
    assert "xs-" in pilot.task_prefixes(explicit=True, include_synthesis=True)


def test_hosted_prefetch_arms_are_self_ingesting_reference_tracks() -> None:
    """Both arms must ingest through Add while remaining static prefetch references.

    Red proof: removing C7 from ``SELF_INGESTING_ARMS`` fails its membership assertion while the
    remaining registry assertions still pass.
    """
    assert "aml_c6_prefetch" in pilot.ARMS
    assert "aml_c7_prefetch" in pilot.ARMS
    assert "aml_c6_prefetch" in pilot.SELF_INGESTING_ARMS
    assert "aml_c7_prefetch" in pilot.SELF_INGESTING_ARMS
    assert "aml_c6_prefetch" not in pilot.MEMORY_ARMS
    assert "aml_c7_prefetch" not in pilot.MEMORY_ARMS
