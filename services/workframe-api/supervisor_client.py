"""WF-032 extract: workframe-supervisor HTTP client and gateway exec proxies."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _srv():
    import server as srv

    return srv


def _supervisor_ready() -> bool:
    return bool(_srv().SUPERVISOR_URL) and bool(_srv().SUPERVISOR_TOKEN)


def _supervisor_request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[int, Any]:
    """Proxy a JSON request to workframe-supervisor."""
    if not _srv().SUPERVISOR_URL:
        return 503, {"ok": False, "error": "WORKFRAME_SUPERVISOR_URL not configured"}
    if not _srv().SUPERVISOR_TOKEN:
        return 503, {"ok": False, "error": "WORKFRAME_SUPERVISOR_TOKEN not configured"}
    url = f"{_srv().SUPERVISOR_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {_srv().SUPERVISOR_TOKEN}",
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
        restart = not _srv()._install_window_open()
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
