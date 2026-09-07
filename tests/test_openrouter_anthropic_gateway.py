from __future__ import annotations

import json

import pytest

from scripts.openrouter_anthropic_gateway import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER_ORDER,
    build_upstream_payload,
    parse_provider_order,
)


def _body(**overrides: object) -> bytes:
    payload = {"model": DEFAULT_MODEL, "messages": [{"role": "user", "content": "ping"}]}
    payload.update(overrides)
    return json.dumps(payload).encode()


def test_gateway_replaces_caller_provider_policy() -> None:
    result = json.loads(
        build_upstream_payload(
            _body(provider={"order": ["untrusted"], "allow_fallbacks": True}),
            provider_order=("deepinfra", "novitaai"),
        )
    )
    assert result["model"] == DEFAULT_MODEL
    assert result["provider"] == {"order": ["deepinfra", "novitaai"], "allow_fallbacks": False}


def test_gateway_rejects_model_drift() -> None:
    with pytest.raises(ValueError, match="model must be"):
        build_upstream_payload(_body(model="anthropic/claude-sonnet-4.5"))


def test_provider_order_is_explicit_and_unique() -> None:
    assert parse_provider_order(None) == DEFAULT_PROVIDER_ORDER
    assert parse_provider_order(" deepinfra, novitaai ") == ("deepinfra", "novitaai")
    with pytest.raises(ValueError, match="at least one"):
        parse_provider_order(" , ")
    with pytest.raises(ValueError, match="duplicates"):
        parse_provider_order("deepinfra,deepinfra")
