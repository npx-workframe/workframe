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
assert route_registry.resolve_auth_level("GET", "/api/meta") == route_registry.AuthLevel.PUBLIC
assert route_registry.resolve_auth_level("GET", "/api/snapshot") == route_registry.AuthLevel.SINGLE_USER_GET
assert route_registry.resolve_auth_level("POST", "/api/auth/start") == route_registry.AuthLevel.AUTH_FLOW
assert route_registry.resolve_auth_level("GET", "/api/me") == route_registry.AuthLevel.SESSION
assert route_registry.resolve_auth_level("GET", "/api/activity/detail") == route_registry.AuthLevel.SESSION

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

# ROUTES table: auth tier matches resolve_auth_level
auth_mismatch: list[str] = []
for route in route_registry.ROUTES:
    resolved = route_registry.resolve_auth_level(route.method, route.path)
    if resolved != route.auth:
        auth_mismatch.append(f"{route.method} {route.path}: table={route.auth} resolved={resolved}")
assert not auth_mismatch, f"route auth mismatch: {auth_mismatch}"

# ROUTES handlers exist on server.Handler
server_src = (ROOT / "server.py").read_text(encoding="utf-8")
missing_handlers: list[str] = []
for route in route_registry.ROUTES:
    if f"def {route.handler}(" not in server_src:
        missing_handlers.append(f"{route.method} {route.path} -> {route.handler}")
assert not missing_handlers, f"missing handler methods: {missing_handlers}"

# Remaining if-chain GET paths still map to a known auth tier
handler_paths = set(re.findall(r'if path == "(/api/[^"]+)"', server_src))
handler_paths |= set(re.findall(r"if path == \'(/api/[^\']+)\'", server_src))
unmapped: list[str] = []
for p in sorted(handler_paths):
    level = route_registry.resolve_auth_level("GET", p)
    if level not in (
        route_registry.AuthLevel.PUBLIC,
        route_registry.AuthLevel.SINGLE_USER_GET,
        route_registry.AuthLevel.SESSION,
        route_registry.AuthLevel.INSTALL,
        route_registry.AuthLevel.AUTH_FLOW,
    ):
        unmapped.append(p)
assert not unmapped, f"unmapped auth levels: {unmapped}"

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

data_read_get = [r for r in route_registry.ROUTES if r.method == "GET"]
assert len(data_read_get) == 36
registry_post = [r for r in route_registry.ROUTES if r.method == "POST"]
assert len(registry_post) == 18

class _PostStub:
    def __init__(self) -> None:
        self.called = False
        self.body: dict | None = None

    def _route_post_auth_start(self, body: dict) -> None:
        self.called = True
        self.body = body

_stub = _PostStub()
assert route_registry.dispatch_post(_stub, "/api/auth/start", {"email": "a@b.c"})
assert _stub.called and _stub.body == {"email": "a@b.c"}
assert not route_registry.dispatch_post(_stub, "/api/not-registered", {})

print("route registry self-check ok")
