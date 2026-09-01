"""The ``cognee`` arm: cognee, entering through its own published integration.

cognee (``pip install "cognee[fastembed]"``) is a self-hosted memory engine: documents are chunked,
their entities and relations extracted by an LLM into a knowledge graph, and retrieved by a search
over that graph plus a vector index. It ships a stdio MCP server, ``cognee-mcp``, whose memory API
is three tools (``remember``, ``recall``, ``forget``), and that server is how this arm reaches the
session. Nothing here reaches into cognee internals; ingest goes through the published Python API,
in cognee's own environment, via `ingest_driver.py`.

## Why this arm exists, and what makes it different from `mempalace`

`mempalace` embeds locally, so its ingest cost is host compute and shows up in ``wall_time_ms``.
cognee **extracts with a hosted LLM**, so its ingest has a bill, and the bill scales with the
corpus rather than with the grid: 4,889 documents per condition on the hard corpus, not 24 sessions
per arm. An arm whose cost is discovered by paying it is the failure this benchmark already made
once (`mempalace`'s ~10.5 hour projected ingest, preregistration 021 Amendment 2).

cognee is wired here because it is the one candidate that can quote the bill first. Its own
``cognify(dry_run=True)`` returns chunk counts, input and output tokens and an estimated cost
**without making an LLM call**, and `ingest_driver.py` refuses above the ceiling in
``config.frozen.json`` before anything is spent. The estimate is a bound to decide by rather than
measured spend, and `ingest` says so in the report it returns instead of publishing it as a
metered number.

## Four environment facts, enforced here rather than rediscovered

- **cognee overrides your environment from a file on disk.** ``cognee/__init__.py`` calls
  ``dotenv.load_dotenv(override=True)`` at import, and ``override=True`` means such a file **beats**
  the frozen configuration this adapter passes in, silently redirecting the LLM, the embedder and
  the databases while the run record still names the frozen config.

  ⚠️ Where it looks was corrected on 2026-09-01, the same day this file was written, by reading
  ``dotenv.find_dotenv`` instead of trusting the obvious reading. It does **not** walk up from the
  working directory in the normal case: it walks up from the directory of the **calling frame's
  file**, which is cognee's own package directory inside the venv, and falls back to the working
  directory only in a REPL, under a debugger, or when frozen. So the file that would capture this
  arm is one beside or above the **venv** (``C:/cgn/.env``), and the working directory matters only
  under a debugger. :meth:`refuse_stray_dotenv` scans both, and the driver checks again from
  ``sys.prefix`` at the point of import.
- **A half-configured cognee bills OpenAI.** ``EmbeddingConfig`` defaults to
  ``openai/text-embedding-3-large`` and, per the vendor's own ``.env`` template, an unset embedding
  key falls back to ``LLM_API_KEY``. Configuring only the LLM therefore ships every embedding to a
  provider nobody chose. All four of provider, model, embedding provider and embedding model are
  set from the frozen config, always, and the driver refuses if any is missing.
- **The store path must be SHORT.** ``fastembed`` embeds through onnxruntime, whose
  ``_pybind11_state`` DLL fails to load from a deep path on Windows with "The filename or extension
  is too long", and the error is re-raised downstream as a missing package. That trap cost the
  `mempalace` arm two debugging detours; :meth:`_store_dir` refuses an over-long path instead.
- **An MCP ``env`` block REPLACES the environment**, the lesson the `recall` and `mempalace` arms
  both paid for. Everything the server needs is named explicitly.

## What is deliberately not here

No :meth:`~harness.adapters.base.MemoryAdapter.search`. cognee's ``recall`` answers from a graph
whose nodes are extracted entities rather than corpus documents, so mapping a hit back to the
corpus-relative transcript path that makes a ranked list joinable against a task's gold sessions is
not a wiring detail but a question about the product. Inheriting the base class's refusal is
correct: an arm that cannot answer ranked retrieval must raise, because an empty list means "found
nothing" and conflating the two would score an unimplemented arm as a product that retrieves badly.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

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
from harness.transcripts import render_corpus

_CONFIG_PATH = Path(__file__).with_name("config.frozen.json")
_DRIVER_PATH = Path(__file__).with_name("ingest_driver.py")

#: Everything the cognee server needs that an MCP ``env`` block would otherwise erase.
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

#: The marker `ingest_driver.py` prints its one machine-readable line behind.
_REPORT_MARKER = "COGNEE_JSON "


class CogneeAdapter(MemoryAdapter):
    name = "cognee"

    def __init__(
        self,
        staging_root: str | Path,
        base_prompt_file: str | Path,
        instruction: str | None = None,
    ) -> None:
        self.staging_root = Path(staging_root)
        self.base_prompt_file = Path(base_prompt_file)
        self.config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        #: None falls back to the shared protocol with this arm's search sentence, which is what
        #: every memory arm gets. ``scripts/pilot.py`` passes the composed text explicitly.
        self.instruction_override = instruction

    # ------------------------------------------------------------------ environment

    def _venv(self) -> Path:
        var = str(self.config["venv_env"])
        raw = os.environ.get(var, "")
        if not raw:
            raise RuntimeError(
                f"the cognee arm needs {var} pointing at the virtualenv cognee is installed in. "
                f"It is not guessed: cognee pulls litellm, lancedb, kuzu and (through the "
                f"fastembed extra) onnxruntime, and resolving those into another arm's "
                f"environment could move that arm's pins, which would corrupt a different arm's "
                f"result rather than this one's. Install "
                f"`{self.config['package_pin']}` and `{self.config['mcp_package_pin']}` there."
            )
        venv = Path(raw)
        if not venv.is_dir():
            raise RuntimeError(f"{var}={raw!r} is not a directory")
        return venv

    def _venv_bin(self, stem: str) -> Path:
        """Resolve an executable inside the venv, on either layout."""

        venv = self._venv()
        for sub, suffix in (("Scripts", ".exe"), ("Scripts", ""), ("bin", "")):
            candidate = venv / sub / f"{stem}{suffix}"
            if candidate.is_file():
                return candidate
        raise RuntimeError(
            f"{stem} is not in {venv}; install the pinned cognee there with "
            f"`pip install \"{self.config['package_pin']}\" {self.config['mcp_package_pin']}`"
        )

    def _passthrough_env(self) -> dict[str, str]:
        # The MCP env block REPLACES the environment, so everything the server needs is named.
        env: dict[str, str] = {}
        for key in _PASSTHROUGH_KEYS:
            value = os.environ.get(key)
            if value:
                env[key] = value
        return env

    def _llm_api_key(self) -> str:
        var = str(self.config["llm"]["api_key_env"])
        key = os.environ.get(var, "")
        if not key:
            raise RuntimeError(
                f"the cognee arm extracts with a hosted LLM and {var} is not set. The key is read "
                f"from the environment and never written into config.frozen.json, which is a "
                f"published, vendor-reviewed file."
            )
        return key

    def cognee_env(self, namespace: str) -> dict[str, str]:
        """The complete cognee configuration for one namespace, as environment variables.

        Every setting that decides what is billed and where it is stored is named here. cognee
        reads all of them from the environment, so this dictionary IS the arm's configuration and
        is what the frozen config hashes over.
        """

        store = self._store_dir(namespace)
        llm = self.config["llm"]
        embedding = self.config["embedding"]
        env: dict[str, str] = {
            **self._passthrough_env(),
            **{str(k): str(v) for k, v in self.config["server_env"].items()},
            **{str(k): str(v) for k, v in self.config["databases"].items()},
            "LLM_PROVIDER": str(llm["provider"]),
            "LLM_MODEL": str(llm["model"]),
            "LLM_ENDPOINT": str(llm["endpoint"]),
            "LLM_API_KEY": self._llm_api_key(),
            "EMBEDDING_PROVIDER": str(embedding["provider"]),
            "EMBEDDING_MODEL": str(embedding["model"]),
            "EMBEDDING_DIMENSIONS": str(embedding["dimensions"]),
            "DATA_ROOT_DIRECTORY": str(store / "data"),
            "SYSTEM_ROOT_DIRECTORY": str(store / "system"),
        }
        return env

    # ------------------------------------------------------------------ paths

    def _store_root(self) -> Path:
        """Where stores live. Short by requirement, not by luck; see the module docstring."""

        override = os.environ.get(str(self.config["store_root_env"]), "")
        return Path(override) if override else self.staging_root / "cognee"

    def _store_dir(self, namespace: str) -> Path:
        # `ingest` runs `shutil.rmtree` on what this returns.
        store = namespace_path(self._store_root(), namespace)
        limit = int(self.config["max_store_path_chars"])
        absolute = str(store.absolute())
        if len(absolute) > limit:
            raise RuntimeError(
                f"the cognee store path is {len(absolute)} characters, over the {limit} this arm "
                f"allows:\n  {absolute}\n"
                f"cognee embeds through fastembed, which embeds through onnxruntime, whose DLL "
                f"fails to load from a deep path on Windows with 'The filename or extension is "
                f"too long'. The arm would score zero for a reason nothing in the record would "
                f"name. Set {self.config['store_root_env']} to a short path such as C:/cgn."
            )
        return store

    def _feed_dir(self, namespace: str) -> Path:
        # Validated BEFORE the f-string, which would otherwise smuggle a traversal through as a
        # prefix of a name that looks constructed.
        return self._store_root() / f"{validate_namespace(namespace)}-feed"

    def _prompt_path(self, namespace: str) -> Path:
        return namespace_path(self.staging_root, namespace, "prompt.md")

    def dataset(self, namespace: str) -> str:
        """This namespace's cognee dataset name.

        A dataset is cognee's own unit of isolation and reaches SQL identifiers, so the namespace
        is validated and then reduced to word characters rather than passed through.
        """

        safe = re.sub(r"[^A-Za-z0-9]", "_", validate_namespace(namespace))
        return f"{self.config['dataset_prefix']}{safe}"

    def refuse_stray_dotenv(self, *directories: Path) -> None:
        """Refuse a ``.env`` at or above any directory cognee would search from.

        ⛔ Not defensive coding. ``cognee/__init__.py`` runs ``dotenv.load_dotenv(override=True)``
        at import, and ``override=True`` means the file WINS against the environment this adapter
        passes in. A developer's ``.env`` two directories up would silently repoint the model, the
        embedder and the databases, and every artifact would still record the frozen config as the
        one in force. That is the config-said-one-thing-and-the-run-did-another failure this
        repository has paid for more than once, so it is refused rather than warned about.

        Pass every root `dotenv.find_dotenv` could start from: the **venv**, which is the one that
        applies in a normal run because the search begins at the importing module's own directory,
        and the working directory, which applies under a REPL, a debugger or a frozen interpreter.
        """

        for start in directories:
            for candidate in (start, *start.parents):
                dotenv = candidate / ".env"
                if dotenv.is_file():
                    raise RuntimeError(
                        f"{dotenv} exists, and cognee loads it with override=True at import, so "
                        f"it would beat this arm's frozen configuration without changing what the "
                        f"run record claims. Move it, or point {self.config['venv_env']} and "
                        f"{self.config['store_root_env']} somewhere without one."
                    )

    # ------------------------------------------------------------------ instruction

    @staticmethod
    def shared_instruction(*, neutral: bool = False, variant: str = "protocol") -> str:
        """The shared protocol with this arm's search sentence, plus its own capped appendix.

        ``variant`` selects WHICH shared protocol, never a per-arm one, so every memory arm in a
        run carries the same text and a protocol variant stays a fair comparison.
        """

        config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        return compose(
            "cognee", str(config["search_sentence"]), neutral=neutral, variant=variant
        )

    def _instruction_text(self) -> str:
        if self.instruction_override is not None:
            return self.instruction_override
        return self.shared_instruction()

    def _write_prompt(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        static = self.base_prompt_file.read_text(encoding="utf-8")
        path.write_text(
            self._instruction_text().rstrip() + "\n\n" + static.rstrip() + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return path

    # ------------------------------------------------------------------ ingest

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        corpus.verify()
        store = self._store_dir(namespace)
        feed = self._feed_dir(namespace)
        # A fresh store AND a fresh feed. cognee skips documents it has already processed
        # (incremental loading), so a leftover store would make an ingest look successful while
        # extracting nothing, and a leftover rendered document from an earlier corpus would ride
        # along invisibly into the graph.
        for stale in (store, feed):
            if stale.exists():
                shutil.rmtree(stale)
        store.mkdir(parents=True, exist_ok=True)
        self.refuse_stray_dotenv(self._venv(), store)

        # Rendered, not raw. cognee has no conversation-transcript mode: it classifies by file
        # extension and `.jsonl` is not a document type it parses, so handing it the corpus bytes
        # would ingest them as opaque text at best. `render_corpus` is the same renderer the
        # `fs_grep` control uses, and `root=` makes each name mirror its corpus path so a
        # retrieval result identifies its own source.
        rendered = render_corpus(
            [corpus.root / rel for rel in sorted(corpus.sessions)], feed, root=corpus.root
        )

        start = time.monotonic()
        result = subprocess.run(
            [
                str(self._venv_bin("python")),
                str(_DRIVER_PATH),
                str(feed),
                self.dataset(namespace),
                str(float(self.config["ingest_cost_ceiling_usd"])),
            ],
            cwd=str(store),
            env=self.cognee_env(namespace),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=36000,
            check=False,  # the return code is inspected below, with stderr in the error
        )
        elapsed_ms = (time.monotonic() - start) * 1000.0
        report = parse_driver_report(result.stdout)
        if result.returncode != 0:
            # A refusal on the ceiling is not a failure to fix, it is the guard doing its job, and
            # the number it refused on is what the operator needs to decide with. The driver
            # prints its report BEFORE exiting non-zero for exactly this.
            refused = " (refused on the cost ceiling before spending anything)" if report.get(
                "refused"
            ) else ""
            raise RuntimeError(
                f"cognee ingest failed with exit {result.returncode}{refused}: "
                f"{result.stderr[-2000:]}"
            )
        if not report:
            raise RuntimeError(
                "the cognee ingest driver printed no report line. Last output:\n"
                + result.stdout[-2000:]
            )
        if not report.get("probe_hits"):
            raise RuntimeError(
                "cognee ingested the corpus and then retrieved nothing for a query taken from "
                "the corpus itself. A store that answers every search with silence is "
                "indistinguishable from a product that found nothing, and the second is a result "
                f"while the first is a wiring fault. Report: {report}"
            )

        estimate = dict(report.get("estimate") or {})
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            items_stored=int(estimate.get("chunks") or 0),
            wall_time_ms=elapsed_ms,
            llm_input_tokens=int(estimate.get("input_tokens") or 0),
            llm_output_tokens=int(estimate.get("output_tokens") or 0),
            # Embedding is local and unbilled; extraction is not. Naming both is the only honest
            # way to read the token counts above, which cover extraction alone.
            local_model=f"fastembed {self.config['embedding']['model']}",
            notes=(
                (
                    f"rendered {rendered} corpus documents and ingested them with "
                    f"`cognee.add` + `cognee.cognify` into dataset "
                    f"{self.dataset(namespace)!r}, one store per namespace"
                ),
                (
                    "⚠️ the token counts are cognee's own `cognify --dry-run` ESTIMATE, not "
                    "provider-billed usage: they cover the two LLM-heavy stages, exclude "
                    "embeddings, and are an upper bound on a re-run. Treat them as the bound the "
                    "run was authorised against, not as measured spend"
                ),
                (
                    f"estimated cost ${float(estimate.get('estimated_cost_usd') or 0.0):.4f} "
                    f"against the ${float(self.config['ingest_cost_ceiling_usd']):.2f} ceiling "
                    f"in config.frozen.json, on model {estimate.get('model')!r}"
                ),
                (
                    "embeddings are computed locally by fastembed and cost no tokens; that half "
                    "of the ingest is paid in host compute and shows up in wall_time_ms"
                ),
            ),
        )

    # ------------------------------------------------------------------ build

    def build(self, session_dir: Path, namespace: str) -> ArmSpec:
        session_dir.mkdir(parents=True, exist_ok=True)
        prompt = self._prompt_path(namespace)
        if not prompt.is_file():
            self._write_prompt(prompt)
        return self._spec(session_dir, namespace, prompt)

    def build_for_task(
        self, session_dir: Path, namespace: str, task_id: str, user_input: str
    ) -> ArmSpec:
        session_dir.mkdir(parents=True, exist_ok=True)
        # One prompt per TASK, in this session's own directory. The namespace-keyed prompt is
        # written once, and a grid holds the namespace constant across tasks, so serving that one
        # would hand the first task's README to every task. That defect shipped in
        # `diagnostic-001`, through this same code path in the recall adapter.
        prompt = self._write_prompt(session_dir / "prompt.md")
        return self._spec(session_dir, namespace, prompt)

    def _spec(self, session_dir: Path, namespace: str, prompt: Path) -> ArmSpec:
        # A file, not inline JSON: an inline --mcp-config copies the whole block into every
        # recorded command line, and this block carries an API key.
        mcp_config_path = session_dir / "cognee.mcp.json"
        mcp_config = {
            "mcpServers": {
                str(self.config["server_name"]): {
                    "command": str(self._venv_bin(str(self.config["mcp_entrypoint"]))),
                    "args": ["--transport", "stdio"],
                    "env": self.cognee_env(namespace),
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
            extra_allowed_tools=tuple(
                f"{prefix}{tool}" for tool in self.config["allowed_tools"]
            ),
            # The driver's bytes are in the digest because the driver decides what the ingest
            # spends and in what order; a change to it is a change to the reviewed configuration.
            config_dir_digest=hashlib.sha256(
                _CONFIG_PATH.read_bytes() + _DRIVER_PATH.read_bytes() + prompt.read_bytes()
            ).hexdigest(),
            metadata={
                "memory": "static+retrieved",
                "transport": "stdio",
                "store": str(self._store_dir(namespace)),
                "dataset": self.dataset(namespace),
                "tool_prefix": prefix,
                "prompt_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest(),
            },
        )

    # ------------------------------------------------------------------ gate, description

    def admission_signal(self) -> AdmissionSignal:
        return AdmissionSignal(
            arm=self.name, mcp_tool_prefixes=(str(self.config["tool_prefix"]),)
        )

    def describe(self) -> dict:
        return {
            "arm": self.name,
            "memory": "static+retrieved",
            "product": str(self.config["product"]),
            "package_pin": str(self.config["package_pin"]),
            "mcp_package_pin": str(self.config["mcp_package_pin"]),
            "extraction_model": str(self.config["llm"]["model"]),
            "embedding_model": str(self.config["embedding"]["model"]),
            "ingest_cost_ceiling_usd": float(self.config["ingest_cost_ceiling_usd"]),
            "tools_allowed": len(self.config["allowed_tools"]),
            "config_sha256": hashlib.sha256(_CONFIG_PATH.read_bytes()).hexdigest(),
            "driver_sha256": hashlib.sha256(_DRIVER_PATH.read_bytes()).hexdigest(),
        }


def parse_driver_report(stdout: str) -> dict:
    """The one JSON line `ingest_driver.py` prints, or ``{}`` when it printed none.

    Parsed rather than inferred from the exit code, and read from the LAST marker line: cognee
    logs to stdout as well, so the report has to be found rather than assumed to be the whole
    output.
    """

    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if stripped.startswith(_REPORT_MARKER):
            try:
                return json.loads(stripped[len(_REPORT_MARKER):])
            except json.JSONDecodeError:
                return {}
    return {}
