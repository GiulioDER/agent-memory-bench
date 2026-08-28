"""The ``claude_md`` arm: one static system-prompt file, and nothing else.

This is the **designated baseline**. Every memory arm receives this same bundle byte for byte (the
additive design), so the diff between any memory arm and this one is exactly one memory layer.

⚠️ **It is the fixture's own orientation README, not a curated conventions file, and this docstring
used to call it "the realistic incumbent".** What the runners actually hand it is two lines of
generic rules plus `tasks/<id>/tree/README.md`, which is three to five lines describing the
project. `scripts/audit_corpus.py` then guarantees the governing fact is absent from it, so the
primary contrast is "has the fact" against "provably does not have the fact", which is a FLOOR with
a document attached rather than an incumbent. A real project `CLAUDE.md` is exactly where a team
would write the convention this benchmark withholds.

One task makes the gap concrete rather than theoretical. `ts-legacy-hash`'s README says "For
digests of resource ids use `hashutil.fast_hash`", and the governing fact is that `fast_hash`
collides: `bare` solved it 1.00 and `claude_md` 0.00 in BOTH `pilot-003-deepseek` and
`pilot-004-placebo`. That is the arm's own bundle actively misdirecting it, and it is a large part
of why `claude_md` scored below `bare` overall.

So: legitimate task design, and a description that overclaimed. Anything comparing against this arm
should call it what it is, and a genuine curated-conventions arm is the incumbent worth adding.

``name`` is overridable because ``placebo`` and ``protocol`` are the same mechanism with different
content: one static file, no memory surface, admission by prompt hash.

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

    def __init__(self, prompt_file: str | Path, *, name: str | None = None) -> None:
        self.prompt_file = Path(prompt_file)
        if name is not None:
            self.name = name

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
