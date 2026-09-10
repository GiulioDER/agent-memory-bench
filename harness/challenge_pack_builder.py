"""Materialize a private challenge pack without accepting public repository input."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from .challenge_pack import PUBLIC_REPO_ROOT, ChallengePack, load_private_pack
from .challenge_pack_audit import ChallengePackLeakageError, audit_pack_corpus


class ChallengePackBuildError(ValueError):
    """The source or destination is not safe for private pack materialization."""


def _outside_public(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if (
        resolved == PUBLIC_REPO_ROOT
        or PUBLIC_REPO_ROOT in resolved.parents
        or resolved in PUBLIC_REPO_ROOT.parents
    ):
        raise ChallengePackBuildError(f"{label} must be outside the public repository: {resolved}")
    return resolved


def materialize_private_pack(source_root: str | Path, destination: str | Path) -> ChallengePack:
    """Copy an external pack source into a fresh private destination and validate it."""

    source = _outside_public(Path(source_root), "pack source")
    target = _outside_public(Path(destination), "pack destination")
    if not source.is_dir():
        raise ChallengePackBuildError(f"pack source is not a directory: {source}")
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise ChallengePackBuildError(f"pack destination is not a regular directory: {target}")
        if any(target.iterdir()):
            raise ChallengePackBuildError(f"pack destination must start empty: {target}")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f".{target.name}.staging-{uuid.uuid4().hex}"
    try:
        shutil.copytree(source, staging, symlinks=True)
        pack = load_private_pack(staging)
        audit_pack_corpus(pack)
        if target.exists():
            target.rmdir()
        staging.replace(target)
        return load_private_pack(target)
    except OSError as error:
        raise ChallengePackBuildError(f"could not materialize private pack: {error}") from error
    except ChallengePackLeakageError as error:
        raise ChallengePackBuildError(f"pack corpus audit failed: {error}") from error
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
