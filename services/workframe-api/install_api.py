"""Install / stack-setup API helpers."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import stack_config
from email_sender import send_email_with_config

HERMES_DATA = Path(os.environ.get("HERMES_DATA", "/opt/data"))
NATIVE_PROFILE = os.environ.get("WORKFRAME_NATIVE_PROFILE", "workframe-agent").strip() or "workframe-agent"

INSTALL_WIZARD_STEPS = frozenset({
    "intro",
    "welcome",
    "publish",
    "smtp",
    "admin_auth",
    "workframe",
    "billing",
    "integrations",
    "profile",
    "agent",
    "agent_model",
    "invites",
    "done",
})
INSTALL_WIZARD_STEP_ORDER = (
    "intro",
    "welcome",
    "publish",
    "smtp",
    "admin_auth",
    "workframe",
    "billing",
    "integrations",
    "profile",
    "agent",
    "agent_model",
    "invites",
    "done",
)


def _user_count(db_path: str) -> int:
    try:
        conn = sqlite3.connect(db_path, timeout=2.0)
        row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        conn.close()
        return int(row[0]) if row else 0
    except (sqlite3.Error, OSError):
        return 0


def install_window_open(db_path: str) -> bool:
    """Open until operator marks install complete — users may exist mid-onboarding."""
    del db_path  # ponytail: reserved for future per-install DB path checks
    return not bool(stack_config.get_stack_config().get("install_complete"))


def install_auth_email_allowed(email: str) -> tuple[bool, dict[str, Any]]:
    """During install, only the configured admin email may register until verified."""
    normalized = str(email or "").strip().lower()
    if not normalized or "@" not in normalized:
        return False, {"error": "email required"}
    if not install_window_open(""):
        return True, {}
    smtp = stack_config.get_stack_config().get("smtp") or {}
    configured = str(smtp.get("admin_email") or "").strip().lower()
    verified_admin = str(smtp.get("admin_email") or "").strip().lower() if stack_config.install_admin_verified() else ""
    if verified_admin:
        if normalized == verified_admin:
            return True, {}
        return False, {
            "error": "install_admin_email_required",
            "message": "Sign in with the admin email for this install.",
        }
    if configured and normalized != configured:
        return False, {
            "error": "install_admin_email_required",
            "message": "Use the admin email entered at the start of setup.",
        }
    return True, {}


def install_owner_claimed(db_path: str) -> bool:
    """True once the first install admin has verified and owns the default workspace."""
    try:
        conn = sqlite3.connect(db_path, timeout=2.0)
        row = conn.execute(
            """
            SELECT 1 FROM workspaces
            WHERE deleted_at IS NULL
              AND TRIM(COALESCE(owner_id, '')) != ''
            LIMIT 1
            """,
        ).fetchone()
        conn.close()
        return bool(row)
    except (sqlite3.Error, OSError):
        return False


def install_mutations_require_owner(db_path: str) -> bool:
    """After admin verify, install stack mutations require the owner session."""
    return install_owner_claimed(db_path) or stack_config.install_admin_verified()


def _default_workspace_settings(db_path: str) -> dict[str, Any]:
    try:
        conn = sqlite3.connect(db_path, timeout=2.0)
        row = conn.execute(
            """
            SELECT settings_json FROM workspaces
            WHERE deleted_at IS NULL
            ORDER BY CASE WHEN slug = 'default' THEN 0 ELSE 1 END, created_at ASC
            LIMIT 1
            """,
        ).fetchone()
        conn.close()
        if not row:
            return {}
        raw = str(row[0] or "{}")
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (sqlite3.Error, OSError, json.JSONDecodeError, TypeError):
        return {}


def _wizard_step_index(step: str) -> int:
    try:
        return INSTALL_WIZARD_STEP_ORDER.index(step)
    except ValueError:
        return -1


def _derive_install_wizard_step(db_path: str) -> str:
    cfg = stack_config.get_stack_config()
    smtp = cfg.get("smtp") if isinstance(cfg.get("smtp"), dict) else {}
    if not str(smtp.get("admin_email") or "").strip():
        return "intro"
    if not install_owner_claimed(db_path):
        return "intro"
    mode = str(cfg.get("deployment_mode") or "").strip()
    if not mode:
        return "welcome"
    if mode == "public_multi_user" and not str(cfg.get("app_base_url") or "").strip():
        return "publish"
    if mode != "single_user_local" and not stack_config.install_admin_verified():
        if stack_config.smtp_setup_complete():
            return "admin_auth"
        return "smtp"

    settings = _default_workspace_settings(db_path)
    if not settings.get("admin_onboarding_done"):
        return "workframe"
    if not settings.get("admin_integrations_done"):
        return "billing"

    return "profile"


def resolve_install_wizard_step(db_path: str) -> str:
    """Resume ConciergeFlow at the last persisted or derived wizard step."""
    derived = _derive_install_wizard_step(db_path)
    raw = stack_config.read_stack_raw()
    saved = str(raw.get("wizard_step") or "").strip()
    if saved in INSTALL_WIZARD_STEPS:
        derived_idx = _wizard_step_index(derived)
        saved_idx = _wizard_step_index(saved)
        # Never resume ahead of incomplete gates (e.g. saved smtp before deployment).
        if derived_idx >= 0 and saved_idx >= 0 and saved_idx != derived_idx:
            return derived
        return saved
    return derived


def install_wizard_public_payload(db_path: str) -> dict[str, Any]:
    return {
        "admin_verified": stack_config.install_admin_verified(),
        "resume_step": resolve_install_wizard_step(db_path),
        "owner_claimed": install_owner_claimed(db_path),
    }


def _hermes_native_present() -> bool:
    for slug in (NATIVE_PROFILE, "workframe-agent"):
        if not slug:
            continue
        prof_dir = HERMES_DATA / "profiles" / slug
        if (prof_dir / "config.yaml").is_file() or (prof_dir / "profile.yaml").is_file():
            return True
    return False


def _setup_complete(db_path: str) -> bool:
    try:
        conn = sqlite3.connect(db_path, timeout=2.0)
        row = conn.execute(
            "SELECT COUNT(*) FROM agent_profiles WHERE deleted_at IS NULL"
        ).fetchone()
        conn.close()
        return bool(row and row[0] > 0)
    except (sqlite3.Error, OSError):
        return _hermes_native_present()


def install_status_payload(
    deployment_mode: str,
    secure_mode: bool,
    dev_unsafe: bool,
    db_path: str,
) -> dict[str, Any]:
    hermes = _hermes_native_present()
    setup = _setup_complete(db_path)
    smtp_ok = stack_config.smtp_configured()
    return {
        "ok": True,
        "phase": "ready" if hermes and setup else ("hermes" if not hermes else "workspace"),
        "hermes_present": hermes,
        "setup_complete": setup,
        "api_ok": True,
        "deployment_mode": deployment_mode,
        "mode": "dev_unsafe" if dev_unsafe else ("secure" if secure_mode else "dev_unsafe"),
        "smtp_configured": smtp_ok,
        "install_complete": bool(stack_config.get_stack_config().get("install_complete")),
        "install_window_open": install_window_open(db_path),
        "native_profile": NATIVE_PROFILE,
    }


def smtp_test_send(to_email: str) -> dict[str, Any]:
    to_email = str(to_email or "").strip().lower()
    if not to_email or "@" not in to_email:
        raise ValueError("valid email required")
    cfg = stack_config.resolved_smtp()
    if not cfg.get("host"):
        raise ValueError("SMTP is not configured yet")
    subject = "Workframe test email"
    text = "If you received this, your Workframe SMTP settings are working."
    html = "<p>If you received this, your Workframe SMTP settings are working.</p>"
    send_email_with_config(to_email, subject, text, html, cfg)
    stack_config.patch_stack_config({"smtp": {"admin_email": to_email}})
    stack_config.mark_smtp_tested()
    return {"ok": True, "email_sent": True, "to": to_email}


def _normalize_app_base_url(url: str) -> str:
    """Ensure app_base_url has a scheme for health checks and OAuth callbacks."""
    u = str(url or "").strip().rstrip("/")
    if not u:
        return ""
    if not u.lower().startswith(("http://", "https://")):
        u = f"https://{u}"
    return u


def _hostname_only(url: str) -> str:
    u = _normalize_app_base_url(url)
    if not u:
        return ""
    try:
        return urllib.parse.urlparse(u).hostname or ""
    except Exception:
        return str(url or "").strip().lower()


def dns_record_name(hostname: str) -> str:
    host = _hostname_only(hostname) or str(hostname or "").strip().lower().rstrip(".")
    if not host:
        return "@"
    parts = host.split(".")
    if len(parts) <= 2:
        return "@"
    return parts[0]


def apex_domain(hostname: str) -> str:
    host = _hostname_only(hostname) or str(hostname or "").strip().lower().rstrip(".")
    if not host:
        return ""
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    return ".".join(parts[-2:])


def detect_public_ipv4() -> str | None:
    for url in ("https://api4.ipify.org", "https://ifconfig.me/ip"):
        try:
            with urllib.request.urlopen(url, timeout=4) as resp:
                ip = resp.read().decode("utf-8", errors="replace").strip()
                if ip and "." in ip:
                    return ip
        except (urllib.error.URLError, OSError, TimeoutError, ValueError):
            continue
    return None


def publish_hints_payload(public_url: str) -> dict[str, Any]:
    host = _hostname_only(public_url)
    apex = apex_domain(host)
    ui_port = int(os.environ.get("WORKFRAME_UI_PORT", "18644") or "18644")
    public_ip = detect_public_ipv4()
    project_root = (
        os.environ.get("WORKFRAME_HOST_PROJECT_ROOT", "").strip()
        or "/opt/workframe/repo"
    )
    setup_command = (
        f"sudo bash {project_root}/scripts/workframe/setup-public-https.sh {host} {ui_port}"
        if host
        else ""
    )
    dns_name = dns_record_name(host)
    return {
        "ok": True,
        "hostname": host,
        "apex_domain": apex,
        "public_ipv4": public_ip,
        "ui_port": ui_port,
        "project_root": project_root,
        "health_url": f"https://{host}/api/health" if host else "",
        "dns": {
            "type": "A",
            "name": dns_name,
            "value": public_ip or "",
            "ttl": "600",
        },
        "dns_cname": {
            "type": "CNAME",
            "name": dns_name,
            "value": apex,
            "hint": "Optional: point the subdomain at your apex hostname instead of an IP. CNAME cannot target an IP address.",
        }
        if apex and dns_name != "@"
        else None,
        "registrar_links": [
            {
                "label": "GoDaddy DNS",
                "url": f"https://dcc.godaddy.com/manage/{apex}/dns" if apex else "https://dcc.godaddy.com/control/portfolio",
            },
            {
                "label": "Namecheap DNS",
                "url": f"https://ap.www.namecheap.com/Domains/DomainControlPanel/{apex}/advancedns"
                if apex
                else "https://www.namecheap.com/domains/",
            },
            {"label": "Cloudflare", "url": "https://dash.cloudflare.com"},
        ],
        "setup_command": setup_command,
    }


def _loopback_hostname(hostname: str) -> bool:
    h = (hostname or "").strip().lower().rstrip(".")
    return h in ("127.0.0.1", "localhost", "::1") or h.endswith(".localhost")


def _fetch_health(url: str, timeout: float = 8) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        ok = resp.status == 200 and '"ok"' in body
        return {"ok": ok, "status": resp.status, "checked_url": url}


def _local_stack_health() -> dict[str, Any]:
    ui_port = int(os.environ.get("WORKFRAME_UI_PORT", "18644") or "18644")
    app_base = str(
        stack_config.get_stack_config().get("app_base_url")
        or os.environ.get("APP_BASE_URL", "")
        or f"http://127.0.0.1:{ui_port}",
    )
    host_header = _hostname_only(app_base) or "127.0.0.1"
    req = urllib.request.Request(
        "http://workframe-ui/api/health",
        headers={"Host": f"{host_header}:{ui_port}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            ok = resp.status == 200 and '"ok"' in body
            return {"ok": ok, "status": resp.status, "local_ok": ok, "checked_url": req.full_url}
    except Exception as exc:
        return {"local_ok": False, "error": str(exc)}


def _url_test_hint(exc: Exception, *, local: dict[str, Any]) -> str:
    msg = str(exc).lower()
    ui_port = int(os.environ.get("WORKFRAME_UI_PORT", "18644") or "18644")
    if "connection refused" in msg or "errno 111" in msg:
        base = (
            f"Nothing is listening on HTTPS for that host yet. Use step 2 (Set up HTTPS on this server), "
            f"point DNS here, and open ports 80/443. Caddy proxies to 127.0.0.1:{ui_port}."
        )
        if local.get("local_ok"):
            return f"Workframe is healthy on this server. {base}"
        return base
    if "timed out" in msg or "timeout" in msg:
        return (
            "Timed out reaching that URL — DNS may not point to this server yet, or HTTPS is not ready. "
            "Add the A record, run Set up HTTPS, wait a minute, then retry."
        )
    if local.get("local_ok"):
        return "Workframe is running on this server; the public URL is not reachable from here yet."
    return "Check DNS, HTTPS (Caddy), and that the domain matches this server."


def url_test(app_base_url: str) -> dict[str, Any]:
    url = _normalize_app_base_url(app_base_url)
    if not url:
        raise ValueError("app_base_url required")
    host = _hostname_only(url)

    if _loopback_hostname(host):
        try:
            local = _local_stack_health()
            if local.get("local_ok"):
                return {
                    "ok": True,
                    "status": local.get("status"),
                    "url": url,
                    "checked_url": local.get("checked_url"),
                    "hint": "Loopback URL — verified via the UI proxy on this stack.",
                }
            return {
                "ok": False,
                "url": url,
                "error": str(local.get("error") or "local health check failed"),
                "hint": "Is the Workframe UI container running?",
            }
        except Exception as exc:
            return {
                "ok": False,
                "url": url,
                "error": str(exc),
                "hint": "Is the Workframe UI container running?",
            }

    health_url = f"{url.rstrip('/')}/api/health"
    local = _local_stack_health()
    try:
        return {**_fetch_health(health_url), "url": health_url}
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status": exc.code,
            "url": health_url,
            "error": str(exc),
            "hint": _url_test_hint(exc, local=local),
            "local_ok": bool(local.get("local_ok")),
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": health_url,
            "error": str(exc),
            "hint": _url_test_hint(exc, local=local),
            "local_ok": bool(local.get("local_ok")),
        }


def smtp_error_hint(exc: Exception) -> str:
    msg = str(exc).lower()
    if "smtp login failed" in msg or "535" in msg or "badcredentials" in msg:
        return "Check SMTP username and app password. For Gmail, use an App Password—not your normal password."
    if "smtp password is required" in msg:
        return "Enter the SMTP app password. Compose uses SMTP_PASS; onboarding saves it in stack config."
    if "rejected from address" in msg:
        return (
            "Gmail rejected that From address for this login. Leave From blank to send as your login email, "
            "or add the address under Gmail Settings → Accounts → Send mail as."
        )
    if "530" in msg and "authentication required" in msg:
        return "SMTP authentication did not complete. Check username, app password, and port (465=SSL, 587=STARTTLS)."
    if "connect" in msg or "timed out" in msg or "unexpectedly closed" in msg:
        return "Check SMTP host and port. Port 465 needs SSL; port 587 uses STARTTLS."
    if "certificate" in msg or "ssl" in msg:
        return "Try toggling TLS/SSL settings to match your provider."
    return "Double-check host, port, username, password, and From address, then try again."


def normalize_setup_https(host: str, port: int | str | None = None) -> tuple[str, int]:
    name = _hostname_only(host) or str(host or "").strip().lower()
    if not name or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", name, re.IGNORECASE):
        raise ValueError("valid hostname required")
    ui_port = int(port or os.environ.get("WORKFRAME_UI_PORT", "18644") or "18644")
    return name, ui_port


if __name__ == "__main__":
    assert dns_record_name("dev.example.com") == "dev"
    assert dns_record_name("example.com") == "@"
    assert apex_domain("dev.example.com") == "example.com"
    assert _loopback_hostname("127.0.0.1")
    assert _loopback_hostname("localhost")
    assert not _loopback_hostname("dev.example.com")
    import tempfile
    from pathlib import Path

    td = Path(tempfile.mkdtemp())
    os.environ["WORKFRAME_API_DATA_DIR"] = str(td)
    stack_config.patch_stack_config({"smtp": {"host": "smtp.test", "user": "a", "password": "b"}})
    assert not stack_config.smtp_tested()
    stack_config.mark_smtp_tested()
    assert stack_config.smtp_tested()
    stack_config.patch_stack_config({"smtp": {"host": "smtp.other"}})
    assert not stack_config.smtp_tested()
    print("install_api publish hints ok")
