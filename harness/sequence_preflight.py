"""Preflight a bound sequence plan and held out evaluation manifest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .frozen_manifest import FrozenEvaluationManifest
from .sequence_plan import SequencePlan


@dataclass(frozen=True)
class SequenceEvaluationPreflight:
    """The immutable identities checked before a sequence run may start."""

    plan_id: str
    manifest_id: str
    manifest_digest: str
    chains: int
    chain_lengths: tuple[int, ...]
    corpus_files: tuple[str, ...]
    protocol_files: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "manifest_id": self.manifest_id,
            "manifest_digest": self.manifest_digest,
            "chains": self.chains,
            "chain_lengths": list(self.chain_lengths),
            "corpus_files": list(self.corpus_files),
            "protocol_files": list(self.protocol_files),
            "verified": True,
        }


def validate_sequence_evaluation(
    plan: SequencePlan, manifest: FrozenEvaluationManifest
) -> SequenceEvaluationPreflight:
    """Verify the frozen inputs and their binding before execution."""

    manifest.verify()
    manifest_id = manifest.data.get("manifest_id")
    if manifest_id != plan.evaluation_manifest_id:
        raise ValueError("sequence plan and heldout manifest identify different manifests")
    if manifest.digest != plan.evaluation_manifest_digest:
        raise ValueError("sequence plan and heldout manifest have different digests")
    return SequenceEvaluationPreflight(
        plan_id=plan.plan_id,
        manifest_id=str(manifest_id),
        manifest_digest=manifest.digest,
        chains=len(plan.chains),
        chain_lengths=tuple(sorted({chain.length for chain in plan.chains})),
        corpus_files=tuple(sorted(manifest.data["corpus_files"])),
        protocol_files=tuple(sorted(manifest.data["protocol_files"])),
    )
