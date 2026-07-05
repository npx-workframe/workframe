#!/usr/bin/env python3
"""Route registry audit (WF-037).

Run: python services/workframe-api/test_route_registry.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import route_registry  # noqa: E402

# Auth level coverage
assert route_registry.resolve_auth_level("GET", "/api/health") == route_registry.AuthLevel.PUBLIC
assert route_registry.resolve_auth_level("GET", "/api/snapshot") == route_registry.AuthLevel.SINGLE_USER_GET
assert route_registry.resolve_auth_level("POST", "/api/auth/start") == route_registry.AuthLevel.AUTH_FLOW
assert route_registry.resolve_auth_level("GET", "/api/me") == route_registry.AuthLevel.SESSION
assert route_registry.resolve_auth_level("POST", "/api/chat/send") == route_registry.AuthLevel.SESSION

# Unknown /api paths require session (deny when anonymous)
assert route_registry.resolve_auth_level("GET", "/api/not-a-real-handler") == route_registry.AuthLevel.SESSION
assert not route_registry.authorize_request(
    "GET",
    "/api/not-a-real-handler",
    "",
    deployment_mode="trusted_team",
    dev_local_unsafe=False,
    install_window_open=False,
    validate_session=lambda _s: None,
    attach_user=lambda _u: None,
)

# Every explicit handler path in server.py should resolve to SESSION or declared tier.
server_src = (ROOT / "server.py").read_text(encoding="utf-8")
handler_paths = set(re.findall(r'if path == "(/api/[^"]+)"', server_src))
handler_paths |= set(re.findall(r'if path == \'(/api/[^\']+)\'', server_src))
missing: list[str] = []
for p in sorted(handler_paths):
    level = route_registry.resolve_auth_level("GET", p)
    if level not in (
        route_registry.AuthLevel.PUBLIC,
        route_registry.AuthLevel.SINGLE_USER_GET,
        route_registry.AuthLevel.SESSION,
        route_registry.AuthLevel.INSTALL,
        route_registry.AuthLevel.AUTH_FLOW,
    ):
        missing.append(p)
assert not missing, f"unmapped auth levels: {missing}"

# trusted_team: data GETs need session (not anonymous), not a hard deny
assert not route_registry.authorize_request(
    "GET",
    "/api/agents",
    "",
    deployment_mode="trusted_team",
    dev_local_unsafe=False,
    install_window_open=False,
    validate_session=lambda _s: None,
    attach_user=lambda _u: None,
)
assert route_registry.authorize_request(
    "GET",
    "/api/agents",
    "sid-ok",
    deployment_mode="trusted_team",
    dev_local_unsafe=False,
    install_window_open=False,
    validate_session=lambda s: {"user_id": "u1"} if s == "sid-ok" else None,
    attach_user=lambda _u: None,
)

print("route registry self-check ok")
