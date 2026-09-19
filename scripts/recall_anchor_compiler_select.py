"""Mechanical admission selector for the preregistered AML anchor compiler v2 pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.recall_hosted_select import _identity_without_variant

INVARIANT_KEYS = (
    "corpus_manifest_sha256",
    "task_set_sha256",
    "task_count",
    "sessions_offered",
    "messages_offered",
    "add_request_count",
    "http_timeout_seconds",
)


def _rows_by_task(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = artifact.get("rows")
    if not isinstance(rows, list):
        raise TypeError(f"missing replay rows for {artifact.get('variant')}")
    by_task = {str(row.get("task_id")): row for row in rows if isinstance(row, dict)}
    if len(by_task) != len(rows):
        raise ValueError(f"duplicate or malformed replay rows for {artifact.get('variant')}")
    return by_task


def _count(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"invalid {name}")
    return value


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        raise ValueError("admission pilot requires eligible sessions")
    return numerator / denominator


def select_anchor_compiler(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    audit: dict[str, Any],
    *,
    baseline_variant: str = "V2_raw",
    candidate_variant: str = "V2_anchor_raw",
) -> dict[str, Any]:
    """Apply frozen admission gates without inspecting task answers or changing thresholds."""
    if baseline.get("schema_version") != 4 or baseline.get("variant") != baseline_variant:
        raise ValueError(f"baseline must be the {baseline_variant} replay schema")
    if candidate.get("schema_version") != 4 or candidate.get("variant") != candidate_variant:
        raise ValueError(f"candidate must be the {candidate_variant} replay schema")
    if any(candidate.get(key) != baseline.get(key) for key in INVARIANT_KEYS):
        raise ValueError("replay population drift")
    baseline_version = baseline.get("version")
    candidate_version = candidate.get("version")
    if (
        not isinstance(baseline_version, dict)
        or baseline_version.get("variant") != baseline_variant
        or not isinstance(candidate_version, dict)
        or candidate_version.get("variant") != candidate_variant
    ):
        raise ValueError("served version mismatch")
    if _identity_without_variant(candidate_version) != _identity_without_variant(baseline_version):
        raise ValueError("served product identity drift")
    baseline_rows = _rows_by_task(baseline)
    candidate_rows = _rows_by_task(candidate)
    if set(candidate_rows) != set(baseline_rows):
        raise ValueError("task row drift")
    for task_id, row in candidate_rows.items():
        reference = baseline_rows[task_id]
        if any(
            row.get(key) != reference.get(key)
            for key in ("kind", "query_sha256", "fact_terms_sha256")
        ):
            raise ValueError(f"task identity drift for {task_id}")

    if audit.get("schema_version") != 1:
        raise ValueError("unsupported audit schema")
    if audit.get("corpus_manifest_sha256") != baseline.get("corpus_manifest_sha256"):
        raise ValueError("audit corpus drift")
    eligible = _count(audit.get("eligible_session_count"), "eligible session count")
    if eligible != _count(baseline.get("sessions_offered"), "sessions offered"):
        raise ValueError("audit population drift")
    compiled_sessions = _count(
        audit.get("compiled_session_count"), "compiled session count"
    )
    typed_sessions = _count(candidate.get("typed_session_count"), "typed session count")
    if compiled_sessions != typed_sessions:
        raise ValueError("typed session count drift")
    audited_records = _count(audit.get("audited_record_count"), "audited record count")
    compiled_records = _count(candidate.get("compiled_record_count"), "compiled record count")
    if audited_records != compiled_records:
        raise ValueError("compiled record count drift")
    fallback_sessions = _count(
        candidate.get("full_session_fallback_count"), "full session fallback count"
    )
    if fallback_sessions != _count(
        audit.get("fallback_session_count"), "audited fallback session count"
    ):
        raise ValueError("fallback session count drift")
    typed_adds = _count(candidate.get("typed_add_count"), "typed add count")
    if typed_adds != typed_sessions:
        raise ValueError("typed Add counter drift")
    raw_sessions = _count(audit.get("raw_session_count"), "raw session count")
    unsupported = _count(audit.get("unsupported_claim_count"), "unsupported claim count")
    invalid_spans = _count(audit.get("invalid_span_count"), "invalid span count")
    wrong_profiles = _count(audit.get("wrong_profile_count"), "wrong profile count")
    violations = audit.get("violations")
    if not isinstance(violations, list):
        raise TypeError("invalid audit violations")

    baseline_aggregate = baseline.get("aggregate")
    candidate_aggregate = candidate.get("aggregate")
    if not isinstance(baseline_aggregate, dict) or not isinstance(candidate_aggregate, dict):
        raise TypeError("missing replay aggregate")
    if (
        _count(candidate_aggregate.get("compiler_fallbacks"), "compiler fallback count")
        != fallback_sessions
    ):
        raise ValueError("fallback counter drift")
    corpus_status = candidate.get("corpus_status")
    if not isinstance(corpus_status, dict):
        raise TypeError("missing stored corpus status")
    if (
        _count(corpus_status.get("compiled_chunk_count"), "stored compiled chunk count")
        != compiled_records
        or _count(corpus_status.get("source_session_count"), "stored source session count")
        != eligible
        or _count(corpus_status.get("raw_chunk_count"), "stored raw chunk count")
        < raw_sessions
    ):
        raise ValueError("stored compiler counter drift")
    baseline_rank_100 = float(baseline_aggregate["complete_coverage_at_100"])
    candidate_rank_100 = float(candidate_aggregate["complete_coverage_at_100"])
    accepted_rate = _rate(compiled_sessions, eligible)
    fallback_rate = _rate(fallback_sessions, eligible)
    gates = {
        "typed_session_acceptance": accepted_rate >= 0.90,
        "full_session_fallback": fallback_rate < 0.10,
        "source_grounding": (
            audited_records > 0
            and unsupported == 0
            and invalid_spans == 0
            and wrong_profiles == 0
            and not violations
        ),
        "raw_rescue": (
            raw_sessions == eligible
            and _count(
                audit.get("session_without_raw_record_count"),
                "sessions without raw records",
            )
            == 0
        ),
        "rank_100": candidate_rank_100 >= baseline_rank_100,
    }
    admission_pass = all(gates.values())
    return {
        "schema_version": 1,
        "baseline": baseline_variant,
        "candidate": candidate_variant,
        "selected_compiler": candidate_variant if admission_pass else baseline_variant,
        "admission_pass": admission_pass,
        "authorize_m2_m3_retrieval": admission_pass,
        "accepted_typed_session_rate": accepted_rate,
        "full_session_fallback_rate": fallback_rate,
        "baseline_complete_coverage_at_100": baseline_rank_100,
        "candidate_complete_coverage_at_100": candidate_rank_100,
        "audited_record_count": audited_records,
        "unsupported_claim_count": unsupported,
        "invalid_span_count": invalid_spans,
        "wrong_profile_count": wrong_profiles,
        "gates": gates,
        "served_product_identity": _identity_without_variant(baseline_version),
        "corpus_manifest_sha256": baseline["corpus_manifest_sha256"],
        "task_set_sha256": baseline["task_set_sha256"],
    }


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-variant", default="V2_raw")
    parser.add_argument("--candidate-variant", default="V2_anchor_raw")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite selection artifact: {args.output}")
    result = select_anchor_compiler(
        json.loads(args.baseline.read_text(encoding="utf-8")),
        json.loads(args.candidate.read_text(encoding="utf-8")),
        json.loads(args.audit.read_text(encoding="utf-8")),
        baseline_variant=args.baseline_variant,
        candidate_variant=args.candidate_variant,
    )
    result["input_sha256"] = {
        "baseline": _digest(args.baseline),
        "candidate": _digest(args.candidate),
        "audit": _digest(args.audit),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
