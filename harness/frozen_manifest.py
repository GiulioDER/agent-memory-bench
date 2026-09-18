"""Build and verify immutable evaluation manifests for held out corpus runs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .adapters.base import resolve_corpus_path

SCHEMA_VERSION = 1


def _canonical_body(data: dict[str, Any]) -> bytes:
    body = {key: value for key, value in data.items() if key != "manifest_digest"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def manifest_digest(data: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_body(data)).hexdigest()


def _relative_path(root: Path, value: str | Path) -> str:
    candidate = Path(value)
    relative = candidate.as_posix() if not candidate.is_absolute() else None
    if relative is None or "\\" in relative:
        raise ValueError(f"evaluation manifest path must be relative and portable: {value!r}")
    resolved = resolve_corpus_path(root, relative)
    if not resolved.is_file():
        raise FileNotFoundError(f"evaluation manifest file does not exist: {relative}")
    return resolved.relative_to(root.resolve()).as_posix()


def _hash_files(root: Path, paths: Iterable[str | Path]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in paths:
        relative = _relative_path(root, value)
        if relative in result:
            raise ValueError(f"evaluation manifest lists {relative!r} more than once")
        result[relative] = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    return dict(sorted(result.items()))


@dataclass(frozen=True)
class FrozenEvaluationManifest:
    root: Path
    data: dict[str, Any]

    @property
    def digest(self) -> str:
        return manifest_digest(self.data)

    @classmethod
    def build(
        cls,
        root: str | Path,
        *,
        manifest_id: str,
        created_at: str,
        corpus_files: Iterable[str | Path],
        protocol_files: Iterable[str | Path] = (),
        split: str = "heldout",
    ) -> FrozenEvaluationManifest:
        repo_root = Path(root).resolve()
        if not manifest_id.strip():
            raise ValueError("manifest_id must not be empty")
        datetime.fromisoformat(created_at)
        if split != "heldout":
            raise ValueError("this freezer is intentionally limited to the heldout split")
        corpus = _hash_files(repo_root, corpus_files)
        protocol = _hash_files(repo_root, protocol_files)
        if not protocol:
            raise ValueError(
                "a heldout evaluation manifest must freeze at least one protocol file"
            )
        overlap = sorted(set(corpus) & set(protocol))
        if overlap:
            raise ValueError(f"a file cannot be both corpus and protocol input: {overlap}")
        data: dict[str, Any] = {
            "schema": SCHEMA_VERSION,
            "manifest_id": manifest_id,
            "split": split,
            "created_at": created_at,
            "frozen": True,
            "corpus_files": corpus,
            "protocol_files": protocol,
        }
        data["manifest_digest"] = manifest_digest(data)
        return cls(repo_root, data)

    @classmethod
    def load(cls, path: str | Path, *, root: str | Path | None = None) -> FrozenEvaluationManifest:
        manifest_path = Path(path)
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("evaluation manifest must be a JSON object")
        return cls(Path(root).resolve() if root is not None else manifest_path.parents[1], data)

    def verify(self) -> None:
        if self.data.get("schema") != SCHEMA_VERSION:
            raise ValueError("unsupported evaluation manifest schema")
        if self.data.get("split") != "heldout" or self.data.get("frozen") is not True:
            raise ValueError("evaluation manifest is not a frozen heldout manifest")
        if self.data.get("manifest_digest") != self.digest:
            raise ValueError("evaluation manifest digest does not match its body")
        for field in ("corpus_files", "protocol_files"):
            files = self.data.get(field)
            if not isinstance(files, dict) or not files:
                raise ValueError(f"evaluation manifest {field} must be a nonempty object")
            for relative, expected in files.items():
                actual_path = resolve_corpus_path(self.root, relative)
                actual = hashlib.sha256(actual_path.read_bytes()).hexdigest()
                if actual != expected:
                    raise ValueError(
                        f"evaluation manifest file {relative} hashes to {actual}, expected {expected}"
                    )

    def write(self, path: str | Path) -> None:
        self.verify()
        Path(path).write_text(json.dumps(self.data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
