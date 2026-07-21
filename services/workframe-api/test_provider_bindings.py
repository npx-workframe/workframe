"""WF-032 provider_bindings pure helpers self-check."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

import provider_bindings  # noqa: E402


class _ProviderServerStub:
    PROVIDER_CONNECT_CATALOG = (
        {
            "id": "openrouter",
            "label": "OpenRouter",
            "category": "llm",
            "connect_mode": "api_key",
            "env_var": "OPENROUTER_API_KEY",
            "description": "router",
        },
    )

    def __init__(self, mode: str) -> None:
        self.mode = mode

    def _workspace_credential_mode(self, _conn, _workspace_id: str) -> str:
        return self.mode

    def _credential_secret(self, binding: dict, _user_id: str) -> str:
        return "secret" if binding else ""

    def _user_hermes_home(self, _user_id: str) -> Path:
        return Path("/profiles/user")


def test_hermes_oauth_auth_keys() -> None:
    keys = provider_bindings._hermes_oauth_auth_keys("openai-codex")
    assert "openai-codex" in keys
    assert "codex" in keys
    assert "openai_codex" in keys


def test_auth_json_has_oauth_material() -> None:
    pool_only = {
        "version": 1,
        "providers": {},
        "credential_pool": {"openai-codex": [{"id": "x", "auth_type": "oauth"}]},
    }
    assert provider_bindings._auth_json_has_oauth_material(pool_only)


def test_merge_oauth_auth_into_profile() -> None:
    pool_only = {
        "version": 1,
        "providers": {},
        "credential_pool": {"openai-codex": [{"id": "x", "auth_type": "oauth"}]},
    }
    merged: dict = {"version": 1, "providers": {}, "credential_pool": {}}
    assert provider_bindings._merge_oauth_auth_into_profile(merged, pool_only, "openai-codex")
    assert merged["credential_pool"].get("openai-codex")


def test_parse_device_oauth_log() -> None:
    text = "Open this URL\n  https://auth.openai.com/device\nEnter this code\n  ABCD-1234"
    parsed = provider_bindings._parse_device_oauth_log(text)
    assert parsed["verification_uri"] and "openai.com" in parsed["verification_uri"]
    assert parsed["user_code"] == "ABCD-1234"


def test_device_oauth_error_from_log() -> None:
    text = (
        "hermes_cli.auth.AuthError: OpenAI is rate-limiting Codex login requests (HTTP 429). "
        "Wait a minute and run the login again."
    )
    msg = provider_bindings._device_oauth_error_from_log(text)
    assert msg == "OpenAI is rate-limiting Codex login requests (HTTP 429). Wait a minute and try again."


def test_reusable_device_oauth_session() -> None:
    provider_bindings._oauth_device_sessions.clear()
    provider_bindings._oauth_device_sessions.update(
        {
            "old-error": {
                "user_id": "user-1",
                "provider_id": "openai-codex",
                "status": "error",
                "started_at": time.time(),
            },
            "live": {
                "user_id": "user-1",
                "provider_id": "openai-codex",
                "status": "pending",
                "started_at": time.time(),
            },
        }
    )
    reusable = provider_bindings._reusable_device_oauth_session("user-1", "openai-codex")
    assert reusable and reusable[0] == "live"
    assert provider_bindings._reusable_device_oauth_session("other", "openai-codex") is None
    provider_bindings._oauth_device_sessions.clear()


def test_finalize_device_oauth_invalidates_model_picker_before_bootstrap(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    server = SimpleNamespace(
        _invalidate_user_llm_picker_cache=lambda user_id: calls.append(("invalidate", user_id)),
        _bootstrap_model_after_llm_connect=lambda user_id, _workspace_id, provider_id: calls.append(
            ("bootstrap", f"{user_id}:{provider_id}")
        ),
    )
    monkeypatch.setattr(provider_bindings, "_srv", lambda: server)
    monkeypatch.setattr(
        provider_bindings,
        "_sync_user_oauth_provider_to_runtime_profiles",
        lambda user_id, auth_id: calls.append(("sync", f"{user_id}:{auth_id}")),
    )

    provider_bindings._finalize_hermes_device_oauth(
        "user-1",
        "openai-codex",
        {"hermes_auth_id": "openai-codex"},
    )

    assert calls == [
        ("sync", "user-1:openai-codex"),
        ("invalidate", "user-1"),
        ("bootstrap", "user-1:openai-codex"),
    ]


def test_workspace_provider_scope_uses_shared_binding(monkeypatch) -> None:
    monkeypatch.setattr(provider_bindings, "_srv", lambda: _ProviderServerStub("workspace"))
    monkeypatch.setattr(provider_bindings, "_user_provider_bindings", lambda _uid: {})
    monkeypatch.setattr(
        provider_bindings,
        "_workspace_provider_bindings",
        lambda _wid: {"openrouter": {"id": "shared-1", "credential_ref": "vault:shared"}},
    )
    monkeypatch.setattr(provider_bindings, "_user_provider_connected", lambda *_args: False)

    result = provider_bindings.list_user_providers("user-1", "workspace-1", "workspace")
    row = result["providers"][0]
    assert result["credential_scope"] == "workspace"
    assert row["connected"] is True
    assert row["source"] == "workspace"
    assert row["credential_id"] == "shared-1"


def test_byok_effective_scope_does_not_leak_shared_binding(monkeypatch) -> None:
    monkeypatch.setattr(provider_bindings, "_srv", lambda: _ProviderServerStub("byok"))
    monkeypatch.setattr(provider_bindings, "_user_provider_bindings", lambda _uid: {})
    monkeypatch.setattr(
        provider_bindings,
        "_workspace_provider_bindings",
        lambda _wid: {"openrouter": {"id": "shared-1", "credential_ref": "vault:shared"}},
    )
    monkeypatch.setattr(provider_bindings, "_user_provider_connected", lambda *_args: False)

    row = provider_bindings.list_user_providers("user-1", "workspace-1", "effective")["providers"][0]
    assert row["connected"] is False
    assert row["source"] is None
    assert row["credential_id"] is None


if __name__ == "__main__":
    test_hermes_oauth_auth_keys()
    test_auth_json_has_oauth_material()
    test_merge_oauth_auth_into_profile()
    test_parse_device_oauth_log()
    test_device_oauth_error_from_log()
    test_reusable_device_oauth_session()
    print("test_provider_bindings: ok")
