#!/usr/bin/env python3
"""workframe-supervisor — token-gated Docker exec for Hermes profile lifecycle."""

from __future__ import annotations

import http.client
import json
import os
import re
import shlex
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERMES_DATA = Path(os.environ.get("HERMES_DATA", "/opt/data"))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8090"))
VERSION = "0.1.0"
NATIVE_PROFILE = os.environ.get("WORKFRAME_NATIVE_PROFILE", "").strip()
DOCKER_SOCK = os.environ.get("DOCKER_SOCK", "/var/run/docker.sock")
GATEWAY_CONTAINER_NAME = os.environ.get("WORKFRAME_GATEWAY_CONTAINER", "workframe-gateway")
SUPERVISOR_TOKEN = (
    os.environ.get("WORKFRAME_SUPERVISOR_TOKEN")
    or os.environ.get("SUPERVISOR_TOKEN")
    or ""
).strip()
DEPLOYMENT_MODE = (os.environ.get("WORKFRAME_DEPLOYMENT_MODE") or "trusted_team").strip().lower()
ROUTES_JSON = HERMES_DATA / "workframe" / "routes.json"
SCRIPTS_DIR = Path(os.environ.get("WORKFRAME_SCRIPTS_DIR", "/opt/install/scripts"))
COMPOSE_DIR = Path(os.environ.get("WORKFRAME_COMPOSE_DIR", "/compose"))


def _compose_file_args() -> list[str]:
    """Absolute host bind paths when compose CLI runs inside supervisor (relative paths break)."""
    args = ["-f", str(COMPOSE_DIR / "docker-compose.yml")]
    host_root = os.environ.get("WORKFRAME_HOST_PROJECT_ROOT", "").strip()
    bindings = COMPOSE_DIR / "docker-compose.host-bindings.yml"
    if host_root and bindings.is_file():
        args.extend(["-f", str(bindings)])
    return args


def _compose_run(argv: list[str], *, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    cmd = ["docker", "compose", *_compose_file_args(), *argv]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(COMPOSE_DIR))


from profile_secret_policy import exec_blocked_for_profile


def _exec_targets_runtime_profile_secrets(cmd: list[str], acting_profile: str = "") -> bool:
    if DEPLOYMENT_MODE == "single_user_local":
        return False
    return exec_blocked_for_profile(cmd, acting_profile)


def _stack_apply(target: str, *, workframe_version: str = "", workframe_tarball: str = "") -> dict[str, Any]:
    target = str(target or "all").strip().lower()
    if target == "gateway-restart":
        script = SCRIPTS_DIR / "restart-gateway-hermes.sh"
        if not script.is_file():
            raise ValueError("restart_script_missing")
        proc = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(COMPOSE_DIR) if COMPOSE_DIR.is_dir() else None,
        )
        log = f"=== {script} (exit {proc.returncode}) ===\n{proc.stdout}\n{proc.stderr}"
        if proc.returncode != 0:
            raise ValueError("restart_failed:gateway")
        return {"ok": True, "target": "gateway", "log": log[-12000:]}
    if target not in {"hermes", "workframe", "all"}:
        raise ValueError("invalid_update_target")
    scripts: list[Path] = []
    if target in {"hermes", "all"}:
        p = SCRIPTS_DIR / "apply-update-hermes.sh"
        if not p.is_file():
            raise ValueError("update_script_missing:hermes")
        scripts.append(p)
    if target in {"workframe", "all"}:
        p = SCRIPTS_DIR / "apply-update-workframe.sh"
        if not p.is_file():
            raise ValueError("update_script_missing:workframe")
        scripts.append(p)
    env = os.environ.copy()
    version = str(workframe_version or "").strip()
    tarball = str(workframe_tarball or "").strip()
    env["WORKFRAME_UPDATE_FROM_SUPERVISOR"] = "1"
    if tarball and target in {"workframe", "all"}:
        env["WORKFRAME_UPDATE_TARBALL"] = tarball
        if version:
            env["WORKFRAME_UPDATE_VERSION"] = version
    elif version and target in {"workframe", "all"}:
        env["WORKFRAME_UPDATE_ALLOW_NPM"] = "1"
        env["WORKFRAME_UPDATE_VERSION"] = version
    logs: list[str] = []
    for script in scripts:
        proc = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            timeout=900,
            env=env,
            cwd=str(COMPOSE_DIR) if COMPOSE_DIR.is_dir() else None,
        )
        logs.append(f"=== {script} (exit {proc.returncode}) ===\n{proc.stdout}\n{proc.stderr}")
        if proc.returncode != 0:
            raise ValueError(f"update_failed:{script.name}")
    return {"ok": True, "target": target, "log": "\n".join(logs)[-12000:]}


_DEVICE_OAUTH_AUTH_IDS = frozenset({"openai-codex", "nous"})


def _gateway_image_digest() -> tuple[str, str]:
    status, data = _docker_request("GET", f"/containers/{urllib.parse.quote(GATEWAY_CONTAINER_NAME, safe='')}/json")
    if status != 200 or not isinstance(data, dict):
        return "", ""
    image_id = str(data.get("Image") or "")
    ist, idata = _docker_request("GET", f"/images/{image_id}/json")
    digest = ""
    ref = os.environ.get("WORKFRAME_HERMES_IMAGE", "nousresearch/hermes-agent")
    if ist == 200 and isinstance(idata, dict):
        digests = idata.get("RepoDigests") or []
        if digests:
            digest = str(digests[0]).split("@")[-1]
        tags = idata.get("RepoTags") or []
        if tags:
            ref = str(tags[0])
    return digest, ref


def _hermes_device_oauth_start(home: str, hermes_auth_id: str, log_path: str) -> tuple[int, str]:
    home = str(home or "").strip()
    hermes_auth_id = str(hermes_auth_id or "").strip()
    log_path = str(log_path or "").strip()
    if not home.startswith("/opt/data/profiles/") or not log_path.startswith("/opt/data/profiles/"):
        raise ValueError("invalid profile home")
    if hermes_auth_id not in _DEVICE_OAUTH_AUTH_IDS:
        raise ValueError("invalid_device_oauth_provider")
    auth_cmd = " ".join(shlex.quote(part) for part in ["auth", "add", hermes_auth_id])
    shell = (
        f"mkdir -p {shlex.quote(home)}; "
        f"chown -R hermes:hermes {shlex.quote(home)}; "
        f"su -s /bin/sh hermes -c "
        f"'export HERMES_HOME={shlex.quote(home)} HOME={shlex.quote(home)}; "
        f"cd {shlex.quote(home)}; "
        f"/opt/hermes/bin/hermes {auth_cmd} >> {shlex.quote(log_path)} 2>&1'"
    )
    return _docker_exec_detached(GATEWAY_CONTAINER_NAME, ["sh", "-lc", shell])


def _host_setup_public_https(host: str, port: int) -> dict[str, Any]:
    host = str(host or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host, re.IGNORECASE):
        raise ValueError("invalid host")
    port = int(port)
    if port < 1 or port > 65535:
        raise ValueError("invalid port")
    root = os.environ.get("WORKFRAME_HOST_PROJECT_ROOT", "").strip() or "/opt/workframe/repo"
    script = f"{root}/scripts/workframe/setup-public-https.sh"
    # ponytail: chroot on host via docker.sock — API container cannot run apt/systemctl on host.
    cmd = [
        "docker",
        "run",
        "--rm",
        "--pull=missing",
        "--privileged",
        "--pid=host",
        "-v",
        "/:/host",
        "debian:bookworm-slim",
        "chroot",
        "/host",
        "bash",
        script,
        host,
        str(port),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    log = f"=== setup-public-https {host}:{port} (exit {proc.returncode}) ===\n{proc.stdout}\n{proc.stderr}"
    if proc.returncode != 0:
        raise ValueError(log[-2000:] or "setup_public_https_failed")
    return {"ok": True, "host": host, "port": port, "log": log[-8000:]}


def _host_set_compose_public_url(public_url: str, *, restart: bool = True) -> dict[str, Any]:
    public_url = str(public_url or "").strip()
    if not public_url:
        raise ValueError("url required")
    compose_dir = Path(os.environ.get("WORKFRAME_COMPOSE_DIR", "/compose"))
    env_path = compose_dir / ".env"
    scripts = Path(os.environ.get("WORKFRAME_SCRIPTS_DIR", "/opt/install/scripts"))
    script = scripts / "set-compose-public-url.mjs"
    if not script.is_file():
        raise ValueError("set-compose_public_url_script_missing")
    proc = subprocess.run(
        ["node", str(script), public_url, "--env", str(env_path)],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(compose_dir),
    )
    log = f"=== set-compose-public-url (exit {proc.returncode}) ===\n{proc.stdout}\n{proc.stderr}"
    if proc.returncode != 0:
        raise ValueError(log[-2000:] or "set_compose_public_url_failed")
    if restart:
        # ponytail: --no-deps — never touch workframe-supervisor (partial up was killing it mid-install).
        restart_proc = _compose_run(["up", "-d", "--no-deps", "workframe-api", "gateway"], timeout=120)
        log += (
            f"\n=== compose up --no-deps workframe-api gateway (exit {restart_proc.returncode}) ===\n"
            f"{restart_proc.stdout}\n{restart_proc.stderr}"
        )
        if restart_proc.returncode != 0:
            raise ValueError(log[-2000:] or "compose_restart_failed")
    try:
        payload = json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        payload = {"ok": True}
    payload["log"] = log[-8000:]
    payload["restarted"] = restart
    return payload


def _primary_profile() -> str:
    if NATIVE_PROFILE and (HERMES_DATA / "profiles" / NATIVE_PROFILE).is_dir():
        return NATIVE_PROFILE
    root = HERMES_DATA / "profiles"
    if not root.is_dir():
        return ""
    names = sorted(p.name for p in root.iterdir() if p.is_dir())
    return names[0] if names else ""


def _profile_dir(profile: str) -> Path:
    return HERMES_DATA / "profiles" / profile


def safe_profile_slug(value: str) -> str:
    slug = (value or "").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", slug):
        raise ValueError("invalid profile")
    return slug


def profile_exists(profile: str) -> bool:
    return _profile_dir(profile).is_dir()


def load_routes() -> dict[str, Any]:
    default_profile = _primary_profile()
    raw_routes: list[dict[str, Any]] = []
    if ROUTES_JSON.is_file():
        try:
            data = json.loads(ROUTES_JSON.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("routes"), list):
                raw_routes = [r for r in data["routes"] if isinstance(r, dict)]
        except (OSError, json.JSONDecodeError):
            pass
    if not raw_routes:
        root = HERMES_DATA / "profiles"
        if root.is_dir():
            for p in sorted(root.iterdir()):
                if p.is_dir():
                    raw_routes.append({"profile": p.name})
    routes = []
    seen: set[str] = set()
    for row in raw_routes:
        slug = str(row.get("profile") or "").strip()
        if slug and profile_exists(slug) and slug not in seen:
            routes.append({"profile": slug})
            seen.add(slug)
    if default_profile and default_profile not in seen and profile_exists(default_profile):
        routes.insert(0, {"profile": default_profile})
        seen.add(default_profile)
    native = safe_profile_slug(NATIVE_PROFILE) if NATIVE_PROFILE else ""
    if native and native not in seen and profile_exists(native):
        routes.insert(0, {"profile": native})
        seen.add(native)
    return {"default_profile": default_profile, "routes": routes}


def resolve_validated_profile(profile: str) -> str:
    slug = safe_profile_slug(str(profile or _primary_profile()).strip())
    allowed = {r["profile"] for r in load_routes()["routes"]}
    if slug not in allowed:
        raise ValueError(f"unknown profile: {slug}")
    if not profile_exists(slug):
        raise ValueError(f"profile not installed: {slug}")
    return slug


_RUNTIME_PROFILE_RE = re.compile(r"^u-[a-z0-9][a-z0-9-]{0,62}$")


def _is_runtime_profile_slug(slug: str) -> bool:
    return bool(_RUNTIME_PROFILE_RE.fullmatch(str(slug or "").strip()))


def resolve_hermes_profile(profile: str) -> str:
    """Workspace routes or per-user runtime u-* dirs on disk."""
    slug = safe_profile_slug(str(profile or _primary_profile()).strip())
    if _is_runtime_profile_slug(slug) and profile_exists(slug):
        return slug
    return resolve_validated_profile(slug)


def gateway_data(profile: str) -> dict[str, Any]:
    path = _profile_dir(profile) / "gateway_state.json"
    base: dict[str, Any] = {
        "ok": False,
        "exists": path.is_file(),
        "state": "unknown",
        "platforms": {},
        "updated_at": None,
        "uptime_seconds": None,
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
    base.update(
        {
            "ok": True,
            "state": raw.get("gateway_state") or raw.get("state") or "unknown",
            "pid": raw.get("pid"),
            "platforms": raw.get("platforms") or {},
            "updated_at": raw.get("updated_at"),
            "uptime_seconds": uptime,
        }
    )
    return base


def _profile_api_port(profile: str) -> int:
    if profile == _primary_profile():
        return 8642
    base = 18610
    span = 100
    h = sum(ord(c) for c in profile) % span
    return base + h


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, unix_path: str):
        super().__init__("localhost")
        self.unix_path = unix_path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.unix_path)
        self.sock = sock


def _docker_request(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
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


def _profile_home_container(profile: str) -> str:
    return f"/opt/data/profiles/{safe_profile_slug(profile)}"


def _gateway_exec(profile: str, args: list[str]) -> tuple[int, str]:
    prof = resolve_hermes_profile(profile)
    cli = ["/opt/hermes/bin/hermes", "-p", prof, *args]
    if _exec_targets_runtime_profile_secrets(cli, prof):
        return 1, "blocked: runtime profile credential paths are not readable via gateway exec"
    if prof == _primary_profile():
        return _docker_exec(GATEWAY_CONTAINER_NAME, cli, acting_profile=prof)
    home = _profile_home_container(prof)
    inner = " ".join(shlex.quote(part) for part in cli)
    shell = (
        f"export HERMES_HOME={shlex.quote(home)} HOME={shlex.quote(home)}; "
        f"cd {shlex.quote(home)}; {inner}"
    )
    return _docker_exec(GATEWAY_CONTAINER_NAME, ["sh", "-lc", shell], acting_profile=prof)


def _configure_profile_api(profile: str) -> tuple[bool, str, int]:
    port = _profile_api_port(profile)
    script = (
        "import yaml\n"
        "from pathlib import Path\n"
        f"d=Path('/opt/data/profiles/{profile}')\n"
        "p=d/'config.yaml'\n"
        "cfg={}\n"
        "if p.exists():\n"
        " cfg=yaml.safe_load(p.read_text(encoding='utf-8')) or {}\n"
        "plats=cfg.setdefault('platforms',{})\n"
        f"native={'True' if profile == _primary_profile() else 'False'}\n"
        "if not native:\n"
        " api_only=plats.get('api_server', {}) if isinstance(plats.get('api_server', {}), dict) else {}\n"
        " plats={'api_server': api_only}\n"
        " for name in ('discord','telegram','slack','whatsapp','webhook','cron'):\n"
        "  plats[name]={'enabled': False}\n"
        " cfg['platforms']=plats\n"
        "api=plats.setdefault('api_server',{})\n"
        "api['enabled']=True\n"
        "extra=api.setdefault('extra',{})\n"
        "extra['host']='0.0.0.0'\n"
        f"extra['port']={port}\n"
        "if not extra.get('key'):\n"
        " extra['key']='workframe-local-key'\n"
        "p.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding='utf-8')\n"
        "print('ok')\n"
    )
    code, out = _docker_exec(GATEWAY_CONTAINER_NAME, ["/opt/hermes/.venv/bin/python", "-c", script])
    return code == 0, out, port


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
    code, out = _docker_exec(GATEWAY_CONTAINER_NAME, ["/opt/hermes/.venv/bin/python", "-c", script])
    return code == 0, out


def _profile_api_healthy(profile: str, timeout: float = 1.5) -> bool:
    """Check profile API from inside the gateway container.

    ponytail: supervisor stays on control-net only; gateway DNS lives on workframe-net.
    """
    port = _profile_api_port(profile)
    wait = max(1.0, float(timeout))
    script = (
        "import sys,urllib.request\n"
        f"u='http://127.0.0.1:{port}/v1/health'\n"
        "r=urllib.request.Request(u,headers={'Authorization':'Bearer workframe-local-key'},method='GET')\n"
        "try:\n"
        f" urllib.request.urlopen(r,timeout={wait}); print('ok')\n"
        "except Exception as e:\n"
        " print(e,file=sys.stderr); sys.exit(1)\n"
    )
    code, _ = _docker_exec(
        GATEWAY_CONTAINER_NAME,
        ["/opt/hermes/.venv/bin/python", "-c", script],
    )
    return code == 0


def profile_gateway_lifecycle(profile: str, action: str) -> dict[str, Any]:
    prof = resolve_hermes_profile(profile)
    if action not in {"start", "stop", "status", "disable"}:
        raise ValueError("invalid action")
    port = _profile_api_port(prof)
    primary = _primary_profile()
    if prof == primary:
        if action == "disable":
            raise ValueError("cannot disable the native profile")
        if action == "stop":
            raise ValueError("cannot stop the native profile")
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
    if action == "status":
        state = gateway_data(prof)
        ok = bool(state.get("ok")) and str(state.get("state") or "").lower() == "running"
        return {
            "ok": ok,
            "profile": prof,
            "action": action,
            "api_port": port,
            "state": state.get("state") or "unknown",
            "pid": state.get("pid"),
            "uptime_seconds": state.get("uptime_seconds"),
            "updated_at": state.get("updated_at"),
            "platforms": state.get("platforms") or {},
        }
    if action == "disable":
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
            f"Path('/opt/data/profiles/{prof}/.disabled').write_text('disabled by supervisor\n', encoding='utf-8')\n"
            "print('ok')\n"
        )
        code, out = _docker_exec(GATEWAY_CONTAINER_NAME, ["/opt/hermes/.venv/bin/python", "-c", script])
        if code != 0:
            raise ValueError(f"disable profile config failed: {out}")
        return {"ok": True, "profile": prof, "action": "disable", "state": "disabled", "api_port": port}
    if action == "start":
        if _profile_api_healthy(prof):
            return {
                "ok": True,
                "profile": prof,
                "action": "start",
                "state": "running",
                "api_port": port,
                "detail": "already running",
            }
        ok, out, port = _configure_profile_api(prof)
        if not ok:
            raise ValueError(f"profile api config failed: {out}")
        ok, out = _patch_profile_gateway_run_script(prof)
        if not ok:
            raise ValueError(f"profile api run patch failed: {out}")
        state = gateway_data(prof)
        if str(state.get("state") or "").lower() in {"running", "starting"}:
            code, out = _gateway_exec(prof, ["gateway", "stop"])
            if code != 0:
                raise ValueError(f"gateway stop failed: {out}")
            time.sleep(1.0)
    code, out = _gateway_exec(prof, ["gateway", action])
    if code != 0:
        raise ValueError(f"gateway {action} failed: {out}")
    if action == "start":
        for _ in range(60):
            if _profile_api_healthy(prof):
                break
            time.sleep(0.5)
        else:
            raise ValueError(f"profile api did not become healthy: {prof}")
    state = gateway_data(prof).get("state") or action
    return {"ok": True, "profile": prof, "action": action, "state": state, "api_port": port, "output": out.strip()}


def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
    if not SUPERVISOR_TOKEN:
        return False
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return secrets_compare(auth[7:].strip(), SUPERVISOR_TOKEN)
    return False


def secrets_compare(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    server_version = "workframe-supervisor/0.1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _json(self, status: int, payload: Any) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/health":
            return self._json(200, {"ok": True, "service": "workframe-supervisor", "version": VERSION})
        if not _auth_ok(self):
            return self._json(401, {"ok": False, "error": "unauthorized"})
        if path == "/v1/profile.status":
            qs = urllib.parse.parse_qs(parsed.query)
            profile = (qs.get("profile") or [""])[0]
            if not profile:
                return self._json(400, {"ok": False, "error": "profile required"})
            try:
                return self._json(200, profile_gateway_lifecycle(profile, "status"))
            except ValueError as exc:
                return self._json(400, {"ok": False, "error": str(exc)})
        if path == "/v1/stack.status":
            profiles = []
            for row in load_routes()["routes"]:
                slug = row["profile"]
                state = gateway_data(slug)
                profiles.append(
                    {
                        "profile": slug,
                        "native": slug == _primary_profile(),
                        "state": state.get("state") or "unknown",
                        "api_port": _profile_api_port(slug),
                    }
                )
            return self._json(
                200,
                {"ok": True, "profiles": profiles, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            )
        if path == "/v1/gateway.image":
            digest, ref = _gateway_image_digest()
            return self._json(
                200,
                {
                    "ok": bool(digest or ref),
                    "digest": digest,
                    "ref": ref,
                    "container": GATEWAY_CONTAINER_NAME,
                },
            )
        return self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if not _auth_ok(self):
            return self._json(401, {"ok": False, "error": "unauthorized"})
        try:
            body = self._read_json()
        except json.JSONDecodeError:
            return self._json(400, {"ok": False, "error": "invalid json"})
        action_map = {
            "/v1/profile.start": "start",
            "/v1/profile.stop": "stop",
            "/v1/profile.disable": "disable",
        }
        if path not in action_map:
            if path == "/v1/gateway.exec":
                profile = str(body.get("profile") or "").strip()
                args = body.get("args")
                if not profile:
                    return self._json(400, {"ok": False, "error": "profile required"})
                if not isinstance(args, list) or not args:
                    return self._json(400, {"ok": False, "error": "args required"})
                try:
                    prof = resolve_hermes_profile(profile)
                    cli_args = [str(part) for part in args]
                    code, out = _gateway_exec(prof, cli_args)
                    return self._json(
                        200,
                        {"ok": code == 0, "profile": prof, "exit_code": code, "output": out},
                    )
                except ValueError as exc:
                    return self._json(400, {"ok": False, "error": str(exc)})
            if path == "/v1/gateway.container_exec":
                if os.environ.get("WORKFRAME_SUPERVISOR_ALLOW_RAW_EXEC", "0") != "1":
                    return self._json(403, {"ok": False, "error": "raw_container_exec_disabled"})
                # ponytail: opt-in only (WORKFRAME_SUPERVISOR_ALLOW_RAW_EXEC=1); default off (0022 N1)
                args = body.get("args")
                if not isinstance(args, list) or not args:
                    return self._json(400, {"ok": False, "error": "args required"})
                detach = bool(body.get("detach"))
                try:
                    cli_args = [str(part) for part in args]
                    if detach:
                        code, out = _docker_exec_detached(GATEWAY_CONTAINER_NAME, cli_args)
                    else:
                        code, out = _docker_exec(GATEWAY_CONTAINER_NAME, cli_args)
                    return self._json(
                        200,
                        {"ok": code == 0, "exit_code": code, "output": out, "detached": detach},
                    )
                except Exception as exc:  # noqa: BLE001
                    return self._json(500, {"ok": False, "error": str(exc)})
            if path == "/v1/stack.apply":
                target = str(body.get("target") or "all").strip().lower()
                workframe_version = str(body.get("workframe_version") or "").strip()
                workframe_tarball = str(body.get("workframe_tarball") or "").strip()
                try:
                    return self._json(
                        200,
                        _stack_apply(
                            target,
                            workframe_version=workframe_version,
                            workframe_tarball=workframe_tarball,
                        ),
                    )
                except ValueError as exc:
                    return self._json(400, {"ok": False, "error": str(exc)})
                except Exception as exc:  # noqa: BLE001
                    return self._json(500, {"ok": False, "error": str(exc)})
            if path == "/v1/hermes.device_oauth_start":
                home = str(body.get("home") or "").strip()
                hermes_auth_id = str(body.get("hermes_auth_id") or "").strip()
                log_path = str(body.get("log_path") or "").strip()
                try:
                    code, out = _hermes_device_oauth_start(home, hermes_auth_id, log_path)
                    return self._json(
                        200,
                        {"ok": code == 0, "exit_code": code, "output": out, "detached": True},
                    )
                except ValueError as exc:
                    return self._json(400, {"ok": False, "error": str(exc)})
                except Exception as exc:  # noqa: BLE001
                    return self._json(500, {"ok": False, "error": str(exc)})
            if path == "/v1/host.setup_public_https":
                host = str(body.get("host") or "").strip()
                try:
                    port = int(body.get("port") or os.environ.get("WORKFRAME_UI_PORT", "18644"))
                except (TypeError, ValueError):
                    return self._json(400, {"ok": False, "error": "invalid port"})
                try:
                    return self._json(200, _host_setup_public_https(host, port))
                except ValueError as exc:
                    return self._json(400, {"ok": False, "error": str(exc)})
                except Exception as exc:  # noqa: BLE001
                    return self._json(500, {"ok": False, "error": str(exc)})
            if path == "/v1/host.set_compose_public_url":
                public_url = str(body.get("url") or body.get("app_base_url") or "").strip()
                restart = body.get("restart", True) is not False
                try:
                    return self._json(200, _host_set_compose_public_url(public_url, restart=restart))
                except ValueError as exc:
                    return self._json(400, {"ok": False, "error": str(exc)})
                except Exception as exc:  # noqa: BLE001
                    return self._json(500, {"ok": False, "error": str(exc)})
            if path == "/v1/hermes.user_exec":
                home = str(body.get("home") or "").strip()
                args = body.get("args")
                if not home or not home.startswith("/opt/data/profiles/"):
                    return self._json(400, {"ok": False, "error": "home required"})
                slug = safe_profile_slug(home.rsplit("/", 1)[-1])
                home = f"/opt/data/profiles/{slug}"
                if not isinstance(args, list) or not args:
                    return self._json(400, {"ok": False, "error": "args required"})
                inner = " ".join(shlex.quote(str(part)) for part in args)
                shell = (
                    f"export HERMES_HOME={shlex.quote(home)} HOME={shlex.quote(home)}; "
                    f"mkdir -p {shlex.quote(home)}; cd {shlex.quote(home)}; "
                    f"/opt/hermes/bin/hermes {inner}"
                )
                code, out = _docker_exec(GATEWAY_CONTAINER_NAME, ["sh", "-lc", shell], acting_profile=slug)
                return self._json(200, {"ok": code == 0, "exit_code": code, "output": out})
            return self._json(404, {"ok": False, "error": "not found"})
        profile = str(body.get("profile") or "").strip()
        if not profile:
            return self._json(400, {"ok": False, "error": "profile required"})
        try:
            return self._json(200, profile_gateway_lifecycle(profile, action_map[path]))
        except ValueError as exc:
            return self._json(400, {"ok": False, "error": str(exc)})


def main() -> None:
    if not SUPERVISOR_TOKEN:
        raise SystemExit("WORKFRAME_SUPERVISOR_TOKEN is required")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"workframe-supervisor listening on {HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
