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

# Auth level coverage (4-value enum)
assert route_registry.resolve_auth_level("GET", "/api/health") == route_registry.AuthLevel.PUBLIC
assert route_registry.resolve_auth_level("GET", "/api/meta") == route_registry.AuthLevel.PUBLIC
assert route_registry.resolve_auth_level("GET", "/api/snapshot") == route_registry.AuthLevel.SESSION
assert route_registry.resolve_auth_level("POST", "/api/auth/start") == route_registry.AuthLevel.PUBLIC
assert route_registry.resolve_auth_level("GET", "/api/me") == route_registry.AuthLevel.SESSION
assert route_registry.resolve_auth_level("GET", "/api/admin/vault/status") == route_registry.AuthLevel.ROLE_OWNER_ADMIN
assert route_registry.resolve_auth_level("GET", "/api/workspace/default/rooms") == route_registry.AuthLevel.SESSION

# Unknown /api paths are unregistered → None (404 at dispatch, not auth-gated)
assert route_registry.resolve_auth_level("GET", "/api/not-a-real-handler") is None
assert route_registry.authorize_request(
    "GET",
    "/api/not-a-real-handler",
    "",
    deployment_mode="trusted_team",
    dev_local_unsafe=False,
    install_window_open=False,
    validate_session=lambda _s: None,
    attach_user=lambda _u: None,
)

# Registered session route without session → 401
assert not route_registry.authorize_request(
    "GET",
    "/api/me",
    "",
    deployment_mode="trusted_team",
    dev_local_unsafe=False,
    install_window_open=False,
    validate_session=lambda _s: None,
    attach_user=lambda _u: None,
)

# ROUTES table: dispatched routes have handlers on server.Handler
server_src = (ROOT / "server.py").read_text(encoding="utf-8")
missing_handlers: list[str] = []
for route in route_registry.ROUTES:
    if not route.handler:
        continue
    if f"def {route.handler}(" not in server_src:
        missing_handlers.append(f"{route.method} {route.path} -> {route.handler}")
assert not missing_handlers, f"missing handler methods: {missing_handlers}"

# Every if-chain literal /api path must be registered with explicit auth
handler_paths = set(re.findall(r'if path == "(/api/[^"]+)"', server_src))
handler_paths |= set(re.findall(r"if path == \'(/api/[^\']+)\'", server_src))
unregistered: list[str] = []
for p in sorted(handler_paths):
    if route_registry.lookup_auth("GET", p) is None and route_registry.lookup_auth("POST", p) is None:
        unregistered.append(p)
assert not unregistered, f"unregistered auth for if-chain paths: {unregistered}"

# Pattern-backed routes from startswith / fullmatch in do_GET/do_POST
_pattern_probes = [
    ("GET", "/api/public/branding/og"),
    ("GET", "/api/workspace/ws-1/rooms"),
    ("GET", "/api/rooms/room-1/messages"),
    ("POST", "/api/rooms/room-1/messages/send"),
    ("PATCH", "/api/workspace/ws-1"),
    ("DELETE", "/api/memory/mem-1"),
]
for method, path in _pattern_probes:
    assert route_registry.lookup_auth(method, path) is not None, f"missing pattern auth: {method} {path}"

# sessionless_ok data GETs
snap = route_registry.lookup_auth("GET", "/api/snapshot")
assert snap is not None and snap.sessionless_ok
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

# owner/admin gate
assert not route_registry.authorize_request(
    "GET",
    "/api/admin/vault/status",
    "sid-ok",
    deployment_mode="trusted_team",
    dev_local_unsafe=False,
    install_window_open=False,
    validate_session=lambda s: {"user_id": "u1"} if s == "sid-ok" else None,
    attach_user=lambda _u: None,
    get_workspace_role=lambda: "member",
)
assert route_registry.authorize_request(
    "GET",
    "/api/admin/vault/status",
    "sid-ok",
    deployment_mode="trusted_team",
    dev_local_unsafe=False,
    install_window_open=False,
    validate_session=lambda s: {"user_id": "u1"} if s == "sid-ok" else None,
    attach_user=lambda _u: None,
    get_workspace_role=lambda: "owner",
)

dispatched_get = [r for r in route_registry.ROUTES if r.method == "GET" and r.handler]
assert len(dispatched_get) == 55
dispatched_post = [r for r in route_registry.ROUTES if r.method == "POST" and r.handler]
assert len(dispatched_post) == 41
dispatched_patch = [r for r in route_registry.ROUTES if r.method == "PATCH" and r.handler]
assert len(dispatched_patch) == 4
pattern_dispatched = [rp for rp in route_registry.ROUTE_PATTERNS if rp.handler]
assert len(pattern_dispatched) == 29

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

class _GetStub:
    def __init__(self) -> None:
        self.called = False
        self.pattern_called = False

    def _route_get_admin_vault_status(self, qs: dict) -> None:
        self.called = True

    def _route_pattern_get_workspace_events(self, path: str, qs: dict) -> None:
        self.pattern_called = True

_get_stub = _GetStub()
assert route_registry.dispatch_get(_get_stub, "/api/admin/vault/status", {})
assert _get_stub.called
assert route_registry.dispatch_get(_get_stub, "/api/admin/vault/status", {})  # idempotent call ok

assert route_registry.dispatch_pattern(
    "GET", _get_stub, "/api/workspace/ws-1/events", qs={},
) is True
assert _get_stub.pattern_called

class _PatchStub:
    def __init__(self) -> None:
        self.called = False

    def _route_patch_me(self, body: dict) -> None:
        self.called = True

_patch_stub = _PatchStub()
assert route_registry.dispatch_patch(_patch_stub, "/api/me", {"display_name": "x"})
assert _patch_stub.called

# No legacy frozenset allowlists
assert not hasattr(route_registry, "GET_ALWAYS_PUBLIC_ROUTES")
assert not hasattr(route_registry, "GET_SINGLE_USER_PUBLIC_ROUTES")
assert not hasattr(route_registry, "GET_PUBLIC_ROUTES")

print("route registry self-check ok")
