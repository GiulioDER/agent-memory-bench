"""Claude-Mem, using the official plugin, worker import route, hooks, and MCP server."""

from __future__ import annotations

import hashlib
import base64
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.adapters.base import (
    ArmSpec,
    CorpusManifest,
    IngestReport,
    MemoryAdapter,
    digest_tree,
    namespace_path,
)
from harness.gate import AdmissionSignal
from harness.instructions import compose
from harness.transcripts import render_corpus

_CONFIG_PATH = Path(__file__).with_name("config.frozen.json")
_WRAPPER_PATH = Path(__file__).with_name("hook_wrapper.js")
_REQUIRED_HOOKS = ("SessionStart", "UserPromptSubmit", "PostToolUse", "Stop")
_PROJECT = "claude_mem"


def _config() -> dict[str, Any]:
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


class ClaudeMemAdapter(MemoryAdapter):
    name = "claude_mem"

    def __init__(
        self,
        staging_root: str | Path,
        base_prompt_file: str | Path,
        *,
        instruction: str | None = None,
        plugin_dir: str | Path | None = None,
    ) -> None:
        self.staging_root = Path(staging_root)
        self.base_prompt_file = Path(base_prompt_file)
        self.config = _config()
        self.instruction_override = instruction
        configured = plugin_dir or os.environ.get(str(self.config["plugin_dir_env"]))
        self.plugin_dir = Path(configured) if configured else None

    @staticmethod
    def shared_instruction(*, neutral: bool = False, variant: str = "protocol") -> str:
        config = _config()
        return compose("claude_mem", str(config["instruction"]), neutral=neutral, variant=variant)

    def _plugin_root(self) -> Path:
        if self.plugin_dir is None:
            raise RuntimeError(
                "CLAUDE_MEM_PLUGIN_DIR is not set; point it at the official claude-mem checkout "
                "or its plugin directory"
            )
        candidate = self.plugin_dir / "plugin"
        root = candidate if (candidate / ".claude-plugin" / "plugin.json").is_file() else self.plugin_dir
        required = (
            root / ".claude-plugin" / "plugin.json",
            root / ".mcp.json",
            root / "hooks" / "hooks.json",
            root / "scripts" / "bun-runner.js",
            root / "scripts" / "worker-service.cjs",
            root / "scripts" / "mcp-server.cjs",
        )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "CLAUDE_MEM_PLUGIN_DIR is not the pinned official plugin checkout; missing "
                f"{missing}"
            )
        manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        if manifest.get("version") != self.config["plugin_version"]:
            raise RuntimeError(
                f"Claude-Mem plugin version is {manifest.get('version')!r}, expected "
                f"{self.config['plugin_version']!r}"
            )
        return root

    def _data_dir(self, namespace: str) -> Path:
        return namespace_path(self.staging_root, namespace, "claude-mem-data")

    def _worker_port(self, namespace: str) -> int:
        configured = os.environ.get("CLAUDE_MEM_BENCHMARK_WORKER_PORT", "").strip()
        if configured:
            port = int(configured)
            if not 1024 <= port <= 65535:
                raise RuntimeError("CLAUDE_MEM_BENCHMARK_WORKER_PORT must be between 1024 and 65535")
            return port
        digest = int(hashlib.sha256(namespace.encode("utf-8")).hexdigest()[:8], 16)
        return int(self.config["worker_port_base"]) + (digest % 2000)

    def _observer_env(self) -> dict[str, str]:
        key = os.environ.get(str(self.config["observer_api_key_env"])) or os.environ.get(
            str(self.config["observer_api_key_fallback_env"])
        )
        if not key:
            raise RuntimeError(
                "Claude-Mem needs CLAUDE_MEM_OPENROUTER_API_KEY or OPENROUTER_API_KEY for its "
                "frozen OpenRouter observer provider"
            )
        return {
            "CLAUDE_MEM_PROVIDER": str(self.config["provider"]),
            "CLAUDE_MEM_OPENROUTER_API_KEY": key,
            "CLAUDE_MEM_OPENROUTER_MODEL": str(self.config["observer_model"]),
        }

    def _runtime_env(self, namespace: str, data_dir: Path) -> dict[str, str]:
        env = self._observer_env()
        env.update(
            {
                str(self.config["data_dir_env"]): str(data_dir.resolve()),
                str(self.config["worker_host_env"]): str(self.config["worker_host"]),
                str(self.config["worker_port_env"]): str(self._worker_port(namespace)),
                "CLAUDE_MEM_PROJECT": _PROJECT,
            }
        )
        return env

    def _write_worker_settings(self, data_dir: Path, namespace: str) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        settings = {
            "CLAUDE_MEM_WORKER_HOST": str(self.config["worker_host"]),
            "CLAUDE_MEM_WORKER_PORT": str(self._worker_port(namespace)),
            "CLAUDE_MEM_PROVIDER": str(self.config["provider"]),
            "CLAUDE_MEM_OPENROUTER_MODEL": str(self.config["observer_model"]),
            "CLAUDE_MEM_CONTEXT_OBSERVATIONS": "50",
        }
        (data_dir / "settings.json").write_text(
            json.dumps(settings, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

    def _worker_url(self, namespace: str) -> str:
        return f"http://{self.config['worker_host']}:{self._worker_port(namespace)}"

    def _request(self, method: str, url: str, body: dict[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        request = urllib.request.Request(url, data=payload, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=10.0) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[-1200:]
            raise RuntimeError(f"Claude-Mem worker returned {error.code}: {detail}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise RuntimeError(f"Claude-Mem worker unavailable at {url}: {error}") from error
        return json.loads(raw) if raw else {}

    def _start_worker(self, plugin_root: Path, data_dir: Path, namespace: str) -> None:
        self._write_worker_settings(data_dir, namespace)
        env = {**os.environ, **self._runtime_env(namespace, data_dir), "CLAUDE_PLUGIN_ROOT": str(plugin_root)}
        node = shutil.which("node") or "node"
        result = subprocess.run(
            [node, str(plugin_root / "scripts" / "bun-runner.js"), str(plugin_root / "scripts" / "worker-service.cjs"), "start"],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Claude-Mem worker start failed with exit "
                f"{result.returncode}: {result.stderr[-2000:]}"
            )

        deadline = time.monotonic() + float(self.config["ingest_timeout_s"])
        while time.monotonic() < deadline:
            try:
                self._request("GET", f"{self._worker_url(namespace)}{self.config['health_path']}")
                return
            except RuntimeError:
                time.sleep(1.0)
        raise RuntimeError("Claude-Mem worker did not become healthy before ingestion timeout")

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        corpus.verify()
        plugin_root = self._plugin_root()
        data_dir = self._data_dir(namespace)
        if data_dir.exists():
            shutil.rmtree(data_dir)
        self._start_worker(plugin_root, data_dir, namespace)

        staged = namespace_path(self.staging_root, namespace, "claude-mem-feed")
        if staged.exists():
            shutil.rmtree(staged)
        render_corpus([corpus.root / rel for rel in corpus.sessions], staged, root=corpus.root)

        # This is the vendor's own import representation. It keeps each rendered transcript as
        # one static discovery observation, so the qualification measures retrieval rather than a
        # second, harness-authored summarizer.
        sessions: list[dict[str, Any]] = []
        observations: list[dict[str, Any]] = []
        base_epoch = 1_700_000_000_000
        for index, path in enumerate(sorted(staged.glob("*.md"))):
            content_session_id = f"{namespace}:{path.stem}"
            memory_session_id = hashlib.sha256(content_session_id.encode("utf-8")).hexdigest()
            epoch = base_epoch + index
            created_at = datetime.fromtimestamp(epoch / 1000, tz=timezone.utc).isoformat()
            text = path.read_text(encoding="utf-8")
            sessions.append(
                {
                    "content_session_id": content_session_id,
                    "memory_session_id": memory_session_id,
                    "project": _PROJECT,
                    "platform_source": "claude",
                    "user_prompt": text[:500],
                    "started_at": created_at,
                    "started_at_epoch": epoch,
                    "completed_at": created_at,
                    "completed_at_epoch": epoch,
                    "status": "completed",
                }
            )
            observations.append(
                {
                    "memory_session_id": memory_session_id,
                    "project": _PROJECT,
                    "text": text,
                    "type": "discovery",
                    "title": path.stem,
                    "subtitle": "AMB frozen transcript feed",
                    "facts": json.dumps([text[:1000]]),
                    "narrative": text,
                    "concepts": json.dumps(["project-memory"]),
                    "files_read": "[]",
                    "files_modified": "[]",
                    "prompt_number": 1,
                    "discovery_tokens": 0,
                    "created_at": created_at,
                    "created_at_epoch": epoch,
                }
            )

        start = time.monotonic()
        result = self._request(
            "POST",
            f"{self._worker_url(namespace)}{self.config['import_path']}",
            {"sessions": sessions, "summaries": [], "observations": observations, "prompts": []},
        )
        stats = result.get("stats") if isinstance(result, dict) else None
        imported = stats.get("observationsImported") if isinstance(stats, dict) else None
        if imported != len(observations):
            raise RuntimeError(
                f"Claude-Mem imported {imported!r} observations, expected {len(observations)}"
            )

        query = next((item["text"][:200] for item in observations if item["text"]), "project memory")
        deadline = time.monotonic() + float(self.config["ingest_timeout_s"])
        hits = 0
        while time.monotonic() < deadline:
            try:
                params = urllib.parse.urlencode(
                    {"query": query, "project": _PROJECT, "limit": 1}
                )
                searched = self._request(
                    "GET", f"{self._worker_url(namespace)}{self.config['search_path']}?{params}"
                )
                rows = searched.get("observations") if isinstance(searched, dict) else None
                hits = len(rows) if isinstance(rows, list) else 0
                if hits:
                    break
            except RuntimeError:
                pass
            time.sleep(1.0)
        if hits == 0:
            raise RuntimeError("Claude-Mem import completed but worker search returned no hits")

        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            items_stored=imported,
            wall_time_ms=(time.monotonic() - start) * 1000.0,
            local_model=None,
            notes=(
                "loaded through Claude-Mem's shipped /api/import route",
                f"worker search verification returned {hits} hit(s) for project {_PROJECT}",
                f"observer provider {self.config['provider']} with model {self.config['observer_model']}",
            ),
        )

    def _write_hook_settings(self, config_dir: Path, plugin_root: Path) -> None:
        source = json.loads((plugin_root / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        wrapper = config_dir / "claude-mem-hook-wrapper.js"
        node = shutil.which("node") or "node"
        hooks: dict[str, list[dict[str, Any]]] = {}
        for event, groups in (source.get("hooks") or {}).items():
            rewritten: list[dict[str, Any]] = []
            for group_index, group in enumerate(groups):
                new_group = {key: value for key, value in group.items() if key != "hooks"}
                new_hooks = []
                for hook_index, hook in enumerate(group.get("hooks", [])):
                    if hook.get("type") != "command":
                        new_hooks.append(dict(hook))
                        continue
                    if event == "SessionStart" and group_index == 0 and hook_index == 0:
                        label = "SessionStartWorker"
                        args = [str(plugin_root / "scripts" / "bun-runner.js"), str(plugin_root / "scripts" / "worker-service.cjs"), "start"]
                    else:
                        labels = {"SessionStart": "SessionStart", "UserPromptSubmit": "UserPromptSubmit", "PostToolUse": "PostToolUse", "PreToolUse": "PreToolUse", "Stop": "Stop", "Setup": "Setup"}
                        label = labels.get(event, event)
                        action = {
                            "SessionStart": "context",
                            "UserPromptSubmit": "session-init",
                            "PostToolUse": "observation",
                            "PreToolUse": "file-context",
                            "Stop": "summarize",
                        }.get(event)
                        if action is None:
                            args = [str(plugin_root / "scripts" / "version-check.js")]
                        else:
                            args = [str(plugin_root / "scripts" / "bun-runner.js"), str(plugin_root / "scripts" / "worker-service.cjs"), "hook", "claude-code", action]
                    new_hook = dict(hook)
                    encoded_args = base64.b64encode(
                        json.dumps(args, separators=(",", ":")).encode("utf-8")
                    ).decode("ascii")
                    command_node = Path(node).as_posix() if os.name == "nt" else node
                    command_wrapper = wrapper.as_posix() if os.name == "nt" else str(wrapper)
                    new_hook["command"] = (
                        f'"{command_node}" "{command_wrapper}" {json.dumps(label)} {encoded_args}'
                    )
                    # Keep the vendor's supported hook shell. The generated command contains no
                    # shell expansion and the argv payload is base64 encoded for Windows quoting.
                    new_hook["shell"] = str(hook.get("shell") or "bash")
                    new_hooks.append(new_hook)
                new_group["hooks"] = new_hooks
                rewritten.append(new_group)
            hooks[event] = rewritten
        (config_dir / "settings.json").write_text(
            json.dumps({"hooks": hooks}, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

    def _prompt(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            (self.instruction_override or self.shared_instruction()).rstrip()
            + "\n\n"
            + self.base_prompt_file.read_text(encoding="utf-8"),
            encoding="utf-8",
            newline="\n",
        )
        return path

    def build(self, session_dir: Path, namespace: str, *, prompt_path: Path | None = None) -> ArmSpec:
        session_dir.mkdir(parents=True, exist_ok=True)
        plugin_root = self._plugin_root()
        data_dir = self._data_dir(namespace)
        config_dir = session_dir / "claude-config"
        if config_dir.exists():
            shutil.rmtree(config_dir)
        config_dir.mkdir(parents=True)
        copied_plugin = config_dir / "plugin"
        shutil.copytree(plugin_root, copied_plugin)
        shutil.copy2(_WRAPPER_PATH, config_dir / "claude-mem-hook-wrapper.js")
        home = config_dir / "home"
        home.mkdir(parents=True)
        self._write_hook_settings(config_dir, copied_plugin)
        prompt = self._prompt(prompt_path or session_dir / "prompt.md")

        mcp_config_path = session_dir / "claude-mem.mcp.json"
        mcp_config_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        str(self.config["server_name"]): {
                            "command": shutil.which("node") or "node",
                            "args": [str(copied_plugin / "scripts" / "mcp-server.cjs")],
                            "env": {
                                **self._runtime_env(namespace, data_dir),
                                "CLAUDE_PLUGIN_ROOT": str(copied_plugin),
                            },
                        }
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        ledger = config_dir / "hook-ledger.jsonl"
        env = {
            **self._runtime_env(namespace, data_dir),
            "CLAUDE_PLUGIN_ROOT": str(copied_plugin),
            "CLAUDE_MEM_HOOK_LEDGER": str(ledger),
            "HOME": str(home),
            "USERPROFILE": str(home),
        }
        return ArmSpec(
            arm=self.name,
            bare=False,
            mcp_config=str(mcp_config_path),
            append_system_prompt_file=prompt,
            memory_tool_prefix=str(self.config["tool_prefix"]),
            extra_allowed_tools=tuple(
                f"{self.config['tool_prefix']}{tool}" for tool in self.config["tools"]
            ),
            config_dir=config_dir,
            config_dir_digest=digest_tree(config_dir),
            env=env,
            metadata={
                "memory": "official_plugin_hooks_and_mcp",
                "transport": "lifecycle_hooks+stdio_mcp",
                "plugin_version": self.config["plugin_version"],
                "plugin_commit": self.config["plugin_commit"],
                "worker_data_dir": str(data_dir),
                "worker_port": self._worker_port(namespace),
                "hook_ledger": str(ledger),
                "prompt_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest(),
            },
        )

    def build_for_task(self, session_dir: Path, namespace: str, task_id: str, user_input: str) -> ArmSpec:
        return self.build(session_dir, namespace)

    def read_hook_ledger(self, session_id: str | None, config_dir: str | Path) -> tuple[dict[str, Any], ...]:
        path = Path(config_dir) / "hook-ledger.jsonl"
        if not path.is_file():
            return ()
        entries: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if session_id is None or entry.get("session_id") == session_id:
                entries.append(entry)
        return tuple(entries)

    def admission_signal(self) -> AdmissionSignal:
        return AdmissionSignal(
            arm=self.name,
            mcp_tool_prefixes=(str(self.config["tool_prefix"]),),
            required_hooks=_REQUIRED_HOOKS,
        )

    def describe(self) -> dict[str, Any]:
        plugin_root = None
        if self.plugin_dir is not None:
            try:
                plugin_root = str(self._plugin_root())
            except (FileNotFoundError, RuntimeError):
                plugin_root = str(self.plugin_dir)
        return {
            "arm": self.name,
            "product": self.config["product"],
            "memory": "official Claude-Mem plugin hooks and MCP search",
            "plugin_version": self.config["plugin_version"],
            "plugin_commit": self.config["plugin_commit"],
            "plugin_root": plugin_root,
            "mcp_server": self.config["server_name"],
            "tools": list(self.config["tools"]),
            "required_hooks": list(_REQUIRED_HOOKS),
            "import_path": self.config["import_path"],
            "observer_provider": self.config["provider"],
            "observer_model": self.config["observer_model"],
        }
