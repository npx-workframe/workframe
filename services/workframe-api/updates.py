"""Admin stack updates — version checks + safe in-place apply (preserves runtime/DB)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HERMES_IMAGE = os.environ.get("WORKFRAME_HERMES_IMAGE", "nousresearch/hermes-agent")
HERMES_TAG = os.environ.get("WORKFRAME_HERMES_TAG", "latest")
NPM_PACKAGE = os.environ.get("WORKFRAME_NPM_PACKAGE", "create-workframe")
RELEASES_URL = str(os.environ.get("WORKFRAME_RELEASES_URL", "")).strip()
DOCKER_SOCK = os.environ.get("DOCKER_SOCK", "/var/run/docker.sock")
GATEWAY_CONTAINER = os.environ.get("WORKFRAME_GATEWAY_CONTAINER", "workframe-gateway")
API_VERSION = str(os.environ.get("WORKFRAME_API_VERSION", "")).strip()


def _version_tuple(raw: str) -> tuple[int, ...]:
    text = re.sub(r"^workframe-api-", "", str(raw or "").strip())
    nums: list[int] = []
    for part in re.split(r"[.+_-]", text):
        if part.isdigit():
            nums.append(int(part))
        elif nums:
            break
    return tuple(nums)


def _version_lt(current: str, latest: str) -> bool:
    cur = str(current or "").strip()
    lat = str(latest or "").strip()
    if not lat:
        return False
    if not cur:
        return True
    return _version_tuple(cur) < _version_tuple(lat)


def _http_json(url: str, timeout: float = 12.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "workframe-api"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _npm_latest_version() -> str:
    data = _http_json(f"https://registry.npmjs.org/{urllib.parse.quote(NPM_PACKAGE)}/latest")
    return str(data.get("version") or "").strip()


def _docker_hub_digest(repo: str, tag: str) -> str:
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags/{urllib.parse.quote(tag)}"
    data = _http_json(url)
    # ponytail: tag digest matches docker pull :tag RepoDigests; images[0] may be arm64 on multi-arch repos
    top = str(data.get("digest") or "").strip()
    if top:
        return top
    for entry in data.get("images") or []:
        if not isinstance(entry, dict) or not entry.get("digest"):
            continue
        if entry.get("architecture") == "amd64" and entry.get("os") == "linux":
            return str(entry["digest"]).strip()
    for entry in data.get("images") or []:
        if isinstance(entry, dict) and entry.get("digest"):
            return str(entry["digest"]).strip()
    return ""


def _docker_sock_request(method: str, path: str, body: bytes | None = None) -> tuple[int, Any]:
    import http.client
    import socket as pysocket

    if not Path(DOCKER_SOCK).exists():
        return 0, {"error": "docker_socket_missing"}
    conn = http.client.HTTPConnection("localhost", timeout=120)
    conn.sock = pysocket.socket(pysocket.AF_UNIX, pysocket.SOCK_STREAM)
    conn.sock.connect(DOCKER_SOCK)
    headers = {"Content-Type": "application/json"} if body else {}
    conn.request(method, path, body=body, headers=headers)
    resp = conn.getresponse()
    raw = resp.read()
    conn.close()
    if not raw:
        return resp.status, {}
    try:
        return resp.status, json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return resp.status, raw.decode("utf-8", errors="replace")


def _container_image_digest(name: str) -> tuple[str, str]:
    status, data = _docker_sock_request("GET", f"/containers/{name}/json")
    if status != 200 or not isinstance(data, dict):
        return "", ""
    image_id = str(data.get("Image") or "")
    ist, idata = _docker_sock_request("GET", f"/images/{image_id}/json")
    digest = ""
    ref = HERMES_IMAGE
    if ist == 200 and isinstance(idata, dict):
        digests = idata.get("RepoDigests") or []
        if digests:
            digest = str(digests[0]).split("@")[-1]
        tags = idata.get("RepoTags") or []
        if tags:
            ref = str(tags[0])
    return digest, ref


def _read_installed_workframe_version(project_root: Path) -> dict[str, str]:
    out = {"api": API_VERSION, "package": "", "manifest_generator": ""}
    manifest = project_root / "workframe-manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            out["package"] = str(data.get("package_version") or "")
            out["manifest_generator"] = str(data.get("generator") or "")
        except Exception:  # noqa: BLE001
            pass
    if not out["api"]:
        try:
            import server as _server  # noqa: WPS433

            out["api"] = str(getattr(_server, "VERSION", ""))
        except Exception:  # noqa: BLE001
            pass
    if not out["package"]:
        out["package"] = out["api"]
    return out


def _compose_dir() -> Path:
    for raw in (
        os.environ.get("WORKFRAME_HOST_COMPOSE_DIR", ""),
        os.environ.get("WORKFRAME_COMPOSE_DIR", ""),
        os.environ.get("WORKFRAME_PROJECT_ROOT", ""),
        "/compose",
        "/project",
    ):
        p = Path(str(raw or "").strip())
        if p.is_dir() and (p / "docker-compose.yml").is_file():
            return p
    return Path(".")


def _project_root() -> Path:
    for raw in (os.environ.get("WORKFRAME_PROJECT_ROOT", ""), "/project", os.environ.get("WORKFRAME_COMPOSE_DIR", "")):
        p = Path(str(raw or "").strip())
        if p.is_dir() and (p / "workframe-manifest.json").is_file():
            return p
    for raw in (os.environ.get("WORKFRAME_PROJECT_ROOT", ""), "/project", os.environ.get("WORKFRAME_COMPOSE_DIR", "")):
        p = Path(str(raw or "").strip())
        if p.is_dir() and (p / "docker-compose.yml").is_file():
            return p
    return _compose_dir()


def _script_path(name: str) -> Path | None:
    roots = [
        Path(f"/opt/install/scripts/{name}"),
        Path(f"/opt/install/scripts/workframe/{name}"),
    ]
    mode = str(os.environ.get("WORKFRAME_DEPLOYMENT_MODE") or "trusted_team").strip().lower()
    if mode == "single_user_local":
        roots.extend(
            [
                _project_root() / "scripts" / "workframe" / name,
                _project_root() / "scripts" / name,
            ],
        )
    for path in roots:
        if path.is_file():
            return path
    return None


def _host_compose_ready() -> bool:
    host_raw = str(os.environ.get("WORKFRAME_HOST_COMPOSE_DIR", "")).strip()
    if not host_raw:
        return False
    host = Path(host_raw)
    if host.is_dir() and (host / "docker-compose.yml").is_file():
        return True
    # ponytail: Windows host paths are not visible inside the API container — trust /compose mount
    compose = _compose_dir()
    return compose.joinpath("docker-compose.yml").is_file()


def _docker_apply_ready() -> tuple[bool, str | None]:
    if not Path(DOCKER_SOCK).exists():
        return False, "Docker socket is not available to the API container."
    if not _compose_dir().joinpath("docker-compose.yml").is_file():
        return False, "docker-compose.yml was not found for this stack."
    if not _host_compose_ready():
        return False, (
            "Set WORKFRAME_HOST_COMPOSE_DIR to the host compose folder so updates run on the Docker host."
        )
    return True, None


def _product_state(*, update_available: bool, can_update: bool) -> str:
    if update_available and can_update:
        return "available"
    if update_available:
        return "blocked"
    return "current"


def parse_hermes_version_output(text: str) -> str:
    """Extract semver from `hermes --version` stdout."""
    match = re.search(r"Hermes Agent v(\d+\.\d+\.\d+)", str(text or ""))
    return match.group(1) if match else ""


def _read_hermes_agent_version() -> str:
    """Native Hermes semver via gateway exec (lazy import avoids server load cycle)."""
    try:
        import server as _server  # noqa: WPS433

        return _server._hermes_agent_version()
    except Exception:  # noqa: BLE001
        return ""


def _releases_manifest() -> dict[str, Any]:
    if not RELEASES_URL:
        return {}
    try:
        return _http_json(RELEASES_URL)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}


def updates_available(*, desktop_version: str = "", hermes_agent_version: str = "") -> dict[str, Any]:
    compose_dir = _compose_dir()
    project_root = _project_root()
    docker_ok = Path(DOCKER_SOCK).exists()
    installed = _read_installed_workframe_version(project_root)

    npm_latest = ""
    try:
        npm_latest = _npm_latest_version()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
        pass

    releases = _releases_manifest()
    workframe_latest = str(releases.get("workframe") or releases.get("create_workframe") or npm_latest or "")
    desktop_latest = str(releases.get("desktop") or os.environ.get("WORKFRAME_DESKTOP_LATEST", "0.1.0"))

    installed_pkg = installed.get("package") or installed.get("api") or ""
    workframe_update = bool(workframe_latest and _version_lt(installed_pkg, workframe_latest))

    hermes_digest, hermes_ref = _container_image_digest(GATEWAY_CONTAINER)
    hermes_tag = hermes_ref.rsplit(":", 1)[-1] if hermes_ref and ":" in hermes_ref else HERMES_TAG
    hermes_latest_digest = ""
    try:
        hermes_latest_digest = _docker_hub_digest(HERMES_IMAGE, HERMES_TAG)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
        pass
    hermes_update = bool(
        docker_ok
        and hermes_latest_digest
        and hermes_digest
        and hermes_digest != hermes_latest_digest,
    )

    desktop_installed = str(desktop_version or "").strip()
    desktop_update = bool(desktop_latest and desktop_installed and _version_lt(desktop_installed, desktop_latest))

    digest_short = hermes_latest_digest
    if len(digest_short) > 28:
        digest_short = digest_short[:28] + "…"

    docker_apply_ok, docker_apply_reason = _docker_apply_ready()
    hermes_script_ok = _script_path("apply-update-hermes.sh") is not None
    workframe_script_ok = _script_path("apply-update-workframe.sh") is not None
    hermes_can_update = bool(docker_apply_ok and hermes_script_ok)
    workframe_can_update = bool(docker_apply_ok and workframe_script_ok)
    hermes_reason = docker_apply_reason
    if not hermes_reason and hermes_update and not hermes_script_ok:
        hermes_reason = "Hermes update script is missing from this install."
    workframe_reason = docker_apply_reason
    if not workframe_reason and workframe_update and not workframe_script_ok:
        workframe_reason = "Workframe update script is missing from this install."
    if not workframe_reason and workframe_update and not workframe_latest:
        workframe_reason = "No published npm release to update to yet."

    agent_version = str(hermes_agent_version or "").strip() or _read_hermes_agent_version()
    hermes_current = agent_version or hermes_tag

    return {
        "ok": True,
        "docker_available": docker_ok,
        "compose_dir": str(compose_dir),
        "project_root": str(project_root),
        "workframe": {
            "current": installed_pkg,
            "latest": workframe_latest,
            "update_available": workframe_update,
            "can_update": workframe_can_update,
            "state": _product_state(update_available=workframe_update, can_update=workframe_can_update),
            "reason": workframe_reason,
            "update_mode": "docker-compose-rebuild",
            "install_kind": "docker",
            "components": ["ui", "api", "supervisor"],
        },
        "hermes": {
            "current": hermes_current,
            "agent_version": agent_version,
            "image_tag": hermes_tag,
            "latest": "",
            "current_image": hermes_ref,
            "current_digest": hermes_digest[:28] + "…" if len(hermes_digest) > 28 else hermes_digest,
            "latest_digest": digest_short,
            "image": f"{HERMES_IMAGE}:{HERMES_TAG}",
            "update_available": hermes_update,
            "can_update": hermes_can_update,
            "state": _product_state(update_available=hermes_update, can_update=hermes_can_update),
            "reason": hermes_reason,
            "update_mode": "docker-compose-pull",
            "install_kind": "docker",
            "can_restart_gateway": bool(docker_apply_ok and _script_path("restart-gateway-hermes.sh") is not None),
        },
        "desktop": {
            "current": desktop_installed,
            "latest": desktop_latest,
            "update_available": desktop_update,
            "can_update": False,
            "state": "available" if desktop_update else "current",
            "reason": "Desktop updates are distributed separately from the Docker stack.",
            "update_mode": "manual-download",
            "install_kind": "desktop",
            "download_url": str(releases.get("desktop_download_url") or ""),
        },
    }


def apply_update(target: str) -> dict[str, Any]:
    if os.environ.get("WORKFRAME_ENABLE_ADMIN_UPDATES") != "1":
        raise ValueError("admin_updates_disabled")
    target = str(target or "all").strip().lower()
    if target not in {"hermes", "workframe", "all"}:
        raise ValueError("invalid_update_target")
    if not Path(DOCKER_SOCK).exists():
        raise ValueError("docker_unavailable")

    scripts: list[str] = []
    if target in {"hermes", "all"}:
        script = _script_path("apply-update-hermes.sh")
        if not script:
            raise ValueError("update_script_missing:hermes")
        scripts.append(str(script))
    if target in {"workframe", "all"}:
        script = _script_path("apply-update-workframe.sh")
        if not script:
            raise ValueError("update_script_missing:workframe")
        scripts.append(str(script))

    env = os.environ.copy()
    env.setdefault("WORKFRAME_COMPOSE_DIR", str(_compose_dir()))
    env.setdefault("WORKFRAME_PROJECT_ROOT", str(_project_root()))

    logs: list[str] = []
    for script in scripts:
        proc = subprocess.run(
            ["bash", script],
            capture_output=True,
            text=True,
            timeout=900,
            env=env,
            cwd=env["WORKFRAME_COMPOSE_DIR"],
        )
        logs.append(f"=== {script} (exit {proc.returncode}) ===\n{proc.stdout}\n{proc.stderr}")
        if proc.returncode != 0:
            raise ValueError(f"update_failed:{Path(script).name}")

    return {"ok": True, "target": target, "log": "\n".join(logs)[-12000:]}


def restart_gateway() -> dict[str, Any]:
    if os.environ.get("WORKFRAME_ENABLE_ADMIN_UPDATES") != "1":
        raise ValueError("admin_updates_disabled")
    if not Path(DOCKER_SOCK).exists():
        raise ValueError("docker_unavailable")
    docker_apply_ok, docker_apply_reason = _docker_apply_ready()
    if not docker_apply_ok:
        raise ValueError(str(docker_apply_reason or "docker_apply_unavailable"))
    script = _script_path("restart-gateway-hermes.sh")
    if not script:
        raise ValueError("restart_script_missing:gateway")

    env = os.environ.copy()
    env.setdefault("WORKFRAME_COMPOSE_DIR", str(_compose_dir()))
    env.setdefault("WORKFRAME_PROJECT_ROOT", str(_project_root()))
    proc = subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
        cwd=env["WORKFRAME_COMPOSE_DIR"],
    )
    log = f"=== {script} (exit {proc.returncode}) ===\n{proc.stdout}\n{proc.stderr}"
    if proc.returncode != 0:
        raise ValueError("restart_failed:gateway")
    return {"ok": True, "target": "gateway", "log": log[-12000:]}


if __name__ == "__main__":
    assert _version_lt("0.1.0", "0.1.1")
    assert not _version_lt("0.1.0", "0.1.0")
    assert parse_hermes_version_output("Hermes Agent v0.17.0 (2026.6.19)") == "0.17.0"
    print("updates module ok")
