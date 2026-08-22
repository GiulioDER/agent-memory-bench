"""The ``bare`` arm: no memory of any kind. The contamination-control arm.

Comparing a memory layer against nothing answers a question nobody asked (no one runs Claude
Code without a CLAUDE.md), so ``bare`` is not the baseline; ``claude_md`` is. ``bare`` exists
to measure the floor: a task a bare session can already do is a task whose governing fact the
model knows from priors, and it is screened out at the pilot.
"""

from __future__ import annotations

from pathlib import Path

from harness.adapters.base import ArmSpec, CorpusManifest, IngestReport, MemoryAdapter
from harness.gate import AdmissionSignal


class BareAdapter(MemoryAdapter):
    name = "bare"

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            items_stored=0,
            notes=("bare arm stores nothing by design",),
        )

    def build(self, session_dir: Path, namespace: str) -> ArmSpec:
        return ArmSpec(arm=self.name, bare=True, metadata={"memory": "none"})

    def admission_signal(self) -> AdmissionSignal:
        # All checks are negative: the gate's forbidden-prefix computation is what verifies
        # that no other arm's tools leaked into this one.
        return AdmissionSignal(arm=self.name)

    def describe(self) -> dict:
        return {"arm": self.name, "memory": "none"}
