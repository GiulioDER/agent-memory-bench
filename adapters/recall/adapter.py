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
import shlex
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
        embedder = str(self.config["embedder"])
        # recall names a hosted embedder `provider:model` and a local one by bare name. The
        # distinction decides how this arm's ingest cost is REPORTED: a local run spends no hosted
        # tokens and real host compute, and a cost table that prints only the zero would read as
        # "this product ingests for free" beside a competitor's extraction bill.
        hosted = ":" in embedder
        stored = self._rows_for_tenant(namespace)
        if stored == 0:
            raise RuntimeError(
                f"recall index exited 0 for tenant {namespace!r} and the tenant holds no rows. "
                f"{count} file(s) were rendered, which is what this report used to publish as "
                f"`items_stored`: an ingest that writes nothing would have looked successful, and "
                f"the arm would then have scored zero as though the PRODUCT had failed."
            )
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            # Rows actually in the tenant, not files rendered. See _rows_for_tenant.
            items_stored=stored,
            wall_time_ms=elapsed_ms,
            local_model=None if hosted else embedder,
            notes=(
                "indexed via `python -m recall.cli index`, one tenant per namespace",
                f"{count} file(s) rendered, {stored} row(s) stored",
            ),
        )

    def _rows_for_tenant(self, namespace: str) -> int:
        """How many chunk rows this tenant actually holds, verified after indexing.

        `render_corpus` returns how many files it WROTE, and reporting that as `items_stored` says
        nothing about whether the index has anything in it. The distinction matters most for an
        arm that is not ours: a competitor whose ingest silently failed would be published at zero
        as though their product could not answer, rather than as a wiring failure the gate should
        have caught.

        ⚠️ `recall.tenant_id` MUST be set. These tables carry row-level security, so a plain
        `select count(*)` returns 0 for every tenant and reads exactly like an empty index. That
        mistake has been made on this project before, on a healthy corpus that was then rebuilt
        for no reason.
        """

        try:
            import psycopg
        except ImportError:  # pragma: no cover - environment without the driver
            return -1
        with psycopg.connect(self._dsn()) as connection, connection.cursor() as cursor:
            # `set_config`, NOT `SET LOCAL ... = %s`. Postgres does not accept a parameter
            # placeholder in a SET statement, and the first version of this raised
            # `syntax error at or near "$1"` AFTER a twenty-minute embed had already succeeded.
            # set_config is an ordinary function, so the tenant name binds as a parameter and is
            # never interpolated into SQL text.
            cursor.execute("SELECT set_config('recall.tenant_id', %s, true)", (namespace,))
            cursor.execute("SELECT count(*) FROM chunks")
            row = cursor.fetchone()
        return int(row[0]) if row else 0

    def _remote_command(self, namespace: str) -> str:
        """The single shell command SSH runs on the remote host.

        ⛔ The environment is INLINED here rather than passed through the MCP config's `env` block,
        because SSH forwards no arbitrary environment: an `env` block would be applied to the local
        `ssh` process and never reach the server. This is the shape recall's own production servers
        are deployed with.

        `RECALL_TRUST_MODE` is UNSET rather than set to a value. Strict is the shipped default and
        is expressed by absence; setting it to any string is how a corpus ends up served relaxed
        while the config claims otherwise.
        """

        exports = {
            "RECALL_DSN": str(self.config["dsn"]),
            "RECALL_EMBEDDER": str(self.config["embedder"]),
            "RECALL_TENANT": namespace,
            "RECALL_ENV": str(self.config["environment"]),
        }
        assignments = " ".join(f"{k}={shlex.quote(v)}" for k, v in exports.items())
        return (
            f"cd {shlex.quote(str(self.config['remote_root']))} && "
            f"set -a && . {shlex.quote(str(self.config['remote_env_file']))} && set +a && "
            f"export {assignments} && unset RECALL_TRUST_MODE && "
            f"exec {shlex.quote(str(self.config['remote_python']))} -m recall_mcp.server"
        )

    def _remote_server_argv(self, namespace: str) -> tuple[str, list[str]]:
        """`(command, args)` for an SSH-transported server."""

        return "ssh", [
            "-o",
            "BatchMode=yes",
            "-o",
            "ServerAliveInterval=30",
            str(self.config["ssh_host"]),
            self._remote_command(namespace),
        ]


    def _server_command(self) -> str:
        """The interpreter that starts the MCP server, resolved rather than passed through.

        `config.frozen.json` declares ``"command": "python"``. Taken literally that is a PATH
        lookup performed inside Claude Code's own subprocess, so the server runs whichever
        interpreter that environment happens to resolve, while :meth:`ingest` runs
        ``sys.executable``. The two are the same only by luck.

        ⛔ They stopped being the same the moment this benchmark pinned its recall version, and the
        failure was silent in the direction that matters. Measured 2026-08-29, mid-run: the ingest
        wrote through the pinned 0.10.0, which applied schema migration 0015, and the server came
        up on a PATH python holding an editable install of a development worktree, which refused
        the corpus outright::

            SchemaTooNew: table 'chunks' has unknown migration(s) ['0015']; upgrade the application

        A dead stdio server is not an error in the transcript. It is a session with no memory
        tools, which records as ``memory_call_count = 0`` and reads exactly like an agent that
        chose not to search. Fourteen sessions ran that way before the search rate gave it away.

        So the declaration is honoured as INTENT, "start the server with a Python interpreter", and
        resolved to the interpreter the harness itself is running under, which is the one the pin
        governs. A config naming a real executable is passed through untouched, because that is a
        deliberate choice about which binary to run rather than a placeholder.
        """

        command = str(self.config["command"])
        return sys.executable if command in ("python", "python3") else command


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
        if str(self.config.get("transport", "local")) == "ssh":
            command, args = self._remote_server_argv(namespace)
            # Only what the LOCAL ssh client needs. The server's own environment travels inside
            # the remote command, because ssh forwards none of this.
            env = {
                key: value
                for key in ("PATH", "SystemRoot", "USERPROFILE", "HOME", "APPDATA")
                if (value := os.environ.get(key))
            }
        else:
            command, args = self._server_command(), list(self.config["args"])
            env = self._server_env(namespace)
        mcp_config = {
            "mcpServers": {
                str(self.config["server_name"]): {
                    "command": command,
                    "args": args,
                    "env": env,
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
