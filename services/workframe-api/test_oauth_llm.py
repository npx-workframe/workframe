"""ponytail self-check: device OAuth is vault-backed; runtime auth.json alone is not enough.

Run: python services/workframe-api/test_oauth_llm.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402

keys = server._hermes_oauth_auth_keys("openai-codex")
assert "openai-codex" in keys
assert "codex" in keys
assert "openai_codex" in keys

pool_only = {
    "version": 1,
    "providers": {},
    "credential_pool": {"openai-codex": [{"id": "x", "auth_type": "oauth"}]},
}
assert server._auth_json_has_oauth_material(pool_only)

# credential_pool-only auth must merge into profile auth
merged: dict = {"version": 1, "providers": {}, "credential_pool": {}}
assert server._merge_oauth_auth_into_profile(merged, pool_only, "openai-codex")
assert merged["credential_pool"].get("openai-codex")

# Leftover runtime auth.json must not satisfy billing. Vault oauth does.
try:
    server._require_runtime_owner_provider("user-1", "ws-1", "codex")
    raise AssertionError("expected ValueError without oauth tokens")
except ValueError:
    pass

_orig = server._hermes_oauth_tokens_present


def _fake_present(_user: str, _auth_id: str) -> bool:
    return True


server._hermes_oauth_tokens_present = _fake_present
try:
    try:
        server._require_runtime_owner_provider(
            "550e8400-e29b-41d4-a716-446655440000",
            "ws-1",
            "codex",
        )
        raise AssertionError("runtime auth.json must not satisfy device OAuth")
    except ValueError:
        pass
finally:
    server._hermes_oauth_tokens_present = _orig

mvp = server.PROVIDER_MVP_MODELS["codex"]["primary"]
assert mvp == "gpt-5.4-mini"

_orig_resolve = server._resolve_credential
_orig_secret = server._credential_secret


def _fake_resolve(_user_id, _workspace_id, provider, *, user_only=False):
    if str(provider) == "codex":
        return {
            "credential_ref": "vault:fake-codex",
            "credential_type": "oauth",
            "provider": "codex",
            "credential_id": "fake-codex",
        }
    return None


def _fake_secret(resolved, _user_id=""):
    if resolved:
        return json.dumps({"kind": "oauth", "access_token": "x", "refresh_token": "y"})
    return ""


server._resolve_credential = _fake_resolve
server._credential_secret = _fake_secret
try:
    got = server._require_runtime_owner_provider("user-1", "ws-1", "codex")
    assert got["credential_type"] == "oauth"
    spec = server._catalog_provider("codex")
    assert spec and server._user_provider_connected("user-1", spec)
finally:
    server._resolve_credential = _orig_resolve
    server._credential_secret = _orig_secret

print("oauth llm self-check ok")
