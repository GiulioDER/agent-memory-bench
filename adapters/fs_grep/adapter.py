"""The ``fs_grep`` arm: past session transcripts on disk, and grep. Letta's baseline.

The most damaging single result in this field's history is a filesystem plus ``grep`` beating
a purpose-built memory product. If this benchmark omitted that baseline, Letta would run it
for us. Its "ingestion" is honest and cheap: each transcript is rendered to readable markdown
under ``memory/`` inside the sandbox, and the CLAUDE.md bundle gains one sentence saying the
notes exist. No extraction, no index, no product.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from harness.adapters.base import ArmSpec, CorpusManifest, IngestReport, MemoryAdapter
from harness.gate import AdmissionSignal
from harness.instructions import compose
from harness.transcripts import render_corpus

#: The one-line nudge this arm carried until 2026-08-28, kept because `smoke-002` ran it and a
#: rerun of that smoke is only comparable against this exact text.
#:
#: ⚠️ It is 231 characters. The recall arm carried 5,428 over the same runs, which is the
#: instruction asymmetry the audit named: most of those 5,428 was generic coaching that would have
#: helped this arm too. `FS_GREP_SEARCH_SENTENCE` plus `harness.instructions` is the replacement,
#: and it gives every memory arm the same protocol.
FS_GREP_SENTENCE = (
    "Notes from previous work sessions on this project live under memory/ as markdown. "
    "Grep them BEFORE deciding how to do anything about this repository's conventions, "
    "tooling, commands, or history; they hold decisions and hazards not derivable from "
    "the code.\n\n"
)

#: This arm's one line in the shared protocol's slot. Everything else it is told is byte-identical
#: to what every other memory arm is told.
FS_GREP_SEARCH_SENTENCE = (
    "Notes from previous work sessions on this project live under `memory/` as markdown files; "
    "search them with `Grep` before acting."
)


class FsGrepAdapter(MemoryAdapter):
    name = "fs_grep"

    def __init__(
        self,
        staging_root: str | Path,
        base_prompt_file: str | Path,
        *,
        instruction: str | None = None,
    ) -> None:
        self.staging_root = Path(staging_root)
        self.base_prompt_file = Path(base_prompt_file)
        #: None keeps the historical one-liner, for comparability with `smoke-002`. Pass
        #: `harness.instructions.compose("fs_grep", FS_GREP_SEARCH_SENTENCE)` for the fair variant.
        self.instruction = instruction

    def _instruction_text(self) -> str:
        if self.instruction is not None:
            return self.instruction.rstrip() + "\n\n"
        return FS_GREP_SENTENCE

    @staticmethod
    def shared_instruction(*, neutral: bool = False) -> str:
        """The fair instruction: the shared protocol plus this arm's own capped appendix."""

        return compose("fs_grep", FS_GREP_SEARCH_SENTENCE, neutral=neutral)

    def _staging_dir(self, namespace: str) -> Path:
        return self.staging_root / namespace / "memory"

    def _prompt_path(self, namespace: str) -> Path:
        return self.staging_root / namespace / "prompt.md"

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        corpus.verify()
        target = self._staging_dir(namespace)
        # A fresh render every time: a stale file from an earlier feed layout would ride
        # along invisibly (the flat-name collision bug left exactly such files behind).
        if target.exists():
            shutil.rmtree(target)
        stored = render_corpus(
            [corpus.root / rel for rel in corpus.sessions], target, root=corpus.root
        )
        prompt = self._prompt_path(namespace)
        prompt.parent.mkdir(parents=True, exist_ok=True)
        prompt.write_text(
            self._instruction_text() + self.base_prompt_file.read_text(encoding="utf-8"),
            encoding="utf-8",
            newline="\n",
        )
        return IngestReport(
            arm=self.name,
            namespace=namespace,
            sessions_offered=len(corpus.sessions),
            items_stored=stored,
            llm_input_tokens=0,
            llm_output_tokens=0,
            notes=(
                (
                    "verbatim markdown render; no extraction, no index, and no model of any "
                    "kind, so the zero token counts are a true zero rather than an unmetered one"
                ),
            ),
        )

    def build(
        self, session_dir: Path, namespace: str, *, prompt_path: Path | None = None
    ) -> ArmSpec:
        staged = self._staging_dir(namespace)
        prompt = self._prompt_path(namespace)
        if not staged.is_dir() or not prompt.is_file():
            raise FileNotFoundError(
                f"fs_grep namespace {namespace!r} has not been ingested; run ingest first"
            )
        if prompt_path is not None:
            # One prompt per TASK, written into this session's own directory. The namespace-keyed
            # file above is written once per ingest, and a grid holds the namespace constant across
            # tasks, so serving it to every task would hand the first task's README to all of them.
            # That exact defect shipped in `diagnostic-001` through the recall adapter.
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(
                self._instruction_text() + self.base_prompt_file.read_text(encoding="utf-8"),
                encoding="utf-8",
                newline="\n",
            )
            prompt = prompt_path
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

    def build_for_task(
        self, session_dir: Path, namespace: str, task_id: str, user_input: str
    ) -> ArmSpec:
        session_dir.mkdir(parents=True, exist_ok=True)
        return self.build(session_dir, namespace, prompt_path=session_dir / "prompt.md")

    def admission_signal(self) -> AdmissionSignal:
        return AdmissionSignal(arm=self.name, sandbox_paths=("memory",))

    def describe(self) -> dict:
        return {
            "arm": self.name,
            "memory": "filesystem+grep",
            "instruction": "shared_protocol" if self.instruction is not None else "legacy_sentence",
        }
