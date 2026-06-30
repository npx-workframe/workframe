"""Google Sign-In for Workframe (workspace-configured OAuth app)."""

from __future__ import annotations

import json
import os
import secrets
import urllib.parse
import urllib.request
from typing import Any

import oidc_jwt
import stack_config

APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:18644").rstrip("/")
_PENDING: dict[str, dict[str, str]] = {}


def _google_creds() -> tuple[str, str]:
    cfg = stack_config.resolved_google_oauth()
    client_id = str(cfg.get("client_id") or "").strip()
    client_secret = str(cfg.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise ValueError("Google Sign-In is not configured")
    return client_id, client_secret


def start_google_auth(invite_email: str = "", invite_token: str = "") -> dict[str, Any]:
    client_id, _ = _google_creds()
    state = secrets.token_urlsafe(24)
    _PENDING[state] = {
        "invite_email": invite_email.strip().lower(),
        "invite_token": invite_token.strip(),
    }
    redirect_uri = f"{APP_BASE_URL}/api/auth/google/callback"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    if invite_email:
        params["login_hint"] = invite_email.strip()
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return {"ok": True, "auth_url": url, "state": state}


def exchange_google_code(code: str, state: str) -> dict[str, Any]:
    pending = _PENDING.pop(state, None)
    if not pending:
        raise ValueError("invalid or expired OAuth state")
    client_id, client_secret = _google_creds()
    redirect_uri = f"{APP_BASE_URL}/api/auth/google/callback"
    data = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        token_payload = json.loads(resp.read().decode())
    id_token = str(token_payload.get("id_token") or "")
    if not id_token:
        raise ValueError("Google did not return an id_token")
    claims = oidc_jwt.verify_google_id_token(id_token, client_id)
    email = str(claims.get("email") or "").strip().lower()
    if not email:
        raise ValueError("Google account has no email")
    if claims.get("email_verified") is False:
        raise ValueError("Google email is not verified")
    invite_email = pending.get("invite_email") or ""
    if invite_email and email != invite_email:
        raise ValueError("Google email does not match the invited address")
    return {
        "email": email,
        "display_name": str(claims.get("name") or email),
        "invite_token": pending.get("invite_token") or "",
    }
