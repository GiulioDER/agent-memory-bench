"""Build deterministic hashes for the private challenge pack and evaluator policy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .challenge_pack import ChallengePack
from .challenge_policy import ChallengeEvaluationPolicy


def hash_private_pack(pack: ChallengePack) -> str:
    """Hash every regular file and its portable relative path in a validated private pack."""

    digest = hashlib.sha256()
    for path in sorted((candidate for candidate in pack.root.rglob("*") if candidate.is_file())):
        relative = path.relative_to(pack.root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def build_release_manifest(
    pack: ChallengePack,
    policy: ChallengeEvaluationPolicy,
) -> dict[str, Any]:
    """Build the immutable release record held by the independent reviewer."""

    return {
        "schema": 1,
        "kind": "amb-challenge-release",
        "pack_id": pack.manifest["pack_id"],
        "pack_digest": hash_private_pack(pack),
        "policy_id": policy.policy_id,
        "policy_digest": policy.digest(),
        "source_public_commit": pack.manifest["source_public_commit"],
        "scoring_version": pack.manifest["scoring_version"],
        "task_count": len(pack.tasks),
    }


def write_release_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    """Write the release record using stable JSON formatting."""

    target = Path(path).expanduser()
    if target.exists() and target.is_symlink():
        raise ValueError(f"release manifest target must not be a symlink: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
