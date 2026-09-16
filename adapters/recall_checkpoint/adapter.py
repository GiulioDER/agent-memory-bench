"""Matched placebo and RE-call pre-mutation checkpoint adapters."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path

from adapters.recall_graph_fulltools.adapter import RecallGraphFullToolsProtocolAdapter
from harness.adapters.base import ArmSpec, digest_tree
from harness.gate import AdmissionSignal

_HOOK = Path(__file__).with_name("hook.py")
_HOOK_COMMAND = '"/usr/local/bin/python" "/session/claude-config/checkpoint_hook.py"'


class _CheckpointBase(RecallGraphFullToolsProtocolAdapter):
    checkpoint_mode = ""

    def build_for_task(
        self, session_dir: Path, namespace: str, task_id: str, user_input: str
    ) -> ArmSpec:
        base = super().build_for_task(session_dir, namespace, task_id, user_input)
        config_dir = session_dir / "claude-config"
        config_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_HOOK, config_dir / "checkpoint_hook.py")
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Write|Edit|Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": _HOOK_COMMAND,
                                "timeout": 180,
                            }
                        ],
                    }
                ]
            }
        }
        (config_dir / "settings.json").write_text(
            json.dumps(settings, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        return replace(
            base,
            arm=self.name,
            bare=False,
            config_dir=config_dir,
            config_dir_digest=digest_tree(config_dir),
            env={
                **base.env,
                "AMB_PUBLIC_CHECKPOINT_MODE": self.checkpoint_mode,
                "AMB_PUBLIC_CHECKPOINT_TASK": user_input,
                "AMB_PUBLIC_CHECKPOINT_TASK_ID": task_id,
                "AMB_PUBLIC_CHECKPOINT_SENTINEL": "/tmp/amb-recall-checkpoint.done",
            },
            metadata={
                **base.metadata,
                "checkpoint_mode": self.checkpoint_mode,
                "checkpoint_config_sha256": digest_tree(config_dir),
                "checkpoint_k": 5,
                "checkpoint_version": 1,
            },
        )

    def admission_signal(self) -> AdmissionSignal:
        return AdmissionSignal(
            arm=self.name,
            mcp_tool_prefixes=(str(self.config["tool_prefix"]),),
            metadata={"checkpoint_mode": self.checkpoint_mode},
        )

    def describe(self) -> dict:
        return {
            **super().describe(),
            "arm": self.name,
            "checkpoint_mode": self.checkpoint_mode,
            "checkpoint_version": 1,
            "checkpoint_hook_sha256": hashlib.sha256(_HOOK.read_bytes()).hexdigest(),
        }


class RecallGraphFullToolsCheckpointPlaceboAdapter(_CheckpointBase):
    name = "recall_graph_fulltools_checkpoint_placebo"
    checkpoint_mode = "placebo"


class RecallGraphFullToolsCheckpointAdapter(_CheckpointBase):
    name = "recall_graph_fulltools_checkpoint"
    checkpoint_mode = "treatment"
