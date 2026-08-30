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




def resolve_location(config: dict, key: str) -> str:
    """The value of a host-specific setting, from the environment the frozen config names.

    THE single resolver. `scripts/prepare_recall_corpora.py` carried a second, near-identical one,
    and two copies of a rule drift: adding a sixth location key could leave one refusing and the
    other defaulting. The same argument is made in
    `tests/test_audit_p1_fixes.py::test_both_execution_paths_share_one_allow_list`, about the
    environment allow-list this file's sibling already unified.

    Raises `KeyError` when the config does not name the variable and `LookupError` when the
    variable is unset, so each caller can convert to the refusal its own layer wants: the adapter
    raises `RuntimeError` mid-run, the prepare script exits.
    """

    var = str(config[f"{key}_env"])
    value = os.environ.get(var, "")
    if not value:
        raise LookupError(var)
    return value


def corpus_fingerprint(corpus: CorpusManifest) -> str:
    """A deterministic identity for the corpus CONTENT this run assembled.

    `CorpusManifest` carries `sessions`, a mapping of transcript path to sha256, so hashing its
    canonical form identifies the feed exactly: a changed transcript, an added session or a
    withheld one all move it. The remote build records the same value beside the tenant it built,
    which is what lets `ingest` refuse a tenant serving an older corpus.

    Sorted and separator-pinned because a fingerprint that depends on dict ordering or on
    json.dumps' default spacing is a fingerprint that changes for no reason.
    """

    payload = json.dumps(dict(sorted(corpus.sessions.items())), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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

    def _location(self, key: str) -> str:
        """A host-specific value, read from the environment because it is not published.

        The frozen config names the variable and never holds the value. A host inventory is
        disclosure without a credential attached, this repository's .gitignore says so in its
        first three lines, and every run publishes the config file. Location is also not a
        protocol fact, by the same argument ``notes.transport`` makes about the carrier: which
        machine serves the corpus cannot change what recall returns, so a reader checking the
        experiment loses nothing.

        Refusing beats defaulting. A default here would point a run at whichever host the
        string happened to name, which is how the ``dsn`` key this replaced came to sit in a
        public artifact for a day.
        """

        try:
            return resolve_location(self.config, key)
        except LookupError as exc:
            raise RuntimeError(
                f"the recall arm needs {exc.args[0]} in the environment to know its {key}; "
                f"refusing to guess rather than quietly reaching for somebody else's host. Put "
                f"it in the secrets file scripts/launch_official.sh sources, and see "
                f"adapters/recall/location.example.env for the shape."
            ) from None

    def _remote_label(self) -> str:
        """A name for the machine serving recall, for ERROR MESSAGES only. Never raises.

        `_location` refuses on an unset variable, which is right where the value is about to be
        used and wrong inside a message: an error path that raises while describing its own error
        replaces the diagnosis with a complaint about configuration. These three call sites fire
        under `transport: host`, where there is no ssh alias at all, so naming one would be
        inaccurate as well as fragile.
        """

        transport = str(self.config.get("transport", "local"))
        if transport != "ssh":
            return f"the corpus host ({transport} transport)"
        return os.environ.get(
            str(self.config["ssh_host_env"]), f"<{self.config['ssh_host_env']} unset>"
        )

    def _dsn(self) -> str:
        return self._location('dsn')

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

    def _remote_rows(self, namespace: str) -> int:
        """How many chunk rows the remote tenant actually holds.

        ⛔ Counted with an EXPLICIT `where tenant_id = ...` rather than by setting the
        `recall.tenant_id` GUC and trusting row-level security, which is what `_rows_for_tenant`
        does. Measured 2026-08-29: the benchmark role bypasses RLS (the server warns about exactly
        this at startup), so the policy never applies and the count silently returns EVERY
        tenant's rows. It read 1544 for a tenant holding 683, because 683 + 861 is 1544, and that
        number was printed into a run log as the corpus size.

        Reported as provenance, so it has to be the real number rather than a plausible one.
        """


        sql = (
            "select count(*) from recall_chunks_v1 where tenant_id = "
            f"{self._sql_literal(namespace)}"
        )
        remote = (
            f"psql {shlex.quote(self._dsn())} -tAc {shlex.quote(sql)}"
        )
        result = self._shell(remote, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(
                f"could not count rows for tenant {namespace!r}: {result.stderr.strip()[-300:]}"
            )
        return int(result.stdout.strip() or 0)

    def _shell(self, command: str, *, timeout: float) -> subprocess.CompletedProcess[str]:
        """Run one POSIX shell command ON THE HOST THAT SERVES THE CORPUS.

        Two transports reach the same host and must produce the same answer:

        * ``ssh``  the harness runs elsewhere and the command is carried to VPS2.
        * ``host`` the harness runs ON VPS2, so the command is handed to a local shell.

        The command string is IDENTICAL either way, which is the point: the verification, the row
        count and the server launch are then provably the same work, and moving the harness onto
        the serving host cannot quietly change what is checked. It also removes the co-location
        asymmetry between the two products, since under ``host`` neither pays a network hop.
        """

        import subprocess

        if str(self.config.get("transport", "local")) == "host":
            argv = ["/bin/bash", "-lc", command]
        else:
            argv = ["ssh", "-o", "BatchMode=yes", self._location('ssh_host'), command]
        return subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, check=False
        )

    @staticmethod
    def _sql_literal(value: str) -> str:
        """A single-quoted SQL literal. Tenant names are ours, but this is a query built by
        concatenation and an unescaped quote would be a syntax error at best."""

        escaped = value.replace("'", "''")
        return f"'{escaped}'"


    def _verify_remote_generation(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        """Confirm the remote tenant serves a promoted, certified generation of THIS corpus.

        The corpus is built and calibrated by `scripts/prepare_recall_corpora.py`, deliberately as
        a separate step rather than here. Two reasons, and the second is the one that matters:

        1. A generation build embeds the whole corpus and a calibration fits a threshold to it.
           Doing that inside a run means a remote failure kills the run mid-flight, which is how
           `abstention-002` lost 86 sessions to an unrelated interruption.
        2. The corpus must be FROZEN across arms and cells. A step that can build is a step that
           can silently rebuild, and a rebuilt corpus mid-run is a different experiment.

        So this asserts rather than acts. What it actually checks, which is less than this
        docstring used to claim:

        - that an ACTIVE generation exists for the tenant, and
        - that the corpus fingerprint stamped beside it equals the manifest this run is about to
          serve. A tenant carrying last week's corpus answers every query happily.

        ⚠️ **It does NOT check that the calibration is CERTIFIED**, although this docstring said
        it did until 2026-08-30. Certification is enforced upstream instead, by recall's own
        `promote()` when `serving_environment == "production"`, which is what
        `scripts/prepare_recall_corpora.py` sets. That covers a generation promoted through this
        pipeline and nothing else: recall's `rollback` does not refuse on certification grounds,
        so a generation made active by hand can be uncertified and this check will not see it.

        ⚠️ **The stamp is not bound to a generation id either.** It is a bare fingerprint written
        beside the tenant, so promoting a different generation afterwards leaves the stamp
        matching and this verification passing. Filed as AMB-009.

        Both gaps are recorded rather than fixed because a false promise in a docstring is the
        defect this project retired from `harness/stats.py` on the same day, and stating the
        weaker truth is worth more than a claim nobody has tested.
        """


        expected = corpus_fingerprint(corpus)
        remote = (
            f"cd {shlex.quote(self._location('remote_root'))} && "
            f"set -a && . {shlex.quote(self._location('remote_env_file'))} && set +a && "
            f"export RECALL_DSN={shlex.quote(self._dsn())} "
            f"RECALL_EMBEDDER={shlex.quote(str(self.config['embedder']))} "
            f"RECALL_ENV={shlex.quote(str(self.config['environment']))} && "
            f"{shlex.quote(self._location('remote_python'))} -m recall.cli "
            f"--tenant {shlex.quote(namespace)} generation list"
        )
        result = self._shell(remote, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(
                f"cannot list generations for tenant {namespace!r} on "
                f"{self._remote_label()}: {result.stderr.strip()[-500:]}"
            )
        active = [line for line in result.stdout.splitlines() if " active " in f" {line} "]
        if not active:
            raise RuntimeError(
                f"tenant {namespace!r} has no ACTIVE generation on {self._remote_label()}. "
                f"Run scripts/prepare_recall_corpora.py before the suite: a tenant with no active "
                f"generation raises NoActiveGeneration under production rather than refusing "
                f"politely, and one carrying an older corpus would answer every query happily."
            )
        line = active[0]

        # The corpus the remote build actually used, recorded beside the tenant by
        # `scripts/prepare_recall_corpora.py`. Compared rather than trusted: a tenant carrying an
        # older corpus answers every query happily and nothing in a session record would say so.
        stamp = self._shell(
            f"cat {shlex.quote(self._location('remote_root'))}/{shlex.quote(namespace)}.corpus",
            timeout=120,
        )
        recorded = stamp.stdout.strip()
        if stamp.returncode != 0 or not recorded:
            raise RuntimeError(
                f"tenant {namespace!r} has an active generation but no corpus stamp on "
                f"{self._remote_label()}, so nothing proves WHICH corpus it was built from. "
                f"Rebuild with scripts/prepare_recall_corpora.py, which writes the stamp."
            )
        if recorded != expected:
            raise RuntimeError(
                f"tenant {namespace!r} serves a generation built from a DIFFERENT corpus than this "
                f"run assembled.\n  active:   {line.strip()}\n  recorded: {recorded}\n"
                f"  expected: {expected}\nRebuild with scripts/prepare_recall_corpora.py."
            )
        stored = self._remote_rows(namespace)
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            items_stored=stored,
            wall_time_ms=0.0,
            notes=(
                f"verified remote generation {line.strip()[:80]}",
                f"corpus fingerprint {expected}",
            ),
        )


    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        corpus.verify()
        if str(self.config.get("transport", "local")) in ("ssh", "host"):
            return self._verify_remote_generation(corpus, namespace)
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
            "RECALL_DSN": self._dsn(),
            "RECALL_EMBEDDER": str(self.config["embedder"]),
            "RECALL_TENANT": namespace,
            "RECALL_ENV": str(self.config["environment"]),
        }
        assignments = " ".join(f"{k}={shlex.quote(v)}" for k, v in exports.items())
        return (
            f"cd {shlex.quote(self._location('remote_root'))} && "
            f"set -a && . {shlex.quote(self._location('remote_env_file'))} && set +a && "
            f"export {assignments} && unset RECALL_TRUST_MODE && "
            f"exec {shlex.quote(self._location('remote_python'))} -m recall_mcp.server"
        )

    def _remote_server_argv(self, namespace: str) -> tuple[str, list[str]]:
        """`(command, args)` for an SSH-transported server."""

        if str(self.config.get("transport", "local")) == "host":
            # Same command string, handed to a shell instead of to ssh. `-l` so the login profile
            # is read, which is where the serving host's own environment lives.
            return "/bin/bash", ["-lc", self._remote_command(namespace)]
        return "ssh", [
            "-o",
            "BatchMode=yes",
            "-o",
            "ServerAliveInterval=30",
            self._location('ssh_host'),
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
        if str(self.config.get("transport", "local")) in ("ssh", "host"):
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
