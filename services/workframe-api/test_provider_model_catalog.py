"""Pure model catalog parsing/cache helpers."""

from __future__ import annotations

import provider_model_catalog


def test_oauth_access_token_provider_layout() -> None:
    auth = {"providers": {"openai-codex": {"tokens": {"access_token": "live-token"}}}}
    assert provider_model_catalog.oauth_access_token(auth, "openai-codex") == "live-token"


def test_oauth_access_token_pool_layout() -> None:
    auth = {"credential_pool": {"openai-codex": [{"accessToken": "pool-token"}]}}
    assert provider_model_catalog.oauth_access_token(auth, "openai-codex") == "pool-token"


def test_discover_without_credential_does_not_call_network() -> None:
    rows, status = provider_model_catalog.discover("openrouter", "")
    assert rows == []
    assert status["status"] == "unauthenticated"


def test_unknown_provider_preserves_custom_model_escape_hatch() -> None:
    rows, status = provider_model_catalog.discover("nous", "oauth")
    assert rows == []
    assert status["status"] == "unsupported"
