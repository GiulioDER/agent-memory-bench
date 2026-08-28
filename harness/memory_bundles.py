"""Corpus backed evidence bundles for the diagnostic benchmark arms."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters.base import CorpusManifest, resolve_corpus_path
from .tasks import TaskSpec

DEFAULT_FORBIDDEN_MARKERS = (
    "checker.py",
    "oracles/",
    "oracle_dir",
    "expected output",
    "expected_output",
    "hazard label",
    "task id",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


@dataclass(frozen=True)
class MemoryItem:
    memory_id: str
    source_path: str
    source_sha256: str
    evidence_text: str
    recorded_at: str
    validity: str
    supersedes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "evidence_text": self.evidence_text,
            "recorded_at": self.recorded_at,
            "validity": self.validity,
            "supersedes": self.supersedes,
        }


@dataclass(frozen=True)
class MemoryBundle:
    bundle_id: str
    task_id: str
    items: tuple[MemoryItem, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "task_id": self.task_id,
            "items": [item.to_dict() for item in self.items],
        }

    @property
    def digest(self) -> str:
        return sha256_bytes(canonical_json(self.to_dict()))


class MemoryBundleCatalog:
    def __init__(
        self,
        root: Path,
        bundles: dict[str, MemoryBundle],
        digest: str,
        task_specs: dict[str, TaskSpec] | None = None,
    ) -> None:
        self.root = root
        self.bundles = bundles
        self.digest = digest
        self.task_specs = task_specs or {}

    @classmethod
    def load(
        cls,
        root: str | Path,
        corpus: CorpusManifest,
        tasks: list[TaskSpec] | tuple[TaskSpec, ...] = (),
    ) -> MemoryBundleCatalog:
        root = Path(root)
        manifest = root / "bundles.jsonl"
        if not manifest.is_file():
            raise FileNotFoundError(f"memory bundle manifest is missing: {manifest}")
        bundles: dict[str, MemoryBundle] = {}
        canonical_records: list[dict[str, Any]] = []
        for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid bundle JSON on line {line_number}") from error
            bundle = _parse_bundle(data, line_number)
            if bundle.bundle_id in bundles:
                raise ValueError(f"duplicate memory bundle id {bundle.bundle_id!r}")
            bundles[bundle.bundle_id] = bundle
            canonical_records.append(bundle.to_dict())

        catalog = cls(
            root=root,
            bundles=bundles,
            digest=sha256_bytes(canonical_json(sorted(canonical_records, key=lambda x: x["bundle_id"]))),
            task_specs={task.task_id: task for task in tasks},
        )
        catalog.validate(corpus, list(tasks))
        return catalog

    def validate(self, corpus: CorpusManifest, tasks: list[TaskSpec]) -> None:
        corpus.verify()
        known_tasks = {task.task_id: task for task in tasks}
        for bundle in self.bundles.values():
            if known_tasks and bundle.task_id not in known_tasks:
                raise ValueError(f"bundle {bundle.bundle_id!r} references unknown task {bundle.task_id!r}")
            seen_ids: set[str] = set()
            for item in bundle.items:
                if item.memory_id in seen_ids:
                    raise ValueError(f"bundle {bundle.bundle_id!r} has duplicate memory id {item.memory_id!r}")
                seen_ids.add(item.memory_id)
                if item.source_path not in corpus.sessions:
                    raise ValueError(f"bundle {bundle.bundle_id!r} references unknown source {item.source_path!r}")
                source = resolve_corpus_path(corpus.root, item.source_path)
                raw = source.read_bytes()
                actual_hash = sha256_bytes(raw)
                if actual_hash != item.source_sha256:
                    raise ValueError(
                        f"bundle {bundle.bundle_id!r} source hash mismatch for {item.source_path!r}"
                    )
                source_text = raw.decode("utf-8")
                semantic_texts = [source_text]
                if item.source_path.endswith(".jsonl"):
                    for source_line in source_text.splitlines():
                        try:
                            source_record = json.loads(source_line)
                        except json.JSONDecodeError:
                            continue
                        for value in source_record.values():
                            if isinstance(value, str):
                                semantic_texts.append(value)
                if not any(item.evidence_text in candidate for candidate in semantic_texts):
                    raise ValueError(
                        f"bundle {bundle.bundle_id!r} evidence {item.memory_id!r} is not an exact source substring"
                    )
                lowered = item.evidence_text.casefold()
                for marker in DEFAULT_FORBIDDEN_MARKERS:
                    if marker.casefold() in lowered:
                        raise ValueError(
                            f"bundle {bundle.bundle_id!r} evidence {item.memory_id!r} contains forbidden marker {marker!r}"
                        )
            if tuple(item.memory_id for item in bundle.items) != tuple(
                sorted(item.memory_id for item in bundle.items)
            ):
                raise ValueError(f"bundle {bundle.bundle_id!r} items are not deterministically ordered")

        for task in tasks:
            if task.memory_bundle_id is None:
                continue
            bundle = self.bundles.get(task.memory_bundle_id)
            if bundle is None:
                raise ValueError(f"task {task.task_id!r} references missing bundle {task.memory_bundle_id!r}")
            if bundle.task_id != task.task_id:
                raise ValueError(
                    f"bundle {bundle.bundle_id!r} belongs to {bundle.task_id!r}, not {task.task_id!r}"
                )

    def get_for_task(self, task: TaskSpec) -> MemoryBundle | None:
        if task.memory_bundle_id is None:
            return None
        try:
            return self.bundles[task.memory_bundle_id]
        except KeyError as error:
            raise ValueError(f"missing memory bundle {task.memory_bundle_id!r} for {task.task_id!r}") from error


def _parse_bundle(data: dict[str, Any], line_number: int) -> MemoryBundle:
    if not isinstance(data, dict):
        raise TypeError(f"bundle line {line_number} must be an object")
    try:
        bundle_id = str(data["bundle_id"])
        task_id = str(data["task_id"])
        raw_items = data["items"]
    except KeyError as error:
        raise ValueError(f"bundle line {line_number} is missing {error.args[0]!r}") from error
    if not isinstance(raw_items, list):
        raise TypeError(f"bundle {bundle_id!r} items must be a list")
    items: list[MemoryItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise TypeError(f"bundle {bundle_id!r} contains a non object item")
        required = ("memory_id", "source_path", "source_sha256", "evidence_text", "recorded_at", "validity")
        missing = [key for key in required if key not in raw]
        if missing:
            raise ValueError(f"bundle {bundle_id!r} item is missing {missing}")
        items.append(
            MemoryItem(
                memory_id=str(raw["memory_id"]),
                source_path=str(raw["source_path"]),
                source_sha256=str(raw["source_sha256"]),
                evidence_text=str(raw["evidence_text"]),
                recorded_at=str(raw["recorded_at"]),
                validity=str(raw["validity"]),
                supersedes=None if raw.get("supersedes") is None else str(raw["supersedes"]),
            )
        )
    return MemoryBundle(bundle_id=bundle_id, task_id=task_id, items=tuple(items))
