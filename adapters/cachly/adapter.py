"""The ``cachly`` arm, entering through its published MCP server.

The session read path is the pinned ``@cachly-dev/mcp-server`` npm package. Corpus loading is
kept behind the vendor supplied bulk loader because the public MCP tools are designed for one
lesson or context write at a time, while this benchmark loads thousands of transcript documents.
The loader receives the corpus and credentials through its environment and must print one JSON
object describing the completed load.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

from harness.adapters.base import (
    ArmSpec,
    CorpusManifest,
    IngestReport,
    MemoryAdapter,
    namespace_path,
    validate_namespace,
)
from harness.gate import AdmissionSignal
from harness.instructions import compose

_CONFIG_PATH = Path(__file__).with_name("config.frozen.json")

# An MCP ``env`` block replaces the parent environment. Keep the runtime values needed by npm and
# Node, while passing the Cachly credentials only when the operator supplied them.
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


class CachlyAdapter(MemoryAdapter):
    name = "cachly"

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

    # ------------------------------------------------------------------ environment

    def _required_env(self, key: str) -> str:
        variable = str(self.config[key])
        value = os.environ.get(variable, "").strip()
        if not value:
            raise RuntimeError(
                f"the cachly arm needs {variable} set; it is named by the frozen config and is "
                "never stored in the repository"
            )
        return value

    def _server_env(self, namespace: str) -> dict[str, str]:
        validate_namespace(namespace)
        instance = self._required_env("instance_id_env")
        api_key = os.environ.get(str(self.config["api_key_env"]), "").strip()
        jwt = os.environ.get(str(self.config["jwt_env"]), "").strip()
        if not api_key and not jwt:
            raise RuntimeError(
                f"the cachly arm needs {self.config['api_key_env']} or "
                f"{self.config['jwt_env']} set; the server must not fall back to an anonymous "
                "or personal Brain"
            )

        env = {
            str(self.config["instance_id_env"]): instance,
            # The server accepts either spelling. Keep the operator's chosen credential name and
            # do not duplicate a secret into a second environment variable.
            **({str(self.config["api_key_env"]): api_key} if api_key else {}),
            **({str(self.config["jwt_env"]): jwt} if jwt else {}),
            # A benchmark session must not emit update checks or usage pings as another treatment.
            "CACHLY_NO_UPDATE_CHECK": "1",
            "CACHLY_NO_TELEMETRY": "1",
        }
        api_url_var = str(self.config["api_url_env"])
        api_url = os.environ.get(api_url_var, "").strip()
        if api_url:
            env[api_url_var] = api_url
        for key in _PASSTHROUGH_KEYS:
            value = os.environ.get(key)
            if value:
                env[key] = value
        return env

    def _bulk_command(self) -> list[str]:
        variable = str(self.config["bulk_ingest_command_env"])
        raw = os.environ.get(variable, "").strip()
        if not raw:
            raise RuntimeError(
                f"the cachly arm needs {variable} set to the vendor supplied bulk loader; "
                "loading thousands of transcripts through one-at-a-time public MCP writes is "
                "not an acceptable benchmark ingest path"
            )
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = shlex.split(raw, posix=os.name != "nt")
        if not isinstance(parsed, list) or not parsed or not all(
            isinstance(item, str) and item for item in parsed
        ):
            raise RuntimeError(
                f"{variable} must be a JSON argv array or a shell-like command, not {raw!r}"
            )
        parsed[0] = self._windows_npx_name(parsed[0])
        return parsed

    @staticmethod
    def _windows_npx_name(command: str) -> str:
        """Use the executable shim that Python can launch on Windows."""

        if os.name == "nt" and Path(command).name.lower() == "npx":
            return f"{command}.cmd"
        return command

    # ------------------------------------------------------------------ instruction and paths

    @staticmethod
    def shared_instruction(*, neutral: bool = False, variant: str = "protocol") -> str:
        config = _config()
        return compose(
            "cachly", str(config["search_sentence"]), neutral=neutral, variant=variant
        )

    def _instruction_text(self) -> str:
        return self.instruction_override or self.shared_instruction()

    def _write_prompt(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        static = self.base_prompt_file.read_text(encoding="utf-8")
        path.write_text(
            self._instruction_text().rstrip() + "\n\n" + static.rstrip() + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return path

    def _prompt_path(self, namespace: str) -> Path:
        return namespace_path(self.staging_root, namespace, "prompt.md")

    # ------------------------------------------------------------------ ingest

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        corpus.verify()
        validate_namespace(namespace)
        command = self._bulk_command()
        env = self._server_env(namespace)
        env.update(
            {
                "AMB_CACHLY_CORPUS_ROOT": str(corpus.root.resolve()),
                "AMB_CACHLY_CORPUS_MANIFEST": str((corpus.root / "manifest.json").resolve()),
                "AMB_CACHLY_NAMESPACE": namespace,
                "AMB_CACHLY_EXPECTED_SESSIONS": str(len(corpus.sessions)),
            }
        )
        start = time.monotonic()
        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(self.config["bulk_ingest_timeout_seconds"]),
            check=False,
        )
        elapsed_ms = (time.monotonic() - start) * 1000.0
        if result.returncode != 0:
            raise RuntimeError(
                f"cachly bulk ingest failed with exit {result.returncode}: "
                f"{result.stderr[-2000:]}"
            )
        report = _last_json_object(result.stdout)
        if report is None:
            raise RuntimeError(
                "cachly bulk ingest returned no JSON report; the loader must print an object "
                "with sessions_offered and items_stored. Last output:\n" + result.stdout[-2000:]
            )
        offered = _positive_int(report, "sessions_offered")
        stored = _positive_int(report, "items_stored")
        if offered != len(corpus.sessions):
            raise RuntimeError(
                f"cachly bulk ingest offered {offered} session(s), but this corpus manifest "
                f"contains {len(corpus.sessions)}"
            )
        if report.get("namespace") not in (None, namespace):
            raise RuntimeError(
                f"cachly bulk ingest reported namespace {report.get('namespace')!r}, "
                f"expected {namespace!r}"
            )
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=offered,
            items_stored=stored,
            wall_time_ms=elapsed_ms,
            llm_input_tokens=None,
            llm_output_tokens=None,
            notes=(
                "loaded through the vendor supplied bulk path, not one MCP write per transcript",
                "the loader owns Cachly's extraction and embedding accounting",
            ),
        )

    # ------------------------------------------------------------------ build

    def build(self, session_dir: Path, namespace: str) -> ArmSpec:
        session_dir.mkdir(parents=True, exist_ok=True)
        prompt = self._prompt_path(namespace)
        if not prompt.is_file():
            prompt = self._write_prompt(prompt)
        return self._spec(session_dir, prompt, namespace)

    def build_for_task(
        self, session_dir: Path, namespace: str, task_id: str, user_input: str
    ) -> ArmSpec:
        session_dir.mkdir(parents=True, exist_ok=True)
        return self._spec(session_dir, self._write_prompt(session_dir / "prompt.md"), namespace)

    def _spec(self, session_dir: Path, prompt: Path, namespace: str) -> ArmSpec:
        mcp_config_path = session_dir / "cachly.mcp.json"
        mcp_config = {
            "mcpServers": {
                str(self.config["server_name"]): {
                    "command": self._windows_npx_name(str(self.config["command"])),
                    "args": list(self.config["args"]),
                    "env": self._server_env(namespace),
                }
            }
        }
        mcp_config_path.write_text(json.dumps(mcp_config, indent=2), encoding="utf-8")
        prefix = str(self.config["tool_prefix"])
        return ArmSpec(
            arm=self.name,
            bare=True,
            mcp_config=str(mcp_config_path),
            append_system_prompt_file=prompt,
            memory_tool_prefix=prefix,
            extra_allowed_tools=tuple(f"{prefix}{tool}" for tool in self.config["allowed_tools"]),
            config_dir_digest=hashlib.sha256(
                _CONFIG_PATH.read_bytes() + prompt.read_bytes()
            ).hexdigest(),
            metadata={
                "memory": "static+retrieved",
                "transport": "stdio",
                "package_pin": str(self.config["package_pin"]),
                "tool_prefix": prefix,
                "prompt_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest(),
            },
        )

    # ------------------------------------------------------------------ gate and description

    def admission_signal(self) -> AdmissionSignal:
        return AdmissionSignal(
            arm=self.name, mcp_tool_prefixes=(str(self.config["tool_prefix"]),)
        )

    def describe(self) -> dict[str, Any]:
        return {
            "arm": self.name,
            "memory": "static+retrieved",
            "product": str(self.config["product"]),
            "package_pin": str(self.config["package_pin"]),
            "bulk_ingest": "vendor supplied command",
            "tools_allowed": len(self.config["allowed_tools"]),
            "config_sha256": hashlib.sha256(_CONFIG_PATH.read_bytes()).hexdigest(),
        }


def _last_json_object(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _positive_int(report: dict[str, Any], key: str) -> int:
    value = report.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RuntimeError(f"cachly bulk ingest report has no positive integer {key!r}: {report!r}")
    return value
