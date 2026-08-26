"""Trusted timestamps for preregistrations: proof the prediction preceded the measurement.

The preregistration guard (:mod:`harness.prereg`) enforces that predictions are committed
before a run. A git commit date, however, is written by the committer and proves nothing to
a skeptic: ``GIT_COMMITTER_DATE`` is a plain environment variable. This module adds the two
anchors that are not ours to edit:

1. **A hash manifest, committed and pushed.** ``stamp()`` writes an append-only manifest of
   the sha256 and git blob id of every preregistration file into
   ``preregistration/timestamps/``. Writing it dirties the preregistration directory, so the
   run guard itself forces the manifest to be committed (and therefore pushable) before a
   single session starts. GitHub's server-side push time is the first independent anchor.
2. **An OpenTimestamps attestation, when the ``ots`` client is installed.** The manifest
   file is stamped against public calendar servers, anchoring its hash in Bitcoin. This is
   optional tooling: its absence is reported, never silently ignored.

What this proves, and deliberately does not claim, is written out in
``docs/TIMESTAMPING.md``. In one line: it proves the stamped bytes existed before the
anchor's time. It cannot prove the run that followed was honest; that is what full result
publication and third-party re-runs are for.

Two rules mirror the repository's preregistration convention:

- **Manifests are append-only.** ``stamp()`` refuses to overwrite, and each stamp creates a
  new file. A superseded manifest is history, not garbage.
- **A CHANGED verdict is not automatically tampering.** Results are appended below the
  frozen prediction in the same file, so any manifest taken before a run will legitimately
  disagree with the file after it. The manifest records the git blob id precisely so the
  stamped bytes stay recoverable (``git cat-file blob <id>``) after the file grows.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from harness.prereg import PREREG_DIR, assert_preregistered

TIMESTAMP_DIR = "timestamps"


class ManifestExists(RuntimeError):
    pass


class NothingToStamp(RuntimeError):
    pass


class ManifestMissing(RuntimeError):
    pass


@dataclass
class FileVerdict:
    path: str
    verdict: str  # MATCH | CHANGED | MISSING
    blob_recoverable: bool


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(repo_root), capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _prereg_files(repo_root: Path) -> list[Path]:
    """Every file under preregistration/ except the manifests themselves, sorted."""

    prereg = repo_root / PREREG_DIR
    return sorted(
        p for p in prereg.rglob("*") if p.is_file() and TIMESTAMP_DIR not in p.parts
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_dir(repo_root: str | Path) -> Path:
    return Path(repo_root) / PREREG_DIR / TIMESTAMP_DIR


def existing_manifests(repo_root: str | Path) -> list[Path]:
    d = manifest_dir(repo_root)
    return sorted(d.glob("manifest-*.json")) if d.is_dir() else []


def stamp(repo_root: str | Path, now: datetime | None = None) -> Path:
    """Write a new, never-overwritten manifest of every preregistration file.

    Refuses while the preregistration directory is dirty: a manifest of uncommitted bytes
    would anchor a prediction nobody can later locate in history.
    """

    repo_root = Path(repo_root)
    assert_preregistered(repo_root)

    files = _prereg_files(repo_root)
    if not files:
        raise NothingToStamp(f"no files under {PREREG_DIR}/ to stamp")

    now = now or datetime.now(UTC)
    out_dir = manifest_dir(repo_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"manifest-{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    if out.exists():
        raise ManifestExists(
            f"{out.name} already exists; manifests are append-only and never overwritten"
        )

    entries = []
    for path in files:
        rel = path.relative_to(repo_root).as_posix()
        blob = _git(repo_root, "rev-parse", f"HEAD:{rel}")
        entries.append(
            {
                "path": rel,
                "sha256": _sha256(path),
                "git_blob": blob,
                "bytes": path.stat().st_size,
            }
        )

    manifest = {
        "created_utc": now.isoformat(timespec="seconds"),
        "commit": _git(repo_root, "rev-parse", "HEAD"),
        "what_this_is": (
            "sha256 and git blob id of every preregistration file at stamp time. "
            "Append-only; a later manifest supersedes, never replaces, this one. "
            "See docs/TIMESTAMPING.md for what an anchor on this file proves."
        ),
        "files": entries,
    }
    # LF explicitly: the repo normalizes text to LF, and an OpenTimestamps attestation
    # covers exact bytes, so the file on disk must equal the committed blob everywhere.
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return out


def ots_stamp(manifest_path: Path) -> str:
    """Anchor the manifest with OpenTimestamps if the client is installed.

    Returns a human-readable status line. Absence of the client is a reported condition,
    not an error: the committed-and-pushed manifest is an anchor on its own, and the .ots
    can be created later (its own date is then the proven one, which stays honest).
    """

    ots = shutil.which("ots")
    if ots is None:
        return (
            "ots client not installed: no OpenTimestamps anchor was created. "
            "Install with 'pip install opentimestamps-client' and run "
            f"'ots stamp {manifest_path}'. The proven time is when the stamp is made."
        )
    result = subprocess.run(
        [ots, "stamp", str(manifest_path)], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return f"ots stamp FAILED: {(result.stderr or result.stdout).strip()}"
    return f"OpenTimestamps attestation written: {manifest_path.name}.ots"


def verify(repo_root: str | Path, manifest_path: Path | None = None) -> list[FileVerdict]:
    """Compare current preregistration files against a manifest (latest by default).

    MATCH means the bytes are identical to the stamped ones. CHANGED is expected once
    results have been appended below a frozen prediction; the stamped bytes remain
    provable through the recorded git blob, and ``blob_recoverable`` reports whether that
    blob is still reachable in this repository. MISSING means a stamped file is gone,
    which preregistration files never legitimately are.
    """

    repo_root = Path(repo_root)
    if manifest_path is None:
        manifests = existing_manifests(repo_root)
        if not manifests:
            raise ManifestMissing(
                f"no manifests under {PREREG_DIR}/{TIMESTAMP_DIR}/; run stamp first"
            )
        manifest_path = manifests[-1]

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    verdicts = []
    for entry in manifest["files"]:
        path = repo_root / entry["path"]
        recoverable = (
            subprocess.run(
                ["git", "cat-file", "-e", entry["git_blob"]],
                cwd=str(repo_root),
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
        if not path.is_file():
            verdict = "MISSING"
        elif _sha256(path) == entry["sha256"]:
            verdict = "MATCH"
        else:
            verdict = "CHANGED"
        verdicts.append(FileVerdict(entry["path"], verdict, recoverable))
    return verdicts
