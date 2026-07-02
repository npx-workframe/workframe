"""ponytail self-check: OAuth LLM providers (Codex/Nous) must pass chat gates without API keys.

Run: python services/workframe-api/test_oauth_llm.py
"""
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

# Without live tokens require path must fail
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
    resolved = server._require_runtime_owner_provider(
        "550e8400-e29b-41d4-a716-446655440000",
        "ws-1",
        "codex",
    )
    assert resolved.get("credential_type") == "oauth"
    assert resolved.get("credential_ref") == "oauth:openai-codex"
finally:
    server._hermes_oauth_tokens_present = _orig

mvp = server.PROVIDER_MVP_MODELS["codex"]["primary"]
assert mvp == "gpt-5.4-medium"

print("oauth llm self-check ok")
