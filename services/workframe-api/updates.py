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

import cell_authority

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


def _supervisor_tarball_path(package: str, version: str) -> str:
    """Path on the compose bind mount — supervisor reads /compose even when API lacks that mount."""
    for raw in (os.environ.get("WORKFRAME_COMPOSE_DIR", ""), "/compose"):
        root = str(raw or "").strip().rstrip("/")
        if root and root != ".":
            return f"{root}/workframe-api/data/.update-staging/{package}-{version}.tgz"
    data_dir = Path(os.environ.get("WORKFRAME_API_DATA_DIR", "/app/data"))
    return str(data_dir / ".update-staging" / f"{package}-{version}.tgz")


def prefetch_workframe_npm_tarball(version: str) -> str:
    """Download create-workframe pack to API data dir; return supervisor-visible path."""
    import base64
    import hashlib

    ver = str(version or "").strip()
    if not ver:
        raise ValueError("workframe_version_required")
    pkg = NPM_PACKAGE
    try:
        meta = _http_json(
            f"https://registry.npmjs.org/{urllib.parse.quote(pkg)}/{urllib.parse.quote(ver)}",
            timeout=60.0,
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"npm_fetch_failed:{exc}") from exc
    dist = meta.get("dist") if isinstance(meta.get("dist"), dict) else {}
    url = str(dist.get("tarball") or "").strip()
    integrity = str(dist.get("integrity") or "").strip()
    if not url:
        raise ValueError("npm_tarball_url_missing")
    data_dir = Path(os.environ.get("WORKFRAME_API_DATA_DIR", "/app/data"))
    staging = data_dir / ".update-staging"
    staging.mkdir(parents=True, exist_ok=True)
    dest = staging / f"{pkg}-{ver}.tgz"
    req = urllib.request.Request(url, headers={"User-Agent": "workframe-api"})
    try:
        with urllib.request.urlopen(req, timeout=300.0) as resp:
            body = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ValueError(f"npm_download_failed:{exc}") from exc
    if integrity.startswith("sha512-"):
        actual = "sha512-" + base64.b64encode(hashlib.sha512(body).digest()).decode()
        if actual != integrity:
            raise ValueError("npm_integrity_mismatch")
    dest.write_bytes(body)
    return _supervisor_tarball_path(pkg, ver)


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
    pin = Path(os.environ.get("WORKFRAME_API_DATA_DIR", "/app/data")) / "package-version"
    if pin.is_file():
        out["package"] = pin.read_text(encoding="utf-8").strip()
    manifest = project_root / "workframe-manifest.json"
    if not out["package"] and manifest.is_file():
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


def _supervisor_configured() -> bool:
    return bool(os.environ.get("WORKFRAME_SUPERVISOR_URL", "").strip()) and bool(
        os.environ.get("WORKFRAME_SUPERVISOR_TOKEN", "").strip()
    )


def _supervisor_gateway_image_digest() -> tuple[str, str]:
    """Read gateway image digest via workframe-supervisor (SECURE_MODE API has no docker.sock)."""
    base = str(os.environ.get("WORKFRAME_SUPERVISOR_URL", "")).rstrip("/")
    token = str(os.environ.get("WORKFRAME_SUPERVISOR_TOKEN", "")).strip()
    if not base or not token:
        return "", ""
    req = urllib.request.Request(
        f"{base}/v1/gateway.image",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": "workframe-api"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return "", ""
    if not isinstance(data, dict) or not data.get("ok"):
        return "", ""
    return str(data.get("digest") or "").strip(), str(data.get("ref") or "").strip()


def _admin_stack_updates_enabled() -> bool:
    if os.environ.get("WORKFRAME_ENABLE_ADMIN_UPDATES") == "1":
        return True
    return _supervisor_configured()


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


def _update_apply_channel() -> tuple[str, bool, str | None]:
    """Returns (channel, ready, reason). channel: api_docker | supervisor | none."""
    api_docker = Path(DOCKER_SOCK).exists()
    if api_docker:
        ok, reason = _docker_apply_ready()
        if ok:
            return "api_docker", True, None
        if not _supervisor_configured():
            return "none", False, reason
    if _supervisor_configured():
        if _script_path("apply-update-workframe.sh") is None and _script_path("apply-update-hermes.sh") is None:
            return "supervisor", False, "Stack update scripts are missing from this install."
        return "supervisor", True, None
    if api_docker:
        _, reason = _docker_apply_ready()
        return "none", False, reason
    return (
        "none",
        False,
        "In-place updates need workframe-supervisor or Docker on the stack host.",
    )


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
    api_docker = Path(DOCKER_SOCK).exists()
    supervisor_ok = _supervisor_configured()
    apply_channel, apply_ready, apply_reason = _update_apply_channel()
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

    hermes_digest, hermes_ref = ("", "")
    if api_docker:
        hermes_digest, hermes_ref = _container_image_digest(GATEWAY_CONTAINER)
    elif supervisor_ok:
        hermes_digest, hermes_ref = _supervisor_gateway_image_digest()
    hermes_tag = hermes_ref.rsplit(":", 1)[-1] if hermes_ref and ":" in hermes_ref else HERMES_TAG
    hermes_latest_digest = ""
    try:
        hermes_latest_digest = _docker_hub_digest(HERMES_IMAGE, HERMES_TAG)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
        pass
    hermes_image_known = bool(api_docker or supervisor_ok)
    hermes_update = bool(
        hermes_image_known
        and hermes_latest_digest
        and hermes_digest
        and hermes_digest != hermes_latest_digest,
    )

    desktop_installed = str(desktop_version or "").strip()
    desktop_update = bool(desktop_latest and desktop_installed and _version_lt(desktop_installed, desktop_latest))

    digest_short = hermes_latest_digest
    if len(digest_short) > 28:
        digest_short = digest_short[:28] + "…"

    hermes_script_ok = _script_path("apply-update-hermes.sh") is not None
    workframe_script_ok = _script_path("apply-update-workframe.sh") is not None
    hermes_can_update = bool(apply_ready and hermes_script_ok)
    workframe_can_update = bool(apply_ready and workframe_script_ok)
    hermes_reason = apply_reason
    if not hermes_reason and hermes_update and not hermes_script_ok:
        hermes_reason = "Hermes update script is missing from this install."
    workframe_reason = apply_reason
    if not workframe_reason and workframe_update and not workframe_script_ok:
        workframe_reason = "Workframe update script is missing from this install."
    if not workframe_reason and workframe_update and not workframe_latest:
        workframe_reason = "No published npm release to update to yet."

    agent_version = str(hermes_agent_version or "").strip() or _read_hermes_agent_version()
    hermes_current = agent_version or hermes_tag

    return {
        "ok": True,
        "docker_available": apply_ready,
        "docker_sock_on_api": api_docker,
        "supervisor_configured": supervisor_ok,
        "update_apply_channel": apply_channel if apply_ready else None,
        "update_apply_ready": apply_ready,
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
            "can_restart_gateway": bool(apply_ready and _script_path("restart-gateway-hermes.sh") is not None),
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


def _supervisor_stack_apply(body: dict[str, Any], *, timeout: float = 900.0) -> dict[str, Any]:
    if not _supervisor_configured():
        raise ValueError("supervisor_not_configured")
    base = str(os.environ.get("WORKFRAME_SUPERVISOR_URL", "")).rstrip("/")
    token = str(os.environ.get("WORKFRAME_SUPERVISOR_TOKEN", "")).strip()
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/v1/stack.apply",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "workframe-api",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict) and parsed.get("error"):
                raise ValueError(str(parsed["error"])) from exc
        except json.JSONDecodeError:
            pass
        raise ValueError(f"supervisor_apply_failed:{exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"supervisor_apply_failed:{exc}") from exc
    if not isinstance(data, dict) or not data.get("ok"):
        raise ValueError(str(data.get("error") or "supervisor_apply_failed"))
    return data


def _workframe_update_target_version() -> str:
    try:
        return str(updates_available().get("workframe", {}).get("latest") or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def _visible_tarball_path(package: str, version: str, *, channel: str) -> str:
    if channel == "supervisor":
        return _supervisor_tarball_path(package, version)
    return str(Path(os.environ.get("WORKFRAME_API_DATA_DIR", "/app/data")) / ".update-staging" / f"{package}-{version}.tgz")


def _prepare_workframe_update(channel: str) -> tuple[str, str]:
    version = _workframe_update_target_version()
    if not version:
        raise ValueError("workframe_update_version_unavailable")
    prefetch_workframe_npm_tarball(version)
    return version, _visible_tarball_path(NPM_PACKAGE, version, channel=channel)


def _run_apply_scripts(target: str, env: dict[str, str]) -> dict[str, Any]:
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


def apply_update(target: str, *, user_ack: bool = False) -> dict[str, Any]:
    if not _admin_stack_updates_enabled():
        raise ValueError("admin_updates_disabled")
    open_decision = cell_authority.evaluate_open(_project_root())
    if open_decision.decision == "deny":
        raise ValueError(open_decision.reason or "cell_open_denied")
    update_decision = cell_authority.evaluate_update(
        _project_root(),
        open_decision=open_decision,
        user_ack=user_ack,
    )
    if update_decision.decision == "deny":
        raise ValueError(update_decision.reason or "cell_update_denied")
    if user_ack and update_decision.decision != "allow":
        raise ValueError(update_decision.reason or "cell_update_denied")
    # ponytail: without user_ack, needs_user_action does not block apply until UI sends ack
    target = str(target or "all").strip().lower()
    if target not in {"hermes", "workframe", "all"}:
        raise ValueError("invalid_update_target")
    channel, apply_ready, apply_reason = _update_apply_channel()
    if not apply_ready:
        raise ValueError(str(apply_reason or "docker_apply_unavailable"))

    workframe_version = ""
    workframe_tarball = ""
    if target in {"workframe", "all"}:
        workframe_version, workframe_tarball = _prepare_workframe_update(channel)

    if channel == "supervisor":
        body: dict[str, Any] = {"target": target}
        if workframe_version:
            body["workframe_version"] = workframe_version
        if workframe_tarball:
            body["workframe_tarball"] = workframe_tarball
        return _supervisor_stack_apply(body)

    if not Path(DOCKER_SOCK).exists():
        raise ValueError("docker_unavailable")

    env = os.environ.copy()
    env.setdefault("WORKFRAME_COMPOSE_DIR", str(_compose_dir()))
    env.setdefault("WORKFRAME_PROJECT_ROOT", str(_project_root()))
    if workframe_version:
        env["WORKFRAME_UPDATE_VERSION"] = workframe_version
    if workframe_tarball:
        env["WORKFRAME_UPDATE_TARBALL"] = workframe_tarball
    return _run_apply_scripts(target, env)


def restart_gateway() -> dict[str, Any]:
    if not _admin_stack_updates_enabled():
        raise ValueError("admin_updates_disabled")
    channel, apply_ready, apply_reason = _update_apply_channel()
    if not apply_ready:
        raise ValueError(str(apply_reason or "docker_apply_unavailable"))
    if channel == "supervisor":
        return _supervisor_stack_apply({"target": "gateway-restart"}, timeout=300.0)
    if not Path(DOCKER_SOCK).exists():
        raise ValueError("docker_unavailable")
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
    ch, ready, _ = _update_apply_channel()
    assert ch in {"api_docker", "supervisor", "none"}
    assert ready is False or ch != "none"
    print("updates module ok")
