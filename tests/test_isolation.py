"""Unit coverage for the participant and checker trust boundaries.

These tests do not require a Docker daemon. The native Linux integration suite is responsible for
proving the policy against a real rootless runtime.
"""

from __future__ import annotations

import io
import json
import os
import tarfile
import tempfile
from pathlib import Path

import pytest

from harness.isolation import (
    ArchiveSafetyError,
    IsolationPolicy,
    ParticipantSpec,
    archive_directory,
    validate_archive,
)


def test_participant_policy_contains_the_nonnegotiable_controls(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    archive = tmp_path / "workspace.tar"
    archive_directory(workspace, archive)
    spec = ParticipantSpec(
        task_id="ts-probe",
        arm="bare",
        seed=0,
        workspace_archive=archive,
        config_archive=None,
        command=("/usr/local/bin/claude", "-p", "run"),
        public_env={"LANG": "C.UTF-8"},
        policy=IsolationPolicy(image="participant@sha256:abc", network="amb-broker-net"),
    )

    from harness import isolation

    args = isolation._container_args(spec, "amb-participant-test")
    joined = " ".join(args)
    for required in (
        "--read-only",
        "--cap-drop=ALL",
        "no-new-privileges:true",
        "--pids-limit 256",
        "--network amb-broker-net",
        "--ipc=private",
        "--tmpfs /workspace:rw,nosuid,nodev,size=512m,mode=1777",
    ):
        assert required in joined
    assert "--privileged" not in args
    # Docker's default PID mode is private. The CLI has no valid `private` value, so the
    # secure construction omits --pid entirely and explicitly rejects host/container modes.
    assert "--pid" not in args
    assert "--pid=host" not in args
    assert "--ipc=host" not in args
    assert "/var/run/docker.sock" not in joined


@pytest.mark.parametrize("network", ["host", ""])
def test_policy_rejects_host_or_missing_network(network: str) -> None:
    with pytest.raises(ValueError):
        IsolationPolicy(image="participant@sha256:abc", network=network)


def test_policy_rejects_all_host_mounts() -> None:
    with pytest.raises(ValueError, match="host mounts"):
        IsolationPolicy(image="participant@sha256:abc", allowed_mounts=("/repo:/workspace",))


def test_participant_spec_refuses_secret_environment_values(tmp_path: Path) -> None:
    archive = tmp_path / "workspace.tar"
    root = tmp_path / "workspace"
    root.mkdir()
    archive_directory(root, archive)
    with pytest.raises(ValueError, match="secret environment"):
        ParticipantSpec(
            task_id="ts-probe",
            arm="bare",
            seed=0,
            workspace_archive=archive,
            config_archive=None,
            command=("claude",),
            public_env={"OPENROUTER_API_KEY": "sentinel"},
        )


def test_mcp_configuration_is_replaced_by_credentialless_relay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness import isolation
    from harness.claude_exec import ClaudeExecConfig

    mcp = tmp_path / "mcp.json"
    mcp.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "recall": {
                        "command": "/host/private/recall",
                        "args": ["--dsn", "host-secret-path"],
                        "env": {"RECALL_DSN": "sentinel-provider-secret"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    config = ClaudeExecConfig(
        cwd=tmp_path,
        mcp_config=str(mcp),
        memory_tool_prefix="mcp__recall__",
        allowed_tools=("mcp__recall__search",),
        env={"RECALL_DSN": "sentinel-provider-secret"},
    )
    monkeypatch.delenv("AMB_CAPABILITY_MEMORY", raising=False)
    with tempfile.TemporaryDirectory() as staging:
        archive, _, _ = isolation._copy_config_archive(
            config, Path(staging), memory_capability="opaque-memory-capability"
        )
        payload = archive.read_bytes()
    assert b"sentinel-provider-secret" not in payload
    assert b"/host/private/recall" not in payload


def test_archive_rejects_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    link = root / "escape"
    try:
        link.symlink_to(tmp_path / "outside")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this test host")
    with pytest.raises(ArchiveSafetyError):
        archive_directory(root, tmp_path / "workspace.tar")


def test_archive_rejects_parent_paths_without_extracting(tmp_path: Path) -> None:
    archive_path = tmp_path / "bad.tar"
    with tarfile.open(archive_path, "w") as archive:
        info = tarfile.TarInfo("../outside")
        payload = b"secret"
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    with pytest.raises(ArchiveSafetyError, match="unsafe archive path"):
        validate_archive(archive_path)


@pytest.mark.parametrize("name", ["/absolute", "a/../../outside", "a\\outside"])
def test_archive_rejects_absolute_and_traversal_paths(tmp_path: Path, name: str) -> None:
    archive_path = tmp_path / "bad.tar"
    with tarfile.open(archive_path, "w") as archive:
        info = tarfile.TarInfo(name)
        info.size = 1
        archive.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(ArchiveSafetyError):
        validate_archive(archive_path)


def test_archive_rejects_links_devices_and_fifos(tmp_path: Path) -> None:
    for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE):
        path = tmp_path / f"bad-{kind}.tar"
        with tarfile.open(path, "w") as archive:
            info = tarfile.TarInfo("bad")
            info.type = kind
            info.linkname = "elsewhere"
            archive.addfile(info)
        with pytest.raises(ArchiveSafetyError):
            validate_archive(path)


def test_archive_rejects_duplicate_and_oversized_members(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.tar"
    with tarfile.open(duplicate, "w") as archive:
        for _ in range(2):
            info = tarfile.TarInfo("same")
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(ArchiveSafetyError, match="duplicate"):
        validate_archive(duplicate)

    oversized = tmp_path / "oversized.tar"
    with tarfile.open(oversized, "w") as archive:
        info = tarfile.TarInfo("huge")
        info.size = 64 * 1024 * 1024 + 1
        archive.addfile(info, io.BytesIO(b"x" * info.size))
    with pytest.raises(ArchiveSafetyError, match="exceeds size"):
        validate_archive(oversized)


def test_archive_directory_rejects_host_links_and_special_files(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("outside", encoding="utf-8")
    link = root / "link"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this test host")
    with pytest.raises(ArchiveSafetyError):
        archive_directory(root, tmp_path / "tree.tar")

    link.unlink()
    fifo = root / "fifo"
    try:
        os.mkfifo(fifo)
    except (OSError, NotImplementedError):
        pytest.skip("fifos are unavailable on this test host")
    with pytest.raises(ArchiveSafetyError):
        archive_directory(root, tmp_path / "fifo.tar")


def test_non_rootless_runtime_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """RED proof: accepting a non-rootless daemon makes the filesystem boundary meaningless."""

    from harness import isolation

    monkeypatch.setattr(isolation.shutil, "which", lambda _runtime: "docker")
    monkeypatch.setattr(
        isolation,
        "_run",
        lambda *_args, **_kwargs: type("Result", (), {"stdout": '["name=seccomp"]'})(),
    )
    with pytest.raises(isolation.IsolationError, match="not rootless"):
        isolation._assert_rootless("docker")


def test_production_launchers_do_not_call_local_claude_helper() -> None:
    """The local helper is retained for unit fixtures, never as a production launcher."""

    import ast

    scripts = Path(__file__).parents[1] / "scripts"
    for path in scripts.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "run_claude_case", path


def test_production_checker_calls_select_the_isolated_worker() -> None:
    import ast

    scripts = Path(__file__).parents[1] / "scripts"
    for path in scripts.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id != "run_checker":
                    continue
                isolated = next((keyword for keyword in node.keywords if keyword.arg == "isolated"), None)
                assert isolated is not None and isinstance(isolated.value, ast.Constant)
                assert isolated.value.value is True, path


def test_participant_build_context_cannot_bake_benchmark_sources() -> None:
    root = Path(__file__).parents[1]
    dockerfile = (root / "docker" / "Dockerfile.participant").read_text(encoding="utf-8")
    assert "COPY ." not in dockerfile
    participant_files = {
        path.name
        for path in (root / "docker" / "participant").iterdir()
        if path.is_file()
    }
    forbidden = {"tasks", "oracles", "reference", "corpus", ".git", ".claude", "results"}
    assert not forbidden.intersection(participant_files)


def test_policy_digest_is_stable_and_does_not_include_secret_values() -> None:
    policy = IsolationPolicy(image="participant@sha256:abc")
    assert policy.digest == IsolationPolicy(image="participant@sha256:abc").digest
    assert "secret" not in policy.digest.lower()
