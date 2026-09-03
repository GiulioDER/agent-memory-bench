"""The ``supermemory`` arm, using the official Claude Code plugin and local API.

The plugin is supplied by ``SUPERMEMORY_PLUGIN_DIR`` and copied without modifying its hook
implementation. AMB adds only a small process wrapper that records hook execution for the
admission gate. The default API URL is Supermemory Local, so the arm does not require a paid
Supermemory account. A remote URL is accepted only when the caller explicitly supplies it.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from harness.adapters.base import ArmSpec, CorpusManifest, IngestReport, MemoryAdapter, digest_tree
from harness.gate import AdmissionSignal
from harness.instructions import compose
from harness.transcripts import render_corpus

_CONFIG_PATH = Path(__file__).with_name("config.frozen.json")
_WRAPPER_PATH = Path(__file__).with_name("hook_wrapper.js")
_REQUIRED_HOOKS = ("SessionStart", "UserPromptSubmit")
_HOOK_FILES = {
    "SessionStart": "session-start.js",
    "UserPromptSubmit": "recall-directive.js",
    "PreToolUse": "recall-approve.js",
    "Stop": "capture.js",
}


class SupermemoryAdapter(MemoryAdapter):
    name = "supermemory"

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
        self.config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        self.instruction = instruction
        configured = plugin_dir or os.environ.get(str(self.config["plugin_dir_env"]))
        self.plugin_dir = Path(configured) if configured else None

    @staticmethod
    def shared_instruction(*, neutral: bool = False) -> str:
        return compose(
            "supermemory",
            "Supermemory provides persistent project context through its official Claude Code "
            "hooks; use that context before acting when relevant.",
            neutral=neutral,
        )

    def _base_url(self) -> str:
        value = os.environ.get(str(self.config["base_url_env"]))
        return (value or str(self.config["base_url_default"])).rstrip("/")

    def _api_key(self) -> str:
        key = os.environ.get(str(self.config["api_key_env"])) or os.environ.get(
            str(self.config["api_key_fallback_env"])
        )
        if not key:
            raise RuntimeError(
                "Supermemory needs SUPERMEMORY_CC_API_KEY or SUPERMEMORY_API_KEY; "
                "use the key printed by Supermemory Local or provide an explicit remote key"
            )
        return key

    @staticmethod
    def _node() -> str:
        return os.environ.get("SUPERMEMORY_NODE") or shutil.which("node") or "node"

    def _plugin_root(self) -> Path:
        if self.plugin_dir is None:
            raise RuntimeError(
                "SUPERMEMORY_PLUGIN_DIR is not set; point it at the official "
                "claude-supermemory checkout or its plugin directory"
            )
        candidate = self.plugin_dir / "plugin"
        root = candidate if (candidate / ".claude-plugin" / "plugin.json").is_file() else self.plugin_dir
        required = [root / "hooks" / name for name in _HOOK_FILES.values()]
        required.append(root / "hooks" / "hooks.json")
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "SUPERMEMORY_PLUGIN_DIR is not the official plugin checkout or is incomplete; "
                f"missing {missing}"
            )
        return root

    def _request(self, path: str, body: dict[str, Any], *, timeout_s: float = 30.0) -> Any:
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            f"{self._base_url()}{path}",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key()}",
                "Content-Type": "application/json",
                "x-sm-source": "agent-memory-bench",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[-1000:]
            raise RuntimeError(f"Supermemory API {error.code} for {path}: {detail}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"Supermemory API unavailable at {self._base_url()}: {error}") from error
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Supermemory API returned non JSON for {path}: {raw[:400]!r}") from error

    def _stored_verification(self, namespace: str, query: str) -> int:
        result = self._request(
            str(self.config["search_path"]),
            {"containerTag": namespace, "q": query[:500]},
            timeout_s=30.0,
        )
        search = result.get("searchResults") if isinstance(result, dict) else None
        results = search.get("results") if isinstance(search, dict) else None
        return len(results) if isinstance(results, list) else 0

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        corpus.verify()
        staged = self.staging_root / namespace / "feed"
        if staged.exists():
            shutil.rmtree(staged)
        rendered = render_corpus(
            [corpus.root / rel for rel in corpus.sessions], staged, root=corpus.root
        )
        start = time.monotonic()
        accepted = 0
        first_query = "project memory"
        for path in sorted(staged.glob("*.md")):
            content = path.read_text(encoding="utf-8")
            if content and first_query == "project memory":
                first_query = content[:500]
            result = self._request(
                str(self.config["write_path"]),
                {
                    "content": content,
                    "containerTag": namespace,
                    "customId": f"{namespace}__{path.stem}",
                    "entityContext": "Shared coding agent memory. Preserve durable project decisions, conventions, and lessons.",
                },
                timeout_s=30.0,
            )
            if not isinstance(result, dict) or not (result.get("id") or result.get("status")):
                raise RuntimeError(
                    f"Supermemory accepted no identifiable document for {path.name}: {result!r}"
                )
            accepted += 1
        verification_hits = 0
        deadline = time.monotonic() + min(60.0, float(self.config["ingest_timeout_s"]))
        while time.monotonic() < deadline and accepted:
            verification_hits = self._stored_verification(namespace, first_query)
            if verification_hits:
                break
            time.sleep(1.0)
        elapsed_ms = (time.monotonic() - start) * 1000.0
        if accepted == 0 or verification_hits == 0:
            raise RuntimeError(
                f"Supermemory write path accepted {accepted} document(s), but search verification "
                f"returned {verification_hits}; refusing to call ingestion successful"
            )
        base_url = self._base_url().lower()
        local = base_url.startswith("http://localhost") or base_url.startswith("http://127.0.0.1")
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            items_stored=accepted,
            wall_time_ms=elapsed_ms,
            local_model=(os.environ.get("SUPERMEMORY_LOCAL_MODEL") or "Supermemory Local configured model")
            if local
            else None,
            notes=(
                "ingested one rendered transcript per request through POST /v3/documents",
                f"{accepted} document(s) accepted; search verification returned {verification_hits} hit(s)",
                "local Supermemory API selected; model compute is local and not represented as hosted tokens"
                if local
                else "remote Supermemory API selected explicitly; ingestion usage is not token metered by AMB",
            ),
        )

    def _prompt_path(self, namespace: str) -> Path:
        return self.staging_root / namespace / "prompt.md"

    def _write_prompt(self, namespace: str) -> Path:
        path = self._prompt_path(namespace)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = self.instruction or self.shared_instruction()
        path.write_text(text.rstrip() + "\n\n" + self.base_prompt_file.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        return path

    def _write_hook_settings(self, config_dir: Path, plugin_root: Path) -> None:
        source = json.loads((plugin_root / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        wrapper = config_dir / "supermemory-hook-wrapper.js"
        node = self._node()
        hooks: dict[str, list[dict[str, Any]]] = {}
        for event, groups in (source.get("hooks") or {}).items():
            rewritten: list[dict[str, Any]] = []
            for group in groups:
                new_group = {key: value for key, value in group.items() if key != "hooks"}
                new_hooks = []
                for hook in group.get("hooks", []):
                    new_hook = dict(hook)
                    target_name = _HOOK_FILES.get(event)
                    if hook.get("type") == "command" and target_name:
                        target = plugin_root / "hooks" / target_name
                        new_hook["command"] = f'"{node}" "{wrapper}" {event} "{target}"'
                    new_hooks.append(new_hook)
                new_group["hooks"] = new_hooks
                rewritten.append(new_group)
            hooks[event] = rewritten
        (config_dir / "settings.json").write_text(
            json.dumps({"hooks": hooks}, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

    def build(self, session_dir: Path, namespace: str, *, prompt_path: Path | None = None) -> ArmSpec:
        session_dir.mkdir(parents=True, exist_ok=True)
        plugin_root = self._plugin_root()
        config_dir = session_dir / "claude-config"
        if config_dir.exists():
            shutil.rmtree(config_dir)
        config_dir.mkdir(parents=True)
        copied_plugin = config_dir / "plugin"
        shutil.copytree(plugin_root, copied_plugin)
        shutil.copy2(_WRAPPER_PATH, config_dir / "supermemory-hook-wrapper.js")
        node = self._node()
        self._write_hook_settings(config_dir, copied_plugin)
        ledger = config_dir / "hook-ledger.jsonl"
        home = config_dir / "home"
        home.mkdir()
        prompt = prompt_path or session_dir / "prompt.md"
        prompt.parent.mkdir(parents=True, exist_ok=True)
        prompt.write_text(
            (self.instruction or self.shared_instruction()).rstrip()
            + "\n\n"
            + self.base_prompt_file.read_text(encoding="utf-8"),
            encoding="utf-8",
            newline="\n",
        )
        return ArmSpec(
            arm=self.name,
            bare=False,
            append_system_prompt_file=prompt,
            config_dir=config_dir,
            config_dir_digest=digest_tree(config_dir),
            env={
                "SUPERMEMORY_API_URL": self._base_url(),
                "SUPERMEMORY_CC_API_KEY": self._api_key(),
                "SUPERMEMORY_REPO_TAG": namespace,
                "SUPERMEMORY_HOOK_LEDGER": str(ledger),
                "SUPERMEMORY_HOOK_HOME": str(home),
                "SUPERMEMORY_ISOLATE_WORKTREES": "true",
                "SUPERMEMORY_NODE": node,
            },
            metadata={
                "memory": "official_plugin_hooks",
                "transport": "lifecycle_hooks",
                "base_url": self._base_url(),
                "plugin_version": self.config["plugin_version"],
                "plugin_commit": self.config["plugin_commit"],
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
        return AdmissionSignal(arm=self.name, required_hooks=_REQUIRED_HOOKS)

    def describe(self) -> dict[str, Any]:
        plugin_root = None
        if self.plugin_dir is not None:
            try:
                plugin_root = str(self._plugin_root())
            except (FileNotFoundError, RuntimeError):
                plugin_root = str(self.plugin_dir)
        return {
            "arm": self.name,
            "memory": "official Supermemory Claude Code plugin hooks",
            "plugin_version": self.config["plugin_version"],
            "plugin_commit": self.config["plugin_commit"],
            "plugin_root": plugin_root,
            "base_url": self._base_url(),
            "required_hooks": list(_REQUIRED_HOOKS),
            "cost_mode": "local by default; no Supermemory subscription required",
        }
