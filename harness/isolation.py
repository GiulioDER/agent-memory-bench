"""Disposable container execution for untrusted benchmark sessions.

The benchmark repository and its evaluator are trusted. A participant session is not. This
module is the single boundary between the two: it creates a rootless Docker container, transfers
only an explicit archive into it, captures the process output, and copies back only validated
regular files after the container has exited.

The runtime is intentionally conservative. A missing Docker runtime, a non rootless daemon, an
unexpected mount, or a malformed archive is an infrastructure failure. It is never silently
replaced with local process execution.
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import stat as statmod
import subprocess
import tarfile
import tempfile
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath


class IsolationError(RuntimeError):
    """The participant boundary could not be established or verified."""


_LOCAL_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")


def _is_pinned_image_reference(image: str) -> bool:
    """Accept registry digests and locally-addressable immutable image IDs."""

    return "@sha256:" in image or bool(_LOCAL_IMAGE_ID.fullmatch(image))


class ArchiveSafetyError(IsolationError):
    """An input or output archive contains a filesystem construct we do not accept."""


@dataclass(frozen=True)
class IsolationPolicy:
    """The complete container policy, recorded by digest rather than by inspect output."""

    image: str
    image_digest: str = ""
    runtime: str = "docker"
    network: str = "amb-broker-net"
    network_policy_digest: str = ""
    memory: str = "2g"
    cpu: str = "2"
    pids_limit: int = 256
    timeout_s: float = 1800.0
    max_output_bytes: int = 8 * 1024 * 1024
    user: str = "65532:65532"
    allowed_mounts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.image.strip():
            raise ValueError("participant image must not be empty")
        if self.runtime != "docker":
            raise ValueError("only the rootless Docker runtime is supported")
        if not self.network.strip() or self.network == "host":
            raise ValueError("participant network must be a private broker network")
        if self.timeout_s <= 0 or self.max_output_bytes <= 0:
            raise ValueError("timeout and output limit must be positive")
        if self.pids_limit < 1:
            raise ValueError("pids_limit must be positive")
        if self.allowed_mounts:
            raise ValueError(
                "participant containers do not accept host mounts; transfer explicit archives "
                "instead"
            )

    @property
    def digest(self) -> str:
        payload = {
            "image": self.image,
            "image_digest": self.image_digest,
            "runtime": self.runtime,
            "network": self.network,
            "network_policy_digest": self.network_policy_digest,
            "memory": self.memory,
            "cpu": self.cpu,
            "pids_limit": self.pids_limit,
            "timeout_s": self.timeout_s,
            "max_output_bytes": self.max_output_bytes,
            "user": self.user,
            "allowed_mounts": list(self.allowed_mounts),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @property
    def effective_image_digest(self) -> str:
        """Return the digest whether it was supplied separately or in the image reference."""

        if self.image_digest:
            return self.image_digest
        if _LOCAL_IMAGE_ID.fullmatch(self.image):
            return self.image
        return self.image.rsplit("@", 1)[-1] if "@sha256:" in self.image else ""


@dataclass(frozen=True)
class ParticipantSpec:
    """Inputs for one untrusted container session."""

    task_id: str
    arm: str
    seed: int
    workspace_archive: Path
    config_archive: Path | None
    command: tuple[str, ...]
    public_env: Mapping[str, str] = field(default_factory=dict)
    capability_grants: Mapping[str, str] = field(default_factory=dict)
    workspace_digest: str = ""
    policy: IsolationPolicy = field(
        default_factory=lambda: IsolationPolicy(image="agent-memory-bench-participant:latest")
    )

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.arm.strip():
            raise ValueError("task_id and arm must not be empty")
        if not self.command:
            raise ValueError("participant command must not be empty")
        if not self.workspace_archive.is_file():
            raise FileNotFoundError(self.workspace_archive)
        if not statmod.S_ISREG(self.workspace_archive.lstat().st_mode):
            raise ArchiveSafetyError("workspace archive must be a regular file")
        if self.workspace_archive.lstat().st_nlink > 1:
            raise ArchiveSafetyError("workspace archive must not be hard linked")
        if self.config_archive is not None and not self.config_archive.is_file():
            raise FileNotFoundError(self.config_archive)
        if self.config_archive is not None and not statmod.S_ISREG(self.config_archive.lstat().st_mode):
            raise ArchiveSafetyError("configuration archive must be a regular file")
        if self.config_archive is not None and self.config_archive.lstat().st_nlink > 1:
            raise ArchiveSafetyError("configuration archive must not be hard linked")
        for name, value in {**self.public_env, **self.capability_grants}.items():
            if not _valid_env_name(str(name)):
                raise ValueError(f"invalid participant environment name {name!r}")
            if "\x00" in str(value):
                raise ValueError(f"participant environment value {name!r} contains NUL")
        grants = {str(value) for value in self.capability_grants.values()}
        forbidden = [
            name
            for name, value in self.public_env.items()
            if _looks_like_secret_name(str(name))
            and not (
                str(name) == "ANTHROPIC_AUTH_TOKEN"
                and str(value) in grants
            )
        ]
        if forbidden:
            raise ValueError(
                "secret environment values cannot enter a participant container: "
                + ", ".join(sorted(forbidden))
            )


@dataclass(frozen=True)
class ParticipantResult:
    """Bounded output and proof data from one participant container."""

    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    output_archive: Path | None
    workspace_input_digest: str
    workspace_output_digest: str | None
    container_exit_status: str
    container_cleanup_status: str
    participant_isolation_verified: bool
    oracle_visible_to_participant: bool = False
    output_exceeded: bool = False
    runtime_name: str = "docker"
    participant_image_digest: str = ""
    isolation_policy_digest: str = ""
    network_policy_digest: str = ""
    wall_time_ms: float = 0.0

    def metadata(self) -> dict[str, object]:
        return {
            "execution_mode": "rootless-docker",
            "runtime_name": self.runtime_name,
            "participant_image_digest": self.participant_image_digest,
            "isolation_policy_digest": self.isolation_policy_digest,
            "network_policy_digest": self.network_policy_digest,
            "participant_isolation_verified": self.participant_isolation_verified,
            "oracle_visible_to_participant": self.oracle_visible_to_participant,
            "workspace_input_digest": self.workspace_input_digest,
            "workspace_output_digest": self.workspace_output_digest,
            "container_exit_status": self.container_exit_status,
            "container_cleanup_status": self.container_cleanup_status,
            "output_exceeded": self.output_exceeded,
        }


_ENV_NAME = r"^[A-Za-z_][A-Za-z0-9_]*$"
_SECRET_PARTS = (
    "API_KEY",
    "AUTH_TOKEN",
    "PASSWORD",
    "SECRET",
    "PRIVATE_KEY",
    "DSN",
    "SSH_",
    "REMOTE_",
    "OPENROUTER",
)
_PUBLIC_ENV_NAMES = frozenset(
    {"HOME", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "NO_COLOR", "TMPDIR"}
)


def _valid_env_name(name: str) -> bool:
    import re

    return bool(re.match(_ENV_NAME, name))


def _looks_like_secret_name(name: str) -> bool:
    upper = name.upper()
    if upper.startswith("AMB_CAPABILITY_"):
        return False
    return any(part in upper for part in _SECRET_PARTS)


def _safe_member_name(name: str) -> str:
    path = PurePosixPath(name)
    if not name or name in {".", ".."} or path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ArchiveSafetyError(f"unsafe archive path {name!r}")
    return path.as_posix()


def _regular_file(path: Path) -> os.stat_result:
    stat = path.lstat()
    if not statmod.S_ISREG(stat.st_mode) or stat.st_nlink > 1:
        raise ArchiveSafetyError(f"only single linked regular files are allowed: {path}")
    return stat


def archive_directory(
    source: str | Path,
    destination: str | Path,
    *,
    exclude_dirs: Sequence[str] = (".git", "__pycache__", ".pytest_cache", ".ruff_cache"),
    max_file_bytes: int = 64 * 1024 * 1024,
    max_total_bytes: int = 256 * 1024 * 1024,
) -> tuple[Path, str]:
    """Write a safe tar archive and return it with the source tree digest.

    Symlinks and special files are rejected rather than followed. This is important both for
    preventing a participant input escape and for ensuring the host never later follows a link
    created by a participant while extracting its output.
    """

    source_path = Path(source)
    if not source_path.is_dir() or not statmod.S_ISDIR(source_path.lstat().st_mode):
        raise ArchiveSafetyError(f"archive source must be a real directory: {source_path}")
    root = source_path.resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    target = Path(destination)
    if target.is_symlink() or (target.exists() and target.lstat().st_nlink > 1):
        raise ArchiveSafetyError(f"archive destination must not be a link: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    total_bytes = 0
    excluded = set(exclude_dirs)
    with tarfile.open(target, "w") as archive:
        for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            kept_dirs: list[str] = []
            for name in sorted(dirs):
                path = current_path / name
                stat = path.lstat()
                if name in excluded:
                    continue
                if not statmod.S_ISDIR(stat.st_mode):
                    raise ArchiveSafetyError(f"unsafe directory {path}")
                kept_dirs.append(name)
                rel = _safe_member_name(path.relative_to(root).as_posix())
                info = tarfile.TarInfo(rel)
                info.type = tarfile.DIRTYPE
                info.mode = stat.st_mode & 0o777
                info.mtime = 0
                archive.addfile(info)
            dirs[:] = kept_dirs
            for name in sorted(files):
                path = current_path / name
                stat = _regular_file(path)
                if stat.st_size > max_file_bytes:
                    raise ArchiveSafetyError(f"file exceeds archive limit: {path}")
                total_bytes += stat.st_size
                if total_bytes > max_total_bytes:
                    raise ArchiveSafetyError("directory contents exceed archive limit")
                rel = _safe_member_name(path.relative_to(root).as_posix())
                data = path.read_bytes()
                digest.update(rel.encode("utf-8"))
                digest.update(b"\0")
                digest.update(data)
                digest.update(b"\0")
                info = tarfile.TarInfo(rel)
                info.size = len(data)
                info.mode = stat.st_mode & 0o777
                info.mtime = 0
                archive.addfile(info, io.BytesIO(data))
    return target, digest.hexdigest()


def validate_archive(
    path: str | Path,
    *,
    max_members: int = 100_000,
    max_archive_bytes: int = 256 * 1024 * 1024,
) -> None:
    """Validate every tar member without extracting it."""

    if Path(path).stat().st_size > max_archive_bytes:
        raise ArchiveSafetyError("archive exceeds the configured size limit")
    seen: set[str] = set()
    kinds: dict[str, str] = {}
    total_bytes = 0
    with tarfile.open(path, "r") as archive:
        members = archive.getmembers()
        if len(members) > max_members:
            raise ArchiveSafetyError("archive contains too many members")
        for member in members:
            name = _safe_member_name(member.name)
            if name in seen:
                raise ArchiveSafetyError(f"duplicate archive path {name!r}")
            for parent in PurePosixPath(name).parents:
                parent_name = parent.as_posix()
                if parent_name == ".":
                    continue
                if kinds.get(parent_name) == "file":
                    raise ArchiveSafetyError(f"archive path is beneath a file: {name!r}")
            if any(
                existing.startswith(name + "/") and kind == "file"
                for existing, kind in kinds.items()
            ) and member.isfile():
                raise ArchiveSafetyError(f"archive path conflicts with a file subtree: {name!r}")
            seen.add(name)
            if not (member.isdir() or member.isfile()):
                raise ArchiveSafetyError(f"archive member is not a regular file or directory: {name}")
            kinds[name] = "dir" if member.isdir() else "file"
            if member.isfile() and member.size > 64 * 1024 * 1024:
                raise ArchiveSafetyError(f"archive member exceeds size limit: {name}")
            if member.isfile():
                total_bytes += member.size
                if total_bytes > 256 * 1024 * 1024:
                    raise ArchiveSafetyError("archive contents exceed the configured size limit")


def _assert_safe_existing_parents(target: Path, relative: str) -> None:
    current = target
    for part in PurePosixPath(relative).parts[:-1]:
        current = current / part
        if current.exists() or current.is_symlink():
            stat = current.lstat()
            if not statmod.S_ISDIR(stat.st_mode):
                raise ArchiveSafetyError(f"output would traverse a non-directory path: {relative}")


def extract_archive(
    source: str | Path,
    destination: str | Path,
    *,
    max_members: int = 100_000,
    merge: bool = False,
) -> str:
    """Safely extract an archive and return the digest of its regular files."""

    validate_archive(source, max_members=max_members)
    target = Path(destination)
    if target.exists() and any(target.iterdir()) and not merge:
        raise ArchiveSafetyError(f"archive destination is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with tarfile.open(source, "r") as archive:
        for member in archive.getmembers():
            name = _safe_member_name(member.name)
            _assert_safe_existing_parents(target, name)
            out = target / name
            if member.isdir():
                if (out.exists() or out.is_symlink()) and not statmod.S_ISDIR(out.lstat().st_mode):
                    raise ArchiveSafetyError(f"output would overwrite a non-directory path: {name}")
                out.mkdir(parents=True, exist_ok=True)
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            if (out.exists() or out.is_symlink()) and not statmod.S_ISREG(out.lstat().st_mode):
                raise ArchiveSafetyError(f"output would overwrite a non regular path: {name}")
            handle = archive.extractfile(member)
            if handle is None:
                raise ArchiveSafetyError(f"archive member cannot be read: {name}")
            data = handle.read(64 * 1024 * 1024 + 1)
            if len(data) > 64 * 1024 * 1024:
                raise ArchiveSafetyError(f"archive member exceeds size limit: {name}")
            digest.update(name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(data)
            digest.update(b"\0")
            out.write_bytes(data)
            os.chmod(out, member.mode & 0o777)
    return digest.hexdigest()


def safe_copy_tree(source: str | Path, destination: str | Path) -> str:
    """Copy a container output tree after rejecting links and special files."""

    root = Path(source)
    target = Path(destination)
    if not root.is_dir():
        raise ArchiveSafetyError(f"container output is not a directory: {root}")
    if target.exists() and any(target.iterdir()):
        raise ArchiveSafetyError(f"output destination is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for name in sorted(dirs):
            path = current_path / name
            stat = path.lstat()
            if not statmod.S_ISDIR(stat.st_mode):
                raise ArchiveSafetyError(f"unsafe container output directory {path}")
            kept_dirs.append(name)
            (target / path.relative_to(root)).mkdir(parents=True, exist_ok=True)
        dirs[:] = kept_dirs
        for name in sorted(files):
            path = current_path / name
            stat = _regular_file(path)
            if stat.st_size > 64 * 1024 * 1024:
                raise ArchiveSafetyError(f"container output file exceeds limit: {path}")
            rel = _safe_member_name(path.relative_to(root).as_posix())
            data = path.read_bytes()
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(data)
            digest.update(b"\0")
            out = target / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            os.chmod(out, stat.st_mode & 0o777)
    return digest.hexdigest()


def _run(runtime: str, args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [runtime, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    if check and result.returncode != 0:
        raise IsolationError(
            f"{runtime} {' '.join(args[:2])} failed with exit {result.returncode}: "
            f"{result.stderr[-1000:] or result.stdout[-1000:]}"
        )
    return result


def _stream_archive_to_container(runtime: str, name: str, archive: Path, destination: str) -> None:
    """Write a validated archive through stdin because docker cp cannot target read-only roots."""

    result = subprocess.run(
        [runtime, "exec", "-i", name, "tar", "-xf", "-", "-C", destination],
        input=archive.read_bytes(),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).decode("utf-8", errors="replace")[-1000:]
        raise IsolationError(
            f"{runtime} exec archive import failed with exit {result.returncode}: {detail}"
        )


def _stream_workspace_from_container(runtime: str, name: str, destination: Path) -> None:
    """Export workspace entries without docker cp, which cannot read rootless tmpfs reliably."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            runtime,
            "exec",
            name,
            "sh",
            "-c",
            "cd /workspace && find . -mindepth 1 -print0 | tar --null --files-from=- --create --file=-",
        ],
        stdout=destination.open("wb"),
        stderr=subprocess.PIPE,
    )
    _, stderr = process.communicate()
    try:
        if destination.stat().st_size > 256 * 1024 * 1024:
            raise ArchiveSafetyError("container output archive exceeds the configured size limit")
        if process.returncode != 0:
            detail = (stderr or b"").decode("utf-8", errors="replace")[-1000:]
            raise IsolationError(
                f"{runtime} workspace export failed with exit {process.returncode}: {detail}"
            )
    finally:
        if process.returncode != 0 or destination.stat().st_size > 256 * 1024 * 1024:
            destination.unlink(missing_ok=True)


def _assert_rootless(runtime: str) -> None:
    if shutil.which(runtime) is None:
        raise IsolationError(f"{runtime} is not installed")
    result = _run(runtime, ["info", "--format", "{{json .SecurityOptions}}"])
    try:
        options = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise IsolationError("Docker did not return a readable security policy") from error
    text = json.dumps(options).lower()
    if "rootless" not in text:
        raise IsolationError("Docker daemon is not rootless; refusing participant execution")


def _container_args(spec: ParticipantSpec, name: str) -> list[str]:
    policy = spec.policy
    args = [
        "create",
        "--name",
        name,
        "--user",
        policy.user,
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--ipc=private",
        "--pids-limit",
        str(policy.pids_limit),
        "--memory",
        policy.memory,
        "--memory-swap",
        policy.memory,
        "--cpus",
        policy.cpu,
        "--network",
        policy.network,
        "--workdir",
        "/workspace",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=256m",
        "--tmpfs",
        "/run:rw,nosuid,nodev,size=16m",
        "--tmpfs",
        "/workspace:rw,nosuid,nodev,size=512m,mode=1777",
        "--tmpfs",
        "/session:rw,nosuid,nodev,size=64m,mode=1777",
    ]
    for key, value in {**spec.public_env, **spec.capability_grants}.items():
        args.extend(("--env", f"{key}={value}"))
    image = policy.image
    if policy.image_digest and not _is_pinned_image_reference(image):
        image = f"{image}@{policy.image_digest}"
    if not _is_pinned_image_reference(image):
        raise IsolationError("participant image must be pinned by digest")
    args.extend((image, "sleep", "infinity"))
    return args


def _pinned_image(image: str, digest: str, *, label: str) -> str:
    resolved = image
    if digest and not _is_pinned_image_reference(resolved):
        resolved = f"{resolved}@{digest}"
    if not _is_pinned_image_reference(resolved):
        raise IsolationError(f"{label} image must be pinned by digest")
    return resolved


def default_participant_policy() -> IsolationPolicy:
    """Build the production participant policy from nonsecret deployment configuration."""

    return IsolationPolicy(
        image=os.environ.get("AMB_PARTICIPANT_IMAGE", "agent-memory-bench-participant"),
        image_digest=os.environ.get("AMB_PARTICIPANT_IMAGE_DIGEST", ""),
        network=os.environ.get("AMB_BROKER_NETWORK", "amb-broker-net"),
        network_policy_digest=os.environ.get("AMB_NETWORK_POLICY_DIGEST", ""),
        memory=os.environ.get("AMB_PARTICIPANT_MEMORY", "2g"),
        cpu=os.environ.get("AMB_PARTICIPANT_CPUS", "2"),
        pids_limit=int(os.environ.get("AMB_PARTICIPANT_PIDS_LIMIT", "256")),
        timeout_s=float(os.environ.get("AMB_PARTICIPANT_TIMEOUT_S", "1800")),
        max_output_bytes=int(os.environ.get("AMB_PARTICIPANT_MAX_OUTPUT_BYTES", str(8 * 1024 * 1024))),
    )


def _read_bounded(path: Path, limit: int) -> tuple[str, bool]:
    data = path.read_bytes()
    exceeded = len(data) > limit
    return data[:limit].decode("utf-8", errors="replace"), exceeded


def _redact_tree(root: Path, secrets: Sequence[str]) -> None:
    """Remove capability values from participant output before it becomes a record artifact."""

    needles = [value.encode("utf-8") for value in secrets if value]
    for current, _, files in os.walk(root, topdown=True, followlinks=False):
        for name in files:
            path = Path(current) / name
            stat = _regular_file(path)
            if stat.st_size > 64 * 1024 * 1024:
                raise ArchiveSafetyError(f"container output file exceeds limit: {path}")
            data = path.read_bytes()
            for needle in needles:
                data = data.replace(needle, b"[REDACTED_CAPABILITY]")
            if data != path.read_bytes():
                path.write_bytes(data)


def _redact_text(value: str, secrets: Sequence[str]) -> str:
    for secret in secrets:
        if secret:
            value = value.replace(secret, "[REDACTED_CAPABILITY]")
    return value


def run_isolated_session(spec: ParticipantSpec) -> ParticipantResult:
    """Run one participant session in a disposable rootless Docker container."""

    _assert_rootless(spec.policy.runtime)
    validate_archive(spec.workspace_archive)
    if spec.config_archive is not None:
        validate_archive(spec.config_archive)

    runtime = spec.policy.runtime
    name = f"amb-participant-{uuid.uuid4().hex}"
    with tempfile.TemporaryDirectory(prefix="amb-isolation-") as temp_name:
        temp = Path(temp_name)
        stdout_path = temp / "stdout"
        stderr_path = temp / "stderr"
        raw_output = temp / "container-output"
        raw_output.mkdir()
        input_digest = spec.workspace_digest or hashlib.sha256(spec.workspace_archive.read_bytes()).hexdigest()
        cleanup_ok = False
        timed_out = False
        output_exceeded = False
        returncode: int | None = None
        exit_status = "not_started"
        started = time.perf_counter()
        result: ParticipantResult | None = None
        try:
            _run(runtime, _container_args(spec, name))
            _run(runtime, ["start", name])
            _stream_archive_to_container(runtime, name, spec.workspace_archive, "/workspace")
            if spec.config_archive is not None:
                _stream_archive_to_container(runtime, name, spec.config_archive, "/session")

            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                process = subprocess.Popen(
                    [runtime, "exec", name, *spec.command],
                    stdout=stdout,
                    stderr=stderr,
                )
                deadline = time.monotonic() + spec.policy.timeout_s
                while process.poll() is None:
                    if time.monotonic() >= deadline:
                        timed_out = True
                        _run(runtime, ["stop", "--time", "0", name], check=False)
                        with contextlib.suppress(ProcessLookupError):
                            process.kill()
                        break
                    if stdout_path.stat().st_size + stderr_path.stat().st_size > spec.policy.max_output_bytes:
                        output_exceeded = True
                        _run(runtime, ["stop", "--time", "0", name], check=False)
                        with contextlib.suppress(ProcessLookupError):
                            process.kill()
                        break
                    time.sleep(0.05)
                process.wait(timeout=10)
            returncode = process.returncode if not timed_out else None
            exit_status = "timed_out" if timed_out else "exited"
            if timed_out or output_exceeded:
                # Timeout enforcement stops the complete tree. Docker preserves tmpfs contents
                # across a restart of the disposable container, allowing validated extraction.
                _run(runtime, ["start", name], check=False)
            container_output_archive = temp / "container-output.tar"
            _stream_workspace_from_container(runtime, name, container_output_archive)
            extract_archive(container_output_archive, raw_output)
            _run(runtime, ["stop", "--time", "0", name], check=False)
            _redact_tree(raw_output, tuple(spec.capability_grants.values()))
            output_archive = temp / "workspace-output.tar"
            output_archive, output_digest = archive_directory(raw_output, output_archive)
            # Keep the archive only until the caller copies it. The path is materialised below.
            retained = Path(spec.workspace_archive).parent / f"{spec.task_id}.s{spec.seed}.{spec.arm}.output.tar"
            shutil.copy2(output_archive, retained)
            stdout_text, stdout_exceeded = _read_bounded(stdout_path, spec.policy.max_output_bytes)
            stderr_text, stderr_exceeded = _read_bounded(stderr_path, spec.policy.max_output_bytes)
            output_exceeded = output_exceeded or stdout_exceeded or stderr_exceeded
            result = ParticipantResult(
                returncode=returncode,
                stdout=_redact_text(stdout_text, tuple(spec.capability_grants.values())),
                stderr=_redact_text(stderr_text, tuple(spec.capability_grants.values())),
                timed_out=timed_out,
                output_archive=retained,
                workspace_input_digest=input_digest,
                workspace_output_digest=output_digest,
                container_exit_status=exit_status,
                container_cleanup_status="pending",
                participant_isolation_verified=True,
                output_exceeded=output_exceeded,
                runtime_name=spec.policy.runtime,
                participant_image_digest=spec.policy.effective_image_digest,
                isolation_policy_digest=spec.policy.digest,
                network_policy_digest=spec.policy.network_policy_digest,
                wall_time_ms=(time.perf_counter() - started) * 1000.0,
            )
        finally:
            removed = _run(runtime, ["rm", "-f", name], check=False)
            cleanup_ok = removed.returncode == 0
        if result is None:
            raise IsolationError("participant container did not produce a result")
        return ParticipantResult(
            **{
                **result.__dict__,
                "container_cleanup_status": "removed" if cleanup_ok else "failed",
            }
        )


def run_isolated_checker(
    task_id: str,
    oracle_dir: str | Path,
    artifact_dir: str | Path,
    *,
    timeout_s: float = 120.0,
    image: str | None = None,
    runtime: str = "docker",
) -> tuple[bool, str]:
    """Run the trusted checker worker after the participant container has exited."""

    if timeout_s <= 0:
        raise ValueError("checker timeout must be positive")
    _assert_rootless(runtime)
    checker_image = image or os.environ.get(
        "AMB_CHECKER_IMAGE", "agent-memory-bench-checker"
    )
    checker_image = _pinned_image(
        checker_image,
        os.environ.get("AMB_CHECKER_IMAGE_DIGEST", ""),
        label="checker",
    )
    with tempfile.TemporaryDirectory(prefix="amb-checker-") as temp_name:
        temp = Path(temp_name)
        artifact_archive, _ = archive_directory(artifact_dir, temp / "artifact.tar")
        oracle_archive, _ = archive_directory(oracle_dir, temp / "oracle.tar")
        artifact_stage = temp / "artifact"
        oracle_stage = temp / "oracle"
        extract_archive(artifact_archive, artifact_stage)
        extract_archive(oracle_archive, oracle_stage)
        name = f"amb-checker-{uuid.uuid4().hex}"
        try:
            create = [
                "create",
                "--name",
                name,
                "--user",
                "65532:65532",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--ipc=private",
                "--pids-limit",
                "256",
                "--memory",
                "1g",
                "--memory-swap",
                "1g",
                "--network",
                "none",
                "--env",
                "PYTHONPATH=/bench",
                "--workdir",
                "/artifact",
                "--mount",
                f"type=bind,src={artifact_stage},dst=/artifact,readonly",
                "--mount",
                f"type=bind,src={oracle_stage},dst=/oracle,readonly",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,nodev,size=256m",
                checker_image,
                "sleep",
                "infinity",
            ]
            _run(runtime, create)
            _run(runtime, ["start", name])
            request = json.dumps(
                {"task_id": task_id, "artifact": "/artifact", "oracle_root": "/oracle"}
            )
            process = subprocess.Popen(
                [runtime, "exec", "-i", name, "python", "-m", "harness.checker_worker"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            try:
                stdout, stderr = process.communicate(request, timeout=timeout_s)
            except subprocess.TimeoutExpired:
                _run(runtime, ["stop", "--time", "0", name], check=False)
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                process.wait(timeout=10)
                raise IsolationError("checker worker timed out") from None
            if process.returncode != 0:
                raise IsolationError(
                    f"checker worker exited {process.returncode}: {stderr[-1000:] or stdout[-1000:]}"
                )
            lines = [line for line in stdout.splitlines() if line.strip()]
            if len(lines) != 1:
                raise IsolationError("checker worker returned something other than one JSON object")
            try:
                response = json.loads(lines[0])
            except json.JSONDecodeError as error:
                raise IsolationError("checker worker returned malformed JSON") from error
            if not isinstance(response, dict):
                raise IsolationError("checker worker response is not an object")
            if response.get("checker_status") != "completed":
                raise IsolationError(
                    f"checker worker infrastructure error: {response.get('diagnostics', {})}"
                )
            if not isinstance(response.get("ok"), bool):
                raise IsolationError("checker worker response has no boolean ok field")
            if not isinstance(response.get("verdict"), str):
                raise IsolationError("checker worker response has no string verdict field")
            if not isinstance(response.get("timed_out"), bool):
                raise IsolationError("checker worker response has no boolean timed_out field")
            return bool(response.get("ok")), str(response.get("verdict", ""))
        finally:
            _run(runtime, ["rm", "-f", name], check=False)


def _container_path(path: str | Path, *, directory: str, name: str) -> str:
    """Map one generated host file to its fixed path inside the participant container."""

    return f"/{directory}/{name}"


def _rewrite_workspace_argument(value: str, source: Path) -> str:
    """Map a known workspace path into the container and reject every other host path."""

    if value == str(source):
        return "/workspace"
    candidate = Path(value)
    if not candidate.is_absolute():
        return value
    try:
        relative = candidate.resolve().relative_to(source.resolve())
    except ValueError as error:
        raise IsolationError(f"participant argument contains an unexpected host path: {value}") from error
    return PurePosixPath("/workspace", *relative.parts).as_posix()


def _copy_config_archive(
    config,
    destination: Path,
    *,
    memory_capability: str | None = None,
) -> tuple[Path | None, str | None, str | None]:
    """Copy only secretless Claude configuration into an archive staging directory."""

    root = destination / "config"
    root.mkdir(parents=True, exist_ok=True)
    secret_values = {
        str(value).encode("utf-8")
        for key, value in getattr(config, "env", {}).items()
        if str(value) and _looks_like_secret_name(str(key))
    }
    secret_values.update(
        str(value).encode("utf-8")
        for key, value in os.environ.items()
        if str(value) and _looks_like_secret_name(str(key))
    )
    mcp_path = None
    prompt_path = None
    config_dir_path = None
    if config.mcp_config is not None:
        source = Path(config.mcp_config)
        data = json.loads(source.read_text(encoding="utf-8"))
        memory_token = memory_capability or os.environ.get("AMB_CAPABILITY_MEMORY", "")
        if not memory_token:
            raise IsolationError(
                "AMB_CAPABILITY_MEMORY is unset; MCP sessions must use the memory broker"
            )
        controller_secrets = {
            str(value)
            for key, value in os.environ.items()
            if _looks_like_secret_name(str(key)) and value
        }
        if memory_token in controller_secrets or memory_token.startswith(("sk-", "or-")):
            raise IsolationError("AMB_CAPABILITY_MEMORY contains a provider credential")
        broker_url = os.environ.get("AMB_MEMORY_BROKER_URL", "http://memory-broker:8080")
        prefix = str(getattr(config, "memory_tool_prefix", "mcp__"))
        allowed_tools = sorted(
            {
                str(item).removeprefix(prefix)
                for item in (
                    getattr(config, "extra_allowed_tools", ())
                    or getattr(config, "allowed_tools", ())
                )
                if str(item).startswith(prefix)
            }
        )
        servers = data.get("mcpServers") or {}
        if not isinstance(servers, dict):
            raise IsolationError("MCP configuration must contain an object mcpServers")
        # Replace each adapter's stdio process with the fixed, credentialless relay. The original
        # command, arguments, host paths, and environment are trusted-controller inputs and do
        # not cross the boundary.
        data["mcpServers"] = {
            str(name): {
                "command": "/usr/local/bin/python",
                "args": ["/usr/local/bin/mcp-relay"],
                "env": {
                    "AMB_MEMORY_RELAY_URL": broker_url,
                    "AMB_ALLOWED_TOOLS": ",".join(allowed_tools),
                },
            }
            for name in servers
        }
        mcp_path = root / "mcp.json"
        mcp_path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    if config.append_system_prompt_file is not None:
        source = Path(config.append_system_prompt_file)
        prompt_path = root / "prompt.md"
        prompt_path.write_bytes(source.read_bytes())
    if config.config_dir is not None:
        source = Path(config.config_dir)
        config_dir_path = root / "claude-config"
        shutil.copytree(source, config_dir_path, symlinks=True)
        for current, _, files in os.walk(config_dir_path):
            for name in files:
                if name.lower() in {".env", ".env.local", "credentials", "secrets", "token"}:
                    raise IsolationError(
                        f"Claude configuration {source} contains a secret-bearing file {name!r}"
                    )
                blob = (Path(current) / name).read_bytes()
                if any(value in blob for value in secret_values):
                    raise IsolationError(
                        f"Claude configuration {source} contains a credential; use a brokered "
                        "integration"
                    )
    archive, _ = archive_directory(root, destination / "config.tar")
    return archive, mcp_path, prompt_path


def run_isolated_claude_case(
    row: Mapping[str, object],
    arm: str,
    config,
    *,
    workspace_digest: str = "",
    workspace_archive: Path | None = None,
    policy: IsolationPolicy | None = None,
    model_capability: str | None = None,
    memory_capability: str | None = None,
):
    """Run Claude with a secretless configuration inside the participant container.

    Adapters must provide broker URLs and capability names through public configuration. Any
    legacy adapter that still places an API key, DSN, SSH location, or provider token in its
    generated configuration is rejected before Claude starts.
    """

    from .claude_exec import ClaudeExecConfig, build_record
    from .sandbox import export_container_input, extract_container_output

    if config.cwd is None:
        raise IsolationError("an isolated Claude case requires a workspace cwd")
    model_token = model_capability or os.environ.get("AMB_CAPABILITY_MODEL", "")
    if not model_token:
        raise IsolationError(
            "AMB_CAPABILITY_MODEL is unset; production sessions must use the model broker"
        )
    controller_secret_values = {
        str(value)
        for key, value in os.environ.items()
        if _looks_like_secret_name(str(key)) and value
    }
    if model_token in controller_secret_values or model_token.startswith(("sk-", "or-")):
        raise IsolationError("AMB_CAPABILITY_MODEL contains a provider credential, not a capability")
    source_workspace = Path(config.cwd)
    work_parent = source_workspace.parent
    work_parent.mkdir(parents=True, exist_ok=True)
    input_archive = workspace_archive or work_parent / f".amb-input-{arm}-{int(row.get('seed', 0))}.tar"
    if workspace_archive is None:
        export_container_input(
            source_workspace,
            input_archive,
            workspace_digest=workspace_digest,
        )

    with tempfile.TemporaryDirectory(prefix="amb-config-") as config_temp:
        config_archive, _mcp_path, _prompt_path = _copy_config_archive(
            config, Path(config_temp), memory_capability=memory_capability
        )
        command = list(config.command(str(row.get("user_input", "")).strip()))
        if not command:
            raise IsolationError("Claude command is empty")
        command[0] = "/usr/local/bin/claude"
        for index, value in enumerate(command):
            if value == str(config.mcp_config):
                command[index] = _container_path(value, directory="session", name="mcp.json")
            elif value == str(config.append_system_prompt_file):
                command[index] = _container_path(value, directory="session", name="prompt.md")
            elif value == str(config.config_dir):
                command[index] = "/session/claude-config"
            else:
                command[index] = _rewrite_workspace_argument(value, source_workspace)
        public_env = {
            str(key): str(value)
            for key, value in config.env.items()
            if (
                not _looks_like_secret_name(str(key))
                and (str(key) in _PUBLIC_ENV_NAMES or str(key).startswith("AMB_PUBLIC_"))
            )
        }
        public_env.setdefault("HOME", "/tmp")
        public_env.setdefault("TMPDIR", "/tmp")
        public_env.update(
            {
                str(key): str(value)
                for key, value in getattr(config, "public_container_env", {}).items()
                if not _looks_like_secret_name(str(key))
            }
        )
        public_env["ANTHROPIC_AUTH_TOKEN"] = model_token
        if config.config_dir is not None:
            public_env["CLAUDE_CONFIG_DIR"] = "/session/claude-config"
        # The model capability is deliberately not called a provider credential, but Claude's
        # client needs the conventional variable. The value is a scoped broker token, not the
        # upstream API key.
        public_env["ANTHROPIC_AUTH_TOKEN"] = model_token
        public_env["ANTHROPIC_BASE_URL"] = os.environ.get(
            "AMB_MODEL_BROKER_URL", "http://model-broker:8080"
        )
        if config.mcp_config is not None:
            public_env["AMB_CAPABILITY_MEMORY"] = memory_capability or os.environ.get(
                "AMB_CAPABILITY_MEMORY", ""
            )
        participant_config = ClaudeExecConfig(
            model=config.model,
            memory_tool_prefix=config.memory_tool_prefix,
            strict_mcp_config=config.strict_mcp_config,
            bare=config.bare,
        )
        participant_policy = policy or default_participant_policy()
        if policy is None and getattr(config, "timeout_s", None):
            participant_policy = replace(participant_policy, timeout_s=float(config.timeout_s))
        spec = ParticipantSpec(
            task_id=str(row["task_id"]),
            arm=arm,
            seed=int(row.get("seed", 0)),
            workspace_archive=input_archive,
            config_archive=config_archive,
            command=tuple(command),
            public_env=public_env,
            capability_grants={"AMB_CAPABILITY_MODEL": model_token},
            workspace_digest=workspace_digest,
            policy=participant_policy,
        )
        result = run_isolated_session(spec)
        if result.output_archive is None:
            raise IsolationError("participant produced no workspace archive")
        output_digest = extract_container_output(result.output_archive, source_workspace)
        stream = result.stdout
        if config.stream_dir is not None:
            stream_dir = Path(config.stream_dir)
            stream_dir.mkdir(parents=True, exist_ok=True)
            safe_task = str(row["task_id"]).replace("/", "_").replace("\\", "_")
            stream_path = stream_dir / f"{safe_task}.s{int(row.get('seed', 0))}.{arm}.jsonl.gz"
            with gzip.open(stream_path, "wt", encoding="utf-8") as handle:
                handle.write(stream)
        record = build_record(
            row,
            arm,
            stream=stream,
            wall_time_ms=result.wall_time_ms,
            config=participant_config,
            command=command,
            exit_code=result.returncode,
            stderr=result.stderr,
        )
        metadata = {
            **record.metadata,
            **result.metadata(),
            "workspace_output_digest": output_digest,
            "checker_image_digest": os.environ.get("AMB_CHECKER_IMAGE_DIGEST", ""),
        }
        return record.__class__.from_mapping({**record.to_dict(), "metadata": metadata})
