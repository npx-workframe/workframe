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


def test_scrub_oauth_auth_material() -> None:
    auth = {
        "providers": {"openai-codex": {"tokens": {"refresh_token": "secret"}}, "github": {"ok": True}},
        "credential_pool": {"openai-codex": [{"refresh_token": "secret"}], "github": [{"id": "x"}]},
        "credentials": [{"provider": "openai-codex"}, {"provider": "github"}],
    }
    assert provider_bindings._scrub_oauth_auth_material(auth, "openai-codex")
    assert "openai-codex" not in auth["providers"]
    assert "openai-codex" not in auth["credential_pool"]
    assert auth["credentials"] == [{"provider": "github"}]


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


def test_read_gateway_data_file_via_supervisor(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    class _Srv:
        SECURE_MODE = True
        HERMES_DATA = Path("/nonexistent")

        def _supervisor_ready(self) -> bool:
            return True

        def _supervisor_request(self, method: str, path: str, body: dict, timeout: float = 30.0):
            calls.append((path, body))
            return 200, {"ok": True, "content": "oauth log body"}

        def _gateway_container_exec(self, _cmd: list[str]) -> tuple[int, str]:
            raise AssertionError("raw exec should not run when supervisor read succeeds")

    monkeypatch.setattr(provider_bindings, "_srv", lambda: _Srv())
    out = provider_bindings._read_gateway_data_file(
        "profiles/user-1/.oauth-session123.log",
    )
    assert out == "oauth log body"
    assert calls == [
        ("/v1/gateway.read_data_file", {"rel_path": "profiles/user-1/.oauth-session123.log"}),
    ]



def test_extract_oauth_from_credential_pool() -> None:
    loaded = {
        "version": 1,
        "providers": {},
        "credential_pool": {
            "openai-codex": [
                {
                    "id": "pool-1",
                    "auth_type": "oauth",
                    "access_token": "at-live",
                    "refresh_token": "rt-live",
                }
            ]
        },
    }
    block = provider_bindings._extract_oauth_block_from_auth(loaded, "openai-codex")
    assert block and block["access_token"] == "at-live"
    camel = {"credential_pool": {"openai-codex": [{"accessToken": "camel-access"}]}}
    camel_block = provider_bindings._extract_oauth_block_from_auth(camel, "openai-codex")
    assert camel_block and provider_bindings._oauth_field(camel_block, provider_bindings._OAUTH_ACCESS_FIELDS) == "camel-access"
    material = provider_bindings._extract_oauth_token_material(loaded, "openai-codex")
    assert material and material["refresh_token"] == "rt-live"
    bundle = provider_bindings._build_oauth_vault_bundle("codex", "openai-codex", material)
    assert bundle["kind"] == "oauth"
    assert bundle["provider"] == "codex"
    assert bundle["token_url"] == provider_bindings.CODEX_OAUTH_TOKEN_URL
    assert bundle["client_id"] == provider_bindings.CODEX_OAUTH_CLIENT_ID
    assert "refresh_token" in bundle


def test_adopt_device_oauth_stores_vault_binding() -> None:
    calls: list[tuple] = []
    auth = {
        "version": 1,
        "providers": {},
        "credential_pool": {
            "openai-codex": [{"access_token": "at-live", "refresh_token": "rt-live", "auth_type": "oauth"}]
        },
    }

    class _Srv:
        def _store_user_credential(self, user_id, provider, cred_type, secret, env_var, label):
            calls.append(("store", user_id, provider, cred_type, env_var, label))
            import json
            bundle = json.loads(secret)
            assert bundle["kind"] == "oauth"
            assert bundle["refresh_token"] == "rt-live"
            assert bundle["token_url"] == provider_bindings.CODEX_OAUTH_TOKEN_URL
            return {"credential_id": "cred-1"}

        def _credential_lifecycle_revoke_other_bindings(self, **kwargs):
            calls.append(("revoke", kwargs["reason"], kwargs["keep_id"]))

        def _bootstrap_model_after_llm_connect(self, user_id, workspace_id, provider_id):
            calls.append(("bootstrap", user_id, workspace_id, provider_id))

        def _invalidate_user_llm_picker_cache(self, user_id):
            calls.append(("invalidate", user_id))

        def _utc_now(self) -> str:
            return "now"

    orig_srv = provider_bindings._srv
    orig_load = provider_bindings._load_user_hermes_auth
    orig_sync = provider_bindings._sync_user_oauth_provider_to_runtime_profiles
    orig_patch = provider_bindings._device_oauth_session_patch
    try:
        provider_bindings._srv = lambda: _Srv()  # type: ignore[method-assign]
        provider_bindings._load_user_hermes_auth = lambda _uid: auth  # type: ignore[method-assign]
        provider_bindings._sync_user_oauth_provider_to_runtime_profiles = (
            lambda user_id, auth_id: calls.append(("sync", user_id, auth_id))
        )  # type: ignore[method-assign]
        provider_bindings._device_oauth_session_patch = lambda *_a, **_k: None  # type: ignore[method-assign]
        result = provider_bindings._adopt_hermes_device_oauth(
            "user-1",
            "codex",
            {"id": "codex", "hermes_auth_id": "openai-codex", "label": "OpenAI Codex", "connect_mode": "oauth"},
            "sess-1",
            "ws-1",
        )
    finally:
        provider_bindings._srv = orig_srv
        provider_bindings._load_user_hermes_auth = orig_load
        provider_bindings._sync_user_oauth_provider_to_runtime_profiles = orig_sync
        provider_bindings._device_oauth_session_patch = orig_patch
    assert result["ok"] is True
    assert result["status"] == "connected"
    assert result["credential_id"] == "cred-1"
    assert ("store", "user-1", "codex", "oauth", "", "OpenAI Codex") in calls or any(
        row[0] == "store" and row[2] == "codex" and row[3] == "oauth" for row in calls
    )
    assert any(row[0] == "bootstrap" for row in calls)
    assert any(row[0] == "sync" for row in calls)
    assert any(row[0] == "invalidate" for row in calls)


def test_publish_turn_oauth_access_omits_refresh(tmp_path) -> None:
    profile = "u-user-mybusiness-agent"
    tmp_path.mkdir(parents=True, exist_ok=True)
    auth_path = tmp_path / "auth.json"
    auth_path.write_text("{\n  \"version\": 1\n}\n", encoding="utf-8")

    class _Srv:
        def resolve_hermes_profile(self, name: str) -> str:
            return name

        def _profile_dir(self, _name: str):
            return tmp_path

        def _utc_now(self) -> str:
            return "now"

        def _publish_profile_gateway_secrets(self, _name: str) -> None:
            return None

        def _catalog_provider(self, _pid: str):
            return {"id": "codex", "hermes_auth_id": "openai-codex", "connect_mode": "oauth", "category": "llm"}

        def _catalog_provider_for_llm(self, _pid: str):
            return self._catalog_provider(_pid)

    orig_srv = provider_bindings._srv
    orig_load = provider_bindings._load_profile_auth_json
    try:
        provider_bindings._srv = lambda: _Srv()  # type: ignore[method-assign]
        provider_bindings._load_profile_auth_json = lambda _name: {"version": 1}  # type: ignore[method-assign]
        ok = provider_bindings._publish_turn_oauth_access(
            profile,
            "codex",
            "at-only",
            {"id": "pool-1", "refresh_token": "must-not-publish", "auth_type": "oauth_external"},
        )
    finally:
        provider_bindings._srv = orig_srv
        provider_bindings._load_profile_auth_json = orig_load
    assert ok is True
    import json
    written = json.loads(auth_path.read_text(encoding="utf-8"))
    entry = written["credential_pool"]["openai-codex"][0]
    assert entry["access_token"] == "at-only"
    assert "refresh_token" not in entry
    assert entry["auth_type"] == "oauth_external"
    assert entry["base_url"] == provider_bindings.CODEX_OAUTH_BASE_URL


def test_user_provider_connected_oauth_uses_vault() -> None:
    class _Srv:
        def _resolve_credential(self, user_id, workspace_id, provider, *, user_only=False):
            assert user_only is True
            return {"credential_ref": "vault:codex", "credential_type": "oauth"}

        def _credential_secret(self, resolved, user_id=""):
            return "{\"kind\": \"oauth\", \"access_token\": \"x\"}" if resolved else ""

        def _user_auth_env_keys(self, _user_id):
            raise AssertionError("oauth connected must not fall through to env keys")

    orig = provider_bindings._srv
    try:
        provider_bindings._srv = lambda: _Srv()  # type: ignore[method-assign]
        spec = {"id": "codex", "connect_mode": "oauth", "category": "llm"}
        assert provider_bindings._user_provider_connected("user-1", spec) is True
    finally:
        provider_bindings._srv = orig


if __name__ == "__main__":
    from pathlib import Path as _Path
    test_hermes_oauth_auth_keys()
    test_auth_json_has_oauth_material()
    test_merge_oauth_auth_into_profile()
    test_parse_device_oauth_log()
    test_device_oauth_error_from_log()
    test_reusable_device_oauth_session()
    test_extract_oauth_from_credential_pool()
    test_adopt_device_oauth_stores_vault_binding()
    test_user_provider_connected_oauth_uses_vault()
    test_publish_turn_oauth_access_omits_refresh(_Path("/tmp/wf-oauth-publish-test"))
    print("test_provider_bindings: ok")
