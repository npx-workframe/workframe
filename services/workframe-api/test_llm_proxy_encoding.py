"""Regression coverage for compressed upstream LLM responses."""

from __future__ import annotations

import credential_broker
import llm_proxy


def test_upstream_request_forces_identity_encoding(monkeypatch) -> None:
    monkeypatch.setattr(
        credential_broker,
        "authorize_broker_lease",
        lambda *args, **kwargs: credential_broker.BrokerLeaseAuth(ok=True, secret="test-secret"),
    )

    request, error = llm_proxy._build_upstream_request(
        "openrouter",
        "/chat/completions",
        "POST",
        {
            "Authorization": "Bearer runtime-llm:test",
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/json",
        },
        b"{}",
        resolve_secret=lambda *_: ("OPENROUTER_API_KEY", "unused"),
    )

    assert error is None
    assert request is not None
    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["accept-encoding"] == "identity"
    assert headers["authorization"] == "Bearer test-secret"
