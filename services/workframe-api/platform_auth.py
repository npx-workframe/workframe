"""Stack-level sign-in: Discord OAuth + Telegram Login (workframe admin config)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import urllib.parse
import urllib.request
from typing import Any
from urllib.parse import urlparse

import stack_config

APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:18644").rstrip("/")


def _oauth_public(block: dict[str, Any]) -> dict[str, Any]:
    client_id = str(block.get("client_id") or "").strip()
    return {
        "client_id": client_id,
        "has_secret": bool(str(block.get("client_secret") or "").strip()),
        "enabled": bool(client_id),
    }


def resolved_discord_oauth() -> dict[str, str]:
    block = stack_config._stack_oauth_raw("discord_oauth")  # ponytail: stack_config sibling module
    return {
        "client_id": str(block.get("client_id") or "").strip(),
        "client_secret": str(block.get("client_secret") or "").strip(),
    }


def discord_oauth_configured() -> bool:
    cfg = resolved_discord_oauth()
    return bool(cfg.get("client_id") and cfg.get("client_secret"))


def resolved_telegram_login() -> dict[str, str]:
    block = stack_config._stack_oauth_raw("telegram_login")
    return {
        "bot_username": str(block.get("bot_username") or "").strip().lstrip("@"),
        "bot_token": str(block.get("bot_token") or "").strip(),
    }


def telegram_login_configured() -> bool:
    cfg = resolved_telegram_login()
    return bool(cfg.get("bot_username") and cfg.get("bot_token"))


def telegram_login_domain() -> str:
    host = urlparse(APP_BASE_URL).hostname or ""
    return host.strip()


def public_discord_oauth() -> dict[str, Any]:
    return _oauth_public(stack_config._stack_oauth_raw("discord_oauth"))


def public_telegram_login() -> dict[str, Any]:
    cfg = resolved_telegram_login()
    domain = telegram_login_domain()
    return {
        "bot_username": cfg.get("bot_username") or "",
        "has_token": bool(cfg.get("bot_token")),
        "enabled": telegram_login_configured(),
        "domain": domain,
    }


def discord_redirect_uri() -> str:
    return f"{APP_BASE_URL}/api/oauth/discord/callback"


def _discord_exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict[str, Any]:
    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://discord.com/api/oauth2/token",
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
        return {"error": raw or "discord_token_exchange_failed"}
    return data if isinstance(data, dict) else {"error": "invalid_discord_response"}


def _discord_fetch_user(access_token: str) -> dict[str, Any]:
    req = urllib.request.Request(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        return {"error": str(exc)}
    return data if isinstance(data, dict) else {"error": "invalid_discord_user"}


def start_discord_link(
    *,
    state: str,
    redirect_url: str,
) -> dict[str, Any]:
    cfg = resolved_discord_oauth()
    client_id = str(cfg.get("client_id") or "").strip()
    if not client_id or not str(cfg.get("client_secret") or "").strip():
        return {
            "ok": False,
            "error": "discord_oauth_not_configured",
            "message": "Workframe admin must register a Discord OAuth app under Integrations.",
        }
    params = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": discord_redirect_uri(),
            "response_type": "code",
            "scope": "identify",
            "state": state,
            "prompt": "consent",
        },
    )
    return {
        "ok": True,
        "provider": "discord",
        "redirect_url": redirect_url or f"https://discord.com/api/oauth2/authorize?{params}",
        "output": "",
        "error": None,
    }


def complete_discord_link(code: str) -> dict[str, Any]:
    cfg = resolved_discord_oauth()
    client_id = str(cfg.get("client_id") or "").strip()
    client_secret = str(cfg.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        return {"ok": False, "error": "discord_oauth_not_configured"}
    token_data = _discord_exchange_code(code, client_id, client_secret, discord_redirect_uri())
    if token_data.get("error"):
        return {"ok": False, "error": str(token_data.get("error"))}
    access_token = str(token_data.get("access_token") or "").strip()
    if not access_token:
        return {"ok": False, "error": "discord_missing_access_token"}
    user = _discord_fetch_user(access_token)
    if user.get("error"):
        return {"ok": False, "error": str(user.get("error"))}
    discord_id = str(user.get("id") or "").strip()
    if not discord_id:
        return {"ok": False, "error": "discord_missing_user_id"}
    return {"ok": True, "provider": "discord", "platform_ids": {"discord": discord_id}}


def verify_telegram_login(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate Telegram Login widget payload; returns user id on success."""
    cfg = resolved_telegram_login()
    bot_token = str(cfg.get("bot_token") or "").strip()
    if not bot_token:
        return {"ok": False, "error": "telegram_login_not_configured"}
    data = {k: str(v) for k, v in payload.items() if k != "hash" and v is not None}
    check_hash = str(payload.get("hash") or "").strip()
    if not check_hash or not data.get("id"):
        return {"ok": False, "error": "telegram_invalid_payload"}
    check_line = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hashlib.sha256(bot_token.encode("utf-8")).digest()
    computed = hmac.new(secret, check_line.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, check_hash):
        return {"ok": False, "error": "telegram_hash_mismatch"}
    return {"ok": True, "provider": "telegram", "platform_ids": {"telegram": str(data["id"]).strip()}}


def new_oauth_state() -> str:
    return secrets.token_urlsafe(24)
