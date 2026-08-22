"""The adapter contract: one memory product, one class, one frozen config.

An A/B whose arms were assembled by hand in several places is an A/B with an unknown number of
differences (the ancestor harness's ``arms.py`` said this first). Here every arm is produced by
one :class:`MemoryAdapter`, and the diff between two arms is the diff between two adapters and
nothing else. The harness controls what must be identical across arms: model, CLAUDE.md content,
tool allow/deny lists, timeout, sandbox restore, prompt. The adapter controls only how its
product is wired in, and that wiring is:

- **frozen**: the adapter reads ``adapters/<name>/config.frozen.json``; the hash of that file
  plus the generated config-dir tree is recorded into every session record;
- **vendor-reviewed**: the same file is what a vendor is invited to review before the run,
  documented in ``adapters/<name>/VENDOR_REVIEW.md``;
- **official**: each product enters through its own published Claude Code integration (plugin,
  MCP server, or lifecycle hooks), not a harness-imposed wrapper.

Adapters must be additive: every memory arm receives the same CLAUDE.md bundle as the
``claude_md`` baseline, byte for byte, plus at most a one-line integration sentence at the TOP
(measured: an instruction buried after 17k characters produced a 0% search rate).
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..gate import AdmissionSignal


@dataclass(frozen=True)
class CorpusManifest:
    """The neutral experience feed: verbatim session transcripts, hashed.

    ``sessions`` maps a transcript path (relative to the corpus root) to its sha256. Every
    adapter ingests the same bytes; what its extraction pipeline stores is part of what is
    being measured.
    """

    root: Path
    sessions: Mapping[str, str]

    @classmethod
    def load(cls, corpus_root: str | Path) -> CorpusManifest:
        root = Path(corpus_root)
        manifest_path = root / "manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return cls(root=root, sessions=dict(data["sessions"]))

    def verify(self) -> None:
        """Refuse to ingest a corpus whose bytes do not match its manifest."""

        for rel_path, expected in self.sessions.items():
            actual = hashlib.sha256((self.root / rel_path).read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(
                    f"corpus file {rel_path} hashes to {actual}, manifest says {expected}; "
                    f"an unverified feed cannot be called identical across arms"
                )


@dataclass(frozen=True)
class IngestReport:
    """What one adapter did with the feed, metered from outside where possible."""

    arm: str
    namespace: str
    sessions_offered: int
    items_stored: int | None = None
    wall_time_ms: float | None = None
    llm_input_tokens: int | None = None
    llm_output_tokens: int | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "namespace": self.namespace,
            "sessions_offered": self.sessions_offered,
            "items_stored": self.items_stored,
            "wall_time_ms": self.wall_time_ms,
            "llm_input_tokens": self.llm_input_tokens,
            "llm_output_tokens": self.llm_output_tokens,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ArmSpec:
    """One arm's session configuration: the adapter's output, consumed by the runner.

    ``config_dir`` is the arm's isolated ``CLAUDE_CONFIG_DIR``, holding exactly that vendor's
    integration and nothing else. ``config_dir_digest`` is the sha256 over its file tree,
    recorded into the session record so the reviewed config is provably the run config.
    """

    arm: str
    mcp_config: str | None = None
    append_system_prompt_file: str | Path | None = None
    memory_tool_prefix: str | None = None
    extra_allowed_tools: tuple[str, ...] = ()
    config_dir: Path | None = None
    config_dir_digest: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    bare: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)


def digest_tree(root: Path) -> str:
    """A stable sha256 over a directory tree's relative paths and contents."""

    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


class MemoryAdapter(ABC):
    """One memory product's complete entry into the benchmark."""

    #: The arm name, unique across the registry.
    name: str = ""

    @abstractmethod
    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        """Feed the corpus through the product's own write path into ``namespace``."""

    @abstractmethod
    def build(self, session_dir: Path, namespace: str) -> ArmSpec:
        """Materialise this arm's session configuration under ``session_dir``.

        Called once per session. Must be deterministic given (frozen config, namespace):
        the returned ``config_dir_digest`` is asserted stable across sessions of one run.
        """

    @abstractmethod
    def admission_signal(self) -> AdmissionSignal:
        """What the gate must verify before this arm's sessions count as evidence."""

    def snapshot(self, namespace: str) -> Any:  # pragma: no cover - optional capability
        """Capture the post-ingest store state, for restore-per-session isolation.

        Self-hosted adapters override this; SaaS adapters raise, and the runner falls back
        to fresh-namespace-per-seed, which the methods section discloses as a limitation.
        """

        raise NotImplementedError(f"{self.name} does not support store snapshots")

    def restore(self, snapshot: Any) -> None:  # pragma: no cover - optional capability
        raise NotImplementedError(f"{self.name} does not support store snapshots")

    def describe(self) -> dict[str, Any]:
        """The frozen config and versions, redacted, for the run artifact."""

        return {"arm": self.name}
