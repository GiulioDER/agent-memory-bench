from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import adapters.recall_aml_prefetch.adapter as hosted_module
from adapters.recall_aml_prefetch.adapter import (
    HostedAmlPrefetchAdapter,
    HostedResult,
)
from harness.adapters.base import ArmSpec, CorpusManifest, IngestReport
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


def test_hosted_prefetch_refuses_an_empty_search_before_a_model_session(tmp_path: Path) -> None:
    """A successful HTTP response with no evidence must block the paid session.

    Red proof: before the fix, ``build_for_task`` wrote an empty prompt and returned an ArmSpec
    whose diagnostic merely said ``abstained=True``. This test failed with DID NOT RAISE.
    """
    client = _Client("C7_routed_specialists")
    client.search_data = []

    with pytest.raises(RuntimeError, match="returned no evidence for task ts-a"):
        _adapter(tmp_path, client).build_for_task(
            tmp_path / "unused",
            "amb-specialist-full",
            "ts-a",
            "Fix the parser",
        )


def test_hosted_prefetch_arms_use_separate_endpoint_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C6 and C7 must not silently reuse one credential for two endpoint identities.

    Red proof: before the fix, both constructors ignored the endpoint-specific keys and refused
    with ``RECALL_AML_API_KEY is required`` before either captured client was created.
    """
    static = tmp_path / "static.md"
    static.write_text("Repository instructions", encoding="utf-8")
    monkeypatch.setenv("RECALL_AML_C6_BASE_URL", "https://c6.invalid")
    monkeypatch.setenv("RECALL_AML_C7_BASE_URL", "https://c7.invalid")
    monkeypatch.setenv("RECALL_AML_C6_API_KEY", "c6-secret")
    monkeypatch.setenv("RECALL_AML_C7_API_KEY", "c7-secret")
    monkeypatch.delenv("RECALL_AML_API_KEY", raising=False)
    captured: list[tuple[str, str]] = []

    class CapturingClient:
        def __init__(self, base_url: str, api_key: str) -> None:
            captured.append((base_url, api_key))

    monkeypatch.setattr(hosted_module, "HostedAmlClient", CapturingClient)
    bundle = {"claude_md": static}

    pilot.adapter_for("aml_c6_prefetch", bundle, tmp_path, {})
    pilot.adapter_for("aml_c7_prefetch", bundle, tmp_path, {})

    assert captured == [
        ("https://c6.invalid", "c6-secret"),
        ("https://c7.invalid", "c7-secret"),
    ]


def test_legacy_hosted_key_alone_is_ambiguous_and_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The old shared key is accepted only when one endpoint-specific key proves equality.

    Red proof: before the fix, a lone ``RECALL_AML_API_KEY`` was accepted for every endpoint, so
    this test failed with DID NOT RAISE.
    """
    static = tmp_path / "static.md"
    static.write_text("Repository instructions", encoding="utf-8")
    monkeypatch.setenv("RECALL_AML_C6_BASE_URL", "https://c6.invalid")
    monkeypatch.setenv("RECALL_AML_API_KEY", "ambiguous-shared-secret")
    monkeypatch.delenv("RECALL_AML_C6_API_KEY", raising=False)
    monkeypatch.delenv("RECALL_AML_C7_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="RECALL_AML_C6_API_KEY is required"):
        pilot.adapter_for("aml_c6_prefetch", {"claude_md": static}, tmp_path, {})


def test_legacy_hosted_key_may_fill_one_endpoint_when_the_peer_proves_equality(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A staged migration may use the legacy value only with an equal explicit peer key."""
    static = tmp_path / "static.md"
    static.write_text("Repository instructions", encoding="utf-8")
    monkeypatch.setenv("RECALL_AML_C7_BASE_URL", "https://c7.invalid")
    monkeypatch.setenv("RECALL_AML_C6_API_KEY", "shared-secret")
    monkeypatch.setenv("RECALL_AML_API_KEY", "shared-secret")
    monkeypatch.delenv("RECALL_AML_C7_API_KEY", raising=False)
    captured: list[tuple[str, str]] = []

    class CapturingClient:
        def __init__(self, base_url: str, api_key: str) -> None:
            captured.append((base_url, api_key))

    monkeypatch.setattr(hosted_module, "HostedAmlClient", CapturingClient)

    pilot.adapter_for("aml_c7_prefetch", {"claude_md": static}, tmp_path, {})

    assert captured == [("https://c7.invalid", "shared-secret")]


def test_prepare_hosted_prefetch_ingests_both_and_searches_each_unique_task_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preparation performs the complete hosted setup without entering the model runner.

    Mutation proof: limiting either hosted-arm loop to its first item makes the two-arm ingest
    assertion or the complete task-by-arm Search assertion fail.
    """
    calls: list[tuple[str, ...]] = []

    class FakeAdapter:
        def __init__(self, arm: str) -> None:
            self.arm = arm

        def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
            calls.append(("ingest", self.arm, namespace))
            return IngestReport(
                arm=self.arm,
                namespace=namespace,
                sessions_offered=len(corpus.sessions),
            )

        def build_for_task(
            self,
            session_dir: Path,
            namespace: str,
            task_id: str,
            user_input: str,
        ) -> ArmSpec:
            calls.append(("search", self.arm, task_id, user_input))
            return ArmSpec(
                arm=self.arm,
                metadata={
                    "memory_diagnostic": {
                        "query_sha256": task_id + "-query",
                        "result_sha256": task_id + "-result",
                        "hit_count": 1,
                        "prefetch_wall_time_ms": 1.0,
                    }
                },
            )

    adapters = {
        arm: FakeAdapter(arm) for arm in pilot.HOSTED_AML_PREFETCH_ARMS
    }

    class FakeRegistry:
        def get(self, arm: str) -> FakeAdapter:
            return adapters[arm]

    monkeypatch.setattr(
        pilot,
        "adapter_for",
        lambda arm, bundle, staging, texts, oracle_catalog=None: adapters[arm],
    )
    tasks = [
        SimpleNamespace(task_id="ts-one", prompt="first prompt"),
        SimpleNamespace(task_id="ts-two", prompt="second prompt"),
    ]
    bundles = {task.task_id: {} for task in tasks}

    reports, specs = pilot.prepare_hosted_prefetch(
        registry=FakeRegistry(),
        corpus=CorpusManifest(root=tmp_path, sessions={"one.jsonl": "digest"}),
        tasks=tasks,
        run_arms=("claude_md", *pilot.HOSTED_AML_PREFETCH_ARMS),
        bundles=bundles,
        staging=tmp_path / "staging",
        texts={},
        namespace="amb-specialist-full-001",
        output_dir=tmp_path,
    )

    assert [report.arm for report in reports] == list(pilot.HOSTED_AML_PREFETCH_ARMS)
    assert set(specs) == {
        (task.task_id, arm)
        for task in tasks
        for arm in pilot.HOSTED_AML_PREFETCH_ARMS
    }
    assert calls == [
        ("ingest", "aml_c6_prefetch", "amb-specialist-full-001"),
        ("ingest", "aml_c7_prefetch", "amb-specialist-full-001"),
        ("search", "aml_c6_prefetch", "ts-one", "first prompt"),
        ("search", "aml_c7_prefetch", "ts-one", "first prompt"),
        ("search", "aml_c6_prefetch", "ts-two", "second prompt"),
        ("search", "aml_c7_prefetch", "ts-two", "second prompt"),
    ]


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
