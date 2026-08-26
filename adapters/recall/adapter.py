"""The ``recall`` arm: our product, entering through the same door as every competitor.

recall is installed with ``pip install recall-rag`` and wired through its MCP server, exactly
as its published integration does it. Nothing in this adapter reaches into recall internals,
and that is the point: the benchmark's neutrality claim depends on recall being provably just
another adapter.

Two paid-for environment facts are baked in rather than rediscovered:

- An MCP ``env`` block REPLACES the environment. Without ``APPDATA`` the server dies on
  ``ModuleNotFoundError: anyio``; without ``SystemRoot`` it dies in Winsock; and the server
  inherits the SESSION's working directory, so ``PYTHONPATH`` must be explicit.
- The one-line tool instruction goes at the TOP of the system prompt, ahead of the static
  bundle. Buried after 17k characters of CLAUDE.md it produced a 0% search rate, and then
  the benchmark measures prompt placement, not retrieval.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from harness.adapters.base import ArmSpec, CorpusManifest, IngestReport, MemoryAdapter
from harness.gate import AdmissionSignal
from harness.transcripts import render_corpus

_CONFIG_PATH = Path(__file__).with_name("config.frozen.json")


class RecallAdapter(MemoryAdapter):
    name = "recall"

    def __init__(
        self,
        staging_root: str | Path,
        base_prompt_file: str | Path,
        instruction: str | None = None,
    ) -> None:
        self.staging_root = Path(staging_root)
        self.base_prompt_file = Path(base_prompt_file)
        self.config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        #: Which instruction to put ABOVE the static bundle. None keeps the frozen
        #: one-liner. scripts/pilot.py has always chosen this per run and the pilots
        #: chose the shipped skill; the diagnostic could not, so its recall arm was a
        #: different treatment from the one it was built to explain.
        self.instruction_override = instruction

    def _dsn(self) -> str:
        dsn_env = self.config["dsn_env"]
        dsn = os.environ.get(dsn_env, "")
        if not dsn:
            raise RuntimeError(
                f"the recall arm needs {dsn_env} in the environment; refusing to guess a "
                f"database rather than quietly pointing at somebody else's"
            )
        return dsn

    def _server_env(self, namespace: str) -> dict[str, str]:
        # The env block REPLACES the environment: everything the server needs must be here.
        env = {
            "RECALL_DSN": self._dsn(),
            "RECALL_EMBEDDER": str(self.config["embedder"]),
            "RECALL_TRUST_MODE": str(self.config["trust_mode"]),
            "RECALL_TENANT": namespace,
        }
        for passthrough in ("APPDATA", "SystemRoot", "PYTHONPATH", "PATH"):
            value = os.environ.get(passthrough)
            if value:
                env[passthrough] = value
        return env

    def search_env(self, namespace: str) -> dict[str, str]:
        """Return the frozen environment used by the published search path."""

        return self._server_env(namespace)

    @property
    def prefetch_k(self) -> int:
        return int(self.config.get("prefetch_k", 5))

    def _prompt_path(self, namespace: str) -> Path:
        return self.staging_root / namespace / "prompt.md"

    def _write_prompt(self, namespace: str) -> Path:
        return self._write_prompt_at(self._prompt_path(namespace))

    def _write_prompt_at(self, prompt: Path) -> Path:
        prefix = str(self.config["tool_prefix"])
        instruction = self.instruction_override or str(self.config["instruction"]).format(
            server=self.config["server_name"], tool=f"{prefix}recall_search"
        )
        prompt.parent.mkdir(parents=True, exist_ok=True)
        static = self.base_prompt_file.read_text(encoding="utf-8")
        # newline="\n" because scripts/pilot.py writes its prompts that way and a benchmark that
        # scores line-ending tasks should not vary its own prompts' line endings between runners.
        prompt.write_text(
            instruction.rstrip() + "\n\n" + static.rstrip() + "\n", "utf-8", newline="\n"
        )
        return prompt

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        corpus.verify()
        staged = self.staging_root / namespace / "feed"
        # Fresh render: leftovers from an earlier feed layout must not survive into the
        # index (and the subsequent re-index prunes what is no longer on disk).
        if staged.exists():
            shutil.rmtree(staged)
        count = render_corpus(
            [corpus.root / rel for rel in corpus.sessions], staged, root=corpus.root
        )
        start = time.monotonic()
        # recall's own write path: the published CLI, one tenant per namespace. Re-indexing
        # prunes sources that vanished from disk, so a namespace maps to exactly one feed
        # directory, always.
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "recall.cli",
                "--tenant",
                namespace,
                "index",
                str(staged),
            ],
            env={
                **os.environ,
                "RECALL_DSN": self._dsn(),
                "RECALL_EMBEDDER": str(self.config["embedder"]),
                # A small bound, always: fastembed pads a batch to its longest member, and an
                # unbounded batch is how a 987-memo index run died of a bad allocation.
                "RECALL_INDEX_BATCH_CHUNKS": os.environ.get("RECALL_INDEX_BATCH_CHUNKS", "16"),
            },
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,  # the return code is inspected below, with stderr in the error
        )
        elapsed_ms = (time.monotonic() - start) * 1000.0
        if result.returncode != 0:
            raise RuntimeError(
                f"recall index failed with exit {result.returncode}: {result.stderr[-2000:]}"
            )
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            items_stored=count,
            wall_time_ms=elapsed_ms,
            notes=("indexed via `python -m recall.cli index`, one tenant per namespace",),
        )

    def build(
        self, session_dir: Path, namespace: str, *, prompt_path: Path | None = None
    ) -> ArmSpec:
        session_dir.mkdir(parents=True, exist_ok=True)
        prompt = prompt_path if prompt_path is not None else self._prompt_path(namespace)
        if not prompt.is_file():
            prompt = self._write_prompt_at(prompt)
        # A file path, not inline JSON: the config may carry credentials, and an inline
        # --mcp-config would copy them into every recorded command line.
        mcp_config_path = session_dir / "recall.mcp.json"
        mcp_config = {
            "mcpServers": {
                str(self.config["server_name"]): {
                    "command": str(self.config["command"]),
                    "args": list(self.config["args"]),
                    "env": self._server_env(namespace),
                }
            }
        }
        mcp_config_path.write_text(json.dumps(mcp_config, indent=2), encoding="utf-8")
        prefix = str(self.config["tool_prefix"])
        digest = hashlib.sha256(
            _CONFIG_PATH.read_bytes() + prompt.read_bytes()
        ).hexdigest()
        return ArmSpec(
            arm=self.name,
            bare=True,
            mcp_config=str(mcp_config_path),
            append_system_prompt_file=prompt,
            memory_tool_prefix=prefix,
            extra_allowed_tools=tuple(
                f"{prefix}{tool}" for tool in self.config["allowed_tools"]
            ),
            config_dir_digest=digest,
            metadata={
                "memory": "static+retrieved",
                "transport": "stdio",
                "tenant": namespace,
                "tool_prefix": prefix,
                "prompt_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest(),
            },
        )

    def build_for_task(
        self, session_dir: Path, namespace: str, task_id: str, user_input: str
    ) -> ArmSpec:
        """One prompt per TASK, written into this session's own directory.

        ⛔ Do not route this back through the namespace-keyed cache in :meth:`build`. That cache
        writes only when the file is absent, and a grid holds the namespace constant across tasks,
        so the FIRST task's static bundle is then served to every other task with nothing raising.
        Measured on `diagnostic-001`: all 24 recall sessions received `ts-append-only`'s README
        while every other arm received its own, which quietly turned the recall arm's static half
        into misdirection about a different repository.
        """

        session_dir.mkdir(parents=True, exist_ok=True)
        return self.build(
            session_dir, namespace, prompt_path=self._write_prompt_at(session_dir / "prompt.md")
        )

    def admission_signal(self) -> AdmissionSignal:
        return AdmissionSignal(
            arm=self.name, mcp_tool_prefixes=(str(self.config["tool_prefix"]),)
        )

    def describe(self) -> dict:
        return {
            "arm": self.name,
            "memory": "static+retrieved",
            "config_sha256": hashlib.sha256(_CONFIG_PATH.read_bytes()).hexdigest(),
            "package_pin": self.config.get("package_pin"),
        }
