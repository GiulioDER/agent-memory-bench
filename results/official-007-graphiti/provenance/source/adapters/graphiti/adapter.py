"""Graphiti's official MCP integration for the AMB harness.

The adapter launches the upstream ``mcp_server/main.py`` through ``uv``. Corpus ingestion also
uses the upstream MCP surface, one ``add_memory`` call per transcript, so the measured arm does
not introduce a second Graphiti write API. The agent receives only the upstream read and status
tools from ``config.frozen.json``.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Self

from harness.adapters.base import (
    ArmSpec,
    CorpusManifest,
    IngestReport,
    MemoryAdapter,
    namespace_path,
    validate_namespace,
)
from harness.broker import broker_jsonrpc_call
from harness.gate import AdmissionSignal
from harness.instructions import compose
from harness.mcp_probe import _bounded_reader, _read_line
from harness.transcripts import render_transcript

_CONFIG_PATH = Path(__file__).with_name("config.frozen.json")
_PASSTHROUGH_KEYS = (
    "APPDATA",
    "LOCALAPPDATA",
    "SystemRoot",
    "TEMP",
    "TMP",
    "PATH",
    "USERPROFILE",
    "HOME",
)


def _config() -> dict[str, Any]:
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def _decode_tool_result(reply: dict[str, Any]) -> dict[str, Any]:
    """Decode a FastMCP tools/call result without accepting a transport error as empty data."""

    if "error" in reply:
        raise RuntimeError(f"Graphiti MCP returned a JSON-RPC error: {reply['error']}")
    result = reply.get("result")
    if not isinstance(result, dict):
        raise TypeError(f"Graphiti MCP returned no result object: {reply!r}")
    if result.get("isError"):
        raise RuntimeError(f"Graphiti MCP tool returned an error: {reply!r}")
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        # FastMCP serializes some Pydantic return values as a single nested
        # ``result`` object, while scalar response models are emitted flat.
        # Unwrap only this exact shape so a real error is never treated as empty.
        if set(structured) == {"result"} and isinstance(structured["result"], dict):
            return structured["result"]
        return structured
    for block in result.get("content", ()):
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        value = block.get("text", "")
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict):
                if set(decoded) == {"result"} and isinstance(decoded["result"], dict):
                    return decoded["result"]
                return decoded
    raise RuntimeError(f"Graphiti MCP returned no JSON tool payload: {reply!r}")


class _StdioMcp:
    """Small synchronous client for the stdio MCP transport used by upstream Graphiti."""

    def __init__(self, argv: list[str], env: dict[str, str], timeout_s: float) -> None:
        self.timeout_s = timeout_s
        self.proc = subprocess.Popen(
            argv,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        if self.proc.stdout is None or self.proc.stdin is None:
            raise RuntimeError("Graphiti MCP did not expose stdio pipes")
        self.lines = _bounded_reader(self.proc.stdout)
        self._next_id = 1
        self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agent-memory-bench", "version": "1"},
            },
        )
        self.notify("notifications/initialized")
        self.request("tools/list", {})

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.proc.stdin is None:
            raise RuntimeError("Graphiti MCP stdin is closed")
        request_id = self._next_id
        self._next_id += 1
        self.proc.stdin.write(
            json.dumps(
                {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            )
            + "\n"
        )
        self.proc.stdin.flush()
        deadline = time.monotonic() + self.timeout_s
        while True:
            line = _read_line(self.lines, deadline, self.proc)
            if not line:
                detail = self._stderr_tail()
                raise RuntimeError(
                    f"Graphiti MCP did not answer {method!r} within {self.timeout_s:.0f}s. "
                    f"stderr: {detail}"
                )
            try:
                reply = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Graphiti MCP wrote non JSON output: {line[:400]!r}") from exc
            if reply.get("id") == request_id:
                return reply

    def notify(self, method: str) -> None:
        if self.proc.stdin is None:
            raise RuntimeError("Graphiti MCP stdin is closed")
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.proc.stdin.flush()

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return _decode_tool_result(
            self.request("tools/call", {"name": name, "arguments": arguments})
        )

    def _stderr_tail(self) -> str:
        if self.proc.stderr is None:
            return ""
        return "stderr is available after the process exits"

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.communicate()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()


class GraphitiAdapter(MemoryAdapter):
    name = "graphiti"

    def __init__(
        self,
        staging_root: str | Path,
        base_prompt_file: str | Path,
        instruction: str | None = None,
        ingest_capability_factory: Callable[[], str] | None = None,
    ) -> None:
        self.staging_root = Path(staging_root)
        self.base_prompt_file = Path(base_prompt_file)
        self.config = _config()
        self.instruction_override = instruction
        self.ingest_capability_factory = ingest_capability_factory

    @staticmethod
    def shared_instruction(*, neutral: bool = False, variant: str = "protocol") -> str:
        config = _config()
        return compose(
            "graphiti", str(config["search_sentence"]), neutral=neutral, variant=variant
        )

    def _required_env(self, name: str) -> str:
        value = os.environ.get(name, "").strip()
        if not value:
            raise RuntimeError(f"the Graphiti arm needs {name} set; secrets stay outside the repo")
        return value

    def _mcp_dir(self) -> Path:
        raw = self._required_env(str(self.config["mcp_dir_env"]))
        path = Path(raw).resolve()
        if not (path / "main.py").is_file():
            raise RuntimeError(f"{path} is not an upstream Graphiti mcp_server checkout")
        return path

    def _ingest_timeout_seconds(self) -> float | None:
        """Return the optional whole-ingest deadline; zero or null means no deadline.

        Graphiti's official ``add_memory`` call is asynchronous and the upstream queue processes
        episodes sequentially. A fixed wall-clock deadline therefore turns a slow but healthy
        queue into a false failed run. Individual MCP requests still retain their transport
        timeout below, so this removes only the benchmark-wide cutoff.
        """
        raw = self.config.get("ingest_timeout_seconds")
        if raw is None:
            return None
        timeout = float(raw)
        return timeout if timeout > 0 else None

    def _mcp_request_timeout_seconds(self) -> float:
        """Return the bounded timeout for one short MCP transport request."""
        timeout = float(self.config.get("broker_request_timeout_seconds", 180))
        if timeout <= 0:
            raise RuntimeError("Graphiti MCP request timeout must be positive")
        return timeout

    def _server_env(self, namespace: str) -> dict[str, str]:
        validate_namespace(namespace)
        key_name = next(
            (name for name in self.config["llm_key_envs"] if os.environ.get(str(name), "").strip()),
            None,
        )
        if key_name is None:
            names = ", ".join(str(name) for name in self.config["llm_key_envs"])
            raise RuntimeError(f"the Graphiti arm needs one of {names} set")
        key = os.environ[str(key_name)].strip()
        api_url = os.environ.get(str(self.config["llm_api_url_env"]), "").strip()
        if not api_url:
            api_url = (
                "https://openrouter.ai/api/v1"
                if key_name == "GRAPHITI_OPENROUTER_API_KEY"
                else "https://api.openai.com/v1"
            )
        provider = os.environ.get(
            str(self.config["database_provider_env"]),
            str(self.config["database_provider_default"]),
        ).strip().lower()
        if provider not in {"neo4j", "falkordb"}:
            raise RuntimeError(f"unsupported Graphiti database provider: {provider}")
        embedder_provider = os.environ.get(
            str(self.config["embedder_provider_env"]),
            str(self.config["embedder_provider_default"]),
        ).strip().lower()
        if embedder_provider not in {"openai", "voyage"}:
            raise RuntimeError(f"unsupported Graphiti embedder provider: {embedder_provider}")
        env = {
            "OPENAI_API_KEY": key,
            "OPENAI_API_URL": api_url,
            "MODEL_NAME": os.environ.get(str(self.config["llm_model_env"]), "gpt-5.5").strip(),
            "LLM_STRUCTURED_OUTPUT_MODE": os.environ.get(
                str(self.config["llm_structured_output_env"]), "json_schema"
            ).strip(),
            "EMBEDDER_MODEL": os.environ.get(
                str(self.config["embedder_model_env"]), "text-embedding-3-small"
            ).strip(),
            "SEMAPHORE_LIMIT": os.environ.get(
                str(self.config["semaphore_env"]), "1"
            ).strip(),
            "GRAPHITI_GROUP_ID": namespace,
            "GRAPHITI_TELEMETRY_ENABLED": "false",
            "LLM__PROVIDERS__OPENAI__API_KEY": key,
            "LLM__PROVIDERS__OPENAI__API_URL": api_url,
        }
        if provider == "neo4j":
            env.update(
                {
                    "NEO4J_URI": os.environ.get(
                        str(self.config["neo4j_uri_env"]), "bolt://localhost:7687"
                    ).strip(),
                    "NEO4J_USER": os.environ.get(
                        str(self.config["neo4j_user_env"]), "neo4j"
                    ).strip(),
                    "NEO4J_PASSWORD": self._required_env(
                        str(self.config["neo4j_password_env"])
                    ),
                    "NEO4J_DATABASE": os.environ.get(
                        str(self.config["neo4j_database_env"]), "neo4j"
                    ).strip(),
                }
            )
        else:
            env.update(
                {
                    "FALKORDB_URI": os.environ.get(
                        str(self.config["falkordb_uri_env"]), "redis://localhost:6379"
                    ).strip(),
                    "FALKORDB_DATABASE": os.environ.get(
                        str(self.config["falkordb_database_env"]), "default_db"
                    ).strip(),
                }
            )
            for key in ("username", "password"):
                value = os.environ.get(str(self.config[f"falkordb_{key}_env"]), "").strip()
                if value:
                    env[f"FALKORDB_{key.upper()}"] = value
        embedder_key = os.environ.get(str(self.config["embedder_api_key_env"]), key).strip()
        embedder_url = os.environ.get(
            str(self.config["embedder_api_url_env"]), "https://api.openai.com/v1"
        ).strip()
        if embedder_provider == "voyage":
            env["VOYAGE_API_KEY"] = self._required_env(str(self.config["voyage_api_key_env"]))
        else:
            env["EMBEDDER__PROVIDERS__OPENAI__API_KEY"] = embedder_key
            env["EMBEDDER__PROVIDERS__OPENAI__API_URL"] = embedder_url
            env["EMBEDDER_MODEL"] = os.environ.get(
                str(self.config["embedder_model_env"]), "text-embedding-3-small"
            ).strip()
        for name in _PASSTHROUGH_KEYS:
            value = os.environ.get(name)
            if value:
                env[name] = value
        return env

    def _server_argv(self, namespace: str) -> list[str]:
        validate_namespace(namespace)
        command = str(self.config["uv_command"])
        if os.name == "nt" and Path(command).name.lower() == "uv":
            command = f"{command}.exe"
        return [
            command,
            "run",
            "--isolated",
            "--directory",
            str(self._mcp_dir()),
            "--project",
            ".",
            "main.py",
            "--transport",
            "stdio",
            "--llm-provider",
            os.environ.get(
                str(self.config["llm_provider_env"]),
                str(self.config["llm_provider_default"]),
            ).strip().lower(),
            "--model",
            os.environ.get(str(self.config["llm_model_env"]), "gpt-5.5").strip(),
            "--embedder-provider",
            os.environ.get(
                str(self.config["embedder_provider_env"]),
                str(self.config["embedder_provider_default"]),
            ).strip().lower(),
            "--embedder-model",
            os.environ.get(
                str(self.config["embedder_model_env"]), "text-embedding-3-small"
            ).strip(),
            "--database-provider",
            os.environ.get(
                str(self.config["database_provider_env"]),
                str(self.config["database_provider_default"]),
            ).strip().lower(),
            "--group-id",
            namespace,
        ]

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

    def _prompt_path(self, namespace: str) -> Path:
        return namespace_path(self.staging_root, namespace, "prompt.md")

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        corpus.verify()
        validate_namespace(namespace)
        if not corpus.sessions:
            return IngestReport(
                arm=self.name,
                namespace=namespace,
                sessions_offered=0,
                items_stored=0,
                notes=("the verified corpus is empty; no Graphiti episode was submitted",),
            )
        start = time.monotonic()
        timeout = self._ingest_timeout_seconds()
        request_timeout = self._mcp_request_timeout_seconds()
        if os.environ.get("AMB_GRAPHITI_INGEST_VIA_BROKER") == "1":
            return self._ingest_via_broker(
                corpus, namespace, start=start, timeout=timeout, request_timeout=request_timeout
            )
        with _StdioMcp(
            self._server_argv(namespace), self._server_env(namespace), request_timeout
        ) as client:
            for rel_path in sorted(corpus.sessions):
                source = corpus.root / rel_path
                response = client.call(
                    "add_memory",
                    {
                        "name": rel_path,
                        "episode_body": render_transcript(source),
                        "group_id": namespace,
                        "source": "text",
                        "source_description": f"agent-memory-bench transcript {rel_path}",
                    },
                )
                if response.get("error"):
                    raise RuntimeError(f"Graphiti rejected {rel_path}: {response['error']}")

            deadline = None if timeout is None else time.monotonic() + timeout
            expected = len(corpus.sessions)
            stored = 0
            reported = -1
            while deadline is None or time.monotonic() < deadline:
                response = client.call(
                    "get_episodes",
                    {"group_ids": [namespace], "max_episodes": expected},
                )
                episodes = response.get("episodes")
                if not isinstance(episodes, list):
                    raise TypeError(
                        "Graphiti get_episodes returned no episode list after add_memory calls"
                    )
                stored = len(episodes)
                if stored != reported:
                    print(f"[ingest] graphiti progress: {stored}/{expected}", flush=True)
                    reported = stored
                if stored >= expected:
                    break
                sleep_for = 2.0 if deadline is None else min(2.0, max(0.05, deadline - time.monotonic()))
                time.sleep(sleep_for)
            if deadline is not None and stored < expected:
                raise RuntimeError(
                    f"Graphiti queued {expected} episode(s), but only {stored} became visible "
                    f"within {timeout:.0f}s"
                )
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            items_stored=stored,
            wall_time_ms=(time.monotonic() - start) * 1000.0,
            llm_input_tokens=None,
            llm_output_tokens=None,
            notes=(
                "ingested through the official Graphiti MCP add_memory tool",
                "add_memory is asynchronous; completion was verified through get_episodes",
            ),
        )

    def _ingest_via_broker(
        self,
        corpus: CorpusManifest,
        namespace: str,
        *,
        start: float,
        timeout: float | None,
        request_timeout: float,
    ) -> IngestReport:
        url = os.environ.get(
            "AMB_GRAPHITI_INGEST_BROKER_URL",
            os.environ.get("AMB_MEMORY_BROKER_URL", ""),
        ).strip()
        token = os.environ.get("AMB_GRAPHITI_INGEST_CAPABILITY", "").strip()
        if not url or (not token and self.ingest_capability_factory is None):
            raise RuntimeError(
                "brokered Graphiti ingestion needs AMB_MEMORY_BROKER_URL and "
                "AMB_GRAPHITI_INGEST_CAPABILITY"
            )

        def current_token() -> str:
            refreshed = (
                self.ingest_capability_factory()
                if self.ingest_capability_factory is not None
                else token
            )
            if not refreshed:
                raise RuntimeError("Graphiti ingest capability factory returned an empty token")
            return refreshed

        broker_jsonrpc_call(
            url, current_token(), "initialize", request_id=1, timeout_s=request_timeout
        )
        request_id = 2
        for rel_path in sorted(corpus.sessions):
            source = corpus.root / rel_path
            response = broker_jsonrpc_call(
                url,
                current_token(),
                "tools/call",
                {
                    "name": "add_memory",
                    "arguments": {
                        "name": rel_path,
                        "episode_body": render_transcript(source),
                        "group_id": namespace,
                        "source": "text",
                        "source_description": f"agent-memory-bench transcript {rel_path}",
                    },
                },
                request_id=request_id,
                timeout_s=request_timeout,
            )
            request_id += 1
            _decode_tool_result(response)

        deadline = None if timeout is None else time.monotonic() + timeout
        expected = len(corpus.sessions)
        stored = 0
        reported = -1
        while deadline is None or time.monotonic() < deadline:
            response = broker_jsonrpc_call(
                url,
                current_token(),
                "tools/call",
                {
                    "name": "get_episodes",
                    "arguments": {"group_ids": [namespace], "max_episodes": expected},
                },
                request_id=request_id,
                timeout_s=request_timeout,
            )
            request_id += 1
            episodes = _decode_tool_result(response).get("episodes")
            if not isinstance(episodes, list):
                raise TypeError("Graphiti broker get_episodes returned no episode list")
            stored = len(episodes)
            if stored != reported:
                print(f"[ingest] graphiti progress: {stored}/{expected}", flush=True)
                reported = stored
            if stored >= expected:
                break
            sleep_for = 2.0 if deadline is None else min(2.0, max(0.05, deadline - time.monotonic()))
            time.sleep(sleep_for)
        if deadline is not None and stored < expected:
            raise RuntimeError(
                f"Graphiti broker queued {expected} episode(s), but only {stored} became visible "
                f"within {timeout:.0f}s"
            )
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=expected,
            items_stored=stored,
            wall_time_ms=(time.monotonic() - start) * 1000.0,
            llm_input_tokens=None,
            llm_output_tokens=None,
            notes=(
                "ingested through the controller-only Graphiti broker capability",
                "add_memory is asynchronous; completion was verified through get_episodes",
            ),
        )

    def _spec(self, session_dir: Path, namespace: str, prompt: Path) -> ArmSpec:
        session_dir.mkdir(parents=True, exist_ok=True)
        mcp_config_path = session_dir / "graphiti.mcp.json"
        mcp_config_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        str(self.config["server_name"]): {
                            "command": self._server_argv(namespace)[0],
                            "args": self._server_argv(namespace)[1:],
                            "env": self._server_env(namespace),
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
            mcp_config=str(mcp_config_path),
            append_system_prompt_file=prompt,
            memory_tool_prefix=prefix,
            extra_allowed_tools=tuple(
                f"{prefix}{tool}" for tool in self.config["allowed_tools"]
            ),
            config_dir_digest=hashlib.sha256(
                _CONFIG_PATH.read_bytes() + prompt.read_bytes()
            ).hexdigest(),
            metadata={
                "memory": "static+retrieved",
                "transport": "stdio",
                "group_id": namespace,
                "database_provider": os.environ.get(
                    str(self.config["database_provider_env"]),
                    str(self.config["database_provider_default"]),
                ).strip().lower(),
                "upstream_ref": self.config["upstream_ref"],
                "tool_prefix": prefix,
                "prompt_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest(),
            },
        )

    def build(self, session_dir: Path, namespace: str) -> ArmSpec:
        prompt = self._prompt_path(namespace)
        if not prompt.is_file():
            prompt = self._write_prompt(prompt)
        return self._spec(session_dir, namespace, prompt)

    def build_for_task(
        self, session_dir: Path, namespace: str, task_id: str, user_input: str
    ) -> ArmSpec:
        return self._spec(session_dir, namespace, self._write_prompt(session_dir / "prompt.md"))

    def admission_signal(self) -> AdmissionSignal:
        return AdmissionSignal(
            arm=self.name, mcp_tool_prefixes=(str(self.config["tool_prefix"]),)
        )

    def describe(self) -> dict[str, Any]:
        return {
            "arm": self.name,
            "memory": "static+retrieved",
            "product": self.config["product"],
            "integration": "official Graphiti MCP server",
            "package_pin": self.config["package_pin"],
            "upstream_ref": self.config["upstream_ref"],
            "config_sha256": hashlib.sha256(_CONFIG_PATH.read_bytes()).hexdigest(),
        }
