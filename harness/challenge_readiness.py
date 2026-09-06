"""Evaluate all machine checkable AMB challenge release gates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .challenge_baselines import ChallengeBaselineError, verify_baseline_ordering
from .challenge_pack import ChallengePackError, load_private_pack
from .challenge_pack_audit import ChallengePackLeakageError, audit_pack_corpus
from .challenge_policy import ChallengePolicyError, load_policy
from .challenge_release import build_release_manifest, hash_private_pack
from .challenge_rules import (
    ChallengeRulesError,
    load_rules,
    rules_digest,
    validate_rules_for_task_ids,
)


@dataclass(frozen=True)
class ChallengeReadinessGate:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"JSON object required: {path}")
    return data


def evaluate_readiness(
    pack_path: str | Path,
    policy_path: str | Path,
    rules_path: str | Path,
    *,
    release_path: str | Path | None = None,
    baseline_path: str | Path | None = None,
    deliberately_bad_path: str | Path | None = None,
    evaluator_revision: str | None = None,
) -> tuple[ChallengeReadinessGate, ...]:
    """Return every gate result without hiding a missing external prerequisite."""

    gates: list[ChallengeReadinessGate] = []
    pack = None
    policy = None
    rules = None
    rules_match_pack = False
    try:
        pack = load_private_pack(pack_path)
        gates.append(ChallengeReadinessGate("private_pack", True, f"{len(pack.tasks)} task(s)"))
    except (ChallengePackError, OSError, ValueError) as error:
        gates.append(ChallengeReadinessGate("private_pack", False, str(error)))
    if pack is not None:
        try:
            report = audit_pack_corpus(pack)
            gates.append(ChallengeReadinessGate("corpus_leakage", True, json.dumps(report.to_dict(), sort_keys=True)))
        except (ChallengePackLeakageError, OSError, ValueError) as error:
            gates.append(ChallengeReadinessGate("corpus_leakage", False, str(error)))
    else:
        gates.append(ChallengeReadinessGate("corpus_leakage", False, "private pack is unavailable"))
    try:
        policy = load_policy(policy_path, require_frozen=True)
        gates.append(ChallengeReadinessGate("evaluation_policy", True, policy.digest()))
    except (ChallengePolicyError, OSError, ValueError) as error:
        gates.append(ChallengeReadinessGate("evaluation_policy", False, str(error)))
    try:
        rules = load_rules(rules_path, require_final=True)
        if pack is not None:
            validate_rules_for_task_ids(rules, (task.task_id for task in pack.tasks))
        if policy is not None and policy.infrastructure_retries != rules["infrastructure_retry_count"]:
            raise ChallengeRulesError(
                "policy and rules infrastructure retry counts must match"
            )
        if pack is not None:
            rules_match_pack = True
        gates.append(ChallengeReadinessGate("final_rules", True, rules_digest(rules)))
    except (ChallengeRulesError, OSError, ValueError) as error:
        gates.append(ChallengeReadinessGate("final_rules", False, str(error)))

    if pack is not None and policy is not None and rules is not None and rules_match_pack:
        if release_path is None:
            gates.append(ChallengeReadinessGate("release_record", False, "release record was not supplied"))
        elif evaluator_revision is None:
            gates.append(ChallengeReadinessGate("release_record", False, "evaluator revision was not supplied"))
        else:
            try:
                expected = build_release_manifest(
                    pack,
                    policy,
                    rules,
                    evaluator_revision=evaluator_revision,
                )
                release = _read_json(Path(release_path))
                mismatches = [
                    field
                    for field in sorted(set(expected) | set(release))
                    if release.get(field) != expected.get(field)
                ]
                gates.append(
                    ChallengeReadinessGate(
                        "release_record",
                        not mismatches,
                        "matching frozen hashes" if not mismatches else f"mismatched fields: {mismatches}",
                    )
                )
            except (OSError, TypeError, ValueError) as error:
                gates.append(ChallengeReadinessGate("release_record", False, str(error)))
    else:
        gates.append(ChallengeReadinessGate("release_record", False, "pack, policy or final rules unavailable"))

    if baseline_path is None or deliberately_bad_path is None:
        gates.append(ChallengeReadinessGate("baseline_ordering", False, "baseline and deliberately bad manifests are required"))
    elif pack is None or policy is None:
        gates.append(ChallengeReadinessGate("baseline_ordering", False, "private pack and frozen policy are required to bind baseline evidence"))
    else:
        try:
            result = verify_baseline_ordering(
                _read_json(Path(baseline_path)),
                _read_json(Path(deliberately_bad_path)),
                minimum_margin=0.0,
                expected_pack_id=pack.manifest["pack_id"],
                expected_pack_digest=hash_private_pack(pack),
                expected_rules_digest=rules_digest(rules),
                expected_policy_digest=policy.digest(),
                expected_scoring_version=pack.manifest["scoring_version"],
                expected_evaluator_revision=evaluator_revision,
                expected_task_ids=(task.task_id for task in pack.tasks),
            )
            gates.append(ChallengeReadinessGate("baseline_ordering", True, json.dumps(result, sort_keys=True)))
        except (OSError, TypeError, ValueError, ChallengeBaselineError) as error:
            gates.append(ChallengeReadinessGate("baseline_ordering", False, str(error)))
    return tuple(gates)


def readiness_result(gates: tuple[ChallengeReadinessGate, ...]) -> dict[str, Any]:
    return {
        "status": "pass" if all(gate.passed for gate in gates) else "blocked",
        "gates": [gate.to_dict() for gate in gates],
    }
