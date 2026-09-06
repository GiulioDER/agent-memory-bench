"""Run a hostile Docker probe against the AMB challenge mount and network policy."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.challenge_pack import (
    IMAGE_DIGEST,
    ChallengePack,
    ChallengeSubmission,
    build_execution_plan,
    load_private_pack,
)
from harness.challenge_redteam import audit_docker_argv, audit_plan, write_red_team_report
from harness.challenge_runner import (
    ChallengeRunnerError,
    build_adapter_service_argv,
    build_docker_argv,
    run_challenge_task,
)


def _image_digest(image: str, docker_binary: str) -> str:
    if "@sha256:" in image:
        if not IMAGE_DIGEST.fullmatch(image):
            raise ChallengeRunnerError(f"image must use a valid immutable digest: {image!r}")
        return image
    completed = subprocess.run(
        [docker_binary, "image", "inspect", image, "--format", "{{index .RepoDigests 0}}"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    digest = completed.stdout.strip()
    if completed.returncode != 0 or not IMAGE_DIGEST.fullmatch(digest):
        raise ChallengeRunnerError(
            f"image must be available locally with a repository digest: {image!r}"
        )
    return digest


def _write_probe_pack(root: Path) -> ChallengePack:
    for relative in (
        "corpus/public.txt",
        "fixtures/task-a/visible.txt",
        "prompts/task-a.txt",
        "checkers/task-a/checker.py",
        "oracles/task-a/private.txt",
        "references/task-a/private.txt",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")
    (root / "pack.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "kind": "amb-private-evaluation-pack",
                "visibility": "private",
                "pack_id": "red-team-probe",
                "source_public_commit": "probe",
                "scoring_version": "probe",
                "corpus": "corpus",
                "tasks": [
                    {
                        "task_id": "task-a",
                        "fixture": "fixtures/task-a",
                        "prompt": "prompts/task-a.txt",
                        "checker": "checkers/task-a/checker.py",
                        "oracle": "oracles/task-a",
                        "reference": "references/task-a",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return load_private_pack(root)


def _submission(image: str) -> ChallengeSubmission:
    return ChallengeSubmission(
        submission_id="red-team",
        image=image,
        source_revision="probe",
        adapter_api="amb-challenge-adapter-v1",
        config_sha256="0" * 64,
        network="none",
        entrypoint=(
            "/bin/sh",
            "-c",
            (
                "set -eu; "
                "test -f /challenge/task/visible.txt; "
                "test -f /challenge/prompt.txt; "
                "test -f /challenge/corpus/public.txt; "
                "test ! -e /challenge/checkers; "
                "test ! -e /challenge/oracles; "
                "test ! -e /challenge/references; "
                "test ! -e /challenge/private; "
                "test ! -e /challenge/hidden-answer; "
                "test \"$(awk 'NR > 1 && NF { print; exit }' /proc/net/route)\" = \"\"; "
                "env > /challenge/output/environment.txt; "
                "! grep -Eq 'OPENAI_API_KEY|DATABASE_URL|DOCKER_HOST' "
                "/challenge/output/environment.txt; "
                "printf 'pass\\n' > /challenge/output/red-team.txt"
            ),
        ),
    )


def _run_sidecar_probe(pack: ChallengePack, submission: ChallengeSubmission, docker_binary: str, root: Path) -> None:
    output_root = root / "sidecar-output"
    runtime_root = root / "sidecar-runtime"
    output_root.mkdir()
    runtime_root.mkdir()
    plan = build_execution_plan(pack, submission, "task-a")
    argv = build_adapter_service_argv(
        pack,
        plan,
        output_root,
        runtime_root,
        container_name="amb-red-team-sidecar",
        docker_binary=docker_binary,
    )
    audit_docker_argv(argv, sidecar=True)
    script = (
        "set -eu; "
        "test -f /challenge/corpus/public.txt; "
        "test ! -e /challenge/task; "
        "test ! -e /challenge/prompt.txt; "
        "test ! -e /challenge/output; "
        "test ! -e /challenge/checkers; "
        "touch /challenge/runtime/sidecar-probe.txt"
    )
    argv[-1] = script
    completed = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=30)
    if completed.returncode != 0:
        raise ChallengeRunnerError(f"sidecar red team probe failed: {completed.stderr[-500:]}")
    if any(output_root.rglob("*")):
        raise ChallengeRunnerError("sidecar red team probe modified the result directory")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="ubuntu:24.04")
    parser.add_argument("--docker-binary", default="docker")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        image = _image_digest(args.image, args.docker_binary)
        with tempfile.TemporaryDirectory(prefix="amb-red-team-") as temporary:
            root = Path(temporary)
            pack = _write_probe_pack(root / "pack")
            submission = _submission(image)
            plan = build_execution_plan(pack, submission, "task-a")
            argv = build_docker_argv(
                pack,
                plan,
                root / "output",
                container_name="amb-red-team-task",
                docker_binary=args.docker_binary,
            )
            audit_plan(plan)
            audit_docker_argv(argv)
            result = run_challenge_task(
                pack,
                submission,
                "task-a",
                root / "output",
                timeout_seconds=30,
                docker_binary=args.docker_binary,
            )
            artifact = root / "output" / "red-team" / "task-a" / "red-team.txt"
            if result.returncode != 0 or not artifact.is_file():
                raise ChallengeRunnerError(f"one shot red team probe failed: {result.to_dict()}")
            _run_sidecar_probe(pack, submission, args.docker_binary, root)
    except (ChallengeRunnerError, OSError, subprocess.SubprocessError) as error:
        print(f"challenge Docker red team failed: {error}", file=sys.stderr)
        return 1
    report = {"schema": 1, "kind": "amb-challenge-red-team-report", "status": "pass", "image": image}
    if args.report is not None:
        write_red_team_report(args.report, image)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
