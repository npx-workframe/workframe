#!/usr/bin/env python3
"""
Workframe API - fast Hermes-native backend for Workframe UI.

Hermes stores (read-only): state.db, kanban.db, gateway_state.json, cron/jobs.json
Local stores: board.db (optional operator tasks), Files/ workspace (/workspace)
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import queue
import re
import secrets
import shlex
import sqlite3
import shutil
import signal
import socket
import threading
import time
import urllib.parse
import uuid
import urllib.request
import http.client
import urllib.error
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

from email_sender import APP_BASE_URL, send_branded_invite_email, send_email, send_verification_email
import install_api
import stack_config
import site_meta
import google_auth
import platform_auth
import credential_vault
import turn_credentials
import llm_proxy
import action_proxy
import internal_proxy_auth
import concierge
import llm_error_glossary
import openrouter_catalog
import updates as stack_updates

HERMES_DATA = Path(os.environ.get("HERMES_DATA", "/opt/data"))
WORKSPACE = Path(os.environ.get("WORKSPACE", "/workspace"))
DATA_DIR = Path(
    os.environ.get("WORKFRAME_API_DATA_DIR")
    or os.environ.get("MISSION_DATA_DIR")
    or str(Path(__file__).resolve().parent / "data")
)
BOARD_DB = Path(os.environ.get("BOARD_DB", str(DATA_DIR / "board.db")))
CONTENT_ROOT = WORKSPACE
ACTIVITY_ROOM_LIMIT = 250
ACTIVITY_WORKSPACE_LIMIT = 1000
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8080"))
NATIVE_PROFILE = os.environ.get("WORKFRAME_NATIVE_PROFILE", "").strip()
PROJECT_NAME = os.environ.get("WORKFRAME_PROJECT", "Workframe")
PUBLIC_DIR = Path(__file__).resolve().parent / "public"
SSE_INTERVAL = float(os.environ.get("SSE_INTERVAL", "5"))
VERSION = "workframe-api-0.1.0"
DELEGATION_SCOPE_AGENTS_DELEGATE = "agents:delegate"
ROUTES_JSON = HERMES_DATA / "workframe" / "routes.json"
AGENTS_JSON = HERMES_DATA / "workframe" / "agents.json"
AVATAR_REGISTRY_JSON = HERMES_DATA / "workframe" / "avatar-registry.json"
_CATALOG_DIR = Path(__file__).resolve().parent / "catalog"
AVATAR_CATALOG_JSON = _CATALOG_DIR / "avatar-catalog.json"
USER_AVATAR_CATALOG_JSON = _CATALOG_DIR / "user-avatar-catalog.json"
LOGO_CATALOG_JSON = _CATALOG_DIR / "logo-catalog.json"
def _lane_registry_json() -> Path:
    # ponytail: must follow DATA_DIR — tests patch DATA_DIR after import
    return DATA_DIR / "lane-registry.json"
DOCKER_SOCK = os.environ.get("DOCKER_SOCK", "/var/run/docker.sock")
GATEWAY_CONTAINER_NAME = os.environ.get("WORKFRAME_GATEWAY_CONTAINER", "workframe-gateway")
SUPERVISOR_URL = os.environ.get("WORKFRAME_SUPERVISOR_URL", "http://workframe-supervisor:8090").rstrip("/")
SUPERVISOR_TOKEN = (
    os.environ.get("WORKFRAME_SUPERVISOR_TOKEN")
    or os.environ.get("SUPERVISOR_TOKEN")
    or ""
).strip()

# Auth config
AUTH_DB_PATH = DATA_DIR / "auth.db"
WORKFRAME_AUTH_PASSWORD = os.environ.get("WORKFRAME_AUTH_PASSWORD", "")
WORKFRAME_AUTH_INSECURE = os.environ.get("WORKFRAME_AUTH_INSECURE", "0").strip() in {"1", "true", "yes"}
WORKFRAME_SESSION_TTL = int(os.environ.get("WORKFRAME_SESSION_TTL", "2592000"))
WORKFRAME_REFRESH_TTL = int(os.environ.get("WORKFRAME_REFRESH_TTL", str(14 * 86400)))
DASHBOARD_HTTP_TIMEOUT = float(os.environ.get("HERMES_DASHBOARD_HTTP_TIMEOUT", "15"))
WORKFRAME_REFRESH_WINDOW = 300  # refresh session ID when expires within 5 min
WORKFRAME_RUNTIME_TOKEN_TTL = int(os.environ.get("WORKFRAME_RUNTIME_TOKEN_TTL", "3600"))
WORKFRAME_LLM_PROXY_INTERNAL = os.environ.get(
    "WORKFRAME_LLM_PROXY_INTERNAL", "http://workframe-api:8080"
).rstrip("/")

import zk_auth as _zk


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
    # Default: secure when neither is set
    if not secure and not dev_unsafe:
        secure = True
    return secure, dev_unsafe


def _require_auth_token() -> str:
    """Load or derive the auth token for secure mode."""
    token = os.environ.get("WORKFRAME_API_TOKEN", "").strip()
    if token:
        return token
    # Fallback: derive from Hermes dashboard session token
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

# ponytail: docker exec per bind was ~10s; cache gateway registration briefly.
_gateway_registered_cache: dict[str, tuple[bool, float]] = {}
_GATEWAY_REG_TTL_SEC = 45.0


def _install_window_open() -> bool:
    try:
        return install_api.install_window_open(str(DATA_DIR / "workframe.db"))
    except Exception:
        return False


def _install_complete() -> bool:
  """Stack install wizard finished — distinct from per-user onboarding gates."""
  return not _install_window_open()


def _invite_only_login_enforced() -> bool:
    """Post-install multi-user: only members or pending invitees may authenticate."""
    if DEPLOYMENT_MODE == "single_user_local" or DEV_LOCAL_UNSAFE:
        return False
    return not _install_window_open()


def _primary_workspace_row(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, display_name FROM workspaces
        WHERE deleted_at IS NULL
        ORDER BY CASE WHEN slug = 'default' THEN 0 ELSE 1 END, created_at ASC
        LIMIT 1
        """,
    ).fetchone()


def _primary_workspace_branding(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, display_name, description, avatar_url, settings_json
        FROM workspaces
        WHERE deleted_at IS NULL
        ORDER BY CASE WHEN slug = 'default' THEN 0 ELSE 1 END, created_at ASC
        LIMIT 1
        """,
    ).fetchone()
    if not row:
        return None
    settings = _parse_workspace_settings(row)
    return {
        "display_name": str(row["display_name"] or "").strip(),
        "description": str(row["description"] or "").strip(),
        "avatar_url": str(row["avatar_url"] or "").strip(),
        "tagline": str(settings.get("tagline") or "").strip(),
    }


def _public_site_meta_payload() -> dict[str, Any]:
    cfg = stack_config.get_stack_config()
    env_base = str(APP_BASE_URL or "").strip().rstrip("/")
    cfg_base = str(cfg.get("app_base_url") or "").strip().rstrip("/")
    # ponytail: HTTPS env wins over loopback stack_config (wizard often saves slot URL first).
    if env_base.startswith("https://"):
        app_base = env_base
    elif cfg_base.startswith("https://"):
        app_base = cfg_base
    elif cfg_base and "127.0.0.1" not in cfg_base and "localhost" not in cfg_base.lower():
        app_base = cfg_base
    else:
        app_base = env_base or cfg_base
    workspace = None
    if _install_complete():
        try:
            conn = _workframe_db()
            workspace = _primary_workspace_branding(conn)
            conn.close()
        except sqlite3.Error:
            workspace = None
    return site_meta.resolve_site_meta(
        app_base_url=app_base,
        install_complete=_install_complete(),
        workspace=workspace,
        normalize_logo=_normalize_logo_url,
    )


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


def _email_allowed_to_authenticate(email: str) -> tuple[bool, dict[str, Any]]:
    normalized = str(email or "").strip().lower()
    if not normalized or "@" not in normalized:
        return False, {"error": "email required"}
    if not _invite_only_login_enforced():
        return True, {}
    conn = _workframe_db()
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


def _invite_token_allows_email(invite_token: str, email: str) -> bool:
    token = str(invite_token or "").strip()
    if not token:
        return False
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    normalized = str(email or "").strip().lower()
    conn = _workframe_db()
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


def _deployment_security_errors() -> list[str]:
    """Fail-closed checks for public_multi_user."""
    errors: list[str] = []
    if DEPLOYMENT_MODE != "public_multi_user":
        return errors
    if _install_window_open():
        return errors
    if DEV_LOCAL_UNSAFE:
        errors.append("public_multi_user cannot run with DEV_LOCAL_UNSAFE")
    if not SECURE_MODE:
        errors.append("public_multi_user requires SECURE_MODE=true")
    if not _supervisor_ready():
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
    if not os.environ.get("WORKFRAME_PROXY_TOKEN", "").strip() and not (
        DATA_DIR / internal_proxy_auth.PROXY_TOKEN_FILE
    ).is_file():
        errors.append("public_multi_user requires WORKFRAME_PROXY_TOKEN")
    if Path(DOCKER_SOCK).exists():
        errors.append("public_multi_user must not mount docker.sock on workframe-api")
    return errors


def _deployment_security_warnings() -> list[str]:
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


def _session_cookie_secure() -> bool:
    """Secure cookies only when the UI is served over HTTPS."""
    if DEV_LOCAL_UNSAFE or WORKFRAME_AUTH_INSECURE:
        return False
    # ponytail: loopback tunnel E2E only — not global WORKFRAME_E2E on HTTPS (0020 F2)
    if os.environ.get("WORKFRAME_E2E") == "1":
        base = APP_BASE_URL.strip().lower()
        if base.startswith("http://127.0.0.1") or base.startswith("http://localhost"):
            return False
    return APP_BASE_URL.strip().lower().startswith("https://")


# Set at module level; only used when SECURE_MODE is True
AUTH_TOKEN: str = ""

def _get_auth_token() -> str:
    """Get or lazy-load the auth token. Only called when SECURE_MODE is True."""
    global AUTH_TOKEN
    if not AUTH_TOKEN:
        try:
            AUTH_TOKEN = _require_auth_token()
        except Exception as exc:
            raise SystemExit(f"SECURE_MODE: failed to obtain auth token: {exc}")
    return AUTH_TOKEN


def _check_auth(request_handler) -> bool:
    """Return True if auth is valid or not required."""
    if DEV_LOCAL_UNSAFE:
        return True
    if getattr(request_handler, "auth_user", None):
        return True
    auth_header = request_handler.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = _get_auth_token()
        if auth_header[7:].strip() == token:
            request_handler.auth_user = "service"
            request_handler.auth_role = "owner"  # type: ignore[attr-defined]
            return True
    sid = _session_id_from_request(request_handler)
    if sid:
        session_info = _zk.validate_session_token(sid)
        if session_info:
            _apply_session_user(request_handler, session_info["user_id"])
            return True
    return False


def _host_without_port(host: str) -> str:
    host = (host or "").strip().lower()
    if not host:
        return ""
    if host.startswith("["):
        end = host.find("]")
        return host[1:end] if end != -1 else host
    if host.count(":") == 1:
        return host.rsplit(":", 1)[0]
    return host


def _allowed_hosts() -> set[str]:
    configured = {host.strip().lower() for host in ALLOWED_HOSTS if host.strip()}
    if configured:
        return configured | DEFAULT_ALLOWED_HOSTS
    return set(DEFAULT_ALLOWED_HOSTS)


def _loopback_ui_origins() -> set[str]:
    port = str(os.environ.get("WORKFRAME_UI_PORT", "18644") or "18644").strip()
    return {f"http://{host}:{port}" for host in ("127.0.0.1", "localhost", "[::1]")}


def _install_setup_route(method: str, path: str) -> bool:
    """Install-window routes configure hosts — must not require ALLOWED_HOSTS to match yet."""
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
    ):
        return True
    return False


def _secure_host_origin_ok(method: str, path: str, headers) -> bool:
    if DEV_LOCAL_UNSAFE:
        return True
    if _install_window_open() and _install_setup_route(method, path):
        return True
    return _validate_host(headers) and _validate_origin(headers)


def _validate_host(headers) -> bool:
    if DEV_LOCAL_UNSAFE:
        return True
    return _host_without_port(headers.get("Host", "")) in _allowed_hosts()


def _origin_host(origin: str) -> str:
    parsed = urllib.parse.urlsplit(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    return parsed.hostname.lower()


def _origin_allowed(origin: str) -> bool:
    if not origin:
        return True
    origin = origin.strip()
    if origin in CORS_ALLOW_ORIGINS:
        return True
    if origin.rstrip("/") in _loopback_ui_origins():
        return True
    if not CORS_ALLOW_ORIGINS:
        return _origin_host(origin) in _allowed_hosts()
    return False


def _validate_origin(headers) -> bool:
    if DEV_LOCAL_UNSAFE:
        return True
    return _origin_allowed(headers.get("Origin", ""))


def _validate_host_origin(headers) -> bool:
    return _validate_host(headers) and _validate_origin(headers)


def _admin_write_allowed(handler: BaseHTTPRequestHandler) -> bool:
    """DEV_LOCAL_UNSAFE: admin POST requires X-Workframe-Local (browsers cannot set cross-origin)."""
    if SECURE_MODE or not DEV_LOCAL_UNSAFE:
        return True
    return handler.headers.get("X-Workframe-Local", "").strip() == "1"


def _apply_stack_update(target: str) -> dict[str, Any]:
    return stack_updates.apply_update(target)


def _restart_stack_gateway() -> dict[str, Any]:
    return stack_updates.restart_gateway()


def _cors_origin_for(headers=None) -> str:
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


def _is_json_content_type(value: str) -> bool:
    return value.split(";", 1)[0].strip().lower() == "application/json"


def _resolve_workspace_id(slug_or_id: str) -> str | None:
    """Resolve a workspace slug or UUID to its canonical UUID.
    Returns None if workspace not found or deleted.
    """
    sid = str(slug_or_id or "").strip()
    if not sid:
        return None
    try:
        conn = _workframe_db()
        row = conn.execute(
            "SELECT id FROM workspaces WHERE (id = ? OR slug = ?) AND deleted_at IS NULL",
            (sid, sid),
        ).fetchone()
        conn.close()
        return row["id"] if row else None
    except Exception:
        return None


def _supervisor_ready() -> bool:
    return bool(SUPERVISOR_URL) and bool(SUPERVISOR_TOKEN)


def _supervisor_request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[int, Any]:
    """Proxy a JSON request to workframe-supervisor."""
    if not SUPERVISOR_URL:
        return 503, {"ok": False, "error": "WORKFRAME_SUPERVISOR_URL not configured"}
    if not SUPERVISOR_TOKEN:
        return 503, {"ok": False, "error": "WORKFRAME_SUPERVISOR_TOKEN not configured"}
    url = f"{SUPERVISOR_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return int(resp.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return int(exc.code), json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return int(exc.code), {"ok": False, "error": raw}
    except (urllib.error.URLError, TimeoutError) as exc:
        return 503, {
            "ok": False,
            "error": "supervisor_unavailable",
            "hint": "On the server: cd infra/compose/workframe && docker compose up -d",
            "detail": str(exc),
        }


def _maybe_sync_compose_public_url(public_url: str, *, restart: bool | None = None) -> dict[str, Any] | None:
    """Write APP_BASE_URL into host compose .env; optionally recreate API/gateway (not supervisor)."""
    url = str(public_url or "").strip()
    if not url:
        return None
    lowered = url.lower()
    if "127.0.0.1" in lowered or "localhost" in lowered:
        return None
    if not _supervisor_ready():
        return None
    if not str(os.environ.get("WORKFRAME_HOST_COMPOSE_DIR") or "").strip():
        return None
    if restart is None:
        restart = not _install_window_open()
    status, data = _supervisor_request(
        "POST",
        "/v1/host.set_compose_public_url",
        {"url": url, "restart": restart},
        timeout=180.0,
    )
    if status >= 400:
        return data if isinstance(data, dict) else {"ok": False, "error": "compose_sync_failed"}
    return data if isinstance(data, dict) else {"ok": True}


def _supervisor_gateway_exec(profile: str, args: list[str]) -> tuple[int, str]:
    if not _supervisor_ready():
        raise RuntimeError(
            "Docker socket access is disabled in SECURE_MODE; "
            "configure WORKFRAME_SUPERVISOR_URL and WORKFRAME_SUPERVISOR_TOKEN"
        )
    status, data = _supervisor_request(
        "POST",
        "/v1/gateway.exec",
        {"profile": profile, "args": args},
        timeout=120.0,
    )
    if status >= 300:
        err = data.get("error") if isinstance(data, dict) else str(data)
        raise ValueError(err or f"supervisor gateway.exec failed ({status})")
    if not isinstance(data, dict):
        raise ValueError("supervisor gateway.exec returned invalid payload")
    exit_code = data.get("exit_code")
    try:
        code = int(exit_code if exit_code is not None else 1)
    except (TypeError, ValueError):
        code = 1
    return code, str(data.get("output") or "")


def _supervisor_container_exec(cmd: list[str], *, detach: bool = False) -> tuple[int, str]:
    if not _supervisor_ready():
        raise RuntimeError(
            "Docker socket access is disabled in SECURE_MODE; "
            "configure WORKFRAME_SUPERVISOR_URL and WORKFRAME_SUPERVISOR_TOKEN"
        )
    status, data = _supervisor_request(
        "POST",
        "/v1/gateway.container_exec",
        {"args": [str(part) for part in cmd], "detach": detach},
        timeout=30.0 if detach else 120.0,
    )
    if status >= 300:
        err = data.get("error") if isinstance(data, dict) else str(data)
        raise ValueError(err or f"supervisor gateway.container_exec failed ({status})")
    if not isinstance(data, dict):
        raise ValueError("supervisor gateway.container_exec returned invalid payload")
    if detach:
        return 0, str(data.get("output") or "")
    exit_code = data.get("exit_code")
    try:
        code = int(exit_code if exit_code is not None else 1)
    except (TypeError, ValueError):
        code = 1
    return code, str(data.get("output") or "")


def _supervisor_profile_lifecycle(profile: str, action: str) -> dict[str, Any]:
    if not _supervisor_ready():
        raise RuntimeError(
            "Docker socket access is disabled in SECURE_MODE; "
            "configure WORKFRAME_SUPERVISOR_URL and WORKFRAME_SUPERVISOR_TOKEN"
        )
    if action == "status":
        q = urllib.parse.quote(profile, safe="")
        status, data = _supervisor_request("GET", f"/v1/profile.status?profile={q}", timeout=15.0)
    else:
        status, data = _supervisor_request("POST", f"/v1/profile.{action}", {"profile": profile}, timeout=60.0)
    if status >= 300:
        err = data.get("error") if isinstance(data, dict) else str(data)
        raise ValueError(err or f"supervisor {action} failed ({status})")
    if not isinstance(data, dict):
        raise ValueError(f"supervisor {action} returned invalid payload")
    return data


SPECIALIST_ROLES: dict[str, str] = {
    "visionary": "Clarifies product purpose, positioning, strategy, user value, and long-term alignment.",
    "architect": "Defines system design, technical boundaries, implementation plans, and code-review standards.",
    "docs": "Maintains AGENTS.md, .hermes.md, docs indexes, source-of-truth maps, and change summaries.",
    "dev": "Builds and modifies project files, scripts, tests, and implementation artifacts.",
    "research": "Performs technical research, market research, references, competitive analysis, and R&D notes.",
    "designer": "Handles UI direction, design docs, visual assets, image prompts, brand direction, and layout feedback.",
}

CREW_COLORS = [
    "#A78BFA",
    "#7DD3FC",
    "#F472B6",
    "#FBBF24",
    "#E879F9",
    "#5EE2B5",
    "#F26D6D",
    "#38BDF8",
]

_board_lock = threading.Lock()
_cpu_cache: dict[str, Any] = {"at": 0.0, "percent": 0.0}
_workspace_state_lock = threading.Lock()
_workspace_state_cache: dict[str, Any] = {
    "ok": True,
    "revision": "0:0:",
    "files": 0,
    "updated_at": "",
    "latest_path": "",
    "generation": 0,
}
_workspace_tree_lock = threading.Lock()
_workspace_tree_cache: dict[str, Any] = {
    "revision": "",
    "root": None,
}
_workspace_event_lock = threading.Lock()
_workspace_event_state: dict[str, int] = {"version": 0}
_room_live_lock = threading.Lock()
_room_live_queues: dict[str, list[queue.SimpleQueue[str]]] = {}
_room_live_turns: dict[str, dict[str, Any]] = {}
_gateway_lifecycle_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Auth session helpers
# ---------------------------------------------------------------------------

# Routes that are public only for GET (POST still needs session)
GET_PUBLIC_ROUTES = {
    "/api/files/read",
    "/api/files/raw",
    "/api/files/tree",
    "/api/files/list",
    "/api/files/state",
    "/api/board",
    "/api/content",
    "/api/content/get",
    "/api/meta",
    "/api/agents",
    "/api/snapshot",
    "/api/health",
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
    "/api/setup/status",
    "/api/install/status",
    "/api/public/site-meta",
    "/api/public/link-preview",
    "/api/public/manifest.webmanifest",
    "/api/auth/google/callback",
}

def _is_public_get(path: str) -> bool:
    """Return True if this GET path is public (no session needed)."""
    if path in ("", "/"):
        return True
    if path.startswith("/static/") or path.startswith("/assets/"):
        return True
    if path.startswith("/api/public/branding/"):
        return True
    return path in GET_PUBLIC_ROUTES


def _cookie_session_id(handler: BaseHTTPRequestHandler) -> str:
    """Extract namespaced session cookie value, or "" if missing."""
    cookie_header = handler.headers.get("Cookie", "")
    prefix = f"{_zk.session_cookie_name()}="
    legacy_prefix = "wf_session="
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(prefix):
            return part[len(prefix):]
        if part.startswith(legacy_prefix):
            return part[len(legacy_prefix):]
    return ""


def _session_id_from_request(handler: BaseHTTPRequestHandler) -> str:
    """Cookie first; X-Workframe-Session when cookies are not stored yet."""
    sid = _cookie_session_id(handler)
    if sid:
        return sid
    return handler.headers.get("X-Workframe-Session", "").strip()


def _auth_check(handler: BaseHTTPRequestHandler) -> bool:
    """Return True if the request should be allowed through."""
    path = urllib.parse.urlparse(handler.path).path
    method = handler.command
    sid = _session_id_from_request(handler)

    if method == "GET" and path == "/api/auth/hermes-dashboard-gate":
        if sid:
            session_info = _zk.validate_session_token(sid)
            if session_info:
                _apply_session_user(handler, session_info["user_id"])
        return True

    if DEV_LOCAL_UNSAFE:
        # Still validate session if present, to populate auth_user
        if sid:
            session_info = _zk.validate_session_token(sid)
            if session_info:
                _apply_session_user(handler, session_info["user_id"])
        return True

    # OPTIONS (CORS preflight) — always allow
    if method == "OPTIONS":
        return True

    # GET public routes — still attach session user when cookie/header present
    # (e.g. /api/hermes/models needs auth_user for per-user provider detection).
    if method == "GET" and _is_public_get(path):
        if sid:
            session_info = _zk.validate_session_token(sid)
            if session_info:
                _apply_session_user(handler, session_info["user_id"])
        return True

    # POST auth endpoints (start/verify/logout/refresh) are public
    if method == "POST" and path in (
        "/api/auth/start",
        "/api/auth/verify",
        "/api/auth/logout",
        "/api/auth/refresh",
        "/api/setup",
    ):
        return True

    if method == "POST" and path in (
        "/api/auth/google/start",
        "/api/auth/local-bootstrap",
    ):
        return True

    if _install_window_open() and method == "POST" and path in (
        "/api/install/email/test",
        "/api/install/complete",
        "/api/install/url/test",
        "/api/install/setup-https",
    ):
        # ponytail: install/complete still needs auth_user in trusted_team — populate when session present
        if sid:
            session_info = _zk.validate_session_token(sid)
            if session_info:
                _apply_session_user(handler, session_info["user_id"])
        return True

    if _install_window_open() and method in ("GET", "PATCH") and path == "/api/install/stack":
        return True

    if _install_window_open() and method == "GET" and path in (
        "/api/install/publish-hints",
        "/api/install/url/test",
    ):
        return True

    # Everything else needs a valid session
    if not sid:
        return False
    session_info = _zk.validate_session_token(sid)
    if not session_info:
        return False
    _apply_session_user(handler, session_info["user_id"])
    return True


def _workspace_role_for_user(user_id: str) -> str:
    """Highest active workspace role for RBAC (owner > admin > member)."""
    rank = {"owner": 3, "admin": 2, "member": 1}
    best = "member"
    try:
        conn = _workframe_db()
        rows = conn.execute(
            """
            SELECT role FROM workspace_memberships
            WHERE user_id = ? AND deleted_at IS NULL AND status = 'active'
            """,
            (user_id,),
        ).fetchall()
        conn.close()
    except Exception:
        return best
    for row in rows:
        role = str(row["role"] or "member")
        if rank.get(role, 0) > rank.get(best, 0):
            best = role
    return best


def _apply_session_user(handler: BaseHTTPRequestHandler, user_id: str) -> None:
    handler.auth_user = user_id  # type: ignore[attr-defined]
    handler.auth_role = _workspace_role_for_user(user_id)  # type: ignore[attr-defined]


def _user_is_stack_operator(user_id: str) -> bool:
    return _workspace_role_for_user(user_id) in OWNER_ADMIN_ROLES


def _user_can_access_hermes_dashboard(user_id: str) -> bool:
    """UI hint: hide dashboard nav unless operator (or single-user local)."""
    if DEPLOYMENT_MODE == "single_user_local":
        return True
    if not user_id:
        return False
    return _workspace_role_for_user(user_id) in OWNER_ADMIN_ROLES



def _exec_targets_runtime_profile_secrets(cmd: list[str], acting_profile: str = "") -> bool:
    """Return True when gateway shell command targets sibling profile secrets."""
    if DEPLOYMENT_MODE == "single_user_local":
        return False
    from profile_secret_policy import exec_blocked_for_profile

    return exec_blocked_for_profile(cmd, acting_profile)


def _runtime_profile_owner(runtime: str, workspace_id: str = "") -> str:
    runtime = safe_profile_slug(str(runtime or "").strip())
    workspace_id = str(workspace_id or "").strip()
    if workspace_id:
        owner = _user_id_for_runtime_slug(runtime, workspace_id)
        if owner:
            return owner
    resolved = _resolve_runtime_owner(runtime)
    return resolved[0] if resolved else ""


def _user_may_access_runtime_profile(user_id: str, profile: str, workspace_id: str = "") -> bool:
    """RBAC for per-user u-* Hermes profile dirs (BFF + gateway exec)."""
    prof = safe_profile_slug(str(profile or "").strip())
    if not _is_runtime_profile_slug(prof):
        return True
    if DEPLOYMENT_MODE == "single_user_local":
        return True
    user_id = str(user_id or "").strip()
    if not user_id:
        return False
    if DEPLOYMENT_MODE == "trusted_team" and _user_is_stack_operator(user_id):
        return True
    owner = _runtime_profile_owner(prof, workspace_id)
    return bool(owner) and owner == user_id


def _stack_profile_env() -> dict[str, str]:
    primary = _primary_profile()
    if not primary:
        return {}
    return _read_env_map(_profile_dir(primary) / ".env")


def _user_auth_env_keys(user_id: str) -> set[str]:
    keys = _read_env_keys(_user_hermes_env_path(user_id))
    auth_path = _user_hermes_auth_path(user_id)
    if not auth_path.is_file():
        return keys
    try:
        loaded = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return keys
    creds = loaded.get("credentials") if isinstance(loaded, dict) else None
    if not isinstance(creds, list):
        return keys
    for row in creds:
        if not isinstance(row, dict):
            continue
        ref = str(row.get("credential_ref") or "")
        if ref.startswith("env:"):
            keys.add(ref[4:])
        env_var = str(row.get("env_var") or "")
        if env_var:
            keys.add(env_var)
    return keys


def _provider_connected_for_user(
    user_id: str,
    spec: dict[str, Any],
    bindings: dict[str, dict[str, Any]],
    env_keys: set[str],
) -> bool:
    provider_id = str(spec["id"])
    env_var = str(spec.get("env_var") or "")
    hermes_auth_id = str(spec.get("hermes_auth_id") or provider_id)
    if bindings.get(provider_id):
        return True
    if env_var and env_var in env_keys:
        return True
    auth_path = _user_hermes_auth_path(user_id)
    if auth_path.is_file():
        try:
            loaded = json.loads(auth_path.read_text(encoding="utf-8"))
            creds = loaded.get("credentials") if isinstance(loaded, dict) else None
            if isinstance(creds, list):
                for row in creds:
                    if not isinstance(row, dict):
                        continue
                    pid = str(row.get("provider") or row.get("id") or "").lower()
                    if pid in {provider_id, hermes_auth_id, hermes_auth_id.replace("-", "")}:
                        return True
        except (OSError, json.JSONDecodeError):
            pass
    if spec.get("user_only"):
        return False
    return False


def _user_hermes_dir_slug(user_id: str) -> str:
    raw = str(user_id or "").strip()
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw) or "user"


def _user_hermes_home(user_id: str) -> Path:
    return HERMES_DATA / "profiles" / _user_hermes_dir_slug(user_id)


def _user_hermes_env_path(user_id: str) -> Path:
    return _user_hermes_home(user_id) / ".env"


def _user_hermes_auth_path(user_id: str) -> Path:
    return _user_hermes_home(user_id) / "auth.json"


def _default_credential_env_var(provider: str, credential_type: str) -> str:
    prefix = re.sub(r"[^A-Za-z0-9]+", "_", str(provider or "WORKFRAME").strip()).upper() or "WORKFRAME"
    suffix = {
        "bot_token": "BOT_TOKEN",
        "oauth": "OAUTH_TOKEN",
    }.get(str(credential_type or "api_key"), "API_KEY")
    return f"{prefix}_{suffix}"


def _quote_env_value(value: str) -> str:
    raw = str(value or "")
    if re.fullmatch(r"[A-Za-z0-9_./:@+-]+", raw):
        return raw
    return json.dumps(raw)


def _upsert_env_secret(env_path: Path, key: str, value: str) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    found = False
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    updated: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            updated.append(line)
            continue
        current_key, _sep, _rest = line.partition("=")
        if current_key.strip() == key:
            updated.append(f"{key}={_quote_env_value(value)}")
            found = True
        else:
            updated.append(line)
    if not found:
        if updated and updated[-1].strip():
            updated.append("")
        updated.append(f"{key}={_quote_env_value(value)}")
    env_path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")
    _publish_profile_gateway_secrets(env_path.parent.name)


def _publish_profile_gateway_secrets(profile: str) -> None:
    """Hermes gateway runs as uid hermes; API container writes bind-mount files as root.

    Runtime profiles only ever get wf_rt_* lease tokens or auth.json pool metadata —
    never raw upstream keys. chmod so the gateway can read overlays; supervisor still
    blocks agent shell exec against these paths.
    """
    slug = safe_profile_slug(str(profile or "").strip())
    if not _is_runtime_profile_slug(slug):
        return
    prof_dir = _profile_dir(slug)
    for name in (".env", "auth.json"):
        path = prof_dir / name
        if not path.is_file():
            continue
        try:
            os.chmod(path, 0o644)
        except OSError:
            pass


def _upsert_auth_metadata(auth_path: Path, payload: dict[str, Any]) -> None:
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if auth_path.exists():
        try:
            loaded = json.loads(auth_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}
    bindings = data.get("credentials")
    if not isinstance(bindings, list):
        bindings = []
    credential_ref = str(payload.get("credential_ref") or "")
    bindings = [row for row in bindings if not isinstance(row, dict) or row.get("credential_ref") != credential_ref]
    bindings.append({
        "provider": payload.get("provider"),
        "credential_type": payload.get("credential_type"),
        "credential_ref": credential_ref,
        "env_var": payload.get("env_var"),
        "label": payload.get("label") or "",
        "updated_at": payload.get("updated_at"),
    })
    data["credentials"] = bindings
    data["updated_at"] = payload.get("updated_at")
    auth_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _store_user_credential(user_id: str, provider: str, credential_type: str, secret: str, env_var: str, label: str) -> dict[str, Any]:
    user_home = _user_hermes_home(user_id)
    auth_path = _user_hermes_auth_path(user_id)
    cred_id = str(uuid.uuid4())
    credential_ref = credential_vault.vault_ref(cred_id)
    now = _utc_now()
    credential_vault.store_secret(
        cred_id,
        secret,
        env_var=env_var,
        provider=provider,
        scope="user",
        user_id=user_id,
    )
    _remove_env_secret(_user_hermes_env_path(user_id), env_var)
    _upsert_auth_metadata(
        auth_path,
        {
            "provider": provider,
            "credential_type": credential_type,
            "credential_ref": credential_ref,
            "env_var": env_var,
            "label": label,
            "updated_at": now,
        },
    )
    return {
        "profile_home": str(user_home),
        "credential_id": cred_id,
        "auth_path": str(auth_path),
        "credential_ref": credential_ref,
        "updated_at": now,
    }


def _store_workspace_credential(
    workspace_id: str,
    provider: str,
    credential_type: str,
    secret: str,
    env_var: str,
    label: str,
    created_by: str,
) -> dict[str, Any]:
    """Company-pay keys live on the primary Hermes profile .env (shared stack)."""
    workspace_id = str(workspace_id or "").strip()
    provider = str(provider or "").strip().lower()
    if not workspace_id or not provider or not secret.strip():
        raise ValueError("workspace_credential_invalid")
    spec = _catalog_provider(provider)
    if spec and spec.get("user_only"):
        raise ValueError("provider_user_only")
    primary = _primary_profile()
    if not primary:
        raise ValueError("no_primary_profile")
    cred_id = str(uuid.uuid4())
    credential_ref = credential_vault.vault_ref(cred_id)
    now = _utc_now()
    credential_vault.store_secret(
        cred_id,
        secret.strip(),
        env_var=env_var,
        provider=provider,
        scope="workspace",
        workspace_id=workspace_id,
    )
    _remove_env_secret(_profile_dir(primary) / ".env", env_var)
    conn = _workframe_db()
    try:
        existing = conn.execute(
            """SELECT id FROM credential_bindings
               WHERE workspace_id = ? AND provider = ? AND deleted_at IS NULL
               ORDER BY updated_at DESC LIMIT 1""",
            (workspace_id, provider),
        ).fetchone()
        if existing:
            cred_id = str(existing[0])
            conn.execute(
                """UPDATE credential_bindings
                   SET credential_ref = ?, label = ?, is_active = 1, updated_at = ?, deleted_at = NULL
                   WHERE id = ?""",
                (credential_ref, label, now, cred_id),
            )
        else:
            conn.execute(
                """INSERT INTO credential_bindings
                   (id, workspace_id, user_id, agent_profile_id, provider, credential_type,
                    credential_ref, label, is_active, created_by, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cred_id, workspace_id, None, None, provider, credential_type,
                    credential_ref, label, 1, created_by, now, now,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return {
        "credential_id": cred_id,
        "credential_ref": credential_ref,
        "updated_at": now,
    }


# Hermes gateway reads these from the primary profile .env; vault is source of truth.
_MESSAGING_GATEWAY_ENV: dict[str, dict[str, str]] = {
    "discord": {
        "token": "DISCORD_BOT_TOKEN",
        "home_channel": "DISCORD_HOME_CHANNEL",
        "allowed_users": "DISCORD_ALLOWED_USERS",
    },
    "telegram": {
        "token": "TELEGRAM_BOT_TOKEN",
        "home_channel": "TELEGRAM_HOME_CHANNEL",
        "allowed_users": "TELEGRAM_ALLOWED_USERS",
    },
}


def _parse_user_platform_ids(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("platform_ids must be an object")
    allowed = frozenset({"discord", "telegram", "slack"})
    out: dict[str, str] = {}
    for raw_key, raw_val in value.items():
        key = str(raw_key or "").strip().lower()
        if key not in allowed:
            raise ValueError(f"unsupported platform_id: {raw_key}")
        val = str(raw_val or "").strip()
        if val:
            out[key] = val
    return out


def _parse_messaging_settings_patch(body: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    """Merge admin messaging channel/allowlist config into workspace settings."""
    raw = body.get("messaging")
    if not isinstance(raw, dict):
        return settings
    messaging = settings.get("messaging") if isinstance(settings.get("messaging"), dict) else {}
    merged = dict(messaging)
    for provider in ("discord", "telegram"):
        block = raw.get(provider)
        if not isinstance(block, dict):
            continue
        current = merged.get(provider) if isinstance(merged.get(provider), dict) else {}
        row = dict(current)
        if "home_channel" in block:
            row["home_channel"] = str(block.get("home_channel") or "").strip()
        if "allowed_users" in block:
            row["allowed_users"] = str(block.get("allowed_users") or "").strip()
        merged[provider] = row
    settings["messaging"] = merged
    return settings


def _workspace_member_platform_ids(workspace_id: str) -> dict[str, set[str]]:
    """Collect linked Discord/Telegram user IDs for workspace members."""
    workspace_id = str(workspace_id or "").strip()
    out: dict[str, set[str]] = {"discord": set(), "telegram": set(), "slack": set()}
    if not workspace_id:
        return out
    conn = _workframe_db()
    try:
        rows = conn.execute(
            """
            SELECT u.platform_ids
            FROM users u
            JOIN workspace_memberships wm ON wm.user_id = u.id
            WHERE wm.workspace_id = ?
              AND wm.deleted_at IS NULL
              AND u.deleted_at IS NULL
              AND wm.status = 'active'
            """,
            (workspace_id,),
        ).fetchall()
    finally:
        conn.close()
    for row in rows:
        raw = row[0] if row else "{}"
        try:
            parsed = json.loads(str(raw or "{}"))
        except (TypeError, json.JSONDecodeError):
            parsed = {}
        if not isinstance(parsed, dict):
            continue
        for platform in out:
            val = str(parsed.get(platform) or "").strip()
            if val:
                out[platform].add(val)
    return out


def _merged_messaging_allowed_users(workspace_id: str, provider: str, seed: str) -> str:
    """Admin seed allowlist + member-linked platform IDs for gateway env."""
    provider = str(provider or "").strip().lower()
    ids: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[\s,;]+", str(seed or "").strip()):
        token = part.strip()
        if token and token not in seen:
            seen.add(token)
            ids.append(token)
    for member_id in sorted(_workspace_member_platform_ids(workspace_id).get(provider, set())):
        if member_id not in seen:
            seen.add(member_id)
            ids.append(member_id)
    return ",".join(ids)


def _workspace_messaging_integrations_payload(workspace_id: str, settings: dict[str, Any]) -> dict[str, Any]:
    messaging = settings.get("messaging") if isinstance(settings.get("messaging"), dict) else {}
    payload: dict[str, Any] = {}
    for provider, env_map in _MESSAGING_GATEWAY_ENV.items():
        block = messaging.get(provider) if isinstance(messaging.get(provider), dict) else {}
        resolved = _resolve_credential("", workspace_id, provider)
        has_token = bool(resolved and _credential_secret(resolved, ""))
        payload[provider] = {
            "bot_token_configured": has_token,
            "home_channel": str(block.get("home_channel") or ""),
            "allowed_users": str(block.get("allowed_users") or ""),
        }
    return payload


def _set_primary_messaging_platforms(enabled: dict[str, bool]) -> tuple[bool, str]:
    primary = _primary_profile()
    if not primary:
        return False, "no_primary_profile"
    flags = {name: bool(enabled.get(name)) for name in ("discord", "telegram")}
    cfg_path = _profile_gateway_config_path(primary)
    if cfg_path is None:
        return False, "no_primary_profile"
    try:
        import yaml

        cfg: dict[str, Any] = {}
        if cfg_path.is_file():
            loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
            cfg = loaded if isinstance(loaded, dict) else {}
        plats = cfg.setdefault("platforms", {})
        if not isinstance(plats, dict):
            plats = {}
            cfg["platforms"] = plats
        for name, on in flags.items():
            row = plats.get(name) if isinstance(plats.get(name), dict) else {}
            row["enabled"] = bool(on)
            plats[name] = row
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        return True, "ok"
    except (OSError, ImportError) as exc:
        return False, str(exc)


def _sync_workspace_messaging_gateway(workspace_id: str) -> dict[str, Any]:
    """Vault → primary profile .env overlay + platform toggles + gateway restart."""
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return {"ok": False, "error": "workspace_id_required"}
    primary = _primary_profile()
    if not primary:
        return {"ok": False, "error": "no_primary_profile"}
    try:
        conn = _workframe_db()
        row = conn.execute(
            "SELECT settings_json FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        conn.close()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"db_error: {exc}"}
    settings = _parse_workspace_settings(row) if row else {}
    messaging = settings.get("messaging") if isinstance(settings.get("messaging"), dict) else {}
    env_path = _profile_dir(primary) / ".env"
    enabled: dict[str, bool] = {}
    for provider, env_map in _MESSAGING_GATEWAY_ENV.items():
        token_var = env_map["token"]
        resolved = _resolve_credential("", workspace_id, provider)
        secret = _credential_secret(resolved, "") if resolved else ""
        block = messaging.get(provider) if isinstance(messaging.get(provider), dict) else {}
        if secret:
            _upsert_env_secret(env_path, token_var, secret)
            enabled[provider] = True
            home = str(block.get("home_channel") or "").strip()
            if home:
                _upsert_env_secret(env_path, env_map["home_channel"], home)
            else:
                _remove_env_secret(env_path, env_map["home_channel"])
            allowed = _merged_messaging_allowed_users(
                workspace_id,
                provider,
                str(block.get("allowed_users") or ""),
            )
            if allowed:
                _upsert_env_secret(env_path, env_map["allowed_users"], allowed)
            else:
                _remove_env_secret(env_path, env_map["allowed_users"])
        else:
            enabled[provider] = False
            for key in env_map.values():
                _remove_env_secret(env_path, key)
    ok, out = _set_primary_messaging_platforms(enabled)
    if not ok:
        return {"ok": False, "error": f"messaging_platform_config_failed: {out}"}
    try:
        restart = _restart_stack_gateway()
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "gateway": restart}


# ponytail: curated Hermes-native provider list; env vars match configuration docs.
PROVIDER_CONNECT_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "id": "openrouter",
        "label": "OpenRouter",
        "category": "llm",
        "connect_mode": "api_key",
        "env_var": "OPENROUTER_API_KEY",
        "description": "Primary LLM router — any model via one API key.",
    },
    {
        "id": "anthropic",
        "label": "Anthropic",
        "category": "llm",
        "connect_mode": "api_key",
        "env_var": "ANTHROPIC_API_KEY",
        "description": "Direct Claude API access.",
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "category": "llm",
        "connect_mode": "api_key",
        "env_var": "OPENAI_API_KEY",
        "description": "Direct OpenAI API access.",
    },
    {
        "id": "codex",
        "label": "OpenAI Codex",
        "category": "llm",
        "connect_mode": "oauth",
        "hermes_auth_id": "openai-codex",
        "description": "Codex CLI OAuth session (hermes auth add openai-codex).",
    },
    {
        "id": "google",
        "label": "Google Gemini",
        "category": "llm",
        "connect_mode": "api_key",
        "env_var": "GEMINI_API_KEY",
        "description": "Gemini models via API key.",
    },
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "category": "llm",
        "connect_mode": "api_key",
        "env_var": "DEEPSEEK_API_KEY",
        "description": "DeepSeek chat models.",
    },
    {
        "id": "brave",
        "label": "Brave Search",
        "category": "search",
        "connect_mode": "api_key",
        "env_var": "BRAVE_API_KEY",
        "description": "Web search API for agent tools.",
    },
    {
        "id": "nous",
        "label": "Nous Portal",
        "category": "llm",
        "connect_mode": "oauth",
        "hermes_auth_id": "nous",
        "description": "OAuth bundle for models + tool gateway (hermes setup --portal).",
    },
    {
        "id": "discord",
        "label": "Discord",
        "category": "messaging",
        "connect_mode": "bot_token",
        "env_var": "DISCORD_BOT_TOKEN",
        "description": "Bot token from the Discord Developer Portal.",
    },
    {
        "id": "telegram",
        "label": "Telegram",
        "category": "messaging",
        "connect_mode": "bot_token",
        "env_var": "TELEGRAM_BOT_TOKEN",
        "description": "Bot token from @BotFather.",
    },
    {
        "id": "slack",
        "label": "Slack",
        "category": "messaging",
        "connect_mode": "bot_token",
        "env_var": "SLACK_BOT_TOKEN",
        "extra_env_vars": ("SLACK_APP_TOKEN",),
        "description": "Slack bot + app tokens (Socket Mode).",
    },
    {
        "id": "github",
        "label": "GitHub",
        "category": "dev",
        "connect_mode": "oauth",
        "env_var": "GITHUB_TOKEN",
        "oauth_provider": "github",
        "hermes_auth_id": "github",
        "user_only": True,
        "description": "OAuth (admin registers app) or fine-grained PAT — repo push and GitHub API.",
    },
    {
        "id": "stripe",
        "label": "Stripe",
        "category": "payments",
        "connect_mode": "oauth",
        "env_var": "STRIPE_SECRET_KEY",
        "oauth_provider": "stripe",
        "user_only": True,
        "description": "Connect your Stripe account — charges, customers, and billing tools.",
    },
    {
        "id": "vercel",
        "label": "Vercel",
        "category": "dev",
        "connect_mode": "api_key",
        "env_var": "VERCEL_TOKEN",
        "user_only": True,
        "description": "Personal access token (VERCEL_TOKEN) for deploy/CLI tools.",
    },
    {
        "id": "netlify",
        "label": "Netlify",
        "category": "dev",
        "connect_mode": "api_key",
        "env_var": "NETLIFY_AUTH_TOKEN",
        "user_only": True,
        "description": "Netlify personal access token (NETLIFY_AUTH_TOKEN).",
    },
)

# Providers where agent actions must use the triggering user's credential only.
_USER_ONLY_PROVIDER_IDS: frozenset[str] = frozenset(
    str(spec["id"]).lower()
    for spec in PROVIDER_CONNECT_CATALOG
    if spec.get("user_only")
)

GITHUB_OAUTH_SCOPES = "repo read:user"
STRIPE_CONNECT_SCOPES = "read_write"


def _stripe_connect_app_config() -> dict[str, str]:
    """Stack Stripe Connect app — platform secret never leaves the BFF."""
    stack_st = stack_config.resolved_stripe_connect()
    if stack_st.get("client_id") and stack_st.get("client_secret"):
        return stack_st
    client_id = (
        os.environ.get("WORKFRAME_STRIPE_CONNECT_CLIENT_ID")
        or os.environ.get("STRIPE_CONNECT_CLIENT_ID")
        or ""
    ).strip()
    client_secret = (
        os.environ.get("WORKFRAME_STRIPE_SECRET_KEY")
        or os.environ.get("STRIPE_SECRET_KEY")
        or ""
    ).strip()
    return {"client_id": client_id, "client_secret": client_secret}


def _stripe_connect_configured() -> bool:
    cfg = _stripe_connect_app_config()
    return bool(cfg.get("client_id") and cfg.get("client_secret"))


def _stripe_oauth_redirect_uri() -> str:
    base = APP_BASE_URL.rstrip("/")
    return f"{base}/api/oauth/stripe/callback"


def _catalog_provider(provider_id: str) -> dict[str, Any] | None:
    needle = str(provider_id or "").strip().lower()
    for row in PROVIDER_CONNECT_CATALOG:
        if str(row.get("id", "")).lower() == needle:
            return row
    return None


def _catalog_provider_for_llm(llm_provider: str) -> dict[str, Any] | None:
    spec = _catalog_provider(llm_provider)
    if spec:
        return spec
    needle = str(llm_provider or "").strip().lower()
    for row in PROVIDER_CONNECT_CATALOG:
        auth_id = str(row.get("hermes_auth_id") or row.get("id") or "").strip().lower()
        if auth_id == needle:
            return row
    return None


def _provider_user_only(provider_id: str) -> bool:
    return str(provider_id or "").strip().lower() in _USER_ONLY_PROVIDER_IDS


def _provider_env_vars(spec: dict[str, Any]) -> list[str]:
    names: list[str] = []
    primary = str(spec.get("env_var") or "").strip()
    if primary:
        names.append(primary)
    for extra in spec.get("extra_env_vars") or ():
        key = str(extra or "").strip()
        if key and key not in names:
            names.append(key)
    return names


def _parse_workspace_settings(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    keys = row.keys() if hasattr(row, "keys") else row
    raw = ""
    if isinstance(keys, (list, set)) or hasattr(keys, "__contains__"):
        if "settings_json" in keys:
            raw = row["settings_json"] if not isinstance(row, dict) else row.get("settings_json", "")
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw or "{}"))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _github_oauth_app_config(workspace_id: str = "") -> dict[str, str]:
    """Stack or workspace GitHub OAuth app — client secret never leaves the BFF."""
    workspace = str(workspace_id or "").strip()
    if workspace:
        try:
            conn = _workframe_db()
            row = conn.execute(
                "SELECT settings_json FROM workspaces WHERE id = ? AND deleted_at IS NULL",
                (workspace,),
            ).fetchone()
            conn.close()
            if row:
                gh = _parse_workspace_settings(row).get("github_oauth")
                if isinstance(gh, dict):
                    client_id = str(gh.get("client_id") or "").strip()
                    client_secret = str(gh.get("client_secret") or "").strip()
                    if client_id and client_secret:
                        return {"client_id": client_id, "client_secret": client_secret}
        except sqlite3.Error:
            pass
    stack_gh = stack_config.resolved_github_oauth()
    if stack_gh.get("client_id") and stack_gh.get("client_secret"):
        return stack_gh
    client_id = (
        os.environ.get("WORKFRAME_GITHUB_OAUTH_CLIENT_ID")
        or os.environ.get("GITHUB_CLIENT_ID")
        or ""
    ).strip()
    client_secret = (
        os.environ.get("WORKFRAME_GITHUB_OAUTH_CLIENT_SECRET")
        or os.environ.get("GITHUB_CLIENT_SECRET")
        or ""
    ).strip()
    return {"client_id": client_id, "client_secret": client_secret}


def _github_oauth_configured(workspace_id: str = "") -> bool:
    cfg = _github_oauth_app_config(workspace_id)
    return bool(cfg.get("client_id") and cfg.get("client_secret"))


def _github_oauth_redirect_uri() -> str:
    base = APP_BASE_URL.rstrip("/")
    return f"{base}/api/oauth/github/callback"


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return verifier, challenge


def _store_oauth_pending(state: str, user_id: str, provider: str, code_verifier: str, workspace_id: str = "") -> None:
    _ensure_oauth_pending_table()
    now = _utc_now()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    conn = _workframe_db()
    try:
        conn.execute(
            """
            INSERT INTO oauth_pending_states (state, user_id, provider, code_verifier, workspace_id, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(state) DO UPDATE SET
                user_id = excluded.user_id,
                provider = excluded.provider,
                code_verifier = excluded.code_verifier,
                workspace_id = excluded.workspace_id,
                expires_at = excluded.expires_at,
                created_at = excluded.created_at
            """,
            (state, user_id, provider, code_verifier, workspace_id or None, expires, now),
        )
        conn.commit()
    finally:
        conn.close()


def _take_oauth_pending(state: str) -> dict[str, Any] | None:
    _ensure_oauth_pending_table()
    conn = _workframe_db()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM oauth_pending_states WHERE state = ?",
            (str(state or "").strip(),),
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM oauth_pending_states WHERE state = ?", (row["state"],))
        conn.commit()
        expires_at = str(row["expires_at"] or "")
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at.replace("Z", "+00:00")) < datetime.now(timezone.utc):
                    return None
            except ValueError:
                pass
        return dict(row)
    finally:
        conn.close()


def _github_exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str, code_verifier: str) -> dict[str, Any]:
    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://github.com/login/oauth/access_token",
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
    except OSError as exc:
        return {"error": str(exc)}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"error": raw or "github_token_exchange_failed"}
    return data if isinstance(data, dict) else {"error": "invalid_github_response"}


def _start_github_oauth(user_id: str, workspace_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    cfg = _github_oauth_app_config(workspace_id)
    client_id = str(cfg.get("client_id") or "").strip()
    if not client_id or not str(cfg.get("client_secret") or "").strip():
        return {
            "ok": False,
            "error": "github_oauth_not_configured",
            "message": "Workframe admin must register a GitHub OAuth app under Workframe → Integrations.",
        }
    state = secrets.token_urlsafe(24)
    verifier, challenge = _pkce_pair()
    _store_oauth_pending(state, user_id, "github", verifier, workspace_id)
    params = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": _github_oauth_redirect_uri(),
            "scope": GITHUB_OAUTH_SCOPES,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
    )
    return {
        "ok": True,
        "provider": str(spec.get("id") or "github"),
        "redirect_url": f"https://github.com/login/oauth/authorize?{params}",
        "output": "",
        "error": None,
    }


def _complete_github_oauth(user_id: str, code: str, state: str) -> dict[str, Any]:
    pending = _take_oauth_pending(state)
    if not pending or str(pending.get("user_id") or "") != user_id:
        return {"ok": False, "error": "invalid_oauth_state"}
    workspace_id = str(pending.get("workspace_id") or "")
    cfg = _github_oauth_app_config(workspace_id)
    client_id = str(cfg.get("client_id") or "").strip()
    client_secret = str(cfg.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        return {"ok": False, "error": "github_oauth_not_configured"}
    token_data = _github_exchange_code(
        code,
        client_id,
        client_secret,
        _github_oauth_redirect_uri(),
        str(pending.get("code_verifier") or ""),
    )
    if token_data.get("error"):
        return {"ok": False, "error": str(token_data.get("error"))}
    access_token = str(token_data.get("access_token") or "").strip()
    if not access_token:
        return {"ok": False, "error": "github_missing_access_token"}
    spec = _catalog_provider("github") or {}
    env_var = str(spec.get("env_var") or "GITHUB_TOKEN")
    payload = _store_user_credential(user_id, "github", "oauth", access_token, env_var, "GitHub OAuth")
    cred_ref = str(payload["credential_ref"])
    now = _utc_now()
    cred_id = str(uuid.uuid4())
    try:
        conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
        conn.execute(
            """
            INSERT INTO credential_bindings
            (id, workspace_id, user_id, agent_profile_id, provider, credential_type,
             credential_ref, label, is_active, created_by, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                cred_id, None, user_id, None, "github", "oauth", cred_ref,
                "GitHub OAuth", 1, user_id, now, now,
            ),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"db_error: {exc}"}
    return {"ok": True, "provider": "github", "credential_id": cred_id}


def _stripe_exchange_code(code: str, client_secret: str) -> dict[str, Any]:
    body = urllib.parse.urlencode(
        {
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://connect.stripe.com/oauth/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
    except OSError as exc:
        return {"error": str(exc)}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"error": raw or "stripe_token_exchange_failed"}
    return data if isinstance(data, dict) else {"error": "invalid_stripe_response"}


def _start_stripe_oauth(user_id: str, workspace_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    cfg = _stripe_connect_app_config()
    client_id = str(cfg.get("client_id") or "").strip()
    client_secret = str(cfg.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        return {
            "ok": False,
            "error": "stripe_connect_not_configured",
            "message": "Workframe admin must register Stripe Connect under Workframe → Integrations.",
        }
    state = secrets.token_urlsafe(24)
    _store_oauth_pending(state, user_id, "stripe", "", workspace_id)
    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "scope": STRIPE_CONNECT_SCOPES,
            "redirect_uri": _stripe_oauth_redirect_uri(),
            "state": state,
        },
    )
    return {
        "ok": True,
        "provider": str(spec.get("id") or "stripe"),
        "redirect_url": f"https://connect.stripe.com/oauth/authorize?{params}",
        "output": "",
        "error": None,
    }


def _complete_stripe_oauth(user_id: str, code: str, state: str) -> dict[str, Any]:
    pending = _take_oauth_pending(state)
    if not pending or str(pending.get("user_id") or "") != user_id:
        return {"ok": False, "error": "invalid_oauth_state"}
    cfg = _stripe_connect_app_config()
    client_secret = str(cfg.get("client_secret") or "").strip()
    if not client_secret:
        return {"ok": False, "error": "stripe_connect_not_configured"}
    token_data = _stripe_exchange_code(code, client_secret)
    if token_data.get("error"):
        err = token_data.get("error")
        if isinstance(err, dict):
            return {"ok": False, "error": str(err.get("message") or err.get("description") or "stripe_oauth_failed")}
        return {"ok": False, "error": str(err)}
    access_token = str(token_data.get("access_token") or "").strip()
    if not access_token:
        return {"ok": False, "error": "stripe_missing_access_token"}
    stripe_user_id = str(token_data.get("stripe_user_id") or "").strip()
    spec = _catalog_provider("stripe") or {}
    env_var = str(spec.get("env_var") or "STRIPE_SECRET_KEY")
    label = f"Stripe Connect ({stripe_user_id})" if stripe_user_id else "Stripe Connect"
    payload = _store_user_credential(user_id, "stripe", "oauth", access_token, env_var, label)
    cred_ref = str(payload["credential_ref"])
    now = _utc_now()
    cred_id = str(uuid.uuid4())
    try:
        conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
        conn.execute(
            """
            INSERT INTO credential_bindings
            (id, workspace_id, user_id, agent_profile_id, provider, credential_type,
             credential_ref, label, is_active, created_by, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                cred_id, None, user_id, None, "stripe", "oauth", cred_ref,
                label, 1, user_id, now, now,
            ),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"db_error: {exc}"}
    return {"ok": True, "provider": "stripe", "credential_id": cred_id, "stripe_user_id": stripe_user_id}


def _merge_user_platform_ids(user_id: str, patch: dict[str, str]) -> None:
    user_id = str(user_id or "").strip()
    if not user_id or not patch:
        return
    current: dict[str, str] = {}
    user = _get_workframe_user(user_id)
    if user and isinstance(user.get("platform_ids"), dict):
        current = {str(k): str(v) for k, v in user["platform_ids"].items() if str(v or "").strip()}
    merged = {**current, **{str(k): str(v) for k, v in patch.items() if str(v or "").strip()}}
    _apply_me_profile_updates(user_id, {"platform_ids": merged})


def _read_user_llm_prefs(user_id: str) -> tuple[str, list[dict[str, str]]]:
    """User-level default model prefs (not agent profile config)."""
    user = _get_workframe_user(str(user_id or "").strip())
    pids = user.get("platform_ids") if user and isinstance(user.get("platform_ids"), dict) else {}
    primary = str(pids.get("llm_primary") or "").strip()
    chain_raw = pids.get("llm_fallback_chain")
    chain: list[dict[str, str]] = []
    if isinstance(chain_raw, str) and chain_raw.strip():
        try:
            parsed = json.loads(chain_raw)
            if isinstance(parsed, list):
                for entry in parsed:
                    if isinstance(entry, dict):
                        prov = str(entry.get("provider") or "").strip()
                        model = str(entry.get("model") or "").strip()
                        if prov and model:
                            chain.append({"provider": prov, "model": model})
        except json.JSONDecodeError:
            pass
    return primary, chain


def _write_user_llm_prefs(
    user_id: str,
    *,
    primary: str = "",
    fallback_chain: list[dict[str, str]] | None = None,
) -> None:
    user_id = str(user_id or "").strip()
    if not user_id:
        return
    patch: dict[str, str] = {}
    if primary:
        patch["llm_primary"] = primary.strip()
    if fallback_chain is not None:
        patch["llm_fallback_chain"] = json.dumps(fallback_chain, separators=(",", ":"))
    if patch:
        _merge_user_platform_ids(user_id, patch)


def _user_llm_has_provider(user_id: str, workspace_id: str = "") -> bool:
    if _user_has_llm_provider(user_id):
        return True
    ws = str(workspace_id or "").strip()
    return bool(ws and _workspace_has_llm_provider(ws))


def _start_discord_oauth(user_id: str, workspace_id: str = "") -> dict[str, Any]:
    cfg = platform_auth.resolved_discord_oauth()
    if not cfg.get("client_id") or not cfg.get("client_secret"):
        return {
            "ok": False,
            "error": "discord_oauth_not_configured",
            "message": "Workframe admin must register a Discord OAuth app under Integrations.",
        }
    state = secrets.token_urlsafe(24)
    _store_oauth_pending(state, user_id, "discord", "", workspace_id)
    params = urllib.parse.urlencode(
        {
            "client_id": cfg["client_id"],
            "redirect_uri": platform_auth.discord_redirect_uri(),
            "response_type": "code",
            "scope": "identify",
            "state": state,
            "prompt": "consent",
        },
    )
    return {
        "ok": True,
        "provider": "discord",
        "redirect_url": f"https://discord.com/api/oauth2/authorize?{params}",
        "output": "",
        "error": None,
    }


def _complete_discord_oauth(user_id: str, code: str, state: str) -> dict[str, Any]:
    pending = _take_oauth_pending(state)
    if not pending or str(pending.get("user_id") or "") != user_id:
        return {"ok": False, "error": "invalid_oauth_state"}
    if str(pending.get("provider") or "") != "discord":
        return {"ok": False, "error": "invalid_oauth_provider"}
    result = platform_auth.complete_discord_link(str(code or ""))
    if not result.get("ok"):
        return result
    patch = result.get("platform_ids") if isinstance(result.get("platform_ids"), dict) else {}
    if patch:
        _merge_user_platform_ids(user_id, {str(k): str(v) for k, v in patch.items()})
    return {"ok": True, "provider": "discord", "platform_ids": patch}


def _user_action_env_specs() -> list[tuple[str, str]]:
    specs: list[tuple[str, str]] = []
    for row in PROVIDER_CONNECT_CATALOG:
        if not row.get("user_only"):
            continue
        for env_var in _provider_env_vars(row):
            specs.append((str(row["id"]), env_var))
    return specs


def _overlay_turn_user_env(profile: str, user_id: str, workspace_id: str, run_id: str = "") -> None:
    """Issue per-run lease tokens for user-only tool credentials (never raw PATs on Agents mount)."""
    user = str(user_id or "").strip()
    if not user:
        return
    base_run = str(run_id or "").strip() or str(uuid.uuid4())
    for provider_id, _env_var in _user_action_env_specs():
        sub_run = f"{base_run}::{provider_id}"
        try:
            _apply_action_credential_lease(profile, user, workspace_id, provider_id, sub_run)
        except ValueError:
            continue


def _strip_profile_action_env(profile: str) -> bool:
    """Remove dev PAT tokens from specialist profile .env (never shared-stack keys)."""
    try:
        prof = resolve_hermes_profile(profile)
    except ValueError:
        return False
    if prof == _primary_profile() and not _is_runtime_profile_slug(prof):
        return False
    path = _profile_dir(prof) / ".env"
    if not path.is_file():
        return False
    drop = set()
    for _pid, env_var in _user_action_env_specs():
        drop.add(env_var)
    kept: list[str] = []
    changed = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.partition("=")[0].strip()
            if key in drop:
                changed = True
                continue
        kept.append(line)
    if changed:
        path.write_text("\n".join(kept).rstrip() + ("\n" if kept else ""), encoding="utf-8")
    return changed


def _read_env_keys(env_path: Path) -> set[str]:
    return set(_read_env_map(env_path).keys())


def _read_env_map(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, _sep, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and value:
            values[key] = value
    return values


def _llm_provider_env_vars() -> list[str]:
    names: list[str] = []
    for spec in PROVIDER_CONNECT_CATALOG:
        if str(spec.get("category") or "") != "llm":
            continue
        env_var = str(spec.get("env_var") or "").strip()
        if env_var:
            names.append(env_var)
    return names


def _remove_env_secret(env_path: Path, key: str) -> None:
    if not env_path.is_file():
        return
    kept: list[str] = []
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            current_key, _sep, _rest = line.partition("=")
            if current_key.strip() == key:
                continue
        kept.append(line)
    env_path.write_text("\n".join(kept).rstrip() + ("\n" if kept else ""), encoding="utf-8")


def _remove_auth_metadata(auth_path: Path, credential_ref: str) -> None:
    if not auth_path.is_file():
        return
    try:
        loaded = json.loads(auth_path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(loaded, dict):
        return
    bindings = loaded.get("credentials")
    if not isinstance(bindings, list):
        return
    loaded["credentials"] = [
        row for row in bindings
        if not isinstance(row, dict) or str(row.get("credential_ref") or "") != credential_ref
    ]
    loaded["updated_at"] = _utc_now()
    auth_path.write_text(json.dumps(loaded, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _hermes_user_home_container(user_id: str) -> str:
    return f"/opt/data/profiles/{_user_hermes_dir_slug(user_id)}"


def _hermes_user_exec(user_id: str, args: list[str]) -> tuple[int, str]:
    home = _hermes_user_home_container(user_id)
    _user_hermes_home(user_id).mkdir(parents=True, exist_ok=True)
    if SECURE_MODE:
        if not _supervisor_ready():
            raise RuntimeError(
                "Docker socket access is disabled in SECURE_MODE; "
                "configure WORKFRAME_SUPERVISOR_URL and WORKFRAME_SUPERVISOR_TOKEN"
            )
        status, data = _supervisor_request(
            "POST",
            "/v1/hermes.user_exec",
            {"home": home, "args": [str(part) for part in args]},
            timeout=120.0,
        )
        if status >= 300:
            err = data.get("error") if isinstance(data, dict) else str(data)
            raise ValueError(err or f"supervisor hermes.user_exec failed ({status})")
        if not isinstance(data, dict):
            raise ValueError("supervisor hermes.user_exec returned invalid payload")
        exit_code = data.get("exit_code")
        try:
            code = int(exit_code if exit_code is not None else 1)
        except (TypeError, ValueError):
            code = 1
        return code, str(data.get("output") or "")
    inner = " ".join(shlex.quote(part) for part in args)
    shell = (
        f"export HERMES_HOME={shlex.quote(home)} HOME={shlex.quote(home)}; "
        f"mkdir -p {shlex.quote(home)}; cd {shlex.quote(home)}; "
        f"/opt/hermes/bin/hermes {inner}"
    )
    return _docker_exec(GATEWAY_CONTAINER_NAME, ["sh", "-lc", shell], acting_profile=_user_hermes_dir_slug(user_id))


def _user_provider_bindings(user_id: str) -> dict[str, dict[str, Any]]:
    by_provider: dict[str, dict[str, Any]] = {}
    try:
        conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT id, provider, credential_type, credential_ref, label, is_active, updated_at
               FROM credential_bindings
               WHERE user_id = ? AND deleted_at IS NULL AND is_active = 1
               ORDER BY updated_at DESC, created_at DESC""",
            (user_id,),
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        rows = []
    for row in rows:
        provider = str(row["provider"] or "").lower()
        if provider and provider not in by_provider:
            by_provider[provider] = dict(row)
    return by_provider


_DEVICE_OAUTH_PROVIDER_IDS: frozenset[str] = frozenset({"codex", "nous"})
_oauth_device_lock = threading.Lock()
_oauth_device_sessions: dict[str, dict[str, Any]] = {}


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", str(text or ""))


def _hermes_auth_id_for_spec(spec: dict[str, Any]) -> str:
    return str(spec.get("hermes_auth_id") or spec.get("id") or "").strip()


def _hermes_oauth_auth_keys(hermes_auth_id: str) -> set[str]:
    raw = str(hermes_auth_id or "").strip().lower()
    if not raw:
        return set()
    keys = {raw, raw.replace("-", ""), raw.replace("-", "_")}
    if "-" in raw:
        keys.add(raw.split("-")[-1])
    return {key for key in keys if key}


def _oauth_llm_provider_spec(provider: str) -> dict[str, Any] | None:
    spec = _catalog_provider_for_llm(provider)
    if spec and str(spec.get("connect_mode") or "") == "oauth":
        return spec
    return None


def _auth_json_has_oauth_material(data: dict[str, Any]) -> bool:
    providers = data.get("providers")
    if isinstance(providers, dict) and providers:
        return True
    pool = data.get("credential_pool")
    if isinstance(pool, dict) and any(isinstance(entries, list) and entries for entries in pool.values()):
        return True
    creds = data.get("credentials")
    return isinstance(creds, list) and bool(creds)


def _extract_oauth_block_from_auth(loaded: dict[str, Any], hermes_auth_id: str) -> dict[str, Any] | None:
    keys = _hermes_oauth_auth_keys(hermes_auth_id)
    providers = loaded.get("providers")
    if isinstance(providers, dict):
        for key, entry in providers.items():
            if str(key).lower() in keys and isinstance(entry, dict):
                tokens = entry.get("tokens")
                if isinstance(tokens, dict) and any(
                    str(tokens.get(field) or "").strip()
                    for field in ("access_token", "refresh_token", "api_key", "id_token")
                ):
                    return entry
                if entry:
                    return entry
    creds = loaded.get("credentials")
    if isinstance(creds, list):
        for row in creds:
            if not isinstance(row, dict):
                continue
            pid = str(row.get("provider") or row.get("id") or "").lower()
            if pid in keys:
                return row
    return None


def _merge_oauth_auth_into_profile(
    auth: dict[str, Any],
    user_auth: dict[str, Any],
    hermes_auth_id: str,
) -> bool:
    keys = _hermes_oauth_auth_keys(hermes_auth_id)
    changed = False
    block = _extract_oauth_block_from_auth(user_auth, hermes_auth_id)
    if isinstance(block, dict):
        merged = auth.get("providers") if isinstance(auth.get("providers"), dict) else {}
        merged[hermes_auth_id] = block
        auth["providers"] = merged
        changed = True
    user_pool = user_auth.get("credential_pool")
    if isinstance(user_pool, dict):
        pool = auth.get("credential_pool")
        if not isinstance(pool, dict):
            pool = {}
            auth["credential_pool"] = pool
        for key, entries in user_pool.items():
            if str(key).lower() in keys and isinstance(entries, list) and entries:
                pool[hermes_auth_id] = entries
                changed = True
    return changed


def _sync_oauth_llm_to_profile(profile: str, user_id: str, provider: str) -> bool:
    spec = _oauth_llm_provider_spec(provider)
    if not spec:
        return False
    hermes_auth_id = _hermes_auth_id_for_spec(spec)
    if not _hermes_oauth_tokens_present(user_id, hermes_auth_id):
        return False
    user_auth = _load_user_hermes_auth(user_id)
    if not isinstance(user_auth, dict):
        return False
    prof = resolve_hermes_profile(profile)
    auth_path = _profile_dir(prof) / "auth.json"
    auth = _load_profile_auth_json(prof)
    if not _merge_oauth_auth_into_profile(auth, user_auth, hermes_auth_id):
        return False
    auth["version"] = 1
    auth["updated_at"] = _utc_now()
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(json.dumps(auth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _publish_profile_gateway_secrets(prof)
    return True


def _hermes_oauth_tokens_present(user_id: str, hermes_auth_id: str) -> bool:
    """True when Hermes auth.json has live OAuth tokens for a provider."""
    hermes_auth_id = str(hermes_auth_id or "").strip()
    if not hermes_auth_id:
        return False
    loaded = _load_user_hermes_auth(user_id)
    if not isinstance(loaded, dict):
        return False
    if _extract_oauth_block_from_auth(loaded, hermes_auth_id):
        return True
    keys = _hermes_oauth_auth_keys(hermes_auth_id)
    pool = loaded.get("credential_pool")
    if isinstance(pool, dict):
        for key, entries in pool.items():
            if str(key).lower() in keys and isinstance(entries, list) and entries:
                return True
    return False


def _load_user_hermes_auth(user_id: str) -> dict[str, Any] | None:
    auth_path = _user_hermes_auth_path(user_id)
    loaded: dict[str, Any] | None = None
    if auth_path.is_file():
        try:
            data = json.loads(auth_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                loaded = data
        except (OSError, json.JSONDecodeError):
            loaded = None
    if isinstance(loaded, dict) and _auth_json_has_oauth_material(loaded):
        return loaded
    rel = f"profiles/{_user_hermes_dir_slug(user_id)}/auth.json"
    text = _read_gateway_data_file(rel)
    if text.strip():
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return loaded


def _read_gateway_data_file(rel_path: str) -> str:
    rel_path = str(rel_path or "").strip().lstrip("/")
    if not rel_path or ".." in rel_path.split("/"):
        return ""
    host_path = HERMES_DATA / rel_path
    if host_path.is_file():
        try:
            return host_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
    full = f"/opt/data/{rel_path}"
    try:
        code, out = _gateway_container_exec(["cat", full])
        return out if code == 0 else ""
    except Exception:
        return ""


def _user_provider_connected(user_id: str, spec: dict[str, Any]) -> bool:
    """Connected = this user's credential resolves with a live secret (no stack/install bleed)."""
    if str(spec.get("connect_mode") or "") == "oauth":
        if _hermes_oauth_tokens_present(user_id, _hermes_auth_id_for_spec(spec)):
            return True
    provider_id = str(spec["id"])
    if str(spec.get("category") or "") == "llm":
        resolved = _resolve_credential(user_id, "", provider_id, user_only=True)
        return bool(resolved and _credential_secret(resolved, user_id))
    bindings = _user_provider_bindings(user_id)
    env_keys = _user_auth_env_keys(user_id)
    return _provider_connected_for_user(user_id, spec, bindings, env_keys)


def list_user_providers(user_id: str, workspace_id: str = "") -> dict[str, Any]:
    bindings = _user_provider_bindings(user_id)
    workspace = str(workspace_id or "").strip()
    providers: list[dict[str, Any]] = []
    for spec in PROVIDER_CONNECT_CATALOG:
        provider_id = str(spec["id"])
        env_var = str(spec.get("env_var") or "")
        binding = bindings.get(provider_id)
        connected = _user_provider_connected(user_id, spec)
        source: str | None = "user" if connected else None
        if not connected and workspace and str(spec.get("category") or "") == "llm":
            resolved = _resolve_credential("", workspace, provider_id)
            if resolved and _credential_secret(resolved, user_id):
                connected = True
                source = "workspace"
        oauth_configured = None
        if str(spec.get("connect_mode") or "") == "oauth":
            oauth_name = str(spec.get("oauth_provider") or provider_id)
            if oauth_name == "github":
                oauth_configured = _github_oauth_configured(workspace_id)
            elif oauth_name == "stripe":
                oauth_configured = _stripe_connect_configured()
        providers.append({
            **spec,
            "connected": connected,
            "source": source,
            "credential_id": str(binding["id"]) if binding else None,
            "credential_ref": str(binding["credential_ref"]) if binding else (f"env:{env_var}" if env_var and connected else None),
            "profile_home": str(_user_hermes_home(user_id)),
            "oauth_configured": oauth_configured,
            "user_only": bool(spec.get("user_only")),
        })
    return {"ok": True, "providers": providers, "profile_home": str(_user_hermes_home(user_id))}


def disconnect_user_credential(user_id: str, credential_id: str) -> dict[str, Any]:
    try:
        conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """SELECT id, provider, credential_type, credential_ref
               FROM credential_bindings
               WHERE id = ? AND user_id = ? AND deleted_at IS NULL""",
            (credential_id, user_id),
        ).fetchone()
        if not row:
            conn.close()
            return {"ok": False, "error": "credential_not_found"}
        cred_ref = str(row["credential_ref"] or "")
        env_var = cred_ref[4:] if cred_ref.startswith("env:") else ""
        if not env_var:
            spec = _catalog_provider(str(row["provider"]))
            env_var = str((spec or {}).get("env_var") or "")
        if env_var:
            _remove_env_secret(_user_hermes_env_path(user_id), env_var)
            _remove_auth_metadata(_user_hermes_auth_path(user_id), cred_ref or f"env:{env_var}")
        now = _utc_now()
        conn.execute(
            "UPDATE credential_bindings SET is_active = 0, deleted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, credential_id),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"db_error: {exc}"}
    return {"ok": True, "credential_id": credential_id, "provider": str(row["provider"])}


def _remove_hermes_oauth_provider(user_id: str, hermes_auth_id: str) -> None:
    hermes_auth_id = str(hermes_auth_id or "").strip()
    if not hermes_auth_id:
        return
    auth_path = _user_hermes_auth_path(user_id)
    if auth_path.is_file():
        try:
            loaded = json.loads(auth_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict):
            providers = loaded.get("providers")
            if isinstance(providers, dict):
                for key in list(providers.keys()):
                    if key.lower() in {hermes_auth_id.lower(), hermes_auth_id.replace("-", "").lower()}:
                        providers.pop(key, None)
            pool = loaded.get("credential_pool")
            if isinstance(pool, dict):
                for key in list(pool.keys()):
                    if key.lower() in {hermes_auth_id.lower(), hermes_auth_id.replace("-", "").lower()}:
                        pool.pop(key, None)
            loaded["updated_at"] = _utc_now()
            auth_path.write_text(json.dumps(loaded, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    user_part = re.sub(r"[^a-z0-9]+", "-", _user_hermes_dir_slug(user_id).lower()).strip("-")[:20] or "user"
    prefix = f"u-{user_part}-"
    profiles_dir = HERMES_DATA / "profiles"
    if profiles_dir.is_dir():
        for prof_dir in profiles_dir.iterdir():
            if not prof_dir.is_dir() or not prof_dir.name.startswith(prefix):
                continue
            prof_auth = prof_dir / "auth.json"
            if not prof_auth.is_file():
                continue
            try:
                pdata = json.loads(prof_auth.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(pdata, dict):
                continue
            pproviders = pdata.get("providers")
            if isinstance(pproviders, dict):
                for key in list(pproviders.keys()):
                    if key.lower() in {hermes_auth_id.lower(), hermes_auth_id.replace("-", "").lower()}:
                        pproviders.pop(key, None)
                pdata["updated_at"] = _utc_now()
                prof_auth.write_text(json.dumps(pdata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def disconnect_user_provider(user_id: str, provider_id: str) -> dict[str, Any]:
    spec = _catalog_provider(provider_id)
    if not spec:
        return {"ok": False, "error": "provider_not_found"}
    env_var = str(spec.get("env_var") or "")
    if env_var:
        _remove_env_secret(_user_hermes_env_path(user_id), env_var)
        _remove_auth_metadata(_user_hermes_auth_path(user_id), f"env:{env_var}")
    if str(spec.get("connect_mode") or "") == "oauth":
        _remove_hermes_oauth_provider(user_id, _hermes_auth_id_for_spec(spec))
    binding = _user_provider_bindings(user_id).get(str(spec["id"]))
    if binding:
        return disconnect_user_credential(user_id, str(binding["id"]))
    return {"ok": True, "provider": provider_id, "disconnected": True}


def _hermes_user_shell(user_id: str, script: str, *, timeout: float = 30.0) -> tuple[int, str]:
    home = _hermes_user_home_container(user_id)
    _user_hermes_home(user_id).mkdir(parents=True, exist_ok=True)
    shell = (
        f"export HERMES_HOME={shlex.quote(home)} HOME={shlex.quote(home)}; "
        f"mkdir -p {shlex.quote(home)}; cd {shlex.quote(home)}; {script}"
    )
    if SECURE_MODE:
        if not _supervisor_ready():
            raise RuntimeError(
                "Docker socket access is disabled in SECURE_MODE; "
                "configure WORKFRAME_SUPERVISOR_URL and WORKFRAME_SUPERVISOR_TOKEN"
            )
        status, data = _supervisor_request(
            "POST",
            "/v1/gateway.container_exec",
            {"args": ["sh", "-lc", shell]},
            timeout=timeout,
        )
        if status >= 300:
            err = data.get("error") if isinstance(data, dict) else str(data)
            raise ValueError(err or f"supervisor gateway.container_exec failed ({status})")
        if not isinstance(data, dict):
            raise ValueError("supervisor gateway.container_exec returned invalid payload")
        exit_code = data.get("exit_code")
        try:
            code = int(exit_code if exit_code is not None else 1)
        except (TypeError, ValueError):
            code = 1
        return code, str(data.get("output") or "")
    return _docker_exec(GATEWAY_CONTAINER_NAME, ["sh", "-lc", shell])


def _parse_device_oauth_log(text: str) -> dict[str, str | None]:
    clean = _strip_ansi(text)
    verification_uri = None
    for match in re.finditer(r"https?://[^\s\]\)>\"']+", clean):
        url = match.group(0).rstrip(".,;)")
        if any(token in url.lower() for token in ("/device", "/portal", "auth.openai.com", "nousresearch")):
            verification_uri = url
            break
    if not verification_uri:
        url_match = re.search(
            r"Open this URL.*?\n\s*(\S+)",
            clean,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if url_match:
            verification_uri = url_match.group(1).strip()
    user_code = None
    code_match = re.search(
        r"Enter this code.*?\n\s*(\S+)",
        clean,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if code_match:
        user_code = code_match.group(1).strip()
    if not user_code:
        bare = re.search(r"\b([A-Z0-9]{4,8}-[A-Z0-9]{4,8})\b", clean)
        if bare:
            user_code = bare.group(1)
    return {"verification_uri": verification_uri, "user_code": user_code}


def _sync_user_oauth_provider_to_runtime_profiles(user_id: str, hermes_auth_id: str) -> None:
    if not _hermes_oauth_tokens_present(user_id, hermes_auth_id):
        return
    user_auth = _load_user_hermes_auth(user_id)
    if not isinstance(user_auth, dict):
        return
    user_part = re.sub(r"[^a-z0-9]+", "-", _user_hermes_dir_slug(user_id).lower()).strip("-")[:20] or "user"
    prefix = f"u-{user_part}-"
    profiles_dir = HERMES_DATA / "profiles"
    if not profiles_dir.is_dir():
        return
    for prof_dir in profiles_dir.iterdir():
        if not prof_dir.is_dir() or not prof_dir.name.startswith(prefix):
            continue
        auth_path = prof_dir / "auth.json"
        auth = _load_profile_auth_json(prof_dir.name)
        user_auth = _load_user_hermes_auth(user_id)
        if not isinstance(user_auth, dict):
            continue
        if not _merge_oauth_auth_into_profile(auth, user_auth, hermes_auth_id):
            continue
        auth["version"] = 1
        auth["updated_at"] = _utc_now()
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        auth_path.write_text(json.dumps(auth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _publish_profile_gateway_secrets(prof_dir.name)


def _finalize_hermes_device_oauth(user_id: str, provider_id: str, spec: dict[str, Any]) -> None:
    hermes_auth_id = _hermes_auth_id_for_spec(spec)
    _sync_user_oauth_provider_to_runtime_profiles(user_id, hermes_auth_id)
    _bootstrap_model_after_llm_connect(user_id, "", provider_id)


def _device_oauth_session_get(session_id: str) -> dict[str, Any] | None:
    with _oauth_device_lock:
        row = _oauth_device_sessions.get(str(session_id or "").strip())
        return dict(row) if isinstance(row, dict) else None


def _device_oauth_session_patch(session_id: str, patch: dict[str, Any]) -> None:
    with _oauth_device_lock:
        row = _oauth_device_sessions.get(session_id)
        if isinstance(row, dict):
            row.update(patch)


def _spawn_hermes_device_oauth(user_id: str, hermes_auth_id: str, log_container: str) -> tuple[int, str]:
    """Start long-running `hermes auth add` detached in gateway (survives exec return)."""
    home = _hermes_user_home_container(user_id)
    _user_hermes_home(user_id).mkdir(parents=True, exist_ok=True)
    if SECURE_MODE and _supervisor_ready():
        status, data = _supervisor_request(
            "POST",
            "/v1/hermes.device_oauth_start",
            {"home": home, "hermes_auth_id": hermes_auth_id, "log_path": log_container},
            timeout=30.0,
        )
        if status >= 300:
            err = data.get("error") if isinstance(data, dict) else str(data)
            raise ValueError(err or "device_oauth_start_failed")
        if not isinstance(data, dict):
            raise ValueError("device_oauth_start_invalid")
        exit_code = data.get("exit_code")
        try:
            code = int(exit_code if exit_code is not None else 1)
        except (TypeError, ValueError):
            code = 1
        return code, str(data.get("output") or "")
    auth_cmd = " ".join(shlex.quote(part) for part in ["auth", "add", hermes_auth_id])
    shell = (
        f"mkdir -p {shlex.quote(home)}; "
        f"chown -R hermes:hermes {shlex.quote(home)}; "
        f"su -s /bin/sh hermes -c "
        f"'export HERMES_HOME={shlex.quote(home)} HOME={shlex.quote(home)}; "
        f"cd {shlex.quote(home)}; "
        f"/opt/hermes/bin/hermes {auth_cmd} >> {shlex.quote(log_container)} 2>&1'"
    )
    return _gateway_container_exec_detached(["sh", "-lc", shell])


def _start_device_oauth(user_id: str, provider_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    hermes_auth_id = _hermes_auth_id_for_spec(spec)
    session_id = secrets.token_urlsafe(16)
    log_name = f".oauth-{session_id}.log"
    home = _hermes_user_home_container(user_id)
    log_container = f"{home}/{log_name}"
    log_host = _user_hermes_home(user_id) / log_name
    try:
        rc, out = _spawn_hermes_device_oauth(user_id, hermes_auth_id, log_container)
    except (RuntimeError, ValueError) as exc:
        return {"ok": False, "provider": provider_id, "error": str(exc)}
    if rc != 0:
        return {
            "ok": False,
            "provider": provider_id,
            "error": "oauth_start_failed",
            "output": (out or "").strip(),
        }
    with _oauth_device_lock:
        _oauth_device_sessions[session_id] = {
            "user_id": user_id,
            "provider_id": provider_id,
            "hermes_auth_id": hermes_auth_id,
            "log_path": str(log_host),
            "status": "pending",
            "verification_uri": None,
            "user_code": None,
            "finalized": False,
            "started_at": time.time(),
        }
    status = device_oauth_status(user_id, provider_id, session_id)
    return {
        "ok": True,
        "provider": provider_id,
        "hermes_auth_id": hermes_auth_id,
        "flow": "device_code",
        "session_id": session_id,
        "status": status.get("status") or "pending",
        "verification_uri": status.get("verification_uri"),
        "user_code": status.get("user_code"),
        "message": status.get("message"),
    }


def device_oauth_status(user_id: str, provider_id: str, session_id: str) -> dict[str, Any]:
    sess = _device_oauth_session_get(session_id)
    if not sess or sess.get("user_id") != user_id or sess.get("provider_id") != provider_id:
        return {"ok": False, "error": "session_not_found"}
    spec = _catalog_provider(provider_id) or {}
    hermes_auth_id = str(sess.get("hermes_auth_id") or _hermes_auth_id_for_spec(spec))
    log_path = Path(str(sess.get("log_path") or ""))
    log_text = ""
    if log_path.is_file():
        try:
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            log_text = ""
    if not log_text.strip() and log_path.name:
        log_text = _read_gateway_data_file(f"profiles/{_user_hermes_dir_slug(user_id)}/{log_path.name}")
    parsed = _parse_device_oauth_log(log_text)
    patch: dict[str, Any] = {}
    if parsed.get("verification_uri"):
        patch["verification_uri"] = parsed["verification_uri"]
    if parsed.get("user_code"):
        patch["user_code"] = parsed["user_code"]
    if patch:
        _device_oauth_session_patch(session_id, patch)
        sess.update(patch)
    if _hermes_oauth_tokens_present(user_id, hermes_auth_id):
        if not sess.get("finalized"):
            _finalize_hermes_device_oauth(user_id, provider_id, spec)
            _device_oauth_session_patch(session_id, {"status": "connected", "finalized": True})
        return {
            "ok": True,
            "provider": provider_id,
            "session_id": session_id,
            "status": "connected",
            "verification_uri": sess.get("verification_uri"),
            "user_code": sess.get("user_code"),
        }
    lowered = log_text.lower()
    if any(token in lowered for token in ("login successful", "auth added", "credentials saved", "successfully authenticated", "logged in")):
        if _hermes_oauth_tokens_present(user_id, hermes_auth_id):
            if not sess.get("finalized"):
                _finalize_hermes_device_oauth(user_id, provider_id, spec)
                _device_oauth_session_patch(session_id, {"status": "connected", "finalized": True})
            return {
                "ok": True,
                "provider": provider_id,
                "session_id": session_id,
                "status": "connected",
                "verification_uri": sess.get("verification_uri"),
                "user_code": sess.get("user_code"),
            }
    if any(token in lowered for token in ("autherror", "login timed out", "login cancelled", "failed")):
        _device_oauth_session_patch(session_id, {"status": "error"})
        return {
            "ok": False,
            "provider": provider_id,
            "session_id": session_id,
            "status": "error",
            "error": "oauth_failed",
            "message": _strip_ansi(log_text).strip()[-500:] or "OAuth failed",
            "verification_uri": sess.get("verification_uri"),
            "user_code": sess.get("user_code"),
        }
    started = float(sess.get("started_at") or 0.0)
    if started and time.time() - started > 16 * 60:
        _device_oauth_session_patch(session_id, {"status": "error"})
        return {
            "ok": False,
            "provider": provider_id,
            "session_id": session_id,
            "status": "error",
            "error": "oauth_timeout",
            "verification_uri": sess.get("verification_uri"),
            "user_code": sess.get("user_code"),
        }
    return {
        "ok": True,
        "provider": provider_id,
        "session_id": session_id,
        "status": "pending",
        "verification_uri": sess.get("verification_uri"),
        "user_code": sess.get("user_code"),
    }


def start_user_oauth(user_id: str, provider_id: str, workspace_id: str = "") -> dict[str, Any]:
    if str(provider_id).lower() == "discord":
        return _start_discord_oauth(user_id, workspace_id)
    spec = _catalog_provider(provider_id)
    if not spec or str(spec.get("connect_mode")) != "oauth":
        return {"ok": False, "error": "not_oauth_provider"}
    oauth_provider = str(spec.get("oauth_provider") or spec["id"]).lower()
    if oauth_provider == "github":
        return {**_start_github_oauth(user_id, workspace_id, spec), "flow": "redirect"}
    if oauth_provider == "stripe":
        return {**_start_stripe_oauth(user_id, workspace_id, spec), "flow": "redirect"}
    if str(provider_id).lower() in _DEVICE_OAUTH_PROVIDER_IDS:
        return _start_device_oauth(user_id, provider_id, spec)
    hermes_auth_id = _hermes_auth_id_for_spec(spec)
    rc, out = _hermes_user_exec(user_id, ["auth", "add", hermes_auth_id])
    redirect_url = None
    for token in re.findall(r"https?://[^\s\])>\"']+", out or ""):
        redirect_url = token.rstrip(".,;)")
        break
    return {
        "ok": rc == 0,
        "provider": provider_id,
        "hermes_auth_id": hermes_auth_id,
        "output": (out or "").strip(),
        "redirect_url": redirect_url,
        "flow": "redirect" if redirect_url else "device_code",
        "error": None if rc == 0 else "oauth_start_failed",
    }


OWNER_ADMIN_ROLES = {"owner", "admin"}
WORKSPACE_MEMBER_ROLES = {"owner", "admin", "editor", "viewer", "member"}
WORKSPACE_MEMBER_STATUSES = {"active", "invited", "removed"}


WORKFRAME_DB_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    email           TEXT UNIQUE,
    display_name    TEXT NOT NULL DEFAULT '',
    avatar_url      TEXT DEFAULT NULL,
    platform_ids    TEXT DEFAULT '{}',
    role            TEXT NOT NULL DEFAULT 'member',
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS workspaces (
    id              TEXT PRIMARY KEY,
    slug            TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL DEFAULT '',
    description     TEXT DEFAULT '',
    owner_id        TEXT NOT NULL,
    runtime_mode    TEXT NOT NULL DEFAULT 'docker',
    ports           TEXT DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS workspace_memberships (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'member',
    status          TEXT NOT NULL DEFAULT 'active',
    invited_by      TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS credential_bindings (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT DEFAULT NULL,
    user_id         TEXT DEFAULT NULL,
    agent_profile_id TEXT DEFAULT NULL,
    provider        TEXT NOT NULL,
    credential_type TEXT NOT NULL DEFAULT 'api_key',
    credential_ref  TEXT NOT NULL,
    label           TEXT DEFAULT '',
    is_active       INTEGER NOT NULL DEFAULT 1,
    expires_at      TEXT DEFAULT NULL,
    created_by      TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    CHECK (
        (workspace_id IS NOT NULL AND user_id IS NULL AND agent_profile_id IS NULL)
        OR (workspace_id IS NULL AND user_id IS NOT NULL AND agent_profile_id IS NULL)
        OR (workspace_id IS NULL AND user_id IS NULL AND agent_profile_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_credential_bindings_workspace_active
    ON credential_bindings(workspace_id, provider, is_active, deleted_at);

CREATE INDEX IF NOT EXISTS idx_credential_bindings_user_active
    ON credential_bindings(user_id, provider, is_active, deleted_at);

CREATE INDEX IF NOT EXISTS idx_credential_bindings_agent_active
    ON credential_bindings(agent_profile_id, provider, is_active, deleted_at);

CREATE TABLE IF NOT EXISTS audit_events (
    id              TEXT PRIMARY KEY,
    user_id         TEXT DEFAULT NULL,
    event_type      TEXT NOT NULL,
    target_type     TEXT DEFAULT NULL,
    target_id       TEXT DEFAULT NULL,
    summary         TEXT DEFAULT '',
    metadata        TEXT DEFAULT '{}',
    ip_address      TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version         TEXT PRIMARY KEY,
    description     TEXT DEFAULT '',
    applied_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_profiles (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    slug            TEXT NOT NULL,
    display_name    TEXT NOT NULL DEFAULT '',
    tagline         TEXT DEFAULT '',
    role            TEXT DEFAULT '',
    model_provider  TEXT DEFAULT '',
    model_name      TEXT DEFAULT '',
    is_native       INTEGER NOT NULL DEFAULT 0,
    avatar_url      TEXT DEFAULT NULL,
    status          TEXT NOT NULL DEFAULT 'available',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces (id),
    UNIQUE (workspace_id, slug, deleted_at)
);

CREATE INDEX IF NOT EXISTS idx_agent_profiles_workspace
    ON agent_profiles(workspace_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_agent_profiles_slug
    ON agent_profiles(slug)
    WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS rooms (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    agent_profile_id TEXT DEFAULT NULL,
    name            TEXT NOT NULL,
    slug            TEXT NOT NULL,
    topic           TEXT DEFAULT '',
    room_type       TEXT NOT NULL DEFAULT 'lane',
    platform_ids    TEXT DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'active',
    created_by      TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces (id),
    FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles (id),
    FOREIGN KEY (created_by) REFERENCES users (id),
    UNIQUE (workspace_id, slug, deleted_at)
);

CREATE INDEX IF NOT EXISTS idx_rooms_workspace
    ON rooms(workspace_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_rooms_agent_profile
    ON rooms(agent_profile_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_rooms_type
    ON rooms(room_type, workspace_id)
    WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS room_memberships (
    id              TEXT PRIMARY KEY,
    room_id         TEXT NOT NULL,
    user_id         TEXT DEFAULT NULL,
    agent_profile_id TEXT DEFAULT NULL,
    role            TEXT NOT NULL DEFAULT 'participant',
    status          TEXT NOT NULL DEFAULT 'active',
    joined_at       TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    FOREIGN KEY (room_id) REFERENCES rooms (id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles (id),
    CHECK (
        (user_id IS NOT NULL AND agent_profile_id IS NULL)
        OR (user_id IS NULL AND agent_profile_id IS NOT NULL)
    ),
    UNIQUE (room_id, user_id, agent_profile_id, deleted_at)
);

CREATE INDEX IF NOT EXISTS idx_room_memberships_room
    ON room_memberships(room_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_room_memberships_user
    ON room_memberships(user_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_room_memberships_agent
    ON room_memberships(agent_profile_id)
    WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    room_id         TEXT NOT NULL,
    sender_user_id  TEXT DEFAULT NULL,
    sender_agent_id TEXT DEFAULT NULL,
    parent_message_id TEXT DEFAULT NULL,
    content         TEXT NOT NULL DEFAULT '',
    content_type    TEXT NOT NULL DEFAULT 'text',
    metadata        TEXT DEFAULT '{}',
    is_edited       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    FOREIGN KEY (room_id) REFERENCES rooms (id),
    FOREIGN KEY (sender_user_id) REFERENCES users (id),
    FOREIGN KEY (sender_agent_id) REFERENCES agent_profiles (id),
    FOREIGN KEY (parent_message_id) REFERENCES messages (id),
    CHECK (
        (sender_user_id IS NOT NULL AND sender_agent_id IS NULL)
        OR (sender_user_id IS NULL AND sender_agent_id IS NOT NULL)
        OR (sender_user_id IS NULL AND sender_agent_id IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_messages_room_created
    ON messages(room_id, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_memberships_workspace_user_active
    ON workspace_memberships(workspace_id, user_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_workspace_memberships_user_active
    ON workspace_memberships(user_id, deleted_at, status);

CREATE INDEX IF NOT EXISTS idx_workspace_memberships_workspace_active
    ON workspace_memberships(workspace_id, deleted_at, status);

CREATE INDEX IF NOT EXISTS idx_workspace_memberships_workspace_role
    ON workspace_memberships(workspace_id, role)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_workspaces_active
    ON workspaces(deleted_at, status);

INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
VALUES ('1', 'workframe-api runtime schema for /api/me', datetime('now'));
INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
VALUES ('2', 'runtime schema with credential_bindings for credential resolution', datetime('now'));
INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
VALUES ('3', 'runtime schema with agent_profiles, rooms, room_memberships, and messages', datetime('now'));
INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
VALUES ('4', 'agent_runs tracking table with trigger, prompt, result, and cost fields', datetime('now'));

CREATE TABLE IF NOT EXISTS room_sessions (
    id              TEXT PRIMARY KEY,
    room_id         TEXT NOT NULL,
    agent_profile_id TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    gateway_session_id TEXT NOT NULL,
    title           TEXT DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'active',
    forked_from     TEXT DEFAULT NULL,
    created_by      TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    FOREIGN KEY (room_id) REFERENCES rooms (id),
    FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles (id)
);

CREATE INDEX IF NOT EXISTS idx_room_sessions_room
    ON room_sessions(room_id, agent_profile_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_room_sessions_status
    ON room_sessions(room_id, status)
    WHERE deleted_at IS NULL;

INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
VALUES ('5', 'room_sessions table for forkable Hermes sessions per room+agent', datetime('now'));
"""


def _workframe_db_path() -> Path:
    return AUTH_DB_PATH.parent / "workframe.db"


def _workframe_db() -> sqlite3.Connection:
    """Open the Workframe domain DB. Tables are ensured by schema migrations."""
    db_path = _workframe_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _user_payload(row: sqlite3.Row) -> dict[str, Any]:
    payload = {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "avatar_url": row["avatar_url"],
        "role": row["role"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    keys = set(row.keys())
    if "current_workspace_id" in keys:
        payload["current_workspace_id"] = row["current_workspace_id"]
    if "platform_ids" in keys:
        raw = row["platform_ids"] or "{}"
        try:
            platform_ids = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, json.JSONDecodeError):
            platform_ids = {}
        payload["platform_ids"] = platform_ids if isinstance(platform_ids, dict) else {}
    return payload


def _workspace_event_revision(conn: sqlite3.Connection, workspace_id: str) -> str:
    row = conn.execute(
        """
        SELECT
            COALESCE((SELECT MAX(updated_at) FROM rooms WHERE workspace_id = ? AND deleted_at IS NULL), '0') AS rooms_max,
            COALESCE((SELECT MAX(updated_at) FROM workspace_memberships WHERE workspace_id = ? AND deleted_at IS NULL), '0') AS workspace_memberships_max,
            COALESCE((SELECT MAX(rm.updated_at)
                      FROM room_memberships rm
                      JOIN rooms r ON r.id = rm.room_id
                      WHERE r.workspace_id = ? AND r.deleted_at IS NULL AND rm.deleted_at IS NULL), '0') AS room_memberships_max,
            COALESCE((SELECT MAX(m.updated_at)
                      FROM messages m
                      JOIN rooms r ON r.id = m.room_id
                      WHERE r.workspace_id = ? AND r.deleted_at IS NULL AND m.deleted_at IS NULL), '0') AS messages_max
        """,
        (workspace_id, workspace_id, workspace_id, workspace_id),
    ).fetchone()
    if not row:
        return '0:0:0:0'
    return f"{row['rooms_max']}:{row['workspace_memberships_max']}:{row['room_memberships_max']}:{row['messages_max']}"


def _workspace_sse_revision(conn: sqlite3.Connection, workspace_id: str) -> str:
    db_rev = _workspace_event_revision(conn, workspace_id)
    files_rev = str(workspace_state().get("revision") or "")
    return f"{db_rev}|{files_rev}"


def _workspace_event_payload(workspace_id: str, revision: str) -> dict[str, Any]:
    return {
        "type": "workspace.changed",
        "workspace_id": workspace_id,
        "revision": revision,
        "files_revision": str(workspace_state().get("revision") or ""),
        "ts": int(time.time()),
    }


def _bump_workspace_event_state() -> None:
    with _workspace_event_lock:
        _workspace_event_state["version"] += 1


def _workspace_event_version() -> int:
    with _workspace_event_lock:
        return _workspace_event_state["version"]


def _room_live_subscribe(room_id: str) -> queue.SimpleQueue[str]:
    q: queue.SimpleQueue[str] = queue.SimpleQueue()
    with _room_live_lock:
        _room_live_queues.setdefault(room_id, []).append(q)
    return q


def _room_live_unsubscribe(room_id: str, q: queue.SimpleQueue[str]) -> None:
    with _room_live_lock:
        subs = _room_live_queues.get(room_id, [])
        if q in subs:
            subs.remove(q)
        if not subs:
            _room_live_queues.pop(room_id, None)


def _room_live_publish(room_id: str, event: dict[str, Any]) -> None:
    line = json.dumps(event)
    with _room_live_lock:
        subs = list(_room_live_queues.get(room_id, []))
    for sub in subs:
        try:
            sub.put(line)
        except Exception:  # noqa: BLE001
            pass


def _room_live_set_turn(turn: dict[str, Any]) -> None:
    with _room_live_lock:
        _room_live_turns[str(turn["turn_id"])] = turn


def _room_live_clear_turn(turn_id: str) -> None:
    with _room_live_lock:
        _room_live_turns.pop(str(turn_id), None)


def _room_live_active_for_room(room_id: str) -> list[dict[str, Any]]:
    with _room_live_lock:
        return [dict(turn) for turn in _room_live_turns.values() if str(turn.get("room_id") or "") == room_id]


def _display_name_from_email(email: str) -> str:
    normalized = str(email or "").strip().lower()
    if not normalized or "@" not in normalized:
        return ""
    local_part = normalized.split("@", 1)[0]
    words = [part for part in re.split(r"[._\-\s]+", local_part) if part]
    if not words:
        return ""
    return " ".join(word[:1].upper() + word[1:] for word in words)


def _workspace_membership_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "workspace_slug": row["slug"],
        "workspace_display_name": row["display_name"],
        "role": row["role"],
        "status": row["status"],
        "created_at": row["membership_created_at"],
        "updated_at": row["membership_updated_at"],
    }


def _room_payload(row: sqlite3.Row) -> dict[str, Any]:
    """Return the API-safe payload for a room row."""
    platform_ids_raw = row["platform_ids"] or "{}"
    try:
        platform_ids = json.loads(platform_ids_raw) if isinstance(platform_ids_raw, str) else platform_ids_raw
    except (TypeError, json.JSONDecodeError):
        platform_ids = {}
    if not isinstance(platform_ids, dict):
        platform_ids = {}
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "agent_profile_id": row["agent_profile_id"],
        "name": row["name"],
        "slug": row["slug"],
        "topic": row["topic"] or "",
        "avatar_url": row["avatar_url"] if "avatar_url" in row.keys() else None,
        "room_type": row["room_type"],
        "platform_ids": platform_ids,
        "status": row["status"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _sanitize_space_room_agent_fields(room: dict[str, Any]) -> None:
    """Spaces never bind a single agent on the room row — agents live in memberships."""
    if str(room.get("room_type") or "") in {"channel", "group"}:
        room["agent_profile_id"] = None
        room["hermes_profile"] = None


def _workspace_payload(row: sqlite3.Row, *, viewer_role: str = "") -> dict[str, Any]:
    keys = row.keys()
    settings = _parse_workspace_settings(row)
    payload: dict[str, Any] = {
        "id": row["id"],
        "slug": row["slug"],
        "display_name": row["display_name"] or "",
        "description": row["description"] if "description" in keys else "",
        "avatar_url": row["avatar_url"] if "avatar_url" in keys else None,
        "status": row["status"],
        "owner_id": row["owner_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    gh = settings.get("github_oauth") if isinstance(settings.get("github_oauth"), dict) else {}
    stack_gh = _github_oauth_app_config("")
    integrations: dict[str, Any] = {
        "github_oauth_configured": _github_oauth_configured(str(row["id"]))
        or bool(stack_gh.get("client_id") and stack_gh.get("client_secret")),
    }
    if viewer_role in OWNER_ADMIN_ROLES:
        integrations["github_oauth_client_id"] = str(gh.get("client_id") or stack_gh.get("client_id") or "")
        integrations["github_oauth_has_secret"] = bool(
            str(gh.get("client_secret") or "").strip()
            or (not gh and stack_gh.get("client_secret"))
        )
        integrations["messaging"] = _workspace_messaging_integrations_payload(str(row["id"]), settings)
    payload["integrations"] = integrations
    payload["credential_mode"] = str(settings.get("credential_mode") or "byok").strip() or "byok"
    payload["tagline"] = str(settings.get("tagline") or "")
    if viewer_role in OWNER_ADMIN_ROLES:
        payload["admin_onboarding_done"] = bool(settings.get("admin_onboarding_done"))
    return payload


def _normalize_room_slug(value: str, fallback: str = "") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower())
    slug = slug.strip("-")
    if not slug:
        slug = f"room-{fallback[:8]}" if fallback else "room"
    if len(slug) > 64:
        slug = slug[:64].rstrip("-") or "room"
    return slug


def _parse_room_platform_ids(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("platform_ids must be a JSON object") from exc
        if not isinstance(parsed, dict):
            raise ValueError("platform_ids must be a JSON object")
        return parsed
    raise ValueError("platform_ids must be an object")


def _resolve_wid(workspace_id_or_slug: str) -> str | None:
    """Resolve a workspace identifier (UUID or slug) to its UUID.
    
    Returns the UUID string if found, or None if the workspace doesn't exist.
    Opens and closes its own DB connection — use once per request, or pass
    the resolved UUID downstream.
    """
    val = str(workspace_id_or_slug or "").strip()
    if not val:
        return None
    try:
        conn = _workframe_db()
        row = conn.execute(
            "SELECT id FROM workspaces WHERE (id = ? OR slug = ?) AND deleted_at IS NULL",
            (val, val),
        ).fetchone()
        conn.close()
        return str(row["id"]) if row else None
    except Exception:
        return None


def _workspace_exists(conn: sqlite3.Connection, workspace_id: str) -> bool:
    row = conn.execute(
        "SELECT id FROM workspaces WHERE id = ? AND deleted_at IS NULL",
        (workspace_id,),
    ).fetchone()
    return row is not None


def _workspace_member_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "membership_id": row["membership_id"],
        "workspace_id": row["workspace_id"],
        "user_id": row["user_id"],
        "email": row["email"],
        "display_name": row["display_name"] or "",
        "avatar_url": row["avatar_url"],
        "role": row["role"],
        "status": row["status"],
        "invited_by": row["invited_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _workspace_member_lookup_sql() -> str:
    return """
        SELECT
            wm.membership_id,
            wm.workspace_id,
            wm.user_id,
            wm.role,
            wm.status,
            wm.invited_by,
            wm.created_at,
            wm.updated_at,
            wm.email,
            wm.display_name,
            wm.avatar_url
        FROM (
            SELECT
                wm.id AS membership_id,
                wm.workspace_id,
                wm.user_id,
                wm.role,
                wm.status,
                wm.invited_by,
                wm.created_at,
                wm.updated_at,
                u.email,
                u.display_name,
                u.avatar_url,
                ROW_NUMBER() OVER (
                    PARTITION BY wm.workspace_id, wm.user_id
                    ORDER BY wm.created_at ASC, wm.id ASC
                ) AS membership_rank
            FROM workspace_memberships wm
            LEFT JOIN users u ON u.id = wm.user_id
            WHERE wm.workspace_id = ?
              AND wm.deleted_at IS NULL
        ) wm
        WHERE wm.membership_rank = 1
    """


def _workspace_member_role(
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
        """,
        (workspace_id, user_id),
    ).fetchone()
    return str(row["role"]) if row else None


_ONBOARDING_PROGRESS_KEYS = frozenset({
    "admin_integrations_done",
    "admin_onboarding_done",
    "credential_mode",
})


def _resolve_workspace_integrations_role(
    conn: sqlite3.Connection,
    workspace_id: str,
    user_id: str,
    body: dict[str, Any],
) -> str | None:
    """Owner/admin for integrations; repair stale membership during install onboarding."""
    role = _workspace_member_role(conn, workspace_id, user_id)
    row = conn.execute(
        "SELECT owner_id FROM workspaces WHERE id = ? AND deleted_at IS NULL",
        (workspace_id,),
    ).fetchone()
    owner_id = str(row["owner_id"] or "").strip() if row else ""
    now = str(int(time.time()))

    if owner_id and owner_id == user_id and role not in OWNER_ADMIN_ROLES:
        mem = conn.execute(
            "SELECT id FROM workspace_memberships WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL",
            (workspace_id, user_id),
        ).fetchone()
        if mem:
            conn.execute(
                "UPDATE workspace_memberships SET role = 'owner', updated_at = ? WHERE id = ?",
                (now, mem["id"]),
            )
        role = "owner"
    elif not owner_id and _install_window_open():
        if _promote_workspace_owner_if_unclaimed(conn, workspace_id, user_id):
            role = _workspace_member_role(conn, workspace_id, user_id)

    if role in OWNER_ADMIN_ROLES:
        return role
    if (
        role
        and _install_window_open()
        and set(body.keys()) <= _ONBOARDING_PROGRESS_KEYS
    ):
        return role
    return role


def _can_read_workspace_members(
    handler: BaseHTTPRequestHandler,
    conn: sqlite3.Connection,
    workspace_id: str,
) -> bool:
    if not SECURE_MODE:
        return True
    if _role_allows(handler, OWNER_ADMIN_ROLES):
        return True
    user_id = str(getattr(handler, "auth_user", "") or "")
    return _workspace_member_role(conn, workspace_id, user_id) is not None


def _can_manage_workspace_members(
    handler: BaseHTTPRequestHandler,
    conn: sqlite3.Connection,
    workspace_id: str,
) -> bool:
    if not SECURE_MODE:
        return True
    if _role_allows(handler, OWNER_ADMIN_ROLES):
        return True
    user_id = str(getattr(handler, "auth_user", "") or "")
    return _workspace_member_role(conn, workspace_id, user_id) in OWNER_ADMIN_ROLES


def _list_workspace_members(
    workspace_id: str,
    handler: BaseHTTPRequestHandler | None = None,
) -> tuple[int, dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return 400, {"ok": False, "error": "workspace_id required"}
    try:
        conn = _workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        if not _workspace_exists(conn, workspace_id):
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        if handler is not None and not _can_read_workspace_members(handler, conn, workspace_id):
            return 403, {"ok": False, "error": "forbidden", "required_role": "workspace_member_or_owner_or_admin"}
        rows = conn.execute(
            f"{_workspace_member_lookup_sql()} ORDER BY COALESCE(wm.display_name, wm.email, wm.user_id) ASC, wm.created_at ASC",
            (workspace_id,),
        ).fetchall()
        members: list[dict[str, Any]] = []
        for row in rows:
            payload = _workspace_member_payload(row)
            prof = _zk.get_profile(str(row["user_id"]))
            if isinstance(prof, dict):
                if prof.get("tagline"):
                    payload["tagline"] = str(prof["tagline"])
                zk_avatar = str(prof.get("avatar_url") or "").strip()
                if zk_avatar:
                    payload["avatar_url"] = _normalize_user_avatar_url(zk_avatar)
            members.append(payload)
        return 200, {
            "ok": True,
            "workspace_id": workspace_id,
            "members": members,
        }
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workspace_member_list_failed: {exc}"}
    finally:
        conn.close()


def _active_owner_count(conn: sqlite3.Connection, workspace_id: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM workspace_memberships
        WHERE workspace_id = ?
          AND deleted_at IS NULL
          AND status = 'active'
          AND role = 'owner'
        """,
        (workspace_id,),
    ).fetchone()
    return int(row["c"] if row else 0)


def _workspace_membership_update_payload(
    conn: sqlite3.Connection,
    workspace_id: str,
    user_id: str,
    updates: dict[str, Any],
    actor_user_id: str,
) -> tuple[int, dict[str, Any]]:
    membership_id = str(updates.get("membership_id", "") or "").strip()
    if membership_id:
        row = conn.execute(
            f"{_workspace_member_lookup_sql()} AND wm.membership_id = ?",
            (workspace_id, membership_id),
        ).fetchone()
    else:
        row = conn.execute(
            f"{_workspace_member_lookup_sql()} AND wm.user_id = ?",
            (workspace_id, user_id),
        ).fetchone()
    if not row:
        return 404, {"ok": False, "error": "member_not_found", "workspace_id": workspace_id, "user_id": user_id}

    role = str(row["role"])
    status = str(row["status"])
    if "role" in updates:
        role = str(updates.get("role", "") or "").strip()
        if role not in WORKSPACE_MEMBER_ROLES:
            return 400, {"ok": False, "error": "invalid_role", "allowed": sorted(WORKSPACE_MEMBER_ROLES)}
    if "status" in updates:
        status = str(updates.get("status", "") or "").strip()
        if status not in WORKSPACE_MEMBER_STATUSES:
            return 400, {"ok": False, "error": "invalid_status", "allowed": sorted(WORKSPACE_MEMBER_STATUSES)}
    if bool(updates.get("remove", False)) or bool(updates.get("delete", False)):
        status = "removed"

    if role == "owner" and status == "active":
        owners = _active_owner_count(conn, workspace_id)
        existing_role = str(row["role"])
        existing_status = str(row["status"])
        if existing_role != "owner" or existing_status != "active":
            owners += 1
    else:
        owners = _active_owner_count(conn, workspace_id)
        existing_role = str(row["role"])
        existing_status = str(row["status"])
        if existing_role == "owner" and existing_status == "active":
            owners -= 1
    if owners < 1:
        return 409, {"ok": False, "error": "cannot_remove_last_owner", "workspace_id": workspace_id}

    now_ts = str(int(time.time()))
    deleted_at = now_ts if status == "removed" else None
    try:
        conn.execute(
            """
            UPDATE workspace_memberships
            SET role = ?, status = ?, deleted_at = ?, invited_by = COALESCE(invited_by, ?), updated_at = ?
            WHERE id = ?
            """,
            (role, status, deleted_at, actor_user_id or None, now_ts, row["membership_id"]),
        )
    except sqlite3.IntegrityError as exc:
        return 409, {"ok": False, "error": "workspace_membership_update_conflict", "detail": str(exc)}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workspace_membership_update_failed: {exc}"}

    updated = conn.execute(
        """
        SELECT
            wm.id AS membership_id,
            wm.workspace_id,
            wm.user_id,
            wm.role,
            wm.status,
            wm.invited_by,
            wm.created_at,
            wm.updated_at,
            u.email,
            u.display_name,
            u.avatar_url
        FROM workspace_memberships wm
        LEFT JOIN users u ON u.id = wm.user_id
        WHERE wm.workspace_id = ? AND wm.id = ?
        """,
        (workspace_id, row["membership_id"]),
    ).fetchone()
    if not updated:
        return 404, {"ok": False, "error": "member_not_found", "workspace_id": workspace_id, "user_id": user_id}
    return 200, {"ok": True, "membership": _workspace_member_payload(updated)}


def _patch_workspace_members(
    workspace_id: str,
    body: dict[str, Any],
    handler: BaseHTTPRequestHandler,
) -> tuple[int, dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return 400, {"ok": False, "error": "workspace_id required"}
    if not isinstance(body, dict):
        body = {}

    bulk = body.get("memberships")
    if bulk is None:
        bulk = body.get("members")
    if bulk is not None and not isinstance(bulk, list):
        return 400, {"ok": False, "error": "memberships must be a list"}

    try:
        conn = _workframe_db()
        actor_user_id = getattr(handler, "auth_user", "")
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        if not _workspace_exists(conn, workspace_id):
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        if not _can_manage_workspace_members(handler, conn, workspace_id):
            return 403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"}

        if isinstance(bulk, list):
            if not bulk:
                return 400, {"ok": False, "error": "memberships list cannot be empty"}
            results = []
            for item in bulk:
                if not isinstance(item, dict):
                    return 400, {"ok": False, "error": "each membership update must be an object"}
                user_id = str(item.get("user_id", "") or "").strip()
                if not user_id and not str(item.get("membership_id", "") or "").strip():
                    return 400, {"ok": False, "error": "user_id or membership_id required"}
                status, payload = _workspace_membership_update_payload(conn, workspace_id, user_id, item, actor_user_id)
                if status != 200:
                    return status, payload
                results.append(payload["membership"])
            conn.commit()
            return 200, {"ok": True, "workspace_id": workspace_id, "memberships": results}

        user_id = str(body.get("user_id", "") or "").strip()
        membership_id = str(body.get("membership_id", "") or "").strip()
        if not user_id and not membership_id:
            return 400, {"ok": False, "error": "user_id or membership_id required"}
        update_body = dict(body)
        if membership_id:
            update_body["membership_id"] = membership_id
        status, payload = _workspace_membership_update_payload(conn, workspace_id, user_id, update_body, actor_user_id)
        if status == 200:
            conn.commit()
        return status, payload
    except sqlite3.Error as exc:
        conn.rollback()
        return 500, {"ok": False, "error": f"workspace_member_patch_failed: {exc}"}
    finally:
        conn.close()


_AGENT_PROFILE_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _lookup_agent_profile(
    conn: sqlite3.Connection,
    workspace_id: str,
    ref: str,
) -> sqlite3.Row | None:
    """Resolve workspace agent_profiles row by canonical id or Hermes slug."""
    ref = str(ref or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if not ref or not workspace_id:
        return None
    if _AGENT_PROFILE_UUID_RE.match(ref):
        return conn.execute(
            """
            SELECT id, workspace_id, slug, display_name, role, tagline, is_native, status
            FROM agent_profiles
            WHERE id = ? AND workspace_id = ? AND deleted_at IS NULL
            """,
            (ref, workspace_id),
        ).fetchone()
    return conn.execute(
        """
        SELECT id, workspace_id, slug, display_name, role, tagline, is_native, status
        FROM agent_profiles
        WHERE slug = ? AND workspace_id = ? AND deleted_at IS NULL
        """,
        (ref, workspace_id),
    ).fetchone()


def _hermes_slug_from_agent_ref(ref: str) -> str:
    """Map workspace agent_profiles.id to Hermes profile slug."""
    ref = str(ref or "").strip()
    if not ref or not _AGENT_PROFILE_UUID_RE.match(ref):
        return ref
    try:
        conn = _workframe_db()
        row = conn.execute(
            "SELECT slug FROM agent_profiles WHERE id = ? AND deleted_at IS NULL LIMIT 1",
            (ref,),
        ).fetchone()
        conn.close()
        return str(row["slug"]) if row else ""
    except Exception:
        return ""


def _enrich_rooms_hermes_profile(conn: sqlite3.Connection, rooms: list[dict[str, Any]]) -> None:
    ids = {
        str(room["agent_profile_id"])
        for room in rooms
        if room.get("agent_profile_id") and str(room.get("room_type") or "") == "direct"
    }
    by_id: dict[str, str] = {}
    if ids:
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"""
            SELECT id, slug FROM agent_profiles
            WHERE id IN ({placeholders}) AND deleted_at IS NULL
            """,
            tuple(ids),
        ).fetchall()
        by_id = {str(row["id"]): str(row["slug"]) for row in rows}
    for room in rooms:
        ref = str(room.get("agent_profile_id") or "")
        if not ref:
            room["hermes_profile"] = None
        elif ref in by_id:
            room["hermes_profile"] = by_id[ref]
        elif not _AGENT_PROFILE_UUID_RE.match(ref):
            room["hermes_profile"] = ref
        else:
            room["hermes_profile"] = None
    for room in rooms:
        _sanitize_space_room_agent_fields(room)


def _ensure_workspace_agent_profile_row(
    slug: str,
    *,
    workspace_id: str = "",
    display_name: str = "",
    role: str = "",
    tagline: str = "",
    is_native: bool = False,
) -> str | None:
    """Ensure agent_profiles row exists for a workspace (default workspace when id omitted)."""
    slug = str(slug or "").strip()
    if not slug:
        return None
    try:
        conn = _workframe_db()
        ws_id = str(workspace_id or "").strip()
        if ws_id:
            ws = conn.execute(
                "SELECT id FROM workspaces WHERE id = ? AND deleted_at IS NULL",
                (ws_id,),
            ).fetchone()
        else:
            ws = conn.execute(
                """
                SELECT id FROM workspaces
                WHERE deleted_at IS NULL
                ORDER BY CASE WHEN slug = 'default' THEN 0 ELSE 1 END, created_at ASC
                LIMIT 1
                """,
            ).fetchone()
        if not ws:
            conn.close()
            return None
        ws_id = str(ws["id"])
        existing = conn.execute(
            """
            SELECT id FROM agent_profiles
            WHERE workspace_id = ? AND slug = ? AND deleted_at IS NULL
            """,
            (ws_id, slug),
        ).fetchone()
        if existing:
            agent_id = str(existing["id"])
            patches: dict[str, Any] = {}
            if display_name.strip():
                patches["display_name"] = display_name.strip()
            if tagline.strip():
                patches["tagline"] = tagline.strip()
            if role.strip():
                patches["role"] = role.strip()
            if patches:
                sets = [f"{col} = ?" for col in patches]
                vals = list(patches.values()) + [str(int(time.time())), ws_id, slug]
                conn.execute(
                    f"UPDATE agent_profiles SET {', '.join(sets)}, updated_at = ? WHERE workspace_id = ? AND slug = ? AND deleted_at IS NULL",
                    vals,
                )
            _add_workspace_agents_to_space_rooms(conn, ws_id, agent_id)
            conn.commit()
            conn.close()
            return agent_id
        agent_id = str(uuid.uuid4())
        now = str(int(time.time()))
        reg = _agent_registry_row(slug)
        avatar_url = str(reg.get("avatar_url") or "").strip() or None
        if not avatar_url and not reg.get("avatar_id"):
            try:
                picked = _assign_agent_avatar(slug)
                avatar_url = picked.get("avatar_url")
            except Exception:
                avatar_url = None
        conn.execute(
            """
            INSERT INTO agent_profiles (
                id, workspace_id, slug, display_name, tagline, role, avatar_url,
                is_native, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'available', ?, ?)
            """,
            (
                agent_id,
                ws_id,
                slug,
                display_name.strip() or slug,
                tagline.strip(),
                role.strip(),
                avatar_url,
                1 if is_native else 0,
                now,
                now,
            ),
        )
        conn.commit()
        _add_workspace_agents_to_space_rooms(conn, ws_id, agent_id)
        conn.close()
        return agent_id
    except Exception:
        return None


def _room_api_payload(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    room = _room_payload(row)
    _enrich_rooms_hermes_profile(conn, [room])
    return room


def _agent_profile_belongs(conn: sqlite3.Connection, agent_profile_id: str, workspace_id: str) -> bool:
    return _lookup_agent_profile(conn, workspace_id, agent_profile_id) is not None


def _room_slug_available(conn: sqlite3.Connection, workspace_id: str, slug: str, room_id: str = "") -> bool:
    row = conn.execute(
        """
        SELECT id FROM rooms
        WHERE workspace_id = ? AND slug = ? AND deleted_at IS NULL
        """,
        (workspace_id, slug),
    ).fetchone()
    return row is None or (room_id and row["id"] == room_id)


def _list_rooms(workspace_id: str, *, include_members: bool = False) -> tuple[int, dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return 400, {"ok": False, "error": "workspace_id required"}
    try:
        conn = _workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        if not _workspace_exists(conn, workspace_id):
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        rows = conn.execute(
            """
            SELECT id, workspace_id, agent_profile_id, name, slug, topic, avatar_url, room_type,
                   platform_ids, status, created_by, created_at, updated_at
            FROM rooms
            WHERE workspace_id = ? AND deleted_at IS NULL
            ORDER BY created_at ASC, name ASC
            """,
            (workspace_id,),
        ).fetchall()
        rooms = [_room_payload(row) for row in rows]
        _enrich_rooms_hermes_profile(conn, rooms)
        if include_members and rooms:
            room_ids = [str(room["id"]) for room in rooms]
            placeholders = ",".join("?" * len(room_ids))
            member_rows = conn.execute(
                f"""
                SELECT room_id, user_id
                FROM room_memberships
                WHERE deleted_at IS NULL AND room_id IN ({placeholders})
                """,
                room_ids,
            ).fetchall()
            members_by_room: dict[str, list[str]] = {}
            for member_row in member_rows:
                members_by_room.setdefault(str(member_row["room_id"]), []).append(str(member_row["user_id"]))
            for room in rooms:
                room["member_user_ids"] = members_by_room.get(str(room["id"]), [])
        return 200, {"ok": True, "workspace_id": workspace_id, "rooms": rooms}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"room_list_failed: {exc}"}
    finally:
        conn.close()


def _patch_room(room_id: str, body: dict[str, Any], user_id: str) -> tuple[int, dict[str, Any]]:
    room_id = str(room_id or "").strip()
    user_id = str(user_id or "").strip()
    if not room_id:
        return 400, {"ok": False, "error": "room_id required"}
    if not user_id:
        return 401, {"ok": False, "error": "no_session"}
    allowed = {"name", "topic", "avatar_url"}
    updates = {key: str(body[key]).strip() for key in allowed if key in body}
    if not updates:
        return 400, {"ok": False, "error": "no_allowed_fields", "allowed": list(allowed)}
    if "avatar_url" in updates:
        _validate_me_profile_updates({"avatar_url": updates["avatar_url"]})
        updates["avatar_url"] = _normalize_logo_url(updates["avatar_url"])
    if "name" in updates and not updates["name"]:
        return 400, {"ok": False, "error": "name required"}
    try:
        conn = _workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        row = conn.execute(
            "SELECT id, workspace_id FROM rooms WHERE id = ? AND deleted_at IS NULL",
            (room_id,),
        ).fetchone()
        if not row:
            return 404, {"ok": False, "error": "room_not_found", "room_id": room_id}
        if not _user_can_access_room(conn, room_id, user_id):
            return 403, {"ok": False, "error": "forbidden"}
        workspace_id = str(row["workspace_id"])
        member = conn.execute(
            """
            SELECT role FROM workspace_memberships
            WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL AND status = 'active'
            """,
            (workspace_id, user_id),
        ).fetchone()
        if not member or str(member["role"]) not in {"owner", "admin"}:
            return 403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"}
        sets = [f"{key} = ?" for key in updates]
        vals = list(updates.values())
        now_ts = str(int(time.time()))
        sets.extend(["updated_at = ?"])
        vals.extend([now_ts, room_id])
        conn.execute(f"UPDATE rooms SET {', '.join(sets)} WHERE id = ?", vals)
        conn.commit()
        updated = conn.execute(
            """
            SELECT id, workspace_id, agent_profile_id, name, slug, topic, avatar_url, room_type,
                   platform_ids, status, created_by, created_at, updated_at
            FROM rooms WHERE id = ?
            """,
            (room_id,),
        ).fetchone()
        if not updated:
            return 500, {"ok": False, "error": "room_lookup_failed"}
        return 200, {"ok": True, "room": _room_api_payload(conn, updated)}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"room_update_failed: {exc}"}
    finally:
        conn.close()


def _get_workspace(workspace_id: str, user_id: str) -> tuple[int, dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not workspace_id:
        return 400, {"ok": False, "error": "workspace_id required"}
    if not user_id:
        return 401, {"ok": False, "error": "no_session"}
    try:
        conn = _workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        if not _workspace_exists(conn, workspace_id):
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        if _workspace_member_role(conn, workspace_id, user_id) is None:
            return 403, {"ok": False, "error": "forbidden"}
        role = _workspace_member_role(conn, workspace_id, user_id) or ""
        row = conn.execute(
            "SELECT * FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        if not row:
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        return 200, {"ok": True, "workspace": _workspace_payload(row, viewer_role=role)}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workspace_lookup_failed: {exc}"}
    finally:
        conn.close()


def _patch_workspace(workspace_id: str, body: dict[str, Any], user_id: str) -> tuple[int, dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not workspace_id:
        return 400, {"ok": False, "error": "workspace_id required"}
    if not user_id:
        return 401, {"ok": False, "error": "no_session"}
    allowed = {"display_name", "description", "avatar_url", "tagline"}
    updates = {key: str(body[key]).strip() for key in ("display_name", "description", "avatar_url") if key in body}
    tagline = str(body.get("tagline") or "").strip() if "tagline" in body else None
    if not updates and tagline is None:
        return 400, {"ok": False, "error": "no_allowed_fields", "allowed": list(allowed)}
    if "avatar_url" in updates:
        _validate_me_profile_updates({"avatar_url": updates["avatar_url"]})
        updates["avatar_url"] = _normalize_logo_url(updates["avatar_url"])
    if "display_name" in updates and not updates["display_name"]:
        return 400, {"ok": False, "error": "display_name required"}
    try:
        conn = _workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        if not _workspace_exists(conn, workspace_id):
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        member = conn.execute(
            """
            SELECT role FROM workspace_memberships
            WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL AND status = 'active'
            """,
            (workspace_id, user_id),
        ).fetchone()
        if not member or str(member["role"]) not in OWNER_ADMIN_ROLES:
            return 403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"}
        row = conn.execute(
            "SELECT * FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        if not row:
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        sets = [f"{key} = ?" for key in updates]
        vals = list(updates.values())
        now_ts = str(int(time.time()))
        if tagline is not None:
            settings = _parse_workspace_settings(row)
            settings["tagline"] = tagline
            sets.append("settings_json = ?")
            vals.append(json.dumps(settings, sort_keys=True))
        sets.append("updated_at = ?")
        vals.extend([now_ts, workspace_id])
        conn.execute(f"UPDATE workspaces SET {', '.join(sets)} WHERE id = ?", vals)
        _sync_workspace_home_room(conn, workspace_id)
        conn.commit()
        row = conn.execute(
            "SELECT * FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        if not row:
            return 500, {"ok": False, "error": "workspace_lookup_failed"}
        return 200, {"ok": True, "workspace": _workspace_payload(row, viewer_role=str(member["role"]))}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workspace_update_failed: {exc}"}
    finally:
        conn.close()


def _patch_workspace_integrations(
    workspace_id: str,
    body: dict[str, Any],
    user_id: str,
) -> tuple[int, dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not workspace_id or not user_id:
        return 401, {"ok": False, "error": "no_session"}
    try:
        conn = _workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        if not _workspace_exists(conn, workspace_id):
            return 404, {"ok": False, "error": "workspace_not_found"}
        role = _resolve_workspace_integrations_role(conn, workspace_id, user_id, body)
        if role not in OWNER_ADMIN_ROLES and not (
            role and _install_window_open() and set(body.keys()) <= _ONBOARDING_PROGRESS_KEYS
        ):
            return 403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"}
        row = conn.execute(
            "SELECT * FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        if not row:
            return 404, {"ok": False, "error": "workspace_not_found"}
        settings = _parse_workspace_settings(row)
        gh = settings.get("github_oauth") if isinstance(settings.get("github_oauth"), dict) else {}
        if "github_oauth_client_id" in body:
            gh["client_id"] = str(body.get("github_oauth_client_id") or "").strip()
        if "github_oauth_client_secret" in body:
            secret = str(body.get("github_oauth_client_secret") or "").strip()
            if secret:
                gh["client_secret"] = secret
        if gh:
            settings["github_oauth"] = gh
        if "credential_mode" in body:
            mode = str(body.get("credential_mode") or "byok").strip().lower()
            if mode not in {"byok", "workspace"}:
                return 400, {"ok": False, "error": "invalid_credential_mode"}
            settings["credential_mode"] = mode
        if body.get("admin_onboarding_done") is True:
            settings["admin_onboarding_done"] = True
        if body.get("admin_integrations_done") is True:
            settings["admin_integrations_done"] = True
        settings = _parse_messaging_settings_patch(body, settings)
        now_ts = str(int(time.time()))
        conn.execute(
            "UPDATE workspaces SET settings_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(settings, sort_keys=True), now_ts, workspace_id),
        )
        conn.commit()
        if "messaging" in body:
            sync_result = _sync_workspace_messaging_gateway(workspace_id)
            if not sync_result.get("ok"):
                return 500, {"ok": False, "error": sync_result.get("error") or "messaging_sync_failed"}
        updated = conn.execute(
            "SELECT * FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        if not updated:
            return 500, {"ok": False, "error": "workspace_lookup_failed"}
        return 200, {"ok": True, "workspace": _workspace_payload(updated, viewer_role=role or "")}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workspace_integrations_update_failed: {exc}"}
    finally:
        conn.close()


def _get_room(room_id: str) -> tuple[int, dict[str, Any]]:
    room_id = str(room_id or "").strip()
    if not room_id:
        return 400, {"ok": False, "error": "room_id required"}
    try:
        conn = _workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        row = conn.execute(
            """
            SELECT id, workspace_id, agent_profile_id, name, slug, topic, avatar_url, room_type,
                   platform_ids, status, created_by, created_at, updated_at
            FROM rooms
            WHERE id = ? AND deleted_at IS NULL
            """,
            (room_id,),
        ).fetchone()
        if not row:
            return 404, {"ok": False, "error": "room_not_found", "room_id": room_id}
        return 200, {"ok": True, "room": _room_api_payload(conn, row)}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"room_lookup_failed: {exc}"}
    finally:
        conn.close()


def _create_room(workspace_id: str, body: dict[str, Any], created_by: str) -> tuple[int, dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return 400, {"ok": False, "error": "workspace_id required"}
    name = str(body.get("name", "") or "").strip()
    if not name:
        return 400, {"ok": False, "error": "name required"}

    room_type = str(body.get("room_type", "channel") or "channel").strip() or "channel"
    if room_type not in {"lane", "group", "direct", "channel"}:
        return 400, {"ok": False, "error": "invalid_room_type", "allowed": ["lane", "group", "direct", "channel"]}

    topic = str(body.get("topic", "") or "").strip()
    agent_profile_id = str(body.get("agent_profile_id", "") or "").strip() or None
    status = str(body.get("status", "active") or "active").strip() or "active"
    if status not in {"active", "archived", "locked"}:
        return 400, {"ok": False, "error": "invalid_room_status", "allowed": ["active", "archived", "locked"]}

    member_user_ids = body.get("member_user_ids", [])
    if member_user_ids in (None, ""):
        member_user_ids = []
    if not isinstance(member_user_ids, list):
        return 400, {"ok": False, "error": "member_user_ids must be a list"}
    member_user_ids = [str(user_id).strip() for user_id in member_user_ids if str(user_id).strip()]

    try:
        platform_ids = _parse_room_platform_ids(body.get("platform_ids", {}))
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}

    base_slug = _normalize_room_slug(str(body.get("slug", "") or ""), name)
    rid = str(uuid.uuid4())
    now_ts = str(int(time.time()))
    try:
        conn = _workframe_db()
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        if not _workspace_exists(conn, workspace_id):
            return 404, {"ok": False, "error": "workspace_not_found", "workspace_id": workspace_id}
        if agent_profile_id and not _agent_profile_belongs(conn, agent_profile_id, workspace_id):
            return 400, {"ok": False, "error": "agent_profile_not_found", "agent_profile_id": agent_profile_id}
        agent_row = (
            _lookup_agent_profile(conn, workspace_id, agent_profile_id) if agent_profile_id else None
        )
        agent_profile_id = str(agent_row["id"]) if agent_row else agent_profile_id

        direct_member_ids = sorted({user_id for user_id in member_user_ids if user_id})
        if room_type == 'direct':
            existing_row = None
            if agent_profile_id and direct_member_ids:
                existing_row = conn.execute(
                    """
                    SELECT id, workspace_id, agent_profile_id, name, slug, topic, avatar_url, room_type,
                           platform_ids, status, created_by, created_at, updated_at
                    FROM rooms
                    WHERE workspace_id = ?
                      AND room_type = 'direct'
                      AND deleted_at IS NULL
                      AND agent_profile_id = ?
                      AND EXISTS (
                          SELECT 1 FROM room_memberships rm
                          WHERE rm.room_id = rooms.id
                            AND rm.deleted_at IS NULL
                            AND rm.user_id = ?
                      )
                    LIMIT 1
                    """,
                    (workspace_id, agent_profile_id, direct_member_ids[0]),
                ).fetchone()
            elif len(direct_member_ids) == 2:
                left_id, right_id = direct_member_ids
                existing_row = conn.execute(
                    """
                    SELECT id, workspace_id, agent_profile_id, name, slug, topic, avatar_url, room_type,
                           platform_ids, status, created_by, created_at, updated_at
                    FROM rooms
                    WHERE workspace_id = ?
                      AND room_type = 'direct'
                      AND deleted_at IS NULL
                      AND agent_profile_id IS NULL
                      AND EXISTS (
                          SELECT 1 FROM room_memberships rm
                          WHERE rm.room_id = rooms.id
                            AND rm.deleted_at IS NULL
                            AND rm.user_id = ?
                      )
                      AND EXISTS (
                          SELECT 1 FROM room_memberships rm
                          WHERE rm.room_id = rooms.id
                            AND rm.deleted_at IS NULL
                            AND rm.user_id = ?
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM room_memberships rm
                          WHERE rm.room_id = rooms.id
                            AND rm.deleted_at IS NULL
                            AND rm.user_id NOT IN (?, ?)
                      )
                    LIMIT 1
                    """,
                    (workspace_id, left_id, right_id, left_id, right_id),
                ).fetchone()
            if existing_row:
                return 200, {"ok": True, "room": _room_api_payload(conn, existing_row)}

        slug = base_slug
        if room_type == 'direct' and direct_member_ids:
            if agent_profile_id and len(direct_member_ids) == 1:
                slug = _normalize_room_slug(f"dm-{direct_member_ids[0]}-{agent_profile_id}", name)
            elif len(direct_member_ids) == 2:
                slug = _normalize_room_slug(f"dm-{direct_member_ids[0]}-{direct_member_ids[1]}", name)
        for attempt in range(1, 26):
            if _room_slug_available(conn, workspace_id, slug):
                break
            slug = f"{base_slug}-{attempt}"
        else:
            return 409, {"ok": False, "error": "room_slug_conflict", "slug": base_slug}

        platform_json = json.dumps(platform_ids, sort_keys=True)
        explicit_avatar = str(body.get("avatar_url", "") or "").strip()
        if explicit_avatar:
            explicit_avatar = _normalize_logo_url(explicit_avatar)
        room_avatar_url = explicit_avatar or (
            _pick_logo_url() if _is_space_room(room_type, agent_profile_id) else ""
        )
        conn.execute(
            """
            INSERT INTO rooms (
                id, workspace_id, agent_profile_id, name, slug, topic, avatar_url, room_type,
                platform_ids, status, created_by, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rid,
                workspace_id,
                agent_profile_id,
                name,
                slug,
                topic,
                room_avatar_url or None,
                room_type,
                platform_json,
                status,
                created_by or None,
                now_ts,
                now_ts,
            ),
        )
        if created_by:
            _ensure_user_in_room(conn, rid, created_by)
        if member_user_ids:
            seen: set[str] = set()
            for user_id in member_user_ids:
                if user_id in seen:
                    continue
                seen.add(user_id)
                membership_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO room_memberships (id, room_id, user_id, role, status, joined_at, updated_at)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (membership_id, rid, user_id, "member", "active", now_ts, now_ts),
                )
        if _is_space_room(room_type, agent_profile_id):
            agents = conn.execute(
                "SELECT id FROM agent_profiles WHERE workspace_id = ? AND deleted_at IS NULL",
                (workspace_id,),
            ).fetchall()
            for agent in agents:
                _ensure_agent_in_space_room(conn, rid, str(agent["id"]))
            _add_workspace_members_to_space_room(conn, workspace_id, rid)
        elif room_type == "direct" and agent_profile_id and direct_member_ids:
            _provision_agent_dm_runtimes(workspace_id, agent_profile_id, direct_member_ids)
        conn.commit()
        row = conn.execute(
            """
            SELECT id, workspace_id, agent_profile_id, name, slug, topic, avatar_url, room_type,
                   platform_ids, status, created_by, created_at, updated_at
            FROM rooms
            WHERE id = ?
            """,
            (rid,),
        ).fetchone()
        if not row:
            return 500, {"ok": False, "error": "room_create_failed"}
        return 201, {"ok": True, "room": _room_api_payload(conn, row)}
    except sqlite3.IntegrityError as exc:
        return 409, {"ok": False, "error": "room_already_exists", "detail": str(exc)}
    except sqlite3.Error as exc:
        return 500, {"ok": False, "error": f"room_create_failed: {exc}"}
    finally:
        conn.close()


def _default_workspace_room(conn: sqlite3.Connection, workspace_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, slug, name
        FROM rooms
        WHERE workspace_id = ? AND deleted_at IS NULL
        ORDER BY CASE slug WHEN 'general' THEN 0 ELSE 1 END, created_at ASC
        LIMIT 1
        """,
        (workspace_id,),
    ).fetchone()


def _ensure_user_in_room(conn: sqlite3.Connection, room_id: str, user_id: str, role: str = "member") -> bool:
    existing = conn.execute(
        "SELECT id FROM room_memberships WHERE room_id = ? AND user_id = ? AND deleted_at IS NULL",
        (room_id, user_id),
    ).fetchone()
    if existing:
        return False
    now = str(int(time.time()))
    conn.execute(
        """
        INSERT INTO room_memberships (id, room_id, user_id, role, status, joined_at, updated_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        (str(uuid.uuid4()), room_id, user_id, role, "active", now, now),
    )
    return True


def _workspace_credential_mode(conn: sqlite3.Connection | None, workspace_id: str) -> str:
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return "byok"
    own_conn = False
    if conn is None:
        conn = _workframe_db()
        own_conn = True
    try:
        row = conn.execute(
            "SELECT settings_json FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        settings = _parse_workspace_settings(row) if row else {}
        mode = str(settings.get("credential_mode") or "byok").strip().lower()
        return mode if mode in ("byok", "workspace") else "byok"
    finally:
        if own_conn:
            conn.close()


def _user_can_access_room(conn: sqlite3.Connection, room_id: str, user_id: str) -> bool:
    user_id = str(user_id or "").strip()
    if not user_id:
        return False
    row = conn.execute(
        """
        SELECT 1 FROM room_memberships
        WHERE room_id = ? AND user_id = ? AND deleted_at IS NULL AND status = 'active'
        LIMIT 1
        """,
        (room_id, user_id),
    ).fetchone()
    if row is not None:
        return True
    # ponytail: repair pre-fix rooms that never added creator membership
    creator = conn.execute(
        "SELECT created_by FROM rooms WHERE id = ? AND deleted_at IS NULL",
        (room_id,),
    ).fetchone()
    if creator and str(creator["created_by"] or "") == user_id:
        _ensure_user_in_room(conn, room_id, user_id)
        conn.commit()
        return True
    return False


def _user_can_manage_room_members(conn: sqlite3.Connection, room_id: str, user_id: str) -> bool:
    user_id = str(user_id or "").strip()
    if not user_id or not _user_can_access_room(conn, room_id, user_id):
        return False
    row = conn.execute(
        """
        SELECT role FROM room_memberships
        WHERE room_id = ? AND user_id = ? AND deleted_at IS NULL AND status = 'active'
        LIMIT 1
        """,
        (room_id, user_id),
    ).fetchone()
    if row and str(row["role"] or "").strip().lower() in {"admin", "owner"}:
        return True
    room = conn.execute(
        "SELECT workspace_id FROM rooms WHERE id = ? AND deleted_at IS NULL",
        (room_id,),
    ).fetchone()
    if room:
        ws_id = str(room["workspace_id"] or "").strip()
        if ws_id and _workspace_member_role(conn, ws_id, user_id) in OWNER_ADMIN_ROLES:
            return True
    return False


def _get_active_room_session(
    conn: sqlite3.Connection,
    room_id: str,
    agent_profile_id: str = "",
) -> sqlite3.Row | None:
    room_id = str(room_id or "").strip()
    agent_profile_id = str(agent_profile_id or "").strip()
    if not room_id:
        return None
    if agent_profile_id:
        return conn.execute(
            """
            SELECT * FROM room_sessions
            WHERE room_id = ? AND agent_profile_id = ? AND deleted_at IS NULL AND status = 'active'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (room_id, agent_profile_id),
        ).fetchone()
    return conn.execute(
        """
        SELECT * FROM room_sessions
        WHERE room_id = ? AND deleted_at IS NULL AND status = 'active'
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (room_id,),
    ).fetchone()


def _list_room_sessions(
    conn: sqlite3.Connection,
    room_id: str,
    agent_profile_id: str,
) -> list[sqlite3.Row]:
    room_id = str(room_id or "").strip()
    agent_profile_id = str(agent_profile_id or "").strip()
    if not room_id or not agent_profile_id:
        return []
    return conn.execute(
        """
        SELECT * FROM room_sessions
        WHERE room_id = ? AND agent_profile_id = ? AND deleted_at IS NULL
        ORDER BY updated_at DESC, created_at DESC
        """,
        (room_id, agent_profile_id),
    ).fetchall()


def _resolve_latest_room_session(
    conn: sqlite3.Connection,
    profile: str,
    room_id: str,
    agent_profile_id: str,
) -> sqlite3.Row | None:
    """Active room_sessions row for this room+agent whose Hermes session still exists."""
    for row in _list_room_sessions(conn, room_id, agent_profile_id):
        if str(row["status"] or "").strip() != "active":
            continue
        sid = str(row["session_id"] or "").strip()
        if sid and _session_exists(profile, sid):
            return row
    return None


def _archive_room_sessions(
    conn: sqlite3.Connection,
    room_id: str,
    agent_profile_id: str = "",
) -> None:
    now = str(int(time.time()))
    room_id = str(room_id or "").strip()
    agent_profile_id = str(agent_profile_id or "").strip()
    if agent_profile_id:
        conn.execute(
            """
            UPDATE room_sessions
            SET status = 'archived', updated_at = ?
            WHERE room_id = ? AND agent_profile_id = ? AND deleted_at IS NULL AND status = 'active'
            """,
            (now, room_id, agent_profile_id),
        )
        return
    conn.execute(
        """
        UPDATE room_sessions
        SET status = 'archived', updated_at = ?
        WHERE room_id = ? AND deleted_at IS NULL AND status = 'active'
        """,
        (now, room_id),
    )


def _upsert_room_session(
    conn: sqlite3.Connection,
    *,
    room_id: str,
    agent_profile_id: str,
    session_id: str,
    gateway_session_id: str,
    created_by: str,
    title: str = "",
) -> None:
    now = str(int(time.time()))
    room_id = str(room_id or "").strip()
    agent_profile_id = str(agent_profile_id or "").strip()
    session_id = str(session_id or "").strip()
    prior = conn.execute(
        """
        SELECT id, session_id, status FROM room_sessions
        WHERE room_id = ? AND agent_profile_id = ? AND session_id = ? AND deleted_at IS NULL
        LIMIT 1
        """,
        (room_id, agent_profile_id, session_id),
    ).fetchone()
    if prior:
        _archive_room_sessions(conn, room_id, agent_profile_id)
        conn.execute(
            """
            UPDATE room_sessions
            SET status = 'active', gateway_session_id = ?, updated_at = ?,
                title = COALESCE(NULLIF(?, ''), title), created_by = COALESCE(?, created_by)
            WHERE id = ?
            """,
            (gateway_session_id, now, title, created_by or None, prior["id"]),
        )
        return
    _archive_room_sessions(conn, room_id, agent_profile_id)
    conn.execute(
        """
        INSERT INTO room_sessions (
            id, room_id, agent_profile_id, session_id, gateway_session_id,
            title, status, created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            room_id,
            agent_profile_id,
            session_id,
            gateway_session_id,
            title,
            created_by,
            now,
            now,
        ),
    )


def _room_session_context(
    conn: sqlite3.Connection,
    user_id: str,
    room_id: str,
    hermes_slug: str,
) -> tuple[sqlite3.Row, str, str]:
    """Validate access and resolve (room, hermes slug, agent_profiles.id) for session bind."""
    room_id = str(room_id or "").strip()
    user_id = str(user_id or "").strip()
    hermes_slug = str(hermes_slug or "").strip()
    if not room_id:
        raise ValueError("room_id required")
    if not user_id:
        raise ValueError("authenticated user required")
    if not hermes_slug:
        raise ValueError("profile required")
    if not _user_can_access_room(conn, room_id, user_id):
        raise ValueError("room_access_denied")
    room = conn.execute(
        "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
        (room_id,),
    ).fetchone()
    if not room:
        raise ValueError("room_not_found")
    if _is_space_room(str(room["room_type"]), None):
        raise ValueError("room_not_agent_chat")
    workspace_id = str(room["workspace_id"])
    agent_row = _lookup_agent_profile(conn, workspace_id, hermes_slug)
    if not agent_row:
        raise ValueError("agent_profile_not_found")
    agent_db_id = str(agent_row["id"])
    room_agent_ref = str(room["agent_profile_id"] or "").strip()
    if room_agent_ref:
        room_agent = _lookup_agent_profile(conn, workspace_id, room_agent_ref)
        if not room_agent or str(room_agent["id"]) != agent_db_id:
            raise ValueError("profile does not match room agent")
    elif not _is_space_room(str(room["room_type"]), room_agent_ref):
        raise ValueError("room_not_agent_chat")
    return room, hermes_slug, agent_db_id


def _resolve_agent_room_for_user(
    conn: sqlite3.Connection,
    user_id: str,
    room_id: str,
) -> tuple[sqlite3.Row, str, str]:
    """Agent DM rooms only — infer Hermes slug from room.agent_profile_id."""
    room_id = str(room_id or "").strip()
    user_id = str(user_id or "").strip()
    if not room_id:
        raise ValueError("room_id required")
    if not user_id:
        raise ValueError("authenticated user required")
    if not _user_can_access_room(conn, room_id, user_id):
        raise ValueError("room_access_denied")
    room = conn.execute(
        "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
        (room_id,),
    ).fetchone()
    if not room:
        raise ValueError("room_not_found")
    agent_ref = str(room["agent_profile_id"] or "").strip()
    if not agent_ref:
        raise ValueError("room_not_agent_chat")
    agent_row = _lookup_agent_profile(conn, str(room["workspace_id"]), agent_ref)
    if not agent_row:
        raise ValueError("agent_profile_not_found")
    return room, str(agent_row["slug"]), str(agent_row["id"])


def _resolve_room_agent_chat(
    conn: sqlite3.Connection,
    user_id: str,
    room_id: str,
) -> tuple[sqlite3.Row, str, str, str, str]:
    """Agent DM bind context from room SSOT — (room, template, runtime, agent_db_id, workspace_id)."""
    user_id = str(user_id or "").strip()
    room_id = str(room_id or "").strip()
    if not user_id or not room_id:
        raise ValueError("room_id and user required")
    if not _user_can_access_room(conn, room_id, user_id):
        raise ValueError("room_access_denied")
    room = conn.execute(
        "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
        (room_id,),
    ).fetchone()
    if not room:
        raise ValueError("room_not_found")
    if _is_space_room(str(room["room_type"]), room["agent_profile_id"]):
        raise ValueError("room_not_agent_chat")
    agent_ref = str(room["agent_profile_id"] or "").strip()
    if str(room["room_type"]) != "direct" or not agent_ref:
        raise ValueError("room_not_agent_chat")
    workspace_id = str(room["workspace_id"])
    agent_row = _lookup_agent_profile(conn, workspace_id, agent_ref)
    if not agent_row:
        raise ValueError("agent_profile_not_found")
    template = resolve_validated_profile(str(agent_row["slug"]))
    runtime = _resolve_chat_hermes_profile(template, user_id, room_id, workspace_id)
    if not _runtime_profile_on_disk(runtime) and runtime != template:
        raise ValueError("runtime_profile_not_provisioned")
    return room, template, runtime, str(agent_row["id"]), workspace_id


def _provision_invited_member_agent_runtimes(workspace_id: str, user_id: str) -> None:
    """Provision u-* runtimes for workspace agents when a member joins."""
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not workspace_id or not user_id:
        return
    try:
        conn = _workframe_db()
        rows = conn.execute(
            """
            SELECT id FROM agent_profiles
            WHERE workspace_id = ? AND deleted_at IS NULL AND status = 'available'
            """,
            (workspace_id,),
        ).fetchall()
        conn.close()
    except Exception:  # noqa: BLE001
        return
    for row in rows:
        _provision_agent_dm_runtimes(workspace_id, str(row["id"]), [user_id])


def _provision_agent_dm_runtimes(
    workspace_id: str,
    agent_profile_id: str,
    user_ids: list[str],
) -> None:
    """Create u-* runtime profiles when an agent DM room is created — install/onboarding only, not bind."""
    workspace_id = str(workspace_id or "").strip()
    agent_profile_id = str(agent_profile_id or "").strip()
    if not workspace_id or not agent_profile_id:
        return
    try:
        conn = _workframe_db()
        agent_row = _lookup_agent_profile(conn, workspace_id, agent_profile_id)
        conn.close()
    except Exception:  # noqa: BLE001
        return
    if not agent_row:
        return
    template = str(agent_row["slug"] or "").strip()
    if not template:
        return
    try:
        template = resolve_validated_profile(template)
    except ValueError as exc:
        print(
            f"[provision_agent_dm_runtimes] skip {agent_profile_id}: invalid template {template!r}: {exc}",
            flush=True,
        )
        return
    for uid in user_ids:
        user = str(uid or "").strip()
        if not user:
            continue
        runtime = _runtime_profile_slug(user, template)
        if _runtime_profile_on_disk(runtime):
            continue
        try:
            ensure_runtime_profile(runtime, template, user, workspace_id)
        except Exception as exc:  # noqa: BLE001
            print(
                f"[provision_agent_dm_runtimes] failed {runtime} for {user}: {exc}",
                flush=True,
            )


def _iter_agent_dm_runtime_slots(conn: sqlite3.Connection) -> list[dict[str, str]]:
    """All (workspace, agent, user) slots that need a u-* runtime for agent DM bind."""
    rows = conn.execute(
        """
        SELECT r.workspace_id, r.agent_profile_id, rm.user_id
        FROM rooms r
        JOIN room_memberships rm ON rm.room_id = r.id AND rm.deleted_at IS NULL
        WHERE r.deleted_at IS NULL
          AND r.room_type = 'direct'
          AND r.agent_profile_id IS NOT NULL
          AND TRIM(r.agent_profile_id) != ''
        """,
    ).fetchall()
    seen: set[tuple[str, str, str]] = set()
    slots: list[dict[str, str]] = []
    for row in rows:
        workspace_id = str(row["workspace_id"] or "").strip()
        agent_ref = str(row["agent_profile_id"] or "").strip()
        user_id = str(row["user_id"] or "").strip()
        if not workspace_id or not agent_ref or not user_id:
            continue
        key = (workspace_id, agent_ref, user_id)
        if key in seen:
            continue
        seen.add(key)
        agent_row = _lookup_agent_profile(conn, workspace_id, agent_ref)
        if not agent_row:
            continue
        template = str(agent_row["slug"] or "").strip()
        if not template:
            continue
        runtime = _runtime_profile_slug(user_id, template)
        slots.append({
            "workspace_id": workspace_id,
            "agent_profile_id": str(agent_row["id"]),
            "user_id": user_id,
            "template": template,
            "runtime": runtime,
            "on_disk": _runtime_profile_on_disk(runtime),
        })
    return slots


def doctor_audit_agent_dm_runtimes() -> dict[str, Any]:
    """Report missing u-* runtimes for agent DM rooms — no mutations."""
    conn = _workframe_db()
    try:
        slots = _iter_agent_dm_runtime_slots(conn)
    finally:
        conn.close()
    missing = [s for s in slots if not s["on_disk"]]
    return {
        "ok": True,
        "total": len(slots),
        "present": len(slots) - len(missing),
        "missing": missing,
    }


def doctor_repair_agent_dm_runtimes(*, repair: bool = True) -> dict[str, Any]:
    """Explicit repair — provision missing u-* runtimes for agent DM rooms."""
    conn = _workframe_db()
    try:
        slots = _iter_agent_dm_runtime_slots(conn)
    finally:
        conn.close()
    missing = [s for s in slots if not s["on_disk"]]
    if not repair:
        return doctor_audit_agent_dm_runtimes()
    repaired: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    for slot in missing:
        runtime = slot["runtime"]
        try:
            ensure_runtime_profile(
                runtime,
                slot["template"],
                slot["user_id"],
                slot["workspace_id"],
            )
            if _runtime_profile_on_disk(runtime):
                repaired.append(slot)
            else:
                failed.append({**slot, "error": "runtime_still_missing"})
        except Exception as exc:  # noqa: BLE001
            failed.append({**slot, "error": str(exc)})
    still_missing = [s for s in missing if not _runtime_profile_on_disk(s["runtime"])]
    return {
        "ok": not failed and not still_missing,
        "total": len(slots),
        "missing_before": len(missing),
        "repaired": repaired,
        "failed": failed,
        "still_missing": still_missing,
    }


def bootstrap_agent_dm_lane(
    user_id: str,
    workspace_id: str,
    template_slug: str,
    *,
    model: str = "",
    soul: str = "",
    bind_session: bool = True,
    room_name: str = "",
    role: str = "",
    tagline: str = "",
    created_by: str = "",
) -> dict[str, Any]:
    """Provision u-* runtime, model/proxy, DM room, and optional session bind — install/create-agent parity."""
    user_id = str(user_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if not _native_profile_present():
        _ensure_native_hermes_profile()
    template = resolve_validated_profile(str(template_slug or "").strip())
    if not user_id or not workspace_id:
        return {"ok": False, "error": "user_id and workspace_id required"}
    runtime = _runtime_profile_slug(user_id, template)
    steps: list[dict[str, Any]] = []
    try:
        ensure_runtime_profile(runtime, template, user_id, workspace_id)
        steps.append({"step": "runtime_profile", "ok": True, "runtime": runtime})
    except Exception as exc:
        steps.append({"step": "runtime_profile", "ok": False, "error": str(exc)})
        return {"ok": False, "template": template, "runtime": runtime, "steps": steps, "error": str(exc)}

    model_id = str(model or "").strip()
    if model_id:
        try:
            applied = hermes_model_set(runtime, model_id, user_id, workspace_id)
            steps.append(
                {
                    "step": "set_runtime_model",
                    "ok": bool(applied.get("ok")),
                    "model": model_id,
                    **({"error": applied.get("error")} if not applied.get("ok") else {}),
                },
            )
            if not applied.get("ok"):
                return {
                    "ok": False,
                    "template": template,
                    "runtime": runtime,
                    "steps": steps,
                    "error": str(applied.get("error") or "set_runtime_model_failed"),
                }
        except Exception as exc:
            steps.append({"step": "set_runtime_model", "ok": False, "error": str(exc)})
            return {
                "ok": False,
                "template": template,
                "runtime": runtime,
                "steps": steps,
                "error": str(exc),
            }
    else:
        try:
            _bootstrap_profile_providers(runtime, user_id, workspace_id)
            steps.append({"step": "bootstrap_providers", "ok": True})
            user_primary, user_chain = _read_user_llm_prefs(user_id)
            if user_primary:
                applied = hermes_model_set(runtime, user_primary, user_id, workspace_id)
                steps.append(
                    {
                        "step": "user_default_model",
                        "ok": bool(applied.get("ok")),
                        "model": user_primary,
                    },
                )
            if user_chain:
                chained = hermes_fallback_chain_set(runtime, user_chain, user_id=user_id)
                steps.append(
                    {
                        "step": "user_default_fallbacks",
                        "ok": bool(chained.get("ok")),
                        "count": len(user_chain),
                    },
                )
        except Exception as exc:
            steps.append({"step": "bootstrap_providers", "ok": False, "error": str(exc)})

    soul_text = str(soul or "").strip()
    identity_role = str(role or "").strip()
    identity_tagline = str(tagline or "").strip()
    identity_name = room_name.strip()
    if soul_text or identity_name or identity_role or identity_tagline:
        _seed_native_user_overlay(
            runtime,
            template,
            display_name=identity_name,
            role=identity_role,
            tagline=identity_tagline,
            user_soul=soul_text,
        )

    gateway_started = False
    last_gw_exc: Exception | None = None
    for attempt in range(3):
        try:
            ensure_profile_api(runtime, user_id, workspace_id, bootstrap_providers=False)
            step_row: dict[str, Any] = {"step": "start_gateway", "ok": True, "runtime": runtime}
            if attempt:
                step_row["retried"] = True
            steps.append(step_row)
            gateway_started = True
            break
        except Exception as exc:
            last_gw_exc = exc
            if attempt < 2:
                time.sleep(1.5)
    if not gateway_started:
        steps.append({"step": "start_gateway", "ok": False, "error": str(last_gw_exc)})
        return {
            "ok": False,
            "template": template,
            "runtime": runtime,
            "steps": steps,
            "error": str(last_gw_exc),
        }

    display = _runtime_display_label(user_id, template, workspace_id)
    _ensure_workspace_agent_profile_row(
        template,
        workspace_id=workspace_id,
        display_name=room_name.strip() or display,
        role=identity_role,
        tagline=identity_tagline,
        is_native=_is_native_profile(template),
    )
    status, room_payload = _create_room(
        workspace_id,
        {
            "name": room_name.strip() or display,
            "room_type": "direct",
            "agent_profile_id": template,
            "member_user_ids": [user_id],
        },
        created_by or user_id,
    )
    room = room_payload.get("room") if isinstance(room_payload.get("room"), dict) else {}
    room_id = str(room.get("id") or "").strip()
    dm_error = ""
    if not room_id:
        dm_error = str(
            room_payload.get("error")
            or room_payload.get("detail")
            or ("dm_room_failed" if status not in (200, 201) else "dm_room_missing_id"),
        ).strip()
    steps.append(
        {
            "step": "dm_room",
            "ok": status in (200, 201) and bool(room_id),
            "room_id": room_id,
            "status": status,
            **({"error": dm_error} if dm_error else {}),
        },
    )
    if not room_id:
        return {
            "ok": False,
            "template": template,
            "runtime": runtime,
            "steps": steps,
            "error": dm_error or "dm_room_failed",
            "room_error": room_payload,
        }

    session_id = ""
    if bind_session:
        bind_payload: dict[str, Any] = {
            "workspace_id": workspace_id,
            "source_id": "ui",
            "client_id": "default",
            "new_session": False,
        }
        if template == _primary_profile():
            bind_payload["binding_version"] = 2
        try:
            bound = room_chat_bind(room_id, bind_payload, user_id)
            session_id = str(bound.get("session_id") or "").strip()
            steps.append({"step": "room_chat_bind", "ok": bool(session_id), "session_id": session_id})
        except Exception as exc:
            steps.append({"step": "room_chat_bind", "ok": False, "error": str(exc)})

    bind_ok = not bind_session or bool(session_id)
    steps_ok = all(s.get("ok") is not False for s in steps)
    return {
        "ok": bind_ok and steps_ok,
        "template": template,
        "runtime": runtime,
        "room_id": room_id,
        "room": room,
        "session_id": session_id,
        "steps": steps,
        **({"error": "room_chat_bind_failed"} if bind_session and not session_id else {}),
    }


def _runtime_profile_slug(user_id: str, template_slug: str) -> str:
    template_slug = safe_profile_slug(template_slug)
    user_part = re.sub(r"[^a-z0-9]+", "-", _user_hermes_dir_slug(user_id).lower()).strip("-")[:20] or "user"
    slug = f"u-{user_part}-{template_slug}"
    if len(slug) > 64:
        slug = slug[:64].rstrip("-")
    return safe_profile_slug(slug)


# Credential payer audit (owner-pays vs acting-user-pays):
# - kanban_proxy_create_task / _refresh_active_kanban_assignee_credentials → profile owner
# - ensure_runtime_profile / _prepare_runtime_profile_credentials → profile owner at create
# - profile_chat_message / stream_profile_chat / _overlay_chat_llm_env → acting user (payer)
# - room @mention turn (_run_room_agent_turn) → triggered_by_user_id (mention author pays)
def _prepare_runtime_profile_credentials(
    runtime: str,
    user_id: str,
    workspace_id: str = "",
) -> bool:
    """Strip stale profile secrets, then overlay the runtime profile owner's keys.

    Delegation assigns work to another user's runtime slug; provider keys and
    billing follow the profile owner (assignee), not the user who delegated.
    """
    runtime = safe_profile_slug(str(runtime or "").strip())
    user = str(user_id or "").strip()
    if not runtime or not user or not _is_runtime_profile_slug(runtime):
        return False
    try:
        resolve_hermes_profile(runtime)
    except ValueError:
        return False
    _strip_profile_llm_env(runtime)
    _strip_profile_action_env(runtime)
    _reconcile_profile_llm_for_user(runtime, user, workspace_id)
    prov = _llm_billing_provider(runtime, user_id=user, workspace_id=workspace_id)
    _ensure_profile_llm_proxy(runtime, prov)
    return _user_can_use_llm(user, workspace_id, prov)


def _resolve_runtime_owner(runtime: str) -> tuple[str, str] | None:
    """Map a u-* runtime slug to (owner_user_id, workspace_id)."""
    runtime = safe_profile_slug(str(runtime or "").strip())
    if not _is_runtime_profile_slug(runtime):
        return None
    conn = _workframe_db()
    try:
        for row in conn.execute("SELECT id FROM workspaces WHERE deleted_at IS NULL").fetchall():
            wid = str(row["id"])
            uid = _user_id_for_runtime_slug(runtime, wid)
            if uid:
                return uid, wid
    finally:
        conn.close()
    return None


def _iter_kanban_dbs() -> list[Path]:
    dbs = [HERMES_DATA / "kanban.db"]
    boards_root = HERMES_DATA / "kanban" / "boards"
    if boards_root.is_dir():
        for board_dir in boards_root.iterdir():
            if board_dir.is_dir():
                candidate = board_dir / "kanban.db"
                if candidate.is_file():
                    dbs.append(candidate)
    return dbs


def _refresh_active_kanban_assignee_credentials() -> None:
    """Keep kanban worker profile .env aligned with assignee owner (not last chatter)."""
    assignees: set[str] = set()
    for db_path in _iter_kanban_dbs():
        conn = _ro_sqlite_live(db_path)
        if not conn:
            continue
        try:
            rows = conn.execute(
                """
                SELECT DISTINCT assignee FROM tasks
                WHERE status IN ('ready', 'running', 'scheduled', 'triage')
                  AND assignee LIKE 'u-%'
                """
            ).fetchall()
            for row in rows:
                slug = safe_profile_slug(str(row["assignee"] or "").strip())
                if slug:
                    assignees.add(slug)
        except sqlite3.Error:
            pass
        finally:
            conn.close()
    for assignee in assignees:
        resolved = _resolve_runtime_owner(assignee)
        if not resolved:
            continue
        owner_id, workspace_id = resolved
        _prepare_runtime_profile_credentials(assignee, owner_id, workspace_id)


def _kanban_credential_guard_daemon() -> None:
    while True:
        try:
            _refresh_active_kanban_assignee_credentials()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(5)


def _user_handle(user_id: str) -> str:
    """Short lowercase handle for cohort aliases (display_name or email local-part)."""
    user_id = str(user_id or "").strip()
    if not user_id:
        return "user"
    conn = _workframe_db()
    try:
        row = conn.execute(
            "SELECT display_name, email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return "user"
    display = str(row["display_name"] or "").strip()
    if display:
        handle = re.sub(r"[^a-z0-9]+", "-", display.lower()).strip("-")[:24]
        if handle:
            return handle
    email = str(row["email"] or "").strip().lower()
    if "@" in email:
        handle = re.sub(r"[^a-z0-9]+", "-", email.split("@", 1)[0]).strip("-")[:24]
        if handle:
            return handle
    return "user"


def _user_owner_name(user_id: str) -> str:
    return _user_handle(user_id).replace("-", " ").strip().title() or "User"


def _runtime_display_label(user_id: str, template_slug: str, workspace_id: str = "") -> str:
    template = safe_profile_slug(str(template_slug or "").strip())
    user_id = str(user_id or "").strip()
    if user_id:
        runtime = _runtime_profile_slug(user_id, template)
        reg_runtime = _agent_registry_row(runtime)
        if str(reg_runtime.get("display_name") or "").strip():
            return str(reg_runtime["display_name"]).strip()
    custom = _agent_db_display_name(template, workspace_id)
    if custom:
        return custom
    reg = _agent_registry_row(template)
    if reg.get("display_name"):
        return str(reg["display_name"])
    if _is_native_profile(template) or template.endswith("-agent"):
        return f"{_user_owner_name(user_id)}'s {_native_display_name().replace(' Agent', '')} Agent"
    role = _agent_db_display_name(template, workspace_id) or _agent_registry_row(template).get("display_name")
    if not role:
        role = template.replace("-", " ").title()
    return f"{_user_owner_name(user_id)}'s {role}"


def _cohort_alias(user_id: str, template_slug: str) -> str:
    """Human alias for docs/prompts — not the Hermes profile dir slug."""
    template = safe_profile_slug(template_slug)
    short = _profile_slug(template).replace("_", "-")
    return f"{_user_handle(user_id)}-{short}"


def resolve_runtime_assignee(template_slug: str, user_id: str, workspace_id: str = "") -> str:
    """Map template specialist slug → per-user runtime profile (has overlaid credentials)."""
    user_id = str(user_id or "").strip()
    template = safe_profile_slug(str(template_slug or "").strip())
    if not user_id:
        return template
    runtime = _runtime_profile_slug(user_id, template)
    ensure_runtime_profile(runtime, template, user_id, workspace_id)
    return runtime


def _user_id_for_runtime_slug(runtime: str, workspace_id: str) -> str | None:
    """Resolve owning user for a per-user runtime Hermes profile slug."""
    runtime = safe_profile_slug(str(runtime or "").strip())
    workspace_id = str(workspace_id or "").strip()
    if not _is_runtime_profile_slug(runtime) or not workspace_id:
        return None
    conn = _workframe_db()
    try:
        members = [
            str(row["user_id"] or "").strip()
            for row in conn.execute(
                """
            SELECT user_id FROM workspace_memberships
            WHERE workspace_id = ? AND status = 'active' AND deleted_at IS NULL
            """,
                (workspace_id,),
            ).fetchall()
            if str(row["user_id"] or "").strip()
        ]
        templates = [
            str(row["slug"] or "").strip()
            for row in conn.execute(
                """
            SELECT slug FROM agent_profiles
            WHERE workspace_id = ? AND deleted_at IS NULL
            """,
                (workspace_id,),
            ).fetchall()
            if str(row["slug"] or "").strip()
        ]
    finally:
        conn.close()
    for uid in members:
        for template in templates:
            if _runtime_profile_slug(uid, template) == runtime:
                return uid
    return None


def cohort_runtime_slugs(user_id: str, workspace_id: str) -> set[str]:
    """Runtime Hermes slugs this user may assign kanban/cron/delegation to (own cohort)."""
    return {
        str(row.get("runtime_slug") or "").strip()
        for row in ensure_user_agent_cohort(user_id, workspace_id)
        if str(row.get("runtime_slug") or "").strip()
    }


def validate_kanban_assignee(
    assignee: str,
    acting_user_id: str,
    workspace_id: str,
    *,
    delegate_user_ids: frozenset[str] | None = None,
    allow_template: bool = False,
) -> tuple[bool, str]:
    """Check whether acting_user may create/dispatch a task to assignee.

    Returns (ok, reason_or_owner_user_id).
    """
    assignee = safe_profile_slug(str(assignee or "").strip())
    acting = str(acting_user_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if not assignee:
        return False, "assignee_required"
    if not acting or not workspace_id:
        return False, "acting_user_required"
    if delegate_user_ids is None:
        delegate_user_ids = frozenset(_delegation_grantor_ids_for_grantee(acting, workspace_id))
    if _is_runtime_profile_slug(assignee):
        owner = _user_id_for_runtime_slug(assignee, workspace_id)
        if not owner:
            return False, "assignee_not_in_workspace"
        allowed = {acting} | set(delegate_user_ids or ())
        if owner in allowed:
            return True, owner
        return False, "assignee_owner_forbidden"
    if allow_template:
        return True, "template"
    return False, "template_assignee_forbidden"


def _user_is_workspace_member(user_id: str, workspace_id: str) -> bool:
    user_id = str(user_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if not user_id or not workspace_id:
        return False
    conn = _workframe_db()
    try:
        return _workspace_member_role(conn, workspace_id, user_id) is not None
    finally:
        conn.close()


def _delegation_grantor_ids_for_grantee(
    grantee_user_id: str,
    workspace_id: str,
    scope: str = DELEGATION_SCOPE_AGENTS_DELEGATE,
) -> set[str]:
    grantee_user_id = str(grantee_user_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if not grantee_user_id or not workspace_id:
        return set()
    conn = _workframe_db()
    try:
        rows = conn.execute(
            """
            SELECT grantor_user_id FROM agent_delegation_grants
            WHERE workspace_id = ? AND grantee_user_id = ? AND scope = ?
              AND deleted_at IS NULL
              AND (expires_at IS NULL OR expires_at > datetime('now'))
            """,
            (workspace_id, grantee_user_id, scope),
        ).fetchall()
    finally:
        conn.close()
    return {str(row["grantor_user_id"]).strip() for row in rows if str(row["grantor_user_id"] or "").strip()}


def _delegation_grant_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "grantor_user_id": row["grantor_user_id"],
        "grantee_user_id": row["grantee_user_id"],
        "scope": row["scope"],
        "expires_at": row["expires_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_delegation_grants(workspace_id: str, user_id: str) -> dict[str, Any]:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not _user_is_workspace_member(user_id, workspace_id):
        raise PermissionError("forbidden")
    conn = _workframe_db()
    try:
        rows = conn.execute(
            """
            SELECT * FROM agent_delegation_grants
            WHERE workspace_id = ? AND deleted_at IS NULL
              AND (grantor_user_id = ? OR grantee_user_id = ?)
            ORDER BY created_at DESC
            """,
            (workspace_id, user_id, user_id),
        ).fetchall()
    finally:
        conn.close()
    return {
        "ok": True,
        "workspace_id": workspace_id,
        "grants": [_delegation_grant_payload(row) for row in rows],
    }


def create_delegation_grant(
    workspace_id: str,
    grantor_user_id: str,
    grantee_user_id: str,
    scope: str = DELEGATION_SCOPE_AGENTS_DELEGATE,
) -> dict[str, Any]:
    workspace_id = str(workspace_id or "").strip()
    grantor_user_id = str(grantor_user_id or "").strip()
    grantee_user_id = str(grantee_user_id or "").strip()
    scope = str(scope or DELEGATION_SCOPE_AGENTS_DELEGATE).strip()
    if not workspace_id or not grantor_user_id or not grantee_user_id:
        raise ValueError("grantor_grantee_required")
    if grantor_user_id == grantee_user_id:
        raise ValueError("self_grant_forbidden")
    if scope != DELEGATION_SCOPE_AGENTS_DELEGATE:
        raise ValueError("unsupported_scope")
    if not _user_is_workspace_member(grantor_user_id, workspace_id):
        raise PermissionError("forbidden")
    if not _user_is_workspace_member(grantee_user_id, workspace_id):
        raise ValueError("grantee_not_member")
    now = _utc_now()
    conn = _workframe_db()
    try:
        existing = conn.execute(
            """
            SELECT id FROM agent_delegation_grants
            WHERE workspace_id = ? AND grantor_user_id = ? AND grantee_user_id = ?
              AND scope = ? AND deleted_at IS NULL
            """,
            (workspace_id, grantor_user_id, grantee_user_id, scope),
        ).fetchone()
        if existing:
            grant_id = str(existing["id"])
            conn.execute(
                "UPDATE agent_delegation_grants SET updated_at = ?, expires_at = NULL WHERE id = ?",
                (now, grant_id),
            )
        else:
            grant_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO agent_delegation_grants (
                    id, workspace_id, grantor_user_id, grantee_user_id, scope,
                    expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (grant_id, workspace_id, grantor_user_id, grantee_user_id, scope, now, now),
            )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM agent_delegation_grants WHERE id = ?",
            (grant_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise ValueError("grant_persist_failed")
    return {"ok": True, "grant": _delegation_grant_payload(row)}


def revoke_delegation_grant(workspace_id: str, grant_id: str, user_id: str) -> dict[str, Any]:
    workspace_id = str(workspace_id or "").strip()
    grant_id = str(grant_id or "").strip()
    user_id = str(user_id or "").strip()
    conn = _workframe_db()
    try:
        row = conn.execute(
            """
            SELECT * FROM agent_delegation_grants
            WHERE id = ? AND workspace_id = ? AND deleted_at IS NULL
            """,
            (grant_id, workspace_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        if user_id not in {str(row["grantor_user_id"]), str(row["grantee_user_id"])}:
            raise PermissionError("forbidden")
        now = _utc_now()
        conn.execute(
            "UPDATE agent_delegation_grants SET deleted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, grant_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "id": grant_id}


def _hermes_kanban_db_path(board_slug: str) -> Path:
    slug = safe_profile_slug(str(board_slug or "default").strip()) or "default"
    if slug == "default":
        return HERMES_DATA / "kanban.db"
    return HERMES_DATA / "kanban" / "boards" / slug / "kanban.db"


def _workspace_kanban_board_row(workspace_id: str) -> sqlite3.Row | None:
    conn = _workframe_db()
    try:
        return conn.execute(
            """
            SELECT * FROM workspace_kanban_boards
            WHERE workspace_id = ? AND deleted_at IS NULL
            LIMIT 1
            """,
            (workspace_id,),
        ).fetchone()
    finally:
        conn.close()


def ensure_workspace_kanban_board(workspace_id: str) -> str:
    workspace_id = str(workspace_id or "").strip()
    row = _workspace_kanban_board_row(workspace_id)
    if row:
        return str(row["hermes_board_slug"])
    conn = _workframe_db()
    try:
        ws = conn.execute(
            "SELECT slug, display_name FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        if not ws:
            raise ValueError("workspace_not_found")
        board_slug = re.sub(r"[^a-z0-9-]+", "-", str(ws["slug"] or workspace_id).lower()).strip("-")[:40]
        if not board_slug:
            board_slug = f"ws-{workspace_id[:8].lower()}"
        display_name = str(ws["display_name"] or board_slug)
        now = _utc_now()
        conn.execute(
            """
            INSERT INTO workspace_kanban_boards (
                id, workspace_id, hermes_board_slug, display_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), workspace_id, board_slug, display_name, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    primary = _primary_profile()
    if primary:
        code, out = _gateway_exec(
            primary,
            ["kanban", "boards", "create", board_slug, "--name", display_name],
        )
        if code != 0 and "already exists" not in out.lower():
            pass  # ponytail: board row is source of truth; Hermes may already have the board
    return board_slug


def kanban_proxy_list_tasks(workspace_id: str, user_id: str) -> dict[str, Any]:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not _user_is_workspace_member(user_id, workspace_id):
        raise PermissionError("forbidden")
    row = _workspace_kanban_board_row(workspace_id)
    board_slug = str(row["hermes_board_slug"]) if row else "default"
    db = _hermes_kanban_db_path(board_slug)
    out: dict[str, Any] = {
        "ok": True,
        "board": board_slug,
        "workspace_id": workspace_id,
        "tasks": [],
        "total": 0,
    }
    conn = _ro_sqlite_live(db)
    if not conn:
        return out
    try:
        rows = conn.execute(
            """
            SELECT id, title, status, assignee, priority, created_at, completed_at
            FROM tasks
            ORDER BY created_at DESC
            LIMIT 100
            """
        ).fetchall()
        tasks = [
            {
                "id": r["id"],
                "title": r["title"],
                "status": r["status"],
                "assignee": r["assignee"] or "",
                "priority": r["priority"] or 0,
                "created_at": _iso_from_unix(r["created_at"]),
                "completed_at": _iso_from_unix(r["completed_at"]) if r["completed_at"] else None,
            }
            for r in rows
        ]
        out["tasks"] = tasks
        out["total"] = len(tasks)
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return out


def kanban_proxy_create_task(workspace_id: str, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not _user_is_workspace_member(user_id, workspace_id):
        raise PermissionError("forbidden")
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("title_required")
    raw_assignee = str(payload.get("assignee") or payload.get("template_slug") or "").strip()
    assignee_owner = str(payload.get("assignee_user_id") or user_id).strip()
    if _is_runtime_profile_slug(safe_profile_slug(raw_assignee)):
        runtime = safe_profile_slug(raw_assignee)
    elif raw_assignee:
        runtime = resolve_runtime_assignee(raw_assignee, assignee_owner, workspace_id)
    else:
        raise ValueError("assignee_required")
    ok, reason = validate_kanban_assignee(runtime, user_id, workspace_id)
    if not ok:
        raise PermissionError(str(reason))
    board = ensure_workspace_kanban_board(workspace_id)
    orchestrator = resolve_runtime_assignee("workframe-agent", user_id, workspace_id)
    args = ["kanban", "--board", board, "create", title, "--assignee", runtime]
    workspace_kind = str(payload.get("workspace_kind") or "scratch").strip()
    if workspace_kind:
        args.extend(["--workspace-kind", workspace_kind])
    body = str(payload.get("body") or "").strip()
    if body:
        args.extend(["--body", body])
    code, out = _gateway_exec(orchestrator, args)
    if code != 0:
        raise ValueError(f"kanban_create_failed: {out.strip()}")
    owner_id = assignee_owner
    if _is_runtime_profile_slug(runtime):
        resolved = _resolve_runtime_owner(runtime)
        if resolved:
            owner_id, workspace_id = resolved[0], resolved[1] or workspace_id
    _prepare_runtime_profile_credentials(runtime, owner_id, workspace_id)
    return {
        "ok": True,
        "board": board,
        "assignee": runtime,
        "title": title,
        "output": out.strip(),
    }


def _allowed_runtime_profiles_for_workspace(workspace_id: str) -> set[str]:
    allowed: set[str] = set()
    conn = _workframe_db()
    try:
        members = [
            str(row["user_id"] or "").strip()
            for row in conn.execute(
                """
                SELECT user_id FROM workspace_memberships
                WHERE workspace_id = ? AND status = 'active' AND deleted_at IS NULL
                """,
                (workspace_id,),
            ).fetchall()
            if str(row["user_id"] or "").strip()
        ]
        templates = [
            str(row["slug"] or "").strip()
            for row in conn.execute(
                """
                SELECT slug FROM agent_profiles
                WHERE workspace_id = ? AND deleted_at IS NULL
                """,
                (workspace_id,),
            ).fetchall()
            if str(row["slug"] or "").strip()
        ]
    finally:
        conn.close()
    for uid in members:
        for template in templates:
            allowed.add(_runtime_profile_slug(uid, template))
    return allowed


def purge_stale_runtime_profiles(workspace_id: str) -> dict[str, Any]:
    workspace_id = str(workspace_id or "").strip()
    allowed = _allowed_runtime_profiles_for_workspace(workspace_id)
    purged: list[str] = []
    for profile in _list_profiles():
        if not _is_runtime_profile_slug(profile):
            continue
        if profile in allowed:
            continue
        _purge_runtime_profile(profile)
        purged.append(profile)
    for orphan in ("u-testalan-workframe-agent", "andy"):
        if orphan in _list_profiles() and orphan not in allowed and orphan not in purged:
            _purge_runtime_profile(orphan)
            purged.append(orphan)
    profiles_dir = HERMES_DATA / "profiles"
    if profiles_dir.is_dir():
        for entry in profiles_dir.iterdir():
            name = entry.name
            if not entry.is_dir() or name in allowed or name in purged:
                continue
            if name == "andy" or (name.startswith("u-test") and _is_runtime_profile_slug(name)):
                _purge_runtime_profile(name)
                purged.append(name)
    return {"ok": True, "purged": purged, "allowed_count": len(allowed)}


def _cohort_manifest_markdown(user_id: str, cohort: list[dict[str, Any]]) -> str:
    owner = _user_owner_name(user_id)
    lines = [
        f"# {owner}'s Workframe cohort",
        "",
        "This file is auto-generated by Workframe. Read it before kanban, cron, or delegation.",
        "",
        "## Rules",
        "",
        "- Use **runtime_slug** (column below) for kanban `--assignee`, cron agent targets, and `delegate_task` profile — never bare template names like `architect`.",
        "- Template profiles (`architect`, `dev`, …) are shared disks **without your API keys**; workers exit immediately.",
        "- Only interact with profiles listed here. Do not read other users' `u-*` profile `.env` files.",
        "- Valid kanban `workspace_kind`: `scratch`, `dir:/absolute/path`, `worktree` — not `project`.",
        "- Kanban workers must call `kanban_complete` or `kanban_block` before exit.",
        "- Hermes CLI: `/opt/hermes/.venv/bin/hermes -p <runtime_slug> …`",
        "",
        "## Your agents",
        "",
        "| Role | You call them | runtime_slug (kanban/delegate) | alias |",
        "|------|---------------|--------------------------------|-------|",
    ]
    for row in cohort:
        lines.append(
            f"| {row.get('role', '')} | {row.get('display_name', '')} | `{row.get('runtime_slug', '')}` | `{row.get('alias', '')}` |"
        )
    lines.extend(["", f"Owner user_id: `{user_id}`", ""])
    return "\n".join(lines)


def _write_workframe_cohort_manifest(user_id: str, workspace_id: str, cohort: list[dict[str, Any]]) -> None:
    if not cohort:
        return
    body = _cohort_manifest_markdown(user_id, cohort)
    for row in cohort:
        runtime = str(row.get("runtime_slug") or "").strip()
        if not runtime:
            continue
        path = _profile_dir(runtime) / "WORKFRAME_COHORT.md"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        except OSError:
            pass


def ensure_user_agent_cohort(user_id: str, workspace_id: str) -> list[dict[str, Any]]:
    """Provision runtime profiles + credentials for every workspace agent this user may orchestrate."""
    user_id = str(user_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if not user_id or not workspace_id:
        return []
    cohort: list[dict[str, Any]] = []
    conn = _workframe_db()
    try:
        rows = conn.execute(
            """
            SELECT slug, display_name, tagline, role, avatar_url, is_native
            FROM agent_profiles
            WHERE workspace_id = ? AND deleted_at IS NULL
            ORDER BY is_native DESC, created_at ASC
            """,
            (workspace_id,),
        ).fetchall()
    finally:
        conn.close()
    for row in rows:
        template = str(row["slug"] or "").strip()
        if not template:
            continue
        runtime = _runtime_profile_slug(user_id, template)
        if not _runtime_profile_ready(runtime):
            try:
                ensure_runtime_profile(runtime, template, user_id, workspace_id)
            except ValueError:
                continue
        ident = _agent_identity_fields(template, workspace_id, user_id)
        role = str(ident.get("role") or row["display_name"] or template).strip()
        cohort.append(
            {
                "template_slug": template,
                "runtime_slug": runtime,
                "display_name": _runtime_display_label(user_id, template, workspace_id),
                "kanban_assignee": runtime,
                "alias": _cohort_alias(user_id, template),
                "role": role,
                "tagline": str(ident.get("tagline") or row["tagline"] or ""),
                "avatar_url": ident.get("avatar_url"),
                "avatar_id": ident.get("avatar_id"),
                "is_native": bool(int(row["is_native"] or 0)),
            }
        )
    _write_workframe_cohort_manifest(user_id, workspace_id, cohort)
    return cohort


def _runtime_gateway_registered(runtime: str) -> bool:
    runtime = safe_profile_slug(str(runtime or "").strip())
    if not runtime:
        return False
    now = time.monotonic()
    cached = _gateway_registered_cache.get(runtime)
    if cached and now - cached[1] < _GATEWAY_REG_TTL_SEC:
        return cached[0]
    if SECURE_MODE and os.environ.get("WORKFRAME_SUPERVISOR_ALLOW_RAW_EXEC", "0") != "1":
        state = str(gateway_data(runtime).get("state") or "").lower()
        ok = state in {"running", "starting"} or _profile_api_healthy(runtime, timeout=0.8)
        _gateway_registered_cache[runtime] = (ok, now)
        return ok
    script = (
        "from pathlib import Path\n"
        f"p=Path('/run/service/gateway-{runtime}/run')\n"
        "raise SystemExit(0 if p.is_file() else 1)\n"
    )
    code, _ = _gateway_container_exec(["/opt/hermes/.venv/bin/python", "-c", script])
    ok = code == 0
    _gateway_registered_cache[runtime] = (ok, now)
    return ok


def _invalidate_gateway_registered_cache(runtime: str = "") -> None:
    if runtime:
        _gateway_registered_cache.pop(safe_profile_slug(runtime), None)
    else:
        _gateway_registered_cache.clear()


def _is_user_credential_home_slug(slug: str) -> bool:
    """UUID dirs under profiles/ hold per-user keys — not Hermes agent profiles."""
    return bool(_AGENT_PROFILE_UUID_RE.fullmatch(str(slug or "").strip()))


def _runtime_profile_on_disk(runtime: str) -> bool:
    p = _profile_dir(runtime)
    return p.is_dir() and _profile_config_path(runtime) is not None


def _runtime_profile_ready(runtime: str) -> bool:
    return _runtime_profile_on_disk(runtime) and _runtime_gateway_registered(runtime)


def _purge_runtime_profile(runtime: str) -> None:
    """Drop Hermes registry entry and on-disk dir (best-effort)."""
    try:
        _gateway_exec(_primary_profile(), ["profile", "delete", "-y", runtime])
    except Exception:  # noqa: BLE001
        pass
    shutil.rmtree(_profile_dir(runtime), ignore_errors=True)


def _register_runtime_profile(runtime: str, template: str) -> None:
    cmd = ["profile", "create", "--clone-from", template, runtime]
    code, out = _gateway_exec(_primary_profile(), cmd)
    if code == 0:
        _inherit_runtime_profile_config(runtime, template)
        return
    out_l = out.lower()
    if "already exists" in out_l:
        if _profile_config_path(runtime) is not None:
            return  # ponytail: Hermes registry + on-disk clone — adopt, don't recreate
        _purge_runtime_profile(runtime)
        code, out = _gateway_exec(_primary_profile(), cmd)
        if code == 0:
            _inherit_runtime_profile_config(runtime, template)
            return
    if code != 0:
        raise ValueError(f"runtime profile create failed: {out.strip()}")


def _copy_tree_missing(src: Path, dst: Path) -> None:
    """Copy files from src into dst only when dst path is absent (never overwrite SOUL edits)."""
    if not src.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(src)
        target = dst / rel
        if target.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(item, target)
        except OSError:
            pass


def _copy_text_without_bom(src: Path, dst: Path) -> None:
    """Copy markdown identity files without UTF-8 BOM (Hermes blocks BOM in context files)."""
    raw = src.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(raw)


def _ensure_profile_terminal_cwd(profile: str, *, cwd: str = "/workspace") -> None:
    """Hermes terminal + code_execution project root must be the shared workspace."""
    config_path = _profile_gateway_config_path(profile)
    if not config_path or not config_path.is_file():
        return
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError:
        return
    fixed = re.sub(r"(?m)^  cwd: .*$", f"  cwd: {cwd}", raw, count=1)
    if fixed == raw:
        return
    try:
        config_path.write_text(fixed, encoding="utf-8")
    except OSError:
        pass


def _backfill_runtime_identity(runtime: str, template: str) -> None:
    """Fill missing SOUL/skills from template — credentials overlay never touches these."""
    runtime = safe_profile_slug(runtime)
    template = safe_profile_slug(template)
    rdir = _profile_dir(runtime)
    tdir = _profile_dir(template)
    if not rdir.is_dir() or not tdir.is_dir():
        return
    for name in ("SOUL.md", "AGENTS.md", "SETUP.md"):
        src = tdir / name
        dst = rdir / name
        if name == "SOUL.md":
            if _write_profile_soul_if_stub(runtime, template):
                continue
        if src.is_file() and not dst.is_file():
            try:
                _copy_text_without_bom(src, dst)
            except OSError:
                pass
    _copy_tree_missing(tdir / "skills", rdir / "skills")
    _ensure_profile_terminal_cwd(runtime)


def _load_profile_yaml_dict(profile: str) -> dict[str, Any]:
    _normalize_profile_config_yaml(profile)
    cfg = _profile_config_path(profile)
    if not cfg or not cfg.is_file():
        return {}
    try:
        import yaml

        data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _profile_toolsets_ready(profile: str, want: tuple[str, ...] | list[str]) -> bool:
    cfg = _load_profile_yaml_dict(profile)
    if not cfg:
        return False
    names = [str(n) for n in want if str(n).strip()]
    if not names:
        return True
    ts = cfg.get("toolsets") if isinstance(cfg.get("toolsets"), list) else []
    if not all(name in ts for name in names):
        return False
    pts = cfg.get("platform_toolsets") if isinstance(cfg.get("platform_toolsets"), dict) else {}
    for platform in ("api_server", "cli"):
        plat = pts.get(platform) if isinstance(pts.get(platform), list) else []
        if not all(name in plat for name in names):
            return False
    agent = cfg.get("agent") if isinstance(cfg.get("agent"), dict) else {}
    disabled = agent.get("disabled_toolsets") if isinstance(agent.get("disabled_toolsets"), list) else []
    return not any(name in disabled for name in names)


def _inherit_runtime_profile_config(runtime: str, template: str) -> None:
    """Hermes clone-from copies .env/SOUL/skills but may omit profile.yaml on u-* slugs."""
    runtime = safe_profile_slug(runtime)
    template = safe_profile_slug(template)
    if _profile_config_path(runtime) is not None:
        return
    src = _profile_config_path(template)
    if src is None:
        raise ValueError(f"template profile has no config: {template}")
    dst = _profile_dir(runtime) / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def ensure_runtime_profile(
    runtime_slug: str,
    template_slug: str,
    user_id: str,
    workspace_id: str = "",
) -> None:
    runtime = safe_profile_slug(runtime_slug)
    template = resolve_validated_profile(template_slug)
    if _runtime_profile_on_disk(runtime):
        if not _runtime_gateway_registered(runtime):
            try:
                _register_runtime_profile(runtime, template)
            except ValueError:
                pass
            ok, out, _port = _configure_profile_api(runtime)
            if not ok:
                raise ValueError(f"runtime profile api config failed: {out}")
        skills_dir = _profile_dir(runtime) / "skills"
        if not skills_dir.is_dir() or not any(skills_dir.iterdir()):
            _backfill_runtime_identity(runtime, template)
        if not _profile_toolsets_ready(runtime, _chat_toolsets_for_profile(runtime)):
            _ensure_profile_toolsets(runtime)
        _ensure_profile_terminal_cwd(runtime)
        _sync_runtime_model_from_template(runtime, template)
        return
    _purge_runtime_profile(runtime)
    _register_runtime_profile(runtime, template)
    if _profile_config_path(runtime) is None:
        raise ValueError(f"runtime profile bootstrap failed: {runtime}")
    # SOUL: clone inherits template at profile create; do not auto-overwrite on disk later.
    soul_src = _profile_dir(template) / "SOUL.md"
    soul_dst = _profile_dir(runtime) / "SOUL.md"
    if soul_src.is_file() and soul_dst.parent.is_dir() and not soul_dst.is_file():
        try:
            shutil.copy2(soul_src, soul_dst)
        except OSError:
            pass
    _write_profile_soul_if_stub(runtime, template)
    _backfill_runtime_identity(runtime, template)
    _strip_profile_llm_env(runtime)
    _strip_profile_action_env(runtime)
    ok, out, _port = _configure_profile_api(runtime)
    if not ok:
        raise ValueError(f"runtime profile api config failed: {out}")
    _ensure_profile_toolsets(runtime)
    _ensure_profile_terminal_cwd(runtime)
    _prepare_runtime_profile_credentials(runtime, user_id, workspace_id)


def _resolve_chat_hermes_profile(
    template_slug: str,
    user_id: str = "",
    room_id: str = "",
    workspace_id: str = "",
) -> str:
    """Agent DM → per-user runtime profile; spaces and lanes keep the template slug."""
    template = resolve_validated_profile(template_slug)
    room_id = str(room_id or "").strip()
    user_id = str(user_id or "").strip()
    if not room_id or not user_id:
        return template
    conn = _workframe_db()
    try:
        room = conn.execute(
            "SELECT room_type, agent_profile_id, workspace_id FROM rooms WHERE id = ? AND deleted_at IS NULL",
            (room_id,),
        ).fetchone()
    finally:
        conn.close()
    if not room:
        return template
    if _is_space_room(str(room["room_type"]), room["agent_profile_id"]):
        return template
    agent_ref = str(room["agent_profile_id"] or "").strip()
    if str(room["room_type"]) != "direct" or not agent_ref:
        return template
    ws = str(workspace_id or room["workspace_id"] or "").strip()
    runtime = _runtime_profile_slug(user_id, template)
    if not _runtime_profile_on_disk(runtime):
        ensure_runtime_profile(runtime, template, user_id, ws)
    if not _runtime_profile_on_disk(runtime):
        raise ValueError("runtime_profile_not_provisioned")
    return runtime


def _migrate_v6_space_rooms(conn: sqlite3.Connection) -> None:
    applied = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version = '6' LIMIT 1",
    ).fetchone()
    if applied:
        return
    now = str(int(time.time()))
    conn.execute(
        """
        UPDATE rooms
        SET agent_profile_id = NULL, updated_at = ?
        WHERE deleted_at IS NULL
          AND room_type IN ('channel', 'group')
          AND agent_profile_id IS NOT NULL
        """,
        (now,),
    )
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('6', 'channel/group rooms are spaces not agent lanes', datetime('now'))
        """,
    )


def _is_space_room(room_type: str, agent_profile_id: str | None = None) -> bool:
    # ponytail: agent_profile_id ignored — legacy rows may still carry it; type defines a space.
    _ = agent_profile_id
    return str(room_type or "") in {"channel", "group"}


def _mention_handle(label: str, email: str = "") -> str:
    label = str(label or "").strip().lower()
    if label:
        handle = re.sub(r"[^a-z0-9]+", "", label.replace(" ", ""))
        if handle:
            return handle[:32]
    normalized = str(email or "").strip().lower()
    if normalized and "@" in normalized:
        local = normalized.split("@", 1)[0]
        handle = re.sub(r"[^a-z0-9]+", "", local)
        if handle:
            return handle[:32]
    return ""


def _ensure_agent_in_space_room(conn: sqlite3.Connection, room_id: str, agent_profile_id: str) -> bool:
    agent_profile_id = str(agent_profile_id or "").strip()
    room_id = str(room_id or "").strip()
    if not agent_profile_id or not room_id:
        return False
    existing = conn.execute(
        """
        SELECT id FROM room_memberships
        WHERE room_id = ? AND agent_profile_id = ? AND deleted_at IS NULL
        """,
        (room_id, agent_profile_id),
    ).fetchone()
    if existing:
        return False
    now = str(int(time.time()))
    conn.execute(
        """
        INSERT INTO room_memberships (id, room_id, agent_profile_id, role, status, joined_at, updated_at)
        VALUES (?, ?, ?, 'agent', 'active', ?, ?)
        """,
        (str(uuid.uuid4()), room_id, agent_profile_id, now, now),
    )
    return True


def _add_workspace_agents_to_space_rooms(conn: sqlite3.Connection, workspace_id: str, agent_profile_id: str) -> None:
    workspace_id = str(workspace_id or "").strip()
    agent_profile_id = str(agent_profile_id or "").strip()
    if not workspace_id or not agent_profile_id:
        return
    rooms = conn.execute(
        """
        SELECT id FROM rooms
        WHERE workspace_id = ? AND deleted_at IS NULL AND room_type IN ('channel', 'group')
        """,
        (workspace_id,),
    ).fetchall()
    for room in rooms:
        _ensure_agent_in_space_room(conn, str(room["id"]), agent_profile_id)


def _add_workspace_member_to_space_rooms(conn: sqlite3.Connection, workspace_id: str, user_id: str) -> int:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not workspace_id or not user_id:
        return 0
    rooms = conn.execute(
        """
        SELECT id FROM rooms
        WHERE workspace_id = ? AND deleted_at IS NULL AND room_type IN ('channel', 'group')
        """,
        (workspace_id,),
    ).fetchall()
    joined = 0
    for room in rooms:
        if _ensure_user_in_room(conn, str(room["id"]), user_id):
            joined += 1
    return joined


def _add_workspace_members_to_space_room(conn: sqlite3.Connection, workspace_id: str, room_id: str) -> int:
    workspace_id = str(workspace_id or "").strip()
    room_id = str(room_id or "").strip()
    if not workspace_id or not room_id:
        return 0
    members = conn.execute(
        """
        SELECT user_id FROM workspace_memberships
        WHERE workspace_id = ? AND deleted_at IS NULL AND status = 'active'
        """,
        (workspace_id,),
    ).fetchall()
    joined = 0
    for member in members:
        uid = str(member["user_id"] or "").strip()
        if uid and _ensure_user_in_room(conn, room_id, uid):
            joined += 1
    return joined


def _onboard_workspace_member_rooms(
    conn: sqlite3.Connection,
    workspace_id: str,
    user_id: str,
    *,
    inviter_user_id: str | None = None,
) -> dict[str, Any]:
    room_join = _join_workspace_default_room(
        conn,
        workspace_id,
        user_id,
        inviter_user_id=inviter_user_id,
    )
    spaces_joined = _add_workspace_member_to_space_rooms(conn, workspace_id, user_id)
    return {**room_join, "spaces_joined": spaces_joined}


def _migrate_v7_space_agent_members(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = '7' LIMIT 1").fetchone():
        return
    rooms = conn.execute(
        """
        SELECT id, workspace_id FROM rooms
        WHERE deleted_at IS NULL AND room_type IN ('channel', 'group')
        """,
    ).fetchall()
    for room in rooms:
        agents = conn.execute(
            """
            SELECT id FROM agent_profiles
            WHERE workspace_id = ? AND deleted_at IS NULL
            """,
            (str(room["workspace_id"]),),
        ).fetchall()
        for agent in agents:
            _ensure_agent_in_space_room(conn, str(room["id"]), str(agent["id"]))
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('7', 'workspace agents joined to space rooms as members', datetime('now'))
        """,
    )


def _migrate_v13_workspace_members_in_spaces(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = '13' LIMIT 1").fetchone():
        return
    rooms = conn.execute(
        """
        SELECT id, workspace_id FROM rooms
        WHERE deleted_at IS NULL AND room_type IN ('channel', 'group')
        """,
    ).fetchall()
    for room in rooms:
        _add_workspace_members_to_space_room(conn, str(room["workspace_id"]), str(room["id"]))
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('13', 'workspace members joined to all space rooms', datetime('now'))
        """,
    )


def _migrate_v8_room_avatars(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = '8' LIMIT 1").fetchone():
        return
    cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(rooms)")}
    if "avatar_url" not in cols:
        conn.execute("ALTER TABLE rooms ADD COLUMN avatar_url TEXT DEFAULT NULL")
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('8', 'room avatar_url for space settings', datetime('now'))
        """,
    )


def _migrate_v9_workspace_avatars(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = '9' LIMIT 1").fetchone():
        return
    cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(workspaces)")}
    if "avatar_url" not in cols:
        conn.execute("ALTER TABLE workspaces ADD COLUMN avatar_url TEXT DEFAULT NULL")
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('9', 'workspace avatar_url for workframe settings', datetime('now'))
        """,
    )


def _migrate_v11_delegation_kanban_boards(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = '11' LIMIT 1").fetchone():
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_delegation_grants (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            grantor_user_id TEXT NOT NULL,
            grantee_user_id TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'agents:delegate',
            expires_at TEXT DEFAULT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT DEFAULT NULL,
            FOREIGN KEY (workspace_id) REFERENCES workspaces (id)
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_delegation_grants_active
            ON agent_delegation_grants(workspace_id, grantor_user_id, grantee_user_id, scope)
            WHERE deleted_at IS NULL
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_kanban_boards (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            hermes_board_slug TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT DEFAULT NULL,
            FOREIGN KEY (workspace_id) REFERENCES workspaces (id)
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_kanban_board_active
            ON workspace_kanban_boards(workspace_id)
            WHERE deleted_at IS NULL
        """
    )
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('11', 'agent_delegation_grants and workspace_kanban_boards', datetime('now'))
        """
    )


def _install_key_owner_user_ids(conn: sqlite3.Connection) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for row in conn.execute(
        "SELECT owner_id FROM workspaces WHERE owner_id IS NOT NULL AND owner_id != '' AND status = 'active'",
    ):
        uid = str(row[0] or "").strip()
        if uid and uid not in seen:
            seen.add(uid)
            ordered.append(uid)
    for row in conn.execute(
        """
        SELECT DISTINCT user_id FROM workspace_memberships
        WHERE role = 'owner' AND status = 'active' AND user_id IS NOT NULL AND user_id != ''
        """,
    ):
        uid = str(row[0] or "").strip()
        if uid and uid not in seen:
            seen.add(uid)
            ordered.append(uid)
    return ordered


def _upsert_user_credential_binding(
    conn: sqlite3.Connection,
    user_id: str,
    provider: str,
    credential_type: str,
    credential_ref: str,
    label: str,
) -> str:
    now = _utc_now()
    existing = conn.execute(
        """SELECT id FROM credential_bindings
           WHERE user_id = ? AND provider = ? AND credential_type = ?
             AND credential_ref = ? AND deleted_at IS NULL
           ORDER BY updated_at DESC, created_at DESC LIMIT 1""",
        (user_id, provider, credential_type, credential_ref),
    ).fetchone()
    if existing:
        cred_id = str(existing[0])
        conn.execute(
            """UPDATE credential_bindings
               SET label = ?, is_active = 1, updated_at = ?, deleted_at = NULL
               WHERE id = ?""",
            (label, now, cred_id),
        )
        return cred_id
    cred_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO credential_bindings
           (id, workspace_id, user_id, agent_profile_id, provider, credential_type,
            credential_ref, label, is_active, created_by, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cred_id, None, user_id, None, provider, credential_type, credential_ref, label, 1, user_id, now, now),
    )
    return cred_id


def _adopt_install_llm_key_for_user(
    conn: sqlite3.Connection,
    user_id: str,
    provider_id: str,
    env_var: str,
    secret: str,
) -> bool:
    """Copy one Hermes-install LLM key into a user's personal store (idempotent)."""
    if _user_provider_connected(user_id, _catalog_provider(provider_id) or {"id": provider_id, "category": "llm"}):
        return False
    label = f"{provider_id} (from install)"
    payload = _store_user_credential(user_id, provider_id, "api_key", secret, env_var, label)
    _upsert_user_credential_binding(
        conn,
        user_id,
        provider_id,
        "api_key",
        str(payload["credential_ref"]),
        label,
    )
    return True


def _install_profile_slug() -> str:
    """Profile that holds legacy Hermes-install .env keys (native concierge)."""
    primary = _primary_profile()
    if primary:
        return primary
    for slug in (NATIVE_PROFILE, "workframe-agent"):
        if slug and (_profile_dir(slug) / ".env").is_file():
            return slug
    return primary


def _migrate_v12_adopt_install_keys_to_owners(conn: sqlite3.Connection) -> None:
    """Hermes install keys on the primary profile become the workspace owner's personal keys."""
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = '12' LIMIT 1").fetchone():
        return
    primary = _install_profile_slug()
    adopted = False
    if primary:
        stack_env = _read_env_map(_profile_dir(primary) / ".env")
        owner_ids = _install_key_owner_user_ids(conn)
        for owner_id in owner_ids:
            for spec in PROVIDER_CONNECT_CATALOG:
                if str(spec.get("category") or "") != "llm":
                    continue
                env_var = str(spec.get("env_var") or "").strip()
                secret = str(stack_env.get(env_var) or "").strip()
                if not env_var or not secret:
                    continue
                if _adopt_install_llm_key_for_user(
                    conn,
                    owner_id,
                    str(spec["id"]),
                    env_var,
                    secret,
                ):
                    adopted = True
        # ponytail: never strip install-profile .env — install keys stay on workframe-agent;
        # user keys live only in profiles/{user-uuid}/. Never copy from local host Hermes.
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('12', 'adopt primary-profile LLM install keys as owner personal keys', datetime('now'))
        """
    )


def _migrate_v10_workspace_settings_oauth(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = '10' LIMIT 1").fetchone():
        return
    cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(workspaces)")}
    if "settings_json" not in cols:
        conn.execute("ALTER TABLE workspaces ADD COLUMN settings_json TEXT NOT NULL DEFAULT '{}'")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS oauth_pending_states (
            state TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            code_verifier TEXT NOT NULL,
            workspace_id TEXT DEFAULT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('10', 'workspace settings_json and oauth_pending_states for user GitHub OAuth', datetime('now'))
        """,
    )


def _ensure_oauth_pending_table() -> None:
    conn = _workframe_db()
    try:
        _migrate_v10_workspace_settings_oauth(conn)
        _migrate_v11_delegation_kanban_boards(conn)
        _migrate_v12_adopt_install_keys_to_owners(conn)
        _migrate_v13_workspace_members_in_spaces(conn)
        conn.commit()
    finally:
        conn.close()


def _room_agents_for_mentions(conn: sqlite3.Connection, room_id: str, workspace_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT ap.id, ap.slug, ap.display_name, ap.model_provider, ap.model_name
        FROM room_memberships rm
        JOIN agent_profiles ap ON ap.id = rm.agent_profile_id
        WHERE rm.room_id = ? AND rm.deleted_at IS NULL AND ap.deleted_at IS NULL
        """,
        (room_id,),
    ).fetchall()
    if rows:
        return [dict(row) for row in rows]
    # ponytail: until membership backfill completes, allow all workspace agents in spaces
    fallback = conn.execute(
        """
        SELECT id, slug, display_name, model_provider, model_name
        FROM agent_profiles
        WHERE workspace_id = ? AND deleted_at IS NULL
        """,
        (workspace_id,),
    ).fetchall()
    return [dict(row) for row in fallback]


def _room_users_for_mentions(conn: sqlite3.Connection, room_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT u.id, u.display_name, u.email
        FROM room_memberships rm
        JOIN users u ON u.id = rm.user_id
        WHERE rm.room_id = ? AND rm.deleted_at IS NULL AND rm.user_id IS NOT NULL
        """,
        (room_id,),
    ).fetchall()
    users: list[dict[str, Any]] = []
    for row in rows:
        users.append(
            {
                "id": str(row["id"]),
                "display_name": str(row["display_name"] or ""),
                "email": str(row["email"] or ""),
                "handle": _mention_handle(str(row["display_name"] or ""), str(row["email"] or "")),
            }
        )
    return users


def _parse_room_mentions(
    text: str,
    agents: list[dict[str, Any]],
    users: list[dict[str, Any]],
    *,
    triggered_by_user_id: str = "",
    workspace_id: str = "",
) -> dict[str, list[dict[str, Any]]]:
    """Resolve @handles in a space message to agents (invoke) and users (notify-only)."""
    handles = {m.group(1).lower() for m in re.finditer(r"@([\w-]+)", str(text or ""))}
    if not handles:
        return {"agents": [], "users": []}
    agent_by_handle: dict[str, dict[str, Any]] = {}
    for agent in agents:
        slug = str(agent.get("slug") or "").strip().lower()
        if slug:
            agent_by_handle[slug] = agent
        display = str(agent.get("display_name") or "").strip().lower()
        if display:
            agent_by_handle[display] = agent
            compact = re.sub(r"[^a-z0-9]+", "", display)
            if compact:
                agent_by_handle[compact] = agent
        if triggered_by_user_id and slug:
            personal = _runtime_display_label(triggered_by_user_id, slug, workspace_id).strip().lower()
            if personal:
                agent_by_handle[personal] = agent
                personal_compact = re.sub(r"[^a-z0-9]+", "", personal)
                if personal_compact:
                    agent_by_handle[personal_compact] = agent
    user_by_handle = {str(u["handle"]).lower(): u for u in users if u.get("handle")}
    matched_agents: list[dict[str, Any]] = []
    seen_agents: set[str] = set()
    for handle in handles:
        agent = agent_by_handle.get(handle)
        if agent and str(agent["id"]) not in seen_agents:
            seen_agents.add(str(agent["id"]))
            matched_agents.append(agent)
    matched_users: list[dict[str, Any]] = []
    seen_users: set[str] = set()
    for handle in handles:
        user = user_by_handle.get(handle)
        if user and str(user["id"]) not in seen_users:
            seen_users.add(str(user["id"]))
            matched_users.append(user)
    return {"agents": matched_agents, "users": matched_users}


def _room_recent_transcript(conn: sqlite3.Connection, room_id: str, limit: int = 24) -> str:
    rows = conn.execute(
        """
        SELECT m.content, u.display_name AS user_name, ap.display_name AS agent_name
        FROM messages m
        LEFT JOIN users u ON u.id = m.sender_user_id
        LEFT JOIN agent_profiles ap ON ap.id = m.sender_agent_id
        WHERE m.room_id = ? AND m.deleted_at IS NULL
        ORDER BY m.created_at DESC
        LIMIT ?
        """,
        (room_id, limit),
    ).fetchall()
    lines: list[str] = []
    for row in reversed(rows):
        name = str(row["user_name"] or row["agent_name"] or "Member")
        lines.append(f"{name}: {row['content']}")
    return "\n".join(lines)


def _inject_turn_credentials(
    turn_body: dict[str, Any],
    user_id: str,
    workspace_id: str,
    provider: str = "openrouter",
) -> None:
    resolved = _resolve_credential(user_id, workspace_id, provider)
    if not resolved:
        return
    turn_body["_credential_override"] = resolved["credential_ref"]
    turn_body["_credential_scope"] = resolved["scope"]


def _live_stream_text(data: dict[str, Any]) -> str:
    return str(data.get("delta") or data.get("text") or data.get("content") or "")


def _live_strip_placeholders(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        segment
        for segment in segments
        if not (
            segment.get("kind") == "text"
            and str(segment.get("text") or "") in ("Thinking…", "…", "")
        )
    ]


def _live_reduce_stream_event(
    segments: list[dict[str, Any]],
    event: str,
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    if event in ("thinking.delta", "reasoning.delta"):
        text = _live_stream_text(data)
        if not text:
            return segments
        base = _live_strip_placeholders(segments)
        if base and base[-1].get("kind") == "thinking":
            merged = dict(base[-1])
            merged["text"] = str(merged.get("text") or "") + text
            return [*base[:-1], merged]
        return [*base, {"kind": "thinking", "text": text}]
    if event in ("message.delta", "assistant.delta"):
        text = _live_stream_text(data)
        if not text:
            return segments
        base = _live_strip_placeholders(segments)
        if base and base[-1].get("kind") == "text":
            merged = dict(base[-1])
            merged["text"] = str(merged.get("text") or "") + text
            return [*base[:-1], merged]
        return [*base, {"kind": "text", "text": text}]
    if event == "tool.started":
        name = str(data.get("tool_name") or "tool")
        preview = str(data.get("preview") or "")
        base = _live_strip_placeholders(segments)
        for idx in range(len(base) - 1, -1, -1):
            segment = base[idx]
            if segment.get("kind") == "tool" and segment.get("name") == name:
                updated = dict(segment)
                updated["status"] = "running"
                if preview:
                    updated["preview"] = preview
                return [*base[:idx], updated, *base[idx + 1 :]]
        tool = {"kind": "tool", "name": name, "status": "running"}
        if preview:
            tool["preview"] = preview
        return [*base, tool]
    if event in ("tool.completed", "tool.failed"):
        name = str(data.get("tool_name") or "tool")
        output = str(data.get("preview") or data.get("output") or "")
        base = _live_strip_placeholders(segments)
        for idx in range(len(base) - 1, -1, -1):
            segment = base[idx]
            if segment.get("kind") == "tool" and segment.get("name") == name:
                updated = dict(segment)
                updated["status"] = "done"
                updated["output"] = output or str(segment.get("output") or segment.get("preview") or "")
                updated.pop("preview", None)
                return [*base[:idx], updated, *base[idx + 1 :]]
        return [*base, {"kind": "tool", "name": name, "status": "done", "output": output}]
    if event == "tool.progress":
        name = str(data.get("tool_name") or "tool")
        if name == "_thinking":
            return segments
        preview = _live_stream_text(data)
        base = _live_strip_placeholders(segments)
        for idx in range(len(base) - 1, -1, -1):
            segment = base[idx]
            if segment.get("kind") == "tool" and segment.get("name") == name:
                updated = dict(segment)
                updated["status"] = "running"
                if preview:
                    updated["preview"] = preview
                return [*base[:idx], updated, *base[idx + 1 :]]
        tool = {"kind": "tool", "name": name, "status": "running"}
        if preview:
            tool["preview"] = preview
        return [*base, tool]
    if event in ("message.complete", "assistant.completed"):
        final = str(data.get("content") or data.get("text") or "").strip()
        if not final:
            return segments
        base = _live_strip_placeholders(segments)
        if base and base[-1].get("kind") == "text":
            merged = dict(base[-1])
            merged["text"] = final
            return [*base[:-1], merged]
        return [*base, {"kind": "text", "text": final}]
    if event == "error":
        text = str(data.get("error") or data.get("message") or "Stream error")
        return _live_strip_placeholders(segments) + [{"kind": "text", "text": text}]
    return segments


def _segments_to_reply_text(segments: list[dict[str, Any]]) -> str:
    return "".join(
        str(segment.get("text") or "")
        for segment in segments
        if segment.get("kind") == "text"
    ).strip()


def _parse_profile_stream_frame(frame: bytes) -> tuple[str, dict[str, Any]] | None:
    text = frame.decode("utf-8", errors="replace")
    lines = text.splitlines()
    event_name = ""
    data_lines: list[str] = []
    for line in lines:
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if not event_name and not data_lines:
        return None
    data: dict[str, Any] = {}
    if data_lines:
        try:
            parsed = json.loads("\n".join(data_lines))
            data = parsed if isinstance(parsed, dict) else {"text": str(parsed)}
        except Exception:  # noqa: BLE001
            data = {"text": "\n".join(data_lines)}
    normalized = event_name
    if event_name in ("assistant.delta", "message.delta"):
        normalized = "message.delta"
    elif event_name in ("assistant.completed", "message.complete"):
        normalized = "message.complete"
    elif event_name in ("thinking.delta", "reasoning.delta"):
        normalized = "thinking.delta"
    return normalized, data


def _iter_profile_stream_frames(upstream: Any) -> Iterator[tuple[str, dict[str, Any]]]:
    buffer = b""
    while True:
        chunk = upstream.read(4096)
        if not chunk:
            break
        buffer += chunk
        while True:
            sep = buffer.find(b"\n\n")
            crlf_sep = buffer.find(b"\r\n\r\n")
            if sep == -1 and crlf_sep == -1:
                break
            if crlf_sep != -1 and (sep == -1 or crlf_sep < sep):
                idx = crlf_sep
                delimiter_len = 4
            else:
                idx = sep
                delimiter_len = 2
            frame = buffer[:idx]
            buffer = buffer[idx + delimiter_len :]
            parsed = _parse_profile_stream_frame(frame)
            if parsed:
                yield parsed
    tail = buffer.strip()
    if tail:
        parsed = _parse_profile_stream_frame(tail)
        if parsed:
            yield parsed


def _invoke_room_agent_mention(
    room_id: str,
    workspace_id: str,
    agent_row: dict[str, Any],
    triggered_by_user_id: str,
    parent_message_id: str,
) -> None:
    """Stream a tagged agent turn in a shared space room; fan out live updates to room subscribers."""
    template_slug = str(agent_row.get("slug") or "").strip()
    agent_db_id = str(agent_row.get("id") or "").strip()
    agent_name = str(agent_row.get("display_name") or template_slug).strip() or template_slug
    if triggered_by_user_id:
        personal = _runtime_display_label(triggered_by_user_id, template_slug, workspace_id)
        if personal:
            agent_name = personal
    if not template_slug or not agent_db_id:
        return
    hermes_slug = _runtime_profile_slug(triggered_by_user_id, template_slug)
    ensure_runtime_profile(hermes_slug, template_slug, triggered_by_user_id, workspace_id)

    turn_id = str(uuid.uuid4())
    segments: list[dict[str, Any]] = []
    last_flush = 0.0
    flush_interval = 0.05
    run_id = str(uuid.uuid4())
    session_id = ""
    user_text = ""

    def publish_update(*, force: bool = False, status: str | None = None) -> None:
        nonlocal last_flush
        now = time.time()
        if not force and (now - last_flush) < flush_interval:
            return
        payload: dict[str, Any] = {
            "type": "turn.update",
            "turn_id": turn_id,
            "room_id": room_id,
            "segments": segments,
        }
        if status:
            payload["status"] = status
        _room_live_publish(room_id, payload)
        _room_live_set_turn(
            {
                "type": "turn.snapshot",
                "turn_id": turn_id,
                "room_id": room_id,
                "agent_slug": hermes_slug,
                "agent_name": agent_name,
                "agent_profile_id": agent_db_id,
                "segments": segments,
                "status": status or "",
            }
        )
        last_flush = now

    def finish_turn(message_id: str = "") -> None:
        _room_live_publish(
            room_id,
            {
                "type": "turn.complete",
                "turn_id": turn_id,
                "room_id": room_id,
                "message_id": message_id,
            },
        )
        _room_live_clear_turn(turn_id)

    def fail_turn(error: str, *, persist: bool = True) -> None:
        segments[:] = _live_reduce_stream_event(segments, "error", {"error": error})
        publish_update(force=True, status="error")
        if persist:
            try:
                conn = _workframe_db()
                try:
                    now_ts = str(int(time.time()))
                    mid = str(uuid.uuid4())
                    conn.execute(
                        """
                        INSERT INTO messages (
                            id, room_id, sender_user_id, sender_agent_id, parent_message_id,
                            content, content_type, is_edited, created_at, updated_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            mid,
                            room_id,
                            None,
                            agent_db_id,
                            parent_message_id,
                            error,
                            "text",
                            0,
                            now_ts,
                            now_ts,
                        ),
                    )
                    conn.execute("UPDATE rooms SET updated_at = ? WHERE id = ?", (now_ts, room_id))
                    conn.commit()
                    _bump_workspace_event_state()
                    finish_turn(mid)
                    return
                finally:
                    conn.close()
            except Exception:  # noqa: BLE001
                pass
        _room_live_publish(
            room_id,
            {
                "type": "turn.error",
                "turn_id": turn_id,
                "room_id": room_id,
                "error": error,
                "segments": segments,
            },
        )
        finish_turn()

    try:
        conn = _workframe_db()
        try:
            parent = conn.execute(
                "SELECT content FROM messages WHERE id = ? AND room_id = ? AND deleted_at IS NULL",
                (parent_message_id, room_id),
            ).fetchone()
            user_text = str(parent["content"] or "").strip() if parent else ""
        finally:
            conn.close()

        _room_live_publish(
            room_id,
            {
                "type": "turn.started",
                "turn_id": turn_id,
                "room_id": room_id,
                "agent_slug": hermes_slug,
                "agent_name": agent_name,
                "agent_profile_id": agent_db_id,
                "triggered_by_user_id": triggered_by_user_id,
            },
        )
        _room_live_set_turn(
            {
                "type": "turn.snapshot",
                "turn_id": turn_id,
                "room_id": room_id,
                "agent_slug": hermes_slug,
                "agent_name": agent_name,
                "agent_profile_id": agent_db_id,
                "segments": segments,
                "status": "starting",
            }
        )

        session = profile_chat_session(
            hermes_slug,
            {
                "room_id": room_id,
                "source_id": "room",
                "client_id": room_id,
            },
            triggered_by_user_id,
        )
        session_id = str(session.get("session_id") or "").strip()
        if not session_id:
            raise ValueError("session_bootstrap_failed: could not start agent session for this room")

        turn_body = _profile_turn_payload(hermes_slug, user_text, room_id)
        provider = str(agent_row.get("model_provider") or "openrouter")
        _overlay_turn_provider_env(hermes_slug, triggered_by_user_id, workspace_id, provider, run_id)
        _overlay_turn_user_env(hermes_slug, triggered_by_user_id, workspace_id, run_id)
        _inject_turn_credentials(turn_body, triggered_by_user_id, workspace_id, provider)
        if not _wait_profile_api_healthy(hermes_slug, attempts=20, delay=0.25):
            raise ValueError("profile api unavailable after session bootstrap")
        _ensure_profile_proxy_headers(hermes_slug)

        upstream_body = json.dumps(turn_body).encode("utf-8")
        port = _profile_api_port(hermes_slug)
        url = f"http://gateway:{port}/api/sessions/{urllib.parse.quote(session_id, safe='')}/chat/stream"
        headers = {
            "Authorization": f"Bearer {_profile_api_key(hermes_slug)}",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, data=upstream_body, headers=headers, method="POST")
        upstream = urllib.request.urlopen(req, timeout=3600)

        final_text = ""
        try:
            publish_update(force=True, status="thinking")
            for event_name, data in _iter_profile_stream_frames(upstream):
                segments[:] = _live_reduce_stream_event(segments, event_name, data)
                if event_name in ("message.delta", "assistant.delta"):
                    final_text += _live_stream_text(data)
                    publish_update(status="writing")
                elif event_name in ("thinking.delta", "reasoning.delta"):
                    publish_update(status="thinking")
                elif event_name == "tool.started":
                    publish_update(force=True, status=f"tool:{data.get('tool_name') or 'tool'}")
                elif event_name in ("tool.completed", "tool.failed", "tool.progress"):
                    publish_update(force=True)
                elif event_name in ("message.complete", "assistant.completed"):
                    final_text = str(data.get("content") or data.get("text") or final_text)
                    publish_update(force=True, status="writing")
            publish_update(force=True)
        finally:
            upstream.close()

        assistant = final_text.strip() or _segments_to_reply_text(segments)
        if not assistant:
            raise ValueError("empty assistant response")

        conn = _workframe_db()
        try:
            now_ts = str(int(time.time()))
            mid = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO messages (
                    id, room_id, sender_user_id, sender_agent_id, parent_message_id,
                    content, content_type, is_edited, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    mid,
                    room_id,
                    None,
                    agent_db_id,
                    parent_message_id,
                    assistant,
                    "text",
                    0,
                    now_ts,
                    now_ts,
                ),
            )
            conn.execute("UPDATE rooms SET updated_at = ? WHERE id = ?", (now_ts, room_id))
            conn.commit()
        finally:
            conn.close()
        _bump_workspace_event_state()
        finish_turn(mid)
        _log_agent_run(
            run_id,
            agent_db_id,
            room_id,
            triggered_by_user_id,
            session_id,
            "completed",
            provider,
            str(agent_row.get("model_name") or "default"),
            error=None,
        )
        chat_dispatch(
            {
                "profile": hermes_slug,
                "session_id": session_id,
                "gateway_session_id": f"api:{hermes_slug}:{session_id}",
                "room_id": room_id,
                "user_id": triggered_by_user_id,
                "source_id": "room",
                "client_id": room_id,
                "text": user_text[:240],
            }
        )
    except Exception as exc:  # noqa: BLE001
        err_text = str(exc)
        if "no_llm_provider_for_user" in err_text:
            reply = (
                "I can't reply yet — the member who @mentioned me needs to connect an LLM provider "
                "(Profile → Connect accounts → OpenRouter or another model provider)."
            )
        else:
            reply = err_text
        try:
            _log_agent_run(
                run_id,
                agent_db_id,
                room_id,
                triggered_by_user_id,
                session_id,
                "failed",
                str(agent_row.get("model_provider") or "openrouter"),
                str(agent_row.get("model_name") or "default"),
                error=err_text,
            )
        except Exception:  # noqa: BLE001
            pass
        fail_turn(reply)
    finally:
        _revoke_turn_credential_lease(run_id, hermes_slug)


def _process_space_message_mentions(
    room_id: str,
    workspace_id: str,
    user_id: str,
    content: str,
    message_id: str,
    *,
    invoke_agents: bool = True,
) -> dict[str, Any]:
    conn = _workframe_db()
    try:
        agents = _room_agents_for_mentions(conn, room_id, workspace_id)
        users = _room_users_for_mentions(conn, room_id)
    finally:
        conn.close()
    mentions = _parse_room_mentions(content, agents, users, triggered_by_user_id=user_id, workspace_id=workspace_id)
    invoked: list[str] = []
    for agent in mentions["agents"]:
        invoked.append(str(agent["slug"]))
        if invoke_agents:
            threading.Thread(
                target=_invoke_room_agent_mention,
                kwargs={
                    "room_id": room_id,
                    "workspace_id": workspace_id,
                    "agent_row": agent,
                    "triggered_by_user_id": user_id,
                    "parent_message_id": message_id,
                },
                daemon=True,
            ).start()
    return {
        "agent_mentions": invoked,
        "user_mentions": [str(u.get("handle") or "") for u in mentions["users"]],
    }


def _enrich_room_messages(conn: sqlite3.Connection, messages: list[Any]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in messages:
        item = dict(row)
        agent_id = str(item.get("sender_agent_id") or "").strip()
        if agent_id:
            agent = conn.execute(
                "SELECT slug, display_name FROM agent_profiles WHERE id = ? AND deleted_at IS NULL",
                (agent_id,),
            ).fetchone()
            if agent:
                item["sender_agent_slug"] = str(agent["slug"])
                item["sender_agent_name"] = str(agent["display_name"] or agent["slug"])
        enriched.append(item)
    return enriched


def _enrich_room_members(conn: sqlite3.Connection, members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for member in members:
        row = dict(member)
        user_id = str(row.get("user_id") or "").strip()
        agent_id = str(row.get("agent_profile_id") or "").strip()
        if user_id:
            user = conn.execute(
                "SELECT display_name, email, avatar_url FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if user:
                row["display_name"] = user["display_name"]
                row["email"] = user["email"]
                prof = _zk.get_profile(user_id)
                zk_avatar = str(prof.get("avatar_url") or "").strip() if isinstance(prof, dict) else ""
                if zk_avatar:
                    row["avatar_url"] = _normalize_user_avatar_url(zk_avatar)
                else:
                    row["avatar_url"] = user["avatar_url"]
                row["handle"] = _mention_handle(str(user["display_name"] or ""), str(user["email"] or ""))
        if agent_id:
            agent = conn.execute(
                "SELECT slug, display_name FROM agent_profiles WHERE id = ? AND deleted_at IS NULL",
                (agent_id,),
            ).fetchone()
            if agent:
                row["display_name"] = agent["display_name"]
                row["hermes_profile"] = agent["slug"]
                label = str(agent["display_name"] or agent["slug"] or "").strip()
                row["mention_handle"] = _mention_handle(label, str(agent["slug"] or "")) or str(agent["slug"] or "")
                row["handle"] = row["mention_handle"]
        enriched.append(row)
    return enriched


def _validate_me_profile_updates(updates: dict[str, Any]) -> None:
  """Reject oversized avatar payloads before they hit SQLite or nginx limits."""
  avatar = updates.get("avatar_url")
  if avatar is None:
    return
  text = str(avatar).strip()
  if not text:
    return
  if text.startswith("data:") and len(text) > 380_000:
    raise ValueError("Avatar image is too large. Use an image under 256 KB.")
  if len(text) > 400_000:
    raise ValueError("Avatar image is too large. Use an image under 256 KB.")


def _apply_me_profile_updates(user_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """PATCH /api/me — zk profile fields + workframe platform_ids."""
    user_id = str(user_id or "").strip()
    allowed = {"display_name", "avatar_url", "tagline", "bio"}
    updates = {k: v for k, v in body.items() if k in allowed}
    _validate_me_profile_updates(updates)
    if "avatar_url" in updates:
        updates["avatar_url"] = _normalize_user_avatar_url(str(updates.get("avatar_url") or ""))
    profile = _zk.update_profile(user_id, updates) if updates else _zk.get_profile(user_id)
    if "platform_ids" in body:
        platform_ids = _parse_user_platform_ids(body.get("platform_ids"))
        conn = _workframe_db()
        try:
            now_ts = str(int(time.time()))
            conn.execute(
                "UPDATE users SET platform_ids = ?, updated_at = ? WHERE id = ?",
                (json.dumps(platform_ids, sort_keys=True), now_ts, user_id),
            )
            conn.commit()
            workspaces = _get_user_workspaces(user_id)
            current = _resolve_current_workspace(user_id, workspaces)
            if current and str(current.get("id") or ""):
                sync_result = _sync_workspace_messaging_gateway(str(current["id"]))
                if not sync_result.get("ok"):
                    raise ValueError(str(sync_result.get("error") or "messaging_sync_failed"))
        finally:
            conn.close()
    _sync_workframe_user_profile(user_id, updates)
    return profile or {}


def _sync_workframe_user_profile(user_id: str, fields: dict[str, Any]) -> None:
    """Mirror zk profile fields onto workframe.db users for member lists."""
    user_id = str(user_id or "").strip()
    if not user_id or not fields:
        return
    conn = _workframe_db()
    try:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return
        sets: list[str] = []
        vals: list[Any] = []
        if "avatar_url" in fields:
            sets.append("avatar_url = ?")
            vals.append(fields["avatar_url"])
        if "display_name" in fields:
            sets.append("display_name = ?")
            vals.append(fields["display_name"])
        if "platform_ids" in fields:
            sets.append("platform_ids = ?")
            vals.append(json.dumps(fields["platform_ids"], sort_keys=True))
        if not sets:
            return
        sets.append("updated_at = ?")
        vals.append(str(int(time.time())))
        vals.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", vals)
        conn.commit()
    finally:
        conn.close()


def _sync_agent_profile_db(profile: str, fields: dict[str, Any]) -> None:
    """Mirror Hermes registry metadata onto workframe.db agent_profiles."""
    slug = safe_profile_slug(profile)
    if not slug or not fields:
        return
    column_map = {
        "display_name": "display_name",
        "tagline": "tagline",
        "role": "role",
        "avatar_url": "avatar_url",
    }
    updates = {column: fields[key] for key, column in column_map.items() if key in fields}
    if not updates:
        return
    conn = _workframe_db()
    try:
        now_ts = str(int(time.time()))
        sets = [f"{col} = ?" for col in updates]
        vals = list(updates.values()) + [now_ts, slug]
        conn.execute(
            f"UPDATE agent_profiles SET {', '.join(sets)}, updated_at = ? WHERE slug = ? AND deleted_at IS NULL",
            vals,
        )
        conn.commit()
    finally:
        conn.close()


def _join_workspace_default_room(
    conn: sqlite3.Connection,
    workspace_id: str,
    user_id: str,
    *,
    inviter_user_id: str | None = None,
) -> dict[str, Any]:
    room = _default_workspace_room(conn, workspace_id)
    if not room:
        return {"room_id": None, "joined": False}
    room_id = str(room["id"])
    joined = _ensure_user_in_room(conn, room_id, user_id)
    inviter_joined = False
    if inviter_user_id and inviter_user_id != user_id:
        inviter_joined = _ensure_user_in_room(conn, room_id, inviter_user_id)
    return {
        "room_id": room_id,
        "room_slug": str(room["slug"]),
        "joined": joined,
        "inviter_joined": inviter_joined,
    }


def _ensure_user_dm_room(
    conn: sqlite3.Connection,
    workspace_id: str,
    user_a: str,
    user_b: str,
) -> dict[str, Any]:
    """Idempotent DM between two workspace users (no agent)."""
    left_id, right_id = sorted([str(user_a).strip(), str(user_b).strip()])
    if not left_id or not right_id or left_id == right_id:
        return {"room_id": None, "created": False}
    existing = conn.execute(
        """
        SELECT id FROM rooms
        WHERE workspace_id = ?
          AND room_type = 'direct'
          AND deleted_at IS NULL
          AND agent_profile_id IS NULL
          AND EXISTS (
              SELECT 1 FROM room_memberships rm
              WHERE rm.room_id = rooms.id AND rm.deleted_at IS NULL AND rm.user_id = ?
          )
          AND EXISTS (
              SELECT 1 FROM room_memberships rm
              WHERE rm.room_id = rooms.id AND rm.deleted_at IS NULL AND rm.user_id = ?
          )
          AND NOT EXISTS (
              SELECT 1 FROM room_memberships rm
              WHERE rm.room_id = rooms.id AND rm.deleted_at IS NULL AND rm.user_id NOT IN (?, ?)
          )
        LIMIT 1
        """,
        (workspace_id, left_id, right_id, left_id, right_id),
    ).fetchone()
    if existing:
        return {"room_id": str(existing["id"]), "created": False}
    now = str(int(time.time()))
    room_id = str(uuid.uuid4())
    slug = _normalize_room_slug(f"dm-{left_id}-{right_id}", "dm")
    conn.execute(
        """
        INSERT INTO rooms
            (id, workspace_id, agent_profile_id, name, slug, topic, room_type, status, created_by, created_at, updated_at)
        VALUES (?, ?, NULL, ?, ?, '', 'direct', 'active', ?, ?, ?)
        """,
        (room_id, workspace_id, f"DM", slug, left_id, now, now),
    )
    for uid in (left_id, right_id):
        _ensure_user_in_room(conn, room_id, uid)
    return {"room_id": room_id, "created": True}


def _promote_workspace_owner_if_unclaimed(conn: sqlite3.Connection, workspace_id: str, user_id: str) -> bool:
    if not _install_window_open():
        return False
    row = conn.execute(
        "SELECT owner_id FROM workspaces WHERE id = ? AND deleted_at IS NULL",
        (workspace_id,),
    ).fetchone()
    if not row:
        return False
    if str(row["owner_id"] or "").strip():
        return False
    now = str(int(time.time()))
    conn.execute(
        "UPDATE workspaces SET owner_id = ?, updated_at = ? WHERE id = ?",
        (user_id, now, workspace_id),
    )
    mem = conn.execute(
        "SELECT id FROM workspace_memberships WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL",
        (workspace_id, user_id),
    ).fetchone()
    if mem:
        conn.execute(
            "UPDATE workspace_memberships SET role = ?, updated_at = ? WHERE id = ?",
            ("owner", now, mem["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO workspace_memberships
            (id, workspace_id, user_id, role, status, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (str(uuid.uuid4()), workspace_id, user_id, "owner", "active", now, now),
        )
    return True


def _sync_workspace_home_room(conn: sqlite3.Connection, workspace_id: str) -> None:
    """Keep slug=general space aligned with workspace display_name, tagline, avatar."""
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return
    ws_row = conn.execute(
        "SELECT display_name, avatar_url, settings_json FROM workspaces WHERE id = ? AND deleted_at IS NULL",
        (workspace_id,),
    ).fetchone()
    if not ws_row:
        return
    settings = _parse_workspace_settings(ws_row)
    name = str(ws_row["display_name"] or "").strip() or "Workspace"
    tagline = str(settings.get("tagline") or "").strip()
    avatar = str(ws_row["avatar_url"] or "").strip() or None
    now = str(int(time.time()))
    room = conn.execute(
        """
        SELECT id FROM rooms
        WHERE workspace_id = ? AND slug = 'general' AND deleted_at IS NULL
        """,
        (workspace_id,),
    ).fetchone()
    if room:
        conn.execute(
            """
            UPDATE rooms
            SET name = ?, topic = ?, avatar_url = COALESCE(?, avatar_url), updated_at = ?
            WHERE id = ?
            """,
            (name, tagline, avatar, now, str(room["id"])),
        )


def _ensure_default_workspace() -> bool:
    """Idempotent first-run DB seed: Workframe workspace + native agent + General room."""
    project_name = str(os.environ.get("WORKFRAME_PROJECT", "Workframe") or "Workframe").strip() or "Workframe"
    native_slug = str(NATIVE_PROFILE or "workframe-agent").strip() or "workframe-agent"
    native_display = f"{project_name} Agent"
    conn = _workframe_db()
    try:
        ws = conn.execute(
            "SELECT id FROM workspaces WHERE slug = 'default' AND deleted_at IS NULL",
        ).fetchone()
        now = str(int(time.time()))
        if not ws:
            ws_id = str(uuid.uuid4())
            settings = json.dumps({
                "credential_mode": "byok",
                "admin_onboarding_done": False,
                "admin_integrations_done": False,
            })
            ws_logo = _pick_logo_url() or None
            conn.execute(
                """
                INSERT INTO workspaces (
                    id, slug, display_name, description, owner_id, status,
                    settings_json, avatar_url, created_at, updated_at
                ) VALUES (?, 'default', ?, '', '', 'active', ?, ?, ?, ?)
                """,
                (ws_id, project_name, settings, ws_logo, now, now),
            )
        else:
            ws_id = str(ws["id"])
        ws_row = conn.execute(
            "SELECT display_name, avatar_url, settings_json FROM workspaces WHERE id = ?",
            (ws_id,),
        ).fetchone()
        settings = _parse_workspace_settings(ws_row) if ws_row else {}
        home_name = str(ws_row["display_name"] or "").strip() if ws_row else project_name
        home_name = home_name or project_name
        home_tagline = str(settings.get("tagline") or "").strip()
        home_avatar = str(ws_row["avatar_url"] or "").strip() if ws_row else ""
        if not home_avatar:
            home_avatar = _pick_logo_url() or ""
        room = conn.execute(
            """
            SELECT id FROM rooms
            WHERE workspace_id = ? AND slug = 'general' AND deleted_at IS NULL
            """,
            (ws_id,),
        ).fetchone()
        if not room:
            conn.execute(
                """
                INSERT INTO rooms (
                    id, workspace_id, name, slug, topic, avatar_url, room_type, status, created_at, updated_at
                ) VALUES (?, ?, ?, 'general', ?, ?, 'channel', 'active', ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    ws_id,
                    home_name,
                    home_tagline,
                    home_avatar or None,
                    now,
                    now,
                ),
            )
        _sync_workspace_home_room(conn, ws_id)
        conn.commit()
    finally:
        conn.close()
    _ensure_workspace_agent_profile_row(
        native_slug,
        display_name=native_display,
        role="native",
        is_native=True,
    )
    return True


def _bootstrap_after_setup(agent_personality: str = "") -> dict[str, Any]:
    """ponytail: verify native gateway after setup; optional SOUL overlay from onboarding text."""
    profile = _primary_profile()
    result: dict[str, Any] = {"profile": profile}
    personality = str(agent_personality or "").strip()
    if personality:
        _seed_native_user_overlay(profile, profile, user_soul=personality)
        result["soul_seeded"] = True
    return result


def current_user_me(user_id: str) -> dict[str, Any]:
    """Return the authenticated user and their active workspace memberships."""
    if not user_id:
        return {"ok": False, "error": "no_authenticated_user"}
    try:
        conn = _workframe_db()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"workframe_db_unavailable: {exc}"}
    try:
        user = conn.execute(
            """
            SELECT id, email, display_name, avatar_url, role, status, created_at, updated_at
            FROM users
            WHERE id = ? AND deleted_at IS NULL AND status = 'active'
            """,
            (user_id,),
        ).fetchone()
        if not user:
            return {"ok": False, "error": "user_not_found", "user_id": user_id}
        memberships = conn.execute(
            """
            SELECT DISTINCT
                wm.id,
                wm.workspace_id,
                wm.role,
                wm.status,
                wm.created_at AS membership_created_at,
                wm.updated_at AS membership_updated_at,
                w.slug,
                w.display_name
            FROM workspace_memberships wm
            JOIN workspaces w ON w.id = wm.workspace_id
            WHERE wm.user_id = ?
              AND wm.deleted_at IS NULL
              AND wm.status = 'active'
              AND w.deleted_at IS NULL
              AND w.status = 'active'
            ORDER BY w.slug, w.display_name
            """,
            (user_id,),
        ).fetchall()
        return {
            "ok": True,
            "user": _user_payload(user),
            "workspace_memberships": [_workspace_membership_payload(row) for row in memberships],
        }
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"current_user_lookup_failed: {exc}"}
    finally:
        conn.close()


def _role_allows(handler: BaseHTTPRequestHandler, roles: set[str]) -> bool:
    """Return True when the current authenticated role is allowed."""
    if not SECURE_MODE:
        return True
    return str(getattr(handler, "auth_role", "")) in roles


def _handler_is_active_workspace_member(handler: BaseHTTPRequestHandler, workspace_id: str = "") -> bool:
    """Any active workspace member (not only owner/admin)."""
    if not SECURE_MODE:
        return True
    if _role_allows(handler, OWNER_ADMIN_ROLES):
        return True
    user_id = str(getattr(handler, "auth_user", "") or "").strip()
    if not user_id:
        return False
    try:
        conn = _workframe_db()
        try:
            ws_id = str(workspace_id or "").strip()
            if ws_id:
                return _workspace_member_role(conn, ws_id, user_id) is not None
            row = conn.execute(
                """
                SELECT 1 FROM workspace_memberships
                WHERE user_id = ? AND deleted_at IS NULL AND status = 'active'
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            return row is not None
        finally:
            conn.close()
    except sqlite3.Error:
        return False


TREE_SKIP_NAMES = {
    ".git",
    ".next",
    ".turbo",
    ".venv",
    ".workframe-cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "users",  # ponytail: legacy scaffold dir — hide if present
    "content",  # ponytail: legacy nested tree — hide if present
}

PROTECTED_WORKSPACE_FILE_NAMES = {"AGENTS.md", ".hermes.md"}
PROTECTED_PROFILE_CONFIG_FILE_NAMES = {"config.yaml", "profile.yaml"}


def _normalized_workspace_rel(rel: str) -> str:
    return (rel or "").replace("\\", "/").lstrip("/")


def _is_env_like_name(name: str) -> bool:
    lower = name.lower()
    return (
        lower == ".env"
        or lower.startswith(".env.")
        or lower.endswith(".env")
        or lower == "environment"
    )


def _workspace_protected_reason(rel: str) -> str | None:
    """Return a stable reason when a workspace-relative path is protected."""
    safe = _safe_workspace_path(_normalized_workspace_rel(rel))
    if safe is None:
        return "invalid_path"
    try:
        rel_path = safe.relative_to(WORKSPACE.resolve())
    except ValueError:
        return "invalid_path"

    parts = rel_path.parts
    if not parts:
        return None

    for part in parts:
        if part in PROTECTED_WORKSPACE_FILE_NAMES:
            return "protected_workspace_file"
        if _is_env_like_name(part):
            return "protected_env_file"

    if len(parts) >= 3 and parts[0] == "profiles" and parts[2] in PROTECTED_PROFILE_CONFIG_FILE_NAMES:
        return "protected_profile_config"
    if len(parts) >= 2 and parts[0] == "profiles" and parts[-1] in PROTECTED_PROFILE_CONFIG_FILE_NAMES:
        return "protected_profile_config"
    return None


BOARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    priority TEXT DEFAULT 'medium',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_from_unix(ts: float | int | None) -> str:
    if ts is None:
        return ""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def _read_model_from_config(profile: str) -> tuple[str, str]:
    """Parse `model.default` and `model.provider` from config.yaml (gateway truth)."""
    gateway = _profile_gateway_config_path(profile)
    if gateway and gateway.is_file():
        try:
            return _parse_model_fields_from_yaml(gateway.read_text(encoding="utf-8"))
        except OSError:
            return "", ""
    meta = _profile_dir(profile) / "profile.yaml"
    if meta.is_file():
        try:
            return _parse_model_fields_from_yaml(meta.read_text(encoding="utf-8"))
        except OSError:
            pass
    return "", ""


def _ro_sqlite(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.is_file():
        return None
    # Hermes keeps state.db open — immutable snapshot reads work while the gateway writes.
    uri_candidates = [
        f"file:{db_path.as_posix()}?immutable=1",
        f"file://{db_path.as_posix()}?immutable=1",
        f"file:{db_path.as_posix()}?mode=ro&nolock=1",
        f"file:{db_path.as_posix()}?mode=ro",
    ]
    for uri in uri_candidates:
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=2.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=1")
            return conn
        except sqlite3.Error:
            continue
    return None


def _rw_sqlite(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.executescript(BOARD_SCHEMA)
    conn.commit()
    return conn


def _ro_sqlite_live(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.is_file():
        return None
    try:
        conn = sqlite3.connect(str(db_path), timeout=2.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=1")
        conn.execute("SELECT 1").fetchone()
        return conn
    except sqlite3.Error:
        try:
            conn.close()  # type: ignore[name-defined]
        except Exception:  # noqa: BLE001
            pass
        return _ro_sqlite(db_path)


def _list_profiles() -> list[str]:
    profiles_dir = HERMES_DATA / "profiles"
    if not profiles_dir.is_dir():
        return []
    return sorted(
        p.name
        for p in profiles_dir.iterdir()
        if p.is_dir() and ((p / "profile.yaml").exists() or (p / "config.yaml").exists())
    )


def _native_profile_slug() -> str:
    return str(NATIVE_PROFILE or "workframe-agent").strip() or "workframe-agent"


def _native_profile_present() -> bool:
    slug = _native_profile_slug()
    prof_dir = _profile_dir(slug)
    return (prof_dir / "config.yaml").is_file() or (prof_dir / "profile.yaml").is_file()


def _hermes_data_uid_gid() -> tuple[int, int]:
    try:
        st = HERMES_DATA.stat()
        return int(st.st_uid), int(st.st_gid)
    except OSError:
        return 10000, 10000


def _chown_profile_tree(prof_dir: Path) -> None:
    """Gateway runs as the Agents volume owner — seeded files must match."""
    uid, gid = _hermes_data_uid_gid()
    prof_dir.mkdir(parents=True, exist_ok=True)
    (prof_dir / "logs").mkdir(parents=True, exist_ok=True)
    for path in [prof_dir, *prof_dir.rglob("*")]:
        try:
            os.chown(path, uid, gid)
        except OSError:
            pass


def _seed_native_profile_on_disk(slug: str) -> bool:
    """Filesystem fallback when Hermes CLI cannot run (empty / crash-looping gateway)."""
    slug = safe_profile_slug(slug)
    prof_dir = _profile_dir(slug)
    prof_dir.mkdir(parents=True, exist_ok=True)
    config = prof_dir / "config.yaml"
    if not config.is_file():
        proxy = _llm_proxy_base_url("openrouter")
        config.write_text(
            "model:\n"
            "  default: google/gemini-2.5-flash\n"
            "  provider: custom\n"
            f"  base_url: {proxy}\n",
            encoding="utf-8",
        )
    soul = prof_dir / "SOUL.md"
    if not soul.is_file():
        soul.write_text(
            f"You are the {PROJECT_NAME} native agent — orchestrator and workspace admin.\n",
            encoding="utf-8",
        )
    _ensure_profile_toolsets(slug)
    _ensure_profile_terminal_cwd(slug)
    _register_profile_route(
        slug,
        {
            "display_name": f"{PROJECT_NAME} Agent",
            "role": f"{PROJECT_NAME} Manager",
        },
    )
    routes_path = ROUTES_JSON
    if routes_path.is_file():
        try:
            data = json.loads(routes_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and not data.get("default_profile"):
                data["default_profile"] = slug
                routes_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass
    _chown_profile_tree(prof_dir)
    return _native_profile_present()


def _ensure_native_hermes_profile() -> bool:
    """Idempotent: native workframe-agent must exist before gateway boot or DM bootstrap."""
    slug = _native_profile_slug()
    if _native_profile_present():
        return True
    shell = (
        "export HERMES_HOME=/opt/data HOME=/opt/data; "
        f"/opt/hermes/bin/hermes profile create {shlex.quote(slug)} --clone "
        f"--description {shlex.quote(f'{PROJECT_NAME} native agent')}"
    )
    try:
        code, out = _gateway_container_exec(["sh", "-lc", shell])
        if code == 0 and _native_profile_present():
            _register_profile_route(
                slug,
                {"display_name": f"{PROJECT_NAME} Agent", "role": f"{PROJECT_NAME} Manager"},
            )
            _chown_profile_tree(_profile_dir(slug))
            return True
        if "already exists" in out.lower() and _native_profile_present():
            _register_profile_route(
                slug,
                {"display_name": f"{PROJECT_NAME} Agent", "role": f"{PROJECT_NAME} Manager"},
            )
            _chown_profile_tree(_profile_dir(slug))
            return True
    except Exception:
        pass
    return _seed_native_profile_on_disk(slug)


def _primary_profile() -> str:
    if NATIVE_PROFILE and (HERMES_DATA / "profiles" / NATIVE_PROFILE).is_dir():
        return NATIVE_PROFILE
    profiles = _list_profiles()
    return profiles[0] if profiles else ""


def _profile_dir(profile: str) -> Path:
    return HERMES_DATA / "profiles" / profile


def _profile_gateway_config_path(profile: str) -> Path | None:
    """Hermes gateway reads platforms + model chain from config.yaml only."""
    d = _profile_dir(profile)
    if not d.is_dir():
        return None
    return d / "config.yaml"


def _ensure_gateway_config_file(profile: str) -> Path:
    path = _profile_gateway_config_path(profile)
    if path is None:
        raise ValueError(f"profile not found: {profile}")
    if path.is_file():
        return path
    provider, model = "", ""
    meta = _profile_dir(profile) / "profile.yaml"
    if meta.is_file():
        provider, model = _parse_model_fields_from_yaml(meta.read_text(encoding="utf-8"))
    seed = ""
    if model:
        seed = f"model:\n  default: {model}\n"
        if provider:
            seed += f"  provider: {provider}\n"
    path.write_text(seed, encoding="utf-8")
    return path


def _fix_invalid_model_header(raw: str) -> str:
    """Scalar `model: ''` breaks yaml.safe_load when proxy writers add nested keys."""
    lines = raw.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("model:") and not line.startswith((" ", "\t")):
            rest = stripped.split(":", 1)[1].strip().strip("'\"")
            if not rest:
                out.append("model:\n")
                continue
            if not stripped.endswith(":") and rest:
                out.append("model:\n")
                out.append(f"  default: {rest}\n")
                continue
        out.append(line)
    return "".join(out)


def _scrub_orphan_top_level_yaml_lines(profile: str) -> None:
    """Drop root-level list items (e.g. `- provider: openrouter`) left by corrupt writers."""
    config_path = _profile_gateway_config_path(profile)
    if not config_path or not config_path.is_file():
        return
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return
    out: list[str] = []
    changed = False
    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if indent == 0 and stripped.startswith("- "):
            changed = True
            continue
        out.append(line)
    if changed:
        try:
            config_path.write_text("".join(out), encoding="utf-8")
        except OSError:
            return


def _fix_model_child_indent(raw: str) -> str:
    """Re-indent model block keys to 2 spaces — fixes api_key nested under base_url scalar."""
    lines = raw.splitlines(keepends=True)
    out: list[str] = []
    in_model = False
    for line in lines:
        stripped = line.lstrip()
        if not line.startswith((" ", "\t")) and stripped.startswith("model:"):
            in_model = True
            out.append(line if line.endswith("\n") else f"{line}\n")
            continue
        if in_model:
            if stripped and not line.startswith((" ", "\t", "#")):
                in_model = False
                out.append(line)
                continue
            if stripped.startswith(("default:", "provider:", "base_url:", "api_key:")):
                _, _, val = stripped.partition(":")
                out.append(f"  {stripped.split(':', 1)[0]}:{val}\n")
                continue
        out.append(line)
    return "".join(out)


def _normalize_profile_config_yaml(profile: str) -> None:
    """Repair invalid model headers before gateway yaml parsers run (no pyyaml in API image)."""
    config_path = _profile_gateway_config_path(profile)
    if not config_path or not config_path.is_file():
        return
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError:
        return
    fixed = _fix_invalid_model_header(raw)
    fixed = _fix_model_child_indent(fixed)
    if fixed != raw:
        try:
            config_path.write_text(fixed, encoding="utf-8")
        except OSError:
            return
    _coalesce_profile_model_yaml(profile)
    _scrub_orphan_top_level_yaml_lines(profile)
    _ensure_profile_terminal_cwd(profile)


def _parse_model_fields_from_yaml(text: str) -> tuple[str, str]:
    provider = ""
    model_name = ""
    in_model_block = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line[:1].isspace() and line.endswith(":"):
            in_model_block = line[:-1].strip() == "model"
            continue
        if not in_model_block or ":" not in line:
            continue
        key, _, value = line.strip().partition(":")
        value = value.strip().strip('"').strip("'")
        if key == "default":
            model_name = value
        elif key == "provider":
            provider = value
    return provider, model_name


def _profile_config_path(profile: str) -> Path | None:
    """Readable profile yaml: prefer gateway config.yaml, else legacy profile.yaml metadata."""
    gateway = _profile_gateway_config_path(profile)
    if gateway and gateway.is_file():
        return gateway
    meta = _profile_dir(profile) / "profile.yaml"
    return meta if meta.is_file() else None


def _profile_home(profile: str) -> Path:
    return _profile_dir(profile)


def _render_soul_placeholders(text: str) -> str:
    native_slug = str(NATIVE_PROFILE or "workframe-agent").strip() or "workframe-agent"
    ctx = {
        "projectName": PROJECT_NAME,
        "nativeProfileSlug": native_slug,
        "nativeAgentName": _native_display_name(),
    }
    out = str(text or "")
    for key, value in ctx.items():
        out = out.replace(f"{{{key}}}", value)
    return out


def _soul_is_stub(text: str) -> bool:
    """True when SOUL is missing, trivial, unexpanded, or not Workframe identity."""
    body = str(text or "").strip()
    if len(body) < 80:
        return True
    low = body.lower()
    if any(token in low for token in ("{nativeagentname}", "{projectname}", "{nativeprofileslug}")):
        return True
    if "workframe" not in low and "botfather" not in low and "concierge" not in low:
        return True
    return False


def _format_child_template(template: str, **kwargs: str) -> str:
    ctx = {"nativeAgentName": _native_display_name(), **kwargs}
    return _render_soul_placeholders(template.format(**ctx))

_CHILD_SOUL_TEMPLATE = """# {display_name}

## Identity (highest priority)
You are **{display_name}** — a Workframe agent. When greeting or identifying yourself, use **{display_name}** — never the underlying model or provider name.

Mission
- {role}

## Hermes & Workframe
- Read `AGENTS.md` in this profile home for tools, skills, memory, and how to upkeep your `SOUL.md`.
- Read `/workspace/AGENTS.md` for project workspace rules.
- Load Hermes skills from `skills/` before specialized work.
- CLI: `/opt/hermes/.venv/bin/hermes -p <your-runtime-slug> …` via **terminal** tool.

Restrictions
- You are a child agent — you cannot create, delete, spawn, or reconfigure other agents.
- Escalate crew changes to the native Workframe agent ({nativeAgentName}).
"""

_CHILD_AGENTS_TEMPLATE = """# AGENTS — {display_name}

Operating rules for **{display_name}**. Identity lives in `SOUL.md` in this profile home.

## Tools & skills

- Load task-appropriate skills from `skills/` before specialized work.
- CLI: `/opt/hermes/.venv/bin/hermes -p <your-runtime-slug> …` via **terminal**.
- Read `WORKFRAME_COHORT.md` when present — use **runtime_slug** for kanban/delegate.

## Restrictions

- Child agent — **not** Botfather. Escalate crew changes to **{nativeAgentName}**.
- You may refine your own `SOUL.md` and notes when the user asks.

## Memory

- Outcomes in `/workspace`; evolve notes via Hermes memory when asked.
"""


def _soul_is_native_concierge(text: str) -> bool:
    low = str(text or "").lower()
    return "botfather" in low or "concierge" in low


def _strip_forbidden_child_skills(profile: str) -> list[str]:
    """Remove botfather/crew-manager skills from child profiles after native clone."""
    prof = safe_profile_slug(profile)
    skills_root = _profile_dir(prof) / "skills"
    if not skills_root.is_dir():
        return []
    removed: list[str] = []

    def walk(dir_path: Path) -> None:
        for entry in list(dir_path.iterdir()):
            if entry.is_dir():
                if entry.name in _FORBIDDEN_CHILD_SKILLS:
                    shutil.rmtree(entry, ignore_errors=True)
                    removed.append(entry.name)
                else:
                    walk(entry)
            elif entry.name == "SKILL.md":
                skill_name = entry.parent.name
                if skill_name in _FORBIDDEN_CHILD_SKILLS:
                    shutil.rmtree(entry.parent, ignore_errors=True)
                    removed.append(skill_name)

    walk(skills_root)
    return sorted(set(removed))


def _seed_native_user_overlay(
    runtime: str,
    template: str,
    *,
    display_name: str = "",
    role: str = "",
    tagline: str = "",
    user_soul: str = "",
) -> None:
    """Keep template SOUL/AGENTS on disk; layer user identity in registry overlay."""
    runtime = safe_profile_slug(runtime)
    template = safe_profile_slug(template)
    if not runtime:
        return
    _write_profile_soul_if_stub(runtime, template)
    if display_name.strip() or role.strip() or tagline.strip() or user_soul.strip():
        _apply_profile_identity(
            runtime,
            display_name=display_name,
            role=role,
            tagline=tagline,
            user_soul=user_soul,
        )


def _apply_profile_identity(
    profile: str,
    *,
    display_name: str = "",
    role: str = "",
    tagline: str = "",
    user_soul: str = "",
) -> None:
    prof = safe_profile_slug(profile)
    patch: dict[str, Any] = {}
    if display_name.strip():
        patch["display_name"] = display_name.strip()
    if role.strip():
        patch["role"] = role.strip()
    if tagline.strip():
        patch["tagline"] = tagline.strip()
    if user_soul.strip():
        patch["user_soul"] = user_soul.strip()
    if patch.get("display_name"):
        aid = _avatar_id_for_display_name(str(patch["display_name"]))
        if aid:
            patch.update(_normalize_agent_avatar_patch("", aid))
    if patch:
        _upsert_agent_registry_row(prof, patch)


def _profile_identity_overlay(profile: str) -> str:
    prof = safe_profile_slug(profile)
    if _is_runtime_profile_slug(prof):
        template = _runtime_template_slug(prof)
        reg = {**_agent_registry_row(template), **_agent_registry_row(prof)}
    else:
        reg = _agent_registry_row(prof)
    blocks: list[str] = []
    identity_lines: list[str] = []
    display = str(reg.get("display_name") or "").strip()
    role = str(reg.get("role") or reg.get("description") or "").strip()
    tagline = str(reg.get("tagline") or "").strip()
    if display:
        identity_lines.append(f"- **Name:** {display}")
    if role:
        identity_lines.append(f"- **Role:** {role}")
    if tagline:
        identity_lines.append(f"- **Tagline:** {tagline}")
    if identity_lines:
        blocks.append("## User identity\n" + "\n".join(identity_lines))
    user_soul = str(reg.get("user_soul") or "").strip()
    if user_soul:
        blocks.append("## Additional instructions\n" + user_soul)
    return "\n\n".join(blocks).strip()


def _install_child_base_artifacts(profile: str, *, display_name: str, role: str) -> bool:
    """Write child SOUL/AGENTS when profile was cloned from native concierge."""
    prof = safe_profile_slug(profile)
    if not prof or _is_native_profile(prof):
        return False
    label = display_name.strip() or _profile_display_name(prof)
    mission = role.strip() or f"{label} specialist for {PROJECT_NAME}."
    raw = _profile_soul_raw(prof)
    wrote = False
    if _soul_is_stub(raw) or _soul_is_native_concierge(raw):
        body = _format_child_template(_CHILD_SOUL_TEMPLATE, display_name=label, role=mission)
        soul_path = _profile_dir(prof) / "SOUL.md"
        soul_path.parent.mkdir(parents=True, exist_ok=True)
        soul_path.write_text(body if body.endswith("\n") else f"{body}\n", encoding="utf-8")
        wrote = True
    agents_path = _profile_dir(prof) / "AGENTS.md"
    if not agents_path.is_file():
        agents_body = _format_child_template(_CHILD_AGENTS_TEMPLATE, display_name=label)
        agents_path.write_text(agents_body.strip() + "\n", encoding="utf-8")
        wrote = True
    return wrote


def _profile_base_soul_text(profile: str) -> str:
    prof = safe_profile_slug(str(profile or "").strip())
    if not prof:
        return ""
    path = _profile_soul_path(prof)
    raw = ""
    try:
        if path.is_file():
            raw = path.read_text(encoding="utf-8-sig", errors="replace").strip()
    except OSError:
        raw = ""
    template = _runtime_template_slug(prof) if _is_runtime_profile_slug(prof) else prof
    if _soul_is_stub(raw) and template:
        tpl_path = _profile_dir(template) / "SOUL.md"
        try:
            if tpl_path.is_file() and tpl_path != path:
                raw = tpl_path.read_text(encoding="utf-8-sig", errors="replace").strip()
        except OSError:
            pass
    if not raw:
        return ""
    return _render_soul_placeholders(raw).strip()


def _profile_soul_text(profile: str) -> str:
    base = _profile_base_soul_text(profile)
    overlay = _profile_identity_overlay(profile)
    if base and overlay:
        return f"{base.rstrip()}\n\n---\n\n{overlay}"
    return overlay or base


def _write_profile_soul_if_stub(profile: str, template: str = "") -> bool:
    """Persist rendered template SOUL when runtime file is stub. Returns True if written."""
    prof = safe_profile_slug(profile)
    tpl = safe_profile_slug(template or (_runtime_template_slug(prof) if _is_runtime_profile_slug(prof) else prof))
    if not prof or not tpl:
        return False
    dst = _profile_dir(prof) / "SOUL.md"
    try:
        current = dst.read_text(encoding="utf-8-sig", errors="replace") if dst.is_file() else ""
    except OSError:
        current = ""
    if not _soul_is_stub(current):
        return False
    src = _profile_dir(tpl) / "SOUL.md"
    if not src.is_file():
        return False
    try:
        rendered = _render_soul_placeholders(src.read_text(encoding="utf-8-sig", errors="replace")).strip()
        if not rendered or _soul_is_stub(rendered):
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(rendered if rendered.endswith("\n") else f"{rendered}\n", encoding="utf-8")
        return True
    except OSError:
        return False


def _profile_soul_path(profile: str) -> Path:
    profile_soul = _profile_home(profile) / "SOUL.md"
    if profile_soul.is_file():
        return profile_soul
    if profile == _primary_profile():
        root_soul = HERMES_DATA / "SOUL.md"
        if root_soul.is_file():
            return root_soul
    return profile_soul


def _profile_soul_raw(profile: str) -> str:
    path = _profile_soul_path(profile)
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace").strip()
    except OSError:
        return ""


def _file_size_mb(path: Path) -> float:
    try:
        return path.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


def _cron_plain_english(schedule: str) -> str:
    s = (schedule or "").strip()
    if not s:
        return "No schedule"
    if s.startswith("every "):
        return s.capitalize()
    parts = s.split()
    if len(parts) == 5:
        minute, hour, dom, month, dow = parts
        if dom == "*" and month == "*" and dow == "*":
            return f"Every day at {hour.zfill(2)}:{minute.zfill(2)} UTC"
        if dom == "*" and month == "*" and dow != "*":
            return f"Cron: {s}"
    return f"Cron: {s}"


def gateway_data(profile: str) -> dict[str, Any]:
    path = _profile_dir(profile) / "gateway_state.json"
    base: dict[str, Any] = {
        "ok": False,
        "exists": path.is_file(),
        "state": "unknown",
        "platforms": {},
        "active_agents": 0,
        "uptime": None,
        "uptime_seconds": None,
        "updated_at": None,
    }
    if not path.is_file():
        return base
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return base
    start = raw.get("start_time")
    uptime = None
    if isinstance(start, (int, float)) and float(start) > 1_000_000_000:
        uptime = max(0.0, time.time() - float(start))
    platforms = raw.get("platforms") or {}
    for name, info in platforms.items():
        if isinstance(info, dict) and "status" not in info:
            info = {**info, "status": info.get("state", "unknown")}
            platforms[name] = info
    base.update(
        {
            "ok": True,
            "state": raw.get("gateway_state") or raw.get("state") or "unknown",
            "kind": raw.get("kind"),
            "pid": raw.get("pid"),
            "platforms": platforms,
            "active_agents": raw.get("active_agents", 0),
            "updated_at": raw.get("updated_at"),
            "uptime": uptime,
            "uptime_seconds": uptime,
            "raw": raw,
        }
    )
    return base


def sessions_data(profile: str) -> dict[str, Any]:
    db = _profile_dir(profile) / "state.db"
    out: dict[str, Any] = {
        "ok": False,
        "count": 0,
        "session_count": 0,
        "message_count": 0,
        "recent": [],
    }
    conn = _ro_sqlite_live(db)
    if not conn:
        return out
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS sessions,
                   COALESCE(SUM(message_count), 0) AS messages
            FROM sessions
            """
        ).fetchone()
        recent = conn.execute(
            """
            SELECT id, source, title, started_at, ended_at, message_count,
                   model, estimated_cost_usd
            FROM sessions
            ORDER BY started_at DESC
            LIMIT 25
            """
        ).fetchall()
        count = int(row["sessions"] or 0)
        messages = int(row["messages"] or 0)
        out.update(
            {
                "ok": True,
                "count": count,
                "session_count": count,
                "message_count": messages,
                "recent": [
                    {
                        "id": r["id"],
                        "source": r["source"],
                        "title": r["title"] or "(untitled)",
                        "started_at": r["started_at"],
                        "started_at_iso": _iso_from_unix(r["started_at"]),
                        "ended_at": r["ended_at"],
                        "message_count": r["message_count"] or 0,
                        "model": r["model"] or "",
                        "cost_usd": r["estimated_cost_usd"],
                    }
                    for r in recent
                ],
            }
        )
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return out


def _profile_slug(profile: str) -> str:
    if profile.endswith("-agent"):
        return profile[: -len("-agent")]
    return profile


def _agent_label(profile: str) -> str:
    return _profile_slug(profile)


def _native_display_name() -> str:
    return f"{PROJECT_NAME} Agent"


def _is_native_profile(profile: str) -> bool:
    return bool(NATIVE_PROFILE and profile == NATIVE_PROFILE)


def _agent_db_display_name(template_slug: str, workspace_id: str = "") -> str:
    template_slug = safe_profile_slug(str(template_slug or "").strip())
    if not template_slug:
        return ""
    conn = _workframe_db()
    try:
        if workspace_id:
            row = _lookup_agent_profile(conn, workspace_id, template_slug)
        else:
            row = conn.execute(
                """
                SELECT display_name FROM agent_profiles
                WHERE slug = ? AND deleted_at IS NULL
                ORDER BY is_native DESC, updated_at DESC
                LIMIT 1
                """,
                (template_slug,),
            ).fetchone()
        if row and str(row["display_name"] or "").strip():
            return str(row["display_name"]).strip()
    finally:
        conn.close()
    return ""


def _profile_display_name(profile: str, workspace_id: str = "") -> str:
    template = _runtime_template_slug(profile) if _is_runtime_profile_slug(profile) else profile
    db_name = _agent_db_display_name(template, workspace_id)
    if db_name:
        return db_name
    reg = _agent_registry_row(template)
    if reg.get("display_name"):
        return str(reg["display_name"])
    if _is_native_profile(template):
        return _native_display_name()
    slug = _profile_slug(template)
    return slug.replace("-", " ").title()


def _default_session_title(profile: str) -> str:
    display = _profile_display_name(profile).strip() or "Agent"
    return f"Session with {display}"


def _create_profile_session_via_api(profile: str, session_id: str, title: str) -> tuple[int, Any, str]:
    base_title = (title or "").strip() or _default_session_title(profile)
    candidate = base_title
    for attempt in range(1, 25):
        status, data = _profile_api_request(
            profile,
            "POST",
            "/api/sessions",
            {"session_id": session_id, "title": candidate},
        )
        if status < 300:
            return status, data, candidate
        msg = json.dumps(data).lower() if isinstance(data, dict) else str(data).lower()
        if "invalid_title" not in msg and "already in use" not in msg:
            return status, data, candidate
        if attempt < 12:
            candidate = f"{base_title} ({attempt + 1})"
        else:
            candidate = f"{base_title} {int(time.time())}-{attempt}"
    return status, data, candidate


def _profile_role(profile: str) -> str:
    if _is_native_profile(profile):
        return (
            f"Workframe Manager and orchestrator for {PROJECT_NAME}. "
            "Routes work to installed specialist profiles."
        )
    slug = _profile_slug(profile)
    return SPECIALIST_ROLES.get(slug, f"{_profile_display_name(profile)} specialist profile.")


def _profile_code(display_name: str, slug: str) -> str:
    word = (display_name.split()[0] if display_name else slug)[:4]
    return word.upper() or "AGNT"


def safe_profile_slug(value: str) -> str:
    slug = (value or "").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", slug):
        raise ValueError("invalid profile")
    return slug


def profile_exists(profile: str) -> bool:
    return _profile_dir(profile).is_dir()


def route_status_for_profile(profile: str) -> str:
    if not profile_exists(profile):
        return "not_installed"
    return "available"


def _register_profile_route(profile: str, meta: dict[str, Any] | None = None) -> bool:
    """Append an on-disk profile to routes.json when missing (post profile_create)."""
    prof = safe_profile_slug(profile)
    if not profile_exists(prof):
        return False
    ROUTES_JSON.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {"version": 1, "routes": []}
    if ROUTES_JSON.is_file():
        try:
            parsed = json.loads(ROUTES_JSON.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                data = parsed
        except (OSError, json.JSONDecodeError):
            pass
    routes = data.get("routes")
    if not isinstance(routes, list):
        routes = []
        data["routes"] = routes
    if any(isinstance(row, dict) and str(row.get("profile") or "") == prof for row in routes):
        return False
    routes.append(_route_record(prof, meta))
    if not data.get("default_profile"):
        data["default_profile"] = _primary_profile()
    ROUTES_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def _route_record(profile: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = meta or {}
    slug = safe_profile_slug(profile)
    ident = _agent_identity_fields(slug)
    row = {
        "id": str(meta.get("id") or slug),
        "profile": slug,
        "display_name": str(ident.get("display_name") or meta.get("display_name") or _profile_display_name(slug)),
        "role": str(ident.get("role") or meta.get("role") or _profile_role(slug)),
        "mode": "lane",
        "route_status": route_status_for_profile(slug),
    }
    if ident.get("avatar_url"):
        row["avatar_url"] = str(ident["avatar_url"])
    if ident.get("avatar_id"):
        row["avatar_id"] = str(ident["avatar_id"])
    _resolve_avatar_fields(row)
    return row


def load_routes() -> dict[str, Any]:
    default_profile = _primary_profile()
    raw_routes: list[dict[str, Any]] = []
    if ROUTES_JSON.is_file():
        try:
            data = json.loads(ROUTES_JSON.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("routes"), list):
                raw_routes = data["routes"]
                if data.get("default_profile"):
                    default_profile = safe_profile_slug(str(data["default_profile"]))
        except (OSError, json.JSONDecodeError, ValueError):
            raw_routes = []

    routes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in raw_routes:
        if not isinstance(entry, dict):
            continue
        try:
            profile = safe_profile_slug(str(entry.get("profile") or entry.get("id") or ""))
        except ValueError:
            continue
        if not profile_exists(profile) or profile in seen:
            continue
        seen.add(profile)
        routes.append(_route_record(profile, entry))

    if not routes:
        for profile in _list_profiles():
            if profile in seen:
                continue
            seen.add(profile)
            routes.append(_route_record(profile, {}))

    route_profiles = {r["profile"] for r in routes}
    if default_profile and default_profile not in route_profiles and profile_exists(default_profile):
        routes.insert(0, _route_record(default_profile, {}))
        route_profiles.add(default_profile)
    native = safe_profile_slug(NATIVE_PROFILE) if NATIVE_PROFILE else ""
    if native and native not in route_profiles and profile_exists(native):
        routes.insert(0, _route_record(native, {}))
        route_profiles.add(native)
    if default_profile and default_profile not in route_profiles:
        default_profile = routes[0]["profile"] if routes else default_profile

    return {"ok": True, "default_profile": default_profile, "routes": routes}


def resolve_validated_profile(profile: str) -> str:
    raw = str(profile or _primary_profile()).strip()
    if _AGENT_PROFILE_UUID_RE.match(raw):
        resolved = _hermes_slug_from_agent_ref(raw)
        if resolved:
            raw = resolved
    slug = safe_profile_slug(raw)
    allowed = {r["profile"] for r in load_routes()["routes"]}
    if slug not in allowed:
        raise ValueError(f"unknown profile: {slug}")
    if not profile_exists(slug):
        raise ValueError(f"profile not installed: {slug}")
    return slug


_RUNTIME_PROFILE_RE = re.compile(r"^u-[a-z0-9][a-z0-9-]{0,62}$")


def _is_runtime_profile_slug(slug: str) -> bool:
    return bool(_RUNTIME_PROFILE_RE.fullmatch(str(slug or "").strip()))


def _runtime_template_slug(runtime: str) -> str:
    """Map per-user runtime slug u-{user}-{template} back to the template profile."""
    slug = safe_profile_slug(str(runtime or "").strip())
    if not _is_runtime_profile_slug(slug):
        return slug
    rest = slug[2:]
    templates: set[str] = {p for p in _list_profiles() if not _is_runtime_profile_slug(p)}
    templates.update(load_agent_registry().keys())
    native = _primary_profile()
    if native:
        templates.add(native)
    for template in sorted(templates, key=len, reverse=True):
        if rest == template or rest.endswith(f"-{template}"):
            return template
    return rest


_DEFAULT_CHAT_TOOLSETS = ("hermes-cli", "terminal")


def _chat_toolsets_for_profile(_profile: str = "") -> tuple[str, ...]:
    """Multi-user safety: runtime RBAC + exec credential guards, not disabled terminal."""
    return _DEFAULT_CHAT_TOOLSETS


def _ensure_profile_toolsets(profile: str, toolsets: tuple[str, ...] | None = None) -> None:
    """Ensure Hermes toolsets (e.g. terminal) are enabled on a profile config."""
    prof = safe_profile_slug(str(profile or "").strip())
    cfg_path = _profile_gateway_config_path(prof)
    if not prof or cfg_path is None:
        return
    _normalize_profile_config_yaml(prof)
    want = list(toolsets if toolsets is not None else _chat_toolsets_for_profile(prof))
    if _profile_toolsets_ready(prof, want):
        return
    try:
        import yaml

        cfg: dict[str, Any] = {}
        if cfg_path.is_file():
            loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
            cfg = loaded if isinstance(loaded, dict) else {}
        ts = cfg.setdefault("toolsets", [])
        if not isinstance(ts, list):
            ts = []
            cfg["toolsets"] = ts
        pts = cfg.setdefault("platform_toolsets", {})
        if not isinstance(pts, dict):
            pts = {}
            cfg["platform_toolsets"] = pts
        changed = False
        for name in want:
            if name not in ts:
                ts.append(name)
                changed = True
        for platform in ("api_server", "cli"):
            plat = pts.setdefault(platform, [])
            if not isinstance(plat, list):
                plat = []
                pts[platform] = plat
            for name in want:
                if name not in plat:
                    plat.append(name)
                    changed = True
        agent = cfg.setdefault("agent", {})
        if not isinstance(agent, dict):
            agent = {}
            cfg["agent"] = agent
        disabled = agent.get("disabled_toolsets") if isinstance(agent.get("disabled_toolsets"), list) else []
        for name in want:
            if name in disabled:
                disabled = [x for x in disabled if x != name]
                changed = True
        agent["disabled_toolsets"] = disabled
        if changed:
            cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    except (OSError, ImportError):
        return


def resolve_hermes_profile(profile: str) -> str:
    """Resolve a Hermes profile dir for API calls; runtime u-* slugs skip route rail."""
    raw = str(profile or _primary_profile()).strip()
    if _AGENT_PROFILE_UUID_RE.match(raw):
        resolved = _hermes_slug_from_agent_ref(raw)
        if resolved:
            raw = resolved
    slug = safe_profile_slug(raw)
    if _is_runtime_profile_slug(slug):
        if not profile_exists(slug):
            raise ValueError(f"profile not installed: {slug}")
        return slug
    return resolve_validated_profile(slug)


def _resolve_bind_profile_arg(
    profile: str,
    user_id: str = "",
    room_id: str = "",
    workspace_id: str = "",
) -> tuple[str, str]:
    """Return (hermes_profile, template_profile) for chat bind/session/message paths."""
    raw = urllib.parse.unquote(str(profile or _primary_profile()).strip())
    slug = safe_profile_slug(raw)
    user_id = str(user_id or "").strip()
    room_id = str(room_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if _is_runtime_profile_slug(slug):
        template = _runtime_template_slug(slug)
        resolve_validated_profile(template)
        if room_id and user_id:
            if not workspace_id:
                try:
                    conn = _workframe_db()
                    row = conn.execute(
                        "SELECT workspace_id FROM rooms WHERE id = ? AND deleted_at IS NULL",
                        (room_id,),
                    ).fetchone()
                    conn.close()
                    if row:
                        workspace_id = str(row["workspace_id"])
                except Exception:  # noqa: BLE001
                    pass
            ensure_runtime_profile(slug, template, user_id, workspace_id)
        elif not profile_exists(slug):
            raise ValueError(f"profile not installed: {slug}")
        return slug, template
    template = resolve_validated_profile(slug)
    if room_id and user_id:
        hermes = _resolve_chat_hermes_profile(template, user_id, room_id, workspace_id)
        return hermes, template
    return template, template


def _gateway_platform(gateway: dict[str, Any], native: bool) -> str:
    platforms = gateway.get("platforms") or {}
    if native:
        for name in ("telegram", "discord", "web", "localhost"):
            p = platforms.get(name)
            if isinstance(p, dict) and str(p.get("state") or p.get("status") or "").lower() == "connected":
                return name.replace("localhost", "Hermes").title()
        return "Hermes"
    for name in ("discord", "telegram", "web"):
        p = platforms.get(name)
        if isinstance(p, dict) and str(p.get("state") or p.get("status") or "").lower() == "connected":
            return name.title()
    return "Hermes"


_avatar_catalog_cache: dict[str, Any] | None = None


def _load_avatar_catalog() -> dict[str, Any]:
    global _avatar_catalog_cache
    if _avatar_catalog_cache is not None:
        return _avatar_catalog_cache
    fallback: dict[str, Any] = {"public_base": "/assets/avatars", "avatars": []}
    if not AVATAR_CATALOG_JSON.is_file():
        _avatar_catalog_cache = fallback
        return fallback
    try:
        data = json.loads(AVATAR_CATALOG_JSON.read_text(encoding="utf-8"))
        _avatar_catalog_cache = data if isinstance(data, dict) else fallback
    except Exception:  # noqa: BLE001
        _avatar_catalog_cache = fallback
    return _avatar_catalog_cache


def _avatar_path_from_url(avatar_url: str) -> str:
    raw = str(avatar_url or "").strip()
    if "://" in raw:
        try:
            parsed = urllib.parse.urlparse(raw)
            raw = parsed.path or raw
        except Exception:  # noqa: BLE001
            pass
    return raw.split("?", 1)[0].split("#", 1)[0]


def _catalog_url_for_id(
    catalog: dict[str, Any],
    avatar_id: str,
    *,
    items_key: str = "avatars",
    default_base: str = "/assets",
) -> str:
    avatar_id = str(avatar_id or "").strip()
    base = str(catalog.get("public_base") or default_base).rstrip("/")
    for row in catalog.get(items_key) or []:
        if isinstance(row, dict) and str(row.get("id")) == avatar_id:
            file_name = str(row.get("file") or f"{avatar_id}.png")
            return f"{base}/{file_name}"
    return f"{base}/{avatar_id}.png"


def _id_from_catalog_url(
    catalog: dict[str, Any],
    avatar_url: str,
    *,
    items_key: str = "avatars",
) -> str:
    path = _avatar_path_from_url(avatar_url)
    basename = path.rsplit("/", 1)[-1]
    if not basename:
        return ""
    rows = [row for row in catalog.get(items_key) or [] if isinstance(row, dict)]
    base = str(catalog.get("public_base") or "").rstrip("/")
    for row in rows:
        if str(row.get("file") or f"{row.get('id')}.png") == basename:
            return str(row.get("id") or "")
    if base:
        stable = re.match(rf"^{re.escape(base)}/([^/]+)\.png$", path, re.I)
        if stable:
            stem = stable.group(1)
            for row in rows:
                if str(row.get("id") or "") == stem:
                    return str(row.get("id") or "")
                file_stem = str(row.get("file") or f"{row.get('id')}.png").replace(".png", "")
                if file_stem == stem:
                    return str(row.get("id") or "")
    hashed = re.match(r"/assets/([a-z0-9]+)-[A-Za-z0-9_]+\.png$", path, re.I)
    if hashed:
        prefix = hashed.group(1)
        for row in rows:
            if str(row.get("id") or "") == prefix:
                return str(row.get("id") or "")
            file_stem = str(row.get("file") or f"{row.get('id')}.png").replace(".png", "")
            if file_stem == prefix:
                return str(row.get("id") or "")
    return ""


def _normalize_catalog_avatar_patch(
    catalog: dict[str, Any],
    avatar_url: str = "",
    avatar_id: str = "",
    *,
    items_key: str = "avatars",
    default_base: str = "/assets",
    include_id: bool = True,
) -> dict[str, str]:
    aid = str(avatar_id or "").strip()
    raw = str(avatar_url or "").strip()
    if raw.startswith("data:"):
        out = {"avatar_url": raw}
        if include_id:
            out["avatar_id"] = ""
        return out
    path = _avatar_path_from_url(raw)
    if not path and not aid:
        out = {"avatar_url": ""}
        if include_id:
            out["avatar_id"] = ""
        return out
    if not aid and path:
        aid = _id_from_catalog_url(catalog, path, items_key=items_key)
    if aid:
        stable = _catalog_url_for_id(catalog, aid, items_key=items_key, default_base=default_base)
        out = {"avatar_url": stable}
        if include_id:
            out["avatar_id"] = aid
        return out
    out = {"avatar_url": path or raw}
    if include_id:
        out["avatar_id"] = ""
    return out


def _avatar_url_for_id(avatar_id: str) -> str:
    return _catalog_url_for_id(
        _load_avatar_catalog(),
        avatar_id,
        items_key="avatars",
        default_base="/assets/avatars",
    )


def _avatar_id_from_url(avatar_url: str) -> str:
    return _id_from_catalog_url(_load_avatar_catalog(), avatar_url, items_key="avatars")


def _normalize_user_avatar_url(avatar_url: str) -> str:
    catalog = _load_preset_catalog(USER_AVATAR_CATALOG_JSON)
    return _normalize_catalog_avatar_patch(
        catalog,
        avatar_url,
        items_key="avatars",
        default_base="/assets/avatars",
        include_id=False,
    )["avatar_url"]


def _normalize_logo_url(avatar_url: str) -> str:
    catalog = _load_preset_catalog(LOGO_CATALOG_JSON)
    return _normalize_catalog_avatar_patch(
        catalog,
        avatar_url,
        items_key="logos",
        default_base="/assets/project-logos",
        include_id=False,
    )["avatar_url"]


def _normalize_agent_avatar_patch(
    avatar_url: str = "",
    avatar_id: str = "",
) -> dict[str, str]:
    """Persist stable catalog id + nginx path — not vite hash or absolute origin."""
    return _normalize_catalog_avatar_patch(
        _load_avatar_catalog(),
        avatar_url,
        avatar_id,
        items_key="avatars",
        default_base="/assets/avatars",
        include_id=True,
    )


_preset_catalog_cache: dict[str, dict[str, Any]] = {}


def _load_preset_catalog(path: Path) -> dict[str, Any]:
    key = str(path)
    if key in _preset_catalog_cache:
        return _preset_catalog_cache[key]
    fallback: dict[str, Any] = {"public_base": "", "avatars": [], "logos": []}
    if not path.is_file():
        _preset_catalog_cache[key] = fallback
        return fallback
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        _preset_catalog_cache[key] = data if isinstance(data, dict) else fallback
    except Exception:  # noqa: BLE001
        _preset_catalog_cache[key] = fallback
    return _preset_catalog_cache[key]


def _pick_preset_url(catalog_path: Path, *, items_key: str = "avatars") -> str:
    catalog = _load_preset_catalog(catalog_path)
    base = str(catalog.get("public_base") or "").rstrip("/")
    items = [row for row in catalog.get(items_key) or [] if isinstance(row, dict) and row.get("id")]
    if not items or not base:
        return ""
    pick = secrets.choice(items)
    file_name = str(pick.get("file") or f"{pick['id']}.png")
    return f"{base}/{file_name}"


def _pick_logo_url() -> str:
    return _pick_preset_url(LOGO_CATALOG_JSON, items_key="logos")


def _pick_user_avatar_url() -> str:
    return _pick_preset_url(USER_AVATAR_CATALOG_JSON, items_key="avatars")


def _resolve_avatar_fields(row: dict[str, Any]) -> None:
    avatar_id = str(row.get("avatar_id") or "").strip()
    if avatar_id:
        row["avatar_url"] = _avatar_url_for_id(avatar_id)
        return
    explicit = str(row.get("avatar_url") or "").strip()
    if explicit:
        row["avatar_url"] = explicit


def _load_avatar_registry() -> dict[str, Any]:
    if not AVATAR_REGISTRY_JSON.is_file():
        return {"version": 1, "weights": {}, "assignments": {}}
    try:
        data = json.loads(AVATAR_REGISTRY_JSON.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("weights", {})
            data.setdefault("assignments", {})
            return data
    except Exception:  # noqa: BLE001
        pass
    return {"version": 1, "weights": {}, "assignments": {}}


def _save_avatar_registry(data: dict[str, Any]) -> None:
    AVATAR_REGISTRY_JSON.parent.mkdir(parents=True, exist_ok=True)
    AVATAR_REGISTRY_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _pick_avatar_id() -> str:
    catalog = _load_avatar_catalog()
    avatars = [row for row in catalog.get("avatars") or [] if isinstance(row, dict) and row.get("id")]
    if not avatars:
        return "steve"
    registry = _load_avatar_registry()
    agents = load_agent_registry()
    assigned = {str(v) for v in registry.get("assignments", {}).values()}
    for row in agents.values():
        aid = str(row.get("avatar_id") or "").strip()
        if aid:
            assigned.add(aid)
    pool = [row for row in avatars if str(row["id"]) not in assigned] or avatars
    weights = registry.get("weights") or {}
    min_weight = min(int(weights.get(str(row["id"]), 0)) for row in pool)
    candidates = [row for row in pool if int(weights.get(str(row["id"]), 0)) <= min_weight]
    pick = secrets.choice(candidates)
    return str(pick["id"])


def _upsert_agent_registry_row(profile: str, patch: dict[str, Any]) -> None:
    prof_key = safe_profile_slug(profile)
    if "avatar_url" in patch or "avatar_id" in patch:
        norm = _normalize_agent_avatar_patch(
            str(patch.get("avatar_url") or ""),
            str(patch.get("avatar_id") or ""),
        )
        patch = {**patch, **norm}
    AGENTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {"version": 1, "owner_profile": _primary_profile(), "agents": {}}
    if AGENTS_JSON.is_file():
        try:
            loaded = json.loads(AGENTS_JSON.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except Exception:  # noqa: BLE001
            pass
    agents = data.setdefault("agents", {})
    current = agents.get(prof_key) if isinstance(agents.get(prof_key), dict) else {}
    agents[prof_key] = {**current, **patch, "profile": prof_key}
    data["agents"] = agents
    AGENTS_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _avatar_id_for_display_name(display_name: str) -> str:
    """Map a chosen agent name to catalog id when labels match (e.g. Ada → ada)."""
    needle = str(display_name or "").strip().lower()
    if not needle:
        return ""
    for row in _load_avatar_catalog().get("avatars") or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip().lower()
        aid = str(row.get("id") or "").strip().lower()
        if needle in (label, aid):
            return str(row["id"])
    return ""


def _assign_agent_avatar(profile: str, *, display_name: str = "") -> dict[str, str]:
    """Pick catalog avatar and persist to agents.json + avatar-registry.json."""
    prof = safe_profile_slug(profile)
    native_slug = safe_profile_slug(str(NATIVE_PROFILE or "workframe-agent"))
    name = str(display_name or "").strip() or str(_agent_registry_row(prof).get("display_name") or "").strip()
    by_name = _avatar_id_for_display_name(name)
    if by_name:
        avatar_id = by_name
    elif prof == native_slug:
        avatar_id = "steve"
    else:
        avatar_id = _pick_avatar_id()
    avatar_url = _avatar_url_for_id(avatar_id)
    _upsert_agent_registry_row(
        prof,
        {
            "avatar_id": avatar_id,
            "avatar_url": avatar_url,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    registry = _load_avatar_registry()
    registry.setdefault("assignments", {})[prof] = avatar_id
    weights = registry.setdefault("weights", {})
    weights[avatar_id] = int(weights.get(avatar_id, 0)) + 1
    _save_avatar_registry(registry)
    return {"avatar_id": avatar_id, "avatar_url": avatar_url}


def load_agent_registry() -> dict[str, dict[str, Any]]:
    if not AGENTS_JSON.is_file():
        return {}
    try:
        data = json.loads(AGENTS_JSON.read_text(encoding="utf-8"))
        agents = data.get("agents")
        if isinstance(agents, dict):
            return {str(k): v for k, v in agents.items() if isinstance(v, dict)}
    except Exception:  # noqa: BLE001
        pass
    return {}


def _agent_registry_row(profile: str) -> dict[str, Any]:
    slug = safe_profile_slug(profile)
    return load_agent_registry().get(slug, {})


def _workspace_agent_identities(workspace_id: str | None = None) -> dict[str, dict[str, Any]]:
    """Slug → display_name/tagline/role/avatar from agent_profiles + registry."""
    identities: dict[str, dict[str, Any]] = {}
    try:
        conn = _workframe_db()
        ws_id = str(workspace_id or "").strip()
        if not ws_id:
            ws = conn.execute(
                "SELECT id FROM workspaces WHERE slug = 'default' AND deleted_at IS NULL LIMIT 1",
            ).fetchone()
            ws_id = str(ws["id"]) if ws else ""
        if ws_id:
            rows = conn.execute(
                """
                SELECT slug, display_name, tagline, role, avatar_url
                FROM agent_profiles
                WHERE workspace_id = ? AND deleted_at IS NULL
                """,
                (ws_id,),
            ).fetchall()
            for row in rows:
                slug = str(row["slug"] or "").strip()
                if not slug:
                    continue
                identities[slug] = {
                    "display_name": str(row["display_name"] or ""),
                    "tagline": str(row["tagline"] or ""),
                    "role": str(row["role"] or ""),
                    "avatar_url": str(row["avatar_url"] or "").strip() or None,
                }
        conn.close()
    except Exception:
        pass
    registry = load_agent_registry()
    for slug, ident in list(identities.items()):
        reg = registry.get(slug) if isinstance(registry.get(slug), dict) else {}
        if reg.get("display_name"):
            ident["display_name"] = str(reg["display_name"])
        if reg.get("tagline"):
            ident["tagline"] = str(reg["tagline"])
        if reg.get("role"):
            ident["role"] = str(reg["role"])
        if reg.get("avatar_url"):
            ident["avatar_url"] = str(reg["avatar_url"])
        if reg.get("avatar_id"):
            ident["avatar_id"] = str(reg["avatar_id"])
    return identities


def _agent_identity_fields(profile: str, workspace_id: str | None = None, user_id: str = "") -> dict[str, Any]:
    slug = safe_profile_slug(str(profile or "").strip())
    template = _runtime_template_slug(slug) if _is_runtime_profile_slug(slug) else slug
    reg = _agent_registry_row(slug)
    if user_id and template:
        runtime = _runtime_profile_slug(user_id, template)
        reg_user = _agent_registry_row(runtime)
        if reg_user.get("display_name") or reg_user.get("tagline") or reg_user.get("avatar_url"):
            reg = {**reg, **{k: v for k, v in reg_user.items() if v}}
    ident = _workspace_agent_identities(workspace_id).get(template, {})
    reg_template = _agent_registry_row(template)
    # Bind avatar_url + avatar_id from the SAME source tier: a custom url (cleared id) on one tier
    # must not pick up a different tier's stale id, which _resolve_avatar_fields would then prefer.
    avatar_url: Any = None
    avatar_id: Any = None
    for src in (reg, ident, reg_template):
        u = str(src.get("avatar_url") or "").strip()
        i = str(src.get("avatar_id") or "").strip()
        if u or i:
            avatar_url, avatar_id = u or None, i or None
            break
    out: dict[str, Any] = {
        "display_name": str(
            reg.get("display_name")
            or ident.get("display_name")
            or reg_template.get("display_name")
            or _profile_display_name(template)
        ),
        "tagline": str(reg.get("tagline") or ident.get("tagline") or reg_template.get("tagline") or ""),
        "role": str(reg.get("role") or ident.get("role") or reg_template.get("role") or _profile_role(template)),
        "avatar_url": avatar_url,
        "avatar_id": avatar_id,
    }
    _resolve_avatar_fields(out)
    return out


def crew_data(profiles: list[str], primary: str, gateway: dict[str, Any]) -> list[dict[str, Any]]:
    registry = load_agent_registry()
    idents = _workspace_agent_identities()
    ordered: list[str] = []
    if primary and primary in profiles:
        ordered.append(primary)
    for profile in sorted(profiles):
        if profile not in ordered:
            ordered.append(profile)
    crew: list[dict[str, Any]] = []
    for index, profile in enumerate(ordered):
        slug = _profile_slug(profile).lower()
        display = _profile_display_name(profile)
        native = _is_native_profile(profile)
        prof_key = safe_profile_slug(profile)
        reg = registry.get(prof_key) if isinstance(registry.get(prof_key), dict) else {}
        if not reg:
            legacy_row = registry.get(slug)
            if isinstance(legacy_row, dict):
                reg = legacy_row
        if reg.get("display_name"):
            display = str(reg["display_name"])
        ident = idents.get(prof_key, {})
        if ident.get("display_name"):
            display = str(ident["display_name"])
        role = str(ident.get("role") or reg.get("role") or _profile_role(profile))
        tagline = str(ident.get("tagline") or reg.get("tagline") or "")
        row: dict[str, Any] = {
            "profile": profile,
            "key": slug,
            "display_name": display,
            "code": _profile_code(display, slug),
            "role": role,
            "tagline": tagline,
            "color": CREW_COLORS[index % len(CREW_COLORS)],
            "is_native": native,
            "platform": _gateway_platform(gateway, native),
            "route_status": route_status_for_profile(profile),
        }
        if reg.get("avatar_url"):
            row["avatar_url"] = str(reg["avatar_url"])
        if reg.get("avatar_id"):
            row["avatar_id"] = str(reg["avatar_id"])
        if ident.get("avatar_url"):
            row["avatar_url"] = str(ident["avatar_url"])
        if ident.get("avatar_id"):
            row["avatar_id"] = str(ident["avatar_id"])
        _resolve_avatar_fields(row)
        crew.append(row)
    return crew


def _crew_lookup(crew: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for member in crew:
        for alias in (
            member.get("profile"),
            member.get("key"),
            member.get("display_name"),
            str(member.get("display_name", "")).lower(),
        ):
            if alias:
                lookup[str(alias).lower()] = member
    return lookup


def _resolve_agent(member: dict[str, Any] | None, fallback: str) -> dict[str, str]:
    if member:
        return {
            "agent_name": member["display_name"],
            "profile": member["profile"],
            "key": member["key"],
        }
    slug = fallback.lower()
    return {"agent_name": fallback, "profile": fallback, "key": slug}


def _message_activity(profile: str, crew_lookup: dict[str, Any], limit: int = 80) -> list[dict[str, Any]]:
    """Extract individual tool calls from messages table as atomic activity entries."""
    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    if not conn:
        return []
    entries: list[dict[str, Any]] = []
    member = crew_lookup.get(profile.lower()) or crew_lookup.get(_profile_slug(profile).lower())
    agent = _resolve_agent(member, _profile_display_name(profile))

    try:
        open_sessions = {
            str(row["id"])
            for row in conn.execute("SELECT id FROM sessions WHERE ended_at IS NULL").fetchall()
        }
        completed_tools = {
            str(row["tool_call_id"])
            for row in conn.execute(
                """
                SELECT tool_call_id FROM messages
                WHERE role = 'tool' AND tool_call_id IS NOT NULL AND tool_call_id != ''
                """,
            ).fetchall()
        }

        rows = conn.execute(
            """
            SELECT m.id, m.session_id, m.timestamp, m.token_count, m.content, m.tool_calls,
                   m.tool_name, s.model
            FROM messages m
            LEFT JOIN sessions s ON s.id = m.session_id
            WHERE m.role = 'assistant'
              AND m.tool_calls IS NOT NULL
              AND m.tool_calls != '[]'
            ORDER BY m.timestamp DESC
            LIMIT ?
            """,
            (limit * 3,),
        ).fetchall()

        for r in rows:
            timestamp = r["timestamp"]
            tool_calls_raw = r["tool_calls"]
            session_id = str(r["session_id"] or "")

            parsed_calls: list[dict[str, Any]] = []
            try:
                parsed_calls = json.loads(tool_calls_raw) if tool_calls_raw else []
            except (json.JSONDecodeError, TypeError):
                continue

            if not parsed_calls:
                continue

            model = r["model"] or ""

            for tc in parsed_calls:
                fn = tc.get("function") or {}
                tool_name = fn.get("name") or tc.get("tool_name") or "unknown"
                raw_args = fn.get("arguments") or tc.get("arguments") or "{}"

                args: dict[str, Any] = {}
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except (json.JSONDecodeError, TypeError):
                    pass

                label = _tool_call_label(tool_name, args)
                call_id = str(tc.get("id") or tc.get("call_id") or "")
                has_result = call_id in completed_tools
                session_open = session_id in open_sessions
                if has_result:
                    status = "completed"
                elif session_open:
                    status = "active"
                else:
                    status = "idle"
                summary = f"running tool: {tool_name}" if status == "active" else f"tool: {tool_name}"

                entries.append({
                    "id": f"tool:{profile}:{call_id or r['id']}:{tool_name}",
                    "kind": "tool_call",
                    "agent_name": agent["agent_name"],
                    "profile": agent["profile"],
                    "key": agent["key"],
                    "task_description": summary,
                    "status": status,
                    "model_used": model,
                    "created_at": _iso_from_unix(timestamp),
                    "source": "message",
                    "tool_call_id": call_id,
                    "message_id": r["id"],
                    "session_id": session_id,
                    "token_count": r["token_count"] or 0,
                    "tool_name": tool_name,
                })

                if len(entries) >= limit:
                    break

            if len(entries) >= limit:
                break

    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return entries


def _tool_call_label(tool_name: str, args: dict[str, Any]) -> str:
    """Build a short, human-readable label for a tool call."""
    name_lower = tool_name.lower()

    if name_lower == "read_file":
        path = args.get("path", "") or args.get("file_path", "")
        if path:
            short = str(path).split("/")[-1]
            return f"read {short}"
        return "read_file"

    if name_lower == "write_file":
        path = args.get("path", "") or args.get("file_path", "")
        if path:
            short = str(path).split("/")[-1]
            return f"write {short}"
        return "write_file"

    if name_lower == "terminal":
        cmd = args.get("command", "") or args.get("cmd", "")
        if cmd:
            cmd_str = str(cmd).strip()
            if len(cmd_str) > 40:
                return f"terminal: {cmd_str[:37]}…"
            return f"terminal: {cmd_str}"
        return "terminal"

    if name_lower in ("web_search", "search"):
        query = args.get("query", "")
        if query:
            q = str(query).strip()
            if len(q) > 35:
                return f"search: {q[:32]}…"
            return f"search: {q}"
        return "search"

    if name_lower == "skill_view":
        skill = args.get("name", "")
        if skill:
            return f"load skill: {skill}"
        return "skill_view"

    if name_lower == "browser_navigate":
        url = args.get("url", "")
        if url:
            from urllib.parse import urlparse
            parsed = urlparse(str(url))
            host = parsed.netloc or str(url)
            if len(host) > 30:
                return f"browser: {host[:27]}…"
            return f"browser: {host}"
        return "browser"

    if name_lower in ("delegate_task", "subagent"):
        goal = args.get("goal", "") or args.get("task", "")
        if goal:
            g = str(goal).strip()
            if len(g) > 35:
                return f"delegate: {g[:32]}…"
            return f"delegate: {g}"
        return "delegate"

    if name_lower == "memory":
        action = args.get("action", "")
        if action:
            return f"memory: {action}"
        return "memory"

    # Generic fallback: tool_name + first arg value
    if args:
        first_key = next(iter(args))
        first_val = str(args[first_key])
        if len(first_val) > 30:
            first_val = first_val[:27] + "…"
        return f"{tool_name}: {first_val}"

    return tool_name


def _activity_default_peer_handle() -> str:
    """Best-effort @handle for activity session subtitles."""
    try:
        conn = sqlite3.connect(str(_workframe_db_path()), timeout=2.0)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT display_name, email FROM users WHERE deleted_at IS NULL ORDER BY created_at ASC LIMIT 1",
        ).fetchone()
        conn.close()
        if row:
            handle = _mention_handle(str(row["display_name"] or ""), str(row["email"] or ""))
            if handle:
                return handle
    except (sqlite3.Error, OSError):
        pass
    return "user"


def _session_activity_label(
    conn: sqlite3.Connection,
    profile: str,
    session_id: str,
    title: str,
    msg_count: int,
    model: str,
) -> str:
    del conn, profile, session_id, title, msg_count, model  # ponytail: uniform label, not message dumps
    return f"chatting with @{_activity_default_peer_handle()}"


def _session_activity(profile: str, crew_lookup: dict[str, dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    if not conn:
        return []
    entries: list[dict[str, Any]] = []
    member = crew_lookup.get(profile.lower()) or crew_lookup.get(_profile_slug(profile).lower())
    agent = _resolve_agent(member, _profile_display_name(profile))
    try:
        rows = conn.execute(
            """
            SELECT id, source, title, started_at, ended_at, message_count, model
            FROM sessions
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        for r in rows:
            session_id = str(r["id"] or "")
            ended = r["ended_at"]
            msg_count = int(r["message_count"] or 0)
            model = str(r["model"] or "").strip()
            title = (r["title"] or "").strip()
            desc = _session_activity_label(conn, profile, session_id, title, msg_count, model)
            if len(desc) > 140:
                desc = desc[:137] + "..."
            status = "completed" if ended else "idle"
            entries.append(
                {
                    "id": f"session:{profile}:{session_id}",
                    "kind": "session_start",
                    "agent_name": agent["agent_name"],
                    "profile": agent["profile"],
                    "key": agent["key"],
                    "task_description": desc,
                    "status": status,
                    "model_used": model,
                    "created_at": _iso_from_unix(r["started_at"]),
                    "source": "session",
                    "session_id": session_id,
                    "message_count": msg_count,
                }
            )
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return entries


def _kanban_activity(
    crew_lookup: dict[str, dict[str, Any]],
    limit: int = 50,
    board_slug: str = "default",
) -> list[dict[str, Any]]:
    db = _hermes_kanban_db_path(board_slug)
    conn = _ro_sqlite_live(db)
    if not conn:
        return []
    entries: list[dict[str, Any]] = []
    try:
        rows = conn.execute(
            """
            SELECT e.kind, e.created_at, t.title, t.assignee, t.status
            FROM task_events e
            JOIN tasks t ON t.id = e.task_id
            ORDER BY e.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        for r in rows:
            assignee = str(r["assignee"] or "kanban")
            member = crew_lookup.get(assignee.lower()) or crew_lookup.get(_profile_slug(assignee).lower())
            agent = _resolve_agent(member, _profile_display_name(assignee) if assignee != "kanban" else "Kanban")
            desc = f"{r['title'] or 'task'} · {r['kind']}"
            if len(desc) > 140:
                desc = desc[:137] + "..."
            st = str(r["status"] or r["kind"] or "event").lower()
            if st in ("done", "completed"):
                status = "completed"
            elif "fail" in st or st == "blocked":
                status = "failed"
            else:
                status = st
            entries.append(
                {
                    "id": f"kanban:{assignee}:{r['created_at']}:{r['kind']}",
                    "kind": "kanban_task",
                    "agent_name": agent["agent_name"],
                    "profile": agent["profile"],
                    "key": agent["key"],
                    "task_description": desc,
                    "status": status,
                    "model_used": "",
                    "created_at": _iso_from_unix(r["created_at"]),
                    "source": "kanban",
                }
            )
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return entries


def activity_data(profiles: list[str], crew: list[dict[str, Any]]) -> dict[str, Any]:
    crew_lookup = _crew_lookup(crew)
    merged: list[dict[str, Any]] = []
    for p in profiles:
        merged.extend(_session_activity(p, crew_lookup, 40))
        merged.extend(_message_activity(p, crew_lookup, 60))
    merged.extend(_kanban_activity(crew_lookup, 40))
    merged.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    merged = merged[:80]

    agents: dict[str, dict[str, Any]] = {}
    for e in merged:
        key = str(e.get("key") or e.get("agent_name") or "unknown").lower()
        member = crew_lookup.get(key)
        a = agents.setdefault(
            key,
            {
                "name": e.get("agent_name") or key,
                "display_name": e.get("agent_name") or key,
                "profile": e.get("profile") or key,
                "key": key,
                "total": 0,
                "completed": 0,
                "failed": 0,
                "last_task": "",
                "last_status": "idle",
                "last_seen": "",
                "model": e.get("model_used") or "",
                "role": member.get("role") if member else "",
                "platform": member.get("platform") if member else "Hermes",
                "color": member.get("color") if member else "",
            },
        )
        a["total"] += 1
        st = str(e.get("status") or "").lower()
        if "fail" in st or st == "blocked":
            a["failed"] += 1
        elif st in ("completed", "done", "active"):
            a["completed"] += 1
        if not a["last_task"]:
            a["last_task"] = e.get("task_description") or ""
            a["last_status"] = e.get("status") or ""
            a["last_seen"] = e.get("created_at") or ""
            if e.get("model_used"):
                a["model"] = e["model_used"]

    for member in crew:
        key = member["key"]
        agents.setdefault(
            key,
            {
                "name": member["display_name"],
                "display_name": member["display_name"],
                "profile": member["profile"],
                "key": key,
                "total": 0,
                "completed": 0,
                "failed": 0,
                "last_task": "No activity yet",
                "last_status": "idle",
                "last_seen": "",
                "model": "",
                "role": member.get("role") or "",
                "platform": member.get("platform") or "Hermes",
                "color": member.get("color") or "",
            },
        )

    by_day: dict[str, dict[str, Any]] = {}
    for e in merged:
        day = str(e.get("created_at") or "")[:10]
        if not day:
            continue
        slot = by_day.setdefault(day, {"day": day, "total": 0, "agents": {}})
        slot["total"] += 1
        an = str(e.get("key") or e.get("agent_name") or "unknown").lower()
        slot["agents"][an] = slot["agents"].get(an, 0) + 1

    total = len(merged)
    completed = sum(
        1 for e in merged if str(e.get("status", "")).lower() in ("completed", "done", "active")
    )
    failed = sum(
        1
        for e in merged
        if "fail" in str(e.get("status", "")).lower() or str(e.get("status", "")).lower() == "blocked"
    )

    return {
        "entries": merged,
        "agents": list(agents.values()),
        "activity_by_day": [by_day[d] for d in sorted(by_day.keys())][-7:],
        "stats": {"total": total, "completed": completed, "failed": failed},
    }


def activity_detail(profile: str, tool_call_id: str, session_id: str, message_id: str) -> dict[str, Any]:
    """Return the full tool call request + result pair for a single activity entry."""
    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    if not conn:
        return {"ok": False, "error": "state.db not found"}

    result: dict[str, Any] = {
        "ok": True,
        "profile": profile,
        "tool_call_id": tool_call_id,
        "session_id": session_id,
        "request": None,
        "response": None,
        "metadata": {},
    }

    try:
        # 1. Find the assistant message with this tool_call_id in its tool_calls JSON
        assistant_params: list[Any] = [session_id] if session_id else []
        assistant_sql = """
            SELECT m.id, m.timestamp, m.token_count, m.content, m.tool_calls, s.model
            FROM messages m
            LEFT JOIN sessions s ON s.id = m.session_id
            WHERE m.role = 'assistant'
              AND m.tool_calls IS NOT NULL
              AND m.tool_calls != '[]'
        """
        if session_id:
            assistant_sql += " AND m.session_id = ?"
        if tool_call_id:
            assistant_sql += " AND m.tool_calls LIKE ?"
            assistant_params.append(f"%{tool_call_id}%")
        assistant_sql += " ORDER BY m.timestamp DESC LIMIT 100"
        assistant_rows = conn.execute(assistant_sql, tuple(assistant_params)).fetchall()

        tool_request: dict[str, Any] | None = None
        assistant_msg_id = ""
        assistant_ts = 0.0
        model = ""

        for r in assistant_rows:
            try:
                calls = json.loads(r["tool_calls"]) if r["tool_calls"] else []
            except (json.JSONDecodeError, TypeError):
                continue
            for tc in calls:
                tc_id = tc.get("id") or tc.get("call_id") or ""
                if tc_id == tool_call_id:
                    tool_request = tc
                    assistant_msg_id = r["id"]
                    assistant_ts = r["timestamp"] or 0.0
                    model = r["model"] or ""
                    break
            if tool_request:
                break

        if not tool_request:
            return {"ok": False, "error": "tool_call_id not found in session"}

        fn = tool_request.get("function") or {}
        tool_name = fn.get("name") or "unknown"
        raw_args = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
        except (json.JSONDecodeError, TypeError):
            args = {}

        result["request"] = {
            "tool_name": tool_name,
            "arguments": args,
            "message_id": assistant_msg_id,
            "timestamp": _iso_from_unix(assistant_ts),
            "model": model,
        }

        # 2. Find the tool result message (role=tool, tool_call_id matches)
        tool_row = conn.execute(
            """
            SELECT id, timestamp, content, token_count
            FROM messages
            WHERE session_id = ?
              AND role = 'tool'
              AND tool_call_id = ?
            LIMIT 1
            """,
            (session_id, tool_call_id),
        ).fetchone()

        if tool_row:
            raw_content = tool_row["content"] or ""
            # Try to parse as JSON for structured display
            try:
                parsed_content = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
            except (json.JSONDecodeError, TypeError):
                parsed_content = None

            result["response"] = {
                "content": raw_content,
                "parsed": parsed_content,
                "message_id": tool_row["id"],
                "timestamp": _iso_from_unix(tool_row["timestamp"]),
                "token_count": tool_row["token_count"] or 0,
            }
        else:
            result["response"] = None

        # 3. Session metadata
        session_row = conn.execute(
            "SELECT title, model, message_count, started_at, ended_at, tool_call_count, input_tokens, output_tokens FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if session_row:
            result["metadata"] = {
                "session_title": session_row["title"] or "",
                "model": session_row["model"] or model,
                "message_count": session_row["message_count"] or 0,
                "started_at": _iso_from_unix(session_row["started_at"]),
                "ended_at": _iso_from_unix(session_row["ended_at"]) if session_row["ended_at"] else None,
                "tool_call_count": session_row["tool_call_count"] or 0,
                "input_tokens": session_row["input_tokens"] or 0,
                "output_tokens": session_row["output_tokens"] or 0,
            }

        # 4. Run duration (response.timestamp - request.timestamp) — the time the
        # tool call took. Falls back to None if either timestamp is missing.
        result["run_duration_seconds"] = None
        req_ts = result.get("request", {}).get("timestamp") if result.get("request") else None
        resp_ts = result.get("response", {}).get("timestamp") if result.get("response") else None
        if req_ts and resp_ts:
            try:
                from datetime import datetime as _dt
                req_unix = _dt.fromisoformat(req_ts).timestamp()
                resp_unix = _dt.fromisoformat(resp_ts).timestamp()
                result["run_duration_seconds"] = round(max(0.0, resp_unix - req_unix), 3)
            except (TypeError, ValueError):
                pass

        # 5. Model/provider from the profile's config.yaml. Hermes stores the
        # profile slug in sessions.model, so the BFF prefers the config value
        # when available. Falls back to sessions.model if config is missing.
        provider, config_model = _read_model_from_config(profile)
        result["model_name"] = config_model or (session_row["model"] if session_row else "") or ""
        result["provider"] = provider

    except sqlite3.Error as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()

    return result


def kanban_data() -> dict[str, Any]:
    db = HERMES_DATA / "kanban.db"
    out: dict[str, Any] = {
        "ok": False,
        "total": 0,
        "tasks": [],
        "stats": {"todo": 0, "scheduled": 0, "ready": 0, "running": 0, "blocked": 0, "done": 0},
    }
    conn = _ro_sqlite_live(db)
    if not conn:
        return out
    try:
        rows = conn.execute(
            """
            SELECT id, title, status, assignee, priority, created_at, completed_at
            FROM tasks
            ORDER BY created_at DESC
            LIMIT 100
            """
        ).fetchall()
        tasks = [
            {
                "id": r["id"],
                "title": r["title"],
                "status": r["status"],
                "assignee": r["assignee"] or "",
                "priority": r["priority"] or 0,
                "created_at": _iso_from_unix(r["created_at"]),
                "completed_at": _iso_from_unix(r["completed_at"]) if r["completed_at"] else None,
            }
            for r in rows
        ]
        out["ok"] = True
        out["tasks"] = tasks
        out["total"] = len(tasks)
        for r in rows:
            st = str(r["status"] or "todo").lower()
            if st in out["stats"]:
                out["stats"][st] += 1
            elif st == "triage":
                out["stats"]["todo"] += 1
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return out


def _hermes_cron_jobs(profile: str) -> list[dict[str, Any]]:
    paths = [
        _profile_dir(profile) / "cron" / "jobs.json",
        HERMES_DATA / "cron" / "jobs.json",
    ]
    jobs: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(raw, dict):
            items = raw.get("jobs") or raw.get("items") or []
        elif isinstance(raw, list):
            items = raw
        else:
            items = []
        for job in items:
            if not isinstance(job, dict):
                continue
            schedule = job.get("schedule") or job.get("cron") or job.get("every") or ""
            command = job.get("prompt") or job.get("message") or job.get("name") or ""
            jobs.append(
                {
                    "id": job.get("id") or job.get("name") or "",
                    "name": job.get("name") or job.get("id") or "job",
                    "schedule": schedule,
                    "command": command[:200],
                    "enabled": job.get("enabled", True),
                    "owner": "hermes",
                    "label": "hermes",
                    "category": "hermes",
                    "source": str(path),
                    "description": _cron_plain_english(str(schedule)),
                    "prompt_preview": command[:120],
                }
            )
    return jobs


def _system_cron_jobs() -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    candidates = [
        Path("/etc/crontab"),
        Path("/var/spool/cron/crontabs/root"),
    ]
    cron_d = Path("/etc/cron.d")
    if cron_d.is_dir():
        candidates.extend(sorted(cron_d.glob("*")))
    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 5 if path.name == "crontab" or "crontabs" in str(path) else 6)
            if len(parts) < 6:
                continue
            if path.name == "crontab" or "crontabs" in str(path):
                schedule = " ".join(parts[:5])
                command = parts[5] if len(parts) > 5 else ""
            else:
                schedule = " ".join(parts[:5])
                command = parts[-1]
            jobs.append(
                {
                    "name": command.split()[0] if command else "system",
                    "schedule": schedule,
                    "command": command[:200],
                    "owner": "system",
                    "label": "system",
                    "category": "system",
                    "source": str(path),
                    "description": _cron_plain_english(schedule),
                    "enabled": True,
                }
            )
    return jobs[:50]


def cron_data(profile: str) -> dict[str, Any]:
    hermes = _hermes_cron_jobs(profile)
    system = _system_cron_jobs()
    all_jobs = hermes + system
    return {"jobs": all_jobs, "items": all_jobs, "count": len(all_jobs), "hermes": hermes, "system": system}


def _read_proc_stat() -> tuple[float, float]:
    try:
        line = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0]
        parts = [int(x) for x in line.split()[1:]]
        idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
        return float(sum(parts)), float(idle)
    except (OSError, ValueError, IndexError):
        return 0.0, 0.0


def health_data(profile: str) -> dict[str, Any]:
    global _cpu_cache
    mem_total_kb = mem_avail_kb = 0
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                mem_total_kb = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                mem_avail_kb = int(line.split()[1])
    except OSError:
        pass
    mem_total_mb = mem_total_kb / 1024
    mem_used_mb = max(0.0, mem_total_mb - mem_avail_kb / 1024)
    disk_total = disk_free = 0
    try:
        st = os.statvfs(str(WORKSPACE if WORKSPACE.exists() else HERMES_DATA))
        disk_total = st.f_blocks * st.f_frsize
        disk_free = st.f_bavail * st.f_frsize
    except OSError:
        pass
    disk_total_gb = disk_total / (1024**3)
    disk_used_gb = max(0.0, (disk_total - disk_free) / (1024**3))

    now = time.time()
    if now - float(_cpu_cache.get("at") or 0) > 3.0:
        t1, i1 = _read_proc_stat()
        time.sleep(0.12)
        t2, i2 = _read_proc_stat()
        cpu_pct = 0.0
        if t2 > t1:
            cpu_pct = max(0.0, min(100.0, (1.0 - (i2 - i1) / (t2 - t1)) * 100.0))
        _cpu_cache = {"at": now, "percent": round(cpu_pct, 1)}
    cpu_pct = float(_cpu_cache.get("percent") or 0.0)
    mem_pct = max(0.0, min(100.0, (mem_used_mb / mem_total_mb * 100) if mem_total_mb else 0.0))
    disk_pct = max(0.0, min(100.0, (disk_used_gb / disk_total_gb * 100) if disk_total_gb else 0.0))
    db_path = _profile_dir(profile) / "state.db" if profile else HERMES_DATA / "state.db"

    return {
        "cpu_percent": cpu_pct,
        "memory_percent": round(mem_pct, 1),
        "disk_percent": round(disk_pct, 1),
        "cpu_pct": cpu_pct,
        "mem_pct": round(mem_pct, 1),
        "disk_pct": round(disk_pct, 1),
        "mem_used_mb": round(mem_used_mb, 1),
        "mem_total_mb": round(mem_total_mb, 1),
        "disk_used_gb": round(disk_used_gb, 2),
        "disk_total_gb": round(disk_total_gb, 2),
        "db_size_mb": round(_file_size_mb(db_path), 2),
    }


def _safe_content_path(rel: str) -> Path | None:
    return _safe_workspace_path(rel)


def _safe_workspace_path(rel: str) -> Path | None:
    rel = rel.replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    path = (WORKSPACE / rel).resolve()
    try:
        path.relative_to(WORKSPACE.resolve())
    except ValueError:
        return None
    return path


def _workspace_rel(path: Path) -> str:
    return path.relative_to(WORKSPACE).as_posix()


def _list_folder_nodes(folder: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        entries = sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except OSError:
        return out
    for p in entries:
        if p.name in TREE_SKIP_NAMES:
            continue
        rel = _workspace_rel(p)
        if _workspace_protected_reason(rel):
            continue
        node: dict[str, Any] = {
            "id": rel,
            "name": p.name,
            "type": "folder" if p.is_dir() else "file",
        }
        if p.is_dir():
            node["children"] = []
            node["children_loaded"] = False
        out.append(node)
    return out


def _files_tree_root_name() -> str:
    """Navigator root label follows workspace branding, not WORKFRAME_PROJECT env."""
    try:
        conn = _workframe_db()
        branding = _primary_workspace_branding(conn)
        conn.close()
        if branding:
            name = str(branding.get("display_name") or "").strip()
            if name:
                return name
    except Exception:
        pass
    return PROJECT_NAME


def files_tree() -> dict[str, Any]:
    current_revision = str(workspace_state().get("revision") or "")
    root_name = _files_tree_root_name()
    with _workspace_tree_lock:
        cached_revision = str(_workspace_tree_cache.get("revision") or "")
        cached_root = _workspace_tree_cache.get("root")
        if cached_root and cached_revision == current_revision:
            if str(cached_root.get("name") or "") == root_name:
                return cached_root
            refreshed = dict(cached_root)
            refreshed["name"] = root_name
            _workspace_tree_cache["root"] = refreshed
            return refreshed

    root = {
        "id": "root",
        "name": root_name,
        "type": "folder",
        "children": [],
    }
    if not WORKSPACE.is_dir():
        return root
    root["children"] = _list_folder_nodes(WORKSPACE)
    with _workspace_tree_lock:
        _workspace_tree_cache["revision"] = current_revision
        _workspace_tree_cache["root"] = root
    return root


def files_list(rel: str = "") -> dict[str, Any]:
    folder = WORKSPACE if not rel.strip() else _safe_workspace_path(rel)
    if folder is None or not folder.exists() or not folder.is_dir():
        raise ValueError("folder not found")
    reason = _workspace_protected_reason(rel)
    if reason:
        raise PermissionError(f"protected file: {reason}")
    folder_rel = "" if folder == WORKSPACE else _workspace_rel(folder)
    return {
        "ok": True,
        "path": folder_rel,
        "children": _list_folder_nodes(folder),
    }


def _scan_workspace_state() -> dict[str, Any]:
    files = 0
    latest_mtime = 0.0
    latest_rel = ""
    if WORKSPACE.is_dir():
        try:
            for path in WORKSPACE.rglob("*"):
                if not path.is_file():
                    continue
                if path.name in TREE_SKIP_NAMES:
                    continue
                try:
                    rel = _workspace_rel(path)
                except ValueError:
                    continue
                if _workspace_protected_reason(rel):
                    continue
                files += 1
                try:
                    mtime = float(path.stat().st_mtime)
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest_mtime = mtime
                    latest_rel = rel
        except OSError:
            pass
    revision = f"{int(latest_mtime)}:{files}:{latest_rel}"
    return {
        "ok": True,
        "revision": revision,
        "files": files,
        "updated_at": _iso_from_unix(latest_mtime),
        "latest_path": latest_rel,
    }


def _refresh_workspace_state() -> dict[str, Any]:
    state = _scan_workspace_state()
    with _workspace_state_lock:
        generation = int(_workspace_state_cache.get("generation") or 0)
        _workspace_state_cache.update(state)
        _workspace_state_cache["generation"] = generation
        if generation:
            _workspace_state_cache["revision"] = f"{state['revision']}:{generation}"
        return dict(_workspace_state_cache)


def workspace_state() -> dict[str, Any]:
    with _workspace_state_lock:
        return dict(_workspace_state_cache)


def _bump_workspace_state(path: Path | None = None) -> None:
    now = time.time()
    rel = ""
    if path is not None:
        try:
            rel = _workspace_rel(path)
        except Exception:  # noqa: BLE001
            rel = ""
    with _workspace_state_lock:
        current_files = int(_workspace_state_cache.get("files") or 0)
        generation = int(_workspace_state_cache.get("generation") or 0) + 1
        _workspace_state_cache.update(
            {
                "ok": True,
                "revision": f"{int(now)}:{current_files}:{rel}:{generation}",
                "updated_at": _iso_from_unix(now),
                "latest_path": rel,
                "generation": generation,
            }
        )
    with _workspace_tree_lock:
        _workspace_tree_cache["revision"] = ""
        _workspace_tree_cache["root"] = None


def _workspace_state_daemon() -> None:
    while True:
        try:
            _refresh_workspace_state()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)


def file_read(rel: str) -> dict[str, Any]:
    reason = _workspace_protected_reason(rel)
    if reason:
        raise PermissionError(f"protected file: {reason}")
    fp = _safe_workspace_path(rel)
    if not fp or not fp.exists() or not fp.is_file():
        raise ValueError("not found")
    try:
        text = fp.read_text(encoding="utf-8")
        return {"path": _workspace_rel(fp), "content": text}
    except UnicodeDecodeError:
        return {"path": _workspace_rel(fp), "content": ""}


def file_write(rel: str, content: str) -> dict[str, Any]:
    reason = _workspace_protected_reason(rel)
    if reason:
        raise PermissionError(f"protected file: {reason}")
    fp = _safe_workspace_path(rel)
    if not fp:
        raise ValueError("invalid path")
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8")
    _bump_workspace_state(fp)
    return {"ok": True, "path": _workspace_rel(fp)}


def file_upload_binary(rel: str, content_b64: str) -> dict[str, Any]:
    reason = _workspace_protected_reason(rel)
    if reason:
        raise PermissionError(f"protected file: {reason}")
    fp = _safe_workspace_path(rel)
    if not fp:
        raise ValueError("invalid path")
    try:
        raw = base64.b64decode(content_b64, validate=True)
    except ValueError as exc:
        raise ValueError("invalid base64") from exc
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_bytes(raw)
    _bump_workspace_state(fp)
    return {"ok": True, "path": _workspace_rel(fp), "size": len(raw)}


def file_raw(rel: str) -> tuple[bytes, str]:
    reason = _workspace_protected_reason(rel)
    if reason:
        raise PermissionError(f"protected file: {reason}")
    fp = _safe_workspace_path(rel)
    if not fp or not fp.is_file():
        raise ValueError("not found")
    mime, _ = mimetypes.guess_type(str(fp))
    return fp.read_bytes(), mime or "application/octet-stream"


_USER_IMAGE_RE = re.compile(
    r"\[User attached image:\s*([^\]]+)\]|📎\s*Attached image:\s*(\S+)",
    re.IGNORECASE,
)


def _parse_multimodal_content(content: str) -> list[dict[str, Any]]:
    text = (content or "").strip()
    if not text.startswith("["):
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    segments: list[dict[str, Any]] = []
    for part in data:
        if not isinstance(part, dict):
            continue
        kind = str(part.get("type") or "")
        if kind in {"image_url", "input_image", "image"}:
            url = ""
            if isinstance(part.get("image_url"), dict):
                url = str(part["image_url"].get("url") or "")
            elif isinstance(part.get("image_url"), str):
                url = part["image_url"]
            path = str(part.get("path") or url or "image")
            segments.append({"kind": "image", "path": path, "name": Path(path).name})
        elif kind in {"text", "input_text", "output_text"}:
            body = str(part.get("text") or part.get("content") or "").strip()
            if body:
                segments.append({"kind": "text", "text": body})
    return segments


def _parse_user_content_segments(content: str) -> list[dict[str, Any]]:
    text = (content or "").strip()
    if not text:
        return []
    multimodal = _parse_multimodal_content(text)
    if multimodal:
        return multimodal
    segments: list[dict[str, Any]] = []
    remainder = text
    for match in _USER_IMAGE_RE.finditer(text):
        name = (match.group(1) or match.group(2) or "").strip()
        if name:
            segments.append({"kind": "image", "path": name, "name": Path(name).name})
        remainder = remainder.replace(match.group(0), " ").strip()
    if remainder:
        segments.append({"kind": "text", "text": remainder})
    elif not segments:
        segments.append({"kind": "text", "text": text})
    return segments


def _parse_tool_content(content: str) -> dict[str, Any]:
    """Parse Hermes tool row JSON when present."""
    text = (content or "").strip()
    if not text:
        return {"output": "", "exit_code": None, "error": None}
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            output = data.get("output")
            if output is None:
                output = data.get("result")
            if output is None and "files" in data:
                output = json.dumps(data, ensure_ascii=False)
            elif output is None:
                output = text
            return {
                "output": str(output or ""),
                "exit_code": data.get("exit_code"),
                "error": data.get("error"),
            }
    except json.JSONDecodeError:
        pass
    return {"output": text, "exit_code": None, "error": None}


def _message_row_segments(m: sqlite3.Row) -> list[dict[str, Any]]:
    """Map one state.db messages row to structured UI segments."""
    role = str(m["role"] or "")
    if role == "session_meta":
        return []

    segments: list[dict[str, Any]] = []
    reasoning = (m["reasoning_content"] or "").strip()
    content = (m["content"] or "").strip()
    tool_name = (m["tool_name"] or "").strip()

    if reasoning:
        segments.append({"kind": "thinking", "text": reasoning})

    if role == "tool":
        parsed = _parse_tool_content(content)
        exit_code = parsed.get("exit_code")
        status = "error" if parsed.get("error") or (exit_code not in (None, 0)) else "done"
        segments.append(
            {
                "kind": "tool",
                "name": tool_name or "tool",
                "status": status,
                "output": parsed.get("output") or "",
            }
        )
    elif role == "user":
        segments.extend(_parse_user_content_segments(content))
    elif content:
        segments.append({"kind": "text", "text": content})

    return segments


def _profile_model(profile: str) -> str:
    """Read configured model from Hermes profile yaml, else latest session model."""
    block = _read_model_block(profile)
    configured = str(block.get("default") or "").strip()
    if configured:
        return configured
    for name in ("config.yaml", "profile.yaml"):
        path = _profile_dir(profile) / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        flat = re.search(r"^[ \t]*model:[ \t]*['\"]?([^'\"#\n]+)['\"]?[ \t]*(?:#.*)?$", text, re.MULTILINE)
        if flat:
            value = flat.group(1).strip()
            if value and not value.endswith(":"):
                return value

    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    if not conn:
        return ""
    try:
        row = conn.execute(
            "SELECT model FROM sessions WHERE model IS NOT NULL AND model != '' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return ""
        model = str(row["model"] or "").strip()
        if model.startswith("default:"):
            model = model.split(":", 1)[1].strip()
        return model
    except sqlite3.Error:
        return ""
    finally:
        conn.close()


def _llm_attribution_for_profile(profile: str, session_model: str = "") -> tuple[str, str]:
    """Resolve model id + billing provider for chat turn footers."""
    _ = session_model  # ponytail: Hermes sessions.model is profile slug, not LLM id
    try:
        prof = resolve_hermes_profile(str(profile or "").strip())
    except ValueError:
        return "", ""
    block = _read_model_block(prof)
    model = str(block.get("default") or "").strip()
    billing = _billing_provider_id_from_hermes_config(str(block.get("provider") or ""))
    if not billing:
        billing = _llm_billing_provider(prof)
    if not billing and model:
        infer_llm = {
            str(spec["id"]).lower()
            for spec in PROVIDER_CONNECT_CATALOG
            if str(spec.get("category") or "") == "llm"
        }
        billing = _resolve_billing_provider_for_model(model, infer_llm)
    return model, str(billing or "").strip()


def _latest_session_id(profile: str) -> str:
    """Most recent session — prefer active (ended_at IS NULL), then by started_at."""
    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    if not conn:
        return ""
    try:
        row = conn.execute(
            """
            SELECT id FROM sessions
            ORDER BY (ended_at IS NULL) DESC, started_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        return str(row["id"]) if row else ""
    except sqlite3.Error:
        return ""
    finally:
        conn.close()


def _session_info(profile: str, session_id: str) -> dict[str, Any]:
    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    if not conn:
        return {
            "session_id": session_id,
            "title": "",
            "active": False,
            "message_count": 0,
        }
    try:
        row = conn.execute(
            """
            SELECT id, title, started_at, ended_at, message_count
            FROM sessions WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
        if not row:
            return {
                "session_id": session_id,
                "title": "",
                "active": False,
                "message_count": 0,
            }
        return {
            "session_id": str(row["id"]),
            "title": (row["title"] or "").strip(),
            "active": row["ended_at"] is None,
            "message_count": int(row["message_count"] or 0),
            "started_at": _iso_from_unix(row["started_at"]),
        }
    except sqlite3.Error:
        return {
            "session_id": session_id,
            "title": "",
            "active": False,
            "message_count": 0,
        }
    finally:
        conn.close()


def _is_blank_session_title(title: str) -> bool:
    t = str(title or "").strip()
    return not t or t == "(untitled)"


def _resolved_session_title(hermes_prof: str, session_id: str, fallback: str = "") -> str:
    """Hermes state.db title, else room_sessions / default — not the (untitled) sentinel."""
    info = _session_info(hermes_prof, session_id)
    title = str(info.get("title") or "").strip()
    if not _is_blank_session_title(title):
        return title
    fb = str(fallback or "").strip()
    if fb and not _is_blank_session_title(fb):
        return fb
    template = (
        _runtime_template_slug(hermes_prof)
        if _is_runtime_profile_slug(hermes_prof)
        else hermes_prof
    )
    return _default_session_title(template)


def _ensure_hermes_session_title(profile: str, session_id: str, title: str) -> None:
    """Backfill empty Hermes session titles on bind via profile API (state.db is often gateway-locked)."""
    sid = str(session_id or "").strip()
    want = str(title or "").strip()
    if not sid or _is_blank_session_title(want):
        return
    if not _is_blank_session_title(str(_session_info(profile, sid).get("title") or "")):
        return
    try:
        path = f"/api/sessions/{urllib.parse.quote(sid, safe='')}"
        status, _ = _profile_api_request(profile, "PATCH", path, {"title": want})
        if status < 300:
            return
    except Exception:  # noqa: BLE001
        pass


def _session_info_display(profile: str, session_id: str, fallback: str = "") -> dict[str, Any]:
    """Like _session_info but title is never blank — for API responses that show humans a label."""
    info = _session_info(profile, session_id)
    title = _resolved_session_title(profile, session_id, fallback)
    info["title"] = title if not _is_blank_session_title(title) else "(untitled)"
    return info


def _latest_api_session_id(profile: str) -> str:
    """Most recent api_server session — prefer active, then by started_at."""
    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    if not conn:
        return ""
    try:
        row = conn.execute(
            """
            SELECT id FROM sessions
            WHERE source = 'api_server'
            ORDER BY (ended_at IS NULL) DESC, started_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        return str(row["id"]) if row else ""
    except sqlite3.Error:
        return ""
    finally:
        conn.close()


def _latest_active_run_id(profile: str) -> str:
    """Most recent active (ended_at IS NULL) api_server run session (run_ prefixed)."""
    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    if not conn:
        return ""
    try:
        row = conn.execute(
            """
            SELECT id FROM sessions
            WHERE source = 'api_server' AND ended_at IS NULL
            AND id LIKE 'run%'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        return str(row["id"]) if row else ""
    except sqlite3.Error:
        return ""
    finally:
        conn.close()

def _session_exists(profile: str, session_id: str) -> bool:
    sid = (session_id or "").strip()
    if not sid:
        return False
    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    if not conn:
        return False
    try:
        row = conn.execute("SELECT 1 FROM sessions WHERE id = ?", (sid,)).fetchone()
        return row is not None
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def chat_session(profile: str, session_id: str = "", source_id: str = "ui") -> dict[str, Any]:
    sid = (session_id or "").strip() or _latest_session_id(profile)
    if not sid:
        return {"ok": True, "session_id": "", "title": "", "active": False, "message_count": 0}
    info = _session_info(profile, sid)
    return {"ok": True, **info}


def chat_bootstrap(profile: str, persistent: str = "", source_id: str = "ui") -> dict[str, Any]:
    """Resolve native profile + latest/persistent Hermes session ids + dashboard WS bootstrap."""
    prof = (profile or "").strip() or _primary_profile()
    latest_id = _latest_session_id(prof)
    persistent_id = (persistent or "").strip()
    persistent_valid = persistent_id and _session_exists(prof, persistent_id)

    active_id = persistent_id if persistent_valid else ""
    latest_info = _session_info(prof, latest_id) if latest_id else {}
    persistent_info = _session_info(prof, persistent_id) if persistent_valid else {}
    active_info = _session_info(prof, active_id) if active_id else {}

    try:
        hermes = hermes_bootstrap(prof)
    except ValueError as exc:
        hermes = {"ok": False, "error": str(exc)}

    display = _profile_display_name(prof) if prof else _native_display_name()
    return {
        "ok": True,
        "profile": prof,
        "native_agent_name": display,
        "latest_session_id": latest_id,
        "latest_session": latest_info,
        "persistent_session_id": persistent_id if persistent_valid else "",
        "persistent_session": persistent_info,
        "active_session_id": active_id,
        "active_session": active_info,
        "hermes": hermes,
    }


def chat_messages(profile: str, session_id: str = "", source_id: str = "ui") -> dict[str, Any]:
    """Recent chat turns for one Hermes session — grouped agent turns with segments."""
    sid = (session_id or "").strip() or _latest_session_id(profile)
    session = _session_info(profile, sid) if sid else {}
    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    if not conn or not sid:
        return {"ok": True, "session_id": sid, "session": session, "messages": []}
    turns: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    author_profile = (
        _runtime_template_slug(profile) if _is_runtime_profile_slug(profile) else profile
    )
    display = _profile_display_name(profile)
    attr_model, attr_provider = _llm_attribution_for_profile(profile)
    try:
        raw = conn.execute(
            """
            SELECT m.id, m.role, m.content, m.reasoning_content, m.tool_name,
                   m.timestamp, m.token_count, s.model AS session_model
            FROM messages m
            LEFT JOIN sessions s ON s.id = m.session_id
            WHERE m.role IN ('user', 'assistant', 'tool') AND m.session_id = ?
            ORDER BY m.timestamp ASC, m.id ASC
            LIMIT 200
            """,
            (sid,),
        ).fetchall()
        for m in raw:
            role = str(m["role"] or "")
            segments = _message_row_segments(m)
            if not segments:
                continue
            tokens = int(m["token_count"] or 0)
            ts = _iso_from_unix(m["timestamp"])

            if role == "user":
                if current:
                    turns.append(current)
                    current = None
                turns.append(
                    {
                        "id": f"msg-{m['id']}",
                        "authorId": "user",
                        "authorName": "You",
                        "role": "user",
                        "segments": segments,
                        "timestamp": ts,
                        "tokens": tokens,
                    }
                )
                continue

            if current and current["role"] == "agent":
                current["segments"].extend(segments)
                current["tokens"] += tokens
                if attr_model:
                    current["model"] = attr_model
                    current["llm_provider"] = attr_provider
            else:
                if current:
                    turns.append(current)
                current = {
                    "id": f"turn-{m['id']}",
                    "authorId": author_profile,
                    "authorName": display,
                    "role": "agent",
                    "segments": list(segments),
                    "timestamp": ts,
                    "tokens": tokens,
                    "model": attr_model,
                    "llm_provider": attr_provider,
                }
        if current:
            turns.append(current)
    except sqlite3.Error:
        return {"ok": True, "session_id": sid, "session": session, "messages": []}
    finally:
        conn.close()
    return {"ok": True, "session_id": sid, "session": session, "messages": turns}


def _load_lane_registry() -> dict[str, Any]:
    path = _lane_registry_json()
    if not path.is_file():
        return {"profiles": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("profiles"), dict):
            return data
    except Exception:  # noqa: BLE001
        pass
    return {"profiles": {}}


def _save_lane_registry(data: dict[str, Any]) -> None:
    path = _lane_registry_json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, unix_path: str):
        super().__init__("localhost")
        self.unix_path = unix_path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.unix_path)
        self.sock = sock


def _docker_request(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    if SECURE_MODE:
        raise RuntimeError("Docker socket access is disabled in SECURE_MODE")
    conn = _UnixHTTPConnection(DOCKER_SOCK)
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    conn.request(method, f"/v1.41{path}", body=payload, headers=headers)
    resp = conn.getresponse()
    raw = resp.read()
    conn.close()
    if not raw:
        return resp.status, None
    try:
        return resp.status, json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return resp.status, raw.decode("utf-8", errors="replace")


def _gateway_container_exec(cmd: list[str]) -> tuple[int, str]:
    """Run a command in the gateway container — via supervisor in SECURE_MODE."""
    if SECURE_MODE:
        return _supervisor_container_exec(cmd)
    return _docker_exec(GATEWAY_CONTAINER_NAME, cmd)


def _hermes_agent_version() -> str:
    """Native Hermes semver from `hermes --version` inside the gateway container."""
    try:
        code, out = _gateway_exec(_primary_profile(), ["--version"])
        if code != 0:
            return ""
        return stack_updates.parse_hermes_version_output(out)
    except Exception:  # noqa: BLE001
        return ""


def _gateway_container_exec_detached(cmd: list[str]) -> tuple[int, str]:
    """Detached gateway exec — long-running jobs survive after exec returns."""
    if SECURE_MODE:
        return _supervisor_container_exec(cmd, detach=True)
    return _docker_exec_detached(GATEWAY_CONTAINER_NAME, cmd)


def _docker_exec_detached(container: str, cmd: list[str], acting_profile: str = "") -> tuple[int, str]:
    if _exec_targets_runtime_profile_secrets(cmd, acting_profile):
        return 1, "blocked: runtime profile credential paths are not readable via gateway exec"
    create_status, create_data = _docker_request(
        "POST",
        f"/containers/{urllib.parse.quote(container, safe='')}/exec",
        {
            "AttachStdout": True,
            "AttachStderr": True,
            "Tty": False,
            "Cmd": cmd,
        },
    )
    if create_status >= 300 or not isinstance(create_data, dict) or not create_data.get("Id"):
        return create_status, f"exec create failed: {create_data}"
    exec_id = str(create_data["Id"])
    start_status, _start_data = _docker_request(
        "POST",
        f"/exec/{urllib.parse.quote(exec_id, safe='')}/start",
        {"Detach": True, "Tty": False},
    )
    if start_status >= 300:
        return start_status, "exec start failed"
    return 0, ""


def _docker_exec(container: str, cmd: list[str], acting_profile: str = "") -> tuple[int, str]:
    if _exec_targets_runtime_profile_secrets(cmd, acting_profile):
        return 1, "blocked: runtime profile credential paths are not readable via gateway exec"
    create_status, create_data = _docker_request(
        "POST",
        f"/containers/{urllib.parse.quote(container, safe='')}/exec",
        {
            "AttachStdout": True,
            "AttachStderr": True,
            "Tty": False,
            "Cmd": cmd,
        },
    )
    if create_status >= 300 or not isinstance(create_data, dict) or not create_data.get("Id"):
        return create_status, f"exec create failed: {create_data}"
    exec_id = str(create_data["Id"])
    start_status, start_data = _docker_request(
        "POST",
        f"/exec/{urllib.parse.quote(exec_id, safe='')}/start",
        {"Detach": False, "Tty": False},
    )
    out = start_data if isinstance(start_data, str) else json.dumps(start_data or {})
    if isinstance(out, str) and out:
        try:
            raw = out.encode("latin-1", errors="ignore")
            buf = bytearray()
            i = 0
            # Docker non-TTY exec streams are 8-byte header framed.
            while i + 8 <= len(raw):
                size = int.from_bytes(raw[i + 4 : i + 8], "big")
                i += 8
                if size < 0 or i + size > len(raw):
                    break
                buf.extend(raw[i : i + size])
                i += size
            if buf:
                out = buf.decode("utf-8", errors="replace")
        except Exception:
            pass
    inspect_status, inspect_data = _docker_request("GET", f"/exec/{urllib.parse.quote(exec_id, safe='')}/json")
    if inspect_status >= 300 or not isinstance(inspect_data, dict):
        return start_status, out
    exit_raw = inspect_data.get("ExitCode")
    exit_code = 0 if exit_raw in (0, "0") else int(exit_raw or 1)
    return exit_code, out


def _profile_home_container(profile: str) -> str:
    return f"/opt/data/profiles/{resolve_hermes_profile(profile)}"


def _gateway_exec(profile: str, args: list[str]) -> tuple[int, str]:
    """Run hermes CLI in the gateway container with specialist profile home."""
    prof = resolve_hermes_profile(profile)
    if SECURE_MODE:
        return _supervisor_gateway_exec(prof, args)
    cli = ["/opt/hermes/bin/hermes", "-p", prof, *args]
    if prof == _primary_profile():
        return _docker_exec(GATEWAY_CONTAINER_NAME, cli, acting_profile=prof)
    home = _profile_home_container(prof)
    inner = " ".join(shlex.quote(part) for part in cli)
    shell = (
        f"export HERMES_HOME={shlex.quote(home)} HOME={shlex.quote(home)}; "
        f"cd {shlex.quote(home)}; {inner}"
    )
    return _docker_exec(GATEWAY_CONTAINER_NAME, ["sh", "-lc", shell], acting_profile=prof)


def _provider_env_var(provider: str) -> str:
    spec = _catalog_provider(provider)
    if spec and str(spec.get("env_var") or "").strip():
        return str(spec["env_var"]).strip()
    return _default_credential_env_var(provider, "api_key")


def _credential_secret(resolved: dict[str, Any], user_id: str = "") -> str:
    ref = str(resolved.get("credential_ref") or "")
    binding_id = credential_vault.parse_vault_ref(ref)
    if binding_id:
        return credential_vault.read_secret(binding_id)
    env_var = str(resolved.get("env_var") or "")
    if not env_var and ref.startswith("env:"):
        env_var = ref[4:]
    if not env_var:
        return ""
    scope = str(resolved.get("scope") or "")
    secret = ""
    if scope == "user":
        user = str(user_id or resolved.get("user_id") or "").strip()
        if user:
            secret = _read_env_map(_user_hermes_env_path(user)).get(env_var, "")
            if secret:
                bid = str(resolved.get("credential_binding_id") or resolved.get("credential_id") or "").strip()
                if bid:
                    credential_vault.store_secret(
                        bid,
                        secret,
                        env_var=env_var,
                        provider=str(resolved.get("provider") or ""),
                        scope="user",
                        user_id=user,
                    )
                    _remove_env_secret(_user_hermes_env_path(user), env_var)
    elif scope == "workspace":
        secret = _stack_profile_env().get(env_var, "")
    elif scope == "stack":
        secret = _stack_profile_env().get(env_var, "")
    return secret


def _resolve_secret_for_lease(
    payer_user_id: str,
    workspace_id: str,
    provider: str,
    binding_id: str,
) -> tuple[str, str]:
    provider = str(provider or "openrouter").strip().lower()
    binding_id = str(binding_id or "").strip()
    if binding_id:
        secret = credential_vault.read_secret(binding_id)
        if secret:
            return _provider_env_var(provider), secret
    resolved = _resolve_credential(payer_user_id, workspace_id, provider, user_only=True)
    if not resolved:
        resolved = _resolve_credential(payer_user_id, workspace_id, provider, user_only=False)
    if not resolved:
        return "", ""
    env_var = str(resolved.get("env_var") or "") or _provider_env_var(provider)
    return env_var, _credential_secret(resolved, payer_user_id)


def _llm_proxy_base_url(provider: str) -> str:
    return f"{WORKFRAME_LLM_PROXY_INTERNAL}/internal/llm/{str(provider or 'openrouter').strip().lower()}/v1"


PROXY_HEADER_TEMPLATE = "${WORKFRAME_PROXY_TOKEN}"


def _upsert_model_default_header(
    lines: list[str],
    header_key: str,
    header_val: str,
) -> list[str]:
    """Ensure model.default_headers contains header_key: header_val (single block)."""
    text = "".join(lines)
    if f"{header_key}: {header_val}" in text or f"{header_key}: '{header_val}'" in text:
        return lines
    out: list[str] = []
    in_model = False
    in_headers = False
    wrote = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("model:"):
            in_model = True
            in_headers = False
            out.append(line)
            continue
        if in_model and stripped.startswith("default_headers:"):
            in_headers = True
            out.append(line)
            continue
        if in_model and in_headers and stripped.startswith(f"{header_key}:"):
            indent = line[: len(line) - len(stripped)]
            out.append(f"{indent}{header_key}: {header_val}\n")
            wrote = True
            continue
        if in_model and in_headers and not wrote:
            # ponytail: sibling model keys + top-level keys end the headers block — append before them
            ends_headers = bool(
                stripped and not line.startswith(("    ", "\t")) and not stripped.startswith("#")
            )
            if ends_headers:
                out.append(f"    {header_key}: {header_val}\n")
                wrote = True
                in_headers = False
        if in_model and stripped and not line.startswith((" ", "\t", "#")):
            if not wrote and not in_headers:
                out.append("  default_headers:\n")
                out.append(f"    {header_key}: {header_val}\n")
                wrote = True
            in_model = False
            in_headers = False
        out.append(line)
    if not wrote:
        rebuilt: list[str] = []
        inserted = False
        for line in out:
            rebuilt.append(line)
            if not inserted and line.lstrip().startswith("model:"):
                rebuilt.append("  default_headers:\n")
                rebuilt.append(f"    {header_key}: {header_val}\n")
                inserted = True
        if not inserted:
            rebuilt.insert(
                0,
                f"model:\n  default_headers:\n    {header_key}: {header_val}\n",
            )
        out = rebuilt
    return out


def _ensure_profile_proxy_headers(profile: str) -> None:
    """Hermes default_headers: proxy token + profile slug for lease binding at /internal/*."""
    prof = safe_profile_slug(profile)
    _normalize_profile_config_yaml(prof)
    try:
        config_path = _ensure_gateway_config_file(prof)
    except ValueError:
        return
    header_specs: list[tuple[str, str]] = [(internal_proxy_auth.PROFILE_HEADER, prof)]
    if internal_proxy_auth.proxy_token_configured():
        header_specs.append((internal_proxy_auth.PROXY_TOKEN_HEADER, PROXY_HEADER_TEMPLATE))
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError:
        return
    lines = raw.splitlines(keepends=True)
    for header_key, header_val in header_specs:
        lines = _upsert_model_default_header(lines, header_key, header_val)
    try:
        config_path.write_text("".join(lines), encoding="utf-8")
    except OSError:
        return


def _set_profile_model_base_url(profile: str, base_url: str) -> tuple[bool, str]:
    _normalize_profile_config_yaml(profile)
    try:
        config_path = _ensure_gateway_config_file(profile)
    except ValueError as exc:
        return False, str(exc)
    base_url = str(base_url or "").strip()
    if not base_url:
        return False, "base_url required"
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"read failed: {exc}"
    lines = raw.splitlines(keepends=True)
    out: list[str] = []
    in_model = False
    wrote = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("model:"):
            if not in_model:
                in_model = True
                rest = stripped.split(":", 1)[1].strip().strip("'\"")
                if rest:
                    out.append("model:\n")
                    out.append(f"  default: {rest}\n")
                else:
                    out.append("model:\n")
            continue
        if in_model and stripped and not line.startswith((" ", "\t", "#")):
            if not wrote:
                out.append(f"  base_url: {base_url}\n")
                wrote = True
            in_model = False
        if in_model and stripped.startswith("base_url:"):
            out.append(f"  base_url: {base_url}\n")
            wrote = True
            continue
        out.append(line)
    if not wrote:
        rebuilt: list[str] = []
        inserted = False
        for line in out:
            rebuilt.append(line)
            if not inserted and line.lstrip().startswith("model:"):
                rebuilt.append(f"  base_url: {base_url}\n")
                inserted = True
        if not inserted:
            rebuilt.insert(0, f"model:\n  base_url: {base_url}\n")
        out = rebuilt
    try:
        config_path.write_text("".join(out), encoding="utf-8")
    except OSError as exc:
        return False, f"write failed: {exc}"
    return True, ""


def _proxy_fallback_chain(profile: str, billing_provider: str) -> None:
    """Runtime fallbacks use provider=custom so Hermes keeps the proxy + lease."""
    if not _is_runtime_profile_slug(profile):
        return
    block = _read_model_block(profile)
    chain = block.get("fallback_chain") or []
    billing = str(billing_provider or "openrouter").strip().lower()
    proxied: list[dict[str, str]] = []
    changed = False
    for entry in chain:
        prov = str(entry.get("provider", "")).strip().lower()
        model = str(entry.get("model", "")).strip()
        if not prov or not model:
            continue
        if prov == billing and prov != "custom":
            changed = True
            proxied.append({"provider": "custom", "model": model})
        else:
            proxied.append({"provider": prov, "model": model})
    if not proxied:
        changed = True
        proxied = [
            {"provider": "custom", "model": str(entry.get("model", "")).strip()}
            for entry in HERMES_DEFAULT_FALLBACK_CHAIN
            if str(entry.get("model", "")).strip()
        ]
    if changed:
        _write_fallback_chain(profile, proxied)


def _coalesce_profile_model_yaml(profile: str) -> None:
    """Merge duplicate top-level `model:` blocks left by incremental config writers."""
    config_path = _profile_gateway_config_path(profile)
    if not config_path or not config_path.is_file():
        return
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return
    model_headers = sum(
        1 for line in lines if line.lstrip().startswith("model:") and not line.startswith((" ", "\t"))
    )
    needs_coalesce = model_headers > 1
    if not needs_coalesce:
        in_model = False
        for line in lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if indent == 0 and stripped.startswith("model:"):
                in_model = True
                continue
            if indent == 0 and stripped:
                in_model = False
            if in_model and indent == 2 and stripped.startswith("- "):
                needs_coalesce = True
                break
    if not needs_coalesce:
        return
    block = _read_model_block(profile)
    api_key_line = ""
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("api_key:"):
            api_key_line = line if line.endswith("\n") else f"{line}\n"
    out: list[str] = []
    skipping_model = False
    skipping_fallback = False
    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if indent == 0 and stripped.startswith("model:"):
            skipping_model = True
            skipping_fallback = False
            continue
        if indent == 0 and stripped.startswith("fallback_providers:"):
            skipping_fallback = True
            skipping_model = False
            continue
        if skipping_model:
            if indent == 0 and stripped:
                if stripped.startswith("- "):
                    continue
                if not stripped.startswith("fallback_providers:"):
                    skipping_model = False
                else:
                    continue
            else:
                continue
        if skipping_fallback:
            if indent == 0 and stripped and not stripped.startswith("fallback_providers"):
                skipping_fallback = False
            else:
                continue
        out.append(line)
    merged: list[str] = ["model:\n"]
    default = str(block.get("default") or HERMES_DEFAULT_PRIMARY).strip()
    merged.append(f"  default: {default}\n")
    provider = str(block.get("provider") or "").strip()
    if provider:
        merged.append(f"  provider: {provider}\n")
    base_url = str(block.get("base_url") or "").strip()
    if base_url:
        merged.append(f"  base_url: {base_url}\n")
    if api_key_line:
        merged.append(api_key_line if api_key_line.startswith("  ") else f"  {api_key_line.lstrip()}")
    chain = block.get("fallback_chain") if isinstance(block.get("fallback_chain"), list) else []
    if chain:
        merged.append("fallback_providers:\n")
        for entry in chain:
            prov = str(entry.get("provider", "")).strip()
            model = str(entry.get("model", "")).strip()
            if prov and model:
                merged.append(f"  - provider: {prov}\n")
                merged.append(f"    model: {model}\n")
    if out and not out[0].startswith("model:"):
        insert_at = 0
        while insert_at < len(out) and (not out[insert_at].strip() or out[insert_at].lstrip().startswith("#")):
            insert_at += 1
        out[insert_at:insert_at] = merged
    else:
        out = merged + out
    try:
        config_path.write_text("".join(out), encoding="utf-8")
    except OSError:
        return


def _profile_llm_proxy_ready(profile: str, provider: str) -> bool:
    prof = safe_profile_slug(profile)
    block = _read_model_block(prof)
    llm_provider = str(provider or "openrouter").strip().lower()
    if str(block.get("base_url") or "").strip() != _llm_proxy_base_url(llm_provider):
        return False
    if not _is_runtime_profile_slug(prof):
        return True
    if str(block.get("provider") or "").strip().lower() != "custom":
        return False
    for entry in block.get("fallback_chain") or []:
        prov = str(entry.get("provider", "")).strip().lower()
        model = str(entry.get("model", "")).strip()
        if model and prov == llm_provider and prov != "custom":
            return False
    return True


def _ensure_profile_llm_proxy(profile: str, provider: str) -> None:
    """Point Hermes at the internal LLM proxy (create/lease paths only — skip when ready)."""
    llm_provider = str(provider or "openrouter").strip().lower()
    prof = safe_profile_slug(profile)
    if _oauth_llm_provider_spec(llm_provider):
        _normalize_profile_config_yaml(prof)
        _apply_mvp_model_for_provider(prof, llm_provider)
        return
    _normalize_profile_config_yaml(prof)
    if _profile_llm_proxy_ready(prof, llm_provider):
        _ensure_profile_proxy_headers(prof)
        if _is_runtime_profile_slug(prof):
            _proxy_fallback_chain(prof, llm_provider)
        return
    _coalesce_profile_model_yaml(prof)
    _set_profile_model_base_url(prof, _llm_proxy_base_url(llm_provider))
    _ensure_profile_proxy_headers(prof)
    if _is_runtime_profile_slug(prof):
        _set_profile_model_provider(prof, "custom")
        _proxy_fallback_chain(prof, llm_provider)


def _set_profile_model_api_key(profile: str, api_key: str) -> tuple[bool, str]:
    _normalize_profile_config_yaml(profile)
    try:
        config_path = _ensure_gateway_config_file(profile)
    except ValueError as exc:
        return False, str(exc)
    value = str(api_key or "").strip()
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"read failed: {exc}"
    lines = raw.splitlines(keepends=True)
    out: list[str] = []
    in_model = False
    wrote = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("model:"):
            if not in_model:
                in_model = True
                out.append(line)
            continue
        if in_model and stripped and not line.startswith((" ", "\t", "#")):
            if not wrote:
                out.append(f"  api_key: {_quote_env_value(value)}\n" if value else "  api_key: ''\n")
                wrote = True
            in_model = False
        if in_model and stripped.startswith("api_key:"):
            out.append(
                f"  api_key: {_quote_env_value(value)}\n" if value else "  api_key: ''\n"
            )
            wrote = True
            continue
        out.append(line)
    if not wrote:
        rebuilt: list[str] = []
        inserted = False
        for line in out:
            rebuilt.append(line)
            if not inserted and line.lstrip().startswith("model:"):
                rebuilt.append(
                    f"  api_key: {_quote_env_value(value)}\n" if value else "  api_key: ''\n"
                )
                inserted = True
        if not inserted:
            rebuilt.insert(0, f"model:\n  api_key: {_quote_env_value(value)}\n" if value else "model:\n  api_key: ''\n")
        out = rebuilt
    try:
        config_path.write_text("".join(out), encoding="utf-8")
    except OSError as exc:
        return False, f"write failed: {exc}"
    return True, ""


def _clear_profile_model_api_key(profile: str) -> None:
    _set_profile_model_api_key(profile, "")


def _profile_lease_env_var(profile: str, provider: str) -> str:
    prov, _model = _read_model_from_config(profile)
    if str(prov or "").strip().lower() == "custom":
        return "OPENAI_API_KEY"
    return _provider_env_var(provider)


def _read_profile_lease_token(profile: str, env_var: str) -> str:
    return str(_read_env_map(_profile_dir(profile) / ".env").get(env_var) or "").strip()


def _lease_reusable_for_turn(
    token: str,
    *,
    user_id: str,
    workspace_id: str,
    provider: str,
    binding_id: str,
) -> bool:
    lease = turn_credentials.validate_lease(token)
    if not lease:
        return False
    if str(lease.get("payer_user_id") or "") != str(user_id or "").strip():
        return False
    if str(lease.get("workspace_id") or "") != str(workspace_id or "").strip():
        return False
    if str(lease.get("provider") or "").strip().lower() != str(provider or "").strip().lower():
        return False
    lease_binding = str(lease.get("credential_binding_id") or "").strip()
    want_binding = str(binding_id or "").strip()
    if want_binding and lease_binding and lease_binding != want_binding:
        return False
    return True


def _read_config_model_api_key(profile: str) -> str:
    return str(_read_model_block(profile).get("api_key") or "").strip()


def _restart_runtime_profile_gateway(profile: str) -> None:
    """Hermes api_server caches config.yaml — reload after lease rotation."""
    prof = resolve_hermes_profile(profile)
    if not _is_runtime_profile_slug(prof) or prof == _primary_profile():
        return
    with _gateway_lifecycle_lock:
        try:
            profile_gateway_lifecycle(prof, "stop", bootstrap_providers=False)
        except ValueError:
            pass
        profile_gateway_lifecycle(prof, "start", bootstrap_providers=False)


def _sync_profile_model_api_key(profile: str, api_key: str) -> None:
    value = str(api_key or "").strip()
    if not value:
        _clear_profile_model_api_key(profile)
        _restart_runtime_profile_gateway(profile)
        return
    if _read_config_model_api_key(profile) == value:
        return
    ok, err = _set_profile_model_api_key(profile, value)
    if not ok:
        raise ValueError(err or "profile model api_key write failed")
    _restart_runtime_profile_gateway(profile)


def _apply_turn_credential_lease(
    profile: str,
    user_id: str,
    workspace_id: str,
    provider: str,
    run_id: str,
) -> str:
    """Issue per-run lease token into profile env; real secret stays in API vault."""
    provider = str(provider or "openrouter").strip().lower()
    prof = resolve_hermes_profile(profile)
    if _is_runtime_profile_slug(prof):
        resolved = _require_runtime_owner_provider(user_id, workspace_id, provider)
    else:
        resolved = _require_user_provider(user_id, workspace_id, provider)
    oauth_spec = _oauth_llm_provider_spec(provider)
    if oauth_spec and str(resolved.get("credential_type") or "") == "oauth":
        _sync_oauth_llm_to_profile(prof, user_id, provider)
        current_model = str(_read_model_from_config(prof)[1] or "").strip()
        if not _resolve_billing_provider_for_model(current_model, {provider}):
            current_model = str(
                (PROVIDER_MVP_MODELS.get(provider) or {}).get("primary") or current_model
            ).strip()
        _apply_model_for_billing_provider(prof, provider, current_model, user_id)
        return ""
    binding_id = str(
        resolved.get("credential_binding_id") or resolved.get("credential_id") or ""
    ).strip()
    vault_id = credential_vault.parse_vault_ref(str(resolved.get("credential_ref") or ""))
    if vault_id:
        binding_id = vault_id
    if not binding_id and _credential_secret(resolved, user_id):
        binding_id = str(uuid.uuid4())
        credential_vault.store_secret(
            binding_id,
            _credential_secret(resolved, user_id),
            env_var=str(resolved.get("env_var") or "") or _provider_env_var(provider),
            provider=provider,
            scope=str(resolved.get("scope") or "user"),
            user_id=user_id,
            workspace_id=workspace_id,
        )
    env_var = _profile_lease_env_var(prof, provider)
    config_lease = _read_config_model_api_key(prof)
    if config_lease and not turn_credentials.validate_lease(config_lease):
        _clear_profile_model_api_key(prof)
    existing_token = _read_profile_lease_token(prof, env_var)
    if existing_token and not turn_credentials.validate_lease(existing_token):
        _strip_profile_llm_env(prof, include_leases=True)
        _clear_profile_model_api_key(prof)
        existing_token = ""
    if _lease_reusable_for_turn(
        existing_token,
        user_id=user_id,
        workspace_id=workspace_id,
        provider=provider,
        binding_id=binding_id,
    ):
        # ponytail: hot path — skip yaml/env rewrite when lease still valid
        if _is_runtime_profile_slug(prof) and existing_token:
            if _read_config_model_api_key(prof) != existing_token:
                _sync_profile_model_api_key(prof, existing_token)
        return existing_token

    token = turn_credentials.issue_lease(
        run_id,
        user_id,
        workspace_id,
        provider,
        prof,
        binding_id or None,
    )
    if token != existing_token:
        _upsert_env_secret(_profile_dir(prof) / ".env", env_var, token)
    if _is_runtime_profile_slug(prof):
        _ensure_profile_llm_proxy(prof, provider)
        _sync_profile_model_api_key(prof, token)
    return token


def _action_proxy_base_url(provider_id: str) -> str:
    base = str(WORKFRAME_LLM_PROXY_INTERNAL or "http://workframe-api:8080").rstrip("/")
    return f"{base}/internal/action/{str(provider_id or '').strip().lower()}"


def _action_proxy_env_var(provider_id: str) -> str:
    return {
        "github": "GITHUB_API_URL",
        "vercel": "VERCEL_API_URL",
        "netlify": "NETLIFY_API_URL",
    }.get(str(provider_id or "").strip().lower(), "")


def _apply_action_credential_lease(
    profile: str,
    user_id: str,
    workspace_id: str,
    provider_id: str,
    run_id: str,
) -> str | None:
    """Lease token for user-only dev tools; upstream secret stays in API vault."""
    provider_id = str(provider_id or "").strip().lower()
    user = str(user_id or "").strip()
    run_id = str(run_id or "").strip()
    if not user or not provider_id or not run_id:
        return None
    prof = resolve_hermes_profile(profile)
    resolved = _resolve_credential(user, workspace_id, provider_id, user_only=True)
    if not resolved:
        return None
    if not _credential_secret(resolved, user):
        return None
    binding_id = str(
        resolved.get("credential_binding_id") or resolved.get("credential_id") or ""
    ).strip()
    if not binding_id:
        binding_id = str(uuid.uuid4())
        credential_vault.store_secret(
            binding_id,
            _credential_secret(resolved, user),
            env_var=str(resolved.get("env_var") or "") or _provider_env_var(provider_id),
            provider=provider_id,
            scope="user",
            user_id=user,
            workspace_id=workspace_id,
        )
    token = turn_credentials.issue_lease(
        run_id,
        user,
        workspace_id,
        provider_id,
        prof,
        binding_id or None,
    )
    env_var = str(resolved.get("env_var") or "") or _provider_env_var(provider_id)
    env_path = _profile_dir(prof) / ".env"
    _upsert_env_secret(env_path, env_var, token)
    proxy_env = _action_proxy_env_var(provider_id)
    if proxy_env:
        _upsert_env_secret(env_path, proxy_env, _action_proxy_base_url(provider_id))
    return token


def _revoke_turn_credential_lease(run_id: str, profile: str) -> None:
    """Revoke lease in DB; clear stale bearer from runtime profile config/gateway."""
    run_id = str(run_id or "").strip()
    if not run_id:
        return
    turn_credentials.revoke_lease(run_id)
    for provider_id, _env_var in _user_action_env_specs():
        turn_credentials.revoke_lease(f"{run_id}::{provider_id}")
    prof = resolve_hermes_profile(profile)
    if not _is_runtime_profile_slug(prof):
        return
    config_key = _read_config_model_api_key(prof)
    if config_key.startswith(turn_credentials.LEASE_PREFIX):
        _clear_profile_model_api_key(prof)
        _restart_runtime_profile_gateway(prof)


def _require_user_provider(user_id: str, workspace_id: str, provider: str) -> dict[str, Any]:
    """LLM billing uses the signed-in user's key only — same rule for chat and runtime agents."""
    return _require_runtime_owner_provider(user_id, workspace_id, provider)


def _require_runtime_owner_provider(user_id: str, workspace_id: str, provider: str) -> dict[str, Any]:
    provider = str(provider or "openrouter").strip().lower()
    oauth_spec = _oauth_llm_provider_spec(provider)
    if oauth_spec and _hermes_oauth_tokens_present(user_id, _hermes_auth_id_for_spec(oauth_spec)):
        hermes_auth_id = _hermes_auth_id_for_spec(oauth_spec)
        return {
            "credential_binding_id": None,
            "credential_id": None,
            "credential_ref": f"oauth:{hermes_auth_id}",
            "scope": "user",
            "provider": provider,
            "credential_type": "oauth",
            "label": hermes_auth_id,
            "env_var": "",
            "user_id": user_id,
            "workspace_id": None,
            "agent_profile_id": None,
            "created_by": user_id,
            "created_at": None,
            "updated_at": None,
            "expires_at": None,
        }
    resolved = _resolve_credential(user_id, workspace_id, provider, user_only=True)
    if resolved and _credential_secret(resolved, user_id):
        return resolved
    if _workspace_credential_mode(None, workspace_id) != "workspace":
        raise ValueError(
            "no_llm_provider_for_user: Connect an LLM provider under Profile → Connected accts before chatting with agents."
        )
    resolved = _resolve_credential(user_id, workspace_id, provider, user_only=False)
    if resolved and _credential_secret(resolved, user_id):
        return resolved
    raise ValueError(
        "no_llm_provider_for_user: Connect an LLM provider under Profile → Connected accts before chatting with agents."
    )


def _strip_profile_llm_env(profile: str, *, include_leases: bool = False) -> bool:
    """Remove shared-stack LLM keys from specialist profile .env."""
    try:
        prof = resolve_hermes_profile(profile)
    except ValueError:
        return False
    if prof == _primary_profile() and not _is_runtime_profile_slug(prof):
        return False
    path = _profile_dir(prof) / ".env"
    if not path.is_file():
        return False
    drop = set(_llm_provider_env_vars())
    kept: list[str] = []
    changed = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.partition("=")[0].strip()
            _val = line.partition("=")[2].strip().strip('"').strip("'")
            if include_leases and _val.startswith(turn_credentials.LEASE_PREFIX):
                changed = True
                continue
            if key in drop:
                # ponytail: keep active per-run lease tokens unless explicitly revoking
                if not include_leases and _val.startswith(turn_credentials.LEASE_PREFIX):
                    kept.append(line)
                    continue
                changed = True
                continue
        kept.append(line)
    if changed:
        path.write_text("\n".join(kept).rstrip() + ("\n" if kept else ""), encoding="utf-8")
    return changed


def _overlay_turn_provider_env(
    profile: str,
    user_id: str,
    workspace_id: str,
    provider: str,
    run_id: str = "",
) -> str:
    """Per-run lease into profile env; upstream key resolved only inside workframe-api."""
    run_id = str(run_id or "").strip() or str(uuid.uuid4())
    prof = resolve_hermes_profile(profile)
    is_runtime = _is_runtime_profile_slug(prof)
    config_before = _read_config_model_api_key(prof) if is_runtime else ""
    token = _apply_turn_credential_lease(profile, user_id, workspace_id, provider, run_id)
    if is_runtime and _read_config_model_api_key(prof) != config_before:
        if not _wait_profile_api_healthy(prof, attempts=20, delay=0.5):
            raise ValueError("profile api unavailable after credential lease sync")
    return token


def _try_overlay_turn_provider_env(
    profile: str,
    user_id: str,
    workspace_id: str,
    provider: str,
    run_id: str = "",
) -> bool:
    """Best-effort LLM lease; returns False when the user has no key yet."""
    try:
        _overlay_turn_provider_env(profile, user_id, workspace_id, provider, run_id)
        return True
    except ValueError as exc:
        if "no_llm_provider_for_user" in str(exc):
            return False
        raise


def _sync_profile_provider_env(profile: str, user_id: str = "", workspace_id: str = "") -> bool:
    """Copy the user's own LLM secrets into a specialist profile .env (never stack keys)."""
    prof = resolve_validated_profile(profile)
    if prof == _primary_profile():
        return False
    user = str(user_id or "").strip()
    if not user:
        return False

    target = _profile_dir(prof) / ".env"
    original = _read_env_map(target)
    merged = dict(original)
    needed = {key for key in _llm_provider_env_vars() if not merged.get(key)}
    if not needed:
        return False

    for key, value in _read_env_map(_user_hermes_env_path(user)).items():
        if key in needed and value:
            merged[key] = value
            needed.discard(key)
    if merged == original:
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(f"{key}={merged[key]}" for key in sorted(merged)) + "\n", encoding="utf-8")
    return True


def _profile_api_port(profile: str) -> int:
    if profile == _primary_profile():
        return 8642
    # Stable per-profile range: 18610..18709
    base = 18610
    span = 100
    h = sum(ord(c) for c in profile) % span
    return base + h


def _configure_profile_api(profile: str) -> tuple[bool, str, int]:
    _normalize_profile_config_yaml(profile)
    prof = resolve_hermes_profile(profile)
    port = _profile_api_port(prof)
    cfg_path = _profile_gateway_config_path(prof)
    if cfg_path is None:
        return False, f"profile not found: {prof}", port
    try:
        import yaml

        cfg: dict[str, Any] = {}
        if cfg_path.is_file():
            loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
            cfg = loaded if isinstance(loaded, dict) else {}
        plats = cfg.setdefault("platforms", {})
        if not isinstance(plats, dict):
            plats = {}
            cfg["platforms"] = plats
        native = prof == _primary_profile()
        if not native:
            api_only = plats.get("api_server") if isinstance(plats.get("api_server"), dict) else {}
            plats = {"api_server": api_only}
            cfg["platforms"] = plats
            for name in ("discord", "telegram", "slack", "whatsapp", "webhook", "cron"):
                plats[name] = {"enabled": False}
        api = plats.setdefault("api_server", {})
        if not isinstance(api, dict):
            api = {}
            plats["api_server"] = api
        api["enabled"] = True
        extra = api.setdefault("extra", {})
        if not isinstance(extra, dict):
            extra = {}
            api["extra"] = extra
        extra["host"] = "0.0.0.0"
        extra["port"] = port
        if not str(extra.get("key") or "").strip():
            extra["key"] = "workframe-local-key"
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        return True, "ok", port
    except (OSError, ImportError) as exc:
        return False, str(exc), port


def _patch_profile_gateway_run_script(profile: str) -> tuple[bool, str]:
    if profile == _primary_profile():
        return True, "native profile unchanged"
    profile_home = f"/opt/data/profiles/{profile}"
    script = (
        "from pathlib import Path\n"
        f"p=Path('/run/service/gateway-{profile}/run')\n"
        "if not p.exists():\n"
        " print('missing run script')\n"
        " raise SystemExit(1)\n"
        "text=p.read_text(encoding='utf-8')\n"
        "needle='export HERMES_S6_SUPERVISED_CHILD=1\\n'\n"
        f"inject=('export HERMES_S6_SUPERVISED_CHILD=1\\n'"
        f"'export HERMES_HOME={profile_home}\\n'"
        f"'export HOME={profile_home}\\n'"
        f"'cd {profile_home}\\n'"
        "'if [ -z \"$WORKFRAME_PROXY_TOKEN\" ] && [ -f /run/workframe-proxy/token ]; then '\n"
        "'export WORKFRAME_PROXY_TOKEN=\"$(tr -d \\'\\r\\n\\' < /run/workframe-proxy/token)\"; fi\\n'"
        "'unset DISCORD_BOT_TOKEN DISCORD_ALLOWED_USERS DISCORD_HOME_CHANNEL\\n'"
        "'unset TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_USERS TELEGRAM_HOME_CHANNEL\\n'"
        "'unset SLACK_BOT_TOKEN SLACK_APP_TOKEN WHATSAPP_MODE\\n'"
        "'unset HERMES_DASHBOARD HERMES_DASHBOARD_HOST HERMES_DASHBOARD_PORT HERMES_DASHBOARD_INSECURE HERMES_DASHBOARD_TUI\\n')\n"
        "if inject not in text:\n"
        " text=text.replace(needle, inject)\n"
        " p.write_text(text, encoding='utf-8')\n"
        "print('ok')\n"
    )
    code, out = _gateway_container_exec(
        ["/opt/hermes/.venv/bin/python", "-c", script],
    )
    return code == 0, out


def _disable_profile(prof: str) -> dict[str, Any]:
    port = _profile_api_port(prof)
    state = gateway_data(prof)
    if str(state.get("state") or "").lower() in {"running", "starting"}:
        code, out = _gateway_exec(prof, ["gateway", "stop"])
        if code != 0:
            raise ValueError(f"gateway stop failed: {out}")
    script = (
        "import yaml\n"
        "from pathlib import Path\n"
        f"d=Path('/opt/data/profiles/{prof}')\n"
        "p=d/'config.yaml'\n"
        "cfg=yaml.safe_load(p.read_text(encoding='utf-8')) if p.exists() else {}\n"
        "plats=cfg.setdefault('platforms',{})\n"
        "for name, value in list(plats.items()):\n"
        " if isinstance(value, dict):\n"
        "  value['enabled']=False\n"
        " else:\n"
        "  plats[name]={'enabled': False}\n"
        "cfg['platforms']=plats\n"
        "p.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding='utf-8')\n"
        f"Path('/opt/data/profiles/{prof}/.disabled').write_text('disabled by workframe-api\n', encoding='utf-8')\n"
        "print('ok')\n"
    )
    code, out = _gateway_container_exec(
        ["/opt/hermes/.venv/bin/python", "-c", script],
    )
    if code != 0:
        raise ValueError(f"disable profile config failed: {out}")
    return {"ok": True, "profile": prof, "action": "disable", "state": "disabled", "api_port": port, "output": out.strip()}


def profile_gateway_lifecycle(profile: str, action: str, *, bootstrap_providers: bool = True) -> dict[str, Any]:
    prof = resolve_hermes_profile(profile)
    if action in {"start", "stop", "disable"}:
        _invalidate_gateway_registered_cache(prof)
    if action not in {"start", "stop", "status", "disable"}:
        raise ValueError("invalid action")
    port = _profile_api_port(prof)
    if SECURE_MODE and prof != _primary_profile() and action in {"start", "stop", "disable"}:
        if action == "start":
            _normalize_profile_config_yaml(prof)
        return _supervisor_profile_lifecycle(prof, action)
    if prof == _primary_profile():
        if action == "disable":
            raise ValueError("cannot disable the native profile")
        if action == "status":
            state = gateway_data(prof)
            ok = bool(state.get("ok")) and str(state.get("state") or "").lower() == "running"
            return {
                "ok": ok,
                "profile": prof,
                "action": action,
                "api_port": port,
                "state": state.get("state") or "unknown",
                "details": state,
            }
        if action == "stop":
            raise ValueError("native gateway stop is not supported via profile api lifecycle")
        return {"ok": True, "profile": prof, "action": action, "api_port": port, "output": "native gateway already managed by compose"}
    if action == "disable":
        return _disable_profile(prof)
    with _gateway_lifecycle_lock:
        if action == "start":
            if bootstrap_providers:
                _bootstrap_profile_providers(prof)
            ok, out, port = _configure_profile_api(prof)
            if not ok:
                raise ValueError(f"profile api config failed: {out}")
            ok, out = _patch_profile_gateway_run_script(prof)
            if not ok:
                raise ValueError(f"profile api run patch failed: {out}")
            state = gateway_data(prof)
            if str(state.get("state") or "").lower() in {"running", "starting"} and not _profile_api_healthy(prof):
                code, out = _gateway_exec(prof, ["gateway", "stop"])
                if code != 0:
                    raise ValueError(f"gateway stop failed: {out}")
                time.sleep(1.0)
        if action == "status":
            state = gateway_data(prof)
            ok = bool(state.get("ok")) and str(state.get("state") or "").lower() == "running"
            return {
                "ok": ok,
                "profile": prof,
                "action": action,
                "api_port": port,
                "state": state.get("state") or "unknown",
                "details": state,
            }
        code, out = _gateway_exec(prof, ["gateway", action])
        if code != 0:
            raise ValueError(f"gateway {action} failed: {out}")
        if action == "start" and not _wait_profile_api_healthy(prof):
            raise ValueError(f"profile api did not become healthy: {prof}")
    return {"ok": True, "profile": prof, "action": action, "api_port": port, "output": out.strip()}


def profile_create(
    name: str,
    model: str = "",
    description: str = "",
    clone_from: str = "",
    soul: str = "",
    display_name: str = "",
    role: str = "",
    tagline: str = "",
    avatar_url: str = "",
    avatar_id: str = "",
    *,
    user_id: str = "",
    workspace_id: str = "",
    bootstrap_dm: bool = True,
) -> dict[str, Any]:
    """Create a new Hermes profile via docker exec. Returns profile info."""
    # Validate name: lowercase, alphanumeric, hyphens
    import re as _re
    if not _re.match(r'^[a-z][a-z0-9-]{0,63}$', name):
        raise ValueError("profile name must be lowercase alphanumeric, start with a letter, max 64 chars")
    
    # Check if profile already exists — register in workspace and return idempotently.
    pdir = _profile_dir(name)
    if pdir.exists():
        registry_patch: dict[str, Any] = {}
        if display_name.strip():
            registry_patch["display_name"] = display_name.strip()
        if role.strip():
            registry_patch["role"] = role.strip()
        elif description.strip():
            registry_patch["role"] = description.strip()
        if tagline.strip():
            registry_patch["tagline"] = tagline.strip()
        if description.strip():
            registry_patch["description"] = description.strip()
        if registry_patch:
            _upsert_agent_registry_row(name, registry_patch)
        _register_profile_route(
            name,
            {
                "display_name": display_name.strip() or name,
                "role": role.strip() or description.strip(),
            },
        )
        prof = resolve_validated_profile(name)
        _ensure_workspace_agent_profile_row(
            prof,
            workspace_id=workspace_id,
            display_name=display_name.strip() or prof,
            role=role.strip() or description.strip(),
            tagline=tagline.strip(),
        )
        soul_text = str(soul or "").strip()
        if soul_text:
            _apply_profile_identity(name, user_soul=soul_text)
        results: dict[str, Any] = {
            "ok": True,
            "profile": prof,
            "already_exists": True,
            "steps": [{"step": "reuse_existing_profile", "ok": True}],
        }
        if bootstrap_dm and user_id and workspace_id:
            try:
                lane = bootstrap_agent_dm_lane(
                    user_id,
                    workspace_id,
                    prof,
                    model=model,
                    bind_session=True,
                    room_name=display_name.strip() or prof,
                    created_by=user_id,
                )
                results["bootstrap"] = lane
                results["room_id"] = lane.get("room_id")
                results["runtime_profile"] = lane.get("runtime")
                results["session_id"] = lane.get("session_id")
                if lane.get("room"):
                    results["room"] = lane["room"]
                results["steps"].extend(lane.get("steps") or [])
            except Exception as exc:
                results["steps"].append({"step": "bootstrap_dm_lane", "ok": False, "error": str(exc)})
        return results
    
    prof = safe_profile_slug(name)
    if not clone_from.strip():
        try:
            clone_slug = resolve_validated_profile(_primary_profile())
        except ValueError as exc:
            raise ValueError(f"native agent profile required to spawn children: {exc}") from exc
    else:
        clone_slug = resolve_validated_profile(clone_from)
    results: dict[str, Any] = {"profile": prof, "steps": []}
    
    # 1. Create profile via hermes CLI — clone native capabilities minus forbidden skills.
    cmd = ["profile", "create", "--clone-from", clone_slug]
    if description:
        cmd.extend(["--description", description])
    cmd.append(prof)

    try:
        code, out = _gateway_exec(_primary_profile(), cmd)
        results["steps"].append({"step": "hermes_profile_create", "ok": code == 0, "output": out.strip()})
        if code != 0:
            raise ValueError(f"hermes profile create failed: {out.strip()}")
    except Exception as exc:
        results["steps"].append({"step": "hermes_profile_create", "ok": False, "error": str(exc)})
        raise

    removed_skills = _strip_forbidden_child_skills(prof)
    results["steps"].append({"step": "strip_forbidden_skills", "ok": True, "removed": removed_skills})
    child_label = display_name.strip() or prof.replace("-", " ").title()
    child_role = role.strip() or description.strip() or f"{child_label} specialist for {PROJECT_NAME}."
    if _install_child_base_artifacts(prof, display_name=child_label, role=child_role):
        results["steps"].append({"step": "install_child_base", "ok": True})
    
    # 2. Start the gateway for this profile
    try:
        ok, out, port = _configure_profile_api(prof)
        results["steps"].append({"step": "configure_api", "ok": ok, "api_port": port, "output": out.strip()})
        if ok:
            ok2, out2 = _patch_profile_gateway_run_script(prof)
            results["steps"].append({"step": "patch_run_script", "ok": ok2, "output": out2.strip()})
    except Exception as exc:
        results["steps"].append({"step": "configure_api", "ok": False, "error": str(exc)})
    
    # 3–4. Template model/gateway only when not bootstrapping a per-user DM runtime (C1).
    if not bootstrap_dm:
        if model:
            try:
                code, out = _gateway_exec(prof, ["model", model])
                results["steps"].append({"step": "set_model", "ok": code == 0, "model": model, "output": out.strip()})
            except Exception as exc:
                results["steps"].append({"step": "set_model", "ok": False, "error": str(exc)})
        try:
            state = profile_gateway_lifecycle(prof, "start")
            results["steps"].append({"step": "gateway_start", "ok": True, "state": state})
        except Exception as exc:
            results["steps"].append({"step": "gateway_start", "ok": False, "error": str(exc)})

    registry_patch: dict[str, Any] = {}
    if display_name.strip():
        registry_patch["display_name"] = display_name.strip()
    if role.strip():
        registry_patch["role"] = role.strip()
    elif description.strip():
        registry_patch["role"] = description.strip()
    if tagline.strip():
        registry_patch["tagline"] = tagline.strip()
    if description.strip():
        registry_patch["description"] = description.strip()
    if registry_patch:
        _upsert_agent_registry_row(prof, registry_patch)
        results["registry"] = registry_patch

    try:
        avatar = _assign_agent_avatar(
            prof,
            display_name=display_name.strip() or child_label,
        )
        results["avatar"] = avatar
        results["steps"].append({"step": "assign_avatar", "ok": True, **avatar})
    except Exception as exc:
        results["steps"].append({"step": "assign_avatar", "ok": False, "error": str(exc)})

    explicit_avatar = _normalize_agent_avatar_patch(avatar_url, avatar_id)
    if explicit_avatar.get("avatar_url") or explicit_avatar.get("avatar_id"):
        _upsert_agent_registry_row(
            prof,
            {
                **explicit_avatar,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        results["avatar"] = explicit_avatar

    soul_text = str(soul or "").strip()
    if soul_text:
        _apply_profile_identity(prof, user_soul=soul_text)
        results["steps"].append({"step": "seed_user_soul", "ok": True})

    _register_profile_route(
        prof,
        {
            "display_name": display_name.strip() or prof,
            "role": role.strip() or description.strip() or description,
        },
    )
    results["steps"].append({"step": "register_route", "ok": True})

    _ensure_workspace_agent_profile_row(
        prof,
        workspace_id=workspace_id,
        display_name=display_name.strip() or prof,
        role=role.strip() or description.strip(),
        tagline=tagline.strip(),
    )

    if bootstrap_dm and user_id and workspace_id:
        try:
            lane = bootstrap_agent_dm_lane(
                user_id,
                workspace_id,
                prof,
                model=model,
                bind_session=True,
                room_name=display_name.strip() or prof,
                created_by=user_id,
            )
            results["bootstrap"] = lane
            results["room_id"] = lane.get("room_id")
            results["runtime_profile"] = lane.get("runtime")
            results["session_id"] = lane.get("session_id")
            if lane.get("room"):
                results["room"] = lane["room"]
            results["steps"].extend(lane.get("steps") or [])
        except Exception as exc:
            results["steps"].append({"step": "bootstrap_dm_lane", "ok": False, "error": str(exc)})

    results["ok"] = True
    return results


def profile_delete(profile: str) -> dict[str, Any]:
    """Delete a child profile: stop gateway, remove directory, clean registries."""
    prof = resolve_validated_profile(profile)
    if prof == _primary_profile():
        raise ValueError("cannot delete the native profile")

    results: dict[str, Any] = {"profile": prof, "steps": []}

    # 1. Stop the gateway for this profile
    try:
        code, out = _gateway_exec(prof, ["gateway", "stop"])
        results["steps"].append({"step": "gateway_stop", "ok": code == 0, "output": out.strip()})
    except Exception as exc:
        results["steps"].append({"step": "gateway_stop", "ok": False, "error": str(exc)})

    # 2. Kill any remaining process for this profile
    try:
        cmd = ["pkill", "-f", f"hermes.*-p {prof}.*gateway"]
        code, out = _docker_exec(GATEWAY_CONTAINER_NAME, cmd)
        results["steps"].append({"step": "kill_process", "ok": True, "output": out.strip()})
    except Exception:
        results["steps"].append({"step": "kill_process", "ok": True, "output": "no process found"})

    # 3. Remove the profile directory (bypasses Hermes security guard)
    profile_dir = _profile_dir(prof)
    try:
        if profile_dir.exists():
            shutil.rmtree(str(profile_dir))
            results["steps"].append({"step": "remove_directory", "ok": True, "path": str(profile_dir)})
        else:
            results["steps"].append({"step": "remove_directory", "ok": True, "output": "directory not found"})
    except Exception as exc:
        results["steps"].append({"step": "remove_directory", "ok": False, "error": str(exc)})

    # 4. Remove from agents.json
    agents_json = HERMES_DATA / "workframe" / "agents.json"
    try:
        if agents_json.exists():
            data = json.loads(agents_json.read_text(encoding="utf-8"))
            if prof in data.get("agents", {}):
                del data["agents"][prof]
                agents_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                results["steps"].append({"step": "clean_agents_json", "ok": True})
            else:
                results["steps"].append({"step": "clean_agents_json", "ok": True, "output": "not in agents.json"})
    except Exception as exc:
        results["steps"].append({"step": "clean_agents_json", "ok": False, "error": str(exc)})

    # 5. Remove from avatar-registry.json
    avatar_json = HERMES_DATA / "workframe" / "avatar-registry.json"
    try:
        if avatar_json.exists():
            data = json.loads(avatar_json.read_text(encoding="utf-8"))
            changed = False
            if prof in data.get("assignments", {}):
                del data["assignments"][prof]
                changed = True
            if changed:
                avatar_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            results["steps"].append({"step": "clean_avatar_registry", "ok": True})
    except Exception as exc:
        results["steps"].append({"step": "clean_avatar_registry", "ok": False, "error": str(exc)})

    # 6. Remove from routes.json
    routes_json = HERMES_DATA / "workframe" / "routes.json"
    try:
        if routes_json.exists():
            data = json.loads(routes_json.read_text(encoding="utf-8"))
            original_len = len(data.get("routes", []))
            data["routes"] = [r for r in data.get("routes", []) if r.get("profile") != prof]
            if len(data["routes"]) < original_len:
                routes_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                results["steps"].append({"step": "clean_routes", "ok": True})
            else:
                results["steps"].append({"step": "clean_routes", "ok": True, "output": "not in routes"})
    except Exception as exc:
        results["steps"].append({"step": "clean_routes", "ok": False, "error": str(exc)})

    results["ok"] = all(s.get("ok", False) for s in results["steps"])
    return results


def _profile_api_key(profile: str) -> str:
    return "workframe-local-key"


def _profile_turn_payload(profile: str, text: str, room_id: str = "") -> dict[str, Any]:
    message = text
    room_id = str(room_id or "").strip()
    if room_id:
        try:
            conn = _workframe_db()
            try:
                room = conn.execute(
                    """
                    SELECT room_type, agent_profile_id
                    FROM rooms WHERE id = ? AND deleted_at IS NULL
                    """,
                    (room_id,),
                ).fetchone()
                if room and _is_space_room(str(room["room_type"]), room["agent_profile_id"]):
                    transcript = _room_recent_transcript(conn, room_id)
                    message = (
                        "You are in a group chat. Reply only to the message that @mentioned you.\n\n"
                        f"Recent messages:\n{transcript}\n\n"
                        "Respond concisely."
                    )
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            pass
    payload: dict[str, Any] = {"message": message}
    soul = _profile_soul_text(profile)
    if soul:
        payload["instructions"] = soul
    return payload


def _profile_api_request(
    profile: str,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    port = _profile_api_port(profile)
    url = f"http://gateway:{port}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {_profile_api_key(profile)}",
        "Content-Type": "application/json",
    }
    last_error: Exception | None = None
    for attempt in range(4):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=1800) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return int(resp.status), (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                return int(exc.code), json.loads(raw)
            except Exception:  # noqa: BLE001
                return int(exc.code), raw
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt < 3 and _is_transient_profile_api_error(exc):
                time.sleep(0.35 * (attempt + 1))
                continue
            raise
    if last_error:
        raise last_error
    return 503, {"error": "profile api unavailable"}


def _is_transient_profile_api_error(exc: Exception) -> bool:
    reason = str(getattr(exc, "reason", exc) or exc).lower()
    return any(token in reason for token in ("connection refused", "timed out", "temporarily unavailable"))


def _profile_api_healthy(profile: str, timeout: float = 1.5) -> bool:
    try:
        prof = resolve_hermes_profile(profile)
    except ValueError:
        return False
    port = _profile_api_port(prof)
    key = _profile_api_key(prof)
    wait = max(1.0, float(timeout))
    url = f"http://gateway:{port}/v1/health"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=wait) as resp:
            return int(resp.status) < 300
    except Exception:  # noqa: BLE001
        return False


def _wait_profile_api_healthy(profile: str, attempts: int = 60, delay: float = 0.5) -> bool:
    try:
        prof = resolve_hermes_profile(profile)
    except ValueError:
        return False
    if _profile_api_healthy(prof):
        return True
    for _ in range(attempts):
        if _profile_api_healthy(prof):
            return True
        time.sleep(delay)
    return False


def _load_profile_auth_json(profile: str) -> dict[str, Any]:
    path = _profile_dir(profile) / "auth.json"
    fallback: dict[str, Any] = {"version": 1, "providers": {}, "credential_pool": {}}
    if not path.is_file():
        return dict(fallback)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(fallback)
    return raw if isinstance(raw, dict) else dict(fallback)


def _provider_pool_entry(provider: str, env_var: str, *, base_url: str = "") -> dict[str, Any]:
    base_urls = {
        "openrouter": "https://openrouter.ai/api/v1",
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com",
    }
    resolved_base = str(base_url or "").strip() or base_urls.get(provider.lower(), "")
    return {
        "id": secrets.token_hex(3),
        "label": env_var,
        "auth_type": "api_key",
        "priority": 0,
        "source": f"env:{env_var}",
        "last_status": "ok",
        "base_url": resolved_base,
        "request_count": 0,
    }


def _runtime_provider_pool_entry(provider: str, env_var: str) -> dict[str, Any]:
    """Credential pool row for u-* profiles — lease token lives in OPENAI_API_KEY."""
    lease_env = "OPENAI_API_KEY"
    return _provider_pool_entry(provider, lease_env, base_url=_llm_proxy_base_url(provider))


def _provider_pool_has_entries(auth: dict[str, Any], provider: str) -> bool:
    pool = auth.get("credential_pool")
    if not isinstance(pool, dict):
        return False
    provider_key = str(provider or "").strip().lower()
    for key in _hermes_oauth_auth_keys(provider_key) | {provider_key}:
        entries = pool.get(key)
        if isinstance(entries, list) and len(entries) > 0:
            return True
    spec = _catalog_provider_for_llm(provider_key)
    if spec:
        auth_id = str(spec.get("hermes_auth_id") or "").strip().lower()
        if auth_id:
            entries = pool.get(auth_id)
            if isinstance(entries, list) and len(entries) > 0:
                return True
    return False


def _connected_provider_names(user_id: str = "", workspace_id: str = "") -> set[str]:
    names: set[str] = set()
    user = str(user_id or "").strip()
    workspace = str(workspace_id or "").strip()
    if user:
        names.update(_user_provider_bindings(user).keys())
        names.update(
            str(spec["id"]).lower()
            for spec in PROVIDER_CONNECT_CATALOG
            if str(spec.get("env_var") or "") in _user_auth_env_keys(user)
        )
    if workspace:
        for provider in ("openrouter", "openai", "anthropic", "google"):
            if _resolve_credential("", workspace, provider):
                names.add(provider)
    if not user:
        primary = _primary_profile()
        if primary:
            primary_pool = _load_profile_auth_json(primary).get("credential_pool")
            if isinstance(primary_pool, dict):
                for pname, entries in primary_pool.items():
                    if isinstance(entries, list) and entries:
                        names.add(str(pname).lower())
        if not names:
            names.add("openrouter")
    return names


def _user_llm_providers_for_picker(user_id: str) -> set[str]:
    user = str(user_id or "").strip()
    if not user:
        return set()
    return {
        str(spec["id"]).lower()
        for spec in PROVIDER_CONNECT_CATALOG
        if str(spec.get("category") or "") == "llm" and _user_provider_connected(user, spec)
    }


def _user_has_llm_provider(user_id: str) -> bool:
    return bool(_user_llm_providers_for_picker(user_id))


def _workspace_has_llm_provider(workspace_id: str) -> bool:
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return False
    for spec in PROVIDER_CONNECT_CATALOG:
        if str(spec.get("category") or "") != "llm":
            continue
        provider_id = str(spec["id"])
        resolved = _resolve_credential("", workspace_id, provider_id)
        if not resolved:
            continue
        env_var = str(spec.get("env_var") or "")
        if env_var and _stack_profile_env().get(env_var):
            return True
    return False


def _user_can_use_llm(user_id: str, workspace_id: str = "", provider: str = "openrouter") -> bool:
    user = str(user_id or "").strip()
    if not user:
        return False
    spec = _catalog_provider_for_llm(provider)
    if spec and str(spec.get("connect_mode") or "") == "oauth":
        return _hermes_oauth_tokens_present(user, _hermes_auth_id_for_spec(spec))
    try:
        resolved = _require_user_provider(user, workspace_id, provider)
        return bool(_credential_secret(resolved, user))
    except ValueError:
        return False


def _overlay_chat_llm_env(
    hermes_prof: str,
    user_id: str,
    workspace_id: str,
    provider: str,
) -> bool:
    """Overlay turn credentials; True when this turn can bill the acting user's key."""
    user = str(user_id or "").strip()
    if not user:
        return False
    prov = _llm_billing_provider(hermes_prof, provider, user_id=user, workspace_id=workspace_id)
    if not _profile_llm_proxy_matches_billing(hermes_prof, prov):
        _ensure_profile_llm_proxy(hermes_prof, prov)
    slug = safe_profile_slug(hermes_prof)
    turn_run = str(uuid.uuid4())
    ready = _try_overlay_turn_provider_env(hermes_prof, user, workspace_id, prov, turn_run)
    if ready:
        _overlay_turn_user_env(hermes_prof, user, workspace_id, turn_run)
        return True
    if _is_runtime_profile_slug(slug):
        return False
    return _user_can_use_llm(user, workspace_id, prov)


def _resolve_models_profile(profile: str) -> str:
    """Template profile slug for model picker reads — never per-user runtime u-*."""
    raw = str(profile or "").strip()
    if not raw:
        return _primary_profile()
    slug = safe_profile_slug(raw)
    if _is_runtime_profile_slug(slug):
        return resolve_validated_profile(_runtime_template_slug(slug))
    return resolve_validated_profile(slug)


def _model_suggestion_row(
    model_id: str,
    *,
    provider_label: str = "OpenRouter",
    label: str = "",
    description: str = "",
) -> dict[str, str]:
    slug = model_id.rsplit("/", 1)[-1] if "/" in model_id else model_id
    return {
        "provider": provider_label,
        "model": model_id,
        "label": label or slug,
        "description": description or model_id,
    }


def _augment_model_suggestions(
    suggestions: list[dict[str, str]],
    block: dict[str, Any],
) -> list[dict[str, str]]:
    """Ensure active primary and fallback chain models appear in the picker."""
    seen = {str(row.get("model") or "") for row in suggestions}
    extra: list[dict[str, str]] = []
    primary = str(block.get("default") or "").strip()
    if primary and primary not in seen:
        bill = _billing_provider_id_from_hermes_config(str(block.get("provider") or "")) or str(
            block.get("provider") or "openrouter"
        )
        extra.append(
            _model_suggestion_row(
                primary,
                provider_label=_provider_display_label(bill),
                label="Current primary",
                description="Active model for this agent profile",
            ),
        )
        seen.add(primary)
    for entry in block.get("fallback_chain") or []:
        if not isinstance(entry, dict):
            continue
        model = str(entry.get("model") or "").strip()
        prov = str(entry.get("provider") or "openrouter").strip()
        if not model:
            continue
        full = model if "/" in model else f"{prov}/{model}"
        if full in seen:
            continue
        bill = _billing_provider_id_from_hermes_config(prov) or prov
        extra.append(
            _model_suggestion_row(
                full,
                provider_label=_provider_display_label(bill),
                label=f"Fallback · {model}",
                description="Configured in this profile's fallback chain",
            ),
        )
        seen.add(full)
    return extra + suggestions


_INTERNAL_LLM_PROXY_RE = re.compile(r"/internal/llm/([a-z0-9_-]+)/v1", re.I)


def _billing_provider_from_block(base_url: str, cfg_provider: str, hint: str) -> str:
    """Pure resolver: the billing provider is the proxy URL segment (the stored fact).

    Order: explicit hint > proxy URL segment > cfg_provider > "openrouter".
    The model-id prefix (e.g. ``google/`` in ``google/gemini-2.5-flash``) is an
    OpenRouter vendor namespace, NOT a billing provider, so it is never used here.
    ponytail: removing model-prefix inference is the root-cause fix for the
    "provider not recognized" bug where an OpenRouter-only user was billed to google.
    """
    h = str(hint or "").strip().lower()
    if h and h not in {"custom", "auto"}:
        return h
    m = _INTERNAL_LLM_PROXY_RE.search(str(base_url or ""))
    if m:
        return m.group(1).lower()
    cfg = str(cfg_provider or "").strip().lower()
    if cfg and cfg not in {"custom", "auto"}:
        return cfg
    return "openrouter"


def _llm_billing_provider(
    profile: str,
    provider_hint: str = "",
    *,
    user_id: str = "",
    workspace_id: str = "",
) -> str:
    """Map Hermes routing provider (often custom for proxy) to vault/billing provider id."""
    prof = resolve_hermes_profile(profile)
    block = _read_model_block(prof)
    cfg_provider = str(block.get("provider") or "").strip().lower()
    billing_cfg = _billing_provider_id_from_hermes_config(cfg_provider)
    user = str(user_id or "").strip()
    ws = str(workspace_id or "").strip()
    if billing_cfg and user and _user_can_use_llm(user, ws, billing_cfg):
        return billing_cfg
    candidate = _billing_provider_from_block(
        str(block.get("base_url") or ""), cfg_provider, provider_hint,
    )
    if user and not _user_can_use_llm(user, ws, candidate):
        connected = sorted(_user_llm_providers_for_picker(user))
        if connected:
            return connected[0]
    return candidate or "openrouter"


def _profile_llm_proxy_matches_billing(profile: str, billing_provider: str) -> bool:
    prof = resolve_hermes_profile(profile)
    base = str(_read_model_block(prof).get("base_url") or "").strip()
    return bool(base) and base == _llm_proxy_base_url(billing_provider)


def _reconcile_profile_llm_for_user(
    profile: str,
    user_id: str,
    workspace_id: str,
    *,
    prefer_provider: str = "",
) -> bool:
    """Point proxy + MVP model at a provider the acting user can bill."""
    user = str(user_id or "").strip()
    if not user:
        return False
    prof = resolve_hermes_profile(profile)
    billing = _llm_billing_provider(prof, user_id=user, workspace_id=workspace_id)
    prefer = str(prefer_provider or "").strip().lower()
    if prefer and _user_can_use_llm(user, workspace_id, prefer):
        billing = prefer
    elif not _user_can_use_llm(user, workspace_id, billing):
        connected = sorted(_user_llm_providers_for_picker(user))
        if not connected:
            return False
        billing = connected[0]
    if _oauth_llm_provider_spec(billing) and _user_can_use_llm(user, workspace_id, billing):
        current = str(_read_model_from_config(prof)[1] or "").strip()
        if not _resolve_billing_provider_for_model(current, {billing}):
            current = str((PROVIDER_MVP_MODELS.get(billing) or {}).get("primary") or "")
        _apply_model_for_billing_provider(prof, billing, current, user_id=user)
        return True
    if _user_can_use_llm(user, workspace_id, billing) and _profile_llm_proxy_matches_billing(prof, billing):
        return False
    changed = _apply_mvp_model_for_provider(prof, billing)
    block = _read_model_block(prof)
    if _is_runtime_profile_slug(prof) or str(block.get("provider") or "").strip().lower() == "custom":
        _ensure_profile_llm_proxy(prof, billing)
    return changed


def _bootstrap_profile_providers(profile: str, user_id: str = "", workspace_id: str = "") -> bool:
    """Seed profile auth + MVP model config from user, workspace, or primary stack."""
    prof = resolve_hermes_profile(profile)
    if prof == _primary_profile():
        return False

    changed = False
    if _is_runtime_profile_slug(prof):
        changed = _prepare_runtime_profile_credentials(prof, user_id, workspace_id) or False
    else:
        changed = _strip_profile_llm_env(prof) or False
        changed = _strip_profile_action_env(prof) or changed
        changed = _sync_profile_provider_env(prof, user_id, workspace_id) or changed

    provider, model_name = _read_model_from_config(prof)
    llm_provider = _llm_billing_provider(prof, provider or "")
    if not str(model_name or "").strip():
        changed = _apply_mvp_model_for_provider(prof, llm_provider) or changed
        if _is_runtime_profile_slug(prof):
            _ensure_profile_llm_proxy(prof, llm_provider)
    elif not str(_read_model_from_config(prof)[0] or "").strip():
        ok_provider, _ = _set_profile_model_provider(prof, llm_provider)
        changed = ok_provider or changed
        if _is_runtime_profile_slug(prof):
            _ensure_profile_llm_proxy(prof, llm_provider)

    auth_path = _profile_dir(prof) / "auth.json"
    auth = _load_profile_auth_json(prof)
    if _provider_pool_has_entries(auth, llm_provider):
        return changed

    user = str(user_id or "").strip()
    llm_spec = _catalog_provider_for_llm(llm_provider)
    if (
        llm_spec
        and str(llm_spec.get("connect_mode") or "") == "oauth"
        and user
        and _sync_oauth_llm_to_profile(prof, user, llm_provider)
    ):
        return True

    if _is_runtime_profile_slug(prof):
        if not user or not _user_can_use_llm(user, workspace_id, llm_provider):
            return changed
        env_var = _provider_env_var(llm_provider)
        template = _runtime_provider_pool_entry(llm_provider, env_var)
    else:
        resolved = _resolve_credential(
            user,
            str(workspace_id or "").strip(),
            llm_provider,
            user_only=_provider_user_only(llm_provider),
        )
        if not resolved:
            return changed

        ref = str(resolved.get("credential_ref") or "")
        env_var = str(resolved.get("env_var") or "") or (ref[4:] if ref.startswith("env:") else _provider_env_var(llm_provider))
        template = _provider_pool_entry(llm_provider, env_var)

    pool = auth.setdefault("credential_pool", {})
    if not isinstance(pool, dict):
        pool = {}
        auth["credential_pool"] = pool
    pool[llm_provider] = [template]
    auth["version"] = 1
    auth["providers"] = auth.get("providers") if isinstance(auth.get("providers"), dict) else {}
    auth["updated_at"] = _utc_now()
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(json.dumps(auth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _publish_profile_gateway_secrets(prof)
    return True


def ensure_profile_api(
    profile: str,
    user_id: str = "",
    workspace_id: str = "",
    *,
    bootstrap_providers: bool = True,
) -> dict[str, Any]:
    """Start profile gateway if down. ponytail: bind/chat must not mutate yaml or bootstrap creds."""
    prof = resolve_hermes_profile(profile)
    port = _profile_api_port(prof)
    if _profile_api_healthy(prof):
        return {"ok": True, "profile": prof, "api_port": port, "started": False}
    if prof == _primary_profile():
        ok, out, _port = _configure_profile_api(prof)
        if not ok:
            raise ValueError(f"profile api config failed: {out}")
        _restart_stack_gateway()
        if not _wait_profile_api_healthy(prof):
            raise ValueError(f"profile api did not become healthy: {prof}")
        return {"ok": True, "profile": prof, "api_port": port, "started": True}
    if bootstrap_providers and user_id:
        _bootstrap_profile_providers(prof, user_id, workspace_id)
    with _gateway_lifecycle_lock:
        if _profile_api_healthy(prof):
            return {"ok": True, "profile": prof, "api_port": port, "started": False}
        result = profile_gateway_lifecycle(prof, "start", bootstrap_providers=bootstrap_providers)
        if not _wait_profile_api_healthy(prof):
            raise ValueError(f"profile api did not become healthy: {prof}")
        return {
            **result,
            "ok": True,
            "profile": prof,
            "api_port": port,
            "started": True,
        }


def _binding_version(raw: Any) -> int:
    try:
        value = int(raw or 0)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def _binding_row_for(
    profile: str,
    source_id: str,
    client_id: str,
    binding_version: int = 0,
) -> dict[str, Any] | None:
    prof = resolve_hermes_profile(profile)
    registry = _load_lane_registry()
    bucket = _registry_profile_bucket(registry, prof)
    bindings = bucket.get("bindings") if isinstance(bucket.get("bindings"), dict) else {}
    binding_key = _source_binding_key(source_id, client_id)
    row = bindings.get(binding_key) if isinstance(bindings, dict) else None
    if not isinstance(row, dict):
        return None
    if binding_version and _binding_version(row.get("binding_version")) != binding_version:
        return None
    session_id = str(row.get("session_id") or "").strip()
    if session_id and not _session_exists(prof, session_id):
        return None
    return row


def _binding_session_for(profile: str, source_id: str, client_id: str, binding_version: int = 0) -> str:
    row = _binding_row_for(profile, source_id, client_id, binding_version)
    return str((row or {}).get("session_id") or "").strip()


def profile_chat_session(profile: str, payload: dict[str, Any], user_id: str = "") -> dict[str, Any]:
    source_id = str(payload.get("source_id") or "ui").strip() or "ui"
    client_id = str(payload.get("client_id") or "default").strip() or "default"
    binding_version = _binding_version(payload.get("binding_version"))
    force_new = bool(payload.get("new_session") or False)
    room_id = str(payload.get("room_id") or "").strip()
    user_id = str(user_id or payload.get("user_id") or "").strip()
    workspace_id = str(payload.get("workspace_id") or "").strip()
    if room_id and not workspace_id:
        try:
            conn_ws = _workframe_db()
            row = conn_ws.execute(
                "SELECT workspace_id FROM rooms WHERE id = ? AND deleted_at IS NULL",
                (room_id,),
            ).fetchone()
            conn_ws.close()
            if row:
                workspace_id = str(row["workspace_id"])
        except Exception:  # noqa: BLE001
            pass

    hermes_prof = ""
    template_prof = ""
    agent_db_id = ""

    if room_id:
        if not user_id:
            raise ValueError("room_id requires authenticated user")
        conn = _workframe_db()
        try:
            room = conn.execute(
                "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
                (room_id,),
            ).fetchone()
            if not room:
                raise ValueError("room_not_found")
            if not _user_can_access_room(conn, room_id, user_id):
                raise ValueError("room_access_denied")
            if not workspace_id:
                workspace_id = str(room["workspace_id"])
            if _is_space_room(str(room["room_type"]), room["agent_profile_id"]):
                raw_prof = str(profile or _primary_profile()).strip()
                if _is_runtime_profile_slug(raw_prof):
                    template_prof = resolve_validated_profile(_runtime_template_slug(raw_prof))
                    hermes_prof = raw_prof
                else:
                    template_prof = resolve_validated_profile(raw_prof)
                    hermes_prof = _resolve_chat_hermes_profile(
                        template_prof, user_id, room_id, workspace_id,
                    )
                agent_row = _lookup_agent_profile(conn, workspace_id, template_prof)
                if not agent_row:
                    raise ValueError("agent_profile_not_found")
                agent_db_id = str(agent_row["id"])
            else:
                _room, template_prof, hermes_prof, agent_db_id, workspace_id = _resolve_room_agent_chat(
                    conn, user_id, room_id,
                )
        finally:
            conn.close()
    else:
        hermes_prof, template_prof = _resolve_bind_profile_arg(
            profile, user_id, "", workspace_id,
        )
    payer = user_id
    if payer:
        _reconcile_profile_llm_for_user(hermes_prof, payer, workspace_id)
    llm_provider = _llm_billing_provider(hermes_prof, user_id=payer, workspace_id=workspace_id)
    lifecycle = ensure_profile_api(hermes_prof, user_id, workspace_id)
    llm_ready = _user_can_use_llm(payer, workspace_id, llm_provider) if payer else False
    session_extra = {"llm_ready": llm_ready, "has_llm_provider": llm_ready}

    if room_id:
        conn = _workframe_db()
        try:
            existing_row = (
                None
                if force_new
                else _get_active_room_session(conn, room_id, agent_db_id)
            )
            if existing_row:
                sid = str(existing_row["session_id"]).strip()
                if not sid or not _session_exists(hermes_prof, sid):
                    existing_row = None
            if existing_row:
                sid = str(existing_row["session_id"]).strip()
                gateway_sid = str(existing_row["gateway_session_id"] or f"api:{hermes_prof}:{sid}").strip()
                session_title = str(existing_row["title"] or _default_session_title(template_prof))
                _ensure_hermes_session_title(hermes_prof, sid, session_title)
                _upsert_room_session(
                    conn,
                    room_id=room_id,
                    agent_profile_id=agent_db_id,
                    session_id=sid,
                    gateway_session_id=gateway_sid,
                    created_by=user_id,
                    title=session_title,
                )
                conn.commit()
                _sync_lane_binding(
                    hermes_prof,
                    source_id,
                    client_id,
                    binding_version,
                    sid,
                    gateway_sid,
                )
                return {
                    "ok": True,
                    "profile": hermes_prof,
                    "template_profile": template_prof,
                    "workspace_id": workspace_id,
                    "room_id": room_id,
                    "session_id": sid,
                    "title": _resolved_session_title(hermes_prof, sid, session_title),
                    "api_port": lifecycle["api_port"],
                    "created": False,
                    "resumed": str(existing_row["status"]) != "active",
                    **session_extra,
                }
            new_id = f"wf_room_{room_id[:8]}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            requested_title = str(payload.get("title") or "").strip() or _default_session_title(template_prof)
            status, data, session_title = _create_profile_session_via_api(hermes_prof, new_id, requested_title)
            if status >= 300:
                raise ValueError(f"create session failed: {data}")
            gateway_sid = f"api:{hermes_prof}:{new_id}"
            _upsert_room_session(
                conn,
                room_id=room_id,
                agent_profile_id=agent_db_id,
                session_id=new_id,
                gateway_session_id=gateway_sid,
                created_by=user_id,
                title=session_title or requested_title,
            )
            conn.commit()
        finally:
            conn.close()
        _sync_lane_binding(
            hermes_prof,
            source_id,
            client_id,
            binding_version,
            new_id,
            gateway_sid,
        )
        return {
            "ok": True,
            "profile": hermes_prof,
            "template_profile": template_prof,
            "workspace_id": workspace_id,
            "room_id": room_id,
            "session_id": new_id,
            "title": session_title,
            "api_port": lifecycle["api_port"],
            "created": True,
            **session_extra,
        }

    # ponytail: legacy client_id binding when room_id omitted (tests / old clients)
    existing = "" if force_new else _binding_session_for(hermes_prof, source_id, client_id, binding_version)
    if existing and _session_exists(hermes_prof, existing):
        return {
            "ok": True,
            "profile": hermes_prof,
            "session_id": existing,
            "title": _session_info(hermes_prof, existing).get("title") or _default_session_title(template_prof),
            "api_port": lifecycle["api_port"],
            "created": False,
            **session_extra,
        }
    new_id = f"wf_{source_id}_{client_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    requested_title = str(payload.get("title") or "").strip() or _default_session_title(template_prof)
    status, data, session_title = _create_profile_session_via_api(hermes_prof, new_id, requested_title)
    if status >= 300:
        raise ValueError(f"create session failed: {data}")
    chat_dispatch(
        {
            "profile": hermes_prof,
            "session_id": new_id,
            "gateway_session_id": f"api:{hermes_prof}:{new_id}",
            "source_id": source_id,
            "client_id": client_id,
            "binding_version": binding_version,
            "text": "",
        }
    )
    return {
        "ok": True,
        "profile": hermes_prof,
        "session_id": new_id,
        "title": session_title,
        "api_port": lifecycle["api_port"],
        "created": True,
        **session_extra,
    }


def room_chat_bind(room_id: str, payload: dict[str, Any], user_id: str = "") -> dict[str, Any]:
    """Room-scoped bind — identity from room.agent_profile_id, not the URL."""
    body = dict(payload or {})
    body["room_id"] = str(room_id or "").strip()
    return profile_chat_bind("", body, user_id)


def profile_chat_bind(profile: str, payload: dict[str, Any], user_id: str = "") -> dict[str, Any]:
    session = profile_chat_session(profile, payload, user_id)
    sid = str(session.get("session_id") or "").strip()
    hermes_prof = str(session.get("profile") or resolve_validated_profile(profile))
    template_prof = str(session.get("template_profile") or "").strip()
    if not template_prof:
        template_prof = (
            _runtime_template_slug(hermes_prof)
            if _is_runtime_profile_slug(hermes_prof)
            else resolve_validated_profile(profile)
        )
    workspace_id = str(session.get("workspace_id") or payload.get("workspace_id") or "").strip()
    history = chat_messages(hermes_prof, sid)
    # ponytail: cohort manifest is lazy — GET /api/me/cohort; bind must stay fast
    cohort: list[dict[str, Any]] = []
    display_name = (
        _runtime_display_label(user_id, template_prof, workspace_id)
        if user_id and _is_runtime_profile_slug(hermes_prof)
        else _profile_display_name(hermes_prof, workspace_id)
    )
    return {
        "ok": True,
        "profile": session.get("profile") or profile,
        "template_profile": template_prof,
        "agent_display_name": display_name,
        "cohort": cohort,
        "session_id": sid,
        "title": session.get("title") or "",
        "created": bool(session.get("created")),
        "api_port": session.get("api_port"),
        "llm_ready": bool(session.get("llm_ready")),
        "has_llm_provider": bool(session.get("has_llm_provider")),
        "messages": history.get("messages") or [],
        "session": history.get("session") or {},
    }


def _room_session_rows(conn: sqlite3.Connection, room_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT rs.*, ap.slug AS agent_slug, ap.display_name AS agent_display_name
        FROM room_sessions rs
        LEFT JOIN agent_profiles ap ON ap.id = rs.agent_profile_id
        WHERE rs.room_id = ? AND rs.deleted_at IS NULL
        ORDER BY rs.updated_at DESC, rs.created_at DESC
        """,
        (room_id,),
    ).fetchall()


def list_room_sessions(room_id: str, user_id: str) -> dict[str, Any]:
    room_id = str(room_id or "").strip()
    user_id = str(user_id or "").strip()
    if not room_id or not user_id:
        raise ValueError("room_id and user required")
    conn = _workframe_db()
    try:
        room = conn.execute(
            "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
            (room_id,),
        ).fetchone()
        if not room:
            raise ValueError("room_not_found")
        if not _user_can_access_room(conn, room_id, user_id):
            raise ValueError("room_access_denied")
        workspace_id = str(room["workspace_id"])
        rows = _room_session_rows(conn, room_id)
    finally:
        conn.close()

    sessions: list[dict[str, Any]] = []
    for row in rows:
        template_slug = str(row["agent_slug"] or "").strip()
        agent_db_id = str(row["agent_profile_id"] or "").strip()
        if not template_slug or not agent_db_id:
            continue
        sid = str(row["session_id"] or "").strip()
        hermes_prof = _resolve_chat_hermes_profile(template_slug, user_id, room_id, workspace_id)
        if not sid or not _session_exists(hermes_prof, sid):
            continue
        info = _session_info(hermes_prof, sid)
        sessions.append(
            {
                "id": str(row["id"]),
                "room_id": room_id,
                "agent_profile_id": agent_db_id,
                "agent_slug": template_slug,
                "hermes_profile": hermes_prof,
                "session_id": sid,
                "title": _resolved_session_title(hermes_prof, sid, str(row["title"] or "")),
                "status": str(row["status"] or "active"),
                "message_count": int(info.get("message_count") or 0),
                "created_at": _iso_from_unix(row["created_at"]),
                "updated_at": _iso_from_unix(row["updated_at"]),
                "active": str(row["status"] or "") == "active",
            }
        )
    return {"ok": True, "room_id": room_id, "sessions": sessions}


def profile_chat_activate_room_session(
    room_id: str,
    session_id: str,
    user_id: str,
    template_prof: str = "",
    *,
    source_id: str = "ui",
    client_id: str = "default",
    binding_version: int = 0,
) -> dict[str, Any]:
    room_id = str(room_id or "").strip()
    session_id = str(session_id or "").strip()
    user_id = str(user_id or "").strip()
    if not room_id or not session_id or not user_id:
        raise ValueError("room_id, session_id, and user required")

    conn = _workframe_db()
    try:
        room = conn.execute(
            "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
            (room_id,),
        ).fetchone()
        if not room:
            raise ValueError("room_not_found")
        if not _user_can_access_room(conn, room_id, user_id):
            raise ValueError("room_access_denied")
        workspace_id = str(room["workspace_id"])
        row = conn.execute(
            """
            SELECT rs.*, ap.slug AS agent_slug
            FROM room_sessions rs
            LEFT JOIN agent_profiles ap ON ap.id = rs.agent_profile_id
            WHERE rs.room_id = ? AND rs.session_id = ? AND rs.deleted_at IS NULL
            LIMIT 1
            """,
            (room_id, session_id),
        ).fetchone()
        if not row:
            raise ValueError("room_session_not_found")
        template_slug = str(template_prof or row["agent_slug"] or "").strip()
        if not template_slug:
            raise ValueError("agent_profile_not_found")
        agent_db_id = str(row["agent_profile_id"] or "").strip()
        hermes_prof = _resolve_chat_hermes_profile(template_slug, user_id, room_id, workspace_id)
        if not _session_exists(hermes_prof, session_id):
            raise ValueError("session_not_found")
        gateway_sid = str(row["gateway_session_id"] or f"api:{hermes_prof}:{session_id}").strip()
        title = str(_session_info(hermes_prof, session_id).get("title") or row["title"] or "")
        _upsert_room_session(
            conn,
            room_id=room_id,
            agent_profile_id=agent_db_id,
            session_id=session_id,
            gateway_session_id=gateway_sid,
            created_by=user_id,
            title=title,
        )
        conn.commit()
    finally:
        conn.close()

    _sync_lane_binding(
        hermes_prof,
        source_id,
        client_id,
        binding_version,
        session_id,
        gateway_sid,
    )

    if payer:
        _reconcile_profile_llm_for_user(hermes_prof, payer, workspace_id)
    llm_provider = _llm_billing_provider(hermes_prof, user_id=payer, workspace_id=workspace_id)
    llm_ready = _overlay_chat_llm_env(hermes_prof, user_id, workspace_id, llm_provider)

    history = chat_messages(hermes_prof, session_id)
    cohort = ensure_user_agent_cohort(user_id, workspace_id)
    return {
        "ok": True,
        "profile": hermes_prof,
        "template_profile": template_slug,
        "agent_display_name": _runtime_display_label(user_id, template_slug, workspace_id),
        "cohort": cohort,
        "room_id": room_id,
        "session_id": session_id,
        "title": title,
        "created": False,
        "resumed": True,
        "llm_ready": llm_ready,
        "has_llm_provider": llm_ready,
        "messages": history.get("messages") or [],
        "session": history.get("session") or {},
    }


def _message_activity_for_sessions(
    profile: str,
    crew_lookup: dict[str, Any],
    session_ids: set[str],
    limit: int = 80,
) -> list[dict[str, Any]]:
    if not session_ids:
        return []
    entries = _message_activity(profile, crew_lookup, limit * 3)
    return [entry for entry in entries if str(entry.get("session_id") or "") in session_ids][:limit]


def _room_session_activity_label(
    room_name: str,
    title: str,
    msg_count: int,
    status: str,
) -> str:
    base = str(title or room_name or "Session").strip()
    if msg_count > 0:
        return f"{base} · {msg_count} message{'s' if msg_count != 1 else ''}"
    if status == "active":
        return f"{base} · active"
    return base


def room_activity_data(
    room_id: str,
    user_id: str,
    *,
    profile_user_id: str | None = None,
) -> list[dict[str, Any]]:
    room_id = str(room_id or "").strip()
    user_id = str(user_id or "").strip()
    if not room_id or not user_id:
        return []
    conn = _workframe_db()
    try:
        room = conn.execute(
            "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
            (room_id,),
        ).fetchone()
        if not room or not _user_can_access_room(conn, room_id, user_id):
            return []
        workspace_id = str(room["workspace_id"])
        room_name = str(room["name"] or "Room")
        rows = _room_session_rows(conn, room_id)
    finally:
        conn.close()

    crew = workframe_agents().get("agents") or []
    if not isinstance(crew, list):
        crew = []
    crew_lookup = _crew_lookup(crew)
    merged: list[dict[str, Any]] = []
    session_ids_by_profile: dict[str, set[str]] = {}
    prof_uid = str(profile_user_id or user_id).strip() or user_id

    for row in rows:
        template_slug = str(row["agent_slug"] or "").strip()
        if not template_slug:
            continue
        sid = str(row["session_id"] or "").strip()
        hermes_prof = _resolve_chat_hermes_profile(template_slug, prof_uid, room_id, workspace_id)
        if not sid or not _session_exists(hermes_prof, sid):
            continue
        info = _session_info(hermes_prof, sid)
        msg_count = int(info.get("message_count") or 0)
        ended = info.get("ended_at")
        row_status = str(row["status"] or "active")
        if row_status == "active" and not ended:
            status = "active"
        elif ended:
            status = "completed"
        else:
            status = "idle"
        member = crew_lookup.get(template_slug.lower()) or crew_lookup.get(_profile_slug(template_slug).lower())
        agent = _resolve_agent(member, str(row["agent_display_name"] or _profile_display_name(template_slug)))
        title = _resolved_session_title(hermes_prof, sid, str(row["title"] or ""))
        desc = _room_session_activity_label(room_name, title, msg_count, status)
        merged.append(
            {
                "id": f"session:{hermes_prof}:{sid}",
                "kind": "session_start",
                "agent_name": agent["agent_name"],
                "profile": hermes_prof,
                "key": agent["key"],
                "task_description": desc,
                "status": status,
                "model_used": str(info.get("model") or ""),
                "created_at": _iso_from_unix(row["updated_at"] or row["created_at"]),
                "source": "session",
                "session_id": sid,
                "room_session_id": str(row["id"]),
                "message_count": msg_count,
            }
        )
        session_ids_by_profile.setdefault(hermes_prof, set()).add(sid)

    for prof, sids in session_ids_by_profile.items():
        merged.extend(_message_activity_for_sessions(prof, crew_lookup, sids, ACTIVITY_ROOM_LIMIT))

    merged.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return merged[:ACTIVITY_ROOM_LIMIT]


def _room_agent_dm_owner_user_id(conn: sqlite3.Connection, room_id: str) -> str | None:
    row = conn.execute(
        """
        SELECT rm.user_id FROM room_memberships rm
        WHERE rm.room_id = ? AND rm.deleted_at IS NULL AND rm.user_id IS NOT NULL
        ORDER BY rm.joined_at ASC
        LIMIT 1
        """,
        (room_id,),
    ).fetchone()
    if not row or not row["user_id"]:
        return None
    return str(row["user_id"]).strip() or None


def workspace_activity_data(workspace_id: str, user_id: str) -> list[dict[str, Any]]:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not _user_is_workspace_member(user_id, workspace_id):
        return []
    conn = _workframe_db()
    try:
        rooms = conn.execute(
            """
            SELECT id, room_type, agent_profile_id, name
            FROM rooms
            WHERE workspace_id = ? AND deleted_at IS NULL
            """,
            (workspace_id,),
        ).fetchall()
    finally:
        conn.close()
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for room in rooms:
        room_id = str(room["id"])
        profile_user_id = user_id
        if str(room["room_type"] or "") == "direct" and room["agent_profile_id"]:
            conn = _workframe_db()
            try:
                owner = _room_agent_dm_owner_user_id(conn, room_id)
            finally:
                conn.close()
            if owner:
                profile_user_id = owner
        for entry in room_activity_data(room_id, user_id, profile_user_id=profile_user_id):
            eid = str(entry.get("id") or "")
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            merged.append(entry)
    board_row = _workspace_kanban_board_row(workspace_id)
    board_slug = str(board_row["hermes_board_slug"]) if board_row else "default"
    crew = workframe_agents().get("agents") or []
    if not isinstance(crew, list):
        crew = []
    crew_lookup = _crew_lookup(crew)
    for entry in _kanban_activity(crew_lookup, 40, board_slug=board_slug):
        eid = str(entry.get("id") or "")
        if eid and eid in seen:
            continue
        if eid:
            seen.add(eid)
        merged.append(entry)
    merged.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return merged[:ACTIVITY_WORKSPACE_LIMIT]


def profile_chat_message(profile: str, payload: dict[str, Any]) -> dict[str, Any]:
    source_id = str(payload.get("source_id") or "ui").strip() or "ui"
    client_id = str(payload.get("client_id") or "default").strip() or "default"
    session_id = str(payload.get("session_id") or "").strip()
    text = str(payload.get("text") or "").strip()
    if not session_id:
        raise ValueError("session_id required")
    if not text:
        raise ValueError("text required")
    payer = str(payload.get("user_id") or "").strip()
    workspace_id = str(payload.get("workspace_id") or "").strip()
    room_id = str(payload.get("room_id") or "").strip()
    hermes_prof, _template_prof = _resolve_bind_profile_arg(
        profile, payer, room_id, workspace_id,
    )
    if payer:
        _reconcile_profile_llm_for_user(hermes_prof, payer, workspace_id)
    llm_provider = _llm_billing_provider(hermes_prof, user_id=payer, workspace_id=workspace_id)
    lifecycle = ensure_profile_api(
        hermes_prof,
        payer,
        workspace_id,
    )
    turn_run_id = str(uuid.uuid4())
    try:
        if payer:
            _overlay_turn_provider_env(
                hermes_prof, payer, workspace_id, llm_provider, turn_run_id,
            )
            _overlay_turn_user_env(hermes_prof, payer, workspace_id, turn_run_id)
        turn_body = _profile_turn_payload(hermes_prof, text, room_id)
        if payer and workspace_id:
            _inject_turn_credentials(turn_body, payer, workspace_id, llm_provider)
        status, data = _profile_api_request(
            hermes_prof,
            "POST",
            f"/api/sessions/{urllib.parse.quote(session_id, safe='')}/chat",
            turn_body,
        )
        if status >= 300:
            raise ValueError(f"session chat failed: {data}")
        assistant = ""
        if isinstance(data, dict):
            msg = data.get("message")
            if isinstance(msg, dict):
                assistant = str(msg.get("content") or "")
        chat_dispatch(
            {
                "profile": hermes_prof,
                "session_id": session_id,
                "gateway_session_id": f"api:{hermes_prof}:{session_id}",
                "source_id": source_id,
                "client_id": client_id,
                "room_id": room_id,
                "user_id": payer,
                "text": text,
            }
        )
        return {
            "ok": True,
            "profile": hermes_prof,
            "session_id": session_id,
            "api_port": lifecycle["api_port"],
            "assistant": assistant,
        }
    finally:
        if payer:
            _revoke_turn_credential_lease(turn_run_id, hermes_prof)


def _enrich_room_chat_payload(payload: dict[str, Any], user_id: str) -> dict[str, Any]:
    body = dict(payload) if isinstance(payload, dict) else {}
    body["user_id"] = user_id
    room_id = str(body.get("room_id") or "").strip()
    if room_id and not str(body.get("workspace_id") or "").strip():
        try:
            conn = _workframe_db()
            row = conn.execute(
                "SELECT workspace_id FROM rooms WHERE id = ? AND deleted_at IS NULL",
                (room_id,),
            ).fetchone()
            conn.close()
            if row:
                body["workspace_id"] = str(row["workspace_id"])
        except Exception:  # noqa: BLE001
            pass
    return body


def _emit_stream_chat_error(
    handler: BaseHTTPRequestHandler,
    message: str = "",
    *,
    entry: dict[str, Any] | None = None,
) -> None:
    """SSE error frame — structured playbook when entry supplied."""
    payload = llm_error_glossary.notice_payload(entry) if entry else {}
    if not payload:
        text = str(message or "").strip() or "Chat failed."
        payload = {"error": text, "text": text, "message": text}
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.end_headers()
        body = json.dumps(payload)
        handler.wfile.write(f"event: error\ndata: {body}\n\n".encode("utf-8"))
        handler.wfile.write(b"event: done\ndata: {}\n\n")
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return


def _emit_stream_concierge(handler: BaseHTTPRequestHandler, entry: dict[str, Any]) -> None:
    """Deterministic assistant reply when LLM path is unavailable."""
    payload = llm_error_glossary.notice_payload(entry)
    text = str(payload.get("message") or "")
    hint = str(payload.get("hint") or "").strip()
    if hint:
        text = f"{text}\n\n{hint}"
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.end_headers()
        handler.wfile.write(
            f"event: concierge\ndata: {json.dumps(payload)}\n\n".encode("utf-8"),
        )
        handler.wfile.write(
            f"event: message.complete\ndata: {json.dumps({'content': text, 'text': text})}\n\n".encode(
                "utf-8",
            ),
        )
        handler.wfile.write(b"event: done\ndata: {}\n\n")
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return


def _log_llm_failure(
    handler: BaseHTTPRequestHandler,
    code: str,
    *,
    provider: str = "",
    model: str = "",
    profile: str = "",
) -> None:
    if hasattr(handler, "_log_audit"):
        handler._log_audit(  # type: ignore[attr-defined]
            "llm_failure",
            "llm",
            profile or provider or "unknown",
            f"code={code} provider={provider} model={model}",
        )


def stream_profile_chat(handler: BaseHTTPRequestHandler, profile: str, payload: dict[str, Any]) -> None:
    _triggering_user = str(payload.get("user_id", "") or "")
    _workspace_id = str(payload.get("workspace_id", "") or "")
    _room_id = str(payload.get("room_id") or "").strip()
    _turn_run_id = str(uuid.uuid4())
    prof, _template_prof = _resolve_bind_profile_arg(
        profile, _triggering_user, _room_id, _workspace_id,
    )
    session_id = str(payload.get("session_id") or "").strip()
    text = str(payload.get("text") or "").strip()
    if not session_id:
        raise ValueError("session_id required")
    if not text:
        raise ValueError("text required")
    if _triggering_user:
        _reconcile_profile_llm_for_user(prof, _triggering_user, _workspace_id)
    llm_provider = _llm_billing_provider(prof, user_id=_triggering_user, workspace_id=_workspace_id)
    model_block = _read_model_block(prof)
    model_used = str(model_block.get("default") or "").strip()
    llm_ready = bool(
        _triggering_user
        and _user_can_use_llm(_triggering_user, _workspace_id, llm_provider)
    )
    if _triggering_user and not llm_ready:
        entry = concierge.respond(text, situation="no_provider")
        _log_llm_failure(handler, str(entry.get("code") or "no_llm_provider"), provider=llm_provider, profile=prof)
        _emit_stream_concierge(handler, entry)
        return
    try:
        lifecycle = ensure_profile_api(
            prof,
            _triggering_user,
            _workspace_id,
        )
        if _triggering_user:
            _require_user_provider(_triggering_user, _workspace_id, llm_provider)
            _overlay_turn_provider_env(
                prof, _triggering_user, _workspace_id, llm_provider, _turn_run_id,
            )
            _overlay_turn_user_env(prof, _triggering_user, _workspace_id, _turn_run_id)
    except ValueError as exc:
        err_text = str(exc)
        if "no_llm_provider_for_user" in err_text:
            entry = concierge.respond(text, situation="no_provider")
            _log_llm_failure(handler, "no_llm_provider", provider=llm_provider, profile=prof)
            _emit_stream_concierge(handler, entry)
            return
        entry = llm_error_glossary.classify_exception_text(err_text)
        _log_llm_failure(handler, str(entry.get("code") or ""), provider=llm_provider, profile=prof)
        _emit_stream_chat_error(handler, entry=entry)
        return
    upstream_body = json.dumps(_profile_turn_payload(prof, text, _room_id)).encode("utf-8")

    if _triggering_user and _workspace_id:
        _resolved_cred = _resolve_credential(
            _triggering_user,
            _workspace_id,
            llm_provider,
            user_only=True,
        )
        if _resolved_cred:
            try:
                _body = json.loads(upstream_body)
                _body["_credential_override"] = _resolved_cred["credential_ref"]
                _body["_credential_scope"] = _resolved_cred["scope"]
                upstream_body = json.dumps(_body).encode("utf-8")
            except Exception:
                pass

    port = _profile_api_port(prof)
    url = f"http://gateway:{port}/api/sessions/{urllib.parse.quote(session_id, safe='')}/chat/stream"
    headers = {
        "Authorization": f"Bearer {_profile_api_key(prof)}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=upstream_body, headers=headers, method="POST")
    try:
        upstream = urllib.request.urlopen(req, timeout=3600)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except Exception:  # noqa: BLE001
            data = {"error": raw or f"upstream stream failed: {exc.code}"}
        raise ValueError(f"session chat stream failed: {data}") from exc
    except OSError as exc:
        raise ValueError(f"session chat stream failed: {exc}") from exc

    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.send_header("X-Workframe-Profile", prof)
        handler.send_header("X-Workframe-Api-Port", str(lifecycle["api_port"]))
        handler.end_headers()
        handler.wfile.write(
            (
                "event: run.started\n"
                f"data: {json.dumps({'text': 'Contacting model...', 'model': model_used, 'llm_provider': llm_provider})}\n\n"
            ).encode("utf-8")
        )
        handler.wfile.flush()
        buffer = b""
        saw_complete = False
        complete_text = ""

        def _rewrite_event_frame(frame: bytes) -> bytes:
            nonlocal saw_complete, complete_text
            text = frame.decode("utf-8", errors="replace")
            lines = text.splitlines()
            event_name = ""
            data_lines: list[str] = []
            other_lines: list[str] = []
            for line in lines:
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
                elif line.strip():
                    other_lines.append(line)

            normalized = event_name
            if event_name in ("assistant.delta", "message.delta"):
                normalized = "message.delta"
            elif event_name in ("assistant.completed", "message.complete"):
                normalized = "message.complete"
                saw_complete = True
                if data_lines:
                    try:
                        payload = json.loads("\n".join(data_lines))
                        complete_text = str(
                            payload.get("content") or payload.get("text") or ""
                        ).strip()
                    except Exception:  # noqa: BLE001
                        complete_text = ""
            elif event_name in ("thinking.delta", "reasoning.delta"):
                normalized = "thinking.delta"
            elif event_name in ("run.failed",):
                normalized = "error"
            elif event_name == "error":
                normalized = "error"

            output_lines: list[str] = []
            if normalized:
                output_lines.append(f"event: {normalized}")
            output_lines.extend(other_lines)
            output_lines.extend(f"data: {line}" for line in data_lines)
            return ("\n".join(output_lines) + "\n\n").encode("utf-8") if output_lines else b""

        while True:
            chunk = upstream.read(4096)
            if not chunk:
                break
            buffer += chunk
            while True:
                sep = buffer.find(b"\n\n")
                crlf_sep = buffer.find(b"\r\n\r\n")
                if sep == -1 and crlf_sep == -1:
                    break
                if crlf_sep != -1 and (sep == -1 or crlf_sep < sep):
                    idx = crlf_sep
                    delimiter_len = 4
                else:
                    idx = sep
                    delimiter_len = 2
                frame = buffer[:idx]
                buffer = buffer[idx + delimiter_len :]
                rewritten = _rewrite_event_frame(frame)
                if rewritten:
                    handler.wfile.write(rewritten)
                    handler.wfile.flush()
        tail = buffer.strip()
        if tail:
            rewritten = _rewrite_event_frame(tail)
            if rewritten:
                handler.wfile.write(rewritten)
                handler.wfile.flush()
        if not saw_complete or not complete_text:
            config_key = _read_config_model_api_key(prof)
            _, model_name = _read_model_from_config(prof)
            if config_key.startswith(turn_credentials.LEASE_PREFIX) and not turn_credentials.validate_lease(
                config_key,
            ):
                entry = llm_error_glossary.playbook_entry("invalid_lease")
            else:
                entry = llm_error_glossary.playbook_entry("provider_empty_reply")
            _log_llm_failure(
                handler,
                str(entry.get("code") or "provider_empty_reply"),
                provider=llm_provider,
                model=str(model_name or ""),
                profile=prof,
            )
            err_payload = json.dumps(llm_error_glossary.notice_payload(entry))
            handler.wfile.write(f"event: error\ndata: {err_payload}\n\n".encode("utf-8"))
            handler.wfile.flush()
        handler.wfile.write(b"event: done\ndata: {}\n\n")
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return
    finally:
        try:
            upstream.close()
        except Exception:  # noqa: BLE001
            pass
        if _triggering_user:
            try:
                _revoke_turn_credential_lease(_turn_run_id, prof)
            except Exception:  # noqa: BLE001
                pass

    room_id = str(payload.get("room_id") or "").strip()
    if room_id:
        try:
            conn = _workframe_db()
            try:
                row = conn.execute(
                    """
                    SELECT id FROM room_sessions
                    WHERE room_id = ? AND session_id = ? AND deleted_at IS NULL
                    LIMIT 1
                    """,
                    (room_id, session_id),
                ).fetchone()
                if row:
                    now = str(int(time.time()))
                    conn.execute(
                        "UPDATE room_sessions SET updated_at = ? WHERE id = ?",
                        (now, row["id"]),
                    )
                    conn.commit()
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            _sync_lane_binding(
                prof,
                str(payload.get("source_id") or "ui").strip() or "ui",
                str(payload.get("client_id") or "default").strip() or "default",
                _binding_version(payload.get("binding_version")),
                session_id,
                f"api:{prof}:{session_id}",
                str(payload.get("text") or ""),
            )
        except Exception:  # noqa: BLE001
            pass
        return
    # ponytail: legacy global rebind when room_id omitted
    try:
        latest = _latest_api_session_id(prof)
        if latest and latest != session_id:
            source_id = str(payload.get("source_id") or "ui").strip() or "ui"
            client_id = str(payload.get("client_id") or "default").strip() or "default"
            binding_version = _binding_version(payload.get("binding_version"))
            chat_dispatch({
                "profile": prof,
                "session_id": latest,
                "gateway_session_id": f"api:{prof}:{latest}",
                "source_id": source_id,
                "client_id": client_id,
                "binding_version": binding_version,
                "text": "",
            })
    except Exception:  # noqa: BLE001
        pass


def _sync_lane_binding(
    profile: str,
    source_id: str,
    client_id: str,
    binding_version: int,
    session_id: str,
    gateway_session_id: str,
    text_preview: str = "",
) -> None:
    """Keep lane-registry aligned with room_sessions for UI client/source binding."""
    # ponytail: registry bookkeeping — slug only, no Hermes disk gate
    prof = safe_profile_slug(profile)
    sid = str(session_id or "").strip()
    if not sid:
        return
    gw = str(gateway_session_id or f"api:{prof}:{sid}").strip()
    registry = _load_lane_registry()
    bucket = _registry_profile_bucket(registry, prof)
    binding_key = _source_binding_key(source_id, client_id)
    bindings = bucket.setdefault("bindings", {})
    bindings[binding_key] = {
        "session_id": sid,
        "gateway_session_id": gw,
        "binding_version": binding_version,
        "last_text_preview": str(text_preview or "")[:240],
        "source_id": source_id,
        "client_id": client_id,
        "updated_at": _utc_now(),
    }
    _save_lane_registry(registry)


def _source_binding_key(source_id: str, client_id: str) -> str:
    src = (source_id or "ui").strip().lower()
    cli = (client_id or "default").strip().lower()
    safe_src = re.sub(r"[^a-z0-9._-]+", "-", src)[:64] or "ui"
    safe_cli = re.sub(r"[^a-z0-9._-]+", "-", cli)[:96] or "default"
    return f"{safe_src}:{safe_cli}"


def _registry_profile_bucket(registry: dict[str, Any], profile: str) -> dict[str, Any]:
    profiles = registry.setdefault("profiles", {})
    bucket = profiles.setdefault(profile, {})
    bindings = bucket.setdefault("bindings", {})
    if not isinstance(bindings, dict):
        bucket["bindings"] = {}
    return bucket


def chat_resolve(payload: dict[str, Any]) -> dict[str, Any]:
    profile = resolve_hermes_profile(str(payload.get("profile") or ""))
    source_id = str(payload.get("source_id") or "ui").strip() or "ui"
    client_id = str(payload.get("client_id") or "default").strip() or "default"
    binding_version = _binding_version(payload.get("binding_version"))
    binding_key = _source_binding_key(source_id, client_id)
    row = _binding_row_for(profile, source_id, client_id, binding_version)
    session_id = str((row or {}).get("session_id") or "").strip()
    return {
        "ok": True,
        "profile": profile,
        "source_id": source_id,
        "client_id": client_id,
        "binding_key": binding_key,
        "session_id": session_id,
    }


def chat_dispatch(payload: dict[str, Any]) -> dict[str, Any]:
    profile = resolve_hermes_profile(str(payload.get("profile") or ""))
    session_id = str(payload.get("session_id") or "").strip()
    gateway_session_id = str(payload.get("gateway_session_id") or "").strip()
    source_id = str(payload.get("source_id") or "ui").strip() or "ui"
    client_id = str(payload.get("client_id") or "default").strip() or "default"
    binding_version = _binding_version(payload.get("binding_version"))
    room_id = str(payload.get("room_id") or "").strip()
    user_id = str(payload.get("user_id") or "").strip()
    text = str(payload.get("text") or "").strip()
    if not session_id:
        raise ValueError("session_id required")
    if not gateway_session_id:
        raise ValueError("gateway_session_id required")

    if room_id:
        conn = _workframe_db()
        try:
            room = conn.execute(
                "SELECT workspace_id, agent_profile_id FROM rooms WHERE id = ? AND deleted_at IS NULL",
                (room_id,),
            ).fetchone()
            agent_profile_id = ""
            if room:
                room_agent = str(room["agent_profile_id"] or "").strip()
                if room_agent:
                    agent_profile_id = room_agent
                else:
                    agent_row = _lookup_agent_profile(conn, str(room["workspace_id"]), profile)
                    agent_profile_id = str(agent_row["id"]) if agent_row else ""
            if agent_profile_id:
                _upsert_room_session(
                    conn,
                    room_id=room_id,
                    agent_profile_id=agent_profile_id,
                    session_id=session_id,
                    gateway_session_id=gateway_session_id,
                    created_by=user_id or "system",
                )
                conn.commit()
        finally:
            conn.close()
        _sync_lane_binding(
            profile,
            source_id,
            client_id,
            binding_version,
            session_id,
            gateway_session_id,
            text,
        )
        return {"ok": True, "profile": profile, "room_id": room_id, "session_id": session_id}

    registry = _load_lane_registry()
    bucket = _registry_profile_bucket(registry, profile)
    binding_key = _source_binding_key(source_id, client_id)
    bindings = bucket.setdefault("bindings", {})
    bindings[binding_key] = {
        "session_id": session_id,
        "gateway_session_id": gateway_session_id,
        "binding_version": binding_version,
        "last_text_preview": text[:240],
        "source_id": source_id,
        "client_id": client_id,
        "updated_at": _utc_now(),
    }
    _save_lane_registry(registry)
    return {"ok": True, "profile": profile, "session_id": session_id, "binding_key": binding_key}


def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+)$", line.strip())
        if m:
            return m.group(1).strip()
    return fallback


def content_list() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    if not WORKSPACE.is_dir():
        return docs
    for path in sorted(WORKSPACE.rglob("*.md")):
        if not path.is_file():
            continue
        rel = path.relative_to(WORKSPACE).as_posix()
        if _workspace_protected_reason(rel):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            mtime = path.stat().st_mtime
            size = path.stat().st_size
        except OSError:
            continue
        docs.append(
            {
                "agent": "workspace",
                "filename": rel,
                "title": _extract_title(text, Path(rel).stem.replace("-", " ")),
                "modified_at": _iso_from_unix(mtime),
                "size": size,
                "path": rel,
            }
        )
    docs.sort(key=lambda d: d.get("modified_at") or "", reverse=True)
    return docs


def board_list() -> list[dict[str, Any]]:
    with _board_lock:
        conn = _rw_sqlite(BOARD_DB)
        try:
            rows = conn.execute(
                "SELECT id, title, status, priority, notes, created_at, updated_at FROM tasks ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def board_create(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("title required")
    now = _utc_now()
    task = {
        "id": str(uuid.uuid4()),
        "title": title,
        "status": str(payload.get("status") or "pending"),
        "priority": str(payload.get("priority") or "medium"),
        "notes": str(payload.get("notes") or ""),
        "created_at": now,
        "updated_at": now,
    }
    with _board_lock:
        conn = _rw_sqlite(BOARD_DB)
        try:
            conn.execute(
                "INSERT INTO tasks (id, title, status, priority, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (
                    task["id"],
                    task["title"],
                    task["status"],
                    task["priority"],
                    task["notes"],
                    task["created_at"],
                    task["updated_at"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return task


def board_update(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {"title", "status", "priority", "notes"}
    fields = {k: payload[k] for k in allowed if k in payload}
    if not fields:
        raise ValueError("no fields to update")
    fields["updated_at"] = _utc_now()
    sets = ", ".join(f"{k}=?" for k in fields)
    with _board_lock:
        conn = _rw_sqlite(BOARD_DB)
        try:
            conn.execute(f"UPDATE tasks SET {sets} WHERE id=?", (*fields.values(), task_id))
            conn.commit()
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row:
                raise ValueError("not found")
            return dict(row)
        finally:
            conn.close()


def board_delete(task_id: str) -> None:
    with _board_lock:
        conn = _rw_sqlite(BOARD_DB)
        try:
            conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            conn.commit()
        finally:
            conn.close()


def build_snapshot() -> dict[str, Any]:
    profiles = _list_profiles()
    primary = _primary_profile()
    gateway = gateway_data(primary) if primary else gateway_data("")
    crew = crew_data(profiles, primary, gateway)
    activity = activity_data(profiles, crew)
    health = health_data(primary)
    sessions = sessions_data(primary) if primary else sessions_data("")
    kanban = kanban_data()
    cron = cron_data(primary) if primary else cron_data("")
    return {
        "ok": True,
        "generated_at": _utc_now(),
        "version": VERSION,
        "project_name": PROJECT_NAME,
        "native_profile": primary,
        "native_agent_name": _native_display_name(),
        "native_model": _profile_model(primary) if primary else "",
        "profiles": profiles,
        "crew": crew,
        "gateway": gateway,
        "sessions": sessions,
        "activity": activity["entries"],
        "agents": activity["agents"],
        "activity_by_day": activity["activity_by_day"],
        "stats": activity["stats"],
        "kanban": kanban,
        "cron": cron,
        "crons": cron,
        "vps": health,
        "health": health,
    }


def workframe_meta() -> dict[str, Any]:
    primary = _primary_profile()
    return {
        "ok": True,
        "project_name": PROJECT_NAME,
        "install_id": str(os.environ.get("WORKFRAME_INSTALL_ID") or "").strip(),
        "native_profile": primary,
        "native_agent_name": _native_display_name(),
        "native_model": _profile_model(primary) if primary else "",
        "app_base_url": APP_BASE_URL,
        "deployment_mode": DEPLOYMENT_MODE,
        "workspace": {
            "content_root": CONTENT_ROOT.as_posix(),
            "root": WORKSPACE.as_posix(),
        },
    }


def _hermes_dashboard_gate_status(handler: BaseHTTPRequestHandler) -> int:
    """nginx auth_request helper: 204 allow, 403 deny."""
    if DEPLOYMENT_MODE == "single_user_local":
        return 204
    user_id = str(getattr(handler, "auth_user", "") or "").strip()
    if DEPLOYMENT_MODE == "trusted_team":
        if DEV_LOCAL_UNSAFE or user_id:
            return 204
        return 403
    if not user_id:
        return 403
    if str(getattr(handler, "auth_role", "") or "") in OWNER_ADMIN_ROLES:
        return 204
    return 403


def workframe_agents() -> dict[str, Any]:
    profiles = _workspace_crew_profile_names()
    primary = _primary_profile()
    gateway = gateway_data(primary) if primary else gateway_data("")
    crew = crew_data(profiles, primary, gateway)
    return {
        "ok": True,
        "project_name": PROJECT_NAME,
        "native_profile": primary,
        "crew": crew,
    }


def _workspace_crew_profile_names(workspace_id: str | None = None) -> list[str]:
    """ponytail: rail shows workspace agents + primary Hermes profile, not every stale on-disk profile."""
    primary = _primary_profile()
    on_disk = set(_list_profiles())
    profiles: list[str] = []
    rows: list[sqlite3.Row] = []
    try:
        conn = _workframe_db()
        ws_id = str(workspace_id or "").strip()
        if not ws_id:
            ws = conn.execute(
                "SELECT id FROM workspaces WHERE slug = 'default' AND deleted_at IS NULL LIMIT 1",
            ).fetchone()
            ws_id = str(ws["id"]) if ws else ""
        if ws_id:
            rows = conn.execute(
                """
                SELECT slug, is_native
                FROM agent_profiles
                WHERE workspace_id = ? AND deleted_at IS NULL
                ORDER BY created_at ASC
                """,
                (ws_id,),
            ).fetchall()
        conn.close()
    except Exception:
        rows = []
    if primary and primary in on_disk:
        profiles.append(primary)
    for row in rows:
        if int(row["is_native"] or 0):
            continue
        slug = str(row["slug"] or "").strip()
        if slug in on_disk and slug not in profiles:
            profiles.append(slug)
    if not profiles:
        if primary and primary in on_disk:
            return [primary]
        return sorted(on_disk)[:1]
    return profiles


def hermes_bootstrap(profile: str = "") -> dict[str, Any]:
    internal_url = os.environ.get("HERMES_DASHBOARD_URL", "http://127.0.0.1:19119").rstrip("/")
    public_url = os.environ.get("HERMES_DASHBOARD_PUBLIC_URL", internal_url).rstrip("/")
    try:
        token = _dashboard_session_token(internal_url)
        embedded_chat = _dashboard_embedded_chat(internal_url)
    except ValueError as exc:
        return {
            "ok": False,
            "dashboard_url": public_url,
            "token": "",
            "embedded_chat": False,
            "error": str(exc),
        }
    return {
        "ok": True,
        "dashboard_url": public_url,
        "token": token,
        "embedded_chat": embedded_chat,
    }


def _dashboard_embedded_chat(internal_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{internal_url}/", timeout=DASHBOARD_HTTP_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return False
    chat_match = re.search(r"__HERMES_DASHBOARD_EMBEDDED_CHAT__=(true|false)", html)
    return (chat_match.group(1) == "true") if chat_match else False


def _dashboard_get(path: str) -> Any:
    internal_url = os.environ.get("HERMES_DASHBOARD_URL", "http://127.0.0.1:19119").rstrip("/")
    token = _dashboard_session_token(internal_url)
    req = urllib.request.Request(
        f"{internal_url}{path}",
        headers={"X-Hermes-Session-Token": token},
    )
    with urllib.request.urlopen(req, timeout=DASHBOARD_HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace") or "null")


def hermes_skills() -> list[dict[str, Any]]:
    """Installed skills from Hermes dashboard — same source as TUI /skills."""
    try:
        data = _dashboard_get("/api/skills")
    except ValueError:
        return []
    return data if isinstance(data, list) else []


# Cache the set of installed skill names so /api/hermes/commands/exec
# can recognise `/skillname` even though skills aren't in the static
# command catalog. The cache TTL is short — a minute is plenty for
# "user clicked a skill, BFF looks it up". Install/uninstall flows
# invalidate naturally within the window.
_skill_name_cache: dict[str, Any] = {"names": None, "expires_at": 0.0}
_SKILL_CACHE_TTL_SECONDS = 60


def _known_skill_names() -> set[str]:
    import time
    now = time.time()
    cached = _skill_name_cache.get("names")
    if cached is not None and _skill_name_cache.get("expires_at", 0) > now:
        return cached
    try:
        names = {str(s.get("name", "")).strip() for s in hermes_skills() if s.get("name")}
    except Exception:
        names = cached or set()
    _skill_name_cache["names"] = names
    _skill_name_cache["expires_at"] = now + _SKILL_CACHE_TTL_SECONDS
    return names


def _is_known_skill(name: str) -> bool:
    if not name:
        return False
    return name in _known_skill_names()


# Static mirror of Hermes' COMMAND_REGISTRY (hermes_cli/commands.py).
# The BFF does not import hermes_agent; it serves a curated snapshot so the
# Workframe UI has a fast, local source of truth for the slash palette.
# Drift is acceptable: any new command lands here in the same release that
# updates upstream Hermes. See workframe-api dead-code note for context.
HERMES_COMMANDS: list[dict[str, Any]] = [
    # Session
    {"name": "/new", "aliases": ["/reset"], "category": "Session",
     "description": "Fresh session", "args_hint": "",
     "dispatch": "client:startNewSession"},
    {"name": "/clear", "aliases": [], "category": "Session",
     "description": "Clear screen + new session", "args_hint": "",
     "dispatch": "client:clearMessages"},
    {"name": "/retry", "aliases": [], "category": "Session",
     "description": "Resend last message", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/undo", "aliases": [], "category": "Session",
     "description": "Remove last exchange", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/compress", "aliases": [], "category": "Session",
     "description": "Manually compress context", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/stop", "aliases": [], "category": "Session",
     "description": "Kill background processes", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/rollback", "aliases": [], "category": "Session",
     "description": "Restore filesystem checkpoint", "args_hint": "[N]",
     "dispatch": "gateway"},
    {"name": "/snapshot", "aliases": [], "category": "Session",
     "description": "Create or restore state snapshots", "args_hint": "[sub]",
     "dispatch": "gateway"},
    {"name": "/background", "aliases": [], "category": "Session",
     "description": "Run prompt in background", "args_hint": "<prompt>",
     "dispatch": "gateway"},
    {"name": "/queue", "aliases": [], "category": "Session",
     "description": "Queue for next turn", "args_hint": "<prompt>",
     "dispatch": "gateway"},
    {"name": "/steer", "aliases": [], "category": "Session",
     "description": "Inject after the next tool call", "args_hint": "<prompt>",
     "dispatch": "gateway"},
    {"name": "/agents", "aliases": ["/tasks"], "category": "Session",
     "description": "Show active agents and running tasks", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/resume", "aliases": [], "category": "Session",
     "description": "Resume a named session", "args_hint": "[name]",
     "dispatch": "gateway"},
    {"name": "/goal", "aliases": [], "category": "Session",
     "description": "Set a standing goal", "args_hint": "[text|sub]",
     "dispatch": "gateway"},
    {"name": "/redraw", "aliases": [], "category": "Session",
     "description": "Force a full UI repaint", "args_hint": "",
     "dispatch": "client:noOp"},

    # Configuration
    {"name": "/model", "aliases": [], "category": "Configuration",
     "description": "Show or change model", "args_hint": "[name]",
     "dispatch": "client:openModelSwitcher"},
    {"name": "/personality", "aliases": [], "category": "Configuration",
     "description": "Set personality", "args_hint": "[name]",
     "dispatch": "client:openPersonality"},
    {"name": "/reasoning", "aliases": [], "category": "Configuration",
     "description": "Set reasoning", "args_hint": "[level]",
     "dispatch": "gateway"},
    {"name": "/verbose", "aliases": [], "category": "Configuration",
     "description": "Cycle verbose level", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/voice", "aliases": [], "category": "Configuration",
     "description": "Voice mode", "args_hint": "[on|off|tts]",
     "dispatch": "gateway"},
    {"name": "/yolo", "aliases": [], "category": "Configuration",
     "description": "Toggle approval bypass", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/busy", "aliases": [], "category": "Configuration",
     "description": "What Enter does while working", "args_hint": "[sub]",
     "dispatch": "gateway"},
    {"name": "/indicator", "aliases": [], "category": "Configuration",
     "description": "Busy indicator style", "args_hint": "[style]",
     "dispatch": "gateway"},
    {"name": "/footer", "aliases": [], "category": "Configuration",
     "description": "Gateway runtime footer on replies", "args_hint": "[on|off]",
     "dispatch": "gateway"},
    {"name": "/skin", "aliases": [], "category": "Configuration",
     "description": "Change theme (CLI)", "args_hint": "[name]",
     "dispatch": "gateway"},
    {"name": "/statusbar", "aliases": [], "category": "Configuration",
     "description": "Toggle status bar (CLI)", "args_hint": "",
     "dispatch": "gateway"},

    # Tools & Skills
    {"name": "/tools", "aliases": [], "category": "Tools & Skills",
     "description": "Manage tools", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/toolsets", "aliases": [], "category": "Tools & Skills",
     "description": "List toolsets", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/skills", "aliases": [], "category": "Tools & Skills",
     "description": "Search/install skills", "args_hint": "",
     "dispatch": "client:openSkills"},
    {"name": "/skill", "aliases": [], "category": "Tools & Skills",
     "description": "Load a skill into session", "args_hint": "<name>",
     "dispatch": "gateway"},
    {"name": "/reload-skills", "aliases": [], "category": "Tools & Skills",
     "description": "Re-scan ~/.hermes/skills/", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/reload", "aliases": [], "category": "Tools & Skills",
     "description": "Reload .env into running session", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/reload-mcp", "aliases": [], "category": "Tools & Skills",
     "description": "Reload MCP servers", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/cron", "aliases": [], "category": "Tools & Skills",
     "description": "Manage cron jobs", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/curator", "aliases": [], "category": "Tools & Skills",
     "description": "Skill lifecycle", "args_hint": "[sub]",
     "dispatch": "gateway"},
    {"name": "/kanban", "aliases": [], "category": "Tools & Skills",
     "description": "Multi-profile board", "args_hint": "[sub]",
     "dispatch": "gateway"},
    {"name": "/plugins", "aliases": [], "category": "Tools & Skills",
     "description": "List plugins", "args_hint": "",
     "dispatch": "gateway"},

    # Utility
    {"name": "/branch", "aliases": ["/fork"], "category": "Utility",
     "description": "Branch the current session", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/fast", "aliases": [], "category": "Utility",
     "description": "Toggle priority/fast processing", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/browser", "aliases": [], "category": "Utility",
     "description": "Open CDP browser connection", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/history", "aliases": [], "category": "Utility",
     "description": "Show conversation history", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/save", "aliases": [], "category": "Utility",
     "description": "Save conversation to file", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/copy", "aliases": [], "category": "Utility",
     "description": "Copy last assistant reply", "args_hint": "[N]",
     "dispatch": "gateway"},
    {"name": "/paste", "aliases": [], "category": "Utility",
     "description": "Attach clipboard image", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/image", "aliases": [], "category": "Utility",
     "description": "Attach local image file", "args_hint": "",
     "dispatch": "gateway"},

    # Info
    {"name": "/help", "aliases": [], "category": "Info",
     "description": "Show commands", "args_hint": "",
     "dispatch": "client:openHelp"},
    {"name": "/status", "aliases": [], "category": "Info",
     "description": "Session info", "args_hint": "",
     "dispatch": "client:openStatus"},
    {"name": "/usage", "aliases": [], "category": "Info",
     "description": "Token usage for the active session", "args_hint": "",
     "dispatch": "client:openUsage"},
    {"name": "/insights", "aliases": [], "category": "Info",
     "description": "Usage analytics", "args_hint": "[days]",
     "dispatch": "client:openInsights"},
    {"name": "/gquota", "aliases": [], "category": "Info",
     "description": "Google Gemini quota", "args_hint": "",
     "dispatch": "client:openGquota"},
    {"name": "/commands", "aliases": [], "category": "Info",
     "description": "Browse all commands", "args_hint": "[page]",
     "dispatch": "client:openHelp"},
    {"name": "/profile", "aliases": [], "category": "Info",
     "description": "Active profile info", "args_hint": "",
     "dispatch": "client:openProfile"},
    {"name": "/debug", "aliases": [], "category": "Info",
     "description": "Upload debug report", "args_hint": "",
     "dispatch": "client:openDebug"},

    # Exit
    {"name": "/quit", "aliases": ["/exit", "/q"], "category": "Exit",
     "description": "Exit CLI", "args_hint": "",
     "dispatch": "client:noOp"},
]


def _resolve_command(token: str) -> dict[str, Any] | None:
    """Resolve a slash token (with or without leading /) to a wired
    catalog entry. Wip commands are internal-only — they live in
    `HERMES_COMMANDS` for the team to track progress, but `_resolve_command`
    treats them as not-found so the user can never accidentally invoke
    something that isn't wired end-to-end.
    """
    if not token:
        return None
    needle = token if token.startswith("/") else f"/{token}"
    for entry in HERMES_COMMANDS:
        if entry.get("wip", False):
            continue
        if entry["name"] == needle or needle in entry.get("aliases", []):
            return entry
    return None


# Canonical 3-tier model chain. `primary` is what new sessions resolve to;
# the fallback list kicks in when the primary fails (rate limit, 5xx,
# timeout). Order matters — Hermes tries them in sequence. Per-profile
# overrides live in the profile's config.yaml under `model.default` and
# `fallback_providers`; this constant is the install-wide default the
# migration writes when a profile is missing either field.
HERMES_DEFAULT_PRIMARY = "google/gemini-2.5-flash"
HERMES_DEFAULT_FALLBACK_CHAIN: list[dict[str, str]] = [
    {"provider": "openrouter", "model": "anthropic/claude-sonnet-4.5"},
    {"provider": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct:free"},
]

# ponytail: minimum-viable agentic models per LLM provider; user can escalate in settings.
PROVIDER_MVP_MODELS: dict[str, dict[str, Any]] = {
    "openrouter": {
        "primary": "google/gemini-2.5-flash",
        "fallbacks": list(HERMES_DEFAULT_FALLBACK_CHAIN),
    },
    "openai": {
        "primary": "gpt-5.4-medium",
        "fallbacks": [{"provider": "openai", "model": "gpt-4o-mini"}],
    },
    "anthropic": {
        "primary": "claude-sonnet-4-5",
        "fallbacks": [{"provider": "anthropic", "model": "claude-3-5-haiku-20241022"}],
    },
    "google": {
        "primary": "gemini-2.5-flash",
        "fallbacks": [{"provider": "google", "model": "gemini-2.5-flash-lite"}],
    },
    "deepseek": {
        "primary": "deepseek-chat",
        "fallbacks": [{"provider": "deepseek", "model": "deepseek-chat"}],
    },
    "codex": {
        "primary": "gpt-5.4-medium",
        "fallbacks": [
            {"provider": "openai-codex", "model": "gpt-5.4-medium"},
            {"provider": "openai-codex", "model": "gpt-5.4-mini"},
        ],
    },
    "nous": {
        "primary": "nousresearch/hermes-4-70b",
        "fallbacks": [{"provider": "nous", "model": "nousresearch/hermes-4-70b"}],
    },
}


# ponytail: billing id (connect catalog) ↔ Hermes config model.provider ↔ picker rows
_PROVIDER_CATALOG_TAGS: dict[str, frozenset[str]] = {
    "codex": frozenset({"codex", "openai"}),
    "openai": frozenset({"openai"}),
    "openrouter": frozenset({"openrouter"}),
    "anthropic": frozenset({"anthropic"}),
    "google": frozenset({"google"}),
    "deepseek": frozenset({"deepseek"}),
    "nous": frozenset({"nous"}),
}

_CODEX_EXTRA_MODELS: tuple[tuple[str, str, str], ...] = (
    ("gpt-5.4-medium", "GPT-5.4 Medium", "Codex default — agentic, tool-capable."),
    ("gpt-5.4-mini", "GPT-5.4 Mini", "Faster Codex model on ChatGPT account."),
)


def _billing_provider_id_from_hermes_config(cfg_provider: str) -> str:
    p = str(cfg_provider or "").strip().lower()
    if p in {"openai-codex", "openai_codex", "codex"}:
        return "codex"
    if p in PROVIDER_MVP_MODELS:
        return p
    return ""


def _catalog_tags_for_billing_provider(provider_id: str) -> frozenset[str]:
    return _PROVIDER_CATALOG_TAGS.get(str(provider_id or "").strip().lower(), frozenset())


def _catalog_row_for_billing_provider(row: dict[str, str], provider_id: str) -> bool:
    tags = _catalog_tags_for_billing_provider(provider_id)
    if not tags:
        return False
    row_tag = str(row.get("provider") or "").strip().lower()
    return row_tag in tags


def _provider_display_label(provider_id: str) -> str:
    spec = _catalog_provider(provider_id) or {}
    return str(spec.get("label") or provider_id).strip() or provider_id


def _model_catalog_rows_for_provider(provider_id: str) -> list[dict[str, str]]:
    """Curated models a connected billing provider can run."""
    provider_key = str(provider_id or "").strip().lower()
    label = _provider_display_label(provider_key)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(model: str, row_label: str, description: str) -> None:
        mid = str(model or "").strip()
        if not mid or mid in seen:
            return
        seen.add(mid)
        rows.append(
            {
                "provider": label,
                "billing_provider": provider_key,
                "model": mid,
                "label": row_label,
                "description": description,
            }
        )

    if provider_key == "codex":
        for model, row_label, description in _CODEX_EXTRA_MODELS:
            _add(model, row_label, description)
    mvp = PROVIDER_MVP_MODELS.get(provider_key) or {}
    primary = str(mvp.get("primary") or "").strip()
    if primary:
        _add(primary, primary, f"Default for {label}.")
    for fb in mvp.get("fallbacks") or []:
        if isinstance(fb, dict):
            _add(str(fb.get("model") or ""), str(fb.get("model") or ""), f"Fallback for {label}.")
    for row in HERMES_MODEL_CATALOG:
        if _catalog_row_for_billing_provider(row, provider_key):
            _add(
                str(row.get("model") or ""),
                str(row.get("label") or row.get("model") or ""),
                str(row.get("description") or ""),
            )
    return rows


def _suggestions_for_connected_llm_providers(connected: set[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for provider_id in sorted(connected):
        for row in _model_catalog_rows_for_provider(provider_id):
            mid = str(row.get("model") or "").strip()
            if not mid or mid in seen:
                continue
            seen.add(mid)
            out.append(row)
    return out


def _resolve_billing_provider_for_model(model_id: str, connected: set[str]) -> str:
    mid = str(model_id or "").strip()
    if not mid or not connected:
        return ""
    for provider_id in sorted(connected):
        for row in _model_catalog_rows_for_provider(provider_id):
            if str(row.get("model") or "").strip() == mid:
                return provider_id
    low = mid.lower()
    if low.startswith("gpt-") and "codex" in connected:
        return "codex"
    if low.startswith("gpt-") and "openai" in connected:
        return "openai"
    if "/" in mid and "openrouter" in connected:
        return "openrouter"
    if low.startswith("claude") and "anthropic" in connected:
        return "anthropic"
    if "gemini" in low and "google" in connected:
        return "google"
    if "deepseek" in low and "deepseek" in connected:
        return "deepseek"
    return ""


def _strip_profile_model_proxy_fields(profile: str) -> None:
    """OAuth/native providers: drop internal proxy base_url + lease api_key from model block."""
    config_path = _profile_gateway_config_path(profile)
    if not config_path or not config_path.is_file():
        return
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return
    out: list[str] = []
    in_model = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("model:") and not line.startswith((" ", "\t")):
            in_model = True
            out.append(line)
            continue
        if in_model and stripped and not line.startswith((" ", "\t", "#")):
            in_model = False
        if in_model and stripped.startswith(("base_url:", "api_key:")):
            continue
        out.append(line)
    try:
        config_path.write_text("".join(out), encoding="utf-8")
    except OSError:
        return


def _apply_model_for_billing_provider(
    profile: str,
    billing: str,
    model_id: str,
    user_id: str = "",
) -> bool:
    billing = str(billing or "").strip().lower()
    ok, _ = _set_profile_model(profile, model_id)
    if not ok:
        return False
    if _oauth_llm_provider_spec(billing):
        ok_provider, _ = _set_profile_model_provider(profile, _hermes_config_provider_id(billing))
        if not ok_provider:
            return False
        _strip_profile_model_proxy_fields(profile)
        fallbacks = PROVIDER_MVP_MODELS.get(billing, {}).get("fallbacks") or []
        if isinstance(fallbacks, list):
            _write_fallback_chain(profile, fallbacks)
        user = str(user_id or "").strip()
        if user:
            _sync_oauth_llm_to_profile(profile, user, billing)
        return True
    ok_provider, _ = _set_profile_model_provider(profile, "custom")
    if not ok_provider:
        return False
    _set_profile_model_base_url(profile, _llm_proxy_base_url(billing))
    return True


def _hermes_config_provider_id(provider_key: str) -> str:
    spec = _catalog_provider(provider_key)
    if spec and spec.get("hermes_auth_id"):
        return str(spec["hermes_auth_id"])
    return str(provider_key or "").strip().lower()


def _first_connected_llm_provider(user_id: str = "", workspace_id: str = "") -> str:
    for spec in PROVIDER_CONNECT_CATALOG:
        if str(spec.get("category") or "") != "llm":
            continue
        provider_id = str(spec["id"])
        if user_id and _user_provider_connected(str(user_id), spec):
            return provider_id
        if workspace_id and str(spec.get("env_var") or ""):
            resolved = _resolve_credential("", str(workspace_id), provider_id)
            if resolved and _credential_secret(resolved, str(user_id or "")):
                return provider_id
    return "openrouter"


def _apply_mvp_model_for_provider(profile: str, provider: str) -> bool:
    """Write model.default, model.provider, and fallback_providers to config.yaml."""
    provider_key = str(provider or "openrouter").strip().lower()
    spec = PROVIDER_MVP_MODELS.get(provider_key) or PROVIDER_MVP_MODELS["openrouter"]
    try:
        _ensure_gateway_config_file(profile)
    except ValueError:
        return False
    ok, _ = _set_profile_model(profile, str(spec["primary"]))
    if not ok:
        return False
    ok_provider, _ = _set_profile_model_provider(profile, _hermes_config_provider_id(provider_key))
    fallbacks = spec.get("fallbacks") if isinstance(spec.get("fallbacks"), list) else []
    ok_chain, _ = _write_fallback_chain(profile, fallbacks)
    return ok_provider and ok_chain


def _bootstrap_model_after_llm_connect(
    user_id: str,
    workspace_id: str,
    provider: str,
) -> None:
    """Seed MVP model on runtime + primary profiles when an LLM key is connected."""
    spec = _catalog_provider(provider)
    if not spec or str(spec.get("category") or "") != "llm":
        return
    provider_key = str(provider or "").strip().lower()
    user = str(user_id or "").strip()
    ws = str(workspace_id or "").strip()
    primary = _primary_profile()
    if primary:
        if user and _oauth_llm_provider_spec(provider_key):
            _reconcile_profile_llm_for_user(primary, user, ws, prefer_provider=provider_key)
        else:
            _, model = _read_model_from_config(primary)
            if not str(model or "").strip():
                _apply_mvp_model_for_provider(primary, provider_key)
            elif user:
                _reconcile_profile_llm_for_user(primary, user, ws, prefer_provider=provider_key)
    template = primary or "workframe-agent"
    runtime = _runtime_profile_slug(user_id, template)
    if _runtime_profile_on_disk(runtime):
        if user and _oauth_llm_provider_spec(provider_key):
            _reconcile_profile_llm_for_user(runtime, user, ws, prefer_provider=provider_key)
        else:
            _, model = _read_model_from_config(runtime)
            if not str(model or "").strip():
                _apply_mvp_model_for_provider(runtime, provider_key)
            elif user:
                _reconcile_profile_llm_for_user(runtime, user, ws, prefer_provider=provider_key)


# Curated snapshot of commonly-used models per provider. Surfaced in the
# Workframe picker as suggestions — the BFF also accepts arbitrary
# `provider/model` ids so users aren't boxed in. The picker shows this
# list ONLY for the active provider; cross-provider entries are hidden
# because they need the matching API key in env to actually work.
HERMES_MODEL_CATALOG: list[dict[str, str]] = [
    {"provider": "Anthropic", "model": "claude-sonnet-4-5",
     "label": "Claude Sonnet 4.5",
     "description": "Latest Sonnet. Strong general purpose."},
    {"provider": "Anthropic", "model": "claude-opus-4-1",
     "label": "Claude Opus 4.1",
     "description": "Heaviest reasoning. Slow but thorough."},
    {"provider": "Anthropic", "model": "claude-3-5-sonnet-20241022",
     "label": "Claude 3.5 Sonnet",
     "description": "Previous gen. Still very capable."},
    {"provider": "Anthropic", "model": "claude-3-5-haiku-20241022",
     "label": "Claude 3.5 Haiku",
     "description": "Fast and cheap."},
    {"provider": "OpenAI", "model": "gpt-5.4-medium",
     "label": "GPT-5.4 Medium", "description": "Workframe OpenAI default — agentic, tool-capable."},
    {"provider": "OpenAI", "model": "gpt-4o",
     "label": "GPT-4o", "description": "OpenAI flagship multimodal."},
    {"provider": "OpenAI", "model": "gpt-4o-mini",
     "label": "GPT-4o mini", "description": "Cheap, fast."},
    {"provider": "OpenAI", "model": "o1",
     "label": "o1", "description": "Reasoning model."},
    {"provider": "OpenAI", "model": "o1-mini",
     "label": "o1 mini", "description": "Cheaper reasoning."},
    {"provider": "OpenAI", "model": "gpt-5.4-mini",
     "label": "GPT-5.4 Mini", "description": "Faster Codex / OpenAI model."},
    {"provider": "Codex", "model": "gpt-5.4-medium",
     "label": "GPT-5.4 Medium (Codex)", "description": "Codex ChatGPT account default."},
    {"provider": "Codex", "model": "gpt-5.4-mini",
     "label": "GPT-5.4 Mini (Codex)", "description": "Faster Codex model."},
    {"provider": "Google", "model": "gemini-2.5-pro",
     "label": "Gemini 2.5 Pro",
     "description": "Long context, strong reasoning."},
    {"provider": "Google", "model": "gemini-2.0-flash",
     "label": "Gemini 2.0 Flash", "description": "Fast, cheap."},
    {"provider": "DeepSeek", "model": "deepseek-chat",
     "label": "DeepSeek Chat",
     "description": "DeepSeek general chat model."},
    {"provider": "DeepSeek", "model": "deepseek-reasoner",
     "label": "DeepSeek Reasoner",
     "description": "Reasoning-focused DeepSeek model."},
    {"provider": "OpenRouter", "model": "openrouter/auto",
     "label": "OpenRouter Auto",
     "description": "OpenRouter picks the best model per prompt."},
    {"provider": "OpenRouter", "model": "google/gemini-2.5-flash",
     "label": "Gemini 2.5 Flash",
     "description": "Fast, capable default for OpenRouter BYOK."},
    {"provider": "OpenRouter", "model": "anthropic/claude-sonnet-4.5",
     "label": "Claude Sonnet 4.5 (via OR)",
     "description": "Strong agentic fallback on OpenRouter."},
    {"provider": "OpenRouter", "model": "meta-llama/llama-3.3-70b-instruct:free",
     "label": "Llama 3.3 70B (free)",
     "description": "Free-tier OpenRouter fallback when available."},
    {"provider": "OpenRouter", "model": "z-ai/glm-5.1",
     "label": "GLM 5.1",
     "description": "High-availability model on OpenRouter."},
    {"provider": "OpenRouter", "model": "nousresearch/hermes-4-70b",
     "label": "Hermes 4 70B",
     "description": "Agent-tuned model on OpenRouter."},
    {"provider": "OpenRouter", "model": "openrouter/nvidia/llama-3.1-nemotron-70b-instruct",
     "label": "Nemotron 70B Instruct",
     "description": "NVIDIA Nemotron via OpenRouter."},
    {"provider": "OpenRouter", "model": "openrouter/openai/gpt-4o",
     "label": "GPT-4o (via OR)",
     "description": "GPT-4o through OpenRouter."},
]


def _set_profile_model(profile: str, model_id: str) -> tuple[bool, str]:
    """Update `model.default` in config.yaml. Minimal text rewrite — no pyyaml."""
    _normalize_profile_config_yaml(profile)
    try:
        config_path = _ensure_gateway_config_file(profile)
    except ValueError as exc:
        return False, str(exc)
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"read failed: {exc}"

    lines = raw.splitlines(keepends=True)
    out: list[str] = []
    in_model_block = False
    wrote_default = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("model:"):
            if not in_model_block:
                in_model_block = True
                rest = stripped.split(":", 1)[1].strip().strip("'\"")
                if rest:
                    out.append("model:\n")
                    out.append(f"  default: {rest}\n")
                else:
                    out.append("model:\n")
            continue
        if in_model_block and stripped and not line.startswith((" ", "\t", "#")):
            in_model_block = False
        if in_model_block and stripped.startswith("default:"):
            indent = line[: len(line) - len(stripped)]
            out.append(f"{indent}default: {model_id}\n")
            wrote_default = True
            continue
        if in_model_block and stripped.startswith("- "):
            continue
        out.append(line)

    if not wrote_default:
        # No model block existed. Prepend one.
        if not raw.endswith("\n"):
            out.insert(0, "\n")
        out.insert(0, f"model:\n  default: {model_id}\n")

    try:
        config_path.write_text("".join(out), encoding="utf-8")
    except OSError as exc:
        return False, f"write failed: {exc}"
    return True, ""


def _set_profile_model_provider(profile: str, provider: str) -> tuple[bool, str]:
    _normalize_profile_config_yaml(profile)
    try:
        config_path = _ensure_gateway_config_file(profile)
    except ValueError as exc:
        return False, str(exc)
    provider = str(provider or "").strip().lower()
    if not provider:
        return False, "provider required"
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"read failed: {exc}"

    lines = raw.splitlines(keepends=True)
    out: list[str] = []
    in_model_block = False
    wrote_provider = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("model:"):
            if not in_model_block:
                in_model_block = True
                rest = stripped.split(":", 1)[1].strip().strip("'\"")
                if rest:
                    out.append("model:\n")
                    out.append(f"  default: {rest}\n")
                else:
                    out.append("model:\n")
            continue
        if in_model_block and stripped and not line.startswith((" ", "\t", "#")):
            if not wrote_provider:
                out.append(f"  provider: {provider}\n")
                wrote_provider = True
            in_model_block = False
        if in_model_block and stripped.startswith("provider:"):
            indent = line[: len(line) - len(stripped)]
            out.append(f"{indent}provider: {provider}\n")
            wrote_provider = True
            continue
        if in_model_block and stripped.startswith("- "):
            continue
        out.append(line)

    if not wrote_provider:
        if not raw.endswith("\n") and out:
            out.append("\n")
        inserted = False
        rebuilt: list[str] = []
        for line in out:
            rebuilt.append(line)
            if not inserted and line.lstrip().startswith("model:"):
                rebuilt.append(f"  provider: {provider}\n")
                inserted = True
        if not inserted:
            rebuilt.insert(0, f"model:\n  provider: {provider}\n")
        out = rebuilt

    try:
        config_path.write_text("".join(out), encoding="utf-8")
    except OSError as exc:
        return False, f"write failed: {exc}"
    return True, ""


def _parse_model_block_from_disk(profile: str) -> dict[str, Any]:
    """Parse the model surface from the profile's config.yaml:
    `model.default`, `model.provider`, etc. (siblings of `model:`) AND
    the top-level `fallback_providers:` block. Pure text scan — no
    pyyaml in the image.
    """
    config_path = _profile_config_path(profile)
    empty: dict[str, Any] = {
        "default": "",
        "provider": "",
        "base_url": "",
        "api_mode": "",
        "api_key": "",
        "providers": {},
        "fallback_chain": [],
    }
    if not config_path:
        return empty
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return empty

    out = dict(empty)
    in_model = False
    in_fallback = False
    fallback_indent = -1
    saw_top_model = False
    for raw in lines:
        stripped = raw.rstrip()
        if not stripped.strip() or stripped.lstrip().startswith("#"):
            continue
        indent = len(stripped) - len(stripped.lstrip())
        content = stripped.lstrip()

        # Track which top-level block we're in. The model block is the
        # `model:` section (indent 0 + `model:`); fallback_providers is
        # a SIBLING at indent 0, not nested under model.
        if indent == 0 and content.startswith("model:"):
            if saw_top_model:
                in_model = False
                continue
            saw_top_model = True
            in_model = True
            in_fallback = False
            continue
        if indent == 0:
            in_model = False

        # `model:` block: read its immediate sub-keys (default, provider,
        # base_url, api_mode). They sit at indent 2 with a `:`.
        if in_model and indent == 2 and ":" in content and not in_fallback:
            key, _, value = content.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key == "default":
                out["default"] = value
            elif key == "provider":
                out["provider"] = value
            elif key == "base_url":
                out["base_url"] = value
            elif key == "api_mode":
                out["api_mode"] = value
            elif key == "api_key":
                out["api_key"] = value
            continue

        # `fallback_providers:` is a top-level list. The key is at
        # indent 0; list items at indent 2 with `- `; sub-keys at
        # indent 4 (e.g. `model:` under the entry). An inline form like
        # `fallback_providers: []` or `{}` is empty; a bare
        # `fallback_providers:` (nothing after the colon) starts a
        # multi-line list and must NOT reset in_fallback.
        if indent == 0 and content.startswith("fallback_providers:"):
            in_fallback = True
            fallback_indent = indent
            after = content.split(":", 1)[1].strip()
            if after and (
                after in {"{}", "[]"}
                or (after.startswith("{") and after.endswith("}"))
                or (after.startswith("[") and after.endswith("]"))
            ):
                in_fallback = False
            continue

        if in_fallback and indent == fallback_indent + 2 and content.startswith("- "):
            # Start of a new fallback entry. First key may be inline.
            inline = content[2:].strip()
            entry: dict[str, str] = {}
            if ":" in inline:
                k, _, v = inline.partition(":")
                entry[k.strip()] = v.strip().strip('"').strip("'")
            out["fallback_chain"].append(entry)
            continue

        if in_fallback and indent > fallback_indent + 2 and ":" in content:
            k, _, v = content.partition(":")
            key = k.strip()
            val = v.strip().strip('"').strip("'")
            if out["fallback_chain"] and key in {"provider", "model", "base_url"}:
                out["fallback_chain"][-1][key] = val
            continue

        if in_fallback and indent <= fallback_indent:
            # Exited the fallback block.
            in_fallback = False
    return out


def _read_model_block(profile: str) -> dict[str, Any]:
    """Model surface for a profile. Runtime u-* slugs inherit default/chain from template."""
    raw = str(profile or "").strip()
    if not raw:
        return _parse_model_block_from_disk("")
    try:
        prof = resolve_hermes_profile(raw)
    except ValueError:
        return _parse_model_block_from_disk(raw)
    block = _parse_model_block_from_disk(prof)
    if not _is_runtime_profile_slug(prof):
        return block
    template = resolve_validated_profile(_runtime_template_slug(prof))
    tblock = _parse_model_block_from_disk(template)
    if str(tblock.get("default") or "").strip():
        block["default"] = tblock["default"]
    if tblock.get("fallback_chain"):
        block["fallback_chain"] = list(tblock["fallback_chain"])
    tpl_provider = str(tblock.get("provider") or "").strip()
    if tpl_provider:
        block["provider"] = tpl_provider
    return block


def _sync_runtime_model_from_template(runtime: str, template: str) -> None:
    """Keep per-user runtime Hermes config aligned with agent template model picks."""
    runtime_slug = safe_profile_slug(runtime)
    template_slug = resolve_validated_profile(template)
    if not _is_runtime_profile_slug(runtime_slug) or not profile_exists(runtime_slug):
        return
    tblock = _parse_model_block_from_disk(template_slug)
    default = str(tblock.get("default") or "").strip()
    if default:
        _set_profile_model(runtime_slug, default)
    chain = [e for e in (tblock.get("fallback_chain") or []) if isinstance(e, dict)]
    if chain:
        _write_fallback_chain(runtime_slug, chain)
    billing = _billing_provider_id_from_hermes_config(str(tblock.get("provider") or ""))
    if billing and default:
        _apply_model_for_billing_provider(runtime_slug, billing, default)


def _write_fallback_chain(profile: str, chain: list[dict[str, str]]) -> tuple[bool, str]:
    """Rewrite the `fallback_providers` block in config.yaml to match the
    supplied chain. Preserves all other keys, comments, and ordering.
    Strips ANY existing `fallback_providers:` blocks first — duplicates
    can occur when a profile was migrated multiple times or when the
    block was hand-edited — then inserts the new block at the natural
    position (right after the `model:` section, before the next
    top-level key).
    """
    _normalize_profile_config_yaml(profile)
    config_path = _profile_gateway_config_path(profile)
    if not config_path or not config_path.is_file():
        try:
            config_path = _ensure_gateway_config_file(profile)
        except ValueError as exc:
            return False, str(exc)
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"read failed: {exc}"

    lines = raw.splitlines(keepends=True)

    # Pass 1: drop every line that belongs to a `fallback_providers:`
    # block (anywhere it appears in the file). We also remember whether
    # a `model:` section existed so pass 2 can decide where to insert.
    out: list[str] = []
    in_fallback = False
    saw_model = False
    for line in lines:
        stripped = line.rstrip()
        if not stripped.strip():
            out.append(line)
            continue
        indent = len(stripped) - len(stripped.lstrip())
        content = stripped.lstrip()
        if indent == 0 and content.startswith("model:"):
            saw_model = True
            in_fallback = False
        if indent == 0 and content.startswith("fallback_providers:"):
            in_fallback = True
            continue
        if in_fallback:
            # A line is part of the block if it's indented more than 0
            # (sub-keys), starts with `- ` (list item at the same
            # indent as the key — also indent 0 here), or is otherwise
            # not a fresh top-level key. Top-level (indent 0) non-fb
            # keys end the block.
            if indent > 0:
                continue
            if content.startswith("- "):
                continue
            if not content.startswith("fallback_providers"):
                in_fallback = False
        if indent == 0:
            in_fallback = False
        out.append(line)

    # Pass 2: build the new block and find the right insertion point.
    new_block: list[str] = ["fallback_providers:\n"]
    for entry in chain:
        provider = str(entry.get("provider", "")).strip()
        model = str(entry.get("model", "")).strip()
        if not provider or not model:
            continue
        new_block.append(f"  - provider: {provider}\n")
        new_block.append(f"    model: {model}\n")

    if not saw_model:
        # No model section at all — create a minimal one with the
        # canonical primary plus the fallback chain.
        if out and not out[-1].endswith("\n"):
            out.append("\n")
        out.append("model:\n")
        out.append(f"  default: {HERMES_DEFAULT_PRIMARY}\n")
        out.extend(new_block)
    else:
        # Insert just after the last line of the `model:` block, which
        # is the first top-level key that follows it.
        insertion = len(out)
        in_model = False
        for idx, line in enumerate(out):
            stripped = line.rstrip()
            if not stripped.strip():
                continue
            indent = len(stripped) - len(stripped.lstrip())
            content = stripped.lstrip()
            if indent == 0 and content.startswith("model:"):
                in_model = True
                continue
            if indent == 0 and in_model:
                insertion = idx
                break
        out[insertion:insertion] = new_block

    try:
        config_path.write_text("".join(out), encoding="utf-8")
    except OSError as exc:
        return False, f"write failed: {exc}"
    _normalize_profile_config_yaml(profile)
    return True, ""


def hermes_models(
    profile: str = "",
    user_id: str = "",
    workspace_id: str = "",
    *,
    selection_only: bool = False,
) -> dict[str, Any]:
    """Return a profile's model surface: primary, fallback chain,
    and curated suggestions scoped to the active provider. The catalog
    is a hint list, not a hardcoded menu — the BFF accepts any
    `provider/model` id and the picker always lets the user type a
    custom one.
    """
    picker_llm = _user_llm_providers_for_picker(user_id) if user_id else set()
    connected = _connected_provider_names(user_id, workspace_id)
    has_llm = _user_llm_has_provider(user_id, workspace_id) if user_id else any(
        str(spec.get("category") or "") == "llm"
        and str(spec.get("id")).lower() in {n.lower() for n in connected}
        for spec in PROVIDER_CONNECT_CATALOG
    )
    connected_llm = picker_llm if user_id else {
        str(spec["id"]).lower()
        for spec in PROVIDER_CONNECT_CATALOG
        if str(spec.get("category") or "") == "llm"
        and str(spec.get("id")).lower() in {n.lower() for n in connected}
    }

    if selection_only:
        user_primary, user_chain = _read_user_llm_prefs(user_id) if user_id else ("", [])
        primary = user_primary or (HERMES_DEFAULT_PRIMARY if has_llm else "")
        billing = _resolve_billing_provider_for_model(primary, connected_llm) if primary else ""
        suggestions = _augment_model_suggestions(
            _suggestions_for_connected_llm_providers(connected_llm) if connected_llm else [],
            {
                "default": primary,
                "provider": billing or "",
                "base_url": "",
                "providers": {},
                "fallback_chain": user_chain,
            },
        )
        return {
            "ok": True,
            "profile": "",
            "primary": primary if has_llm else "",
            "provider": billing if has_llm else "",
            "base_url": "",
            "fallback_chain": user_chain if has_llm else [],
            "suggestions": suggestions,
            "connected_providers": sorted(picker_llm if user_id else connected),
            "has_llm_provider": has_llm,
            "billing_provider": billing if has_llm else "",
            "selection_only": True,
            "default_primary": HERMES_DEFAULT_PRIMARY,
            "default_fallback_chain": HERMES_DEFAULT_FALLBACK_CHAIN,
        }

    try:
        primary_profile = _resolve_models_profile(profile) if profile else _primary_profile()
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if primary_profile:
        _bootstrap_profile_providers(primary_profile, user_id, workspace_id)
    block = _read_model_block(primary_profile) if primary_profile else {
        "default": "", "provider": "", "base_url": "",
        "providers": {}, "fallback_chain": [],
    }
    active_provider = block.get("provider", "").strip()
    suggestions = _augment_model_suggestions(
        _suggestions_for_connected_llm_providers(connected_llm) if connected_llm else [],
        block,
    )
    if user_id and "openrouter" in connected_llm:
        resolved = _resolve_credential(user_id, workspace_id, "openrouter", user_only=True)
        secret = _credential_secret(resolved or {}, user_id) if resolved else ""
        live = openrouter_catalog.live_suggestions(secret, limit=30)
        if live:
            seen = {str(r.get("model") or "") for r in suggestions}
            suggestions = [
                {**row, "label": f"Live · {row.get('label', row.get('model', ''))}"}
                for row in live
                if str(row.get("model") or "") not in seen
            ] + suggestions
    seen_models: set[str] = set()
    deduped: list[dict[str, str]] = []
    for row in suggestions:
        mid = str(row.get("model") or "").strip()
        if not mid or mid in seen_models:
            continue
        seen_models.add(mid)
        deduped.append(row)
    suggestions = deduped
    primary_model = str(block.get("default") or "").strip()
    billing = _billing_provider_id_from_hermes_config(active_provider)
    if not billing and primary_model:
        billing = _resolve_billing_provider_for_model(primary_model, connected_llm) or ""
    if str(active_provider or "").lower() == "custom" and billing:
        display_provider = billing
    else:
        display_provider = active_provider
    return {
        "ok": True,
        "profile": primary_profile,
        "primary": primary_model if has_llm else "",
        "provider": display_provider if has_llm else "",
        "base_url": block.get("base_url", ""),
        "fallback_chain": block.get("fallback_chain", []) if has_llm else [],
        "suggestions": suggestions,
        "connected_providers": sorted(picker_llm if user_id else connected),
        "has_llm_provider": has_llm,
        "billing_provider": billing if has_llm else "",
        "default_primary": HERMES_DEFAULT_PRIMARY,
        "default_fallback_chain": HERMES_DEFAULT_FALLBACK_CHAIN,
    }


def hermes_apply_default_model_config() -> dict[str, Any]:
    """One-shot migration: every profile gets owl-alpha as the primary
    and the canonical 3-tier fallback chain. Idempotent — running it
    again produces the same state. Use after a fresh install or to
    recover from a profile whose config was hand-edited into a bad
    state.
    """
    profiles = _list_profiles()
    results: list[dict[str, str]] = []
    for profile in profiles:
        ok_model, err_model = _set_profile_model(profile, HERMES_DEFAULT_PRIMARY)
        ok_chain, err_chain = _write_fallback_chain(profile, HERMES_DEFAULT_FALLBACK_CHAIN)
        results.append({
            "profile": profile,
            "ok": "yes" if (ok_model and ok_chain) else "no",
            "error": err_model or err_chain or "",
        })
    return {
        "ok": True,
        "applied_to": [r["profile"] for r in results if r["ok"] == "yes"],
        "details": results,
    }


def hermes_model_set(
    profile: str,
    model_id: str,
    user_id: str = "",
    workspace_id: str = "",
    *,
    selection_only: bool = False,
) -> dict[str, Any]:
    """Set primary model and align Hermes provider routing to a connected billing provider."""
    user = str(user_id or "").strip()
    if selection_only:
        if not user:
            return {"ok": False, "error": "unauthorized"}
        connected = _user_llm_providers_for_picker(user)
        billing = _resolve_billing_provider_for_model(model_id, connected)
        if not billing and not _user_llm_has_provider(user, workspace_id):
            return {"ok": False, "error": "connect an LLM provider first"}
        _write_user_llm_prefs(user, primary=model_id)
        return {
            "ok": True,
            "profile": "",
            "model": model_id,
            "provider": billing or "",
            "billing_provider": billing or "",
            "selection_only": True,
        }
    target = profile or _primary_profile()
    if not target:
        return {"ok": False, "error": "no profile resolved"}
    if not model_id or " " in model_id or "\n" in model_id:
        return {"ok": False, "error": "invalid model id"}
    user = str(user_id or "").strip()
    ws = str(workspace_id or "").strip()
    connected = _user_llm_providers_for_picker(user) if user else set()
    billing = _resolve_billing_provider_for_model(model_id, connected)
    if billing:
        if not _apply_model_for_billing_provider(target, billing, model_id, user_id=user):
            return {"ok": False, "error": "model apply failed"}
    else:
        ok, err = _set_profile_model(target, model_id)
        if not ok:
            return {"ok": False, "error": err}
    tpl = safe_profile_slug(target)
    if user and not _is_runtime_profile_slug(tpl):
        runtime = _runtime_profile_slug(user, tpl)
        if _runtime_profile_on_disk(runtime):
            _sync_runtime_model_from_template(runtime, tpl)
    block = _read_model_block(target)
    return {
        "ok": True,
        "profile": target,
        "model": model_id,
        "provider": str(block.get("provider") or ""),
        "billing_provider": billing or _billing_provider_id_from_hermes_config(
            str(block.get("provider") or "")
        ),
    }


def hermes_fallback_chain_set(
    profile: str,
    chain: list[Any],
    *,
    selection_only: bool = False,
    user_id: str = "",
) -> dict[str, Any]:
    """Set the fallback chain for a profile. Each entry must have
    `provider` and `model` keys. Order matters: Hermes tries them in
    sequence when the primary fails.
    """
    normalized: list[dict[str, str]] = []
    for entry in chain:
        if not isinstance(entry, dict):
            continue
        provider = str(entry.get("provider", "")).strip()
        model = str(entry.get("model", "")).strip()
        if not provider or not model or " " in model or "\n" in model:
            return {
                "ok": False,
                "error": f"invalid fallback entry: provider={provider!r} model={model!r}",
            }
        normalized.append({"provider": provider, "model": model})
    if selection_only:
        user = str(user_id or "").strip()
        if not user:
            return {"ok": False, "error": "unauthorized"}
        _write_user_llm_prefs(user, fallback_chain=normalized)
        return {"ok": True, "profile": "", "fallback_chain": normalized, "selection_only": True}
    target = profile or _primary_profile()
    if not target:
        return {"ok": False, "error": "no profile resolved"}
    ok, err = _write_fallback_chain(target, normalized)
    if not ok:
        return {"ok": False, "error": err}
    user = str(user_id or "").strip()
    tpl = safe_profile_slug(target)
    if user and not _is_runtime_profile_slug(tpl):
        runtime = _runtime_profile_slug(user, tpl)
        if _runtime_profile_on_disk(runtime):
            _sync_runtime_model_from_template(runtime, tpl)
    return {"ok": True, "profile": target, "fallback_chain": normalized}


def hermes_usage() -> dict[str, Any]:
    """Token usage for the latest session of the active profile."""
    profile = _primary_profile()
    if not profile:
        return {"ok": False, "error": "no active profile"}

    session_id = _latest_session_id(profile)
    if not session_id:
        return {"ok": True, "profile": profile, "session": None}

    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    if not conn:
        return {"ok": False, "error": "state.db not reachable"}

    try:
        row = conn.execute(
            "SELECT title, model, message_count, started_at, ended_at, "
            "tool_call_count, input_tokens, output_tokens "
            "FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if not row:
            return {"ok": True, "profile": profile, "session": None}

        input_tokens = int(row["input_tokens"] or 0)
        output_tokens = int(row["output_tokens"] or 0)

        return {
            "ok": True,
            "profile": profile,
            "session": {
                "id": str(session_id)[:12] + "…",
                "title": row["title"] or "(untitled)",
                "model": row["model"] or "—",
                "message_count": int(row["message_count"] or 0),
                "tool_call_count": int(row["tool_call_count"] or 0),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "started_at": _iso_from_unix(row["started_at"]),
                "ended_at": _iso_from_unix(row["ended_at"]) if row["ended_at"] else None,
            },
        }
    except sqlite3.Error as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def hermes_gateway_exec(
    line: str,
    profile: str = "",
    user_id: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    """Execute a slash command through the Hermes CLI.

    Runs `hermes -p {profile} {cmd}` via Docker exec in the gateway
    container. This bypasses the streaming chat endpoint — slash commands
    are processed synchronously by the CLI's command handler and the
    output is returned immediately.
    """
    prof = resolve_validated_profile(profile) if profile else _primary_profile()
    if not prof:
        return {"ok": False, "error": "no active profile"}

    if not _user_may_access_runtime_profile(user_id, prof, workspace_id):
        return {"ok": False, "error": "profile_access_denied", "profile": prof}

    text = (line or "").strip()
    if not text:
        return {"ok": False, "error": "empty command"}

    # Parse the command: first token is the command name (with or without
    # leading /), rest is args.
    parts = text.split(None, 1)
    cmd_token = parts[0].lstrip("/")
    cmd_args = parts[1] if len(parts) > 1 else ""

    # Build the CLI command.
    cli_args = [cmd_token]
    if cmd_args:
        cli_args.extend(cmd_args.split())

    if _exec_targets_runtime_profile_secrets(cli_args, prof) or _exec_targets_runtime_profile_secrets(
        ["hermes", "-p", prof, *cli_args], prof,
    ):
        return {"ok": False, "error": "blocked_credential_path", "profile": prof}

    try:
        rc, output = _gateway_exec(prof, cli_args)
        return {
            "ok": rc == 0,
            "profile": prof,
            "command": cmd_token,
            "rc": rc,
            "output": output.strip() if output else "",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def profile_gateway_stop(profile: str, run_id: str) -> dict[str, Any]:
    """Stop a running agent via the Hermes /v1/runs/{run_id}/stop API."""
    prof = resolve_validated_profile(profile)
    lifecycle = ensure_profile_api(prof)
    port = _profile_api_port(prof)
    api_base = f"http://gateway:{port}"
    auth_headers = {
        "Authorization": f"Bearer {_profile_api_key(prof)}",
        "Content-Type": "application/json",
    }
    try:
        req = urllib.request.Request(
            f"{api_base}/v1/runs/{urllib.parse.quote(run_id, safe='')}/stop",
            data=b"{}",
            headers=auth_headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"ok": True, "profile": prof, "run_id": run_id, "status": "stopped", "detail": body[:500]}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "profile": prof, "run_id": run_id, "error": raw or f"stop failed: {exc.code}"}
    except Exception as exc:
        return {"ok": False, "profile": prof, "run_id": run_id, "error": str(exc)}


def profile_gateway_steer(profile: str, run_id: str, text: str) -> dict[str, Any]:
    """Steer a running agent: stop the current run and append a new input via /v1/runs."""
    prof = resolve_validated_profile(profile)
    # First stop the current run
    stop_result = profile_gateway_stop(prof, run_id)
    if not stop_result.get("ok"):
        return stop_result
    # Then submit the steered input as a new run
    lifecycle = ensure_profile_api(prof)
    port = _profile_api_port(prof)
    api_base = f"http://gateway:{port}"
    auth_headers = {
        "Authorization": f"Bearer {_profile_api_key(prof)}",
        "Content-Type": "application/json",
    }
    payload = json.dumps({"input": text}).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{api_base}/v1/runs",
            data=payload,
            headers=auth_headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
        new_run_id = str(body.get("run_id") or "").strip()
        return {"ok": True, "profile": prof, "run_id": new_run_id, "message": "steered", "detail": str(body)[:500]}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "profile": prof, "error": raw or f"steer failed: {exc.code}"}
    except Exception as exc:
        return {"ok": False, "profile": prof, "error": str(exc)}


def hermes_profile() -> dict[str, Any]:
    """Active profile info for the /profile dialog."""
    profile = _primary_profile()
    if not profile:
        return {"ok": False, "error": "no active profile"}

    soul_path = _profile_soul_path(profile)
    description = ""
    if soul_path.is_file():
        try:
            text = soul_path.read_text(encoding="utf-8", errors="replace")
            for raw in text.splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                description = line[:200]
                break
        except Exception:
            description = ""

    try:
        state = gateway_data(profile)
        gateway_running = bool(state.get("ok")) and str(state.get("state") or "").lower() == "running"
    except Exception:
        gateway_running = False

    session_id = _latest_session_id(profile)
    session_info = None
    if session_id:
        try:
            info = _session_info(profile, session_id)
            session_info = {
                "id": str(session_id)[:12] + "…",
                "title": info.get("session_title", ""),
                "message_count": info.get("message_count", 0),
                "model": info.get("model", ""),
            }
        except Exception:
            pass

    return {
        "ok": True,
        "profile": profile,
        "description": description,
        "gateway_running": gateway_running,
        "session": session_info,
    }


def _agent_db_row(template_slug: str, workspace_id: str = "") -> dict[str, Any]:
    template_slug = safe_profile_slug(str(template_slug or "").strip())
    if not template_slug:
        return {}
    conn = _workframe_db()
    try:
        if workspace_id:
            row = _lookup_agent_profile(conn, workspace_id, template_slug)
        else:
            row = conn.execute(
                """
                SELECT display_name, tagline, role, avatar_url
                FROM agent_profiles
                WHERE slug = ? AND deleted_at IS NULL
                ORDER BY is_native DESC, updated_at DESC
                LIMIT 1
                """,
                (template_slug,),
            ).fetchone()
        if not row:
            return {}
        return {
            "display_name": str(row["display_name"] or "").strip(),
            "tagline": str(row["tagline"] or "").strip() if "tagline" in row.keys() else "",
            "role": str(row["role"] or "").strip() if "role" in row.keys() else "",
            "avatar_url": str(row["avatar_url"] or "").strip() if "avatar_url" in row.keys() else "",
        }
    finally:
        conn.close()


def hermes_profile_detail(profile: str, workspace_id: str = "") -> dict[str, Any]:
    """Profile metadata + SOUL + model surface for a specific Hermes profile."""
    prof = resolve_validated_profile(profile)
    reg = _agent_registry_row(prof)
    db_row = _agent_db_row(prof, workspace_id)
    soul_text = _profile_soul_text(prof)
    block = _read_model_block(prof)
    try:
        state = gateway_data(prof)
        gateway_running = bool(state.get("ok")) and str(state.get("state") or "").lower() == "running"
        gateway_state = str(state.get("state") or "unknown")
    except Exception:
        gateway_running = False
        gateway_state = "unknown"
    row: dict[str, Any] = {
        "ok": True,
        "profile": prof,
        "display_name": str(
            db_row.get("display_name")
            or reg.get("display_name")
            or _profile_display_name(prof, workspace_id)
        ),
        "role": str(db_row.get("role") or reg.get("role") or _profile_role(prof)),
        "tagline": str(db_row.get("tagline") or reg.get("tagline") or ""),
        "description": str(reg.get("description") or ""),
        "soul": soul_text,
        "soul_exists": bool(soul_text),
        "gateway_running": gateway_running,
        "gateway_state": gateway_state,
        "model": block.get("default", ""),
        "provider": block.get("provider", ""),
        "is_native": _is_native_profile(prof),
    }
    avatar_url = str(db_row.get("avatar_url") or reg.get("avatar_url") or "").strip()
    if avatar_url:
        row["avatar_url"] = avatar_url
    if reg.get("avatar_id"):
        row["avatar_id"] = str(reg["avatar_id"])
    _resolve_avatar_fields(row)
    return row


def hermes_profile_update(profile: str, body: dict[str, Any]) -> dict[str, Any]:
    """Update Workframe agent registry metadata for a Hermes profile."""
    prof = resolve_validated_profile(profile)
    allowed = {"display_name", "role", "tagline", "description", "avatar_url", "avatar_id"}
    patch: dict[str, Any] = {}
    for key in allowed:
        if key not in body:
            continue
        value = body[key]
        patch[key] = str(value).strip() if value is not None else ""
    if "avatar_url" in patch:
        _validate_me_profile_updates({"avatar_url": patch["avatar_url"]})
    if not patch:
        return {"ok": False, "error": "no_allowed_fields"}
    _upsert_agent_registry_row(prof, patch)
    _sync_agent_profile_db(prof, patch)
    return {"ok": True, "profile": prof, **patch}


def profile_soul_get(profile: str) -> dict[str, Any]:
    prof = resolve_validated_profile(profile)
    text = _profile_soul_text(prof)
    path = _profile_soul_path(prof)
    return {
        "ok": True,
        "profile": prof,
        "soul": text,
        "path": str(path),
        "exists": path.is_file(),
    }


def profile_soul_set(profile: str, soul: str) -> dict[str, Any]:
    prof = resolve_validated_profile(profile)
    if _is_native_profile(prof):
        path = _profile_soul_path(prof)
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = soul if not soul or soul.endswith("\n") else f"{soul}\n"
        path.write_text(normalized, encoding="utf-8")
        return {"ok": True, "profile": prof, "bytes": len(normalized.encode("utf-8")), "target": "soul_file"}
    lookup = _runtime_template_slug(prof) if _is_runtime_profile_slug(prof) else prof
    _apply_profile_identity(lookup, user_soul=soul)
    return {"ok": True, "profile": prof, "bytes": len(soul.encode("utf-8")), "target": "user_soul_overlay"}


def hermes_debug() -> dict[str, Any]:
    """Debug info for the /debug dialog."""
    profile = _primary_profile()
    if not profile:
        return {"ok": False, "error": "no active profile"}

    import platform as plat
    import sys

    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    session_count = 0
    message_count = 0
    if conn:
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM sessions").fetchone()
            session_count = row["cnt"] if row else 0
            row = conn.execute("SELECT COUNT(*) as cnt FROM messages").fetchone()
            message_count = row["cnt"] if row else 0
        except Exception:
            pass
        finally:
            conn.close()

    return {
        "ok": True,
        "profile": profile,
        "python_version": sys.version,
        "platform": plat.platform(),
        "session_count": session_count,
        "message_count": message_count,
    }


def hermes_insights() -> dict[str, Any]:
    """Usage analytics for the /insights dialog."""
    profile = _primary_profile()
    if not profile:
        return {"ok": False, "error": "no active profile"}

    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    if not conn:
        return {"ok": False, "error": "state.db not reachable"}

    try:
        # Total tokens per day (last 7 days)
        rows = conn.execute(
            "SELECT DATE(started_at, 'unixepoch') as day, "
            "SUM(input_tokens) as input_tok, SUM(output_tokens) as output_tok, "
            "COUNT(*) as sessions "
            "FROM sessions "
            "WHERE started_at > strftime('%s', 'now', '-7 days') "
            "GROUP BY day ORDER BY day DESC"
        ).fetchall()

        daily = []
        for r in rows:
            daily.append({
                "day": r["day"] or "unknown",
                "input_tokens": int(r["input_tok"] or 0),
                "output_tokens": int(r["output_tok"] or 0),
                "sessions": int(r["sessions"] or 0),
            })

        # Model usage breakdown
        model_rows = conn.execute(
            "SELECT model, COUNT(*) as cnt, SUM(input_tokens) as input_tok "
            "FROM sessions GROUP BY model ORDER BY cnt DESC LIMIT 10"
        ).fetchall()

        models = []
        for r in model_rows:
            models.append({
                "model": r["model"] or "unknown",
                "sessions": int(r["cnt"] or 0),
                "input_tokens": int(r["input_tok"] or 0),
            })

        return {"ok": True, "profile": profile, "daily": daily, "models": models}
    except sqlite3.Error as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def hermes_gquota() -> dict[str, Any]:
    """Google Gemini quota info — stub until Google API is configured."""
    profile = _primary_profile()
    if not profile:
        return {"ok": False, "error": "no active profile"}
    return {
        "ok": True,
        "profile": profile,
        "configured": False,
        "message": "Google Gemini quota: not configured. Set GOOGLE_API_KEY in .env to enable.",
    }


def hermes_commands_catalog() -> dict[str, Any]:
    """Categorized slash command catalog for the Workframe composer palette.

    `wip` commands are an internal tracker — they exist in
    `HERMES_COMMANDS` so the team can see what's still to wire, but
    they aren't returned here. The UI never sees a half-implemented
    command; either it's wired end-to-end or it's invisible.
    """
    visible = [e for e in HERMES_COMMANDS if not e.get("wip", False)]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in visible:
        grouped.setdefault(entry["category"], []).append(
            {
                "name": entry["name"],
                "aliases": entry.get("aliases", []),
                "description": entry["description"],
                "args_hint": entry.get("args_hint", ""),
                "dispatch": entry["dispatch"],
            }
        )
    categories = [
        {"name": name, "commands": [
            (cmd["name"], cmd["description"]) for cmd in items
        ]}
        for name, items in grouped.items()
    ]
    return {
        "ok": True,
        "categories": categories,
        "entries": [
            {**entry, "wired": True}
            for entry in visible
        ],
    }


def hermes_commands_exec(line: str) -> dict[str, Any]:
    """Resolve a slash command line and return a dispatch decision for the UI.

    The BFF does not run client-side UI effects; it classifies the command
    and returns a hint. The UI executes the hint. For commands that need to
    round-trip the gateway (`/auth`, `/config`, etc.) the BFF returns a
    `gateway` dispatch and the UI calls a separate gateway proxy endpoint.

    Skills (`/skillname` where the skill is installed in Hermes) aren't in
    the static catalog. The BFF falls back to a skill-name lookup so the
    UI gets a clean "this is dispatchable" decision rather than "unknown
    command" for every installed skill.
    """
    raw = (line or "").strip()
    if not raw.startswith("/"):
        return {"ok": False, "error": "not a slash command", "line": raw}
    parts = raw.split(maxsplit=1)
    token = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    entry = _resolve_command(token)
    if entry is None:
        # Fallback: is this an installed skill? Skills route through
        # the gateway once the gateway hookup lands (Slice 2). For now
        # the UI gets a `gateway` dispatch so the user sees the same
        # "real command, gateway side not wired yet" hint as the other
        # gateway-class commands.
        skill_name = token.lstrip("/")
        if _is_known_skill(skill_name):
            return {
                "ok": True,
                "dispatched": "gateway",
                "command": token,
                "args": rest,
                "message": f"Skill: {skill_name} — gateway dispatch coming in Slice 2",
            }
        return {
            "ok": False,
            "error": f"unknown command: {token}",
            "suggestion": "/help",
        }
    dispatch = entry["dispatch"]
    if dispatch == "noop":
        return {
            "ok": True,
            "dispatched": "noop",
            "command": entry["name"],
            "args": rest,
            "message": "Not yet wired in Workframe — see M2 in the Workframe roadmap.",
        }
    if dispatch.startswith("client:"):
        return {
            "ok": True,
            "dispatched": "client",
            "command": entry["name"],
            "args": rest,
            "handler": dispatch.split(":", 1)[1],
        }
    if dispatch.startswith("bff:"):
        return {
            "ok": True,
            "dispatched": "bff",
            "command": entry["name"],
            "args": rest,
            "handler": dispatch.split(":", 1)[1],
        }
    return {
        "ok": True,
        "dispatched": "gateway",
        "command": entry["name"],
        "args": rest,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "WorkframeAPI/0.1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def do_OPTIONS(self) -> None:  # noqa: N802
        cors_origin = _cors_origin_for(self.headers)
        if not DEV_LOCAL_UNSAFE and not cors_origin:
            self.send_response(405)
            for name, value in self._security_headers():
                self.send_header(name, value)
            self.end_headers()
            return
        self.send_response(204)
        for name, value in self._security_headers():
            self.send_header(name, value)
        self.send_header("Access-Control-Allow-Origin", cors_origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        try:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            cors_origin = _cors_origin_for(self.headers)
            if cors_origin:
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            # Client disconnected before the response could be completed.
            return

    def _json(self, code: int, payload: Any, extra_headers: list[tuple[str, str]] | None = None) -> None:
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            for name, value in self._security_headers():
                self.send_header(name, value)
            cors_origin = _cors_origin_for(self.headers)
            if cors_origin:
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Vary", "Origin")
            if extra_headers:
                for name, value in extra_headers:
                    self.send_header(name, value)
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}

    # ------------------------------------------------------------------
    # Security headers (Sprint B: helmet equivalent)
    # ------------------------------------------------------------------
    def _security_headers(self) -> list[tuple[str, str]]:
        """Return security headers for every response."""
        headers = [
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Referrer-Policy", "strict-origin-when-cross-origin"),
        ]
        if SECURE_MODE:
            headers += [
                ("Strict-Transport-Security", "max-age=31536000; includeSubDomains"),
                ("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'"),
            ]
        return headers

    # ------------------------------------------------------------------
    # Audit logging (Sprint B: mutation audit)
    # ------------------------------------------------------------------
    def _log_audit(self, event_type: str, target_type: str = "", target_id: str = "",
                   summary: str = "", metadata: dict | None = None) -> None:
        """Append an audit event to the audit_events table."""
        try:
            uid = str(uuid.uuid4())
            user_id = str(getattr(self, "auth_user", "") or "")
            ip = self.client_address[0] if self.client_address else ""
            now_ts = int(time.time())
            conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
            conn.execute(
                """INSERT INTO audit_events
                   (id, user_id, event_type, target_type, target_id, summary, metadata, ip_address, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (uid, user_id, event_type, target_type, target_id, summary,
                 json.dumps(metadata or {}), ip, now_ts),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # audit logging must never block the response

    def _file_public(self, rel: str) -> None:
        safe = Path(rel.lstrip("/"))
        if ".." in safe.parts:
            self._json(403, {"error": "forbidden"})
            return
        path = PUBLIC_DIR / safe
        if not path.is_file():
            self._json(404, {"error": "not found"})
            return
        ctype = "text/html; charset=utf-8"
        if path.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        elif path.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        self._send(200, path.read_bytes(), ctype)

    def _handle_internal_llm_proxy(self, method: str, path: str) -> bool:
        if not path.startswith("/internal/llm/"):
            return False
        body: bytes | None = None
        if method.upper() in {"POST", "PUT", "PATCH"}:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length > 0 else b""
        return llm_proxy.handle_proxy_request(
            self,
            path,
            method,
            body,
            resolve_secret=_resolve_secret_for_lease,
        )

    def _handle_internal_action_proxy(self, method: str, path: str) -> bool:
        if not path.startswith("/internal/action/"):
            return False
        body: bytes | None = None
        if method.upper() in {"POST", "PUT", "PATCH"}:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length > 0 else b""
        return action_proxy.handle_proxy_request(
            self,
            path,
            method,
            body,
            resolve_secret=_resolve_secret_for_lease,
        )

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if self._handle_internal_llm_proxy("GET", path):
            return
        if self._handle_internal_action_proxy("GET", path):
            return

        # Auth middleware — returns 401 if session required and missing/invalid.
        # In DEV_LOCAL_UNSAFE mode this is a no-op.
        if not _auth_check(self):
            return self._json(401, {"ok": False, "error": "no_session"})

        if SECURE_MODE:
            if not _secure_host_origin_ok(self.command, path, self.headers):
                if not _validate_host(self.headers):
                    return self._json(403, {"error": "invalid host"})
                return self._json(403, {"error": "invalid origin"})

        try:
            # Serve static files and UI
            if path in ("", "/") or not path.startswith("/api/") and not path.startswith("/assets/") and not path.startswith("/static/"):
                return self._file_public("index.html")
            if path.startswith("/assets/"):
                return self._file_public(path.lstrip("/"))
            if path == "/api/health":
                vault_stat = credential_vault.vault_status()
                return self._json(
                    200,
                    {
                        "ok": True,
                        "version": VERSION,
                        "mode": "dev_unsafe" if DEV_LOCAL_UNSAFE else "secure",
                        "secure_mode": SECURE_MODE,
                        "deployment_mode": DEPLOYMENT_MODE,
                        "admin_updates_enabled": os.environ.get("WORKFRAME_ENABLE_ADMIN_UPDATES") == "1",
                        "docker_sock_on_api": Path("/var/run/docker.sock").exists(),
                        "proxy_token_configured": internal_proxy_auth.proxy_token_configured(),
                        "vault_sealed": vault_stat.get("sealed"),
                        "vault_envelope": not vault_stat.get("sealed"),
                        "install_window_open": _install_window_open(),
                        "workframe_e2e": os.environ.get("WORKFRAME_E2E") == "1",
                        "dev_local_unsafe": DEV_LOCAL_UNSAFE,
                    },
                )
            if path == "/api/admin/vault/status":
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                return self._json(200, {"ok": True, **credential_vault.vault_status()})
            if path == "/api/doctor/agent-dm-runtimes":
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                return self._json(200, doctor_audit_agent_dm_runtimes())
            if path == "/api/admin/updates":
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                desktop_version = str((qs.get("desktop_version") or [""])[0] or "").strip()
                try:
                    return self._json(
                        200,
                        stack_updates.updates_available(
                            desktop_version=desktop_version,
                            hermes_agent_version=_hermes_agent_version(),
                        ),
                    )
                except Exception as exc:  # noqa: BLE001
                    return self._json(500, {"ok": False, "error": str(exc)})
            if path == "/api/auth/hermes-dashboard-gate":
                status = _hermes_dashboard_gate_status(self)
                if status == 204:
                    self.send_response(204)
                    self.end_headers()
                    return
                return self._json(403, {"ok": False, "error": "dashboard_forbidden"})
            if path == "/api/setup/status":
                # Public endpoint: check if default workspace has agents (setup complete?)
                try:
                    db = _workframe_db()
                    ws = db.execute("SELECT id FROM workspaces WHERE slug='default' AND deleted_at IS NULL").fetchone()
                    if not ws:
                        db.close()
                        return self._json(200, {"setup_complete": False})
                    agents = db.execute("SELECT COUNT(*) AS c FROM agent_profiles WHERE workspace_id = ? AND deleted_at IS NULL", (ws["id"],)).fetchone()
                    db.close()
                    return self._json(200, {"setup_complete": bool(agents and agents["c"] > 0)})
                except Exception:
                    return self._json(200, {"setup_complete": False})
            if path == "/api/install/status":
                if install_api.install_window_open(str(_workframe_db_path())):
                    try:
                        _ensure_native_hermes_profile()
                    except Exception:
                        pass
                payload = install_api.install_status_payload(
                    DEPLOYMENT_MODE,
                    SECURE_MODE,
                    DEV_LOCAL_UNSAFE,
                    str(_workframe_db_path()),
                )
                return self._json(200, payload)
            if path == "/api/public/site-meta":
                return self._json(200, _public_site_meta_payload())
            if path == "/api/public/link-preview":
                meta = _public_site_meta_payload()
                html = site_meta.link_preview_html(meta).encode("utf-8")
                self._send(200, html, "text/html; charset=utf-8")
                return
            if path == "/api/public/manifest.webmanifest":
                meta = _public_site_meta_payload()
                body = json.dumps(site_meta.manifest_payload(meta), indent=2).encode("utf-8")
                self._send(200, body, "application/manifest+json; charset=utf-8")
                return
            branding_match = re.fullmatch(r"/api/public/branding/(og|favicon)", path)
            if branding_match:
                asset = site_meta.branding_asset_bytes(branding_match.group(1))
                if not asset:
                    return self._json(404, {"ok": False, "error": "not_found"})
                data, ctype = asset
                self._send(200, data, ctype)
                return
            if path == "/api/install/stack":
                if not _install_window_open() and not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                return self._json(200, {"ok": True, **stack_config.public_stack_payload()})
            if path == "/api/install/url/test":
                if not _install_window_open():
                    return self._json(403, {"ok": False, "error": "install_closed"})
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                url = (qs.get("url") or [""])[0] or stack_config.get_stack_config().get("app_base_url") or ""
                return self._json(200, install_api.url_test(str(url)))
            if path == "/api/install/publish-hints":
                if not _install_window_open():
                    return self._json(403, {"ok": False, "error": "install_closed"})
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                url = (qs.get("url") or [""])[0] or stack_config.get_stack_config().get("app_base_url") or ""
                return self._json(200, install_api.publish_hints_payload(str(url)))
            if path == "/api/auth/google/callback":
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                code = (qs.get("code") or [""])[0]
                state = (qs.get("state") or [""])[0]
                if not code or not state:
                    return self._json(400, {"ok": False, "error": "missing code or state"})
                try:
                    profile = google_auth.exchange_google_code(code, state)
                    invite_token = str(profile.get("invite_token") or "")
                    allowed, deny_meta = _email_allowed_to_authenticate(profile["email"])
                    if not allowed and not _invite_token_allows_email(invite_token, profile["email"]):
                        self._log_audit(
                            "login_denied_private",
                            "user",
                            profile["email"],
                            str(deny_meta.get("error") or ""),
                        )
                        return self._json(403, {"ok": False, **deny_meta})
                    result = _zk.create_session_for_email(profile["email"])
                    self.auth_user = result["user_id"]
                    self._ensure_user(
                        result["user_id"],
                        profile.get("display_name") or profile["email"],
                        profile["email"],
                    )
                    invite_token = str(profile.get("invite_token") or "")
                    use_secure = _session_cookie_secure()
                    cookie_val = _zk.session_cookie_value(result["session_id"], secure=use_secure)
                    redirect_to = f"{APP_BASE_URL.rstrip('/')}/onboarding"
                    if invite_token:
                        redirect_to = (
                            f"{APP_BASE_URL.rstrip('/')}/?invite_token="
                            f"{urllib.parse.quote(invite_token)}&email={urllib.parse.quote(profile['email'])}"
                        )
                    self.send_response(302)
                    self.send_header("Location", redirect_to)
                    self.send_header("Set-Cookie", cookie_val)
                    cors_origin = _cors_origin_for(self.headers)
                    if cors_origin:
                        self.send_header("Access-Control-Allow-Origin", cors_origin)
                        self.send_header("Vary", "Origin")
                    self.end_headers()
                    return
                except Exception as exc:
                    return self._json(401, {"ok": False, "error": str(exc)})
            if path == "/api/me":
                # zk-auth compatible profile endpoint (GET)
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                payload = _session_profile_payload(user_id)
                if not payload:
                    return self._json(404, {"ok": False, "error": "user_not_found"})
                return self._json(200, payload)

            if path == "/api/me/onboarding":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                return self._json(200, _onboarding_payload(user_id))

            if path == "/api/me/credentials":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                try:
                    conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
                    conn.row_factory = sqlite3.Row
                    rows = conn.execute(
                        """SELECT id, workspace_id, user_id, agent_profile_id, provider, credential_type,
                               credential_ref, label, is_active, created_at, updated_at
                           FROM credential_bindings
                           WHERE user_id = ? AND deleted_at IS NULL
                           ORDER BY updated_at DESC, created_at DESC""",
                        (user_id,),
                    ).fetchall()
                    conn.close()
                except sqlite3.Error as exc:
                    return self._json(500, {"ok": False, "error": f"db_error: {exc}"})
                return self._json(200, {"ok": True, "credentials": [dict(row) for row in rows]})

            if path == "/api/me/providers":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                workspace_id = qs.get("workspace_id", [""])[0]
                return self._json(200, list_user_providers(user_id, workspace_id))

            if path.startswith("/api/me/oauth/") and path.endswith("/status"):
                parts = path.strip("/").split("/")
                if len(parts) == 5 and parts[2] == "oauth" and parts[4] == "status":
                    user_id = str(getattr(self, "auth_user", "") or "")
                    if not user_id:
                        return self._json(401, {"ok": False, "error": "no_session"})
                    provider_id = parts[3]
                    session_id = str(qs.get("session_id", [""])[0] or "").strip()
                    if not session_id:
                        return self._json(400, {"ok": False, "error": "session_id required"})
                    return self._json(200, device_oauth_status(user_id, provider_id, session_id))

            if path == "/api/oauth/github/callback":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                code = qs.get("code", [""])[0]
                state = qs.get("state", [""])[0]
                result = _complete_github_oauth(user_id, str(code or ""), str(state or ""))
                status = "ok" if result.get("ok") else "error"
                message = urllib.parse.quote(str(result.get("error") or "connected"))
                location = f"{APP_BASE_URL.rstrip('/')}/?provider_connect=github&status={status}&message={message}"
                self.send_response(302)
                self.send_header("Location", location)
                self.end_headers()
                return

            if path == "/api/oauth/discord/callback":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                code = qs.get("code", [""])[0]
                state = qs.get("state", [""])[0]
                result = _complete_discord_oauth(user_id, str(code or ""), str(state or ""))
                status = "ok" if result.get("ok") else "error"
                message = urllib.parse.quote(str(result.get("error") or "connected"))
                location = f"{APP_BASE_URL.rstrip('/')}/?provider_connect=discord&status={status}&message={message}"
                self.send_response(302)
                self.send_header("Location", location)
                self.end_headers()
                return

            if path == "/api/oauth/stripe/callback":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                code = qs.get("code", [""])[0]
                state = qs.get("state", [""])[0]
                result = _complete_stripe_oauth(user_id, str(code or ""), str(state or ""))
                status = "ok" if result.get("ok") else "error"
                message = urllib.parse.quote(str(result.get("error") or "connected"))
                location = f"{APP_BASE_URL.rstrip('/')}/?provider_connect=stripe&status={status}&message={message}"
                self.send_response(302)
                self.send_header("Location", location)
                self.end_headers()
                return

            workspace_get_match = re.fullmatch(r"/api/workspace/([^/]+)", path)
            if workspace_get_match and self.command == "GET":
                user_id = str(getattr(self, "auth_user", "") or "")
                ws_id = _resolve_wid(workspace_get_match.group(1))
                if not ws_id:
                    return self._json(404, {"ok": False, "error": "workspace_not_found"})
                return self._json(*_get_workspace(ws_id, user_id))

            # --- Sprint F: Room APIs (GET) ---
            if path.startswith("/api/workspace/") and path.endswith("/rooms") and self.command == "GET":
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    include_members = qs.get("include_members", [""])[0].lower() in {"1", "true", "yes"}
                    return self._json(*_list_rooms(ws_id, include_members=include_members))

            # --- Sprint F: Room delete (DELETE /api/rooms/:id) ---
            if re.fullmatch(r"/api/rooms/[^/]+", path) and self.command == "DELETE":
                rid = path.strip("/").split("/")[-1]
                try:
                    db = _workframe_db()
                    cur = db.execute("UPDATE rooms SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL", (str(int(time.time())), rid))
                    db.commit()
                    affected = cur.rowcount
                    db.close()
                except Exception:
                    return self._json(500, {"ok": False, "error": "delete_failed"})
                if not affected:
                    return self._json(404, {"ok": False, "error": "room_not_found"})
                self._log_audit("room_deleted", "room", rid, f"room={rid}")
                return self._json({"ok": True, "room_id": rid, "status": "deleted"})

            if re.fullmatch(r"/api/rooms/[^/]+", path):
                rid = path.strip("/").split("/")[-1]
                return self._json(*_get_room(rid))

            if path.startswith("/api/rooms/") and path.endswith("/members"):
                rid = path.strip("/").split("/")[-2]
                viewer_id = str(getattr(self, "auth_user", "") or "")
                try:
                    conn = _workframe_db()
                    conn.row_factory = sqlite3.Row
                    if not _user_can_access_room(conn, rid, viewer_id):
                        conn.close()
                        return self._json(403, {"ok": False, "error": "forbidden"})
                    members = conn.execute(
                        "SELECT * FROM room_memberships WHERE room_id = ? AND deleted_at IS NULL",
                        (rid,),
                    ).fetchall()
                    payload = _enrich_room_members(conn, [dict(m) for m in members])
                    conn.close()
                except Exception:
                    payload = []
                return self._json(200, {"ok": True, "room_id": rid, "members": payload})

            if path.startswith("/api/rooms/") and path.endswith("/live"):
                rid = path.strip("/").split("/")[-2]
                user_id = str(getattr(self, "auth_user", "") or "")
                try:
                    conn = _workframe_db()
                    if not _user_can_access_room(conn, rid, user_id):
                        conn.close()
                        return self._json(403, {"ok": False, "error": "forbidden"})
                    conn.close()
                except Exception:
                    return self._json(500, {"ok": False, "error": "db_error"})
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                cors_origin = _cors_origin_for(self.headers)
                if cors_origin:
                    self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Vary", "Origin")
                self.end_headers()
                sub = _room_live_subscribe(rid)
                try:
                    for turn in _room_live_active_for_room(rid):
                        payload = json.dumps(turn)
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    while True:
                        try:
                            line = sub.get(timeout=15)
                            self.wfile.write(f"data: {line}\n\n".encode("utf-8"))
                            self.wfile.flush()
                        except queue.Empty:
                            heartbeat = json.dumps(
                                {"type": "heartbeat", "room_id": rid, "ts": int(time.time())}
                            )
                            self.wfile.write(f"data: {heartbeat}\n\n".encode("utf-8"))
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    _room_live_unsubscribe(rid, sub)
                return

            if path.startswith("/api/rooms/") and path.endswith("/activity"):
                rid = path.strip("/").split("/")[-2]
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                try:
                    activity = room_activity_data(rid, user_id)
                except ValueError as exc:
                    return self._json(400, {"ok": False, "error": str(exc)})
                return self._json(200, {"ok": True, "room_id": rid, "activity": activity})

            if path.startswith("/api/workspace/") and path.endswith("/activity"):
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    wid = _resolve_wid(parts[2])
                    user_id = str(getattr(self, "auth_user", "") or "")
                    if not user_id:
                        return self._json(401, {"ok": False, "error": "no_session"})
                    if not wid:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    try:
                        activity = workspace_activity_data(wid, user_id)
                    except ValueError as exc:
                        return self._json(400, {"ok": False, "error": str(exc)})
                    return self._json(200, {"ok": True, "workspace_id": wid, "activity": activity})

            if path.startswith("/api/workspace/") and path.endswith("/kanban/tasks"):
                parts = path.strip("/").split("/")
                if len(parts) == 5:
                    wid = _resolve_wid(parts[2])
                    user_id = str(getattr(self, "auth_user", "") or "")
                    if not user_id:
                        return self._json(401, {"ok": False, "error": "no_session"})
                    if not wid:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    try:
                        payload = kanban_proxy_list_tasks(wid, user_id)
                    except PermissionError as exc:
                        return self._json(403, {"ok": False, "error": str(exc)})
                    return self._json(200, payload)

            if path.startswith("/api/workspace/") and path.endswith("/delegation-grants"):
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    wid = _resolve_wid(parts[2])
                    user_id = str(getattr(self, "auth_user", "") or "")
                    if not user_id:
                        return self._json(401, {"ok": False, "error": "no_session"})
                    if not wid:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    try:
                        payload = list_delegation_grants(wid, user_id)
                    except PermissionError as exc:
                        return self._json(403, {"ok": False, "error": str(exc)})
                    return self._json(200, payload)

            if path == "/api/me/cohort":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                workspace_id = str(qs.get("workspace_id", [""])[0] or "").strip()
                if not workspace_id:
                    return self._json(400, {"ok": False, "error": "workspace_id_required"})
                ws_id = _resolve_wid(workspace_id) or workspace_id
                if not _user_is_workspace_member(user_id, ws_id):
                    return self._json(403, {"ok": False, "error": "forbidden"})
                cohort = ensure_user_agent_cohort(user_id, ws_id)
                return self._json(
                    200,
                    {
                        "ok": True,
                        "workspace_id": ws_id,
                        "user_id": user_id,
                        "cohort": cohort,
                    },
                )

            if path.startswith("/api/rooms/") and path.endswith("/sessions"):
                rid = path.strip("/").split("/")[-2]
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                try:
                    payload = list_room_sessions(rid, user_id)
                except ValueError as exc:
                    err = str(exc)
                    if "not_found" in err:
                        return self._json(404, {"ok": False, "error": err})
                    if "denied" in err or "forbidden" in err:
                        return self._json(403, {"ok": False, "error": err})
                    return self._json(400, {"ok": False, "error": err})
                return self._json(200, payload)

            # --- Sprint H: Invites (GET) ---
            if path.startswith("/api/workspace/") and path.endswith("/invites"):
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    wid = parts[2]
                    ws_id = _resolve_wid(wid)
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    try:
                        conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
                        conn.row_factory = sqlite3.Row
                        invites = conn.execute(
                            "SELECT id, workspace_id, email, role, invited_by_user_id, expires_at, created_at, accepted_at, deleted_at FROM workspace_invites WHERE workspace_id = ? AND deleted_at IS NULL ORDER BY created_at DESC",
                            (ws_id,)).fetchall()
                        conn.close()
                    except Exception:
                        invites = []
                    return self._json(200, {"ok": True, "invites": [dict(i) for i in invites]})

            if path.startswith("/api/invites/"):
                parts = path.strip("/").split("/")
                if len(parts) == 3:
                    token = parts[2]
                    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
                    try:
                        conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
                        conn.row_factory = sqlite3.Row
                        inv = conn.execute(
                            "SELECT id, workspace_id, email, role, invited_by_user_id, expires_at, created_at, accepted_at, deleted_at FROM workspace_invites WHERE token_hash = ? AND deleted_at IS NULL",
                            (token_hash,)).fetchone()
                        conn.close()
                    except Exception:
                        inv = None
                    if not inv:
                        return self._json(404, {"ok": False, "error": "invite_not_found"})
                    return self._json(200, {"ok": True, "invite": dict(inv)})

            # --- Sprint H: Workspace members (GET only, POST/PATCH/DELETE in do_POST) ---
            if path.startswith("/api/workspace/") and path.endswith("/members"):
                parts = path.strip("/").split("/")
                if len(parts) == 4 and self.command == "GET":
                    wid = parts[2]
                    ws_id = _resolve_wid(wid)
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    return self._json(*_list_workspace_members(ws_id, self))

            # --- Sprint J: User credentials (GET) ---
            if path == "/api/user/credentials":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    if DEV_LOCAL_UNSAFE:
                        user_id = "dev"
                    else:
                        return self._json(401, {"ok": False, "error": "no_authenticated_user"})
                try:
                    conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
                    conn.row_factory = sqlite3.Row
                    creds = conn.execute(
                        "SELECT id, workspace_id, user_id, agent_profile_id, provider, credential_type, label, is_active, created_at, updated_at FROM credential_bindings WHERE user_id = ? AND deleted_at IS NULL ORDER BY created_at DESC",
                        (user_id,)).fetchall()
                    conn.close()
                except Exception:
                    creds = []
                return self._json(200, {"ok": True, "credentials": [dict(c) for c in creds]})

            # --- Sprint I: Memory (GET) ---
            if path.startswith("/api/workspace/") and path.endswith("/memory"):
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    wid = parts[2]
                    ws_id = _resolve_wid(wid)
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    try:
                        conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
                        conn.row_factory = sqlite3.Row
                        items = conn.execute(
                            "SELECT * FROM memory_items WHERE workspace_id = ? AND deleted_at IS NULL ORDER BY created_at DESC",
                            (ws_id,)).fetchall()
                        conn.close()
                    except Exception:
                        items = []
                    return self._json(200, {"ok": True, "items": [dict(i) for i in items]})

            # --- Sprint K: Budgets + Grants (GET) ---
            if path.startswith("/api/workspace/") and path.endswith("/budget"):
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    try:
                        conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
                        conn.row_factory = sqlite3.Row
                        policies = conn.execute(
                            "SELECT * FROM budget_policies WHERE workspace_id = ? ORDER BY created_at DESC",
                            (ws_id,)).fetchall()
                        conn.close()
                    except Exception:
                        policies = []
                    return self._json(200, {"ok": True, "budget_policies": [dict(p) for p in policies]})

            if path.startswith("/api/workspace/") and path.endswith("/grants"):
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    try:
                        conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
                        conn.row_factory = sqlite3.Row
                        grants = conn.execute(
                            "SELECT cg.*, cb.provider AS binding_provider FROM credential_grants cg LEFT JOIN credential_bindings cb ON cb.id = cg.credential_binding_id WHERE cb.workspace_id = ? OR cg.grantee_id = ? ORDER BY cg.created_at DESC",
                            (ws_id, ws_id)).fetchall()
                        conn.close()
                    except Exception:
                        grants = []
                    return self._json(200, {"ok": True, "grants": [dict(g) for g in grants]})

            # --- Sprint F: Message APIs (GET) ---
            if path.startswith("/api/rooms/") and path.endswith("/messages"):
                slug_or_id = path.strip("/").split("/")[-2]
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                limit = int(qs.get("limit", ["50"])[0])
                offset = int(qs.get("offset", ["0"])[0])
                try:
                    conn = _workframe_db()
                    room = conn.execute(
                        "SELECT id FROM rooms WHERE (id = ? OR slug = ?) AND deleted_at IS NULL",
                        (slug_or_id, slug_or_id),
                    ).fetchone()
                    if not room:
                        conn.close()
                        return self._json(404, {"error": "room_not_found"})
                    rid = room["id"]
                    if not _user_can_access_room(conn, rid, user_id):
                        conn.close()
                        return self._json(403, {"ok": False, "error": "forbidden"})
                    messages = conn.execute(
                        """
                        SELECT * FROM (
                            SELECT * FROM messages
                            WHERE room_id = ? AND deleted_at IS NULL
                            ORDER BY created_at DESC
                            LIMIT ? OFFSET ?
                        ) AS recent
                        ORDER BY created_at ASC
                        """,
                        (rid, limit, offset),
                    ).fetchall()
                    total = conn.execute(
                        "SELECT COUNT(*) FROM messages WHERE room_id = ? AND deleted_at IS NULL",
                        (rid,),
                    ).fetchone()[0]
                    payload = _enrich_room_messages(conn, messages)
                    conn.close()
                except Exception:
                    messages = []
                    total = 0
                    payload = []
                return self._json(200, {"ok": True, "messages": payload, "total": total, "limit": limit, "offset": offset})

            # --- Sprint F: Workspace event stream (SSE) ---
            if path.startswith("/api/workspace/") and path.endswith("/events"):
                parts = path.strip("/").split("/")
                if len(parts) >= 4:
                    wid = parts[2]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    cors_origin = _cors_origin_for(self.headers)
                    if cors_origin:
                        self.send_header("Access-Control-Allow-Origin", cors_origin)
                    self.send_header("Vary", "Origin")
                    self.end_headers()
                    last_revision = ""
                    last_heartbeat = time.time()
                    try:
                        while True:
                            try:
                                conn = _workframe_db()
                                revision = _workspace_sse_revision(conn, wid)
                                conn.close()
                            except Exception:
                                revision = "error"
                            if revision != last_revision:
                                payload = json.dumps(_workspace_event_payload(wid, revision))
                                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                                self.wfile.flush()
                                last_revision = revision
                                last_heartbeat = time.time()
                            elif time.time() - last_heartbeat >= 15:
                                heartbeat = json.dumps({"type": "heartbeat", "workspace_id": wid, "ts": int(time.time())})
                                self.wfile.write(f"data: {heartbeat}\n\n".encode("utf-8"))
                                self.wfile.flush()
                                last_heartbeat = time.time()
                            time.sleep(1)
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        pass
                    return

            if path == "/api/meta":
                return self._json(200, workframe_meta())
            if path == "/api/agents":
                return self._json(200, workframe_agents())
            if path == "/api/snapshot":
                return self._json(200, build_snapshot())
            if path == "/api/activity/detail":
                profile = qs.get("profile", [""])[0].strip()
                tool_call_id = qs.get("tool_call_id", [""])[0].strip()
                session_id = qs.get("session_id", [""])[0].strip()
                message_id = qs.get("message_id", [""])[0].strip()
                return self._json(200, activity_detail(profile, tool_call_id, session_id, message_id))
            if path == "/api/board":
                return self._json(200, board_list())
            if path == "/api/content":
                return self._json(200, content_list())
            if path == "/api/content/get":
                rel = qs.get("path", [""])[0]
                reason = _workspace_protected_reason(rel)
                if reason:
                    return self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
                fp = _safe_content_path(rel)
                if not fp or not fp.is_file():
                    return self._json(404, {"error": "not found"})
                text = fp.read_text(encoding="utf-8", errors="replace")
                return self._json(200, {"path": rel, "content": text, "text": text})
            if path == "/api/files/tree":
                return self._json(200, {"root": files_tree()})
            if path == "/api/files/list":
                rel = qs.get("path", [""])[0]
                reason = _workspace_protected_reason(rel)
                if reason:
                    return self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
                return self._json(200, files_list(rel))
            if path == "/api/files/state":
                return self._json(200, workspace_state())
            if path == "/api/files/read":
                rel = qs.get("path", [""])[0]
                reason = _workspace_protected_reason(rel)
                if reason:
                    return self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
                return self._json(200, file_read(rel))
            if path == "/api/files/raw":
                rel = qs.get("path", [""])[0]
                reason = _workspace_protected_reason(rel)
                if reason:
                    return self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
                try:
                    data, mime = file_raw(rel)
                except ValueError:
                    return self._json(404, {"error": "not found"})
                return self._send(200, data, mime)
            if path == "/api/routes":
                return self._json(200, load_routes())
            if path == "/api/chat/messages":
                profile = resolve_hermes_profile(qs.get("profile", [""])[0] or _primary_profile())
                session = qs.get("session", [""])[0]
                source_id = qs.get("source", ["ui"])[0]
                return self._json(200, chat_messages(profile, session, source_id))
            if path == "/api/chat/session":
                profile = resolve_hermes_profile(qs.get("profile", [""])[0] or _primary_profile())
                session = qs.get("session", [""])[0]
                source_id = qs.get("source", ["ui"])[0]
                return self._json(200, chat_session(profile, session, source_id))
            if path == "/api/chat/resolve":
                profile = resolve_validated_profile(qs.get("profile", [""])[0] or _primary_profile())
                source_id = qs.get("source", ["ui"])[0]
                client_id = qs.get("client", ["default"])[0]
                return self._json(
                    200,
                    chat_resolve({"profile": profile, "source_id": source_id, "client_id": client_id}),
                )
            if path == "/api/chat/bootstrap":
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                profile = resolve_validated_profile(qs.get("profile", [""])[0] or _primary_profile())
                persistent = qs.get("persistent", [""])[0]
                source_id = qs.get("source", ["ui"])[0]
                return self._json(200, chat_bootstrap(profile, persistent, source_id))
            if path == "/api/hermes/bootstrap":
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                return self._json(200, hermes_bootstrap())
            if path == "/api/hermes/skills":
                return self._json(200, {"skills": hermes_skills()})
            if path == "/api/hermes/commands":
                return self._json(200, hermes_commands_catalog())
            if path == "/api/hermes/usage":
                return self._json(200, hermes_usage())
            if path == "/api/hermes/profile":
                return self._json(200, hermes_profile())
            if path == "/api/hermes/debug":
                return self._json(200, hermes_debug())
            if path == "/api/hermes/insights":
                return self._json(200, hermes_insights())
            if path == "/api/hermes/gquota":
                return self._json(200, hermes_gquota())
            if path == "/api/hermes/models":
                profile = qs.get("profile", [""])[0]
                user_id = str(getattr(self, "auth_user", "") or "")
                workspace_id = qs.get("workspace_id", [""])[0]
                selection_only = qs.get("selection_only", ["0"])[0] in {"1", "true", "yes"}
                payload = hermes_models(profile, user_id, workspace_id, selection_only=selection_only)
                status = 200 if payload.get("ok", True) else 400
                return self._json(status, payload)
            if path == "/api/hermes/profiles/status":
                profile = resolve_validated_profile(qs.get("profile", [""])[0] or _primary_profile())
                if SUPERVISOR_URL:
                    return self._json(
                        *_supervisor_request(
                            "GET",
                            f"/v1/profile.status?profile={urllib.parse.quote(profile, safe='')}",
                            timeout=10.0,
                        )
                    )
                return self._json(200, profile_gateway_lifecycle(profile, "status"))
            profile_soul_match = re.fullmatch(r"/api/hermes/profiles/([^/]+)/soul", path)
            if profile_soul_match:
                profile = resolve_validated_profile(profile_soul_match.group(1))
                return self._json(200, profile_soul_get(profile))
            profile_detail_match = re.fullmatch(r"/api/hermes/profiles/([^/]+)", path)
            if profile_detail_match and profile_detail_match.group(1) not in {
                "status",
                "create",
                "start",
                "stop",
                "delete",
                "disable",
            }:
                profile = resolve_validated_profile(profile_detail_match.group(1))
                ws_id = ""
                user_id = str(getattr(self, "auth_user", "") or "")
                if user_id:
                    try:
                        conn = _workframe_db()
                        row = conn.execute(
                            """
                            SELECT workspace_id FROM workspace_memberships
                            WHERE user_id = ? AND status = 'active' AND deleted_at IS NULL
                            ORDER BY created_at ASC LIMIT 1
                            """,
                            (user_id,),
                        ).fetchone()
                        conn.close()
                        if row:
                            ws_id = str(row["workspace_id"])
                    except Exception:  # noqa: BLE001
                        pass
                return self._json(200, hermes_profile_detail(profile, ws_id))
            if path == "/api/supervisor/v1/profile.status":
                profile = qs.get("profile", [""])[0]
                if not profile:
                    return self._json(400, {"error": "profile required"})
                if SUPERVISOR_URL:
                    return self._json(
                        *_supervisor_request(
                            "GET",
                            f"/v1/profile.status?profile={urllib.parse.quote(profile, safe='')}",
                            timeout=10.0,
                        )
                    )
                return self._json(503, {"ok": False, "error": "WORKFRAME_SUPERVISOR_URL not configured"})
            if path == "/api/supervisor/v1/stack.status":
                if SUPERVISOR_URL:
                    return self._json(*_supervisor_request("GET", "/v1/stack.status", timeout=15.0))
                return self._json(503, {"ok": False, "error": "WORKFRAME_SUPERVISOR_URL not configured"})
            if path.startswith("/api/hermes/profiles/") and path.endswith("/sessions"):
                parts = path.strip("/").split("/")
                if len(parts) >= 5:
                    profile_raw = urllib.parse.unquote(parts[3])
                    source_id = qs.get("source", ["ui"])[0]
                    client_id = qs.get("client", ["default"])[0]
                    return self._json(
                        200,
                        profile_chat_session(
                            profile_raw,
                            {"source_id": source_id, "client_id": client_id, "new_session": False},
                        ),
                    )
            if path.startswith("/api/hermes/profiles/") and path.endswith("/bind"):
                parts = path.strip("/").split("/")
                if len(parts) >= 5:
                    profile_raw = urllib.parse.unquote(parts[3])
                    source_id = qs.get("source", ["ui"])[0]
                    client_id = qs.get("client", ["default"])[0]
                    return self._json(
                        200,
                        profile_chat_bind(
                            profile_raw,
                            {"source_id": source_id, "client_id": client_id, "new_session": False},
                        ),
                    )
            if path in ("/events", "/api/events"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                cors_origin = _cors_origin_for(self.headers)
                if cors_origin:
                    self.send_header("Access-Control-Allow-Origin", cors_origin)
                    self.send_header("Vary", "Origin")
                self.end_headers()
                try:
                    while True:
                        payload = json.dumps(build_snapshot())
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                        self.wfile.flush()
                        time.sleep(SSE_INTERVAL)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return

            # --- Credential listing (GET) ---

            # GET /api/workspace/:wid/credentials
            if path.startswith("/api/workspace") and path.endswith("/credentials") and self.command == "GET":
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    if not _role_allows(self, OWNER_ADMIN_ROLES):
                        return self._json(403, {"ok": False, "error": "forbidden"})
                    try:
                        conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
                        conn.row_factory = sqlite3.Row
                        rows = conn.execute(
                            """SELECT id, workspace_id, user_id, agent_profile_id, provider,
                                      credential_type, credential_ref, label, is_active,
                                      expires_at, created_by, created_at, updated_at
                               FROM credential_bindings
                               WHERE workspace_id = ? AND deleted_at IS NULL
                               ORDER BY created_at DESC""",
                            (ws_id,),
                        ).fetchall()
                        conn.close()
                    except sqlite3.Error as exc:
                        return self._json(500, {"ok": False, "error": str(exc)})
                    return self._json(200, {
                        "ok": True,
                        "scope": "workspace",
                        "workspace_id": ws_id,
                        "credentials": [dict(r) for r in rows],
                    })

            # GET /api/me/credentials — user-scoped credentials
            if path == "/api/me/credentials" and self.command == "GET":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                try:
                    conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
                    conn.row_factory = sqlite3.Row
                    rows = conn.execute(
                        """SELECT id, workspace_id, user_id, agent_profile_id, provider,
                                  credential_type, credential_ref, label, is_active,
                                  expires_at, created_by, created_at, updated_at
                           FROM credential_bindings
                           WHERE user_id = ? AND deleted_at IS NULL
                           ORDER BY created_at DESC""",
                        (user_id,),
                    ).fetchall()
                    conn.close()
                except sqlite3.Error as exc:
                    return self._json(500, {"ok": False, "error": str(exc)})
                return self._json(200, {
                    "ok": True,
                    "scope": "user",
                    "user_id": user_id,
                    "credentials": [dict(r) for r in rows],
                })

            # GET /api/agents/:agentId/credentials — agent-profile-scoped
            if path.startswith("/api/agents/") and path.endswith("/credentials") and self.command == "GET":
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    agent_id = parts[2]
                    if not _role_allows(self, OWNER_ADMIN_ROLES):
                        return self._json(403, {"ok": False, "error": "forbidden"})
                    try:
                        conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
                        conn.row_factory = sqlite3.Row
                        rows = conn.execute(
                            """SELECT id, workspace_id, user_id, agent_profile_id, provider,
                                  credential_type, credential_ref, label, is_active,
                                  expires_at, created_by, created_at, updated_at
                               FROM credential_bindings
                               WHERE agent_profile_id = ? AND deleted_at IS NULL
                               ORDER BY created_at DESC""",
                            (agent_id,),
                        ).fetchall()
                        conn.close()
                    except sqlite3.Error as exc:
                        return self._json(500, {"ok": False, "error": str(exc)})
                    return self._json(200, {
                        "ok": True,
                        "scope": "agent_profile",
                        "agent_profile_id": agent_id,
                        "credentials": [dict(r) for r in rows],
                    })

            # --- Audit event listing (admin only) ---

            if path == "/api/admin/audit" and self.command == "GET":
                if SECURE_MODE and not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden"})
                try:
                    limit = min(int(qs.get("limit", ["50"])[0]), 200)
                    offset = max(int(qs.get("offset", ["0"])[0]), 0)
                except (ValueError, IndexError):
                    limit, offset = 50, 0
                event_type_filter = str(qs.get("event_type", [""])[0]).strip()
                user_filter = str(qs.get("user_id", [""])[0]).strip()
                try:
                    conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
                    conn.row_factory = sqlite3.Row
                    where_clauses: list[str] = []
                    params: list = []
                    if event_type_filter:
                        where_clauses.append("event_type = ?")
                        params.append(event_type_filter)
                    if user_filter:
                        where_clauses.append("user_id = ?")
                        params.append(user_filter)
                    where_str = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
                    rows = conn.execute(
                        f"""SELECT id, user_id, event_type, target_type, target_id,
                                    summary, metadata, ip_address, created_at
                             FROM audit_events
                             {where_str}
                             ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                        params + [limit, offset],
                    ).fetchall()
                    total = conn.execute(
                        f"SELECT COUNT(*) AS c FROM audit_events {where_str}",
                        params,
                    ).fetchone()["c"]
                    conn.close()
                except sqlite3.Error as exc:
                    return self._json(500, {"ok": False, "error": str(exc)})
                return self._json(200, {
                    "ok": True,
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "events": [dict(r) for r in rows],
                })

            return self._json(404, {"error": "not found"})
        except ValueError as exc:
            return self._json(400, {"error": str(exc)})
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
        except Exception as exc:  # noqa: BLE001
            return self._json(500, {"ok": False, "error": str(exc)})

    # ------------------------------------------------------------------
    # First-owner bootstrap (Sprint C: secure single-user install)
    # ------------------------------------------------------------------
    def _first_owner_bootstrap(self, user_id: str, display_name: str, email: str = "") -> dict:
        """Create the owner user + default workspace if no users exist.

        Called by /api/auth/start on first login and by /api/auth/bootstrap.
        Idempotent: if users already exist, returns existing state.
        """
        try:
            conn = _workframe_db()
            existing = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
            if existing and existing["c"] > 0:
                conn.close()
                return {"ok": True, "already_initialized": True, "user_id": user_id}

            now_ts = int(time.time())
            project_name = str(os.environ.get("WORKFRAME_PROJECT", "Workframe") or "Workframe").strip() or "Workframe"
            user_avatar = _pick_user_avatar_url() or None
            ws_logo = _pick_logo_url() or None
            room_logo = ws_logo
            # Create user
            conn.execute(
                "INSERT INTO users (id, email, display_name, avatar_url, role, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (user_id, email, display_name, user_avatar, "owner", "active", str(now_ts), str(now_ts)),
            )
            # Create default workspace
            ws_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO workspaces (id, slug, display_name, owner_id, avatar_url, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (ws_id, "default", project_name, user_id, ws_logo, "active", str(now_ts), str(now_ts)),
            )
            # Create workspace membership
            conn.execute(
                "INSERT INTO workspace_memberships (id, workspace_id, user_id, role, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), ws_id, user_id, "owner", "active", str(now_ts), str(now_ts)),
            )
            # Sprint F: Seed default room
            room_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO rooms (id, workspace_id, name, slug, avatar_url, room_type, status, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (room_id, ws_id, project_name, "general", room_logo, "channel", "active", user_id, str(now_ts), str(now_ts)),
            )
            # Sprint F: Seed default agent profile
            agent_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO agent_profiles (id, workspace_id, slug, display_name, role, model_provider, model_name, is_native, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (agent_id, ws_id, "assistant", "Assistant", "assistant", "openrouter", "default", 0, "active", str(now_ts), str(now_ts)),
            )
            _ensure_user_in_room(conn, room_id, user_id, role="admin")
            _ensure_agent_in_space_room(conn, room_id, agent_id)
            conn.commit()

            # Verify
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            ws_count = conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]
            conn.close()
            return {"ok": True, "already_initialized": False, "user_id": user_id, "workspace_id": ws_id, "workspace_slug": "default", "user_count": user_count, "workspace_count": ws_count}
        except Exception as exc:
            import traceback
            traceback.print_exc()
            return {"ok": False, "error": str(exc)}

    def _complete_install(self, user_id: str, body: dict[str, Any]) -> dict[str, Any]:
        global DEPLOYMENT_MODE
        if not _native_profile_present():
            _ensure_native_hermes_profile()
        data = body if isinstance(body, dict) else {}
        if not user_id and DEPLOYMENT_MODE == "single_user_local":
            user_id = str(data.get("user_id") or secrets.token_hex(8))
            email = str(data.get("email") or "owner@local.workframe")
            display = str(data.get("display_name") or "Owner")
            self._ensure_user(user_id, display, email)
            self._first_owner_bootstrap(user_id, display, email)
        if not user_id:
            return {"ok": False, "error": "no_session"}
        ws_id = _primary_workspace_id(user_id)
        workframe_name = str(data.get("workframe_name") or "").strip()
        if ws_id and workframe_name:
            try:
                conn = _workframe_db()
                conn.execute(
                    """
                    UPDATE workspaces
                    SET display_name = ?, updated_at = ?
                    WHERE id = ? AND deleted_at IS NULL
                    """,
                    (workframe_name, str(int(time.time())), ws_id),
                )
                _sync_workspace_home_room(conn, ws_id)
                conn.commit()
                conn.close()
            except Exception:
                pass
        native_slug = str(NATIVE_PROFILE or "workframe-agent")
        runtime = _runtime_profile_slug(user_id, native_slug)
        agent_id = _ensure_workspace_agent_profile_row(
            native_slug,
            workspace_id=ws_id,
            display_name=str(data.get("agent_name") or f"{native_slug} Agent"),
            role=str(data.get("agent_role") or data.get("agent_tagline") or "Workframe Manager"),
            tagline=str(data.get("agent_tagline") or "Workframe Manager"),
            is_native=True,
        ) or ""
        if not agent_id and ws_id:
            try:
                conn = _workframe_db()
                row = conn.execute(
                    """SELECT id FROM agent_profiles
                       WHERE workspace_id = ? AND is_native = 1 AND deleted_at IS NULL LIMIT 1""",
                    (ws_id,),
                ).fetchone()
                conn.close()
                if row:
                    agent_id = str(row["id"])
            except Exception:
                pass
        room_id = ""
        session_id = ""
        bootstrap_error = ""
        lane: dict[str, Any] = {}
        if ws_id and agent_id:
            try:
                soul = str(data.get("agent_soul") or data.get("bio") or "").strip()
                model = str(data.get("model") or "").strip()
                if not model:
                    model = str(hermes_models("", user_id, ws_id).get("primary") or "").strip()
                lane = bootstrap_agent_dm_lane(
                    user_id,
                    ws_id,
                    native_slug,
                    model=model,
                    soul=soul,
                    bind_session=False,
                    room_name=str(data.get("agent_name") or "Agent").strip() or "Agent",
                    role=str(data.get("agent_role") or data.get("agent_tagline") or "Workframe Manager").strip(),
                    tagline=str(data.get("agent_tagline") or "").strip(),
                    created_by=user_id,
                )
                if not str(lane.get("room_id") or "").strip():
                    bootstrap_error = str(lane.get("error") or "native_agent_dm_bootstrap_failed")
                else:
                    room_id = str(lane["room_id"])
                    session_id = str(lane.get("session_id") or "")
            except Exception as exc:
                bootstrap_error = str(exc)
        if bootstrap_error:
            return {
                "ok": False,
                "error": bootstrap_error,
                "user_id": user_id,
                "workspace_id": ws_id,
                "agent_profile_id": agent_id,
                "runtime_profile": runtime,
                "install_complete": False,
                "steps": lane.get("steps", []) if isinstance(lane, dict) else [],
            }
        stack_config.patch_stack_config({"install_complete": True})
        if ws_id:
            _mark_workspace_install_onboarding_done(ws_id)
        DEPLOYMENT_MODE = _resolve_deployment_mode()
        pub_url = str(stack_config.get_stack_config().get("app_base_url") or "").strip()
        compose_sync = _maybe_sync_compose_public_url(pub_url, restart=True) if pub_url else None
        result: dict[str, Any] = {
            "ok": True,
            "user_id": user_id,
            "workspace_id": ws_id,
            "agent_profile_id": agent_id,
            "runtime_profile": runtime,
            "room_id": room_id,
            "session_id": session_id or _session_id_from_request(self) or "",
            "install_complete": True,
            "steps": lane.get("steps", []) if isinstance(lane, dict) else [],
        }
        if compose_sync is not None:
            result["compose_sync"] = compose_sync
        return result

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------
    def _ensure_user(self, user_id: str, display_name: str, email: str = "") -> None:
        """Ensure a user row + default workspace membership exist. Idempotent."""
        try:
            db = _workframe_db()
            now = str(int(time.time()))
            normalized_email = str(email or "").strip().lower()
            resolved_display_name = str(display_name or "").strip()
            if not resolved_display_name or "@" in resolved_display_name:
                resolved_display_name = _display_name_from_email(normalized_email) or resolved_display_name
            db.execute(
                "INSERT OR IGNORE INTO users (id, email, display_name, role, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (user_id, normalized_email or f"{user_id}@local", resolved_display_name or "Member", "user", "active", now, now),
            )
            if normalized_email:
                db.execute(
                    "UPDATE users SET email = ?, updated_at = ? WHERE id = ?",
                    (normalized_email, now, user_id),
                )
            if resolved_display_name:
                db.execute(
                    """UPDATE users
                       SET display_name = ?, updated_at = ?
                       WHERE id = ?
                         AND (COALESCE(display_name, '') = '' OR display_name LIKE '%@%')""",
                    (resolved_display_name, now, user_id),
                )
            # Ensure membership in default workspace
            ws = db.execute("SELECT id FROM workspaces WHERE slug = ? AND deleted_at IS NULL", ("default",)).fetchone()
            if ws:
                ws_id = str(ws["id"])
                _promote_workspace_owner_if_unclaimed(db, ws_id, user_id)
                existing_membership = db.execute(
                    "SELECT id, role FROM workspace_memberships WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL",
                    (ws_id, user_id),
                ).fetchone()
                if existing_membership:
                    _onboard_workspace_member_rooms(db, ws_id, user_id)
                elif not _invite_only_login_enforced():
                    db.execute(
                        "INSERT INTO workspace_memberships (id, workspace_id, user_id, role, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                        (str(uuid.uuid4()), ws_id, user_id, "member", "active", now, now),
                    )
                    _onboard_workspace_member_rooms(db, ws_id, user_id)
            db.commit()
            db.close()
        except Exception:
            pass

    def do_DELETE(self) -> None:  # noqa: N802
        """Route DELETE requests: rooms, members, memory."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        # Auth middleware
        if not _auth_check(self):
            return self._json(401, {"ok": False, "error": "no_session"})

        body = self._read_json() if self.headers.get("Content-Length") else {}

        # DELETE /api/workspace/:wid/members — direct soft-delete
        if path.startswith("/api/workspace/") and path.endswith("/members"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                ws_id = _resolve_wid(parts[2])
                if not ws_id:
                    return self._json(404, {"ok": False, "error": "workspace_not_found"})
                target_user_id = str(body.get("user_id", "")).strip()
                if not target_user_id:
                    return self._json(400, {"ok": False, "error": "user_id required"})
                try:
                    db = _workframe_db()
                    cur = db.execute("UPDATE workspace_memberships SET deleted_at = ?, status = 'removed' WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL", (str(int(time.time())), ws_id, target_user_id))
                    db.commit()
                    affected = cur.rowcount
                    db.close()
                except Exception:
                    return self._json(500, {"ok": False, "error": "delete_failed"})
                if not affected:
                    return self._json(404, {"ok": False, "error": "member_not_found"})
                self._log_audit("workspace_member_removed", "workspace_membership", f"{ws_id}/{target_user_id}", f"workspace={ws_id} user={target_user_id}")
                return self._json(200, {"ok": True, "user_id": target_user_id, "status": "removed"})

        # DELETE /api/memory/:id
        if path.startswith("/api/memory/"):
            parts = path.strip("/").split("/")
            if len(parts) == 3:
                mem_id = parts[2]
                try:
                    db = _workframe_db()
                    cur = db.execute("UPDATE memory_items SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL", (str(int(time.time())), mem_id))
                    db.commit()
                    affected = cur.rowcount
                    db.close()
                except Exception:
                    return self._json(500, {"ok": False, "error": "delete_failed"})
                if not affected:
                    return self._json(404, {"ok": False, "error": "memory_not_found"})
                return self._json(200, {"ok": True, "memory_id": mem_id, "status": "deleted"})

        # DELETE /api/rooms/:id
        if re.fullmatch(r"/api/rooms/[^/]+", path):
            rid = path.strip("/").split("/")[-1]
            try:
                db = _workframe_db()
                cur = db.execute("UPDATE rooms SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL", (str(int(time.time())), rid))
                db.commit()
                affected = cur.rowcount
                db.close()
            except Exception:
                return self._json(500, {"ok": False, "error": "delete_failed"})
            if not affected:
                return self._json(404, {"ok": False, "error": "room_not_found"})
            return self._json(200, {"ok": True, "room_id": rid, "status": "deleted"})

        if path.startswith("/api/me/credentials/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[2] == "credentials":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                return self._json(200, disconnect_user_credential(user_id, parts[3]))

        return self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if self._handle_internal_llm_proxy("POST", path):
            return
        if self._handle_internal_action_proxy("POST", path):
            return

        if SECURE_MODE:
            if not _secure_host_origin_ok(self.command, path, self.headers):
                if not _validate_host(self.headers):
                    return self._json(403, {"error": "invalid host"})
                return self._json(403, {"error": "invalid origin"})
        ct = self.headers.get("Content-Type", "")
        if SECURE_MODE and not _is_json_content_type(ct):
            return self._json(415, {"error": "Content-Type must be application/json"})

        # Auth middleware — returns 401 if session required and missing/invalid.
        if not _auth_check(self):
            return self._json(401, {"ok": False, "error": "no_session"})

        try:
            body = self._read_json()

            if path == "/api/install/email/test":
                if not _install_window_open():
                    return self._json(403, {"ok": False, "error": "install_closed"})
                try:
                    to_email = str(body.get("email", "")).strip()
                    result = install_api.smtp_test_send(to_email)
                    return self._json(200, result)
                except ValueError as exc:
                    return self._json(400, {"ok": False, "error": str(exc), "hint": install_api.smtp_error_hint(exc)})
                except Exception as exc:
                    return self._json(500, {"ok": False, "error": str(exc), "hint": install_api.smtp_error_hint(exc)})

            if path == "/api/install/url/test":
                if not _install_window_open():
                    return self._json(403, {"ok": False, "error": "install_closed"})
                url = str(body.get("url") or body.get("app_base_url") or "").strip()
                return self._json(200, install_api.url_test(url))

            if path == "/api/install/setup-https":
                if not _install_window_open():
                    return self._json(403, {"ok": False, "error": "install_closed"})
                try:
                    host, port = install_api.normalize_setup_https(
                        str(body.get("host") or body.get("url") or body.get("app_base_url") or ""),
                        body.get("port"),
                    )
                except ValueError as exc:
                    return self._json(400, {"ok": False, "error": str(exc)})
                if not _supervisor_ready():
                    return self._json(503, {"ok": False, "error": "supervisor_unavailable"})
                status, data = _supervisor_request(
                    "POST",
                    "/v1/host.setup_public_https",
                    {"host": host, "port": port},
                    timeout=600.0,
                )
                if status < 400:
                    sync = _maybe_sync_compose_public_url(f"https://{host}")
                    if isinstance(data, dict) and sync:
                        data = {**data, "compose_sync": sync}
                return self._json(status, data if isinstance(data, dict) else {"ok": False, "error": "invalid_response"})

            if path == "/api/install/complete":
                user_id = str(getattr(self, "auth_user", "") or "").strip()
                if not user_id and DEPLOYMENT_MODE != "single_user_local":
                    return self._json(401, {"ok": False, "error": "no_session"})
                return self._json(200, self._complete_install(user_id, body))

            if path == "/api/install/stack/branding-asset":
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                kind = str(body.get("kind") or "").strip().lower()
                if kind not in {"og", "favicon"}:
                    return self._json(400, {"ok": False, "error": "invalid_kind"})
                raw_b64 = str(body.get("data_base64") or "").strip()
                if raw_b64.startswith("data:"):
                    header, _, encoded = raw_b64.partition(",")
                    content_type = header.split(";")[0].replace("data:", "").strip()
                    raw_b64 = encoded
                else:
                    content_type = str(body.get("content_type") or "").strip()
                try:
                    data = base64.b64decode(raw_b64, validate=False)
                except Exception:
                    return self._json(400, {"ok": False, "error": "invalid_base64"})
                try:
                    site_meta.save_branding_asset(kind, data, content_type)
                except ValueError as exc:
                    return self._json(400, {"ok": False, "error": str(exc)})
                meta = _public_site_meta_payload()
                return self._json(
                    200,
                    {
                        "ok": True,
                        "kind": kind,
                        "og_image": meta.get("og_image"),
                        "favicon": meta.get("favicon"),
                    },
                )

            if path == "/api/admin/updates/apply":
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                if not _admin_write_allowed(self):
                    return self._json(403, {"ok": False, "error": "admin_write_forbidden", "hint": "X-Workframe-Local required in dev-unsafe"})
                target = str(body.get("target") or "all").strip().lower()
                if target not in {"hermes", "workframe", "all"}:
                    return self._json(400, {"ok": False, "error": "invalid_target"})
                try:
                    result = _apply_stack_update(target)
                    self._log_audit("stack_update_apply", "stack", target, str(result.get("ok")))
                    return self._json(200 if result.get("ok") else 500, result)
                except Exception as exc:  # noqa: BLE001
                    return self._json(500, {"ok": False, "error": str(exc)})

            if path == "/api/admin/stack/restart-gateway":
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                if not _admin_write_allowed(self):
                    return self._json(403, {"ok": False, "error": "admin_write_forbidden", "hint": "X-Workframe-Local required in dev-unsafe"})
                try:
                    result = _restart_stack_gateway()
                    self._log_audit("stack_restart_gateway", "stack", "gateway", str(result.get("ok")))
                    return self._json(200 if result.get("ok") else 500, result)
                except Exception as exc:  # noqa: BLE001
                    return self._json(500, {"ok": False, "error": str(exc)})

            if path == "/api/admin/vault/init":
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                if not _admin_write_allowed(self):
                    return self._json(403, {"ok": False, "error": "admin_write_forbidden"})
                passphrase = str(body.get("passphrase") or "").strip()
                if not passphrase:
                    return self._json(400, {"ok": False, "error": "passphrase required"})
                try:
                    status = credential_vault.init_vault_passphrase(passphrase)
                    self._log_audit("vault_passphrase_init", "vault", "meta", "passphrase_enabled")
                    return self._json(200, {"ok": True, **status})
                except ValueError as exc:
                    return self._json(400, {"ok": False, "error": str(exc)})
                except Exception as exc:  # noqa: BLE001
                    return self._json(500, {"ok": False, "error": str(exc)})

            if path == "/api/admin/vault/unlock":
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                passphrase = str(body.get("passphrase") or "").strip()
                if not passphrase:
                    return self._json(400, {"ok": False, "error": "passphrase required"})
                try:
                    status = credential_vault.unlock_vault(passphrase)
                    self._log_audit("vault_unlock", "vault", "meta", "unsealed")
                    return self._json(200, {"ok": True, **status})
                except ValueError as exc:
                    self._log_audit("vault_unlock_failed", "vault", "meta", str(exc))
                    return self._json(403, {"ok": False, "error": str(exc)})
                except Exception as exc:  # noqa: BLE001
                    return self._json(500, {"ok": False, "error": str(exc)})

            if path == "/api/admin/vault/seal":
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                if not _admin_write_allowed(self):
                    return self._json(403, {"ok": False, "error": "admin_write_forbidden"})
                status = credential_vault.seal_vault()
                self._log_audit("vault_seal", "vault", "meta", "sealed")
                return self._json(200, {"ok": True, **status})

            if path == "/api/admin/vault/wipe":
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                if not _admin_write_allowed(self):
                    return self._json(403, {"ok": False, "error": "admin_write_forbidden"})
                if not body.get("confirm"):
                    return self._json(400, {"ok": False, "error": "confirm required"})
                deleted = credential_vault.wipe_all_secrets()
                credential_vault.seal_vault()
                self._log_audit("vault_wipe", "vault", "secrets", f"deleted={deleted}")
                return self._json(200, {"ok": True, "deleted": deleted, **credential_vault.vault_status()})

            if path == "/api/auth/google/start":
                invite_email = str(body.get("email") or "").strip().lower()
                invite_token = str(body.get("invite_token") or "")
                if invite_email:
                    allowed, deny_meta = _email_allowed_to_authenticate(invite_email)
                    if not allowed and not _invite_token_allows_email(invite_token, invite_email):
                        self._log_audit(
                            "login_denied_private",
                            "user",
                            invite_email,
                            str(deny_meta.get("error") or ""),
                        )
                        return self._json(403, {"ok": False, **deny_meta})
                try:
                    payload = google_auth.start_google_auth(invite_email, invite_token)
                    return self._json(200, payload)
                except ValueError as exc:
                    return self._json(400, {"ok": False, "error": str(exc)})

            if path == "/api/auth/local-bootstrap":
                if DEPLOYMENT_MODE != "single_user_local" or not _install_window_open():
                    return self._json(403, {"ok": False, "error": "local_bootstrap_unavailable"})
                display = str(body.get("display_name") or "Owner")
                email = "owner@local.workframe"
                try:
                    result = _zk.create_session_for_email(email)
                except Exception as exc:
                    return self._json(500, {"ok": False, "error": str(exc)})
                user_id = str(result["user_id"])
                self.auth_user = user_id
                self._ensure_user(user_id, display, email)
                self._first_owner_bootstrap(user_id, display, email)
                use_secure = _session_cookie_secure()
                cookie_val = _zk.session_cookie_value(result["session_id"], secure=use_secure)
                me_payload = _session_profile_payload(user_id)
                return self._json(
                    200,
                    {
                        "ok": True,
                        "user_id": user_id,
                        "session_id": result["session_id"],
                        "refresh_token": result["refresh_token"],
                        **(me_payload or {}),
                    },
                    extra_headers=[("Set-Cookie", cookie_val)],
                )

            # --- First-owner bootstrap (also wired into /api/auth/start) ---
            if path == "/api/auth/bootstrap":
                if not SECURE_MODE:
                    return self._json(501, {"ok": False, "error": "bootstrap_requires_secure_mode"})
                data = body if isinstance(body, dict) else {}
                user_id = str(data.get("user_id", "") or secrets.token_hex(8))
                user_email = str(data.get("email", ""))
                user_display = str(data.get("display_name", "") or "Owner")
                result = self._first_owner_bootstrap(user_id, user_display, user_email)
                self._log_audit("user_created", "user", user_id, f"first-owner bootstrap: {user_display}")
                return self._json(200, result)

            # --- Setup endpoint (public, no auth) ---
            if path == "/api/setup":
                data = body if isinstance(body, dict) else {}
                agent_name = str(data.get("agent_name", "")).strip()
                workframe_name = str(data.get("workframe_name", "")).strip()
                if not agent_name:
                    return self._json(400, {"ok": False, "error": "agent_name required"})
                try:
                    db = _workframe_db()
                    ws = db.execute("SELECT * FROM workspaces WHERE slug='default' AND deleted_at IS NULL").fetchone()
                    if not ws:
                        ws_id = str(uuid.uuid4())
                        now = str(int(time.time()))
                        workspace_display_name = workframe_name or "Default Workspace"
                        ws_settings = stack_config.github_oauth_for_workspace_settings({})
                        settings_json = json.dumps(ws_settings, sort_keys=True) if ws_settings else "{}"
                        db.execute(
                            "INSERT INTO workspaces (id, slug, display_name, description, owner_id, status, created_at, updated_at, settings_json) VALUES (?, 'default', ?, '', '', 'active', ?, ?, ?)",
                            (ws_id, workspace_display_name, now, now, settings_json),
                        )
                        ws = db.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,)).fetchone()
                    elif workframe_name and str(ws["display_name"] or "").strip() != workframe_name:
                        now = str(int(time.time()))
                        db.execute(
                            "UPDATE workspaces SET display_name = ?, updated_at = ? WHERE id = ?",
                            (workframe_name, now, ws["id"]),
                        )
                        ws = db.execute("SELECT * FROM workspaces WHERE id = ?", (ws["id"],)).fetchone()
                    ws_id = ws["id"]
                    existing_agents = db.execute("SELECT COUNT(*) AS c FROM agent_profiles WHERE workspace_id = ? AND deleted_at IS NULL", (ws_id,)).fetchone()
                    if existing_agents and existing_agents["c"] > 0:
                        if agent_name:
                            now = str(int(time.time()))
                            db.execute(
                                """
                                UPDATE agent_profiles
                                SET display_name = ?, updated_at = ?
                                WHERE workspace_id = ? AND is_native = 1 AND deleted_at IS NULL
                                """,
                                (agent_name, now, ws_id),
                            )
                            db.commit()
                        db.close()
                        return self._json(200, {"ok": True, "already_initialized": True, "workspace_id": ws_id})
                    import re as _re
                    agent_slug = _re.sub(r"[^a-z0-9-]", "", agent_name.lower().replace(" ", "-"))[:40]
                    agent_id = str(uuid.uuid4())
                    now = str(int(time.time()))
                    db.execute(
                        "INSERT INTO agent_profiles (id, workspace_id, slug, display_name, tagline, role, is_native, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, 'active', ?, ?)",
                        (agent_id, ws_id, agent_slug, agent_name, str(data.get("agent_personality", "")), "native", now, now),
                    )
                    room_id = str(uuid.uuid4())
                    db.execute(
                        "INSERT INTO rooms (id, workspace_id, name, slug, topic, room_type, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'channel', 'active', ?, ?)",
                        (room_id, ws_id, "General", "general", "General discussion", now, now),
                    )
                    db.commit()
                    db.close()
                    hermes = _bootstrap_after_setup(str(data.get("agent_personality", "")))
                    return self._json(
                        200,
                        {
                            "ok": True,
                            "workspace_id": ws_id,
                            "agent_id": agent_id,
                            "room_id": room_id,
                            "hermes": hermes,
                        },
                    )
                except Exception as exc:
                    return self._json(500, {"ok": False, "error": str(exc)})

            # --- Auth endpoints (zk-auth compatible) ---
            if path == "/api/auth/start":
                # POST /api/auth/start — email → OTP → send email (or return in dev)
                email = str(body.get("email", "")).strip().lower()
                if not email or "@" not in email:
                    return self._json(400, {"ok": False, "error": "email required"})
                client_ip = str(self.client_address[0] if self.client_address else "")
                import auth_rate_limit

                if not auth_rate_limit.allow_auth_request("start", client_ip, email):
                    return self._json(429, {"ok": False, "error": "too_many_requests"})
                allowed, deny_meta = _email_allowed_to_authenticate(email)
                if not allowed:
                    self._log_audit("login_denied_private", "user", email, str(deny_meta.get("error") or ""))
                    return self._json(403, {"ok": False, **deny_meta})
                try:
                    base = APP_BASE_URL.strip().lower()
                    loopback = base.startswith("http://127.0.0.1") or base.startswith("http://localhost")
                    expose_otp = (
                        os.environ.get("WORKFRAME_E2E") == "1"
                        and _install_window_open()
                        and loopback
                    )
                    result = _zk.start_email_verification(
                        email,
                        dev_local_unsafe=DEV_LOCAL_UNSAFE,
                        expose_otp=expose_otp,
                    )
                except Exception as exc:
                    return self._json(500, {"ok": False, "error": str(exc)})
                if not DEV_LOCAL_UNSAFE and not expose_otp:
                    result.pop("otp_code", None)
                    result.pop("_dev_warning", None)
                result.pop("_e2e_warning", None)
                self._log_audit("otp_requested", "user", email, f"challenge={result.get('challenge_id','')}")
                return self._json(200, {"ok": True, "status": "verification_sent", **result})

            if path == "/api/auth/verify":
                # POST /api/auth/verify — email + OTP → session
                email = str(body.get("email", "")).strip().lower()
                code = str(body.get("code", "")).strip()
                if not email or not code:
                    return self._json(400, {"ok": False, "error": "email and code required"})
                client_ip = str(self.client_address[0] if self.client_address else "")
                import auth_rate_limit

                if not auth_rate_limit.allow_auth_request("verify", client_ip, email):
                    return self._json(429, {"ok": False, "error": "too_many_requests"})
                allowed, deny_meta = _email_allowed_to_authenticate(email)
                if not allowed:
                    self._log_audit("login_denied_private", "user", email, str(deny_meta.get("error") or ""))
                    return self._json(403, {"ok": False, **deny_meta})
                try:
                    result = _zk.verify_email_code(email, code)
                except ValueError as exc:
                    self._log_audit("login_failed", "user", email, f"verify failed: {exc}")
                    return self._json(401, {"ok": False, "error": str(exc)})
                except Exception as exc:
                    return self._json(500, {"ok": False, "error": str(exc)})
                # Set session cookie
                use_secure = _session_cookie_secure()
                cookie_val = _zk.session_cookie_value(result["session_id"], secure=use_secure)
                # Store user_id on handler for role checks
                self.auth_user = result["user_id"]
                self._ensure_user(result["user_id"], email, email)
                self._log_audit("login", "session", result["session_id"],
                                f"user={result['user_id']} new={result['is_new_user']}")
                me_payload = _session_profile_payload(result["user_id"])
                return self._json(
                    200,
                    {
                        "ok": True,
                        "user_id": result["user_id"],
                        "session_id": result["session_id"],
                        "refresh_token": result["refresh_token"],
                        "expires_at": result["expires_at"],
                        "is_new_user": result["is_new_user"],
                        **(me_payload or {}),
                    },
                    extra_headers=[("Set-Cookie", cookie_val)],
                )

            if path == "/api/auth/logout":
                # POST /api/auth/logout — revoke session
                sid = _session_id_from_request(self)
                user_id = str(getattr(self, "auth_user", "") or "")
                if sid:
                    try:
                        _zk.logout_session(sid)
                    except Exception:
                        pass
                use_secure = _session_cookie_secure()
                cookie_val = _zk.clear_session_cookie(secure=use_secure)
                self._log_audit("logout", "session", sid, f"user={user_id}")
                return self._json(200, {"ok": True}, extra_headers=[("Set-Cookie", cookie_val)])

            if path == "/api/auth/refresh":
                # POST /api/auth/refresh — refresh token rotation or cookie session extend
                refresh_token = str(body.get("refresh_token", "")).strip()
                if not refresh_token:
                    sid = _session_id_from_request(self)
                    if not sid:
                        return self._json(400, {"ok": False, "error": "refresh_token required"})
                    validated = _zk.validate_session_token(sid)
                    if not validated:
                        return self._json(401, {"ok": False, "error": "session_expired"})
                    use_secure = _session_cookie_secure()
                    cookie_val = _zk.session_cookie_value(validated["session_id"], secure=use_secure)
                    return self._json(
                        200,
                        {
                            "ok": True,
                            "user_id": validated["user_id"],
                            "session_id": validated["session_id"],
                            "expires_at": validated["expires_at"],
                        },
                        extra_headers=[("Set-Cookie", cookie_val)],
                    )
                try:
                    result = _zk.refresh_session(refresh_token)
                except ValueError as exc:
                    return self._json(401, {"ok": False, "error": str(exc)})
                except Exception as exc:
                    return self._json(500, {"ok": False, "error": str(exc)})
                # Set new session cookie
                use_secure = _session_cookie_secure()
                cookie_val = _zk.session_cookie_value(result["session_id"], secure=use_secure)
                self._log_audit("session_refreshed", "session", result["session_id"],
                                f"user={result['user_id']}")
                return self._json(
                    200,
                    {
                        "ok": True,
                        "user_id": result["user_id"],
                        "session_id": result["session_id"],
                        "refresh_token": result["refresh_token"],
                        "expires_at": result["expires_at"],
                    },
                    extra_headers=[("Set-Cookie", cookie_val)],
                )

            if path == "/api/me/credentials":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                provider = str(body.get("provider", "")).strip()
                credential_type = str(body.get("credential_type", "api_key")).strip() or "api_key"
                secret = str(body.get("secret", "")).strip()
                spec = _catalog_provider(provider)
                if spec:
                    credential_type = str(spec.get("connect_mode") or credential_type)
                env_var = str(body.get("env_var", "")).strip() or (
                    str(spec.get("env_var") or "") if spec else ""
                ) or _default_credential_env_var(provider, credential_type)
                label = str(body.get("label", "")).strip() or env_var
                if not provider:
                    return self._json(400, {"ok": False, "error": "provider required"})
                if not secret:
                    return self._json(400, {"ok": False, "error": "secret required"})
                payload = _store_user_credential(user_id, provider, credential_type, secret, env_var, label)
                cred_ref = str(payload["credential_ref"])
                now = _utc_now()
                try:
                    conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
                    conn.row_factory = sqlite3.Row
                    existing = conn.execute(
                        """SELECT id FROM credential_bindings
                           WHERE user_id = ? AND provider = ? AND credential_type = ?
                             AND credential_ref = ? AND deleted_at IS NULL
                           ORDER BY updated_at DESC, created_at DESC LIMIT 1""",
                        (user_id, provider, credential_type, cred_ref),
                    ).fetchone()
                    if existing:
                        cred_id = str(existing["id"])
                        conn.execute(
                            """UPDATE credential_bindings
                               SET label = ?, is_active = 1, updated_at = ?, deleted_at = NULL
                               WHERE id = ?""",
                            (label, now, cred_id),
                        )
                    else:
                        cred_id = str(payload["credential_id"])
                        conn.execute(
                            """INSERT INTO credential_bindings
                               (id, workspace_id, user_id, agent_profile_id, provider, credential_type,
                                credential_ref, label, is_active, created_by, created_at, updated_at)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (cred_id, None, user_id, None, provider, credential_type, cred_ref, label, 1, user_id, now, now),
                        )
                    conn.execute(
                        """UPDATE credential_bindings
                           SET is_active = 0, deleted_at = ?, updated_at = ?
                           WHERE user_id = ? AND provider = ? AND deleted_at IS NULL AND id != ?""",
                        (now, now, user_id, provider, cred_id),
                    )
                    conn.commit()
                    conn.close()
                except sqlite3.Error as exc:
                    return self._json(500, {"ok": False, "error": f"db_error: {exc}"})
                self._log_audit("credential_stored", "credential_binding", cred_id, f"provider={provider}")
                health: dict[str, Any] = {}
                if provider == "openrouter":
                    secret_probe = _credential_secret(
                        {
                            "credential_ref": cred_ref,
                            "scope": "user",
                            "user_id": user_id,
                        },
                        user_id,
                    )
                    if secret_probe:
                        health = openrouter_catalog.probe_account(secret_probe)
                _bootstrap_model_after_llm_connect(user_id, str(body.get("workspace_id") or ""), provider)
                return self._json(200, {
                    "ok": True,
                    "credential_id": cred_id,
                    "provider": provider,
                    "credential_type": credential_type,
                    "label": label,
                    "is_active": 1,
                    "user_id": user_id,
                    "created_at": now,
                    "updated_at": now,
                    "health": health,
                    **payload,
                })

            if path.startswith("/api/me/oauth/") and path.endswith("/start"):
                parts = path.strip("/").split("/")
                if len(parts) == 5 and parts[2] == "oauth" and parts[4] == "start":
                    user_id = str(getattr(self, "auth_user", "") or "")
                    if not user_id:
                        return self._json(401, {"ok": False, "error": "no_session"})
                    provider_id = parts[3]
                    workspace_id = str(body.get("workspace_id") or "")
                    return self._json(200, start_user_oauth(user_id, provider_id, workspace_id))

            if path == "/api/me/telegram/link":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                result = platform_auth.verify_telegram_login(body if isinstance(body, dict) else {})
                if not result.get("ok"):
                    return self._json(400, {"ok": False, "error": result.get("error") or "telegram_link_failed"})
                patch = result.get("platform_ids") if isinstance(result.get("platform_ids"), dict) else {}
                if patch:
                    _merge_user_platform_ids(user_id, {str(k): str(v) for k, v in patch.items()})
                return self._json(200, {"ok": True, "provider": "telegram", "platform_ids": patch})

            if path.startswith("/api/me/providers/") and path.endswith("/disconnect"):
                parts = path.strip("/").split("/")
                if len(parts) == 5 and parts[2] == "providers" and parts[4] == "disconnect":
                    user_id = str(getattr(self, "auth_user", "") or "")
                    if not user_id:
                        return self._json(401, {"ok": False, "error": "no_session"})
                    return self._json(200, disconnect_user_provider(user_id, parts[3]))

            # --- Profile management ---
            # GET /api/me is handled in do_GET above
            if path == "/api/me" and self.command == "PATCH":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                try:
                    _apply_me_profile_updates(user_id, body)
                except ValueError as exc:
                    return self._json(400, {"ok": False, "error": str(exc)})
                payload = _session_profile_payload(user_id)
                if not payload:
                    return self._json(404, {"ok": False, "error": "user_not_found"})
                return self._json(200, payload)

            # --- Credential management (Sprint D) ---
            if path.startswith("/api/workspace/") and path.endswith("/credentials/store"):
                # POST /api/workspace/:wid/credentials/store
                parts = path.strip("/").split("/")
                if len(parts) >= 4:
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    if not _role_allows(self, OWNER_ADMIN_ROLES):
                        return self._json(403, {"ok": False, "error": "forbidden"})
                    provider = str(body.get("provider", "")).strip().lower()
                    api_key = str(body.get("api_key", "") or body.get("secret", "")).strip()
                    label = str(body.get("label", "") or provider)
                    if not provider or not api_key:
                        return self._json(400, {"error": "provider and api_key required"})
                    spec = _catalog_provider(provider)
                    if not spec:
                        return self._json(400, {"error": "provider_not_found"})
                    if spec.get("user_only"):
                        return self._json(403, {"ok": False, "error": "provider_user_only"})
                    env_var = str(spec.get("env_var") or _default_credential_env_var(provider, "api_key"))
                    try:
                        payload = _store_workspace_credential(
                            ws_id,
                            provider,
                            "api_key",
                            api_key,
                            env_var,
                            label,
                            str(getattr(self, "auth_user", "") or ""),
                        )
                    except ValueError as exc:
                        return self._json(400, {"error": str(exc)})
                    cred_id = str(payload["credential_id"])
                    self._log_audit("credential_stored", "credential_binding", cred_id, f"provider={provider}")
                    _bootstrap_model_after_llm_connect("", ws_id, provider)
                    if str(spec.get("category") or "") == "messaging":
                        sync_result = _sync_workspace_messaging_gateway(ws_id)
                        if not sync_result.get("ok"):
                            return self._json(500, {"ok": False, "error": sync_result.get("error") or "messaging_sync_failed"})
                    return self._json(200, {"ok": True, "credential_id": cred_id, "credential_ref": payload["credential_ref"]})

            if path.startswith("/api/workspace/") and "/credentials/" in path and path.endswith("/revoke"):
                # POST /api/workspace/:wid/credentials/:bindingId/revoke
                parts = path.strip("/").split("/")
                if len(parts) >= 5:
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    binding_id = parts[4]
                    if not _role_allows(self, OWNER_ADMIN_ROLES):
                        return self._json(403, {"ok": False, "error": "forbidden"})
                    try:
                        conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
                        conn.row_factory = sqlite3.Row
                        row = conn.execute(
                            "SELECT provider FROM credential_bindings WHERE id = ? AND workspace_id = ?",
                            (binding_id, ws_id),
                        ).fetchone()
                        provider = str(row["provider"] or "").strip().lower() if row else ""
                        cur = conn.execute(
                            "UPDATE credential_bindings SET is_active = 0, updated_at = ? WHERE id = ? AND workspace_id = ?",
                            (str(int(time.time())), binding_id, ws_id),
                        )
                        conn.commit()
                        affected = cur.rowcount
                        conn.close()
                    except sqlite3.Error as exc:
                        return self._json(500, {"error": f"db_error: {exc}"})
                    if not affected:
                        return self._json(404, {"error": "credential_not_found"})
                    self._log_audit("credential_revoked", "credential_binding", binding_id, f"workspace={ws_id}")
                    spec = _catalog_provider(provider)
                    if spec and str(spec.get("category") or "") == "messaging":
                        sync_result = _sync_workspace_messaging_gateway(ws_id)
                        if not sync_result.get("ok"):
                            return self._json(500, {"ok": False, "error": sync_result.get("error") or "messaging_sync_failed"})
                    return self._json(200, {"ok": True, "credential_id": binding_id, "status": "revoked"})

            # --- Credential listing (workspace / user / agent-profile) ---

            # GET /api/workspace/:wid/credentials
            if path.startswith("/api/workspace") and path.endswith("/credentials") and self.command == "GET":
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    if not _role_allows(self, OWNER_ADMIN_ROLES):
                        return self._json(403, {"ok": False, "error": "forbidden"})
                    try:
                        conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
                        conn.row_factory = sqlite3.Row
                        rows = conn.execute(
                            """SELECT id, workspace_id, user_id, agent_profile_id, provider,
                                      credential_type, credential_ref, label, is_active,
                                      expires_at, created_by, created_at, updated_at
                               FROM credential_bindings
                               WHERE workspace_id = ? AND deleted_at IS NULL
                               ORDER BY created_at DESC""",
                            (ws_id,),
                        ).fetchall()
                        conn.close()
                    except sqlite3.Error as exc:
                        return self._json(500, {"ok": False, "error": str(exc)})
                    return self._json(200, {
                        "ok": True,
                        "scope": "workspace",
                        "workspace_id": ws_id,
                        "credentials": [dict(r) for r in rows],
                    })

            # GET /api/me/credentials — user-scoped credentials
            if path == "/api/me/credentials" and self.command == "GET":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                try:
                    conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
                    conn.row_factory = sqlite3.Row
                    rows = conn.execute(
                        """SELECT id, workspace_id, user_id, agent_profile_id, provider,
                                  credential_type, credential_ref, label, is_active,
                                  expires_at, created_by, created_at, updated_at
                           FROM credential_bindings
                           WHERE user_id = ? AND deleted_at IS NULL
                           ORDER BY created_at DESC""",
                        (user_id,),
                    ).fetchall()
                    conn.close()
                except sqlite3.Error as exc:
                    return self._json(500, {"ok": False, "error": str(exc)})
                return self._json(200, {
                    "ok": True,
                    "scope": "user",
                    "user_id": user_id,
                    "credentials": [dict(r) for r in rows],
                })

            # GET /api/agents/:agentId/credentials — agent-profile-scoped credentials
            if path.startswith("/api/agents/") and path.endswith("/credentials") and self.command == "GET":
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    agent_id = parts[2]
                    if not _role_allows(self, OWNER_ADMIN_ROLES):
                        return self._json(403, {"ok": False, "error": "forbidden"})
                    try:
                        conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
                        conn.row_factory = sqlite3.Row
                        rows = conn.execute(
                            """SELECT id, workspace_id, user_id, agent_profile_id, provider,
                                  credential_type, credential_ref, label, is_active,
                                  expires_at, created_by, created_at, updated_at
                           FROM credential_bindings
                           WHERE agent_profile_id = ? AND deleted_at IS NULL
                           ORDER BY created_at DESC""",
                            (agent_id,),
                        ).fetchall()
                        conn.close()
                    except sqlite3.Error as exc:
                        return self._json(500, {"ok": False, "error": str(exc)})
                    return self._json(200, {
                        "ok": True,
                        "scope": "agent_profile",
                        "agent_profile_id": agent_id,
                        "credentials": [dict(r) for r in rows],
                    })

            # --- Audit event listing (admin only) ---

            # GET /api/admin/audit — list audit events with optional filters
            if path == "/api/admin/audit" and self.command == "GET":
                if SECURE_MODE and not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden"})
                # Pagination
                try:
                    limit = min(int(qs.get("limit", ["50"])[0]), 200)
                    offset = max(int(qs.get("offset", ["0"])[0]), 0)
                except (ValueError, IndexError):
                    limit, offset = 50, 0
                event_type_filter = str(qs.get("event_type", [""])[0]).strip()
                user_filter = str(qs.get("user_id", [""])[0]).strip()
                try:
                    conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
                    conn.row_factory = sqlite3.Row
                    where_clauses = []
                    params: list = []
                    if event_type_filter:
                        where_clauses.append("event_type = ?")
                        params.append(event_type_filter)
                    if user_filter:
                        where_clauses.append("user_id = ?")
                        params.append(user_filter)
                    where_str = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
                    rows = conn.execute(
                        f"""SELECT id, user_id, event_type, target_type, target_id,
                                    summary, metadata, ip_address, created_at
                             FROM audit_events
                             {where_str}
                             ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                        params + [limit, offset],
                    ).fetchall()
                    total = conn.execute(
                        f"SELECT COUNT(*) AS c FROM audit_events {where_str}",
                        params,
                    ).fetchone()["c"]
                    conn.close()
                except sqlite3.Error as exc:
                    return self._json(500, {"ok": False, "error": str(exc)})
                return self._json(200, {
                    "ok": True,
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "events": [dict(r) for r in rows],
                })

            # --- Sprint F: Room APIs (POST) ---
            if path.startswith("/api/workspace/") and path.endswith("/rooms"):
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    created_by = str(getattr(self, "auth_user", "") or "")
                    if not _handler_is_active_workspace_member(self, ws_id):
                        return self._json(403, {"ok": False, "error": "forbidden", "required_role": "workspace_member"})
                    status, payload = _create_room(ws_id, body, created_by)
                    if status == 201:
                        self._log_audit("room_created", "room", payload["room"]["id"], f"name={payload['room']['name']}")
                    return self._json(status, payload)

            if path.startswith("/api/workspace/") and path.endswith("/rooms/create"):
                parts = path.strip("/").split("/")
                if len(parts) >= 4:
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    name = str(body.get("name", "")).strip()
                    slug = str(body.get("slug", "") or name.lower().replace(" ", "-")).strip()
                    room_type = str(body.get("room_type", "channel")).strip()
                    topic = str(body.get("topic", "")).strip()
                    agent_id = str(body.get("agent_profile_id", "")).strip()
                    if not name:
                        return self._json(400, {"error": "name required"})
                    rid = str(uuid.uuid4())
                    now_ts = str(int(time.time()))
                    try:
                        conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
                        conn.execute(
                            "INSERT INTO rooms (id, workspace_id, agent_profile_id, name, slug, topic, room_type, status, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (rid, ws_id, agent_id or None, name, slug, topic, room_type, "active", getattr(self, "auth_user", ""), now_ts, now_ts),
                        )
                        conn.commit()
                        conn.close()
                    except sqlite3.Error as exc:
                        return self._json(500, {"error": f"db_error: {exc}"})
                    self._log_audit("room_created", "room", rid, f"name={name}")
                    return self._json(200, {"ok": True, "room_id": rid})

            # --- Sprint F: Room membership (POST/DELETE) ---
            if path.startswith("/api/rooms/") and path.endswith("/members"):
                rid = path.strip("/").split("/")[-2]
                actor_id = str(getattr(self, "auth_user", "") or "")
                if not actor_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                if self.command == "POST":
                    user_id_to_add = str(body.get("user_id", "")).strip()
                    role = str(body.get("role", "member")).strip()
                    if not user_id_to_add:
                        return self._json(400, {"error": "user_id required"})
                    mid = str(uuid.uuid4())
                    now_ts = str(int(time.time()))
                    try:
                        conn = _workframe_db()
                        if not _user_can_manage_room_members(conn, rid, actor_id):
                            conn.close()
                            return self._json(403, {"ok": False, "error": "forbidden"})
                        conn.execute(
                            "INSERT INTO room_memberships (id, room_id, user_id, role, status, joined_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                            (mid, rid, user_id_to_add, role, "active", now_ts, now_ts),
                        )
                        conn.commit()
                        conn.close()
                    except sqlite3.Error as exc:
                        return self._json(500, {"error": f"db_error: {exc}"})
                    self._log_audit("room_member_added", "room_membership", mid, f"room={rid} user={user_id_to_add}")
                    return self._json(200, {"ok": True, "membership_id": mid})
                elif self.command == "DELETE":
                    uid = qs.get("user_id", [None])[0]
                    if not uid:
                        return self._json(400, {"error": "user_id required"})
                    try:
                        conn = _workframe_db()
                        if not _user_can_manage_room_members(conn, rid, actor_id):
                            conn.close()
                            return self._json(403, {"ok": False, "error": "forbidden"})
                        conn.execute(
                            "UPDATE room_memberships SET deleted_at = ?, status = 'removed' WHERE room_id = ? AND user_id = ?",
                            (str(int(time.time())), rid, uid),
                        )
                        conn.commit()
                        conn.close()
                    except sqlite3.Error as exc:
                        return self._json(500, {"error": f"db_error: {exc}"})
                    self._log_audit("room_member_removed", "room_membership", rid, f"user={uid}")
                    return self._json(200, {"ok": True})

            # --- Sprint F: Message APIs (POST) ---
            if path.startswith("/api/rooms/") and path.endswith("/bind"):
                rid = path.strip("/").split("/")[-2]
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                try:
                    return self._json(200, room_chat_bind(rid, body, user_id))
                except ValueError as exc:
                    err = str(exc)
                    if "not_found" in err:
                        return self._json(404, {"ok": False, "error": err})
                    if "denied" in err or "forbidden" in err:
                        return self._json(403, {"ok": False, "error": err})
                    return self._json(400, {"ok": False, "error": err})

            if path.startswith("/api/rooms/") and path.endswith("/sessions/activate"):
                rid = path.strip("/").split("/")[-3]
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                session_id = str(body.get("session_id", "")).strip()
                template_prof = str(body.get("profile", "")).strip()
                source_id = str(body.get("source_id") or "ui").strip() or "ui"
                client_id = str(body.get("client_id") or "default").strip() or "default"
                binding_version = _binding_version(body.get("binding_version"))
                if not session_id:
                    return self._json(400, {"error": "session_id required"})
                try:
                    payload = profile_chat_activate_room_session(
                        rid,
                        session_id,
                        user_id,
                        template_prof,
                        source_id=source_id,
                        client_id=client_id,
                        binding_version=binding_version,
                    )
                except ValueError as exc:
                    err = str(exc)
                    if "not_found" in err:
                        return self._json(404, {"ok": False, "error": err})
                    if "denied" in err:
                        return self._json(403, {"ok": False, "error": err})
                    return self._json(400, {"ok": False, "error": err})
                return self._json(200, payload)

            if path.startswith("/api/rooms/") and path.endswith("/messages/send"):
                slug_or_id = path.strip("/").split("/")[-3]
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                sender_agent = str(body.get("sender_agent_id", "")).strip()
                content = str(body.get("content", "")).strip()
                content_type = str(body.get("content_type", "text")).strip()
                parent_id = str(body.get("parent_message_id", "") or None)
                if not content:
                    return self._json(400, {"error": "content required"})
                try:
                    conn = _workframe_db()
                    room = conn.execute(
                        """
                        SELECT id, workspace_id, room_type, agent_profile_id
                        FROM rooms WHERE (id = ? OR slug = ?) AND deleted_at IS NULL
                        """,
                        (slug_or_id, slug_or_id),
                    ).fetchone()
                    if not room:
                        conn.close()
                        return self._json(404, {"error": "room_not_found"})
                    rid = str(room["id"])
                    workspace_id = str(room["workspace_id"])
                    if not _user_can_access_room(conn, rid, user_id):
                        conn.close()
                        return self._json(403, {"ok": False, "error": "forbidden"})
                    if sender_agent:
                        sender_user = ""
                        agent_member = conn.execute(
                            """
                            SELECT 1 FROM room_memberships
                            WHERE room_id = ? AND agent_profile_id = ? AND deleted_at IS NULL
                            """,
                            (rid, sender_agent),
                        ).fetchone()
                        if not agent_member:
                            conn.close()
                            return self._json(403, {"ok": False, "error": "agent_not_in_room"})
                    else:
                        sender_user = str(body.get("sender_user_id", "") or user_id).strip()
                        if sender_user != user_id:
                            conn.close()
                            return self._json(403, {"ok": False, "error": "forbidden"})
                    mid = str(uuid.uuid4())
                    now_ts = str(int(time.time()))
                    conn.execute(
                        "INSERT INTO messages (id, room_id, sender_user_id, sender_agent_id, parent_message_id, content, content_type, is_edited, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (mid, rid, sender_user or None, sender_agent or None, parent_id, content, content_type, 0, now_ts, now_ts),
                    )
                    conn.execute("UPDATE rooms SET updated_at = ? WHERE id = ?", (now_ts, rid))
                    mention_meta: dict[str, Any] = {}
                    if _is_space_room(str(room["room_type"]), room["agent_profile_id"]) and not sender_agent:
                        invoke_agents = body.get("invoke_agents", True)
                        if isinstance(invoke_agents, str):
                            invoke_agents = invoke_agents.lower() not in ("0", "false", "no")
                        mention_meta = _process_space_message_mentions(
                            rid,
                            workspace_id,
                            user_id,
                            content,
                            mid,
                            invoke_agents=bool(invoke_agents),
                        )
                    conn.commit()
                    conn.close()
                except sqlite3.Error as exc:
                    return self._json(500, {"error": f"db_error: {exc}"})
                self._log_audit("message_sent", "message", mid, f"room={rid}")
                return self._json(200, {"ok": True, "message_id": mid, **mention_meta})

            # --- Sprint H: Invites (POST) ---
            if path.startswith("/api/workspace/") and path.endswith("/invites"):
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    if not _role_allows(self, OWNER_ADMIN_ROLES):
                        return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                    email = str(body.get("email", "")).strip()
                    role = str(body.get("role", "member")).strip()
                    if not email:
                        return self._json(400, {"error": "email required"})
                    invite_id = str(uuid.uuid4())
                    token = secrets.token_hex(32)
                    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
                    now_ts = str(int(time.time()))
                    expires_at = str(int(time.time()) + 86400 * 7)
                    try:
                        conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
                        conn.execute(
                            "INSERT INTO workspace_invites (id, workspace_id, email, role, token_hash, invited_by_user_id, expires_at, created_at) VALUES (?,?,?,?,?,?,?,?)",
                            (invite_id, ws_id, email, role, token_hash, getattr(self, "auth_user", ""), expires_at, now_ts),
                        )
                        conn.commit()
                        conn.close()
                    except sqlite3.Error as exc:
                        return self._json(500, {"error": f"db_error: {exc}"})
                    invite_url = f"{APP_BASE_URL}/?invite_token={urllib.parse.quote(token)}&email={urllib.parse.quote(email)}"
                    email_sent = False
                    email_error = None
                    ws_name = ws_id
                    logo_url = ""
                    try:
                        conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
                        conn.row_factory = sqlite3.Row
                        ws_row = conn.execute(
                            "SELECT display_name, avatar_url FROM workspaces WHERE id = ?",
                            (ws_id,),
                        ).fetchone()
                        conn.close()
                        if ws_row:
                            ws_name = str(ws_row["display_name"] or ws_id)
                            logo_url = str(ws_row["avatar_url"] or "")
                    except sqlite3.Error:
                        pass
                    try:
                        send_branded_invite_email(email, ws_name, invite_url, logo_url)
                        email_sent = True
                    except Exception as exc:
                        email_error = str(exc)
                    self._log_audit("invite_created", "workspace_invite", invite_id, f"workspace={ws_id} email={email}")
                    payload = {"ok": True, "invite_id": invite_id, "token": token, "email": email, "role": role, "expires_at": expires_at, "invite_url": invite_url, "email_sent": email_sent}
                    if email_error:
                        payload["email_error"] = email_error
                    return self._json(201, payload)

            if path.startswith("/api/invites/") and path.endswith("/accept"):
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[3] == "accept":
                    token = parts[2]
                    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
                    user_id = str(getattr(self, "auth_user", "") or "")
                    if not user_id:
                        if DEV_LOCAL_UNSAFE:
                            user_id = "dev"
                        else:
                            return self._json(401, {"ok": False, "error": "no_authenticated_user"})
                    try:
                        conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
                        conn.row_factory = sqlite3.Row
                        inv = conn.execute(
                            "SELECT * FROM workspace_invites WHERE token_hash = ? AND deleted_at IS NULL AND accepted_at IS NULL",
                            (token_hash,)).fetchone()
                        if not inv:
                            conn.close()
                            return self._json(404, {"ok": False, "error": "invite_not_found_or_expired"})
                        if int(inv["expires_at"]) < int(time.time()):
                            conn.close()
                            return self._json(410, {"ok": False, "error": "invite_expired"})
                        wid = inv["workspace_id"]
                        role = inv["role"]
                        membership_id = str(uuid.uuid4())
                        now_ts = str(int(time.time()))
                        inviter_id = str(inv["invited_by_user_id"] or "").strip()
                        existing = conn.execute(
                            "SELECT id FROM workspace_memberships WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL",
                            (wid, user_id)).fetchone()
                        if existing:
                            room_join = _onboard_workspace_member_rooms(
                                conn,
                                wid,
                                user_id,
                                inviter_user_id=inviter_id or None,
                            )
                            dm_room = _ensure_user_dm_room(conn, wid, user_id, inviter_id)
                            conn.execute("UPDATE workspace_invites SET accepted_by_user_id = ?, accepted_at = ?, deleted_at = ? WHERE id = ?",
                                         (user_id, now_ts, now_ts, inv["id"]))
                            conn.commit()
                            conn.close()
                            _set_user_current_workspace(user_id, wid)
                            return self._json(200, {"ok": True, "already_member": True, "workspace_id": wid, "room": room_join, "dm_room": dm_room})
                        conn.execute(
                            "INSERT INTO workspace_memberships (id, workspace_id, user_id, role, status, invited_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                            (membership_id, wid, user_id, role, "active", inv["invited_by_user_id"], now_ts, now_ts),
                        )
                        room_join = _onboard_workspace_member_rooms(
                            conn,
                            wid,
                            user_id,
                            inviter_user_id=inviter_id or None,
                        )
                        dm_room = _ensure_user_dm_room(conn, wid, user_id, inviter_id)
                        conn.execute("UPDATE workspace_invites SET accepted_by_user_id = ?, accepted_at = ?, deleted_at = ? WHERE id = ?",
                                     (user_id, now_ts, now_ts, inv["id"]))
                        conn.commit()
                        conn.close()
                    except sqlite3.Error as exc:
                        return self._json(500, {"error": f"db_error: {exc}"})
                    _provision_invited_member_agent_runtimes(wid, user_id)
                    _set_user_current_workspace(user_id, wid)
                    self._log_audit("invite_accepted", "workspace_invite", inv["id"], f"workspace={wid} user={user_id}")
                    return self._json(
                        200,
                        {
                            "ok": True,
                            "workspace_id": wid,
                            "role": role,
                            "membership_id": membership_id,
                            "room": room_join,
                            "dm_room": dm_room,
                        },
                    )

            # --- Sprint H: Member management (POST/PATCH/DELETE) ---
            if path.startswith("/api/workspace/") and path.endswith("/members"):
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    if self.command == "POST":
                        target_user_id = str(body.get("user_id", "") or body.get("email", "")).strip()
                        role = str(body.get("role", "member")).strip()
                        if not target_user_id:
                            return self._json(400, {"ok": False, "error": "user_id required"})
                        # Check if membership already exists
                        try:
                            db = _workframe_db()
                            existing = db.execute("SELECT id FROM workspace_memberships WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL", (ws_id, target_user_id)).fetchone()
                            db.close()
                        except Exception:
                            existing = None
                        if existing:
                            # Update existing membership
                            status, payload = _patch_workspace_members(ws_id, {"user_id": target_user_id, "role": role}, self)
                        else:
                            # Create new membership
                            mid = str(uuid.uuid4())
                            now_ts = str(int(time.time()))
                            try:
                                db = _workframe_db()
                                db.execute("INSERT INTO workspace_memberships (id, workspace_id, user_id, role, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)", (mid, ws_id, target_user_id, role, "active", now_ts, now_ts))
                                _onboard_workspace_member_rooms(db, ws_id, target_user_id)
                                db.commit()
                                db.close()
                                status, payload = 200, {"ok": True, "membership_id": mid, "user_id": target_user_id, "role": role}
                            except sqlite3.Error as exc:
                                status, payload = 500, {"ok": False, "error": str(exc)}
                        if status == 200:
                            self._log_audit("workspace_member_added", "workspace_membership", f"{ws_id}/{target_user_id}", f"workspace={ws_id} user={target_user_id}")
                        return self._json(status, payload)
                    elif self.command == "PATCH":
                        status, payload = _patch_workspace_members(ws_id, body, self)
                        if status == 200:
                            self._log_audit("workspace_member_updated", "workspace_membership", ws_id, f"workspace={ws_id}")
                        return self._json(status, payload)
                    elif self.command == "DELETE":
                        target_user_id = str(body.get("user_id", "")).strip()
                        if not target_user_id:
                            return self._json(400, {"ok": False, "error": "user_id required"})
                        status, payload = _patch_workspace_members(ws_id, {"user_id": target_user_id, "delete": True}, self)
                        if status == 200:
                            self._log_audit("workspace_member_removed", "workspace_membership", f"{ws_id}/{target_user_id}", f"workspace={ws_id} user={target_user_id}")
                        return self._json(status, payload)

            if path.startswith("/api/workspace/") and path.endswith("/kanban/tasks"):
                parts = path.strip("/").split("/")
                if len(parts) == 5 and self.command == "POST":
                    ws_id = _resolve_wid(parts[2])
                    user_id = str(getattr(self, "auth_user", "") or "")
                    if not user_id:
                        return self._json(401, {"ok": False, "error": "no_session"})
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    try:
                        payload = kanban_proxy_create_task(ws_id, user_id, body)
                    except PermissionError as exc:
                        return self._json(403, {"ok": False, "error": str(exc)})
                    except ValueError as exc:
                        return self._json(400, {"ok": False, "error": str(exc)})
                    return self._json(201, payload)

            if path.startswith("/api/workspace/") and path.endswith("/delegation-grants"):
                parts = path.strip("/").split("/")
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                if len(parts) == 4 and self.command == "POST":
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    grantee_user_id = str(body.get("grantee_user_id") or "").strip()
                    scope = str(body.get("scope") or DELEGATION_SCOPE_AGENTS_DELEGATE).strip()
                    try:
                        payload = create_delegation_grant(ws_id, user_id, grantee_user_id, scope=scope)
                    except PermissionError as exc:
                        return self._json(403, {"ok": False, "error": str(exc)})
                    except ValueError as exc:
                        return self._json(400, {"ok": False, "error": str(exc)})
                    return self._json(201, payload)
                if len(parts) == 5 and self.command == "DELETE":
                    ws_id = _resolve_wid(parts[2])
                    grant_id = parts[4]
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    try:
                        payload = revoke_delegation_grant(ws_id, grant_id, user_id)
                    except PermissionError as exc:
                        return self._json(403, {"ok": False, "error": str(exc)})
                    except ValueError as exc:
                        return self._json(404, {"ok": False, "error": str(exc)})
                    return self._json(200, payload)

            if path.startswith("/api/workspace/") and path.endswith("/runtime-profiles/purge"):
                parts = path.strip("/").split("/")
                if len(parts) == 5 and self.command == "POST":
                    ws_id = _resolve_wid(parts[2])
                    user_id = str(getattr(self, "auth_user", "") or "")
                    if not user_id:
                        return self._json(401, {"ok": False, "error": "no_session"})
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    conn = _workframe_db()
                    try:
                        role = _workspace_member_role(conn, ws_id, user_id)
                    finally:
                        conn.close()
                    if role not in OWNER_ADMIN_ROLES:
                        return self._json(403, {"ok": False, "error": "forbidden"})
                    try:
                        payload = purge_stale_runtime_profiles(ws_id)
                    except ValueError as exc:
                        return self._json(400, {"ok": False, "error": str(exc)})
                    return self._json(200, payload)

            # --- Sprint I: Memory (POST/DELETE) ---
            if path.startswith("/api/workspace/") and path.endswith("/memory"):
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    content = str(body.get("content", "")).strip()
                    if not content:
                        return self._json(400, {"error": "content required"})
                    agent_profile_id = str(body.get("agent_profile_id", "") or None)
                    scope = str(body.get("scope", "workspace")).strip()
                    room_id = str(body.get("room_id") or None) if body.get("room_id") else None
                    user_id_mem = str(body.get("user_id") or None) if body.get("user_id") else None
                    visibility = str(body.get("visibility", "shared")).strip()
                    mem_id = str(uuid.uuid4())
                    now_ts = str(int(time.time()))
                    try:
                        conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
                        conn.execute(
                            "INSERT INTO memory_items (id, workspace_id, agent_profile_id, scope, room_id, user_id, content, visibility, created_by_user_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (mem_id, ws_id, agent_profile_id, scope, room_id, user_id_mem, content, visibility, getattr(self, "auth_user", ""), now_ts, now_ts),
                        )
                        conn.commit()
                        conn.close()
                    except sqlite3.Error as exc:
                        return self._json(500, {"error": f"db_error: {exc}"})
                    self._log_audit("memory_created", "memory_item", mem_id, f"workspace={ws_id} scope={scope}")
                    return self._json(201, {"ok": True, "memory_id": mem_id})

            if path.startswith("/api/memory/"):
                parts = path.strip("/").split("/")
                if len(parts) == 3:
                    mem_id = parts[2]
                    user_id = str(getattr(self, "auth_user", "") or "")
                    try:
                        conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
                        conn.row_factory = sqlite3.Row
                        item = conn.execute("SELECT * FROM memory_items WHERE id = ? AND deleted_at IS NULL", (mem_id,)).fetchone()
                        if not item:
                            conn.close()
                            return self._json(404, {"error": "memory_not_found"})
                        if not DEV_LOCAL_UNSAFE and str(item["created_by_user_id"]) != user_id:
                            auth_role = str(getattr(self, "auth_role", ""))
                            if auth_role not in OWNER_ADMIN_ROLES:
                                conn.close()
                                return self._json(403, {"error": "forbidden"})
                        now_ts = str(int(time.time()))
                        conn.execute("UPDATE memory_items SET deleted_at = ?, updated_at = ? WHERE id = ?", (now_ts, now_ts, mem_id))
                        conn.commit()
                        conn.close()
                    except sqlite3.Error as exc:
                        return self._json(500, {"error": f"db_error: {exc}"})
                    self._log_audit("memory_deleted", "memory_item", mem_id, f"user={user_id}")
                    return self._json(200, {"ok": True, "memory_id": mem_id, "status": "deleted"})

            # --- Sprint K: Budgets + Grants (POST) ---
            if path.startswith("/api/workspace/") and path.endswith("/budget"):
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    if not _role_allows(self, OWNER_ADMIN_ROLES):
                        return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                    subject_type = str(body.get("subject_type", "workspace")).strip()
                    subject_id = str(body.get("subject_id") or ws_id)
                    provider = str(body.get("provider", "") or None)
                    daily_limit = body.get("daily_limit_cents")
                    monthly_limit = body.get("monthly_limit_cents")
                    allowed_models = str(body.get("allowed_models", "") or None)
                    now_ts = str(int(time.time()))
                    policy_id = str(uuid.uuid4())
                    try:
                        conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
                        conn.execute(
                            "INSERT INTO budget_policies (id, workspace_id, subject_type, subject_id, provider, daily_limit_cents, monthly_limit_cents, allowed_models, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (policy_id, ws_id, subject_type, subject_id, provider, daily_limit, monthly_limit, allowed_models, now_ts, now_ts),
                        )
                        conn.commit()
                        conn.close()
                    except sqlite3.Error as exc:
                        return self._json(500, {"error": f"db_error: {exc}"})
                    self._log_audit("budget_created", "budget_policy", policy_id, f"workspace={ws_id} subject={subject_type}")
                    return self._json(201, {"ok": True, "budget_policy_id": policy_id})

            if path.startswith("/api/workspace/") and path.endswith("/grants"):
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    if not _role_allows(self, OWNER_ADMIN_ROLES):
                        return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                    credential_binding_id = str(body.get("credential_binding_id", "")).strip()
                    if not credential_binding_id:
                        return self._json(400, {"error": "credential_binding_id required"})
                    grantee_type = str(body.get("grantee_type", "user")).strip()
                    grantee_id = str(body.get("grantee_id", "")).strip()
                    if not grantee_id:
                        return self._json(400, {"error": "grantee_id required"})
                    provider = str(body.get("provider", "") or None)
                    max_daily = body.get("max_daily_cents")
                    max_total = body.get("max_total_cents")
                    allowed_models = str(body.get("allowed_models", "") or None)
                    allowed_agent_ids = str(body.get("allowed_agent_profile_ids", "") or None)
                    allowed_room_ids = str(body.get("allowed_room_ids", "") or None)
                    expires_at = str(body.get("expires_at") or None) if body.get("expires_at") else None
                    grant_id = str(uuid.uuid4())
                    now_ts = str(int(time.time()))
                    user_id = str(getattr(self, "auth_user", "") or "")
                    try:
                        conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
                        conn.execute(
                            "INSERT INTO credential_grants (id, credential_binding_id, granted_by_user_id, grantee_type, grantee_id, provider, max_daily_cents, max_total_cents, allowed_models, allowed_agent_profile_ids, allowed_room_ids, expires_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (grant_id, credential_binding_id, user_id, grantee_type, grantee_id, provider, max_daily, max_total, allowed_models, allowed_agent_ids, allowed_room_ids, expires_at, now_ts),
                        )
                        conn.commit()
                        conn.close()
                    except sqlite3.Error as exc:
                        return self._json(500, {"error": f"db_error: {exc}"})
                    self._log_audit("grant_created", "credential_grant", grant_id, f"workspace={ws_id} grantee={grantee_type}:{grantee_id}")
                    return self._json(201, {"ok": True, "grant_id": grant_id})

            if path == "/api/hermes/commands/exec":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                line = str(body.get("line", "")).strip()
                if not line:
                    return self._json(400, {"error": "line required"})
                return self._json(200, hermes_commands_exec(line))
            if path == "/api/hermes/gateway/exec":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                line = str(body.get("line", "")).strip()
                profile = str(body.get("profile", "")).strip()
                if not line:
                    return self._json(400, {"error": "line required"})
                user_id = str(getattr(self, "auth_user", "") or "")
                workspace_id = str(body.get("workspace_id", "") or "")
                return self._json(
                    200,
                    hermes_gateway_exec(line, profile, user_id=user_id, workspace_id=workspace_id),
                )
            if path == "/api/chat/stop":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                profile = resolve_validated_profile(str(body.get("profile") or _primary_profile()))
                run_id = str(body.get("run_id") or "").strip()
                # If no run_id provided, find the latest active run for this profile
                if not run_id:
                    run_id = _latest_active_run_id(profile)
                if not run_id:
                    return self._json(400, {"error": "no active run to stop"})
                return self._json(200, profile_gateway_stop(profile, run_id))
            if path == "/api/chat/steer":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                profile = resolve_validated_profile(str(body.get("profile") or _primary_profile()))
                run_id = str(body.get("run_id") or "").strip()
                text = str(body.get("text") or "").strip()
                if not text:
                    return self._json(400, {"error": "text required"})
                # If no run_id provided, find the latest active run
                if not run_id:
                    run_id = _latest_active_run_id(profile)
                return self._json(200, profile_gateway_steer(profile, run_id or "", text))
            if path == "/api/hermes/model":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                model_id = str(body.get("model", "")).strip()
                profile = str(body.get("profile", "")).strip()
                user_id = str(getattr(self, "auth_user", "") or "")
                workspace_id = str(body.get("workspace_id", "")).strip()
                selection_only = bool(body.get("selection_only"))
                if not model_id:
                    return self._json(400, {"error": "model required"})
                if profile and not selection_only:
                    try:
                        _bootstrap_profile_providers(_resolve_models_profile(profile), user_id, workspace_id)
                    except ValueError as exc:
                        return self._json(400, {"ok": False, "error": str(exc)})
                return self._json(
                    200,
                    hermes_model_set(
                        profile,
                        model_id,
                        user_id,
                        workspace_id,
                        selection_only=selection_only,
                    ),
                )
            if path == "/api/hermes/model/apply-default":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                return self._json(200, hermes_apply_default_model_config())
            if path == "/api/hermes/fallback-chain":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                profile = str(body.get("profile", "")).strip()
                chain = body.get("chain", [])
                selection_only = bool(body.get("selection_only"))
                user_id = str(getattr(self, "auth_user", "") or "")
                if not isinstance(chain, list):
                    return self._json(400, {"error": "chain must be a list"})
                if not selection_only and not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                return self._json(
                    200,
                    hermes_fallback_chain_set(
                        profile,
                        chain,
                        selection_only=selection_only,
                        user_id=user_id,
                    ),
                )
            if path == "/api/board":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                return self._json(201, board_create(body))
            if path == "/api/board/update":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                task_id = qs.get("id", [""])[0]
                if not task_id:
                    return self._json(400, {"error": "id required"})
                return self._json(200, board_update(task_id, body))
            if path == "/api/board/delete":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                task_id = qs.get("id", [""])[0]
                if not task_id:
                    return self._json(400, {"error": "id required"})
                board_delete(task_id)
                return self._json(200, {"ok": True})
            if path == "/api/content/save":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                rel = str(body.get("path") or "").strip()
                reason = _workspace_protected_reason(rel)
                if reason:
                    return self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
                content = str(body.get("content") or "")
                fp = _safe_content_path(rel)
                if not fp:
                    return self._json(400, {"error": "invalid path"})
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text(content, encoding="utf-8")
                _bump_workspace_state(fp)
                return self._json(200, {"ok": True, "path": rel.replace("\\", "/")})
            if path == "/api/content/delete":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                rel = qs.get("path", [""])[0] or str(body.get("path") or "")
                reason = _workspace_protected_reason(rel)
                if reason:
                    return self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
                fp = _safe_content_path(rel)
                if not fp or not fp.is_file():
                    return self._json(404, {"error": "not found"})
                fp.unlink()
                _bump_workspace_state(fp.parent)
                return self._json(200, {"ok": True})
            if path == "/api/files/write":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                rel = str(body.get("path") or "").strip()
                reason = _workspace_protected_reason(rel)
                if reason:
                    return self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
                content = str(body.get("content") or "")
                return self._json(200, file_write(rel, content))
            if path == "/api/files/upload":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                rel = str(body.get("path") or "").strip()
                reason = _workspace_protected_reason(rel)
                if reason:
                    return self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
                content_b64 = str(body.get("content_base64") or body.get("content") or "")
                return self._json(200, file_upload_binary(rel, content_b64))
            if path == "/api/chat/dispatch":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                return self._json(200, chat_dispatch(body))
            if path == "/api/hermes/profiles/create":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                if not _handler_is_active_workspace_member(self):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "workspace_member"})
                name = str(body.get("name") or "").strip()
                if not name:
                    return self._json(400, {"error": "name required"})
                model = str(body.get("model") or "").strip()
                description = str(body.get("description") or "").strip()
                clone_from = str(body.get("clone_from") or "").strip()
                soul = str(body.get("soul") or "").strip()
                display_name = str(body.get("display_name") or "").strip()
                role = str(body.get("role") or "").strip()
                tagline = str(body.get("tagline") or "").strip()
                avatar_url = str(body.get("avatar_url") or "").strip()
                avatar_id = str(body.get("avatar_id") or "").strip()
                user_id = str(getattr(self, "auth_user", "") or "").strip()
                workspace_id = str(body.get("workspace_id") or "").strip()
                if not workspace_id and user_id:
                    workspaces = _get_user_workspaces(user_id)
                    current = _resolve_current_workspace(user_id, workspaces)
                    workspace_id = str((current or {}).get("id") or (workspaces[0] or {}).get("id") or "")
                return self._json(
                    200,
                    profile_create(
                        name,
                        model,
                        description,
                        clone_from,
                        soul,
                        display_name,
                        role,
                        tagline,
                        avatar_url,
                        avatar_id,
                        user_id=user_id,
                        workspace_id=workspace_id,
                    ),
                )
            profile_bootstrap_post = re.fullmatch(r"/api/hermes/profiles/([^/]+)/bootstrap-dm", path)
            if profile_bootstrap_post:
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                if not _handler_is_active_workspace_member(self):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "workspace_member"})
                template = resolve_validated_profile(profile_bootstrap_post.group(1))
                user_id = str(getattr(self, "auth_user", "") or "").strip()
                workspace_id = str(body.get("workspace_id") or "").strip()
                if not workspace_id and user_id:
                    workspaces = _get_user_workspaces(user_id)
                    current = _resolve_current_workspace(user_id, workspaces)
                    workspace_id = str((current or {}).get("id") or (workspaces[0] or {}).get("id") or "")
                if not user_id or not workspace_id:
                    return self._json(400, {"error": "workspace_id and session required"})
                model = str(body.get("model") or "").strip()
                soul = str(body.get("soul") or "").strip()
                display_name = str(body.get("display_name") or body.get("room_name") or "").strip()
                role = str(body.get("role") or "").strip()
                tagline = str(body.get("tagline") or "").strip()
                lane = bootstrap_agent_dm_lane(
                    user_id,
                    workspace_id,
                    template,
                    model=model,
                    soul=soul,
                    bind_session=bool(body.get("bind_session", True)),
                    room_name=display_name or str(body.get("room_name") or "").strip(),
                    role=role,
                    tagline=tagline,
                    created_by=user_id,
                )
                status = 200 if lane.get("ok") else 500
                return self._json(status, lane)
            profile_soul_post = re.fullmatch(r"/api/hermes/profiles/([^/]+)/soul", path)
            if profile_soul_post:
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                profile = resolve_validated_profile(profile_soul_post.group(1))
                soul = str(body.get("soul", body.get("text", "")))
                return self._json(200, profile_soul_set(profile, soul))
            if path == "/api/hermes/profiles/start":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                profile = resolve_validated_profile(str(body.get("profile") or _primary_profile()))
                if SUPERVISOR_URL:
                    return self._json(*_supervisor_request("POST", "/v1/profile.start", body))
                return self._json(200, profile_gateway_lifecycle(profile, "start"))
            if path == "/api/hermes/profiles/stop":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                profile = resolve_validated_profile(str(body.get("profile") or _primary_profile()))
                if SUPERVISOR_URL:
                    return self._json(*_supervisor_request("POST", "/v1/profile.stop", body))
                return self._json(200, profile_gateway_lifecycle(profile, "stop"))
            if path == "/api/hermes/profiles/delete":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                profile = str(body.get("profile") or "").strip()
                if not profile:
                    return self._json(400, {"error": "profile required"})
                return self._json(200, profile_delete(profile))
            if path == "/api/hermes/profiles/disable":
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                profile = resolve_validated_profile(str(body.get("profile") or _primary_profile()))
                if SUPERVISOR_URL:
                    return self._json(*_supervisor_request("POST", "/v1/profile.disable", body))
                return self._json(200, profile_gateway_lifecycle(profile, "disable"))
            if path in {
                "/api/supervisor/v1/profile.start",
                "/api/supervisor/v1/profile.stop",
                "/api/supervisor/v1/profile.disable",
            }:
                if not _check_auth(self):
                    return self._json(401, {"error": "unauthorized"})
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                if SUPERVISOR_URL:
                    return self._json(*_supervisor_request("POST", path.removeprefix("/api/supervisor"), body))
                return self._json(503, {"ok": False, "error": "WORKFRAME_SUPERVISOR_URL not configured"})
            if path.startswith("/api/hermes/profiles/") and path.endswith("/sessions"):
                parts = path.strip("/").split("/")
                if len(parts) >= 5:
                    profile_raw = urllib.parse.unquote(parts[3])
                    user_id = getattr(self, "auth_user", "") or ""
                    return self._json(200, profile_chat_session(profile_raw, body, user_id))
            if path.startswith("/api/hermes/profiles/") and path.endswith("/bind"):
                parts = path.strip("/").split("/")
                if len(parts) >= 5:
                    profile_raw = urllib.parse.unquote(parts[3])
                    user_id = getattr(self, "auth_user", "") or ""
                    return self._json(200, profile_chat_bind(profile_raw, body, user_id))
            if path.startswith("/api/hermes/profiles/") and path.endswith("/messages"):
                parts = path.strip("/").split("/")
                if len(parts) >= 5:
                    profile_raw = urllib.parse.unquote(parts[3])
                    stream_body = _enrich_room_chat_payload(body, getattr(self, "auth_user", "") or "")
                    return self._json(200, profile_chat_message(profile_raw, stream_body))
            if path.startswith("/api/hermes/profiles/") and path.endswith("/messages/stream"):
                parts = path.strip("/").split("/")
                if len(parts) >= 6:
                    profile_raw = urllib.parse.unquote(parts[3])
                    stream_body = _enrich_room_chat_payload(body, getattr(self, "auth_user", "") or "")
                    stream_profile_chat(self, profile_raw, stream_body)
                    return
            return self._json(404, {"error": "not found"})
        except ValueError as exc:
            return self._json(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            return self._json(500, {"ok": False, "error": str(exc)})

    def do_PATCH(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if SECURE_MODE:
            if not _secure_host_origin_ok(self.command, path, self.headers):
                if not _validate_host(self.headers):
                    return self._json(403, {"error": "invalid host"})
                return self._json(403, {"error": "invalid origin"})
        ct = self.headers.get("Content-Type", "")
        if SECURE_MODE and not _is_json_content_type(ct):
            return self._json(415, {"error": "Content-Type must be application/json"})

        if not _auth_check(self):
            return self._json(401, {"ok": False, "error": "no_session"})

        try:
            body = self._read_json()
            if path == "/api/doctor/repair":
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                repair = body.get("repair", True) is not False
                result = doctor_repair_agent_dm_runtimes(repair=repair)
                if repair:
                    self._log_audit(
                        "doctor_repair_agent_dm_runtimes",
                        "runtime_profile",
                        "",
                        f"repaired={len(result.get('repaired') or [])} failed={len(result.get('failed') or [])}",
                    )
                return self._json(200, result)

            if path == "/api/install/stack":
                if not _install_window_open() and not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                try:
                    global DEPLOYMENT_MODE
                    updated = stack_config.patch_stack_config(body if isinstance(body, dict) else {})
                    compose_sync = None
                    if isinstance(body, dict) and body.get("app_base_url"):
                        compose_sync = _maybe_sync_compose_public_url(str(body.get("app_base_url") or ""))
                    DEPLOYMENT_MODE = _resolve_deployment_mode()
                    payload: dict[str, Any] = {"ok": True, **updated}
                    if compose_sync is not None:
                        payload["compose_sync"] = compose_sync
                    return self._json(200, payload)
                except ValueError as exc:
                    return self._json(400, {"ok": False, "error": str(exc)})

            if path.startswith("/api/workspace/") and path.endswith("/members"):
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    ws_id = _resolve_wid(parts[2])
                    if not ws_id:
                        return self._json(404, {"ok": False, "error": "workspace_not_found"})
                    status, payload = _patch_workspace_members(ws_id, body, self)
                    if status == 200:
                        self._log_audit(
                            "workspace_member_updated",
                            "workspace_membership",
                            ws_id,
                            f"workspace={ws_id}",
                            {"workspace_id": ws_id, "changes": body},
                        )
                    return self._json(status, payload)

            # PATCH /api/me — update own profile
            if path == "/api/me":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                try:
                    _apply_me_profile_updates(user_id, body)
                except ValueError as exc:
                    return self._json(400, {"ok": False, "error": str(exc)})
                payload = _session_profile_payload(user_id)
                if not payload:
                    return self._json(404, {"ok": False, "error": "user_not_found"})
                return self._json(200, payload)

            if path == "/api/me/native-agent":
                user_id = str(getattr(self, "auth_user", "") or "")
                if not user_id:
                    return self._json(401, {"ok": False, "error": "no_session"})
                native_slug = str(NATIVE_PROFILE or "workframe-agent")
                runtime = _runtime_profile_slug(user_id, native_slug)
                soul = (
                    str(body.get("soul") or body.get("soul_md") or "").strip()
                    if ("soul" in body or "soul_md" in body)
                    else ""
                )
                display = str(body.get("display_name") or "").strip() if "display_name" in body else ""
                tagline = str(body.get("tagline") or "").strip() if "tagline" in body else ""
                _seed_native_user_overlay(
                    runtime,
                    native_slug,
                    display_name=display,
                    tagline=tagline,
                    user_soul=soul,
                )
                profile_patch: dict[str, Any] = {}
                if display:
                    profile_patch["display_name"] = display
                if tagline:
                    profile_patch["tagline"] = tagline
                if profile_patch:
                    _sync_agent_profile_db(native_slug, profile_patch)
                if "avatar_url" in body or "avatar_id" in body:
                    avatar_patch = _normalize_agent_avatar_patch(
                        str(body.get("avatar_url") or ""),
                        str(body.get("avatar_id") or ""),
                    )
                    if avatar_patch.get("avatar_url") or avatar_patch.get("avatar_id"):
                        stamp = datetime.now(timezone.utc).isoformat()
                        row_patch = {**avatar_patch, "updated_at": stamp}
                        _upsert_agent_registry_row(native_slug, row_patch)
                        _upsert_agent_registry_row(runtime, row_patch)
                        _sync_agent_profile_db(native_slug, {"avatar_url": avatar_patch.get("avatar_url", "")})
                return self._json(200, {"ok": True, "runtime_profile": runtime})

            profile_patch_match = re.fullmatch(r"/api/hermes/profiles/([^/]+)", path)
            if profile_patch_match and profile_patch_match.group(1) not in {
                "status",
                "create",
                "start",
                "stop",
                "delete",
                "disable",
            }:
                if not _role_allows(self, OWNER_ADMIN_ROLES):
                    return self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
                profile = resolve_validated_profile(profile_patch_match.group(1))
                return self._json(200, hermes_profile_update(profile, body))

            room_patch_match = re.fullmatch(r"/api/rooms/([^/]+)", path)
            if room_patch_match:
                user_id = str(getattr(self, "auth_user", "") or "")
                status, payload = _patch_room(room_patch_match.group(1), body, user_id)
                if status == 200:
                    self._log_audit(
                        "room_updated",
                        "room",
                        room_patch_match.group(1),
                        f"room={room_patch_match.group(1)}",
                        {"changes": body},
                    )
                return self._json(status, payload)

            workspace_integrations_match = re.fullmatch(r"/api/workspace/([^/]+)/integrations", path)
            if workspace_integrations_match:
                user_id = str(getattr(self, "auth_user", "") or "")
                ws_id = _resolve_wid(workspace_integrations_match.group(1))
                if not ws_id:
                    return self._json(404, {"ok": False, "error": "workspace_not_found"})
                status, payload = _patch_workspace_integrations(ws_id, body, user_id)
                if status == 200:
                    self._log_audit(
                        "workspace_integrations_updated",
                        "workspace",
                        ws_id,
                        f"workspace={ws_id}",
                        {"changes": list(body.keys())},
                    )
                return self._json(status, payload)

            workspace_patch_match = re.fullmatch(r"/api/workspace/([^/]+)", path)
            if workspace_patch_match:
                user_id = str(getattr(self, "auth_user", "") or "")
                ws_id = _resolve_wid(workspace_patch_match.group(1))
                if not ws_id:
                    return self._json(404, {"ok": False, "error": "workspace_not_found"})
                status, payload = _patch_workspace(ws_id, body, user_id)
                if status == 200:
                    self._log_audit(
                        "workspace_updated",
                        "workspace",
                        ws_id,
                        f"workspace={ws_id}",
                        {"changes": body},
                    )
                return self._json(status, payload)

            return self._json(404, {"error": "not found"})
        except ValueError as exc:
            return self._json(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            return self._json(500, {"ok": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# Sprint E: Credential resolution + runtime tokens + agent run logging
# ---------------------------------------------------------------------------

def _credential_binding_payload(row: sqlite3.Row, scope: str) -> dict[str, Any]:
    """Return the safe metadata payload for a resolved credential binding."""
    return {
        "credential_binding_id": row["id"],
        "credential_id": row["id"],
        "credential_ref": row["credential_ref"],
        "scope": scope,
        "provider": row["provider"],
        "credential_type": row["credential_type"],
        "label": row["label"] or "",
        "user_id": row["user_id"],
        "workspace_id": row["workspace_id"],
        "agent_profile_id": row["agent_profile_id"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "expires_at": row["expires_at"],
    }


def _resolve_credential(
    user_id: str,
    workspace_id: str,
    provider: str,
    *,
    user_only: bool = False,
) -> dict[str, Any] | None:
    """Resolve which credential binding to use for an agent run.

    Resolution order:
    1. User-owned credential for this user + provider (if active and not expired)
    2. Workspace credential for this workspace + provider (if active and not expired)
       — skipped when user_only=True (dev/github/vercel tenancy)
    3. None (caller uses profile config fallback)
    """
    user = str(user_id or "").strip()
    workspace = str(workspace_id or "").strip()
    provider_name = str(provider or "").strip().lower()
    if not provider_name or (not user and not workspace):
        return None

    now_iso = _utc_now()
    now_ts = str(int(time.time()))
    conn = None
    try:
        conn = _workframe_db()
        conn.row_factory = sqlite3.Row
        if user:
            row = conn.execute(
                """
                SELECT id, workspace_id, user_id, agent_profile_id, provider,
                       credential_type, credential_ref, label, is_active,
                       expires_at, created_by, created_at, updated_at, deleted_at
                FROM credential_bindings
                WHERE user_id = ?
                  AND LOWER(provider) = ?
                  AND is_active = 1
                  AND deleted_at IS NULL
                  AND (expires_at IS NULL OR expires_at > ? OR CAST(expires_at AS INTEGER) > ?)
                ORDER BY updated_at DESC, created_at DESC, id DESC
                LIMIT 1
                """,
                (user, provider_name, now_iso, now_ts),
            ).fetchone()
            if row:
                return _credential_binding_payload(row, "user")

        if workspace and not user_only:
            row = conn.execute(
                """
                SELECT id, workspace_id, user_id, agent_profile_id, provider,
                       credential_type, credential_ref, label, is_active,
                       expires_at, created_by, created_at, updated_at, deleted_at
                FROM credential_bindings
                WHERE workspace_id = ?
                  AND LOWER(provider) = ?
                  AND is_active = 1
                  AND deleted_at IS NULL
                  AND (expires_at IS NULL OR expires_at > ? OR CAST(expires_at AS INTEGER) > ?)
                ORDER BY updated_at DESC, created_at DESC, id DESC
                LIMIT 1
                """,
                (workspace, provider_name, now_iso, now_ts),
            ).fetchone()
            if row:
                return _credential_binding_payload(row, "workspace")
    except sqlite3.Error:
        pass
    finally:
        if conn is not None:
            conn.close()

    if user:
        spec = _catalog_provider(provider_name)
        if spec and str(spec.get("category") or "") == "llm":
            env_var = str(spec.get("env_var") or "").strip()
            if env_var and _read_env_map(_user_hermes_env_path(user)).get(env_var):
                return {
                    "credential_binding_id": None,
                    "credential_id": None,
                    "credential_ref": f"env:{env_var}",
                    "scope": "user",
                    "provider": provider_name,
                    "credential_type": str(spec.get("connect_mode") or "api_key"),
                    "label": env_var,
                    "env_var": env_var,
                    "user_id": user,
                    "workspace_id": None,
                    "agent_profile_id": None,
                    "created_by": user,
                    "created_at": None,
                    "updated_at": None,
                    "expires_at": None,
                }
    return None



def _ensure_runtime_tokens_table() -> None:
    """Create provider_runtime_tokens table and indexes if needed."""
    conn = _workframe_db()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("""CREATE TABLE IF NOT EXISTS provider_runtime_tokens (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        used_at TEXT,
        revoked_at TEXT,
        created_at TEXT NOT NULL
    )""")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_provider_runtime_tokens_run "
        "ON provider_runtime_tokens(run_id, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_provider_runtime_tokens_expiry "
        "ON provider_runtime_tokens(expires_at)"
    )
    conn.commit()
    conn.close()


def _hash_runtime_token(token: str) -> str:
    """Hash a bearer runtime token before storing it."""
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _runtime_token_expired(expires_at: str) -> bool:
    """Return True when an expires_at value is expired or invalid."""
    value = str(expires_at or "").strip()
    if not value:
        return True
    if value.isdigit():
        return int(value) < int(time.time())
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) < datetime.now(timezone.utc)
    except ValueError:
        return True


def _create_runtime_token(run_id: str, ttl_seconds: int = WORKFRAME_RUNTIME_TOKEN_TTL) -> str:
    """Create a short-lived runtime token for an agent run. Returns the token."""
    run = str(run_id or "").strip()
    if not run:
        raise ValueError("run_id required")
    ttl = int(ttl_seconds or WORKFRAME_RUNTIME_TOKEN_TTL)
    if ttl <= 0:
        raise ValueError("ttl_seconds must be positive")

    _ensure_runtime_tokens_table()
    token = secrets.token_hex(32)
    now = _utc_now()
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat()
    conn = _workframe_db()
    conn.execute(
        "INSERT INTO provider_runtime_tokens "
        "(id, run_id, token_hash, expires_at, created_at) VALUES (?,?,?,?,?)",
        (secrets.token_hex(16), run, _hash_runtime_token(token), expires_at, now),
    )
    conn.commit()
    conn.close()
    return token


def _validate_runtime_token(token: str) -> dict[str, Any] | None:
    """Validate a runtime token once. Returns {"run_id": str} or None."""
    raw = str(token or "").strip()
    if not raw:
        return None

    _ensure_runtime_tokens_table()
    conn = _workframe_db()
    conn.row_factory = sqlite3.Row
    token_hash = _hash_runtime_token(raw)
    row = conn.execute(
        "SELECT id, run_id, expires_at, revoked_at, used_at "
        "FROM provider_runtime_tokens WHERE token_hash = ?",
        (token_hash,),
    ).fetchone()
    if not row:
        conn.close()
        return None

    now = _utc_now()
    if row["revoked_at"] or row["used_at"] or _runtime_token_expired(row["expires_at"]):
        conn.close()
        return None

    cursor = conn.execute(
        "UPDATE provider_runtime_tokens "
        "SET used_at = ? "
        "WHERE id = ? AND revoked_at IS NULL AND used_at IS NULL AND expires_at > ?",
        (now, row["id"], now),
    )
    if cursor.rowcount != 1:
        conn.close()
        return None
    conn.commit()
    run_id = row["run_id"]
    conn.close()
    return {"run_id": run_id}


def _log_agent_run(run_id: str, agent_profile_id: str, room_id: str, user_id: str,
                   session_id: str, status: str, model_provider: str, model_name: str,
                   input_tokens: int = 0, output_tokens: int = 0, cost_usd: float = 0.0,
                   credential_binding_id: str = None, error: str = None):
    """Record an agent run in the agent_runs table."""
    now = _utc_now()
    conn = _workframe_db()
    conn.execute(
        """INSERT INTO agent_runs (id, agent_profile_id, room_id, triggered_by_user_id, session_id,
           status, trigger_source, model_provider, model_name, input_tokens, output_tokens,
           cost_usd, error_message, started_at, completed_at, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (run_id, agent_profile_id, room_id, user_id, session_id, status, "chat",
         model_provider, model_name, input_tokens, output_tokens, cost_usd, error,
         now, now if status in ("completed", "failed") else None, now, now)
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Sprint G-K: Agent runs, invites, memory, policies, budgets, grants
# ---------------------------------------------------------------------------

# --- Sprint G: Mention parser ---
def _parse_mentions(text: str) -> list[dict]:
    """Extract @agent mentions from message text.
    Returns [{"type": "agent", "id": slug, "display_name": name}, ...]
    """
    import re as _re
    mentions = []
    for m in _re.finditer(r'@(\w+)', text):
        slug = m.group(1)
        mentions.append({"type": "agent", "slug": slug})
    return mentions


# --- Sprint G: Context package v0 ---
def _build_context_package(user_id: str, workspace_id: str, room_id: str | None = None) -> dict:
    """Assemble context package for an agent run."""
    ctx: dict[str, Any] = {"user_id": user_id, "workspace_id": workspace_id}
    conn = None
    try:
        conn = _workframe_db()
        conn.row_factory = sqlite3.Row
        ws = conn.execute("SELECT id, slug, display_name FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        if ws:
            ctx["workspace"] = dict(ws)
        if room_id:
            room = conn.execute("SELECT id, name, slug, topic FROM rooms WHERE id = ?", (room_id,)).fetchone()
            if room:
                ctx["room"] = dict(room)
        # Sprint I: memory items
        mem_items = conn.execute(
            "SELECT content, scope FROM memory_items WHERE workspace_id = ? AND deleted_at IS NULL ORDER BY updated_at DESC LIMIT 20",
            (workspace_id,)
        ).fetchall()
        if mem_items:
            ctx["memory"] = [dict(m) for m in mem_items]
    except Exception:
        pass
    finally:
        if conn:
            conn.close()
    return ctx


# --- Sprint G: Agent runs schema migration ---
def _ensure_agent_runs_schema() -> None:
    """Create or migrate the Workframe agent_runs tracking table.

    Existing Workframe installs may already have a partial agent_runs table from
    earlier schema work. This migration is idempotent: it creates the table when
    absent, adds missing columns with SQLite defaults, and records schema
    migration version 4 once the table has the required tracking fields.
    """
    conn = _workframe_db()
    try:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if "agent_runs" not in tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id TEXT PRIMARY KEY,
                    agent_profile_id TEXT NOT NULL,
                    room_id TEXT DEFAULT NULL,
                    triggered_by_user_id TEXT DEFAULT NULL,
                    session_id TEXT DEFAULT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    trigger_source TEXT NOT NULL DEFAULT 'manual',
                    prompt_text TEXT DEFAULT '',
                    result_summary TEXT DEFAULT '',
                    model_provider TEXT DEFAULT '',
                    model_name TEXT DEFAULT '',
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0.0,
                    error_message TEXT DEFAULT '',
                    started_at TEXT NOT NULL,
                    completed_at TEXT DEFAULT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles (id),
                    FOREIGN KEY (room_id) REFERENCES rooms (id),
                    FOREIGN KEY (triggered_by_user_id) REFERENCES users (id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_runs_agent "
                "ON agent_runs(agent_profile_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_runs_room "
                "ON agent_runs(room_id, created_at DESC) WHERE room_id IS NOT NULL"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_runs_session "
                "ON agent_runs(session_id) WHERE session_id IS NOT NULL"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_runs_triggered_by "
                "ON agent_runs(triggered_by_user_id) WHERE triggered_by_user_id IS NOT NULL"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at "
                "ON agent_runs(started_at DESC)"
            )
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations "
                "(version, description, applied_at) VALUES "
                "('4', 'agent_runs tracking table with trigger, prompt, result, and cost fields', datetime('now'))"
            )
            conn.commit()
            return

        cols = {c["name"] for c in conn.execute("PRAGMA table_info(agent_runs)").fetchall()}
        column_specs = {
            "trigger_source": "TEXT NOT NULL DEFAULT 'manual'",
            "prompt_text": "TEXT DEFAULT ''",
            "result_summary": "TEXT DEFAULT ''",
            "model_provider": "TEXT DEFAULT ''",
            "model_name": "TEXT DEFAULT ''",
            "input_tokens": "INTEGER DEFAULT 0",
            "output_tokens": "INTEGER DEFAULT 0",
            "cost_usd": "REAL DEFAULT 0.0",
            "error_message": "TEXT DEFAULT ''",
            "started_at": "TEXT DEFAULT ''",
            "completed_at": "TEXT DEFAULT NULL",
            "created_at": "TEXT DEFAULT ''",
            "updated_at": "TEXT DEFAULT ''",
        }
        for column, spec in column_specs.items():
            if column not in cols:
                conn.execute(f"ALTER TABLE agent_runs ADD COLUMN {column} {spec}")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_agent "
            "ON agent_runs(agent_profile_id, created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_room "
            "ON agent_runs(room_id, created_at DESC) WHERE room_id IS NOT NULL"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_session "
            "ON agent_runs(session_id) WHERE session_id IS NOT NULL"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_triggered_by "
            "ON agent_runs(triggered_by_user_id) WHERE triggered_by_user_id IS NOT NULL"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at "
            "ON agent_runs(started_at DESC)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations "
            "(version, description, applied_at) VALUES "
            "('4', 'agent_runs tracking table with trigger, prompt, result, and cost fields', datetime('now'))"
        )
        conn.commit()
    finally:
        conn.close()


# --- Sprint H: Invites ---
def _ensure_invites_schema():
    """Create workspace_invites table if not exists."""
    conn = _workframe_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS workspace_invites (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'member',
        token_hash TEXT NOT NULL,
        invited_by_user_id TEXT,
        accepted_by_user_id TEXT,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        accepted_at TEXT,
        deleted_at TEXT
    )""")
    conn.commit()
    conn.close()


# --- Sprint I: Memory ---
def _ensure_memory_schema():
    """Create memory_items table if not exists."""
    conn = _workframe_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS memory_items (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        agent_profile_id TEXT,
        scope TEXT NOT NULL CHECK(scope IN ('workspace', 'agent_profile', 'room', 'user_agent')),
        room_id TEXT,
        user_id TEXT,
        content TEXT NOT NULL,
        source_message_id TEXT,
        visibility TEXT NOT NULL DEFAULT 'shared' CHECK(visibility IN ('shared', 'private')),
        created_by_user_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT
    )""")
    conn.commit()
    conn.close()


# --- Sprint J: Provider policies ---
def _ensure_policies_schema():
    """Create workspace_provider_policies table if not exists."""
    conn = _workframe_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS workspace_provider_policies (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        allow_user_credentials INTEGER NOT NULL DEFAULT 1,
        allow_workspace_fallback INTEGER NOT NULL DEFAULT 1,
        default_model TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(workspace_id, provider)
    )""")
    conn.commit()
    conn.close()


# --- User prefs ---
def _ensure_user_prefs_schema() -> None:
    """Add users.current_workspace_id for active workspace selection."""
    conn = _workframe_db()
    try:
        cols = {c[1] for c in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "current_workspace_id" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN current_workspace_id TEXT DEFAULT NULL")
            conn.commit()
        conn.execute(
            """
            UPDATE users
            SET current_workspace_id = (
                SELECT wi.workspace_id
                FROM workspace_invites wi
                WHERE wi.accepted_by_user_id = users.id
                  AND wi.accepted_at IS NOT NULL
                ORDER BY wi.accepted_at DESC
                LIMIT 1
            )
            WHERE COALESCE(current_workspace_id, '') = ''
              AND EXISTS (
                SELECT 1 FROM workspace_invites wi
                WHERE wi.accepted_by_user_id = users.id AND wi.accepted_at IS NOT NULL
              )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _set_user_current_workspace(user_id: str, workspace_id: str) -> None:
    user_id = str(user_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if not user_id or not workspace_id:
        return
    try:
        conn = _workframe_db()
        now = str(int(time.time()))
        conn.execute(
            "UPDATE users SET current_workspace_id = ?, updated_at = ? WHERE id = ?",
            (workspace_id, now, user_id),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _resolve_current_workspace(user_id: str, workspaces: list[dict[str, Any]]) -> dict[str, Any] | None:
    user = _get_workframe_user(user_id)
    pref_id = str((user or {}).get("current_workspace_id") or "").strip()
    if pref_id:
        match = next((ws for ws in workspaces if ws.get("id") == pref_id), None)
        if match:
            return match
    default_workspace = next((ws for ws in workspaces if ws.get("slug") == "default"), None)
    return default_workspace or (workspaces[0] if workspaces else None)


def _primary_workspace_id(user_id: str = "") -> str:
    """Default workspace id for this install — one DB lookup, ponytail constant for single-ws dogfood."""
    user_id = str(user_id or "").strip()
    if user_id:
        workspaces = _get_user_workspaces(user_id)
        ws = _resolve_current_workspace(user_id, workspaces)
        if ws:
            return str(ws.get("id") or "")
    conn = _workframe_db()
    try:
        row = conn.execute(
            """
            SELECT id FROM workspaces
            WHERE deleted_at IS NULL
            ORDER BY CASE WHEN slug = 'default' THEN 0 ELSE 1 END, created_at ASC
            LIMIT 1
            """,
        ).fetchone()
        return str(row["id"]) if row else ""
    finally:
        conn.close()


# --- Sprint K: Budgets + Grants ---
def _ensure_budgets_grants_schema():
    """Create budget_policies and credential_grants tables if not exists."""
    conn = _workframe_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS budget_policies (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        subject_type TEXT NOT NULL CHECK(subject_type IN ('workspace', 'user', 'agent_profile')),
        subject_id TEXT,
        provider TEXT,
        daily_limit_cents INTEGER,
        monthly_limit_cents INTEGER,
        allowed_models TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS credential_grants (
        id TEXT PRIMARY KEY,
        credential_binding_id TEXT NOT NULL,
        granted_by_user_id TEXT NOT NULL,
        grantee_type TEXT NOT NULL CHECK(grantee_type IN ('user', 'workspace', 'agent_profile', 'room')),
        grantee_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        max_daily_cents INTEGER,
        max_total_cents INTEGER,
        allowed_models TEXT,
        allowed_agent_profile_ids TEXT,
        allowed_room_ids TEXT,
        expires_at TEXT,
        revoked_at TEXT,
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()


def _ensure_workframe_db_schema() -> None:
    """Base workframe.db tables (users, workspaces, schema_migrations, …)."""
    conn = _workframe_db()
    try:
        conn.executescript(WORKFRAME_DB_SCHEMA)
        _migrate_v6_space_rooms(conn)
        _migrate_v7_space_agent_members(conn)
        _migrate_v8_room_avatars(conn)
        _migrate_v9_workspace_avatars(conn)
        _migrate_v10_workspace_settings_oauth(conn)
        _migrate_v11_delegation_kanban_boards(conn)
        _migrate_v12_adopt_install_keys_to_owners(conn)
        _migrate_v13_workspace_members_in_spaces(conn)
        conn.commit()
    finally:
        conn.close()


def _ensure_workspace_readme() -> None:
    """Seed README.md and AGENTS.md when workspace is empty — matches create-workframe scaffold."""
    try:
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        readme = WORKSPACE / "README.md"
        if not readme.is_file():
            readme.write_text(
                f"# {PROJECT_NAME}\n\n"
                "Welcome to Workframe — your team's social AI collaboration space.\n\n"
                "Use this file to keep a living record of what this project is, who is on the team, "
                "sub-projects, agents, kanban guidelines, and anything else newcomers should know.\n",
                encoding="utf-8",
            )
        agents = WORKSPACE / "AGENTS.md"
        if agents.is_file():
            return
        native = _native_display_name()
        native_slug = str(NATIVE_PROFILE or "workframe-agent").strip() or "workframe-agent"
        agents.write_text(
            f"# AGENTS — {PROJECT_NAME}\n\n"
            "Shared project workspace (`/workspace` → `/opt/data/workspace`). "
            "All users and agents persist deliverables here.\n\n"
            f"## Native agent\n\n"
            f"**{native}** (`{native_slug}`) — concierge and orchestrator.\n\n"
            "## Layout\n\n"
            "| Path | Role |\n"
            "|------|------|\n"
            "| `/workspace/` (here) | Project artifacts — source of truth for files |\n"
            "| `/opt/data/profiles/<slug>/` | Hermes profile home — SOUL, skills, credentials |\n\n"
            "## Rules\n\n"
            "- **All deliverables** (HTML, code, docs, assets) go under `/workspace/`, never profile home.\n"
            "- Use subfolders (`/workspace/games/`, `/workspace/docs/`) to stay organized.\n"
            "- Profile `AGENTS.md` / `SOUL.md` are identity and tooling — not project output.\n"
            "- Credentials never in chat — use Workframe secure UI.\n"
            "- Chat is intake; `/workspace` is the system of record.\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_workspace_readme()
    if NATIVE_PROFILE:
        _ensure_profile_terminal_cwd(NATIVE_PROFILE)
    if not PUBLIC_DIR.is_dir():
        raise SystemExit(f"Missing public dir: {PUBLIC_DIR}")
    _ensure_workframe_db_schema()
    _ensure_default_workspace()
    # Sprint G-K: Ensure all schemas are up to date
    _ensure_agent_runs_schema()
    _ensure_invites_schema()
    _ensure_memory_schema()
    _ensure_policies_schema()
    _ensure_budgets_grants_schema()
    _ensure_user_prefs_schema()
    _ensure_runtime_tokens_table()
    credential_vault.ensure_schema()
    credential_vault.bootstrap_vault(
        allow_generate_file=DEPLOYMENT_MODE != "public_multi_user",
    )
    internal_proxy_auth.bootstrap_proxy_token(
        allow_generate_file=DEPLOYMENT_MODE != "public_multi_user",
    )
    turn_credentials.ensure_schema()
    for warning in _deployment_security_warnings():
        print(f"  WARN deployment: {warning}", flush=True)
    deploy_errors = _deployment_security_errors()
    if deploy_errors:
        raise SystemExit(
            "WORKFRAME_DEPLOYMENT_MODE security violations:\n  - " + "\n  - ".join(deploy_errors)
        )
    threading.Thread(target=_workspace_state_daemon, name="workspace-state", daemon=True).start()
    threading.Thread(target=_kanban_credential_guard_daemon, name="kanban-credential-guard", daemon=True).start()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Workframe API {VERSION} on http://{HOST}:{PORT}")
    print(f"  Hermes: {HERMES_DATA}  Workspace: {WORKSPACE}  Board: {BOARD_DB}")
    print(f"  Deployment: {DEPLOYMENT_MODE}  Secure: {SECURE_MODE}  DevUnsafe: {DEV_LOCAL_UNSAFE}")
    httpd.serve_forever()


def _get_user_workspaces(user_id: str) -> list:
    """Get workspace memberships for a user from the workframe DB."""
    try:
        db = _workframe_db()
        rows = db.execute(
            """SELECT DISTINCT w.id, w.slug, w.display_name, w.description, w.avatar_url, w.settings_json, wm.role
               FROM workspace_memberships wm
               JOIN workspaces w ON w.id = wm.workspace_id
               WHERE wm.user_id = ? AND wm.deleted_at IS NULL AND wm.status = 'active'
               ORDER BY w.slug""",
            (user_id,),
        ).fetchall()
        db.close()
        out = []
        for r in rows:
            settings = _parse_workspace_settings(r) if "settings_json" in r.keys() else {}
            out.append(
                {
                    "id": r["id"],
                    "slug": r["slug"],
                    "display_name": r["display_name"],
                    "description": r["description"] if "description" in r.keys() else "",
                    "tagline": str(settings.get("tagline") or ""),
                    "avatar_url": r["avatar_url"] if "avatar_url" in r.keys() else None,
                    "role": r["role"],
                }
            )
        return out
    except Exception:
        return []


def _get_workframe_user(user_id: str) -> dict[str, Any] | None:
    try:
        db = _workframe_db()
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        db.close()
        if not row:
            return None
        return _user_payload(row)
    except Exception:
        return None


def _mark_workspace_install_onboarding_done(workspace_id: str) -> None:
    """Persist admin wizard progress when install/complete succeeds."""
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return
    try:
        conn = _workframe_db()
        row = conn.execute(
            "SELECT settings_json FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        if not row:
            conn.close()
            return
        settings = _parse_workspace_settings(row)
        settings["admin_integrations_done"] = True
        settings["admin_onboarding_done"] = True
        conn.execute(
            "UPDATE workspaces SET settings_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(settings, sort_keys=True), str(int(time.time())), workspace_id),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error:
        pass


def _onboarding_payload(user_id: str) -> dict[str, Any]:
    """Post-auth wizard state: admin integrations → user BYOK (when workspace is byok)."""
    user_id = str(user_id or "").strip()
    workspaces = _get_user_workspaces(user_id)
    ws = next((w for w in workspaces if w.get("slug") == "default"), None) or (workspaces[0] if workspaces else None)
    if not ws:
        return {"ok": True, "complete": False, "step": "workspace", "credential_mode": "byok"}
    ws_id = str(ws.get("id") or "")
    role = str(ws.get("role") or "")
    settings: dict[str, Any] = {}
    try:
        conn = _workframe_db()
        row = conn.execute(
            "SELECT settings_json FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (ws_id,),
        ).fetchone()
        conn.close()
        if row:
            settings = _parse_workspace_settings(row)
    except sqlite3.Error:
        pass
    credential_mode = str(settings.get("credential_mode") or "byok").strip() or "byok"
    is_admin = role in OWNER_ADMIN_ROLES
    install_done = _install_complete()
    integrations_done = bool(settings.get("admin_integrations_done")) or not is_admin or install_done
    admin_done = bool(settings.get("admin_onboarding_done")) or not is_admin or install_done
    user_has_llm = _user_has_llm_provider(user_id)
    if is_admin and not integrations_done:
        return {
            "ok": True,
            "complete": False,
            "step": "admin_integrations",
            "credential_mode": credential_mode,
            "role": role,
            "workspace_id": ws_id,
        }
    if is_admin and not admin_done:
        return {
            "ok": True,
            "complete": False,
            "step": "admin",
            "credential_mode": credential_mode,
            "role": role,
            "workspace_id": ws_id,
        }
    if credential_mode == "workspace" and is_admin and not _workspace_has_llm_provider(ws_id):
        return {
            "ok": True,
            "complete": False,
            "step": "workspace_provider",
            "credential_mode": credential_mode,
            "role": role,
            "workspace_id": ws_id,
        }
    if credential_mode == "byok" and not user_has_llm:
        return {
            "ok": True,
            "complete": False,
            "step": "user_provider",
            "credential_mode": credential_mode,
            "role": role,
            "workspace_id": ws_id,
        }
    return {
        "ok": True,
        "complete": True,
        "step": "done",
        "credential_mode": credential_mode,
        "role": role,
        "workspace_id": ws_id,
        "has_llm_provider": user_has_llm,
    }


def _session_profile_payload(user_id: str) -> dict[str, Any] | None:
    """Build GET /api/me JSON body. Returns None when user cannot be resolved."""
    user_id = str(user_id or "").strip()
    if not user_id:
        return None
    profile = _zk.get_profile(user_id)
    user = _get_workframe_user(user_id)
    if not profile and not user:
        return None
    workspaces = _get_user_workspaces(user_id)
    email = str((user or {}).get("email", "") or "")
    display_name = (
        str((profile or {}).get("display_name", "") or "").strip()
        or str((user or {}).get("display_name", "") or "").strip()
        or _display_name_from_email(email)
    )
    default_workspace = next((ws for ws in workspaces if ws.get("slug") == "default"), None)
    current_workspace = _resolve_current_workspace(user_id, workspaces)
    wf_user = _get_workframe_user(user_id) or {}
    platform_ids = wf_user.get("platform_ids") if isinstance(wf_user.get("platform_ids"), dict) else {}
    zk_avatar = str((profile or {}).get("avatar_url") or "").strip()
    wf_avatar = str((user or {}).get("avatar_url") or wf_user.get("avatar_url") or "").strip()
    avatar_url = _normalize_user_avatar_url(zk_avatar or wf_avatar) if (zk_avatar or wf_avatar) else None
    return {
        "ok": True,
        "user": {
            "user_id": user_id,
            "id": user_id,
            "email": email,
            "display_name": display_name,
            "avatar_url": avatar_url,
            "tagline": (profile or {}).get("tagline"),
            "bio": (profile or {}).get("bio"),
            "platform_ids": platform_ids,
        },
        "workspaces": workspaces,
        "current_workspace": current_workspace,
        "default_workspace": default_workspace,
        "hermes_dashboard_access": _user_can_access_hermes_dashboard(user_id),
    }


if __name__ == "__main__":
    main()
