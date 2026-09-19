"""Independent source-byte audit for the AML anchor compiler admission pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from adapters.recall_hosted.adapter import session_messages
from harness.adapters.base import CorpusManifest, resolve_corpus_path


FACT_FIELDS = ("task_shape", "problem", "action", "outcome", "validation")


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _event_time_ms(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return -1
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return -1
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp() * 1_000)


def compiler_record_state(metadata: Mapping[str, Any]) -> tuple[str, bool]:
    """Classify stored compiler output and validate the profile attached by RE-call."""
    fallback = metadata.get("compiler_fallback")
    profile = metadata.get("compiler_profile")
    if fallback is False:
        return "accepted", profile == "anchor-v2"
    if fallback is True:
        return "fallback", profile == "deterministic-fallback"
    return "unknown", False


def audit_record(
    record: Mapping[str, Any],
    messages: Sequence[Mapping[str, Any]],
    *,
    expected_source_session_id: str | None = None,
) -> list[str]:
    """Return deterministic issue codes after resolving stored spans against source bytes."""
    issues: list[str] = []
    supported_quotes: list[str] = []
    spans = record.get("evidence_spans", [])
    if not isinstance(spans, list):
        spans = []
    for index, span in enumerate(spans):
        valid = isinstance(span, Mapping)
        ordinal = span.get("message_ordinal") if valid else None
        start = span.get("start") if valid else None
        end = span.get("end") if valid else None
        quote = span.get("quote") if valid else None
        valid = (
            valid
            and _integer(ordinal)
            and _integer(start)
            and _integer(end)
            and isinstance(quote, str)
            and 0 <= ordinal < len(messages)
            and 0 <= start < end
        )
        if valid:
            content = messages[ordinal].get("content")
            valid = (
                isinstance(content, str)
                and end <= len(content)
                and content[start:end] == quote
            )
        if valid:
            supported_quotes.append(quote)
        else:
            issues.append(f"invalid_evidence_span:{index}")

    for field in FACT_FIELDS:
        value = record.get(field, "")
        if isinstance(value, str) and value and not any(value in quote for quote in supported_quotes):
            issues.append(f"unsupported_field:{field}")

    entities = record.get("entities", [])
    if isinstance(entities, list):
        for index, entity in enumerate(entities):
            if not isinstance(entity, str) or not entity or not any(
                entity in quote for quote in supported_quotes
            ):
                issues.append(f"unsupported_entity:{index}")
    else:
        issues.append("invalid_entities")
    event_time_ms = _event_time_ms(record.get("event_time"))
    if event_time_ms is not None and not any(
        message.get("timestamp") == event_time_ms for message in messages
    ):
        issues.append("unsupported_event_time")
    if (
        expected_source_session_id is not None
        and record.get("source_session_id") != expected_source_session_id
    ):
        issues.append("source_session_mismatch")
    return list(dict.fromkeys(issues))


def audit_corpus(
    *,
    store: Any,
    corpus: CorpusManifest,
    namespace: str,
) -> dict[str, Any]:
    """Audit all stored compiler v2 records without calling a model or product endpoint."""
    from recall_aml.identity import session_digest, tenant_for

    corpus.verify()
    tenant = tenant_for(namespace)
    tenant_store = store.for_tenant(tenant)
    eligible_sessions = 0
    compiled_sessions = 0
    fallback_sessions = 0
    raw_sessions = 0
    audited_records = 0
    unsupported_claim_count = 0
    invalid_span_count = 0
    wrong_profile_count = 0
    violations: list[dict[str, Any]] = []
    for relative in sorted(corpus.sessions):
        messages = session_messages(resolve_corpus_path(corpus.root, relative))
        if any(str(message.get("content", "")).strip() for message in messages):
            eligible_sessions += 1
        source = "aml://session/" + session_digest(relative)
        chunks = list(tenant_store.chunks_for_source(source))
        raw = [chunk for chunk in chunks if chunk.metadata.get("record_type") == "raw"]
        compiled = [
            chunk for chunk in chunks if chunk.metadata.get("record_type") == "compiled"
        ]
        raw_sessions += int(bool(raw))
        states = [compiler_record_state(chunk.metadata)[0] for chunk in compiled]
        compiled_sessions += int("accepted" in states)
        fallback_sessions += int("fallback" in states)
        for chunk in compiled:
            audited_records += 1
            issues: list[str] = []
            _, profile_valid = compiler_record_state(chunk.metadata)
            if not profile_valid:
                issues.append("wrong_compiler_profile")
                wrong_profile_count += 1
            record = chunk.metadata.get("coding_record")
            if isinstance(record, Mapping):
                record_issues = audit_record(
                    record,
                    messages,
                    expected_source_session_id=relative,
                )
            else:
                record_issues = ["missing_coding_record"]
            issues.extend(record_issues)
            unsupported_claim_count += sum(
                issue.startswith("unsupported_") for issue in record_issues
            )
            invalid_span_count += sum(
                issue.startswith("invalid_evidence_span") for issue in record_issues
            )
            if issues:
                violations.append(
                    {
                        "record_id": chunk.id,
                        "session_sha256": hashlib.sha256(relative.encode()).hexdigest(),
                        "issues": issues,
                    }
                )
    return {
        "schema_version": 1,
        "namespace_sha256": hashlib.sha256(namespace.encode()).hexdigest(),
        "corpus_manifest_sha256": hashlib.sha256(
            (corpus.root / "manifest.json").read_bytes()
        ).hexdigest(),
        "eligible_session_count": eligible_sessions,
        "compiled_session_count": compiled_sessions,
        "fallback_session_count": fallback_sessions,
        "raw_session_count": raw_sessions,
        "session_without_compiled_record_count": eligible_sessions - compiled_sessions,
        "session_without_raw_record_count": eligible_sessions - raw_sessions,
        "audited_record_count": audited_records,
        "unsupported_claim_count": unsupported_claim_count,
        "invalid_span_count": invalid_span_count,
        "wrong_profile_count": wrong_profile_count,
        "violations": violations,
    }


def main() -> None:
    from recall.store import PgVectorStore

    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--table", default=os.environ.get("RECALL_AML_TABLE", "recall_chunks"))
    parser.add_argument("--generation", default="aml-anchor-compiler-v2")
    parser.add_argument("--dimension", type=int, default=1_024)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite audit artifact: {args.output}")
    database_url = os.environ.get("RECALL_AML_DATABASE_URL", "")
    if not database_url:
        raise SystemExit("RECALL_AML_DATABASE_URL is required")
    store = PgVectorStore(
        database_url,
        args.dimension,
        table=args.table,
        tenant="aml_anchor_audit",
        generation_id=args.generation,
    )
    try:
        result = audit_corpus(
            store=store,
            corpus=CorpusManifest.load(args.corpus),
            namespace=args.namespace,
        )
    finally:
        store.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
