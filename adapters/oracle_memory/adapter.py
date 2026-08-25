"""Ceiling control that supplies corpus verified evidence without memory tools."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from harness.adapters.base import ArmSpec, CorpusManifest, IngestReport, MemoryAdapter
from harness.gate import AdmissionSignal
from harness.memory_bundles import MemoryBundleCatalog
from harness.memory_prompt import estimated_input_tokens, format_memory_items, sha256_text


class OracleMemoryAdapter(MemoryAdapter):
    name = "oracle_memory"

    def __init__(
        self,
        staging_root: str | Path,
        base_prompt_file: str | Path,
        catalog: MemoryBundleCatalog,
    ) -> None:
        self.staging_root = Path(staging_root)
        self.base_prompt_file = Path(base_prompt_file)
        self.catalog = catalog

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        corpus.verify()
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            items_stored=0,
            notes=("corpus evidence is selected per task, with no product store",),
        )

    def build(self, session_dir: Path, namespace: str) -> ArmSpec:
        raise TypeError("oracle_memory requires build_for_task so the task bundle is explicit")

    def build_for_task(
        self,
        session_dir: Path,
        namespace: str,
        task_id: str,
        user_input: str,
    ) -> ArmSpec:
        del user_input
        task_spec = self.catalog.task_specs.get(task_id)
        bundle = self.catalog.bundles.get(task_spec.memory_bundle_id) if task_spec else None
        if task_spec is None:
            raise ValueError(f"oracle_memory has no task definition for {task_id!r}")
        if task_spec.memory_bundle_id is None:
            from harness.memory_bundles import MemoryBundle

            bundle = MemoryBundle(bundle_id=f"empty_{task_id}", task_id=task_id, items=())
        if bundle is None:
            raise ValueError(f"oracle_memory has no bundle for task {task_id!r}")
        memory_text = format_memory_items(bundle.items)
        return self._materialize(
            session_dir,
            namespace,
            task_id,
            bundle,
            memory_text,
            empty=task_spec.memory_bundle_id is None,
        )

    def _materialize(
        self,
        session_dir: Path,
        namespace: str,
        task_id: str,
        bundle,
        memory_text: str,
        *,
        empty: bool = False,
    ) -> ArmSpec:
        session_dir.mkdir(parents=True, exist_ok=True)
        prompt = self.staging_root / namespace / task_id / "oracle.system.md"
        prompt.parent.mkdir(parents=True, exist_ok=True)
        static = self.base_prompt_file.read_text(encoding="utf-8").rstrip()
        prompt.write_text(memory_text.rstrip() + "\n\n" + static + "\n", encoding="utf-8")
        payload = prompt.with_name("oracle.payload.json")
        payload.write_text(
            json.dumps(
                {
                    "bundle": bundle.to_dict(),
                    "bundle_sha256": None if empty else bundle.digest,
                    "injected_text_sha256": sha256_text(memory_text),
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
                "memory": "oracle",
                "prompt_sha256": prompt_hash,
                "memory_diagnostic": {
                    "kind": self.name,
                    "task_id": task_id,
                    "bundle_id": None if empty else bundle.bundle_id,
                    "bundle_sha256": None if empty else bundle.digest,
                    "catalog_sha256": self.catalog.digest,
                    "item_ids": [item.memory_id for item in bundle.items],
                    "injected_text_sha256": sha256_text(memory_text),
                    "injected_input_tokens": estimated_input_tokens(memory_text),
                    "status": "ok",
                },
            },
        )

    def admission_signal(self) -> AdmissionSignal:
        return AdmissionSignal(
            arm=self.name,
            metadata={
                "diagnostic_kind": self.name,
                "catalog_sha256": self.catalog.digest,
                "bundle_digests": {
                    key: value.digest for key, value in self.catalog.bundles.items()
                },
            },
        )

    def describe(self) -> dict:
        return {"arm": self.name, "memory": "corpus backed ceiling control", "catalog_sha256": self.catalog.digest}
