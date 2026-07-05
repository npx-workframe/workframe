"""Stack operator config (SMTP, deployment mode, install state).

During install window: stack file only (clean install — no compose env ghost creds).
After install_complete: env wins over file for VPS ops overrides.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.environ.get("WORKFRAME_API_DATA_DIR", "/app/data"))
CONFIG_PATH = DATA_DIR / "stack_config.json"

DEPLOYMENT_MODES = frozenset({"single_user_local", "trusted_team", "public_multi_user"})


def normalize_smtp_secure(port: int, secure: str) -> str:
    """Map provider port + secure hint to smtplib mode (ssl | starttls | none)."""
    s = str(secure or "").strip().lower()
    p = int(port or 587)
    if s in {"ssl", "smtps", "1", "true", "yes"}:
        return "ssl"
    if s in {"none", "off", "false", "0", "plain"}:
        return "none"
    if p == 465:
        return "ssl"
    if s in {"starttls", "tls"}:
        return "starttls"
    if p in {587, 2525}:
        return "starttls"
    return "starttls"


def _read_raw() -> dict[str, Any]:
    if not CONFIG_PATH.is_file():
        return {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_raw(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, CONFIG_PATH)
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass


def _stack_smtp_raw() -> dict[str, Any]:
    raw = _read_raw()
    smtp = raw.get("smtp")
    return smtp if isinstance(smtp, dict) else {}


def _stack_oauth_raw(key: str) -> dict[str, Any]:
    block = _read_raw().get(key)
    return block if isinstance(block, dict) else {}


def _oauth_public(block: dict[str, Any]) -> dict[str, Any]:
    client_id = str(block.get("client_id") or "").strip()
    return {
        "client_id": client_id,
        "has_secret": bool(str(block.get("client_secret") or "").strip()),
        "enabled": bool(client_id),
    }


def resolved_google_oauth() -> dict[str, str]:
    go = _stack_oauth_raw("google_oauth")
    return {
        "client_id": str(go.get("client_id") or "").strip(),
        "client_secret": str(go.get("client_secret") or "").strip(),
    }


def resolved_github_oauth() -> dict[str, str]:
    gh = _stack_oauth_raw("github_oauth")
    return {
        "client_id": str(gh.get("client_id") or "").strip(),
        "client_secret": str(gh.get("client_secret") or "").strip(),
    }


def resolved_stripe_connect() -> dict[str, str]:
    st = _stack_oauth_raw("stripe_connect")
    return {
        "client_id": str(st.get("client_id") or "").strip(),
        "client_secret": str(st.get("client_secret") or "").strip(),
    }


def github_oauth_for_workspace_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Copy install-time GitHub OAuth app creds into workspace settings when present."""
    gh = resolved_github_oauth()
    if gh.get("client_id") and gh.get("client_secret"):
        settings = dict(settings or {})
        settings["github_oauth"] = dict(gh)
    return settings


def get_stack_config() -> dict[str, Any]:
    raw = _read_raw()
    smtp = raw.get("smtp") if isinstance(raw.get("smtp"), dict) else {}
    return {
        "deployment_mode": str(raw.get("deployment_mode") or "").strip(),
        "app_base_url": str(raw.get("app_base_url") or "").strip(),
        "install_complete": bool(raw.get("install_complete")),
        "smtp": {
            "provider": str(smtp.get("provider") or "").strip(),
            "host": str(smtp.get("host") or "").strip(),
            "port": int(smtp.get("port") or 587),
            "user": str(smtp.get("user") or "").strip(),
            "from": str(smtp.get("from") or smtp.get("from_address") or "").strip(),
            "secure": str(smtp.get("secure") or "starttls").strip(),
            "has_password": bool(str(smtp.get("password") or "").strip()),
        },
        "google_oauth": _oauth_public(_stack_oauth_raw("google_oauth")),
        "github_oauth": _oauth_public(_stack_oauth_raw("github_oauth")),
        "discord_oauth": _oauth_public(_stack_oauth_raw("discord_oauth")),
        "telegram_login": _telegram_login_public(),
        "stripe_connect": _oauth_public(_stack_oauth_raw("stripe_connect")),
    }


def _telegram_login_public() -> dict[str, Any]:
    block = _stack_oauth_raw("telegram_login")
    bot_username = str(block.get("bot_username") or "").strip().lstrip("@")
    return {
        "bot_username": bot_username,
        "has_token": bool(str(block.get("bot_token") or "").strip()),
        "enabled": bool(bot_username and str(block.get("bot_token") or "").strip()),
    }


def patch_stack_config(body: dict[str, Any]) -> dict[str, Any]:
    raw = _read_raw()
    if "deployment_mode" in body:
        mode = str(body.get("deployment_mode") or "").strip().lower()
        if mode not in DEPLOYMENT_MODES:
            raise ValueError(f"invalid deployment_mode: {mode}")
        raw["deployment_mode"] = mode
        os.environ["WORKFRAME_DEPLOYMENT_MODE"] = mode
    if "app_base_url" in body:
        raw["app_base_url"] = str(body.get("app_base_url") or "").strip().rstrip("/")
    if body.get("install_complete") is True:
        raw["install_complete"] = True
    if "smtp" in body and isinstance(body["smtp"], dict):
        smtp = dict(raw.get("smtp") if isinstance(raw.get("smtp"), dict) else {})
        creds_changed = False
        for key in ("provider", "host", "user", "secure"):
            if key in body["smtp"]:
                val = str(body["smtp"][key] or "").strip()
                if str(smtp.get(key) or "").strip() != val:
                    creds_changed = True
                smtp[key] = val
        if "port" in body["smtp"]:
            port_val = int(body["smtp"].get("port") or 587)
            if int(smtp.get("port") or 587) != port_val:
                creds_changed = True
            smtp["port"] = port_val
        if "password" in body["smtp"]:
            pw = str(body["smtp"].get("password") or "")
            if pw:
                creds_changed = True
                smtp["password"] = pw
        elif "pass" in body["smtp"]:
            pw = str(body["smtp"].get("pass") or "")
            if pw:
                creds_changed = True
                smtp["password"] = pw
        if "from" in body["smtp"] or "from_address" in body["smtp"]:
            from_val = str(
                body["smtp"].get("from") if "from" in body["smtp"] else body["smtp"].get("from_address") or ""
            ).strip()
            if from_val:
                smtp["from"] = from_val
            elif "from" in smtp:
                del smtp["from"]
        if "admin_email" in body["smtp"]:
            admin_email = str(body["smtp"].get("admin_email") or "").strip().lower()
            if admin_email:
                smtp["admin_email"] = admin_email
            elif "admin_email" in smtp:
                del smtp["admin_email"]
        if creds_changed:
            smtp.pop("tested", None)
        port = int(smtp.get("port") or 587)
        smtp["secure"] = normalize_smtp_secure(port, str(smtp.get("secure") or ""))
        raw["smtp"] = smtp
    if "google_oauth" in body and isinstance(body["google_oauth"], dict):
        go = raw.get("google_oauth") if isinstance(raw.get("google_oauth"), dict) else {}
        for key in ("client_id", "client_secret"):
            if key in body["google_oauth"]:
                val = str(body["google_oauth"].get(key) or "").strip()
                if val or key == "client_id":
                    go[key] = val
        raw["google_oauth"] = go
    if "github_oauth" in body and isinstance(body["github_oauth"], dict):
        gh = raw.get("github_oauth") if isinstance(raw.get("github_oauth"), dict) else {}
        for key in ("client_id", "client_secret"):
            if key in body["github_oauth"]:
                val = str(body["github_oauth"].get(key) or "").strip()
                if val or key == "client_id":
                    gh[key] = val
        raw["github_oauth"] = gh
    if "discord_oauth" in body and isinstance(body["discord_oauth"], dict):
        dc = raw.get("discord_oauth") if isinstance(raw.get("discord_oauth"), dict) else {}
        for key in ("client_id", "client_secret"):
            if key in body["discord_oauth"]:
                val = str(body["discord_oauth"].get(key) or "").strip()
                if val or key == "client_id":
                    dc[key] = val
        raw["discord_oauth"] = dc
    if "telegram_login" in body and isinstance(body["telegram_login"], dict):
        tg = raw.get("telegram_login") if isinstance(raw.get("telegram_login"), dict) else {}
        if "bot_username" in body["telegram_login"]:
            tg["bot_username"] = str(body["telegram_login"].get("bot_username") or "").strip().lstrip("@")
        if "bot_token" in body["telegram_login"]:
            token = str(body["telegram_login"].get("bot_token") or "").strip()
            if token:
                tg["bot_token"] = token
        raw["telegram_login"] = tg
    if "stripe_connect" in body and isinstance(body["stripe_connect"], dict):
        st = raw.get("stripe_connect") if isinstance(raw.get("stripe_connect"), dict) else {}
        for key in ("client_id", "client_secret"):
            if key in body["stripe_connect"]:
                val = str(body["stripe_connect"].get(key) or "").strip()
                if val or key == "client_id":
                    st[key] = val
        raw["stripe_connect"] = st
    if "site_branding" in body and isinstance(body["site_branding"], dict):
        block = raw.get("site_branding") if isinstance(raw.get("site_branding"), dict) else {}
        for key in ("title", "description", "theme_color"):
            if key in body["site_branding"]:
                block[key] = str(body["site_branding"].get(key) or "").strip()
        raw["site_branding"] = block
    _write_raw(raw)
    return get_stack_config()


def resolve_deployment_mode(env_default: str = "trusted_team") -> str:
    """Persisted stack_config deployment_mode wins when set; else WORKFRAME_DEPLOYMENT_MODE env."""
    try:
        sc_mode = str(_read_raw().get("deployment_mode") or "").strip().lower()
        if sc_mode in DEPLOYMENT_MODES:
            return sc_mode
    except Exception:
        pass
    env_raw = (os.environ.get("WORKFRAME_DEPLOYMENT_MODE") or "").strip().lower()
    if env_raw in DEPLOYMENT_MODES:
        return env_raw
    if env_raw:
        return env_raw
    raw = (env_default or "trusted_team").strip().lower()
    return raw if raw in DEPLOYMENT_MODES else "trusted_team"


def effective_deployment_mode(env_default: str) -> str:
    return resolve_deployment_mode(env_default)


def _install_window_open() -> bool:
    return not bool(_read_raw().get("install_complete"))


def resolved_smtp() -> dict[str, Any]:
    """Stack file during install; env overrides only after install_complete."""
    stack = _stack_smtp_raw()
    stack_host = str(stack.get("host") or "").strip()
    stack_user = str(stack.get("user") or "").strip()
    stack_pw = str(stack.get("password") or "").strip().replace(" ", "")
    stack_from = str(stack.get("from") or "").strip()

    env_host = "" if _install_window_open() else os.environ.get("SMTP_HOST", "").strip()
    if env_host:
        port = int(os.environ.get("SMTP_PORT", "587"))
        secure = normalize_smtp_secure(
            port,
            os.environ.get("SMTP_SECURE", "").strip().lower(),
        )
        user = os.environ.get("SMTP_USER", "").strip() or stack_user
        password = (
            os.environ.get("SMTP_PASSWORD") or os.environ.get("SMTP_PASS") or stack_pw or ""
        ).strip().replace(" ", "")
        from_addr = (
            os.environ.get("SMTP_FROM") or os.environ.get("EMAIL_FROM") or stack_from or user or ""
        ).strip()
        return {
            "host": env_host,
            "port": port,
            "user": user,
            "password": password,
            "from": from_addr or user,
            "secure": secure,
            "source": "env",
        }

    if not stack_host:
        return {"source": "none"}
    port = int(stack.get("port") or 587)
    user = stack_user
    return {
        "host": stack_host,
        "port": port,
        "user": user,
        "password": stack_pw,
        "from": stack_from or user,
        "secure": normalize_smtp_secure(port, str(stack.get("secure") or "starttls")),
        "source": "stack_config",
    }


def smtp_configured() -> bool:
    s = resolved_smtp()
    return bool(s.get("host") and s.get("source") != "none")


def smtp_tested() -> bool:
    stack = _stack_smtp_raw()
    return bool(stack.get("tested"))


def smtp_has_password() -> bool:
    stack = _stack_smtp_raw()
    if str(stack.get("password") or "").strip():
        return True
    resolved = resolved_smtp()
    return bool(str(resolved.get("password") or "").strip())


def smtp_setup_complete() -> bool:
    """SMTP tested and admin email saved — wizard may skip re-test."""
    if not smtp_tested():
        return False
    stack = _stack_smtp_raw()
    return bool(str(stack.get("admin_email") or "").strip()) and smtp_has_password() and smtp_configured()


def mark_smtp_tested() -> None:
    raw = _read_raw()
    smtp = dict(raw.get("smtp") if isinstance(raw.get("smtp"), dict) else {})
    smtp["tested"] = True
    raw["smtp"] = smtp
    _write_raw(raw)


def _site_branding_public_payload() -> dict[str, Any]:
    try:
        import site_meta

        return site_meta.site_branding_public()
    except Exception:
        return {
            "title": "",
            "description": "",
            "theme_color": "",
            "has_og_image": False,
            "has_favicon": False,
        }


def public_stack_payload() -> dict[str, Any]:
    cfg = get_stack_config()
    smtp = cfg.get("smtp") or {}
    go = cfg.get("google_oauth") or {}
    gh = cfg.get("github_oauth") or {}
    dc = cfg.get("discord_oauth") or {}
    tg = cfg.get("telegram_login") or {}
    st = cfg.get("stripe_connect") or {}
    app_base = str(cfg.get("app_base_url") or "").strip().rstrip("/")
    domain = ""
    if app_base:
        try:
            from urllib.parse import urlparse

            domain = (urlparse(app_base).hostname or "").strip()
        except Exception:
            domain = ""
    return {
        "deployment_mode": cfg.get("deployment_mode") or "",
        "app_base_url": cfg.get("app_base_url") or "",
        "install_complete": bool(cfg.get("install_complete")),
        "smtp": {
            "provider": smtp.get("provider") or "",
            "host": smtp.get("host") or "",
            "port": smtp.get("port") or 587,
            "user": smtp.get("user") or "",
            "from": smtp.get("from") or "",
            "admin_email": smtp.get("admin_email") or "",
            "secure": smtp.get("secure") or "starttls",
            "configured": smtp_configured(),
            "tested": smtp_tested(),
            "setup_complete": smtp_setup_complete(),
            "has_password": smtp_has_password(),
        },
        "google_oauth": {
            "client_id": go.get("client_id") or "",
            "has_secret": bool(go.get("has_secret")),
            "enabled": bool(go.get("enabled")),
        },
        "github_oauth": {
            "client_id": gh.get("client_id") or "",
            "has_secret": bool(gh.get("has_secret")),
            "enabled": bool(gh.get("enabled")),
        },
        "discord_oauth": {
            "client_id": dc.get("client_id") or "",
            "has_secret": bool(dc.get("has_secret")),
            "enabled": bool(dc.get("enabled")),
        },
        "telegram_login": {
            "bot_username": tg.get("bot_username") or "",
            "has_token": bool(tg.get("has_token")),
            "enabled": bool(tg.get("enabled")),
            "domain": domain,
        },
        "stripe_connect": {
            "client_id": st.get("client_id") or "",
            "has_secret": bool(st.get("has_secret")),
            "enabled": bool(st.get("enabled")),
        },
        "site_branding": _site_branding_public_payload(),
    }
