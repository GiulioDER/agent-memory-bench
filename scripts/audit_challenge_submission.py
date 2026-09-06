"""Run static red team checks against every task command for a challenge submission."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.challenge_pack import (
    ChallengePackError,
    build_execution_plan,
    load_private_pack,
    load_submission,
)
from harness.challenge_redteam import (
    ChallengeRedTeamError,
    audit_docker_argv,
    audit_plan,
)
from harness.challenge_runner import (
    ChallengeRunnerError,
    build_adapter_service_argv,
    build_docker_argv,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--model-proxy-socket", type=Path)
    args = parser.parse_args()
    try:
        pack = load_private_pack(args.pack)
        submission = load_submission(args.submission)
        rows = []
        for task in pack.tasks:
            plan = build_execution_plan(pack, submission, task.task_id)
            one_shot = build_docker_argv(
                pack,
                plan,
                args.output_root,
                container_name=f"amb-audit-task-{task.task_id}",
                model_proxy_socket=args.model_proxy_socket,
            )
            sidecar = build_adapter_service_argv(
                pack,
                plan,
                args.output_root,
                args.runtime_root / task.task_id,
                container_name=f"amb-audit-adapter-{task.task_id}",
                model_proxy_socket=args.model_proxy_socket,
            )
            audit_plan(plan)
            audit_docker_argv(one_shot)
            audit_docker_argv(sidecar, sidecar=True)
            rows.append({"task_id": task.task_id, "one_shot": "pass", "sidecar": "pass"})
    except (ChallengePackError, ChallengeRedTeamError, ChallengeRunnerError) as error:
        print(f"challenge red team audit failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"audited_tasks": rows, "status": "pass"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
