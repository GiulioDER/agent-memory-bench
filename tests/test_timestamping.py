import json
import subprocess
from datetime import UTC, datetime

import pytest

from harness.prereg import PreregistrationDirty
from harness.timestamping import (
    ManifestExists,
    existing_manifests,
    stamp,
    verify,
)

T0 = datetime(2026, 8, 26, 12, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 8, 26, 13, 0, 0, tzinfo=UTC)


def _commit(repo, message):
    subprocess.run(["git", "add", "preregistration"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", message, "--no-gpg-sign"], cwd=repo, check=True
    )


@pytest.fixture()
def repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    prereg = tmp_path / "preregistration"
    prereg.mkdir()
    (prereg / "000-pilot.md").write_text("prediction: 0.4\n", encoding="utf-8")
    _commit(tmp_path, "prereg")
    return tmp_path


def test_stamp_records_hash_and_recoverable_blob(repo):
    manifest_path = stamp(repo, now=T0)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    (entry,) = manifest["files"]
    assert entry["path"] == "preregistration/000-pilot.md"

    (verdict,) = verify(repo, manifest_path)
    assert verdict.verdict == "MATCH"
    assert verdict.blob_recoverable


def test_manifest_bytes_are_lf_so_an_ots_anchor_survives_checkout(repo):
    # The repo normalizes text to LF; a CRLF manifest would commit as different bytes
    # than the ones an OpenTimestamps attestation covers.
    manifest_path = stamp(repo, now=T0)
    assert b"\r" not in manifest_path.read_bytes()


def test_stamp_refuses_uncommitted_prediction(repo):
    (repo / "preregistration" / "000-pilot.md").write_text("edited\n", encoding="utf-8")
    with pytest.raises(PreregistrationDirty):
        stamp(repo, now=T0)


def test_manifests_are_append_only(repo):
    stamp(repo, now=T0)
    _commit(repo, "manifest one")
    with pytest.raises(ManifestExists):
        stamp(repo, now=T0)
    stamp(repo, now=T1)
    assert len(existing_manifests(repo)) == 2


def test_manifests_do_not_stamp_themselves(repo):
    stamp(repo, now=T0)
    _commit(repo, "manifest one")
    second = json.loads(stamp(repo, now=T1).read_text(encoding="utf-8"))
    assert all("timestamps" not in e["path"] for e in second["files"])


def test_appended_result_reads_changed_with_bytes_still_provable(repo):
    manifest_path = stamp(repo, now=T0)
    _commit(repo, "manifest")
    prereg = repo / "preregistration" / "000-pilot.md"
    prereg.write_text(prereg.read_text(encoding="utf-8") + "\nresult: 0.1\n", encoding="utf-8")
    _commit(repo, "append result")

    (verdict,) = verify(repo, manifest_path)
    assert verdict.verdict == "CHANGED"
    assert verdict.blob_recoverable  # the stamped bytes remain in history


def test_missing_preregistration_file_is_flagged(repo):
    manifest_path = stamp(repo, now=T0)
    _commit(repo, "manifest")
    subprocess.run(
        ["git", "rm", "-q", "preregistration/000-pilot.md"], cwd=repo, check=True
    )
    subprocess.run(["git", "commit", "-q", "-m", "rm", "--no-gpg-sign"], cwd=repo, check=True)

    (verdict,) = verify(repo, manifest_path)
    assert verdict.verdict == "MISSING"
