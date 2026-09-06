"""Run every private AMB challenge task with one fixed evaluator agent command.

Example:
    python -m scripts.evaluate_challenge --pack /private/amb-pack \
        --submission submission.json --output-root /private/amb-output \
        --runtime-root /private/amb-runtime --public-manifest public.json \
        --private-manifest private.json --policy /private/amb-policy.json \
        --agent-command \
        "python /evaluator/fixed_agent.py"

The agent command is supplied by the evaluator, not by an entrant image. It receives explicit
task and adapter environment variables and runs without a shell under a bounded process tree.
Provider credentials must be injected through the evaluator's approved environment policy, never
through the submission descriptor.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.challenge_agent import make_command_agent_runner
from harness.challenge_evaluator import ChallengeEvaluatorError, evaluate_submission
from harness.challenge_pack import ChallengePackError, load_private_pack, load_submission
from harness.challenge_pack_audit import ChallengePackLeakageError, audit_pack_corpus
from harness.challenge_policy import ChallengePolicyError, agent_command_digest, load_policy
from harness.challenge_release import hash_private_pack
from harness.challenge_rules import (
    ChallengeRulesError,
    load_rules,
    rules_digest,
    validate_rules_for_task_ids,
)
from harness.challenge_scoring import ChallengeScoringError, write_score_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--public-manifest", required=True, type=Path)
    parser.add_argument("--private-manifest", required=True, type=Path)
    parser.add_argument("--agent-command", required=True)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--rules", required=True, type=Path)
    parser.add_argument("--evaluator-revision", required=True)
    parser.add_argument("--model-proxy-socket", type=Path)
    args = parser.parse_args()

    try:
        command = shlex.split(args.agent_command, posix=True)
        if not command:
            raise ChallengeEvaluatorError("agent command must not be empty")
        policy = load_policy(args.policy, require_frozen=True)
        if agent_command_digest(command) != policy.agent_command_sha256:
            raise ChallengePolicyError("agent command does not match the frozen policy digest")
        pack = load_private_pack(args.pack)
        audit_pack_corpus(pack)
        rules = load_rules(args.rules, require_final=True)
        validate_rules_for_task_ids(rules, (task.task_id for task in pack.tasks))
        if policy.infrastructure_retries != rules["infrastructure_retry_count"]:
            raise ChallengeRulesError(
                "policy and rules infrastructure retry counts must match"
            )
        submission = load_submission(args.submission)
        public, private = evaluate_submission(
            pack,
            submission,
            args.output_root,
            args.runtime_root,
            make_command_agent_runner(
                command,
                timeout_seconds=policy.agent_timeout_seconds,
                extra_env={
                    "AMB_MODEL_ID": policy.model_id,
                    "AMB_PROVIDER_ID": policy.provider_id,
                    "AMB_TEMPERATURE": str(policy.temperature),
                    "AMB_CONTEXT_LIMIT_TOKENS": str(policy.context_limit_tokens),
                    **(
                        {"AMB_MODEL_PROXY_SOCKET": str(args.model_proxy_socket)}
                        if args.model_proxy_socket is not None
                        else {}
                    ),
                },
            ),
            checker_timeout_s=policy.checker_timeout_seconds,
            pack_digest=hash_private_pack(pack),
            rules_digest=rules_digest(rules),
            evaluator_revision=args.evaluator_revision,
            model_proxy_socket=args.model_proxy_socket,
            adapter_call_budget=policy.adapter_call_budget,
            infrastructure_retries=policy.infrastructure_retries,
        )
        public["policy_digest"] = policy.digest()
        private["policy_digest"] = policy.digest()
        write_score_manifest(args.public_manifest, public)
        write_score_manifest(args.private_manifest, private)
    except (
        ChallengePackError,
        ChallengePackLeakageError,
        ChallengePolicyError,
        ChallengeRulesError,
        ChallengeEvaluatorError,
        ChallengeScoringError,
    ) as error:
        print(f"challenge evaluation failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps(public, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
