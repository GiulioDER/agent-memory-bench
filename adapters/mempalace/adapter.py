"""The ``mempalace`` arm: MemPalace, entering through its own published integration.

MemPalace (``pip install mempalace``) is a local-first store: conversations are mined into
"drawers" inside a "palace" directory, embedded locally with onnxruntime through chromadb, and
retrieved by a hybrid of cosine similarity and BM25. It ships a stdio MCP server, ``mempalace-mcp``,
and that server is how this arm reaches the session. Nothing here reaches into MemPalace internals.

Four environment facts were paid for by measurement on 2026-08-29 against ``mempalace==3.8.0``, and
are enforced here rather than rediscovered:

- **The palace path must be SHORT.** onnxruntime's ``_pybind11_state`` DLL fails to load from a
  deep path on Windows with ``DLL load failed ... The filename or extension is too long``, and
  chromadb catches that ImportError and re-raises it as "The onnxruntime python package is not
  installed" even though it is. Under the harness's own staging root the venv sat about 260
  characters deep and every embed call failed. That is a silent zero for the arm, so
  :meth:`_palace_dir` refuses an over-long path instead of letting it happen.
- **MemPalace parses the corpus JSONL natively.** ``mine --mode convos`` reads the corpus's
  ``{"role", "content", "ts"}`` records directly, so this arm ingests the corpus bytes rather than
  the harness's markdown render. Handing it the render would bypass the conversation extraction
  that is the product.
- **An MCP ``env`` block REPLACES the environment**, the same lesson the recall arm paid for.
  Without ``APPDATA`` the server dies on a missing dependency and without ``SystemRoot`` it dies in
  Winsock, so both are passed through explicitly.
- **MemPalace needs its own virtualenv.** It pulls chromadb, onnxruntime and numpy, and installing
  that beside recall's dependencies risks resolving one of recall's pins away. An arm that quietly
  degrades another arm is worse than an arm that does not run, so the venv is required by
  ``MEMPALACE_VENV`` and never guessed.
"""

from __future__ import annotations

import hashlib
import json
import os
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

_CONFIG_PATH = Path(__file__).with_name("config.frozen.json")

#: Everything the MemPalace server needs that an MCP ``env`` block would otherwise erase.
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


class MemPalaceAdapter(MemoryAdapter):
    name = "mempalace"

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
                f"the mempalace arm needs {var} pointing at the virtualenv MemPalace is "
                f"installed in. It is not guessed: MemPalace pulls chromadb, onnxruntime and "
                f"numpy, and resolving those into recall's environment could move recall's pins, "
                f"which would corrupt a different arm's result rather than this one's."
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
            f"{stem} is not in {venv}; install the pinned MemPalace there with "
            f"`pip install {self.config['package_pin']}`"
        )

    def _passthrough_env(self) -> dict[str, str]:
        # The MCP env block REPLACES the environment, so everything the server needs is named.
        env: dict[str, str] = {}
        for key in _PASSTHROUGH_KEYS:
            value = os.environ.get(key)
            if value:
                env[key] = value
        return env

    # ------------------------------------------------------------------ paths

    def _palace_root(self) -> Path:
        """Where palaces live. Short by requirement, not by luck; see the module docstring."""

        override = os.environ.get(str(self.config["palace_root_env"]), "")
        return Path(override) if override else self.staging_root / "mempalace"

    def _palace_dir(self, namespace: str) -> Path:
        # `ingest` runs `shutil.rmtree` on what this returns.
        palace = namespace_path(self._palace_root(), namespace)
        limit = int(self.config["max_palace_path_chars"])
        absolute = str(palace.absolute())
        if len(absolute) > limit:
            raise RuntimeError(
                f"the mempalace palace path is {len(absolute)} characters, over the {limit} this "
                f"arm allows:\n  {absolute}\n"
                f"MemPalace embeds through onnxruntime, whose DLL fails to load from a deep path "
                f"on Windows with 'The filename or extension is too long'. chromadb reports that "
                f"as 'onnxruntime is not installed', so the arm would score zero for a reason "
                f"nothing in the record would name. Set "
                f"{self.config['palace_root_env']} to a short path such as C:/mpb/palaces."
            )
        return palace

    def _feed_dir(self, namespace: str) -> Path:
        # Validated BEFORE the f-string, which would otherwise smuggle a traversal
        # through as a prefix of a name that looks constructed.
        return self._palace_root() / f"{validate_namespace(namespace)}-feed"

    def _prompt_path(self, namespace: str) -> Path:
        # Same join, same risk: this namespace comes from the same argument as the staging
        # directory's. Found by widening `tests/test_namespace_guard.py`'s scan, which is a
        # tripwire for common shapes and NOT a proof that none is left; see that file.
        return namespace_path(self.staging_root, namespace, "prompt.md")

    # ------------------------------------------------------------------ instruction

    @staticmethod
    def shared_instruction(*, neutral: bool = False) -> str:
        """The shared protocol with this arm's search sentence, plus its own capped appendix."""

        config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        return compose("mempalace", str(config["search_sentence"]), neutral=neutral)

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

    @staticmethod
    def base_palace() -> Path | None:
        """A prebuilt palace to copy, or None to mine every condition from scratch.

        Off unless `MEMPALACE_BASE_PALACE` names a real palace, so the default behaviour is
        byte-for-byte what it was and no run changes shape by accident.
        """
        raw = os.environ.get("MEMPALACE_BASE_PALACE", "").strip()
        if not raw:
            return None
        base = Path(raw).expanduser()
        if not (base / "chroma.sqlite3").is_file():
            raise RuntimeError(
                f"MEMPALACE_BASE_PALACE={raw!r} is not a MemPalace palace: no chroma.sqlite3 in it."
            )
        return base

    @staticmethod
    def filed_document_count(palace: Path) -> int:
        """How many distinct source documents a palace has filed.

        Read from MemPalace's own store rather than counted from a manifest, because the question
        is what the store ACTUALLY holds. Counting the input would re-derive it and could not
        detect a base built from a different corpus, which is the one failure this exists to catch.
        """
        import sqlite3

        with sqlite3.connect(f"file:{palace / 'chroma.sqlite3'}?mode=ro", uri=True) as db:
            row = db.execute(
                "select count(distinct string_value) from embedding_metadata "
                "where key='source_file'"
            ).fetchone()
        return int(row[0]) if row else 0

    @staticmethod
    def check_base_covers_shared(base: Path, reused: int, shared: int, prefix: str) -> None:
        """Refuse a base palace that does not hold EXACTLY the corpus's shared documents.

        ⛔ This is the guard against a silently thinner corpus. If the base was built from a
        different haystack, every condition copied from it loses the documents it lacks, the arm is
        measured on a corpus nobody described, and nothing downstream can tell: ingest reports
        success, the sessions run, the records look ordinary, and the endpoints are computed over
        an index quietly missing evidence.

        Exact equality rather than `>=` on purpose. A base holding MORE than the shared set is also
        wrong: those extra documents are in no condition's corpus yet would be retrievable in all
        five, which is contamination rather than a shortfall and is harder to see.
        """
        if reused != shared:
            raise RuntimeError(
                f"base palace {base} holds {reused} document(s) but this corpus has {shared} "
                f"shared document(s) under {prefix!r}. Rebuild the base from this corpus's "
                f"haystack, or unset MEMPALACE_BASE_PALACE to mine in full."
            )

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        corpus.verify()
        palace = self._palace_dir(namespace)
        feed = self._feed_dir(namespace)
        # A fresh palace AND a fresh feed. `mine` skips a file it has already filed, so a leftover
        # store would make an ingest look successful while filing nothing, and a leftover feed file
        # from an earlier corpus would ride along invisibly into the index.
        for stale in (palace, feed):
            if stale.exists():
                shutil.rmtree(stale)
        feed.mkdir(parents=True, exist_ok=True)

        # A prebuilt base palace holding the documents every condition SHARES, so they are mined
        # once rather than once per condition.
        #
        # Measured 2026-08-31: ingest runs at ~30 documents/min, and the hard corpus is 4,889
        # documents per condition of which 4,704 are the identical haystack. Mining all five from
        # scratch is ~10.5 hours, nearly all of it re-embedding the same synthetic documents.
        # recall avoids this with a content-addressed cache (RE-call #549); MemPalace has none, so
        # the reuse has to happen here.
        #
        # Verified on a 20-document probe BEFORE being relied on, because "faster" is worthless if
        # it measures something else: a copied palace retains its contents, accepts further mining,
        # leaves the original untouched, retrieves newly mined content, and returns identical top-3
        # results to a palace built monolithically from the same documents across three queries.
        #
        # `mine` also skips a file it has already filed (measured: 10 already-filed documents in 3s
        # against 20s to file 10 new ones, reporting "Files skipped (already filed): 10"), which
        # makes the copy safe without filtering but NOT free: skipping 4,704 documents costs about
        # 23 minutes per condition. So the shared documents are left out of the feed instead.
        base = self.base_palace()
        shared_prefix = str(self.config.get("shared_prefix", "synthetic/"))
        if base is not None:
            shutil.rmtree(palace, ignore_errors=True)
            shutil.copytree(base, palace)
            shared = [rel for rel in corpus.sessions if rel.startswith(shared_prefix)]
            self.check_base_covers_shared(
                base, self.filed_document_count(palace), len(shared), shared_prefix
            )

        # The corpus bytes, flattened into one directory. Names mirror their corpus paths so a
        # retrieval result identifies its own source, matching `harness.transcripts.render_corpus`.
        # `mine` dedups on this flattened name, which is what makes a base palace's documents
        # recognisable across conditions.
        for rel in sorted(corpus.sessions):
            if base is not None and rel.startswith(shared_prefix):
                continue
            shutil.copyfile(corpus.root / rel, feed / rel.replace("/", "__"))

        start = time.monotonic()
        result = subprocess.run(
            [
                str(self._venv_bin("python")),
                "-m",
                str(self.config["cli_module"]),
                "--palace",
                str(palace),
                "mine",
                str(feed),
                "--mode",
                str(self.config["ingest_mode"]),
                "--wing",
                str(self.config["wing"]),
                "--agent",
                str(self.config["agent"]),
            ],
            env={**os.environ, **self._passthrough_env()},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=7200,
            check=False,  # the return code is inspected below, with stderr in the error
        )
        elapsed_ms = (time.monotonic() - start) * 1000.0
        if result.returncode != 0:
            raise RuntimeError(
                f"mempalace mine failed with exit {result.returncode}: {result.stderr[-2000:]}"
            )
        drawers = drawers_filed(result.stdout)
        if not drawers:
            raise RuntimeError(
                "mempalace mine reported no drawers filed. An empty store that answers every "
                "search with nothing is indistinguishable from a product that found nothing, and "
                "the second is a result while the first is a wiring fault. Last output:\n"
                + result.stdout[-2000:]
            )
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            items_stored=drawers,
            wall_time_ms=elapsed_ms,
            llm_input_tokens=0,
            llm_output_tokens=0,
            # Not an unmetered zero: MemPalace makes no hosted call, and pays in local compute.
            local_model="chromadb onnx all-MiniLM-L6-v2",
            notes=(
                (
                    f"filed via `mempalace mine --mode {self.config['ingest_mode']}`, one palace "
                    f"per namespace"
                ),
                (
                    "embedded locally through onnxruntime; the zero token counts are a true zero "
                    "paid for in host compute, and wall_time_ms is where that cost shows up"
                ),
            ),
        )

    # ------------------------------------------------------------------ build

    def build(self, session_dir: Path, namespace: str) -> ArmSpec:
        session_dir.mkdir(parents=True, exist_ok=True)
        prompt = self._prompt_path(namespace)
        if not prompt.is_file():
            self._write_prompt(prompt)
        return self._spec(session_dir, self._palace_dir(namespace), prompt)

    def build_for_task(
        self, session_dir: Path, namespace: str, task_id: str, user_input: str
    ) -> ArmSpec:
        session_dir.mkdir(parents=True, exist_ok=True)
        # One prompt per TASK, in this session's own directory. The namespace-keyed prompt is
        # written once, and a grid holds the namespace constant across tasks, so serving that one
        # would hand the first task's README to every task. That defect shipped in
        # `diagnostic-001`, through this same code path in the recall adapter.
        prompt = self._write_prompt(session_dir / "prompt.md")
        return self._spec(session_dir, self._palace_dir(namespace), prompt)

    def _spec(self, session_dir: Path, palace: Path, prompt: Path) -> ArmSpec:
        # A file, not inline JSON: an inline --mcp-config copies the whole block into every
        # recorded command line.
        mcp_config_path = session_dir / "mempalace.mcp.json"
        mcp_config = {
            "mcpServers": {
                str(self.config["server_name"]): {
                    "command": str(self._venv_bin(str(self.config["mcp_entrypoint"]))),
                    "args": ["--palace", str(palace)],
                    "env": self._passthrough_env(),
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
            config_dir_digest=hashlib.sha256(
                _CONFIG_PATH.read_bytes() + prompt.read_bytes()
            ).hexdigest(),
            metadata={
                "memory": "static+retrieved",
                "transport": "stdio",
                "palace": str(palace),
                "wing": str(self.config["wing"]),
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
            "ingest_mode": str(self.config["ingest_mode"]),
            "tools_allowed": len(self.config["allowed_tools"]),
            "config_sha256": hashlib.sha256(_CONFIG_PATH.read_bytes()).hexdigest(),
        }


def drawers_filed(stdout: str) -> int:
    """The drawer count MemPalace prints, or 0 when it printed none.

    Parsed rather than inferred from the exit code: `mine` exits 0 having filed nothing when every
    file was already filed, and an ingest that stored nothing must be a loud failure rather than a
    store that answers every search with silence.
    """

    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if stripped.lower().startswith("drawers filed:"):
            digits = stripped.split(":", 1)[1].strip()
            return int(digits) if digits.isdigit() else 0
    return 0
