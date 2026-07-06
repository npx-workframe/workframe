"""WF-032 extract: profile_gateway."""
from __future__ import annotations

import json
import os
import queue
import re
import shlex
import shutil
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from http.server import BaseHTTPRequestHandler

import user_prefs


def _srv():
    import server as srv

    return srv


def _reload_runtime_profile_gateway(profile: str, *, wait_healthy: bool = True) -> None:
    """Reload Hermes after config.yaml change — gateway restart before stop+start."""
    prof = _srv().resolve_hermes_profile(profile)
    if not _srv()._is_runtime_profile_slug(prof) or prof == _srv()._primary_profile():
        return
    with _srv()._gateway_lifecycle_lock:
        if _profile_api_healthy(prof, timeout=0.5, use_cache=False):
            code, _out = _srv()._gateway_exec(prof, ["gateway", "restart"])
            if code == 0:
                _srv()._invalidate_profile_health_cache(prof)
                if wait_healthy:
                    _wait_profile_api_healthy(prof, attempts=48, delay=0.25)
                return
        _srv()._invalidate_profile_health_cache(prof)
        try:
            _srv().profile_gateway_lifecycle(prof, "stop", bootstrap_providers=False)
        except ValueError:
            pass
        _srv().profile_gateway_lifecycle(prof, "start", bootstrap_providers=False)
        if wait_healthy:
            _wait_profile_api_healthy(prof)


def _schedule_gateway_reload(profile: str) -> None:
    """ponytail: model-save hot path — yaml is sync; reload async (~7s, not ~45s)."""
    prof = _srv().resolve_hermes_profile(profile)
    if not _profile_api_healthy(prof, timeout=0.5, use_cache=False):
        return  # cold start on next bind via ensure_profile_api

    def _run() -> None:
        try:
            with _srv()._gateway_lifecycle_lock:
                _reload_runtime_profile_gateway(prof, wait_healthy=False)
        except Exception as exc:  # noqa: BLE001
            print(f"[workframe-api] gateway reload failed for {prof}: {exc}")

    threading.Thread(target=_run, name=f"gw-reload-{prof}", daemon=True).start()


def _restart_runtime_profile_gateway(profile: str) -> None:
    """Hermes api_server caches config.yaml — reload after lease rotation."""
    _reload_runtime_profile_gateway(profile, wait_healthy=True)
def _profile_api_port(profile: str) -> int:
    if profile == _srv()._primary_profile():
        return 8642
    # Stable per-profile range: 18610..18709
    base = 18610
    span = 100
    h = sum(ord(c) for c in profile) % span
    return base + h


def _configure_profile_api(profile: str) -> tuple[bool, str, int]:
    _srv()._normalize_profile_config_yaml(profile)
    prof = _srv().resolve_hermes_profile(profile)
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
        native = prof == _srv()._primary_profile()
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
    if profile == _srv()._primary_profile():
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
    code, out = _srv()._gateway_container_exec(
        ["/opt/hermes/.venv/bin/python", "-c", script],
    )
    return code == 0, out


def _disable_profile(prof: str) -> dict[str, Any]:
    port = _profile_api_port(prof)
    state = _srv().gateway_data(prof)
    if str(state.get("state") or "").lower() in {"running", "starting"}:
        code, out = _srv()._gateway_exec(prof, ["gateway", "stop"])
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
    code, out = _srv()._gateway_container_exec(
        ["/opt/hermes/.venv/bin/python", "-c", script],
    )
    if code != 0:
        raise ValueError(f"disable profile config failed: {out}")
    return {"ok": True, "profile": prof, "action": "disable", "state": "disabled", "api_port": port, "output": out.strip()}


def profile_gateway_lifecycle(profile: str, action: str, *, bootstrap_providers: bool = True) -> dict[str, Any]:
    prof = _srv().resolve_hermes_profile(profile)
    if action in {"start", "stop", "disable"}:
        _srv()._invalidate_gateway_registered_cache(prof)
        _srv()._invalidate_profile_health_cache(prof)
    if action not in {"start", "stop", "status", "disable"}:
        raise ValueError("invalid action")
    port = _profile_api_port(prof)
    if _srv().SECURE_MODE and prof != _srv()._primary_profile() and action in {"start", "stop", "disable"}:
        if action == "start":
            _srv()._normalize_profile_config_yaml(prof)
        return _srv()._supervisor_profile_lifecycle(prof, action)
    if prof == _srv()._primary_profile():
        if action == "disable":
            raise ValueError("cannot disable the native profile")
        if action == "status":
            state = _srv().gateway_data(prof)
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
    with _srv()._gateway_lifecycle_lock:
        if action == "start":
            if bootstrap_providers:
                _srv()._bootstrap_profile_providers(prof)
            ok, out, port = _configure_profile_api(prof)
            if not ok:
                raise ValueError(f"profile api config failed: {out}")
            ok, out = _patch_profile_gateway_run_script(prof)
            if not ok:
                raise ValueError(f"profile api run patch failed: {out}")
            state = _srv().gateway_data(prof)
            if str(state.get("state") or "").lower() in {"running", "starting"} and not _profile_api_healthy(prof):
                code, out = _srv()._gateway_exec(prof, ["gateway", "stop"])
                if code != 0:
                    raise ValueError(f"gateway stop failed: {out}")
                time.sleep(1.0)
        if action == "status":
            state = _srv().gateway_data(prof)
            ok = bool(state.get("ok")) and str(state.get("state") or "").lower() == "running"
            return {
                "ok": ok,
                "profile": prof,
                "action": action,
                "api_port": port,
                "state": state.get("state") or "unknown",
                "details": state,
            }
        code, out = _srv()._gateway_exec(prof, ["gateway", action])
        if code != 0:
            raise ValueError(f"gateway {action} failed: {out}")
        if action == "start" and not _wait_profile_api_healthy(prof):
            raise ValueError(f"profile api did not become healthy: {prof}")
    return {"ok": True, "profile": prof, "action": action, "api_port": port, "output": out.strip()}




def _profile_api_key(profile: str) -> str:
    return "workframe-local-key"


def _profile_turn_payload(profile: str, text: str, room_id: str = "") -> dict[str, Any]:
    message = text
    room_id = str(room_id or "").strip()
    if room_id:
        try:
            conn = _srv()._workframe_db()
            try:
                room = conn.execute(
                    """
                    SELECT room_type, agent_profile_id
                    FROM rooms WHERE id = ? AND deleted_at IS NULL
                    """,
                    (room_id,),
                ).fetchone()
                if room and _srv()._is_space_room(str(room["room_type"]), room["agent_profile_id"]):
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


def _profile_api_healthy(profile: str, timeout: float = 1.5, *, use_cache: bool = True) -> bool:
    try:
        prof = _srv().resolve_hermes_profile(profile)
    except ValueError:
        return False
    wait = max(1.0, float(timeout))
    if use_cache and wait >= 1.0:
        cached = _srv()._profile_health_cache.get(prof)
        if cached and time.monotonic() - cached[1] < _srv()._PROFILE_HEALTH_TTL_SEC:
            return cached[0]
    port = _profile_api_port(prof)
    key = _profile_api_key(prof)
    url = f"http://gateway:{port}/v1/health"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=wait) as resp:
            ok = int(resp.status) < 300
    except Exception:  # noqa: BLE001
        ok = False
    if use_cache and wait >= 1.0:
        _srv()._profile_health_cache[prof] = (ok, time.monotonic())
    return ok


def _wait_profile_api_healthy(profile: str, attempts: int = 60, delay: float = 0.5) -> bool:
    try:
        prof = _srv().resolve_hermes_profile(profile)
    except ValueError:
        return False
    if _profile_api_healthy(prof):
        return True
    for _ in range(attempts):
        if _profile_api_healthy(prof):
            return True
        time.sleep(delay)
    return False
def profile_gateway_stop(profile: str, run_id: str) -> dict[str, Any]:
    """Stop a running agent via the Hermes /v1/runs/{run_id}/stop API."""
    prof = _srv().resolve_validated_profile(profile)
    lifecycle = _srv().ensure_profile_api(prof)
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
    prof = _srv().resolve_validated_profile(profile)
    # First stop the current run
    stop_result = _srv().profile_gateway_stop(prof, run_id)
    if not stop_result.get("ok"):
        return stop_result
    # Then submit the steered input as a new run
    lifecycle = _srv().ensure_profile_api(prof)
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
