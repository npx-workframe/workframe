"""ponytail self-check: session-less GET policy (WF-031).

Run: python services/workframe-api/test_public_routes.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402

ALWAYS = "/api/health"
DATA = "/api/snapshot"
META = "/api/meta"


def allowed(path: str, mode: str, dev: bool = False) -> bool:
    return server._sessionless_get_allowed(path, deployment_mode=mode, dev_local_unsafe=dev)


# Always-public routes work in every deployment mode.
assert allowed(META, "public_multi_user")
assert allowed(ALWAYS, "trusted_team")
assert allowed("/api/public/branding/logo", "public_multi_user")

# Data routes: blocked for multi-user modes without DEV_LOCAL_UNSAFE.
assert not allowed(DATA, "public_multi_user")
assert not allowed(DATA, "trusted_team")
assert not allowed("/api/chat/messages", "public_multi_user")
assert not allowed("/api/files/list", "trusted_team")

# Data routes: allowed for single_user_local or dev unsafe.
assert allowed(DATA, "single_user_local")
assert allowed(DATA, "public_multi_user", dev=True)
assert allowed("/api/board", "single_user_local")

# _is_public_get composes static/UI paths.
assert server._is_public_get("/")
assert server._is_public_get("/assets/app.js")

print("public routes self-check ok")
