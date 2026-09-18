from __future__ import annotations

import pytest

from harness.broker import (
    BrokerError,
    CapabilityAuthority,
    SessionCapabilityIssuer,
)


def test_capability_is_bound_to_run_arm_namespace_and_method() -> None:
    authority = CapabilityAuthority(clock=lambda: 100.0)
    token = authority.issue(
        run_id="run-1",
        arm="recall",
        namespace="run-1/recall",
        service="memory",
        allowed_methods=("tools/call",),
        ttl_s=60,
    )
    grant = authority.validate(
        token,
        run_id="run-1",
        arm="recall",
        namespace="run-1/recall",
        service="memory",
        method="tools/call",
        request_bytes=10,
        max_request_bytes=100,
    )
    assert grant.service == "memory"
    for field, value in (
        ("run_id", "run-2"),
        ("arm", "bare"),
        ("namespace", "run-1/bare"),
        ("service", "model"),
    ):
        values = {
            "run_id": "run-1",
            "arm": "recall",
            "namespace": "run-1/recall",
            "service": "memory",
        }
        values[field] = value
        with pytest.raises(BrokerError):
            authority.validate(
                token,
                **values,
                method="tools/call",
                request_bytes=10,
                max_request_bytes=100,
            )
    with pytest.raises(BrokerError):
        authority.validate(
            token,
            run_id="run-1",
            arm="recall",
            namespace="run-1/recall",
            service="memory",
            method="resources/read",
            request_bytes=10,
            max_request_bytes=100,
        )


def test_expired_and_oversized_capabilities_are_rejected() -> None:
    now = [100.0]
    authority = CapabilityAuthority(clock=lambda: now[0])
    token = authority.issue(
        run_id="run-1",
        arm="bare",
        namespace="run-1/bare",
        service="model",
        allowed_methods=("messages",),
        ttl_s=1,
    )
    now[0] = 101.0
    with pytest.raises(BrokerError):
        authority.validate(
            token,
            run_id="run-1",
            arm="bare",
            namespace="run-1/bare",
            service="model",
            method="messages",
            request_bytes=1,
            max_request_bytes=100,
        )

    now[0] = 100.0
    token = authority.issue(
        run_id="run-1",
        arm="bare",
        namespace="run-1/bare",
        service="model",
        allowed_methods=("messages",),
        ttl_s=10,
    )
    with pytest.raises(BrokerError):
        authority.validate(
            token,
            run_id="run-1",
            arm="bare",
            namespace="run-1/bare",
            service="model",
            method="messages",
            request_bytes=101,
            max_request_bytes=100,
        )


def test_session_issuer_mints_distinct_scoped_model_and_memory_grants() -> None:
    issuer = SessionCapabilityIssuer("s" * 32, ttl_s=60)
    model_a, memory_a = issuer.issue(
        run_id="run-1", arm="graphiti", namespace="cell-a", memory=True
    )
    model_b, memory_b = issuer.issue(
        run_id="run-1", arm="graphiti", namespace="cell-b", memory=True
    )
    assert model_a != model_b
    assert memory_a and memory_b and memory_a != memory_b

    issuer.authority.validate(
        model_a,
        run_id="*",
        arm="*",
        namespace="*",
        service="model",
        method="messages",
        request_bytes=1,
        max_request_bytes=100,
    )
    issuer.authority.validate(
        memory_a,
        run_id="*",
        arm="*",
        namespace="*",
        service="memory",
        method="tools/call",
        request_bytes=1,
        max_request_bytes=100,
    )
    with pytest.raises(BrokerError):
        issuer.authority.validate(
            model_a,
            run_id="run-1",
            arm="graphiti",
            namespace="cell-b",
            service="model",
            method="messages",
            request_bytes=1,
            max_request_bytes=100,
        )
