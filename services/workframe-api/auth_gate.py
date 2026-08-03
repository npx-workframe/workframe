"""Auth gate: session, CORS/host validation, deployment mode (WF-032)."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from email_sender import APP_BASE_URL
import internal_proxy_auth
import route_registry
import stack_config
import zk_auth as _zk

DASHBOARD_HTTP_TIMEOUT = float(os.environ.get("HERMES_DASHBOARD_HTTP_TIMEOUT", "15"))
WORKFRAME_AUTH_INSECURE = os.environ.get("WORKFRAME_AUTH_INSECURE", "0").strip() in {"1", "true", "yes"}
DOCKER_SOCK = os.environ.get("DOCKER_SOCK", "/var/run/docker.sock")

OWNER_ADMIN_ROLES = {"owner", "admin"}


def _srv():
    import server as srv

    return srv


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _dashboard_session_token(internal_url: str) -> str:
    import http.cookiejar

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def _fetch_html(url: str) -> str:
        with opener.open(url, timeout=DASHBOARD_HTTP_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _token_from_html(html: str) -> str:
        token_match = re.search(r"__HERMES_SESSION_TOKEN__=\"([^\"]+)\"", html)
        return token_match.group(1) if token_match else ""

    try:
        html = _fetch_html(f"{internal_url}/")
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"dashboard unavailable: {exc}") from exc

    token = _token_from_html(html)
    if token:
        return token

    user = os.environ.get("HERMES_DASHBOARD_BASIC_AUTH_USERNAME", "").strip()
    password = os.environ.get("HERMES_DASHBOARD_BASIC_AUTH_PASSWORD", "").strip()
    if user and password:
        body = json.dumps({"username": user, "password": password}).encode("utf-8")
        req = urllib.request.Request(
            f"{internal_url}/auth/password-login",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            opener.open(req, timeout=DASHBOARD_HTTP_TIMEOUT).read()
            html = _fetch_html(f"{internal_url}/")
            token = _token_from_html(html)
            if token:
                return token
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"dashboard login failed: {exc}") from exc

    raise ValueError("dashboard session token not found")


def _resolve_mode_flags() -> tuple[bool, bool]:
    secure = _is_truthy(os.environ.get("SECURE_MODE"))
    dev_unsafe = _is_truthy(os.environ.get("DEV_LOCAL_UNSAFE"))
    if secure and dev_unsafe:
        raise SystemExit(
            "SECURE_MODE and DEV_LOCAL_UNSAFE are mutually exclusive. "
            "Set one or neither (neither defaults to secure)."
        )
    if not secure and not dev_unsafe:
        secure = True
    return secure, dev_unsafe


def _require_auth_token() -> str:
    token = os.environ.get("WORKFRAME_API_TOKEN", "").strip()
    if token:
        return token
    dashboard_url = os.environ.get("HERMES_DASHBOARD_URL", "http://127.0.0.1:9119")
    return _dashboard_session_token(dashboard_url)


SECURE_MODE, DEV_LOCAL_UNSAFE = _resolve_mode_flags()
DEPLOYMENT_MODES = frozenset({"single_user_local", "trusted_team", "public_multi_user"})


def _resolve_deployment_mode() -> str:
    mode = stack_config.resolve_deployment_mode("trusted_team")
    if mode not in DEPLOYMENT_MODES:
        raise SystemExit(
            f"Invalid WORKFRAME_DEPLOYMENT_MODE={mode!r}. "
            f"Use one of: {', '.join(sorted(DEPLOYMENT_MODES))}"
        )
    return mode


DEPLOYMENT_MODE = _resolve_deployment_mode()


def _invite_only_login_enforced() -> bool:
    if DEPLOYMENT_MODE == "single_user_local" or DEV_LOCAL_UNSAFE:
        return False
    return not _srv()._install_window_open()


def _primary_workspace_row(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, display_name FROM workspaces
        WHERE deleted_at IS NULL
        ORDER BY CASE WHEN slug = 'default' THEN 0 ELSE 1 END, created_at ASC
        LIMIT 1
        """,
    ).fetchone()


def _pending_invite_for_email(conn: sqlite3.Connection, workspace_id: str, email: str) -> sqlite3.Row | None:
    now_ts = int(time.time())
    return conn.execute(
        """
        SELECT id FROM workspace_invites
        WHERE workspace_id = ? AND LOWER(email) = ? AND deleted_at IS NULL
          AND accepted_at IS NULL AND CAST(expires_at AS INTEGER) > ?
        LIMIT 1
        """,
        (workspace_id, str(email or "").strip().lower(), now_ts),
    ).fetchone()


def email_allowed_to_authenticate(email: str) -> tuple[bool, dict[str, Any]]:
    normalized = str(email or "").strip().lower()
    if not normalized or "@" not in normalized:
        return False, {"error": "email required"}
    if not _invite_only_login_enforced():
        return True, {}
    conn = _srv()._workframe_db()
    try:
        ws = _primary_workspace_row(conn)
        if not ws:
            return True, {}
        ws_id = str(ws["id"])
        user_count = int(conn.execute("SELECT COUNT(*) FROM users WHERE deleted_at IS NULL").fetchone()[0] or 0)
        if user_count == 0:
            return True, {}
        member = conn.execute(
            """
            SELECT 1 FROM workspace_memberships wm
            JOIN users u ON u.id = wm.user_id
            WHERE wm.workspace_id = ? AND wm.deleted_at IS NULL AND wm.status = 'active'
              AND LOWER(u.email) = ?
            LIMIT 1
            """,
            (ws_id, normalized),
        ).fetchone()
        if member:
            return True, {}
        if _pending_invite_for_email(conn, ws_id, normalized):
            return True, {}
        display = str(ws["display_name"] or "this workspace")
        return False, {
            "error": "private_workspace",
            "workspace_name": display,
            "message": (
                f'This Workframe is private. Contact the Admin of "{display}" to get an invite link.'
            ),
        }
    finally:
        conn.close()


def invite_token_allows_email(invite_token: str, email: str) -> bool:
    token = str(invite_token or "").strip()
    if not token:
        return False
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    normalized = str(email or "").strip().lower()
    conn = _srv()._workframe_db()
    try:
        inv = conn.execute(
            """
            SELECT email, expires_at FROM workspace_invites
            WHERE token_hash = ? AND deleted_at IS NULL AND accepted_at IS NULL
            LIMIT 1
            """,
            (token_hash,),
        ).fetchone()
        if not inv or str(inv["email"]).strip().lower() != normalized:
            return False
        return int(inv["expires_at"]) > int(time.time())
    finally:
        conn.close()


def deployment_security_errors() -> list[str]:
    errors: list[str] = []
    if DEPLOYMENT_MODE != "public_multi_user":
        return errors
    if _srv()._install_window_open():
        return errors
    if DEV_LOCAL_UNSAFE:
        errors.append("public_multi_user cannot run with DEV_LOCAL_UNSAFE")
    if not SECURE_MODE:
        errors.append("public_multi_user requires SECURE_MODE=true")
    if not _srv()._supervisor_ready():
        errors.append("public_multi_user requires WORKFRAME_SUPERVISOR_URL and WORKFRAME_SUPERVISOR_TOKEN")
    for key in ("ZK_AUTH_HMAC_KEY", "ZK_AUTH_ENCRYPTION_KEY", "ZK_AUTH_SESSION_SECRET"):
        if not os.environ.get(key, "").strip():
            errors.append(f"public_multi_user requires {key}")
    if not os.environ.get("WORKFRAME_API_TOKEN", "").strip():
        errors.append("public_multi_user requires WORKFRAME_API_TOKEN")
    if not stack_config.smtp_configured():
        errors.append("public_multi_user requires SMTP_HOST")
    base = str(stack_config.get_stack_config().get("app_base_url") or APP_BASE_URL).strip()
    if not base.lower().startswith("https://"):
        errors.append("public_multi_user requires HTTPS APP_BASE_URL")
    if not os.environ.get("WORKFRAME_VAULT_KEK", "").strip():
        errors.append("public_multi_user requires WORKFRAME_VAULT_KEK")
    data_dir = _srv().DATA_DIR
    if not os.environ.get("WORKFRAME_PROXY_TOKEN", "").strip() and not (
        data_dir / internal_proxy_auth.PROXY_TOKEN_FILE
    ).is_file():
        errors.append("public_multi_user requires WORKFRAME_PROXY_TOKEN")
    if Path(DOCKER_SOCK).exists():
        errors.append("public_multi_user must not mount docker.sock on workframe-api")
    return errors


def deployment_security_warnings() -> list[str]:
    warnings: list[str] = []
    if DEPLOYMENT_MODE == "trusted_team" and DEV_LOCAL_UNSAFE:
        warnings.append("trusted_team + DEV_LOCAL_UNSAFE: session and dashboard gates are relaxed for local dev")
    return warnings


CORS_ALLOW_ORIGINS = tuple(
    origin.strip()
    for origin in os.environ.get("CORS_ALLOW_ORIGIN", "").split(",")
    if origin.strip() and origin.strip() != "*"
)
ALLOWED_HOSTS = tuple(
    host.strip().lower()
    for host in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if host.strip()
)
DEFAULT_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


def session_cookie_secure() -> bool:
    if DEV_LOCAL_UNSAFE or WORKFRAME_AUTH_INSECURE:
        return False
    if os.environ.get("WORKFRAME_E2E") == "1":
        base = APP_BASE_URL.strip().lower()
        if base.startswith("http://127.0.0.1") or base.startswith("http://localhost"):
            return False
    return APP_BASE_URL.strip().lower().startswith("https://")


AUTH_TOKEN: str = ""


def get_auth_token() -> str:
    global AUTH_TOKEN
    if not AUTH_TOKEN:
        try:
            AUTH_TOKEN = _require_auth_token()
        except Exception as exc:
            raise SystemExit(f"SECURE_MODE: failed to obtain auth token: {exc}") from exc
    return AUTH_TOKEN


def check_auth(request_handler) -> bool:
    if DEV_LOCAL_UNSAFE:
        return True
    if getattr(request_handler, "auth_user", None):
        return True
    auth_header = request_handler.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = get_auth_token()
        if token and hmac.compare_digest(auth_header[7:].strip(), token):
            request_handler.auth_user = "service"
            request_handler.auth_stack_role = "owner"  # type: ignore[attr-defined]
            request_handler.auth_role = "owner"  # type: ignore[attr-defined]
            return True
    sid = session_id_from_request(request_handler)
    if sid:
        session_info = _zk.validate_session_token(sid)
        if session_info:
            apply_session_user(request_handler, session_info["user_id"])
            return True
    return False


def host_without_port(host: str) -> str:
    host = (host or "").strip().lower()
    if not host:
        return ""
    if host.startswith("["):
        end = host.find("]")
        return host[1:end] if end != -1 else host
    if host.count(":") == 1:
        return host.rsplit(":", 1)[0]
    return host


def _url_hostname(url: str) -> str:
    host = urllib.parse.urlsplit(str(url or "").strip()).hostname or ""
    return host.strip().lower()


def allowed_hosts() -> set[str]:
    configured = {host.strip().lower() for host in ALLOWED_HOSTS if host.strip()}
    hosts = configured | DEFAULT_ALLOWED_HOSTS if configured else set(DEFAULT_ALLOWED_HOSTS)
    for base_url in (
        APP_BASE_URL,
        str(stack_config.get_stack_config().get("app_base_url") or ""),
    ):
        host = _url_hostname(base_url)
        if host:
            hosts.add(host)
    return hosts


def loopback_ui_origins() -> set[str]:
    port = str(os.environ.get("WORKFRAME_UI_PORT", "18644") or "18644").strip()
    return {f"http://{host}:{port}" for host in ("127.0.0.1", "localhost", "[::1]")}


def install_setup_route(method: str, path: str) -> bool:
    if path == "/api/install/stack" and method in ("GET", "PATCH"):
        return True
    if path == "/api/install/status" and method == "GET":
        return True
    if path == "/api/install/publish-hints" and method == "GET":
        return True
    if path == "/api/install/url/test" and method in ("GET", "POST"):
        return True
    if method == "POST" and path in (
        "/api/install/email/test",
        "/api/install/complete",
        "/api/install/setup-https",
        "/api/install/register-admin",
    ):
        return True
    return False


def secure_host_origin_ok(method: str, path: str, headers) -> bool:
    if DEV_LOCAL_UNSAFE:
        return True
    if _srv()._install_window_open() and install_setup_route(method, path):
        return True
    return validate_host(headers) and validate_origin(headers)


def validate_host(headers) -> bool:
    if DEV_LOCAL_UNSAFE:
        return True
    return host_without_port(headers.get("Host", "")) in allowed_hosts()


def origin_host(origin: str) -> str:
    parsed = urllib.parse.urlsplit(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    return parsed.hostname.lower()


def origin_allowed(origin: str) -> bool:
    if not origin:
        return True
    origin = origin.strip()
    if origin in CORS_ALLOW_ORIGINS:
        return True
    if origin.rstrip("/") in loopback_ui_origins():
        return True
    if not CORS_ALLOW_ORIGINS:
        return origin_host(origin) in allowed_hosts()
    return False


def validate_origin(headers) -> bool:
    if DEV_LOCAL_UNSAFE:
        return True
    return origin_allowed(headers.get("Origin", ""))


def validate_host_origin(headers) -> bool:
    return validate_host(headers) and validate_origin(headers)


def admin_write_allowed(handler: BaseHTTPRequestHandler) -> bool:
    if SECURE_MODE or not DEV_LOCAL_UNSAFE:
        return True
    return handler.headers.get("X-Workframe-Local", "").strip() == "1"


def cors_origin_for(headers=None) -> str:
    if DEV_LOCAL_UNSAFE:
        return "*"
    if not CORS_ALLOW_ORIGINS:
        return ""
    origin = ""
    if headers is not None:
        origin = headers.get("Origin", "").strip()
    if origin:
        return origin if origin in CORS_ALLOW_ORIGINS else ""
    if len(CORS_ALLOW_ORIGINS) == 1:
        return CORS_ALLOW_ORIGINS[0]
    return ""


def deployment_allows_sessionless_data_get(
    *,
    deployment_mode: str | None = None,
    dev_local_unsafe: bool | None = None,
) -> bool:
    mode = deployment_mode if deployment_mode is not None else _resolve_deployment_mode()
    dev = DEV_LOCAL_UNSAFE if dev_local_unsafe is None else dev_local_unsafe
    return route_registry.deployment_allows_sessionless_data_get(mode, dev_local_unsafe=dev)


def sessionless_get_allowed(
    path: str,
    *,
    deployment_mode: str | None = None,
    dev_local_unsafe: bool | None = None,
) -> bool:
    mode = deployment_mode if deployment_mode is not None else _resolve_deployment_mode()
    dev = DEV_LOCAL_UNSAFE if dev_local_unsafe is None else dev_local_unsafe
    return route_registry.sessionless_get_allowed(path, deployment_mode=mode, dev_local_unsafe=dev)


def is_public_get(path: str) -> bool:
    if path in ("", "/"):
        return True
    if path.startswith("/static/") or path.startswith("/assets/"):
        return True
    return sessionless_get_allowed(path)


def cookie_session_id(handler: BaseHTTPRequestHandler) -> str:
    cookie_header = handler.headers.get("Cookie", "")
    prefix = f"{_zk.session_cookie_name()}="
    legacy_prefix = "wf_session="
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(prefix):
            return part[len(prefix) :]
        if part.startswith(legacy_prefix):
            return part[len(legacy_prefix) :]
    return ""


def session_id_from_request(handler: BaseHTTPRequestHandler) -> str:
    sid = cookie_session_id(handler)
    if sid:
        return sid
    return handler.headers.get("X-Workframe-Session", "").strip()


def _stack_role_for_user(user_id: str) -> str:
    user = str(user_id or "").strip()
    if not user:
        return "member"
    if user == "service":
        return "owner"
    try:
        conn = _srv()._workframe_db()
        try:
            row = conn.execute(
                "SELECT role FROM users WHERE id = ? AND deleted_at IS NULL LIMIT 1",
                (user,),
            ).fetchone()
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return "member"
    role = str(row["role"] or "").strip().lower() if row else ""
    return role if role in OWNER_ADMIN_ROLES else "member"


def workspace_role_for_user(user_id: str) -> str:
    """Legacy aggregate role for diagnostics only; never target-resource authority."""
    rank = {"owner": 3, "admin": 2, "member": 1}
    best = "member"
    try:
        conn = _srv()._workframe_db()
        try:
            rows = conn.execute(
                """
                SELECT role FROM workspace_memberships
                WHERE user_id = ? AND deleted_at IS NULL AND status = 'active'
                """,
                (user_id,),
            ).fetchall()
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return best
    for row in rows:
        role = str(row["role"] or "member")
        if rank.get(role, 0) > rank.get(best, 0):
            best = role
    return best


def apply_session_user(handler: BaseHTTPRequestHandler, user_id: str) -> None:
    stack_role = _stack_role_for_user(user_id)
    handler.auth_user = user_id  # type: ignore[attr-defined]
    handler.auth_stack_role = stack_role  # type: ignore[attr-defined]
    handler.auth_role = stack_role  # type: ignore[attr-defined]
    handler.auth_workspace_id = ""  # type: ignore[attr-defined]


def user_is_stack_operator(user_id: str) -> bool:
    return _stack_role_for_user(user_id) in OWNER_ADMIN_ROLES


def user_can_access_hermes_dashboard(user_id: str) -> bool:
    if DEPLOYMENT_MODE == "single_user_local":
        return True
    if not user_id:
        return False
    return user_is_stack_operator(user_id)


def _workspace_role(
    conn: sqlite3.Connection,
    workspace_id: str,
    user_id: str,
) -> str | None:
    row = conn.execute(
        """
        SELECT wm.role
        FROM workspace_memberships wm
        JOIN workspaces w ON w.id = wm.workspace_id
        WHERE wm.workspace_id = ?
          AND wm.user_id = ?
          AND wm.deleted_at IS NULL
          AND wm.status = 'active'
          AND w.deleted_at IS NULL
          AND w.status = 'active'
        LIMIT 1
        """,
        (workspace_id, user_id),
    ).fetchone()
    return str(row["role"] or "member").strip().lower() if row else None


def _scoped_request_policy(method: str, path: str) -> tuple[str, str, bool] | None:
    """Return (resource kind, resource ref, owner/admin required)."""
    m = str(method or "GET").upper()
    parts = [urllib.parse.unquote(part) for part in str(path or "").strip("/").split("/")]
    if len(parts) < 3 or parts[0] != "api":
        return None

    if parts[1] == "workspace":
        ref = parts[2]
        suffix = "/".join(parts[3:])
        admin = False
        if not suffix:
            admin = m in {"PATCH", "DELETE"}
        elif suffix == "members":
            admin = m in {"POST", "PATCH", "DELETE"}
        elif suffix.startswith("credentials"):
            admin = True
        elif suffix in {
            "invites",
            "budget",
            "grants",
            "integrations",
            "runtime-profiles/purge",
        }:
            admin = True
        return "workspace", ref, admin

    if parts[1] == "rooms":
        admin = (m == "DELETE" and len(parts) == 3) or (m == "PATCH" and len(parts) == 3)
        return "room", parts[2], admin

    if parts[1] == "memory":
        return "memory", parts[2], m == "DELETE"

    if parts[1] == "agents" and len(parts) >= 4 and parts[3] == "credentials":
        return "agent", parts[2], True

    if parts[1] == "invites":
        return "invite", parts[2], False

    return None


def _workspace_id_for_scope(
    conn: sqlite3.Connection,
    kind: str,
    ref: str,
) -> str | None:
    if kind == "workspace":
        row = conn.execute(
            "SELECT id FROM workspaces WHERE (id = ? OR slug = ?) AND deleted_at IS NULL LIMIT 1",
            (ref, ref),
        ).fetchone()
        return str(row["id"]) if row else None
    if kind == "room":
        row = conn.execute(
            "SELECT workspace_id FROM rooms WHERE id = ? AND deleted_at IS NULL LIMIT 1",
            (ref,),
        ).fetchone()
        return str(row["workspace_id"]) if row else None
    if kind == "memory":
        row = conn.execute(
            "SELECT workspace_id FROM memory_items WHERE id = ? AND deleted_at IS NULL LIMIT 1",
            (ref,),
        ).fetchone()
        return str(row["workspace_id"]) if row else None
    if kind == "agent":
        rows = conn.execute(
            """
            SELECT workspace_id FROM agent_profiles
            WHERE (id = ? OR slug = ?) AND deleted_at IS NULL
            ORDER BY CASE WHEN id = ? THEN 0 ELSE 1 END
            LIMIT 2
            """,
            (ref, ref, ref),
        ).fetchall()
        if not rows:
            return None
        if len(rows) > 1 and str(rows[0]["workspace_id"]) != str(rows[1]["workspace_id"]):
            return None
        return str(rows[0]["workspace_id"])
    return None


def _invite_scope_allows(
    conn: sqlite3.Connection,
    handler: BaseHTTPRequestHandler,
    token: str,
    user_id: str,
) -> bool:
    token_hash = hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()
    row = conn.execute(
        """
        SELECT wi.workspace_id, wi.email, wi.expires_at, u.email AS user_email
        FROM workspace_invites wi
        JOIN users u ON u.id = ? AND u.deleted_at IS NULL
        WHERE wi.token_hash = ?
          AND wi.deleted_at IS NULL
          AND wi.accepted_at IS NULL
        LIMIT 1
        """,
        (user_id, token_hash),
    ).fetchone()
    if not row:
        return False
    if int(row["expires_at"] or 0) <= int(time.time()):
        return False
    invited = str(row["email"] or "").strip().lower()
    actual = str(row["user_email"] or "").strip().lower()
    if not invited or invited != actual:
        return False
    handler.auth_workspace_id = str(row["workspace_id"])  # type: ignore[attr-defined]
    handler.auth_role = "invited"  # type: ignore[attr-defined]
    return True


def _authorize_scoped_request(
    handler: BaseHTTPRequestHandler,
    method: str,
    path: str,
) -> bool:
    if DEV_LOCAL_UNSAFE or not SECURE_MODE:
        return True
    user_id = str(getattr(handler, "auth_user", "") or "").strip()
    if not user_id:
        return False
    if user_id == "service":
        return True
    policy = _scoped_request_policy(method, path)
    if policy is None:
        return True
    kind, ref, admin_required = policy
    try:
        conn = _srv()._workframe_db()
        try:
            if kind == "invite":
                return _invite_scope_allows(conn, handler, ref, user_id)
            workspace_id = _workspace_id_for_scope(conn, kind, ref)
            if not workspace_id:
                return True
            role = _workspace_role(conn, workspace_id, user_id)
        finally:
            conn.close()
    except (sqlite3.Error, OSError, ValueError):
        return False
    if not role:
        return False
    handler.auth_workspace_id = workspace_id  # type: ignore[attr-defined]
    handler.auth_role = role  # type: ignore[attr-defined]
    if admin_required and role not in OWNER_ADMIN_ROLES:
        return False
    return True


def authorize_request(handler: BaseHTTPRequestHandler) -> bool:
    path = urllib.parse.urlparse(handler.path).path
    method = handler.command
    sid = session_id_from_request(handler)
    install_window_open = _srv()._install_window_open()

    if SECURE_MODE and not DEV_LOCAL_UNSAFE and path == "/api/auth/bootstrap":
        return False

    def _validate(sid_token: str):
        return _zk.validate_session_token(sid_token)

    def _attach(user_id: str) -> None:
        apply_session_user(handler, user_id)

    allowed = route_registry.authorize_request(
        method,
        path,
        sid,
        deployment_mode=_resolve_deployment_mode(),
        dev_local_unsafe=DEV_LOCAL_UNSAFE,
        install_window_open=install_window_open,
        validate_session=_validate,
        attach_user=_attach,
        get_workspace_role=lambda: str(getattr(handler, "auth_stack_role", "") or ""),
    )
    if not allowed:
        return False
    if DEV_LOCAL_UNSAFE:
        return True
    if path == "/api/setup":
        user_id = str(getattr(handler, "auth_user", "") or "").strip()
        return bool(install_window_open and user_id and user_is_stack_operator(user_id))
    return _authorize_scoped_request(handler, method, path)


def role_allows(handler: BaseHTTPRequestHandler, roles: set[str]) -> bool:
    if not SECURE_MODE:
        return True
    return str(getattr(handler, "auth_role", "")) in roles


def handler_is_active_workspace_member(handler: BaseHTTPRequestHandler, workspace_id: str = "") -> bool:
    if not SECURE_MODE:
        return True
    user_id = str(getattr(handler, "auth_user", "") or "").strip()
    if not user_id:
        return False
    if user_id == "service":
        return True
    ws_id = str(workspace_id or getattr(handler, "auth_workspace_id", "") or "").strip()
    try:
        conn = _srv()._workframe_db()
        try:
            if ws_id:
                return _workspace_role(conn, ws_id, user_id) is not None
            row = conn.execute(
                """
                SELECT 1 FROM workspace_memberships wm
                JOIN workspaces w ON w.id = wm.workspace_id
                WHERE wm.user_id = ?
                  AND wm.deleted_at IS NULL
                  AND wm.status = 'active'
                  AND w.deleted_at IS NULL
                  AND w.status = 'active'
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            return row is not None
        finally:
            conn.close()
    except sqlite3.Error:
        return False
