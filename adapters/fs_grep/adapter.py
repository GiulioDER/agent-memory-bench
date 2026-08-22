"""The ``fs_grep`` arm: past session transcripts on disk, and grep. Letta's baseline.

The most damaging single result in this field's history is a filesystem plus ``grep`` beating
a purpose-built memory product. If this benchmark omitted that baseline, Letta would run it
for us. Its "ingestion" is honest and cheap: each transcript is rendered to readable markdown
under ``memory/`` inside the sandbox, and the CLAUDE.md bundle gains one sentence saying the
notes exist. No extraction, no index, no product.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from harness.adapters.base import ArmSpec, CorpusManifest, IngestReport, MemoryAdapter
from harness.gate import AdmissionSignal
from harness.transcripts import render_transcript

#: The one-line nudge, at the TOP of the bundle like every other arm's (measured: buried
#: instructions produce a 0% usage rate, and then you are benchmarking prompt placement).
FS_GREP_SENTENCE = (
    "Notes from previous work sessions on this project live under memory/ as markdown. "
    "Grep them BEFORE deciding how to do anything about this repository's conventions, "
    "tooling, commands, or history; they hold decisions and hazards not derivable from "
    "the code.\n\n"
)


class FsGrepAdapter(MemoryAdapter):
    name = "fs_grep"

    def __init__(self, staging_root: str | Path, base_prompt_file: str | Path) -> None:
        self.staging_root = Path(staging_root)
        self.base_prompt_file = Path(base_prompt_file)

    def _staging_dir(self, namespace: str) -> Path:
        return self.staging_root / namespace / "memory"

    def _prompt_path(self, namespace: str) -> Path:
        return self.staging_root / namespace / "prompt.md"

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        corpus.verify()
        target = self._staging_dir(namespace)
        target.mkdir(parents=True, exist_ok=True)
        stored = 0
        for rel_path in sorted(corpus.sessions):
            source = corpus.root / rel_path
            out = target / (Path(rel_path).with_suffix(".md").name)
            out.write_text(render_transcript(source), encoding="utf-8")
            stored += 1
        prompt = self._prompt_path(namespace)
        prompt.write_text(
            FS_GREP_SENTENCE + self.base_prompt_file.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            items_stored=stored,
            llm_input_tokens=0,
            llm_output_tokens=0,
            notes=("verbatim markdown render; no extraction, no index",),
        )

    def build(self, session_dir: Path, namespace: str) -> ArmSpec:
        staged = self._staging_dir(namespace)
        prompt = self._prompt_path(namespace)
        if not staged.is_dir() or not prompt.is_file():
            raise FileNotFoundError(
                f"fs_grep namespace {namespace!r} has not been ingested; run ingest first"
            )
        return ArmSpec(
            arm=self.name,
            bare=True,
            append_system_prompt_file=prompt,
            metadata={
                "memory": "filesystem",
                # The sandbox builder overlays this directory at memory/ inside the sandbox
                # and records "memory" into metadata["sandbox_paths_present"].
                "sandbox_overlay": str(staged),
                "prompt_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest(),
            },
        )

    def admission_signal(self) -> AdmissionSignal:
        return AdmissionSignal(arm=self.name, sandbox_paths=("memory",))

    def describe(self) -> dict:
        return {"arm": self.name, "memory": "filesystem+grep"}
