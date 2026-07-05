"""Declarative API route auth registry (WF-037).

Deny-by-default: every /api/* path resolves to an AuthLevel; handlers stay in server.py for now.
"""
from __future__ import annotations

from enum import Enum


class AuthLevel(str, Enum):
    PUBLIC = "public"
    SINGLE_USER_GET = "single_user_get"
    AUTH_FLOW = "auth_flow"
    INSTALL = "install"
    SESSION = "session"


GET_ALWAYS_PUBLIC_ROUTES = frozenset({
    "/api/meta",
    "/api/health",
    "/api/setup/status",
    "/api/install/status",
    "/api/public/site-meta",
    "/api/public/link-preview",
    "/api/public/manifest.webmanifest",
    "/api/auth/google/callback",
})

GET_SINGLE_USER_PUBLIC_ROUTES = frozenset({
    "/api/files/read",
    "/api/files/raw",
    "/api/files/tree",
    "/api/files/list",
    "/api/files/state",
    "/api/board",
    "/api/content",
    "/api/content/get",
    "/api/agents",
    "/api/snapshot",
    "/api/hermes/usage",
    "/api/hermes/profile",
    "/api/hermes/debug",
    "/api/hermes/insights",
    "/api/hermes/gquota",
    "/api/hermes/models",
    "/api/hermes/skills",
    "/api/hermes/commands",
    "/api/routes",
    "/api/chat/session",
    "/api/chat/resolve",
    "/api/chat/messages",
    "/api/profiles",
})

AUTH_FLOW_POST_ROUTES = frozenset({
    "/api/auth/start",
    "/api/auth/verify",
    "/api/auth/logout",
    "/api/auth/refresh",
    "/api/auth/bootstrap",
    "/api/setup",
    "/api/auth/google/start",
    "/api/auth/local-bootstrap",
})

INSTALL_ROUTE_METHODS: dict[str, frozenset[str]] = {
    "GET": frozenset({
        "/api/install/publish-hints",
        "/api/install/url/test",
    }),
    "PATCH": frozenset({"/api/install/stack"}),
    "POST": frozenset({
        "/api/install/email/test",
        "/api/install/complete",
        "/api/install/url/test",
        "/api/install/setup-https",
    }),
}


def resolve_auth_level(method: str, path: str) -> AuthLevel:
    """Map HTTP method + path to required auth level. All /api/* paths are covered."""
    m = str(method or "GET").upper()
    p = str(path or "").strip()
    if m == "GET" and p == "/api/auth/hermes-dashboard-gate":
        return AuthLevel.PUBLIC
    if m == "GET" and p in GET_ALWAYS_PUBLIC_ROUTES:
        return AuthLevel.PUBLIC
    if p.startswith("/api/public/"):
        return AuthLevel.PUBLIC
    if m == "GET" and p in GET_SINGLE_USER_PUBLIC_ROUTES:
        return AuthLevel.SINGLE_USER_GET
    if m == "POST" and p in AUTH_FLOW_POST_ROUTES:
        return AuthLevel.AUTH_FLOW
    if p in INSTALL_ROUTE_METHODS.get(m, frozenset()):
        return AuthLevel.INSTALL
    if m == "GET" and p == "/api/install/stack":
        return AuthLevel.INSTALL
    if p.startswith("/api/"):
        return AuthLevel.SESSION
    return AuthLevel.PUBLIC


def deployment_allows_sessionless_data_get(
    deployment_mode: str,
    *,
    dev_local_unsafe: bool = False,
) -> bool:
    return deployment_mode == "single_user_local" or dev_local_unsafe


def sessionless_get_allowed(
    path: str,
    *,
    deployment_mode: str,
    dev_local_unsafe: bool = False,
) -> bool:
    level = resolve_auth_level("GET", path)
    if level == AuthLevel.PUBLIC:
        return True
    if level == AuthLevel.SINGLE_USER_GET:
        return deployment_allows_sessionless_data_get(
            deployment_mode, dev_local_unsafe=dev_local_unsafe,
        )
    return False


def authorize_request(
    method: str,
    path: str,
    session_id: str,
    *,
    deployment_mode: str,
    dev_local_unsafe: bool,
    install_window_open: bool,
    validate_session,
    attach_user,
) -> bool:
    """Return True when the request may proceed to the handler."""
    m = str(method or "GET").upper()
    if dev_local_unsafe:
        if session_id:
            info = validate_session(session_id)
            if info:
                attach_user(info["user_id"])
        return True
    if m == "OPTIONS":
        return True

    level = resolve_auth_level(m, path)
    sid = str(session_id or "").strip()

    if level == AuthLevel.PUBLIC:
        if sid:
            info = validate_session(sid)
            if info:
                attach_user(info["user_id"])
        return True

    if level == AuthLevel.SINGLE_USER_GET:
        if m != "GET":
            return _require_session(sid, validate_session, attach_user)
        if deployment_allows_sessionless_data_get(
            deployment_mode, dev_local_unsafe=dev_local_unsafe,
        ):
            if sid:
                info = validate_session(sid)
                if info:
                    attach_user(info["user_id"])
            return True
        return _require_session(sid, validate_session, attach_user)

    if level == AuthLevel.AUTH_FLOW:
        return True

    if level == AuthLevel.INSTALL:
        if not install_window_open:
            return False
        if sid:
            info = validate_session(sid)
            if info:
                attach_user(info["user_id"])
        return True

    if level == AuthLevel.SESSION:
        return _require_session(sid, validate_session, attach_user)

    return False


def _require_session(sid: str, validate_session, attach_user) -> bool:
    if not sid:
        return False
    info = validate_session(sid)
    if not info:
        return False
    attach_user(info["user_id"])
    return True


def iter_registered_api_paths() -> frozenset[tuple[str, str]]:
    """Exact (method, path) pairs declared in the registry (for audit tests)."""
    out: set[tuple[str, str]] = set()
    for p in GET_ALWAYS_PUBLIC_ROUTES:
        out.add(("GET", p))
    for p in GET_SINGLE_USER_PUBLIC_ROUTES:
        out.add(("GET", p))
    for p in AUTH_FLOW_POST_ROUTES:
        out.add(("POST", p))
    for m, paths in INSTALL_ROUTE_METHODS.items():
        for p in paths:
            out.add((m, p))
    out.add(("GET", "/api/install/stack"))
    out.add(("PATCH", "/api/install/stack"))
    out.add(("GET", "/api/auth/hermes-dashboard-gate"))
    return frozenset(out)
