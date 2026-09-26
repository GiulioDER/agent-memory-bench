"""Task aware prefetch through the public AML Add and Search contract."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from harness.adapters.base import (
    ArmSpec,
    CorpusManifest,
    IngestReport,
    MemoryAdapter,
    namespace_path,
    resolve_corpus_path,
)
from harness.corpus_names import neutral_stem
from harness.gate import AdmissionSignal
from harness.memory_prompt import estimated_input_tokens, sha256_text
from scripts.audit_corpus import readable_text


@dataclass(frozen=True)
class HostedResult:
    payload: dict[str, Any]
    headers: dict[str, str]
    latency_ms: float


class HostedAmlClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        try:
            self.request_timeout_s = float(
                os.environ.get("AMB_HOSTED_REQUEST_TIMEOUT_S", "180")
            )
        except ValueError as error:
            raise ValueError("AMB_HOSTED_REQUEST_TIMEOUT_S must be numeric") from error
        if self.request_timeout_s <= 0 or self.request_timeout_s > 1_800:
            raise ValueError(
                "AMB_HOSTED_REQUEST_TIMEOUT_S must be greater than 0 and at most 1800"
            )

    def request(self, path: str, payload: dict[str, Any]) -> HostedResult:
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        started = time.monotonic()
        with urlopen(request, timeout=self.request_timeout_s) as response:
            body = json.loads(response.read().decode("utf-8"))
            headers = {key.casefold(): value for key, value in response.headers.items()}
            status = response.status
        if status != 200:
            raise RuntimeError(f"hosted AML {path} returned HTTP {status}")
        return HostedResult(body, headers, (time.monotonic() - started) * 1_000)

    def get(self, path: str) -> HostedResult:
        request = Request(
            self.base_url + path,
            method="GET",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        started = time.monotonic()
        with urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
            headers = {key.casefold(): value for key, value in response.headers.items()}
            status = response.status
        if status != 200:
            raise RuntimeError(f"hosted AML {path} returned HTTP {status}")
        return HostedResult(body, headers, (time.monotonic() - started) * 1_000)


def resolve_hosted_api_key(api_key_env: str, peer_api_key_env: str) -> str:
    """Resolve one endpoint credential without guessing that two identities share a key.

    The endpoint-specific variable is authoritative. The legacy shared variable may fill one
    missing endpoint only when the peer endpoint-specific variable is present and byte equal to
    it. A lone legacy value proves no relationship between the two deployed services and is
    therefore refused.
    """

    specific = os.environ.get(api_key_env, "").strip()
    if specific:
        return specific
    legacy = os.environ.get("RECALL_AML_API_KEY", "").strip()
    peer = os.environ.get(peer_api_key_env, "").strip()
    if legacy and peer and hmac.compare_digest(legacy, peer):
        return legacy
    raise RuntimeError(
        f"{api_key_env} is required; legacy RECALL_AML_API_KEY fallback is allowed only when "
        f"it explicitly equals {peer_api_key_env}"
    )


def _manifest_digest(corpus: CorpusManifest) -> str:
    encoded = json.dumps(dict(sorted(corpus.sessions.items())), separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _ranked_evidence(data: list[dict[str, Any]]) -> str:
    blocks = ["Project memory retrieved with the exact task prompt:", ""]
    for rank, item in enumerate(data, start=1):
        content = item.get("content", "")
        if not isinstance(content, str) or not content.strip():
            continue
        blocks.extend(
            [
                f"[Evidence item rank={rank}]",
                content,
                f"Source session: {item.get('session_id', 'unknown')}",
                "[/Evidence item]",
                "",
            ]
        )
    return "\n".join(blocks).rstrip() + "\n"


class HostedAmlPrefetchAdapter(MemoryAdapter):
    """Bulk ingest once, then Search with each exact AMB task prompt."""

    def __init__(
        self,
        *,
        name: str,
        expected_variant: str,
        base_url_env: str,
        staging_root: str | Path,
        base_prompt_file: str | Path,
        api_key_env: str | None = None,
        peer_api_key_env: str | None = None,
        client: HostedAmlClient | None = None,
        add_workers: int | None = None,
        top_k: int = 10,
    ) -> None:
        self.name = name
        self.expected_variant = expected_variant
        self.base_url_env = base_url_env
        self.api_key_env = api_key_env
        self.peer_api_key_env = peer_api_key_env
        self.staging_root = Path(staging_root)
        self.base_prompt_file = Path(base_prompt_file)
        self.top_k = top_k
        workers = add_workers or int(os.environ.get("AMB_HOSTED_ADD_WORKERS", "3"))
        if workers < 1 or workers > 3:
            raise ValueError("hosted AML Add workers must be from 1 through 3")
        self.add_workers = workers
        if client is None:
            base_url = os.environ.get(base_url_env, "").strip()
            if not base_url:
                raise RuntimeError(f"{base_url_env} is required")
            if not api_key_env or not peer_api_key_env:
                raise RuntimeError("endpoint-specific hosted AML API key variables are required")
            api_key = resolve_hosted_api_key(api_key_env, peer_api_key_env)
            client = HostedAmlClient(base_url, api_key)
        self.client = client

    def _version(self) -> dict[str, Any]:
        version = self.client.get("/version").payload
        if version.get("variant") != self.expected_variant:
            raise RuntimeError(
                f"{self.name} expected {self.expected_variant}, got {version.get('variant')}"
            )
        return version

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        corpus.verify()
        version = self._version()
        manifest_sha = _manifest_digest(corpus)
        self.client.request("/v1/delete", {"user_id": namespace})
        started = time.monotonic()

        def add_one(item: tuple[str, str]) -> int:
            relative, expected_sha = item
            path = resolve_corpus_path(corpus.root, relative)
            actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_sha != expected_sha:
                raise RuntimeError(f"corpus changed after verification: {relative}")
            content = readable_text(path)
            result = self.client.request(
                "/v1/add",
                {
                    "request_id": "amb-" + hashlib.sha256(
                        f"{manifest_sha}\0{relative}".encode()
                    ).hexdigest(),
                    "user_id": namespace,
                    # The hosted API echoes this back and `_ranked_evidence` prints it into the
                    # prompt as "Source session". It was the corpus path until 2026-09-26, so a
                    # planted hit arrived labelled `plants/<task>/stale_...`. Neutral now.
                    "session_id": neutral_stem(relative),
                    "messages": [{"role": "user", "content": content}],
                },
            )
            if result.payload.get("success") is not True:
                raise RuntimeError(f"hosted AML Add failed for {relative}")
            return int(result.payload.get("raw_count", 0))

        with ThreadPoolExecutor(max_workers=self.add_workers) as pool:
            raw_counts = list(pool.map(add_one, sorted(corpus.sessions.items())))
        wall_ms = (time.monotonic() - started) * 1_000
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            items_stored=sum(raw_counts),
            wall_time_ms=wall_ms,
            notes=(
                f"public AML Add with {self.add_workers} workers",
                f"variant={version['variant']}",
                f"git_commit={version.get('git_commit', 'unknown')}",
                f"generation_id={version.get('generation_id', 'unknown')}",
            ),
        )

    def build(self, session_dir: Path, namespace: str) -> ArmSpec:
        raise TypeError("hosted AML prefetch requires the exact task prompt")

    def build_for_task(
        self, session_dir: Path, namespace: str, task_id: str, user_input: str
    ) -> ArmSpec:
        started = time.monotonic()
        result = self.client.request(
            "/v1/search",
            {"query": user_input, "user_id": namespace, "top_k": self.top_k},
        )
        elapsed_ms = (time.monotonic() - started) * 1_000
        data = result.payload.get("data")
        if not isinstance(data, list):
            raise TypeError("hosted AML Search response has no data list")
        if not data:
            raise RuntimeError(f"{self.name} returned no evidence for task {task_id}")
        evidence = _ranked_evidence(data)
        prompt = namespace_path(self.staging_root, namespace, task_id, self.name, "prompt.md")
        prompt.parent.mkdir(parents=True, exist_ok=True)
        static = self.base_prompt_file.read_text(encoding="utf-8").rstrip()
        prompt.write_text(evidence.rstrip() + "\n\n" + static + "\n", encoding="utf-8")
        result_sha = sha256_text(json.dumps(result.payload, ensure_ascii=False, sort_keys=True))
        payload = prompt.with_name("search.json")
        payload.write_text(
            json.dumps(
                {
                    "query_sha256": sha256_text(user_input),
                    "result_sha256": result_sha,
                    "hit_count": len(data),
                    "headers": {
                        key: value
                        for key, value in result.headers.items()
                        if key.startswith("x-recall-")
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        diagnostic = {
            "kind": self.name,
            "task_id": task_id,
            "query_sha256": sha256_text(user_input),
            "query_text": None,
            "result_sha256": result_sha,
            "hit_count": len(data),
            "abstained": not data,
            "prefetch_wall_time_ms": elapsed_ms,
            "prefetch_input_tokens": None,
            "prefetch_status": "ok",
            "config_identity": hashlib.sha256(
                f"{self.expected_variant}\0{self.base_url_env}\0{self.top_k}".encode()
            ).hexdigest(),
            "injected_text_sha256": sha256_text(evidence),
            "injected_input_tokens": estimated_input_tokens(evidence),
        }
        return ArmSpec(
            arm=self.name,
            bare=True,
            append_system_prompt_file=prompt,
            metadata={
                "memory": "hosted_aml_prefetch",
                "prompt_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest(),
                "memory_diagnostic": diagnostic,
            },
        )

    def admission_signal(self) -> AdmissionSignal:
        return AdmissionSignal(arm=self.name, metadata={"diagnostic_kind": self.name})

    def describe(self) -> dict[str, Any]:
        return {
            "arm": self.name,
            "memory": "hosted AML exact prompt prefetch",
            "expected_variant": self.expected_variant,
            "base_url_env": self.base_url_env,
            "api_key_env": self.api_key_env,
            "top_k": self.top_k,
            "add_workers": self.add_workers,
            "version": self._version(),
        }
