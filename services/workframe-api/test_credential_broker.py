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

print("credential broker self-check ok")
