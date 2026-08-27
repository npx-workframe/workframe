"""WF-048 broker boundary checks: bundles never escape as upstream secrets."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import credential_broker  # noqa: E402


plain, status = credential_broker.materialize_provider_secret("openrouter", "", "plain-key")
assert plain == "plain-key" and status == "ok"

live = json.dumps({"kind": "oauth", "access_token": "live-token", "expires_at": 4102444800})
materialized, status = credential_broker.materialize_provider_secret("github", "", live)
assert materialized == "live-token" and status == "ok"

expired = json.dumps({"kind": "oauth", "access_token": "old", "expires_at": 1})
materialized, status = credential_broker.materialize_provider_secret("github", "", expired)
assert materialized == "" and status == "oauth_refresh_unavailable"

expired_codex = json.dumps({
    "kind": "oauth",
    "access_token": "old",
    "refresh_token": "rt",
    "expires_at": 1,
    "token_url": "https://auth.openai.com/oauth/token",
    "client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
})


class _Resp:
    def read(self):
        return json.dumps({"access_token": "new-access", "expires_in": 3600}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


import urllib.request

_orig_urlopen = urllib.request.urlopen
urllib.request.urlopen = lambda *_a, **_k: _Resp()  # type: ignore[assignment]
try:
    materialized, status = credential_broker.materialize_provider_secret("codex", "", expired_codex)
    assert materialized == "new-access" and status == "ok"
finally:
    urllib.request.urlopen = _orig_urlopen


future_codex = json.dumps({
    "kind": "oauth",
    "access_token": "still-listed-as-live",
    "refresh_token": "rt",
    "expires_at": 4102444800,
    "token_url": "https://auth.openai.com/oauth/token",
    "client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
})
urllib.request.urlopen = lambda *_a, **_k: _Resp()  # type: ignore[assignment]
try:
    materialized, status = credential_broker.materialize_provider_secret("codex", "", future_codex)
    assert materialized == "new-access" and status == "ok"
finally:
    urllib.request.urlopen = _orig_urlopen

no_expiry = json.dumps({
    "kind": "oauth",
    "access_token": "stale",
    "refresh_token": "rt",
    "token_url": "https://auth.openai.com/oauth/token",
    "client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
})
urllib.request.urlopen = lambda *_a, **_k: _Resp()  # type: ignore[assignment]
try:
    materialized, status = credential_broker.materialize_provider_secret("codex", "", no_expiry)
    assert materialized == "new-access" and status == "ok"
finally:
    urllib.request.urlopen = _orig_urlopen

print("credential broker self-check ok")
