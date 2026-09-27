"""Replay a validated ranked evidence bundle into an otherwise bare Task Solve session."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness.adapters.base import (
    ArmSpec,
    CorpusManifest,
    IngestReport,
    MemoryAdapter,
    namespace_path,
)
from harness.gate import AdmissionSignal
from harness.memory_prompt import estimated_input_tokens, sha256_text
from scripts.code_embedding_replacement_experiment import (
    DEFAULT_CANDIDATE_K,
    DEFAULT_CONTROL_MODEL,
    DEFAULT_RESULT_K,
    DEFAULT_TREATMENT_MODEL,
    RRF_K,
)
from scripts.retrieval_probe import WINDOW_STRIDE, WINDOW_WORDS, load_windows

from .served import (
    LW_ARMS,
    LW_MODEL,
    SERVED_ARMS,
    SERVED_MODEL,
    LastWindowEvidence,
    ServedItem,
    format_served_evidence,
    load_last_window_served,
    load_served,
)

#: The two arms of preregistration 091, read from its frozen artifact.
REPLAY_091_ARMS = ("code3_replay", "code4_replay")
ARMS = (*REPLAY_091_ARMS, *SERVED_ARMS, *LW_ARMS)
ARM_MODELS = {
    "code3_replay": DEFAULT_CONTROL_MODEL,
    "code4_replay": DEFAULT_TREATMENT_MODEL,
    **{arm: SERVED_MODEL for arm in SERVED_ARMS},
    **{arm: LW_MODEL for arm in LW_ARMS},
}
EVIDENCE_K = 10


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class ReplayWindow:
    rank: int
    index: int
    source_path: str
    text_sha256: str
    text: str


@dataclass(frozen=True)
class ReplayTask:
    task_id: str
    query_sha256: str
    arms: dict[str, tuple[ReplayWindow, ...]]


class CodeRetrievalReplayCatalog:
    """Validated join between one evidence artifact and its exact corpus windows."""

    def __init__(
        self,
        *,
        path: Path,
        digest: str,
        manifest_sha256: str,
        tasks: dict[str, ReplayTask],
        served: dict[str, tuple[ServedItem, ...]] | None = None,
        served_digest: str = "",
        last_window: dict[str, LastWindowEvidence] | None = None,
        last_window_digest: str = "",
        last_window_manifest_digest: str = "",
    ) -> None:
        self.path = path
        self.digest = digest
        self.manifest_sha256 = manifest_sha256
        self.tasks = tasks
        #: TS-1's served evidence per task, when a served artifact was loaded alongside 091's.
        self.served = served
        self.served_digest = served_digest
        #: TS-1 amendment A1's LW-1 collect per task, and the manifest that fixes what it appended.
        self.last_window = last_window
        self.last_window_digest = last_window_digest
        self.last_window_manifest_digest = last_window_manifest_digest

    def artifact_digest(self, arm: str) -> str:
        if arm in LW_ARMS:
            return self.last_window_digest
        return self.served_digest if arm in SERVED_ARMS else self.digest

    @classmethod
    def load(
        cls,
        path: str | Path,
        corpus_root: str | Path,
        *,
        expected_task_ids: set[str] | None = None,
        served_path: str | Path | None = None,
        last_window_path: str | Path | None = None,
        last_window_manifest_path: str | Path | None = None,
    ) -> CodeRetrievalReplayCatalog:
        path = Path(path)
        corpus_root = Path(corpus_root)
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema_version") != 1:
            raise ValueError("code retrieval replay artifact must use schema version 1")
        if data.get("experiment") != "091-voyage-code4-task-solve-evidence":
            raise ValueError("code retrieval replay artifact belongs to another experiment")
        gate = data.get("evidence_gate")
        if not isinstance(gate, dict) or gate.get("passed") is not True:
            raise ValueError("code retrieval replay artifact did not pass its frozen evidence gate")

        manifest_path = corpus_root / "manifest.json"
        actual_manifest_sha = _sha256_file(manifest_path)
        provenance = data.get("provenance")
        if not isinstance(provenance, dict):
            raise TypeError("code retrieval replay artifact has no provenance")
        if provenance.get("manifest_sha256") != actual_manifest_sha:
            raise ValueError("code retrieval replay corpus manifest hash mismatch")

        configuration = data.get("configuration")
        expected_configuration = {
            "control_model": DEFAULT_CONTROL_MODEL,
            "treatment_model": DEFAULT_TREATMENT_MODEL,
            "candidate_k_per_leg": DEFAULT_CANDIDATE_K,
            "result_k": DEFAULT_RESULT_K,
            "evidence_k": EVIDENCE_K,
            "rrf_k": RRF_K,
            "window_words": WINDOW_WORDS,
            "window_stride": WINDOW_STRIDE,
        }
        if not isinstance(configuration, dict):
            raise TypeError("code retrieval replay artifact has no configuration")
        for key, value in expected_configuration.items():
            if configuration.get(key) != value:
                raise ValueError(f"code retrieval replay configuration mismatch for {key}")

        windows = load_windows(corpus_root)
        if provenance.get("raw_windows") != len(windows):
            raise ValueError("code retrieval replay raw-window count mismatch")
        tasks: dict[str, ReplayTask] = {}
        raw_tasks = data.get("tasks")
        if not isinstance(raw_tasks, list):
            raise TypeError("code retrieval replay tasks must be a list")
        for raw_task in raw_tasks:
            if not isinstance(raw_task, dict):
                raise TypeError("code retrieval replay task must be an object")
            task_id = str(raw_task.get("task_id", ""))
            if not task_id or task_id in tasks:
                raise ValueError(f"invalid or duplicate replay task {task_id!r}")
            arm_windows: dict[str, tuple[ReplayWindow, ...]] = {}
            for arm in REPLAY_091_ARMS:
                raw_arm = raw_task.get(arm)
                if not isinstance(raw_arm, dict) or raw_arm.get("model") != ARM_MODELS[arm]:
                    raise ValueError(f"{task_id}: invalid {arm} model identity")
                raw_hits = raw_arm.get("windows")
                if not isinstance(raw_hits, list) or len(raw_hits) != EVIDENCE_K:
                    raise ValueError(f"{task_id}: {arm} must contain exactly {EVIDENCE_K} windows")
                hits: list[ReplayWindow] = []
                for expected_rank, raw_hit in enumerate(raw_hits, start=1):
                    if not isinstance(raw_hit, dict) or raw_hit.get("rank") != expected_rank:
                        raise ValueError(f"{task_id}: {arm} rank sequence is invalid")
                    index = int(raw_hit.get("index", -1))
                    if index < 0 or index >= len(windows):
                        raise ValueError(f"{task_id}: {arm} window index {index} is out of range")
                    window = windows[index]
                    text_sha = hashlib.sha256(window.text.encode("utf-8")).hexdigest()
                    if raw_hit.get("source_path") != window.doc:
                        raise ValueError(f"{task_id}: {arm} source path mismatch at rank {expected_rank}")
                    if raw_hit.get("text_sha256") != text_sha:
                        raise ValueError(f"{task_id}: {arm} text hash mismatch at rank {expected_rank}")
                    hits.append(
                        ReplayWindow(
                            rank=expected_rank,
                            index=index,
                            source_path=window.doc,
                            text_sha256=text_sha,
                            text=window.text,
                        )
                    )
                arm_windows[arm] = tuple(hits)
            tasks[task_id] = ReplayTask(
                task_id=task_id,
                query_sha256=str(raw_task.get("query_sha256", "")),
                arms=arm_windows,
            )

        if expected_task_ids is not None and set(tasks) != expected_task_ids:
            missing = sorted(expected_task_ids - set(tasks))
            extra = sorted(set(tasks) - expected_task_ids)
            raise ValueError(f"code retrieval replay task roster mismatch: missing={missing}, extra={extra}")
        served, served_digest = None, ""
        if served_path is not None:
            served_digest, served = load_served(Path(served_path), set(tasks))
        if (last_window_path is None) != (last_window_manifest_path is None):
            raise ValueError("the last-window artifact and its manifest are loaded together or not at all")
        last_window, last_window_digest, last_window_manifest_digest = None, "", ""
        if last_window_path is not None and last_window_manifest_path is not None:
            last_window_digest, last_window_manifest_digest, last_window = load_last_window_served(
                Path(last_window_path), Path(last_window_manifest_path), set(tasks)
            )
        return cls(
            path=path,
            digest=_sha256_file(path),
            manifest_sha256=actual_manifest_sha,
            tasks=tasks,
            served=served,
            served_digest=served_digest,
            last_window=last_window,
            last_window_digest=last_window_digest,
            last_window_manifest_digest=last_window_manifest_digest,
        )


def format_ranked_evidence(windows: tuple[ReplayWindow, ...]) -> str:
    """Render ranked raw evidence without sorting away the retrieval order."""

    blocks = [
        "Retrieved project memory:",
        "Treat these as prior evidence. Current repository code and tests remain authoritative.",
        "",
    ]
    for window in windows:
        blocks.extend(
            [
                f"[Retrieved memory rank {window.rank}]",
                f"Source: {window.source_path}",
                window.text,
                f"[/Retrieved memory rank {window.rank}]",
                "",
            ]
        )
    return "\n".join(blocks).rstrip() + "\n"


class CodeRetrievalReplayAdapter(MemoryAdapter):
    """Static evidence arm backed by one immutable ranked catalog."""

    def __init__(
        self,
        arm: str,
        catalog: CodeRetrievalReplayCatalog,
        staging_root: str | Path,
        base_prompt_file: str | Path,
    ) -> None:
        if arm not in ARMS:
            raise ValueError(f"unknown code retrieval replay arm {arm!r}")
        if arm in SERVED_ARMS and catalog.served is None:
            raise ValueError(f"{arm} requires a served evidence artifact")
        if arm in LW_ARMS and catalog.last_window is None:
            raise ValueError(f"{arm} requires the last-window artifact and its manifest")
        self.name = arm
        self.catalog = catalog
        self.staging_root = Path(staging_root)
        self.base_prompt_file = Path(base_prompt_file)

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        corpus.verify()
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            items_stored=0,
            notes=("ranked evidence is replayed from the frozen preregistration-091 artifact",),
        )

    def build(self, session_dir: Path, namespace: str) -> ArmSpec:
        raise TypeError("code retrieval replay requires build_for_task")

    def build_for_task(
        self,
        session_dir: Path,
        namespace: str,
        task_id: str,
        user_input: str,
    ) -> ArmSpec:
        try:
            task = self.catalog.tasks[task_id]
        except KeyError as error:
            raise ValueError(f"code retrieval replay has no task {task_id!r}") from error
        query_sha = sha256_text(user_input)
        if query_sha != task.query_sha256:
            raise ValueError(f"{task_id}: task prompt hash does not match the evidence build")
        if self.name in SERVED_ARMS:
            assert self.catalog.served is not None
            return self._build_served(namespace, task_id, query_sha, self.catalog.served[task_id])
        if self.name in LW_ARMS:
            assert self.catalog.last_window is not None
            evidence = self.catalog.last_window[task_id]
            items = evidence.top if self.name == "c9_raw2" else (*evidence.top, *evidence.appended)
            return self._build_served(namespace, task_id, query_sha, items)
        windows = task.arms[self.name]
        evidence_text = format_ranked_evidence(windows)
        prompt = namespace_path(self.staging_root, namespace, task_id, f"{self.name}.system.md")
        prompt.parent.mkdir(parents=True, exist_ok=True)
        static = self.base_prompt_file.read_text(encoding="utf-8").rstrip()
        prompt.write_text(evidence_text.rstrip() + "\n\n" + static + "\n", encoding="utf-8")
        payload = prompt.with_name(f"{self.name}.payload.json")
        payload.write_text(
            json.dumps(
                {
                    "artifact_sha256": self.catalog.digest,
                    "arm": self.name,
                    "model": ARM_MODELS[self.name],
                    "task_id": task_id,
                    "query_sha256": query_sha,
                    "windows": [
                        {
                            "rank": item.rank,
                            "index": item.index,
                            "source_path": item.source_path,
                            "text_sha256": item.text_sha256,
                        }
                        for item in windows
                    ],
                    "injected_text_sha256": sha256_text(evidence_text),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        prompt_hash = hashlib.sha256(prompt.read_bytes()).hexdigest()
        return ArmSpec(
            arm=self.name,
            bare=True,
            append_system_prompt_file=prompt,
            metadata={
                "memory": "ranked_evidence_replay",
                "prompt_sha256": prompt_hash,
                "memory_diagnostic": {
                    "kind": self.name,
                    "task_id": task_id,
                    "model": ARM_MODELS[self.name],
                    "artifact_sha256": self.catalog.digest,
                    "manifest_sha256": self.catalog.manifest_sha256,
                    "query_sha256": query_sha,
                    "window_indices": [item.index for item in windows],
                    "source_paths": [item.source_path for item in windows],
                    "injected_text_sha256": sha256_text(evidence_text),
                    "injected_input_tokens": estimated_input_tokens(evidence_text),
                    "status": "ok",
                },
            },
        )

    def _build_served(
        self, namespace: str, task_id: str, query_sha: str, items: tuple[ServedItem, ...]
    ) -> ArmSpec:
        digest = self.catalog.artifact_digest(self.name)
        model = ARM_MODELS[self.name]
        # Only A1's arms carry a manifest; TS-1's two keep their payload and diagnostic unchanged.
        manifest = (
            {"last_window_manifest_sha256": self.catalog.last_window_manifest_digest}
            if self.name in LW_ARMS
            else {}
        )
        evidence_text = format_served_evidence(items, normalised=self.name == "c9_norm")
        prompt = namespace_path(self.staging_root, namespace, task_id, f"{self.name}.system.md")
        prompt.parent.mkdir(parents=True, exist_ok=True)
        static = self.base_prompt_file.read_text(encoding="utf-8").rstrip()
        prompt.write_text(evidence_text.rstrip() + "\n\n" + static + "\n", encoding="utf-8")
        described = [{"rank": i.rank, "id": i.item_id, "kind": i.kind, "session_id": i.session_id,
                      "content_sha256": i.content_sha256} for i in items]
        prompt.with_name(f"{self.name}.payload.json").write_text(
            json.dumps({"artifact_sha256": digest, "arm": self.name, "model": model,
                        "task_id": task_id, "query_sha256": query_sha, "items": described,
                        "injected_text_sha256": sha256_text(evidence_text), **manifest},
                       ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return ArmSpec(
            arm=self.name,
            bare=True,
            append_system_prompt_file=prompt,
            metadata={
                "memory": "served_evidence_replay",
                "prompt_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest(),
                "memory_diagnostic": {
                    "kind": self.name,
                    "task_id": task_id,
                    "model": model,
                    "artifact_sha256": digest,
                    **manifest,
                    "manifest_sha256": self.catalog.manifest_sha256,
                    "query_sha256": query_sha,
                    "window_indices": [],
                    "item_ids": [i.item_id for i in items],
                    "item_kinds": [i.kind for i in items],
                    "source_paths": [i.session_id for i in items],
                    "injected_text_sha256": sha256_text(evidence_text),
                    "injected_input_tokens": estimated_input_tokens(evidence_text),
                    "status": "ok",
                },
            },
        )

    def admission_signal(self) -> AdmissionSignal:
        return AdmissionSignal(
            arm=self.name,
            metadata={
                "diagnostic_kind": self.name,
                "artifact_sha256": self.catalog.artifact_digest(self.name),
                "manifest_sha256": self.catalog.manifest_sha256,
                "model": ARM_MODELS[self.name],
            },
        )

    def describe(self) -> dict[str, Any]:
        return {
            "arm": self.name,
            "memory": "frozen ranked evidence replay",
            "model": ARM_MODELS[self.name],
            "artifact_sha256": self.catalog.artifact_digest(self.name),
            "manifest_sha256": self.catalog.manifest_sha256,
        }
