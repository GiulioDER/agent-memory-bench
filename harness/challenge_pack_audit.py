"""Audit a private challenge corpus for exact sensitive file leakage."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .challenge_pack import ChallengePack
from .challenge_release import HASH_CHUNK_SIZE


class ChallengePackLeakageError(ValueError):
    """The public memory corpus contains an exact private task or scoring file."""


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ChallengePackLeakageReport:
    corpus_files: int
    sensitive_files: int
    exact_duplicates: tuple[tuple[str, str], ...]
    suspicious_corpus_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "corpus_files": self.corpus_files,
            "sensitive_files": self.sensitive_files,
            "exact_duplicates": [list(pair) for pair in self.exact_duplicates],
            "suspicious_corpus_paths": list(self.suspicious_corpus_paths),
            "status": "fail" if self.exact_duplicates else "pass",
        }


def _regular_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*") if path.is_file())


def audit_pack_corpus(pack: ChallengePack) -> ChallengePackLeakageReport:
    """Compare corpus bytes to private scoring inputs and report suspicious names."""

    corpus_files = _regular_files(pack.corpus)
    sensitive_roots = [
        path
        for task in pack.tasks
        for path in (
            task.fixture,
            task.prompt,
            task.checker,
            task.oracle,
            task.reference,
        )
    ]
    sensitive_files = [
        path for root in sensitive_roots for path in _regular_files(root) if path.is_file()
    ]
    sensitive_by_digest: dict[str, list[Path]] = {}
    for path in sensitive_files:
        sensitive_by_digest.setdefault(_file_digest(path), []).append(path)

    duplicates: list[tuple[str, str]] = []
    for corpus_file in corpus_files:
        digest = _file_digest(corpus_file)
        for sensitive_file in sensitive_by_digest.get(digest, []):
            duplicates.append(
                (
                    corpus_file.relative_to(pack.root).as_posix(),
                    sensitive_file.relative_to(pack.root).as_posix(),
                )
            )
    suspicious_words = ("oracle", "reference", "checker", "answer", "gold")
    suspicious_paths = tuple(
        path.relative_to(pack.corpus).as_posix()
        for path in corpus_files
        if any(word in path.name.lower() for word in suspicious_words)
    )
    report = ChallengePackLeakageReport(
        corpus_files=len(corpus_files),
        sensitive_files=len(sensitive_files),
        exact_duplicates=tuple(sorted(set(duplicates))),
        suspicious_corpus_paths=tuple(sorted(suspicious_paths)),
    )
    if report.exact_duplicates:
        raise ChallengePackLeakageError(
            f"corpus exactly duplicates private scoring files: {report.exact_duplicates}"
        )
    return report
