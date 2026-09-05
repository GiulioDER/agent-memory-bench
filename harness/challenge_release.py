"""Build deterministic hashes for the private challenge pack and evaluator policy."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .challenge_pack import ChallengePack
from .challenge_policy import ChallengeEvaluationPolicy
from .challenge_rules import rules_digest

EVALUATOR_REVISION = re.compile(r"^[0-9a-f]{40,64}$")


def hash_private_pack(pack: ChallengePack) -> str:
    """Hash every regular file and its portable relative path in a validated private pack."""

    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in pack.root.rglob("*") if candidate.is_file()):
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
    rules: dict[str, Any] | None = None,
    *,
    evaluator_revision: str | None = None,
) -> dict[str, Any]:
    """Build the immutable release record held by the independent reviewer."""

    manifest = {
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
    if evaluator_revision is not None:
        if not EVALUATOR_REVISION.fullmatch(evaluator_revision):
            raise ValueError("evaluator_revision must be a 40 to 64 character lowercase commit hash")
        manifest["evaluator_revision"] = evaluator_revision
    if rules is not None:
        manifest["rules_id"] = rules["rules_id"]
        manifest["rules_digest"] = rules_digest(rules)
    return manifest


def write_release_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    """Create an immutable release record using stable JSON formatting."""

    target = Path(path).expanduser()
    if target.exists() and target.is_symlink():
        raise ValueError(f"release manifest target must not be a symlink: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    try:
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except FileExistsError as error:
        raise ValueError(f"release manifest target already exists: {target}") from error
