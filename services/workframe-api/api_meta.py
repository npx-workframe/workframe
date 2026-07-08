"""WF-032 extract: /api/meta, Hermes dashboard bootstrap, and skills snapshot."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any


def _srv():
    import server as srv

    return srv


def _ui_build_stamp() -> dict[str, str]:
    """Read workframe-build.json from bundled UI static roots when present."""
    candidates: list[Path] = []
    for raw in (
        os.environ.get("WORKFRAME_UI_STATIC_DIR", ""),
        os.environ.get("WORKFRAME_PROJECT_ROOT", ""),
        os.environ.get("WORKFRAME_COMPOSE_DIR", ""),
        "/project",
        "/compose",
    ):
        root = Path(str(raw or "").strip())
        if not root.is_dir():
            continue
        candidates.extend([root / "workframe-ui" / "public", root])
    seen: set[str] = set()
    for root in candidates:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        stamp_path = root / "workframe-build.json"
        if not stamp_path.is_file():
            continue
        try:
            data = json.loads(stamp_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        version = str(data.get("package_version") or "").strip()
        if not version:
            continue
        return {
            "package_version": version,
            "bundled_at": str(data.get("bundled_at") or "").strip(),
            "git_ref": str(data.get("git_ref") or "").strip(),
        }
    return {}


def _installed_package_version() -> str:
    import updates

    versions = updates._read_installed_workframe_version(updates._project_root())
    return str(versions.get("package") or os.environ.get("WORKFRAME_API_VERSION") or "").strip()


def workframe_meta() -> dict[str, Any]:
    primary = _srv()._primary_profile()
    ui_build = _ui_build_stamp()
    package_version = _installed_package_version() or ui_build.get("package_version", "")
    payload: dict[str, Any] = {
        "ok": True,
        "project_name": _srv().PROJECT_NAME,
        "install_id": str(os.environ.get("WORKFRAME_INSTALL_ID") or "").strip(),
        "native_profile": primary,
        "native_agent_name": _srv()._native_display_name(),
        "native_model": _srv()._profile_model(primary) if primary else "",
        "app_base_url": _srv().APP_BASE_URL,
        "deployment_mode": _srv().DEPLOYMENT_MODE,
        "package_version": package_version,
        "workspace": {
            "content_root": _srv().CONTENT_ROOT.as_posix(),
            "root": _srv().WORKSPACE.as_posix(),
        },
    }
    if ui_build:
        payload["ui_build"] = ui_build
    return payload


def hermes_dashboard_gate_status(handler: BaseHTTPRequestHandler) -> int:
    """nginx auth_request helper: 204 allow, 403 deny."""
    if _srv().DEPLOYMENT_MODE == "single_user_local":
        return 204
    user_id = str(getattr(handler, "auth_user", "") or "").strip()
    if _srv().DEPLOYMENT_MODE == "trusted_team":
        if _srv().DEV_LOCAL_UNSAFE or user_id:
            return 204
        return 403
    if not user_id:
        return 403
    if str(getattr(handler, "auth_role", "") or "") in _srv().OWNER_ADMIN_ROLES:
        return 204
    return 403


def _dashboard_embedded_chat(internal_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{internal_url}/", timeout=_srv().DASHBOARD_HTTP_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return False
    chat_match = re.search(r"__HERMES_DASHBOARD_EMBEDDED_CHAT__=(true|false)", html)
    return (chat_match.group(1) == "true") if chat_match else False


def _dashboard_get(path: str) -> Any:
    internal_url = os.environ.get("HERMES_DASHBOARD_URL", "http://127.0.0.1:19119").rstrip("/")
    token = _srv()._dashboard_session_token(internal_url)
    req = urllib.request.Request(
        f"{internal_url}{path}",
        headers={"X-Hermes-Session-Token": token},
    )
    with urllib.request.urlopen(req, timeout=_srv().DASHBOARD_HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace") or "null")


def hermes_bootstrap(profile: str = "") -> dict[str, Any]:
    del profile  # ponytail: reserved for per-profile dashboard routing
    internal_url = os.environ.get("HERMES_DASHBOARD_URL", "http://127.0.0.1:19119").rstrip("/")
    public_url = os.environ.get("HERMES_DASHBOARD_PUBLIC_URL", internal_url).rstrip("/")
    try:
        token = _srv()._dashboard_session_token(internal_url)
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


def hermes_skills() -> list[dict[str, Any]]:
    """Installed skills from Hermes dashboard — same source as TUI /skills."""
    try:
        data = _dashboard_get("/api/skills")
    except ValueError:
        return []
    return data if isinstance(data, list) else []
