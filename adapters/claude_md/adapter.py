"""The ``claude_md`` arm: the hand-written static bundle, and nothing else.

This is the **designated baseline**: the realistic incumbent, because nobody runs Claude Code
memory-free. Every memory arm receives this same bundle byte for byte (the additive design),
so the diff between any memory arm and this one is exactly one memory layer.

The bundle is one file per run, frozen; its sha256 goes into the admission signal, and the
run script must record the hash of the prompt file it actually passed into
``record.metadata["prompt_sha256"]`` so the gate can compare the two. A baseline whose prompt
drifted mid-run is not a baseline.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from harness.adapters.base import ArmSpec, CorpusManifest, IngestReport, MemoryAdapter
from harness.gate import AdmissionSignal


class ClaudeMdAdapter(MemoryAdapter):
    name = "claude_md"

    def __init__(self, prompt_file: str | Path) -> None:
        self.prompt_file = Path(prompt_file)

    def _prompt_sha256(self) -> str:
        return hashlib.sha256(self.prompt_file.read_bytes()).hexdigest()

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            items_stored=0,
            notes=(
                (
                    "the static bundle is authored, not ingested: this arm measures what a "
                    "hand-maintained file gives you, so feeding it the transcripts would "
                    "make it a memory product"
                ),
            ),
        )

    def build(self, session_dir: Path, namespace: str) -> ArmSpec:
        if not self.prompt_file.is_file():
            raise FileNotFoundError(f"static bundle is missing: {self.prompt_file}")
        return ArmSpec(
            arm=self.name,
            bare=True,
            append_system_prompt_file=self.prompt_file,
            metadata={
                "memory": "static",
                "prompt_file": str(self.prompt_file),
                "prompt_sha256": self._prompt_sha256(),
            },
        )

    def admission_signal(self) -> AdmissionSignal:
        return AdmissionSignal(arm=self.name, prompt_sha256=self._prompt_sha256())

    def describe(self) -> dict:
        return {
            "arm": self.name,
            "memory": "static",
            "prompt_sha256": self._prompt_sha256(),
        }
