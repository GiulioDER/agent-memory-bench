"""Industry benchmark adapter using RE-call Hosted's public Add and Search API."""

from __future__ import annotations

import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from harness.adapters.base import (
    ArmSpec,
    CorpusManifest,
    IngestReport,
    MemoryAdapter,
    RankedHit,
    RankedResult,
    resolve_corpus_path,
    validate_namespace,
)
from harness.gate import AdmissionSignal
from harness.instructions import compose

_CONFIG_PATH = Path(__file__).with_name("config.frozen.json")
_REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class HostedHttpResponse:
    payload: dict[str, Any]
    headers: dict[str, str]


def _config() -> dict[str, Any]:
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def _timestamp_ms(value: object) -> int:
    """Translate the corpus ISO timestamp to AML's Unix millisecond wire format."""
    if isinstance(value, bool):
        raise TypeError("session timestamp must not be a boolean")
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        raise TypeError("session timestamp must be an ISO string or Unix milliseconds")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp() * 1_000)


def session_messages(path: Path) -> list[dict[str, Any]]:
    """Translate one neutral JSONL transcript without dropping tool evidence."""
    messages: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        event = json.loads(raw)
        parts = [str(event.get("content", ""))]
        if event.get("tool_name"):
            parts.extend(
                [
                    f"tool_name: {event['tool_name']}",
                    f"tool_input: {event.get('tool_input', '')}",
                    f"tool_result: {event.get('tool_result', '')}",
                ]
            )
        content = "\n".join(part for part in parts if part)
        if not content:
            content = "[empty message]"
        message: dict[str, Any] = {
            "role": str(event.get("role", "unknown")),
            "content": content,
        }
        if event.get("ts"):
            message["timestamp"] = _timestamp_ms(event["ts"])
        messages.append(message)
    return messages


class HostedHttpClient:
    def __init__(self, base_url: str, api_key: str, *, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def request_with_headers(
        self, path: str, payload: dict[str, Any] | None = None
    ) -> HostedHttpResponse:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=body,
            method="GET" if payload is None else "POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                headers = {key.casefold(): value for key, value in response.headers.items()}
        except HTTPError as exc:
            detail = exc.read(2_000).decode("utf-8", errors="replace")
            raise RuntimeError(f"hosted API {path} returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"hosted API {path} is unreachable: {exc.reason}") from exc
        if not isinstance(result, dict):
            raise TypeError(f"hosted API {path} returned a non-object response")
        return HostedHttpResponse(result, headers)

    def request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.request_with_headers(path, payload).payload


class RecallHostedAdapter(MemoryAdapter):
    name = "recall_hosted"
    supported_gatings = ("served",)

    def __init__(
        self,
        staging_root: str | Path,
        base_prompt_file: str | Path,
        instruction: str | None = None,
    ) -> None:
        self.staging_root = Path(staging_root)
        self.base_prompt_file = Path(base_prompt_file)
        self.config = _config()
        self.instruction_override = instruction

    @staticmethod
    def shared_instruction(*, neutral: bool = False, variant: str = "protocol") -> str:
        config = _config()
        return compose(
            "recall_hosted",
            str(config["search_sentence"]),
            neutral=neutral,
            variant=variant,
        )

    def _required(self, config_key: str) -> str:
        variable = str(self.config[config_key])
        value = os.environ.get(variable, "").strip()
        if not value:
            raise RuntimeError(f"the recall_hosted arm needs {variable} set")
        return value

    def _client(self, *, search: bool = False) -> HostedHttpClient:
        timeout_key = "search_timeout_seconds" if search else "add_timeout_seconds"
        return HostedHttpClient(
            self._required("url_env"),
            self._required("api_key_env"),
            timeout=float(self.config[timeout_key]),
        )

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        corpus.verify()
        validate_namespace(namespace)
        client = self._client()
        client.request("/v1/delete", {"user_id": namespace})

        def add_one(item: tuple[str, str]) -> int:
            relative, content_hash = item
            messages = session_messages(resolve_corpus_path(corpus.root, relative))
            stored = 0
            for offset in range(0, len(messages), 256):
                batch = messages[offset : offset + 256]
                request_id = hashlib.sha256(
                    f"{namespace}\0{relative}\0{content_hash}\0{offset}".encode()
                ).hexdigest()
                response = client.request(
                    "/v1/add",
                    {
                        "request_id": request_id,
                        "messages": batch,
                        "user_id": namespace,
                        "session_id": relative,
                    },
                )
                expected = {
                    "success": True,
                    "request_id": request_id,
                    "user_id": namespace,
                    "session_id": relative,
                }
                if not expected.items() <= response.items():
                    raise RuntimeError("hosted Add response did not echo the request identity")
                stored += len(batch)
            return stored

        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=int(self.config["add_concurrency"])) as pool:
            counts = list(pool.map(add_one, sorted(corpus.sessions.items())))
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            items_stored=sum(counts),
            wall_time_ms=(time.monotonic() - started) * 1_000,
            llm_input_tokens=None,
            llm_output_tokens=None,
            notes=(
                "loaded through the public synchronous Add endpoint",
                "items_stored counts source messages acknowledged by the hosted product",
            ),
        )

    def search(
        self, namespace: str, query: str, *, gating: str = "served", limit: int = 10
    ) -> RankedResult:
        if gating not in self.supported_gatings:
            raise ValueError(f"recall_hosted supports only {self.supported_gatings}")
        validate_namespace(namespace)
        result = self._client(search=True).request(
            "/v1/search",
            {"query": query, "user_id": namespace, "top_k": min(limit, 100)},
        )
        data = result.get("data")
        if not isinstance(data, list):
            raise TypeError("hosted Search response has no data array")
        hits: list[RankedHit] = []
        seen: set[str] = set()
        for item in data:
            if not isinstance(item, dict) or not item.get("session_id"):
                continue
            source = str(item["session_id"])
            if source in seen:
                continue
            seen.add(source)
            hits.append(
                RankedHit(
                    source_path=source, score=float(item.get("score", 0.0)), rank=len(hits) + 1
                )
            )
            if len(hits) >= limit:
                break
        return RankedResult(
            hits=tuple(hits),
            gating=gating,
            abstained=False,
            query_sha256=hashlib.sha256(query.encode()).hexdigest(),
            detail={"items_returned": len(data), "documents": len(hits)},
        )

    def _write_prompt(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        instruction = self.instruction_override or self.shared_instruction()
        static = self.base_prompt_file.read_text(encoding="utf-8")
        path.write_text(
            instruction.rstrip() + "\n\n" + static.rstrip() + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return path

    def build(self, session_dir: Path, namespace: str) -> ArmSpec:
        return self.build_for_task(session_dir, namespace, "", "")

    def build_for_task(
        self, session_dir: Path, namespace: str, task_id: str, user_input: str
    ) -> ArmSpec:
        validate_namespace(namespace)
        session_dir.mkdir(parents=True, exist_ok=True)
        prompt = self._write_prompt(session_dir / "prompt.md")
        mcp_path = session_dir / "recall_hosted.mcp.json"
        mcp_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        str(self.config["server_name"]): {
                            "command": os.environ.get("PYTHON", os.sys.executable),
                            "args": ["-m", "adapters.recall_hosted.mcp_bridge"],
                            "env": {
                                "PYTHONPATH": str(_REPO),
                                "RECALL_HOSTED_URL": self._required("url_env"),
                                "RECALL_HOSTED_API_KEY": self._required("api_key_env"),
                                "RECALL_HOSTED_USER_ID": namespace,
                                "RECALL_HOSTED_TOP_K": str(self.config["search_top_k"]),
                            },
                        }
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        prefix = str(self.config["tool_prefix"])
        return ArmSpec(
            arm=self.name,
            bare=True,
            mcp_config=str(mcp_path),
            append_system_prompt_file=prompt,
            memory_tool_prefix=prefix,
            extra_allowed_tools=tuple(f"{prefix}{tool}" for tool in self.config["allowed_tools"]),
            config_dir_digest=hashlib.sha256(
                _CONFIG_PATH.read_bytes() + prompt.read_bytes()
            ).hexdigest(),
            metadata={
                "memory": "static+retrieved",
                "transport": "hosted HTTPS through stdio MCP bridge",
                "product": self.config["product"],
                "tool_prefix": prefix,
            },
        )

    def admission_signal(self) -> AdmissionSignal:
        return AdmissionSignal(arm=self.name, mcp_tool_prefixes=(str(self.config["tool_prefix"]),))

    def describe(self) -> dict[str, Any]:
        return {
            "arm": self.name,
            "product": self.config["product"],
            "memory": "static+retrieved",
            "transport": "hosted HTTPS",
            "config_sha256": hashlib.sha256(_CONFIG_PATH.read_bytes()).hexdigest(),
        }
