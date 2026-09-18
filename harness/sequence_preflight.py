"""Preflight a bound sequence plan and held out evaluation manifest."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .frozen_manifest import FrozenEvaluationManifest
from .sequence_plan import SequencePlan
from .sequence_validation import sequence_input_files


@dataclass(frozen=True)
class SequenceEvaluationPreflight:
    """The immutable identities checked before a sequence run may start."""

    plan_id: str
    plan_digest: str
    manifest_id: str
    manifest_digest: str
    chains: int
    chain_lengths: tuple[int, ...]
    corpus_files: tuple[str, ...]
    protocol_files: tuple[str, ...]
    bound_sequence_files: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "plan_digest": self.plan_digest,
            "manifest_id": self.manifest_id,
            "manifest_digest": self.manifest_digest,
            "chains": self.chains,
            "chain_lengths": list(self.chain_lengths),
            "corpus_files": list(self.corpus_files),
            "protocol_files": list(self.protocol_files),
            "bound_sequence_files": list(self.bound_sequence_files),
            "verified": True,
        }


def validate_sequence_evaluation(
    plan: SequencePlan,
    manifest: FrozenEvaluationManifest,
    *,
    repo_root: str | Path | None = None,
    tasks_root: str | Path | None = None,
) -> SequenceEvaluationPreflight:
    """Verify the frozen inputs and their binding before execution.

    The manifest binds runtime task inputs.  The sequence plan is bound
    separately by its content digest, which avoids making the manifest and
    the plan recursively depend on each other.
    """

    manifest.verify()
    manifest_id = manifest.data.get("manifest_id")
    if manifest_id != plan.evaluation_manifest_id:
        raise ValueError("sequence plan and heldout manifest identify different manifests")
    if manifest.digest != plan.evaluation_manifest_digest:
        raise ValueError("sequence plan and heldout manifest have different digests")
    bound_sequence_files: set[str] = set()
    if repo_root is not None or tasks_root is not None:
        if repo_root is None or tasks_root is None:
            raise ValueError("repo_root and tasks_root must be supplied together")
        bound_sequence_files.update(
            sequence_input_files(plan, repo_root=repo_root, tasks_root=tasks_root)
        )
    missing = sorted(
        bound_sequence_files - set(manifest.data.get("protocol_files", {}))
    )
    if missing:
        raise ValueError(
            "heldout manifest does not bind all sequence evaluation inputs: " + ", ".join(missing)
        )
    return SequenceEvaluationPreflight(
        plan_id=plan.plan_id,
        plan_digest=plan.digest,
        manifest_id=str(manifest_id),
        manifest_digest=manifest.digest,
        chains=len(plan.chains),
        chain_lengths=tuple(sorted({chain.length for chain in plan.chains})),
        corpus_files=tuple(sorted(manifest.data["corpus_files"])),
        protocol_files=tuple(sorted(manifest.data["protocol_files"])),
        bound_sequence_files=tuple(sorted(bound_sequence_files)),
    )
