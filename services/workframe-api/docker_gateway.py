"""WF-032 extract: Docker socket and gateway container exec helpers."""

from __future__ import annotations

import http.client
import json
import shlex
import socket
import urllib.parse
from typing import Any

import updates as stack_updates


def _srv():
    import server as srv

    return srv


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, unix_path: str):
        super().__init__("localhost")
        self.unix_path = unix_path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.unix_path)
        self.sock = sock


def _docker_request(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    if _srv().SECURE_MODE:
        raise RuntimeError("Docker socket access is disabled in SECURE_MODE")
    conn = _UnixHTTPConnection(_srv().DOCKER_SOCK)
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


def _docker_exec_detached(container: str, cmd: list[str], acting_profile: str = "") -> tuple[int, str]:
    if _srv()._exec_targets_runtime_profile_secrets(cmd, acting_profile):
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
    if _srv()._exec_targets_runtime_profile_secrets(cmd, acting_profile):
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


def _gateway_container_exec(cmd: list[str]) -> tuple[int, str]:
    """Run a command in the gateway container — via supervisor in SECURE_MODE."""
    if _srv().SECURE_MODE:
        return _srv()._supervisor_container_exec(cmd)
    return _docker_exec(_srv().GATEWAY_CONTAINER_NAME, cmd)


def _gateway_container_exec_detached(cmd: list[str]) -> tuple[int, str]:
    """Detached gateway exec — long-running jobs survive after exec returns."""
    if _srv().SECURE_MODE:
        return _srv()._supervisor_container_exec(cmd, detach=True)
    return _docker_exec_detached(_srv().GATEWAY_CONTAINER_NAME, cmd)


def _profile_home_container(profile: str) -> str:
    return f"/opt/data/profiles/{_srv().resolve_hermes_profile(profile)}"


def _gateway_exec(profile: str, args: list[str]) -> tuple[int, str]:
    """Run hermes CLI in the gateway container with specialist profile home."""
    prof = _srv().resolve_hermes_profile(profile)
    if _srv().SECURE_MODE:
        return _srv()._supervisor_gateway_exec(prof, args)
    cli = ["/opt/hermes/bin/hermes", "-p", prof, *args]
    if prof == _srv()._primary_profile():
        return _docker_exec(_srv().GATEWAY_CONTAINER_NAME, cli, acting_profile=prof)
    home = _profile_home_container(prof)
    inner = " ".join(shlex.quote(part) for part in cli)
    shell = (
        f"export HERMES_HOME={shlex.quote(home)} HOME={shlex.quote(home)}; "
        f"cd {shlex.quote(home)}; {inner}"
    )
    return _docker_exec(_srv().GATEWAY_CONTAINER_NAME, ["sh", "-lc", shell], acting_profile=prof)


def _hermes_agent_version() -> str:
    """Native Hermes semver from `hermes --version` inside the gateway container."""
    try:
        code, out = _gateway_exec(_srv()._primary_profile(), ["--version"])
        if code != 0:
            return ""
        return stack_updates.parse_hermes_version_output(out)
    except Exception:  # noqa: BLE001
        return ""
