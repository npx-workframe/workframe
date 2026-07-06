"""Declarative API route registry (WF-037).

Deny-by-default auth tiers plus batched handler dispatch; handler bodies live on server.Handler.
Unknown /api/* paths pass auth and return 404 at dispatch; registered paths without auth → 401.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class AuthLevel(str, Enum):
    PUBLIC = "public"
    SESSION = "session"
    ROLE_OWNER_ADMIN = "role_owner_admin"
    INTERNAL = "internal"


@dataclass(frozen=True, slots=True)
class Route:
    method: str
    path: str
    auth: AuthLevel
    handler: str | None = None
    sessionless_ok: bool = False
    install_window: bool = False


@dataclass(frozen=True, slots=True)
class RoutePattern:
    method: str
    pattern: re.Pattern[str]
    label: str
    auth: AuthLevel
    sessionless_ok: bool = False
    install_window: bool = False


# Exact routes — handler set when dispatched via registry; auth always required.
ROUTES: tuple[Route, ...] = (
    # --- public GET ---
    Route("GET", "/api/meta", AuthLevel.PUBLIC, "_route_get_meta"),
    Route("GET", "/api/health", AuthLevel.PUBLIC, "_route_get_health"),
    Route("GET", "/api/setup/status", AuthLevel.PUBLIC, "_route_get_setup_status"),
    Route("GET", "/api/install/status", AuthLevel.PUBLIC, "_route_get_install_status"),
    Route("GET", "/api/public/site-meta", AuthLevel.PUBLIC, "_route_get_public_site_meta"),
    Route("GET", "/api/public/link-preview", AuthLevel.PUBLIC, "_route_get_public_link_preview"),
    Route("GET", "/api/public/manifest.webmanifest", AuthLevel.PUBLIC, "_route_get_public_manifest"),
    Route("GET", "/api/auth/hermes-dashboard-gate", AuthLevel.PUBLIC),
    Route("GET", "/api/auth/google/callback", AuthLevel.PUBLIC),
    # --- sessionless_ok GET (single_user_local / DEV_LOCAL_UNSAFE) ---
    Route("GET", "/api/agents", AuthLevel.SESSION, "_route_get_agents", sessionless_ok=True),
    Route("GET", "/api/snapshot", AuthLevel.SESSION, "_route_get_snapshot", sessionless_ok=True),
    Route("GET", "/api/board", AuthLevel.SESSION, "_route_get_board", sessionless_ok=True),
    Route("GET", "/api/content", AuthLevel.SESSION, "_route_get_content", sessionless_ok=True),
    Route("GET", "/api/content/get", AuthLevel.SESSION, "_route_get_content_get", sessionless_ok=True),
    Route("GET", "/api/files/tree", AuthLevel.SESSION, "_route_get_files_tree", sessionless_ok=True),
    Route("GET", "/api/files/list", AuthLevel.SESSION, "_route_get_files_list", sessionless_ok=True),
    Route("GET", "/api/files/state", AuthLevel.SESSION, "_route_get_files_state", sessionless_ok=True),
    Route("GET", "/api/files/read", AuthLevel.SESSION, "_route_get_files_read", sessionless_ok=True),
    Route("GET", "/api/files/raw", AuthLevel.SESSION, "_route_get_files_raw", sessionless_ok=True),
    Route("GET", "/api/routes", AuthLevel.SESSION, "_route_get_routes", sessionless_ok=True),
    Route("GET", "/api/chat/messages", AuthLevel.SESSION, "_route_get_chat_messages", sessionless_ok=True),
    Route("GET", "/api/chat/session", AuthLevel.SESSION, "_route_get_chat_session", sessionless_ok=True),
    Route("GET", "/api/chat/resolve", AuthLevel.SESSION, "_route_get_chat_resolve", sessionless_ok=True),
    Route("GET", "/api/hermes/skills", AuthLevel.SESSION, "_route_get_hermes_skills", sessionless_ok=True),
    Route("GET", "/api/hermes/commands", AuthLevel.SESSION, "_route_get_hermes_commands", sessionless_ok=True),
    Route("GET", "/api/hermes/usage", AuthLevel.SESSION, "_route_get_hermes_usage", sessionless_ok=True),
    Route("GET", "/api/hermes/profile", AuthLevel.SESSION, "_route_get_hermes_profile", sessionless_ok=True),
    Route("GET", "/api/hermes/models", AuthLevel.SESSION, "_route_get_hermes_models", sessionless_ok=True),
    Route("GET", "/api/hermes/debug", AuthLevel.SESSION, "_route_get_hermes_debug", sessionless_ok=True),
    Route("GET", "/api/hermes/insights", AuthLevel.SESSION, "_route_get_hermes_insights", sessionless_ok=True),
    Route("GET", "/api/hermes/gquota", AuthLevel.SESSION, "_route_get_hermes_gquota", sessionless_ok=True),
    # --- session GET ---
    Route("GET", "/api/activity/detail", AuthLevel.SESSION, "_route_get_activity_detail"),
    Route("GET", "/api/me", AuthLevel.SESSION, "_route_get_me"),
    Route("GET", "/api/me/onboarding", AuthLevel.SESSION, "_route_get_me_onboarding"),
    Route("GET", "/api/me/credentials", AuthLevel.SESSION, "_route_get_me_credentials"),
    Route("GET", "/api/me/providers", AuthLevel.SESSION, "_route_get_me_providers"),
    Route("GET", "/api/me/cohort", AuthLevel.SESSION, "_route_get_me_cohort"),
    Route("GET", "/api/user/credentials", AuthLevel.SESSION, "_route_get_user_credentials"),
    Route("GET", "/api/hermes/profiles/status", AuthLevel.SESSION),
    Route("GET", "/api/oauth/github/callback", AuthLevel.SESSION),
    Route("GET", "/api/oauth/discord/callback", AuthLevel.SESSION),
    Route("GET", "/api/oauth/stripe/callback", AuthLevel.SESSION),
    Route("GET", "/api/events", AuthLevel.SESSION),
    # --- owner/admin GET ---
    Route("GET", "/api/chat/bootstrap", AuthLevel.ROLE_OWNER_ADMIN),
    Route("GET", "/api/hermes/bootstrap", AuthLevel.ROLE_OWNER_ADMIN),
    Route("GET", "/api/admin/vault/status", AuthLevel.ROLE_OWNER_ADMIN),
    Route("GET", "/api/doctor/agent-dm-runtimes", AuthLevel.ROLE_OWNER_ADMIN),
    Route("GET", "/api/admin/updates", AuthLevel.ROLE_OWNER_ADMIN),
    Route("GET", "/api/admin/audit", AuthLevel.ROLE_OWNER_ADMIN),
    # --- install-window GET ---
    Route("GET", "/api/install/publish-hints", AuthLevel.PUBLIC, install_window=True),
    Route("GET", "/api/install/url/test", AuthLevel.PUBLIC, install_window=True),
    Route("GET", "/api/install/stack", AuthLevel.SESSION, install_window=True),
    # --- internal GET ---
    Route("GET", "/api/supervisor/v1/profile.status", AuthLevel.SESSION),
    Route("GET", "/api/supervisor/v1/stack.status", AuthLevel.SESSION),
    # --- public POST (auth flow) ---
    Route("POST", "/api/auth/start", AuthLevel.PUBLIC, "_route_post_auth_start"),
    Route("POST", "/api/auth/verify", AuthLevel.PUBLIC, "_route_post_auth_verify"),
    Route("POST", "/api/auth/logout", AuthLevel.PUBLIC, "_route_post_auth_logout"),
    Route("POST", "/api/auth/refresh", AuthLevel.PUBLIC, "_route_post_auth_refresh"),
    Route("POST", "/api/auth/bootstrap", AuthLevel.PUBLIC, "_route_post_auth_bootstrap"),
    Route("POST", "/api/auth/google/start", AuthLevel.PUBLIC, "_route_post_auth_google_start"),
    Route("POST", "/api/auth/local-bootstrap", AuthLevel.PUBLIC, "_route_post_auth_local_bootstrap"),
    Route("POST", "/api/setup", AuthLevel.PUBLIC, "_route_post_setup"),
    # --- session POST ---
    Route("POST", "/api/hermes/model", AuthLevel.SESSION, "_route_post_hermes_model"),
    Route("POST", "/api/hermes/model/apply-default", AuthLevel.SESSION, "_route_post_hermes_model_apply_default"),
    Route("POST", "/api/hermes/fallback-chain", AuthLevel.SESSION, "_route_post_hermes_fallback_chain"),
    Route("POST", "/api/hermes/commands/exec", AuthLevel.SESSION, "_route_post_hermes_commands_exec"),
    Route("POST", "/api/hermes/gateway/exec", AuthLevel.SESSION, "_route_post_hermes_gateway_exec"),
    Route("POST", "/api/chat/stop", AuthLevel.SESSION, "_route_post_chat_stop"),
    Route("POST", "/api/chat/steer", AuthLevel.SESSION, "_route_post_chat_steer"),
    Route("POST", "/api/me/credentials", AuthLevel.SESSION, "_route_post_me_credentials"),
    Route("POST", "/api/me/telegram/link", AuthLevel.SESSION, "_route_post_me_telegram_link"),
    Route("POST", "/api/board", AuthLevel.SESSION, "_route_post_board"),
    Route("POST", "/api/board/update", AuthLevel.SESSION, "_route_post_board_update"),
    Route("POST", "/api/board/delete", AuthLevel.SESSION, "_route_post_board_delete"),
    Route("POST", "/api/content/save", AuthLevel.SESSION, "_route_post_content_save"),
    Route("POST", "/api/content/delete", AuthLevel.SESSION, "_route_post_content_delete"),
    Route("POST", "/api/files/write", AuthLevel.SESSION, "_route_post_files_write"),
    Route("POST", "/api/files/upload", AuthLevel.SESSION, "_route_post_files_upload"),
    Route("POST", "/api/chat/dispatch", AuthLevel.SESSION, "_route_post_chat_dispatch"),
    Route("POST", "/api/me", AuthLevel.SESSION),
    Route("POST", "/api/me/native-agent", AuthLevel.SESSION),
    Route("POST", "/api/hermes/profiles/create", AuthLevel.SESSION),
    Route("POST", "/api/hermes/profiles/start", AuthLevel.SESSION),
    Route("POST", "/api/hermes/profiles/stop", AuthLevel.SESSION),
    Route("POST", "/api/hermes/profiles/delete", AuthLevel.SESSION),
    Route("POST", "/api/hermes/profiles/disable", AuthLevel.SESSION),
    Route("POST", "/api/doctor/repair", AuthLevel.SESSION),
    # --- owner/admin POST ---
    Route("POST", "/api/admin/updates/apply", AuthLevel.ROLE_OWNER_ADMIN),
    Route("POST", "/api/admin/stack/restart-gateway", AuthLevel.ROLE_OWNER_ADMIN),
    Route("POST", "/api/admin/vault/init", AuthLevel.ROLE_OWNER_ADMIN),
    Route("POST", "/api/admin/vault/unlock", AuthLevel.ROLE_OWNER_ADMIN),
    Route("POST", "/api/admin/vault/seal", AuthLevel.ROLE_OWNER_ADMIN),
    Route("POST", "/api/admin/vault/wipe", AuthLevel.ROLE_OWNER_ADMIN),
    Route("POST", "/api/install/stack/branding-asset", AuthLevel.ROLE_OWNER_ADMIN),
    # --- install-window POST ---
    Route("POST", "/api/install/email/test", AuthLevel.PUBLIC, install_window=True),
    Route("POST", "/api/install/url/test", AuthLevel.PUBLIC, install_window=True),
    Route("POST", "/api/install/setup-https", AuthLevel.PUBLIC, install_window=True),
    Route("POST", "/api/install/complete", AuthLevel.PUBLIC, install_window=True),
    Route("POST", "/api/install/stack", AuthLevel.SESSION, install_window=True),
    # --- PATCH ---
    Route("PATCH", "/api/me", AuthLevel.SESSION),
    Route("PATCH", "/api/install/stack", AuthLevel.SESSION, install_window=True),
)

_ROUTE_PATTERNS_RAW: tuple[tuple[str, str, str, AuthLevel, bool, bool], ...] = (
    # method, regex, label, auth, sessionless_ok, install_window
    ("GET", r"^/api/public/branding/(og|favicon)$", "/api/public/branding/{kind}", AuthLevel.PUBLIC, False, False),
    ("GET", r"^/api/workspace/[^/]+$", "/api/workspace/{id}", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/workspace/[^/]+/rooms$", "/api/workspace/{id}/rooms", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/rooms/[^/]+$", "/api/rooms/{id}", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/rooms/[^/]+/members$", "/api/rooms/{id}/members", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/rooms/[^/]+/live$", "/api/rooms/{id}/live", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/rooms/[^/]+/activity$", "/api/rooms/{id}/activity", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/workspace/[^/]+/activity$", "/api/workspace/{id}/activity", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/workspace/[^/]+/kanban/tasks$", "/api/workspace/{id}/kanban/tasks", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/workspace/[^/]+/delegation-grants$", "/api/workspace/{id}/delegation-grants", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/rooms/[^/]+/sessions$", "/api/rooms/{id}/sessions", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/workspace/[^/]+/invites$", "/api/workspace/{id}/invites", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/invites/[^/]+$", "/api/invites/{token}", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/workspace/[^/]+/members$", "/api/workspace/{id}/members", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/workspace/[^/]+/memory$", "/api/workspace/{id}/memory", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/workspace/[^/]+/budget$", "/api/workspace/{id}/budget", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/workspace/[^/]+/grants$", "/api/workspace/{id}/grants", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/rooms/[^/]+/messages$", "/api/rooms/{id}/messages", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/workspace/[^/]+/events$", "/api/workspace/{id}/events", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/me/oauth/[^/]+/status$", "/api/me/oauth/{provider}/status", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/hermes/profiles/[^/]+/soul$", "/api/hermes/profiles/{slug}/soul", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/hermes/profiles/[^/]+/sessions$", "/api/hermes/profiles/{slug}/sessions", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/hermes/profiles/[^/]+/bind$", "/api/hermes/profiles/{slug}/bind", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/hermes/profiles/[^/]+$", "/api/hermes/profiles/{slug}", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/workspace/[^/]+/credentials$", "/api/workspace/{id}/credentials", AuthLevel.SESSION, False, False),
    ("GET", r"^/api/agents/[^/]+/credentials$", "/api/agents/{id}/credentials", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/me/oauth/[^/]+/start$", "/api/me/oauth/{provider}/start", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/me/providers/[^/]+/disconnect$", "/api/me/providers/{id}/disconnect", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/workspace/[^/]+/credentials/store$", "/api/workspace/{id}/credentials/store", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/workspace/[^/]+/credentials/[^/]+/revoke$", "/api/workspace/{id}/credentials/{cid}/revoke", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/workspace/[^/]+/rooms$", "/api/workspace/{id}/rooms", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/workspace/[^/]+/rooms/create$", "/api/workspace/{id}/rooms/create", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/rooms/[^/]+/members$", "/api/rooms/{id}/members", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/rooms/[^/]+/bind$", "/api/rooms/{id}/bind", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/rooms/[^/]+/sessions/activate$", "/api/rooms/{id}/sessions/activate", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/rooms/[^/]+/messages/send$", "/api/rooms/{id}/messages/send", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/workspace/[^/]+/invites$", "/api/workspace/{id}/invites", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/invites/[^/]+/accept$", "/api/invites/{token}/accept", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/workspace/[^/]+/members$", "/api/workspace/{id}/members", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/workspace/[^/]+/kanban/tasks$", "/api/workspace/{id}/kanban/tasks", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/workspace/[^/]+/delegation-grants$", "/api/workspace/{id}/delegation-grants", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/workspace/[^/]+/runtime-profiles/purge$", "/api/workspace/{id}/runtime-profiles/purge", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/workspace/[^/]+/memory$", "/api/workspace/{id}/memory", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/memory/[^/]+$", "/api/memory/{id}", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/workspace/[^/]+/budget$", "/api/workspace/{id}/budget", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/workspace/[^/]+/grants$", "/api/workspace/{id}/grants", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/hermes/profiles/[^/]+/bootstrap-dm$", "/api/hermes/profiles/{slug}/bootstrap-dm", AuthLevel.SESSION, False, False),
    ("POST", r"^/api/hermes/profiles/[^/]+/soul$", "/api/hermes/profiles/{slug}/soul", AuthLevel.SESSION, False, False),
    ("PATCH", r"^/api/hermes/profiles/[^/]+$", "/api/hermes/profiles/{slug}", AuthLevel.SESSION, False, False),
    ("PATCH", r"^/api/rooms/[^/]+$", "/api/rooms/{id}", AuthLevel.SESSION, False, False),
    ("PATCH", r"^/api/workspace/[^/]+/integrations$", "/api/workspace/{id}/integrations", AuthLevel.SESSION, False, False),
    ("PATCH", r"^/api/workspace/[^/]+$", "/api/workspace/{id}", AuthLevel.SESSION, False, False),
    ("DELETE", r"^/api/rooms/[^/]+$", "/api/rooms/{id}", AuthLevel.SESSION, False, False),
    ("DELETE", r"^/api/memory/[^/]+$", "/api/memory/{id}", AuthLevel.SESSION, False, False),
    ("DELETE", r"^/api/workspace/[^/]+/members$", "/api/workspace/{id}/members", AuthLevel.SESSION, False, False),
    ("DELETE", r"^/api/me/credentials/[^/]+$", "/api/me/credentials/{provider}", AuthLevel.SESSION, False, False),
)

ROUTE_PATTERNS: tuple[RoutePattern, ...] = tuple(
    RoutePattern(method=m, pattern=re.compile(rx), label=label, auth=auth, sessionless_ok=sl, install_window=iw)
    for m, rx, label, auth, sl, iw in _ROUTE_PATTERNS_RAW
)

_ROUTES_BY_METHOD_PATH: dict[tuple[str, str], Route] = {
    (r.method.upper(), r.path): r for r in ROUTES
}

_DISPATCH_ROUTES: dict[tuple[str, str], Route] = {
    (r.method.upper(), r.path): r for r in ROUTES if r.handler
}


@dataclass(frozen=True, slots=True)
class AuthSpec:
    auth: AuthLevel
    sessionless_ok: bool = False
    install_window: bool = False


def lookup_auth(method: str, path: str) -> AuthSpec | None:
    """Return auth spec for a registered /api/* route, or None when unregistered."""
    m = str(method or "GET").upper()
    p = str(path or "").strip()
    if not p.startswith("/api/"):
        return None
    exact = _ROUTES_BY_METHOD_PATH.get((m, p))
    if exact:
        return AuthSpec(exact.auth, sessionless_ok=exact.sessionless_ok, install_window=exact.install_window)
    for rp in ROUTE_PATTERNS:
        if rp.method == m and rp.pattern.fullmatch(p):
            return AuthSpec(rp.auth, sessionless_ok=rp.sessionless_ok, install_window=rp.install_window)
    if p.startswith("/api/public/"):
        return AuthSpec(AuthLevel.PUBLIC)
    if p.startswith("/internal/"):
        return AuthSpec(AuthLevel.INTERNAL)
    return None


def resolve_auth_level(method: str, path: str) -> AuthLevel | None:
    """Map HTTP method + path to required auth level. None = unregistered /api/* (404 at dispatch)."""
    spec = lookup_auth(method, path)
    return spec.auth if spec else None


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
    spec = lookup_auth("GET", path)
    if spec is None:
        return False
    if spec.auth == AuthLevel.PUBLIC:
        return True
    if spec.sessionless_ok and deployment_allows_sessionless_data_get(
        deployment_mode, dev_local_unsafe=dev_local_unsafe,
    ):
        return True
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
    get_workspace_role=None,
) -> bool:
    """Return True when the request may proceed. Unregistered /api/* passes (404 later)."""
    m = str(method or "GET").upper()
    p = str(path or "").strip()

    if dev_local_unsafe:
        sid = str(session_id or "").strip()
        if sid:
            info = validate_session(sid)
            if info:
                attach_user(info["user_id"])
        return True
    if m == "OPTIONS":
        return True
    if not p.startswith("/api/"):
        return True

    spec = lookup_auth(m, p)
    if spec is None:
        return True

    sid = str(session_id or "").strip()

    if spec.install_window and install_window_open:
        if sid:
            info = validate_session(sid)
            if info:
                attach_user(info["user_id"])
        return True

    level = spec.auth

    if level == AuthLevel.PUBLIC:
        if spec.install_window and not install_window_open:
            return False
        if sid:
            info = validate_session(sid)
            if info:
                attach_user(info["user_id"])
        return True

    if level == AuthLevel.INTERNAL:
        return True

    if level == AuthLevel.SESSION:
        if m == "GET" and spec.sessionless_ok and deployment_allows_sessionless_data_get(
            deployment_mode, dev_local_unsafe=dev_local_unsafe,
        ):
            if sid:
                info = validate_session(sid)
                if info:
                    attach_user(info["user_id"])
            return True
        return _require_session(sid, validate_session, attach_user)

    if level == AuthLevel.ROLE_OWNER_ADMIN:
        if not _require_session(sid, validate_session, attach_user):
            return False
        role = ""
        if callable(get_workspace_role):
            role = str(get_workspace_role() or "").strip().lower()
        return role in {"owner", "admin"}

    return False


def lookup_route(method: str, path: str) -> Route | None:
    return _DISPATCH_ROUTES.get((str(method or "GET").upper(), str(path or "").strip()))


def dispatch_get(handler: Any, path: str, qs: dict[str, list[str]]) -> bool:
    """Invoke a registered GET handler on *handler*; return True when dispatched."""
    route = lookup_route("GET", path)
    if not route or not route.handler:
        return False
    fn = getattr(handler, route.handler, None)
    if not callable(fn):
        raise RuntimeError(f"missing handler {route.handler!r} for GET {path}")
    fn(qs)
    return True


def dispatch_post(handler: Any, path: str, body: dict) -> bool:
    """Invoke a registered POST handler on *handler*; return True when dispatched."""
    route = lookup_route("POST", path)
    if not route or not route.handler:
        return False
    fn = getattr(handler, route.handler, None)
    if not callable(fn):
        raise RuntimeError(f"missing handler {route.handler!r} for POST {path}")
    fn(body)
    return True


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
    for route in ROUTES:
        out.add((route.method.upper(), route.path))
    return frozenset(out)
