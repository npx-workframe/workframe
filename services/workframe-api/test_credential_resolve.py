"""WF-032 credential_resolve self-check."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import credential_resolve  # noqa: E402


def test_default_env_var() -> None:
    assert credential_resolve._default_credential_env_var("openrouter", "api_key") == "OPENROUTER_API_KEY"
    assert credential_resolve._default_credential_env_var("discord", "bot_token") == "DISCORD_BOT_TOKEN"


def test_resolve_empty() -> None:
    assert credential_resolve._resolve_credential("", "", "openrouter") is None
    assert credential_resolve._resolve_credential("user-1", "", "") is None


def test_binding_payload_shape() -> None:
    class _Row(dict):
        def __getitem__(self, key: str):
            return dict(self).get(key)

    row = _Row(
        id="bind-1",
        credential_ref="vault:abc",
        provider="openrouter",
        credential_type="api_key",
        label="test",
        user_id="u1",
        workspace_id=None,
        agent_profile_id=None,
        created_by="u1",
        created_at="1",
        updated_at="1",
        expires_at=None,
    )
    payload = credential_resolve._credential_binding_payload(row, "user")  # type: ignore[arg-type]
    assert payload["scope"] == "user"
    assert payload["credential_ref"] == "vault:abc"


if __name__ == "__main__":
    test_default_env_var()
    test_resolve_empty()
    test_binding_payload_shape()
    print("test_credential_resolve: ok")
