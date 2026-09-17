"""RE-call graph arm with the released prompt-time hook enabled."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

from adapters.recall_graph_fulltools.adapter import RecallGraphFullToolsProtocolAdapter
from harness.adapters.base import ArmSpec, CorpusManifest, digest_tree, namespace_path
from harness.gate import AdmissionSignal
from harness.transcripts import render_corpus

_HOOK = Path(__file__).with_name("hook.py")
_SNAPSHOT_NAME = "prompt-time-store"


class RecallGraphFullToolsPromptTimeAdapter(RecallGraphFullToolsProtocolAdapter):
    """Official-019 treatment: same graph protocol plus UserPromptSubmit retrieval."""

    name = "recall_graph_fulltools_prompt_time"

    def _snapshot(self, namespace: str) -> Path:
        return namespace_path(self.staging_root, namespace, _SNAPSHOT_NAME)

    def ingest(self, corpus: CorpusManifest, namespace: str):
        report = super().ingest(corpus, namespace)
        corpus.verify()
        snapshot = self._snapshot(namespace)
        if snapshot.exists():
            shutil.rmtree(snapshot)
        snapshot.mkdir(parents=True)
        paths = [corpus.root / relative for relative in corpus.sessions]
        render_corpus(paths, snapshot, root=corpus.root)
        manifest = {
            "corpus_fingerprint": hashlib.sha256(
                json.dumps(dict(sorted(corpus.sessions.items())), separators=(",", ":")).encode()
            ).hexdigest(),
            "files": len(corpus.sessions),
            "snapshot_digest": digest_tree(snapshot),
        }
        (snapshot / "snapshot.manifest.json").write_text(
            json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        self._snapshot_manifest = manifest
        return replace(report, notes=report.notes + ("prompt-time snapshot rendered",))

    def build_for_task(
        self, session_dir: Path, namespace: str, task_id: str, user_input: str
    ) -> ArmSpec:
        base = super().build_for_task(session_dir, namespace, task_id, user_input)
        snapshot = self._snapshot(namespace)
        if not snapshot.is_dir():
            raise RuntimeError(f"prompt-time snapshot is missing: {snapshot}")
        source_root = os.environ.get("AMB_RECALL_HOOK_SOURCE_ROOT", "").strip()
        if not source_root:
            raise RuntimeError(
                "AMB_RECALL_HOOK_SOURCE_ROOT is unset; refusing to run without the released hook source"
            )
        source = Path(source_root)
        if not (source / "recall_hooks" / "prompt_time.py").is_file():
            raise RuntimeError(f"released prompt-time hook is missing under {source}")

        config_dir = session_dir / "claude-config"
        if config_dir.exists():
            shutil.rmtree(config_dir)
        config_dir.mkdir(parents=True)
        # The participant boundary transfers config_dir as an archive; host paths and arbitrary
        # mounts are deliberately unavailable inside the container. Copy the reviewed release
        # and the manifest-bound snapshot into that archive so the hook executes the same bytes
        # in both the controller smoke and the real participant image.
        shutil.copytree(source / "recall_hooks", config_dir / "recall_hooks")
        shutil.copytree(snapshot, config_dir / _SNAPSHOT_NAME)
        wrapper = config_dir / "prompt_time_hook.py"
        shutil.copy2(_HOOK, wrapper)
        # /session is private to the participant container and is not copied back by the
        # isolation boundary. Keep the bounded receipt in the transferred workspace instead.
        trace = session_dir / ".amb-prompt-time-ledger.jsonl"
        command = '"/usr/local/bin/python" "/session/claude-config/prompt_time_hook.py"'
        settings = {
            "hooks": {
                "UserPromptSubmit": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": command,
                                "timeout": 10,
                            }
                        ]
                    }
                ]
            }
        }
        (config_dir / "settings.json").write_text(
            json.dumps(settings, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        (config_dir / "recall-hook.json").write_text(
            json.dumps(
                {
                    "prompt_time": {
                        "enabled": True,
                        "k": 3,
                        "min_chars": 20,
                        "store": f"/session/claude-config/{_SNAPSHOT_NAME}",
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return replace(
            base,
            arm=self.name,
            bare=False,
            config_dir=config_dir,
            config_dir_digest=digest_tree(config_dir),
            env={
                **base.env,
                "AMB_RECALL_PROMPT_TIME_TRACE": "/workspace/.amb-prompt-time-ledger.jsonl",
            },
            metadata={
                **base.metadata,
                "prompt_time_snapshot": str(snapshot),
                "prompt_time_snapshot_manifest": dict(getattr(self, "_snapshot_manifest", {})),
                "prompt_time_trace": str(trace),
                "prompt_time_hook_version": 1,
            },
        )

    def admission_signal(self) -> AdmissionSignal:
        return AdmissionSignal(
            arm=self.name,
            mcp_tool_prefixes=(str(self.config["tool_prefix"]),),
            required_hooks=("UserPromptSubmit",),
            metadata={"prompt_time_hook": True},
        )

    def describe(self) -> dict:
        return {
            **super().describe(),
            "arm": self.name,
            "prompt_time_hook_sha256": hashlib.sha256(_HOOK.read_bytes()).hexdigest(),
            "prompt_time_hook_source": "released recall_hooks.prompt_time",
        }
