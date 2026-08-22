import subprocess

import pytest

from harness.prereg import PreregistrationDirty, assert_preregistered


@pytest.fixture()
def repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    prereg = tmp_path / "preregistration"
    prereg.mkdir()
    (prereg / "000-pilot.md").write_text("prediction", encoding="utf-8")
    subprocess.run(["git", "add", "preregistration"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "prereg", "--no-gpg-sign"], cwd=tmp_path, check=True
    )
    return tmp_path


def test_clean_preregistration_passes(repo):
    assert_preregistered(repo)


def test_modified_preregistration_refuses(repo):
    (repo / "preregistration" / "000-pilot.md").write_text("edited", encoding="utf-8")
    with pytest.raises(PreregistrationDirty, match="000-pilot.md"):
        assert_preregistered(repo)


def test_untracked_preregistration_refuses(repo):
    (repo / "preregistration" / "001-new.md").write_text("draft", encoding="utf-8")
    with pytest.raises(PreregistrationDirty, match="001-new.md"):
        assert_preregistered(repo)


def test_dirt_elsewhere_does_not_block(repo):
    (repo / "unrelated.txt").write_text("scratch", encoding="utf-8")
    assert_preregistered(repo)
