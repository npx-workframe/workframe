"""WF-032 extract: GitHub, Stripe, and Discord OAuth redirect flows."""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

import oauth_pending
import platform_auth
import provider_catalog
import stack_config
from email_sender import APP_BASE_URL

GITHUB_OAUTH_SCOPES = "repo read:user"
STRIPE_CONNECT_SCOPES = "read_write"

_store_oauth_pending = oauth_pending.store_pending
_take_oauth_pending = oauth_pending.take_pending
_pkce_pair = oauth_pending.pkce_pair


def _srv():
    import server as srv

    return srv


def _stripe_connect_app_config() -> dict[str, str]:
    """Stack Stripe Connect app â€” platform secret never leaves the BFF."""
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
    """Stack or workspace GitHub OAuth app â€” client secret never leaves the BFF."""
    workspace = str(workspace_id or "").strip()
    if workspace:
        try:
            conn = _srv()._workframe_db()
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
            "message": "Workframe admin must register a GitHub OAuth app under Workframe â†’ Integrations.",
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
    spec = provider_catalog.catalog_provider("github") or {}
    env_var = str(spec.get("env_var") or "GITHUB_TOKEN")
    payload = _srv()._store_user_credential(user_id, "github", "oauth", access_token, env_var, "GitHub OAuth")
    cred_ref = str(payload["credential_ref"])
    now = _srv()._utc_now()
    cred_id = str(uuid.uuid4())
    try:
        conn = sqlite3.connect(str(_srv()._workframe_db_path()), timeout=3.0)
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
            "message": "Workframe admin must register Stripe Connect under Workframe â†’ Integrations.",
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
    spec = provider_catalog.catalog_provider("stripe") or {}
    env_var = str(spec.get("env_var") or "STRIPE_SECRET_KEY")
    label = f"Stripe Connect ({stripe_user_id})" if stripe_user_id else "Stripe Connect"
    payload = _srv()._store_user_credential(user_id, "stripe", "oauth", access_token, env_var, label)
    cred_ref = str(payload["credential_ref"])
    now = _srv()._utc_now()
    cred_id = str(uuid.uuid4())
    try:
        conn = sqlite3.connect(str(_srv()._workframe_db_path()), timeout=3.0)
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
        _srv()._merge_user_platform_ids(user_id, {str(k): str(v) for k, v in patch.items()})
    return {"ok": True, "provider": "discord", "platform_ids": patch}
