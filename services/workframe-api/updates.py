"""Admin stack updates — version checks + safe in-place apply (preserves runtime/DB)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
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


def _api_env_version() -> str:
    return _normalize_api_env_version(
        str(os.environ.get("WORKFRAME_API_VERSION", API_VERSION) or "").strip(),
    )


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
    """Path on the supervisor /compose mount (pack installs: workframe-api/data/.update-staging)."""
    ver = str(version or "").strip()
    pkg = str(package or NPM_PACKAGE).strip()
    return f"/compose/workframe-api/data/.update-staging/{pkg}-{ver}.tgz"


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
    if not integrity.startswith("sha512-"):
        raise ValueError("npm_integrity_missing")
    actual = "sha512-" + base64.b64encode(hashlib.sha512(body).digest()).decode()
    if actual != integrity:
        raise ValueError("npm_integrity_mismatch")
    dest.write_bytes(body)
    dest.with_suffix(dest.suffix + ".sha512").write_text(actual + "\n", encoding="utf-8")
    if not dest.is_file():
        raise ValueError("npm_staging_write_failed")
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


def _read_build_stamp_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    version = str(data.get("package_version") or "").strip()
    if not version:
        return {}
    out = {"package_version": version}
    for key in ("synced_at", "bundled_at", "git_ref", "asset_revision"):
        val = str(data.get(key) or "").strip()
        if val:
            out[key] = val
    return out


def _api_build_stamp_paths(project_root: Path) -> list[Path]:
    roots = [project_root]
    for raw in (
        os.environ.get("WORKFRAME_HOST_PROJECT_ROOT", ""),
        os.environ.get("WORKFRAME_PROJECT_ROOT", ""),
        os.environ.get("WORKFRAME_COMPOSE_DIR", ""),
        "/project",
        "/compose",
    ):
        p = Path(str(raw or "").strip())
        if p.is_dir() and p not in roots:
            roots.append(p)
    paths: list[Path] = []
    for root in roots:
        paths.extend(
            [
                root / "workframe-api" / "workframe-api-build.json",
                root / "services" / "workframe-api" / "workframe-api-build.json",
            ],
        )
    paths.append(Path(__file__).with_name("workframe-api-build.json"))
    return paths


def _ui_build_stamp_paths(project_root: Path) -> list[Path]:
    roots = [project_root]
    for raw in (
        os.environ.get("WORKFRAME_HOST_PROJECT_ROOT", ""),
        os.environ.get("WORKFRAME_PROJECT_ROOT", ""),
        os.environ.get("WORKFRAME_COMPOSE_DIR", ""),
        "/project",
        "/compose",
    ):
        p = Path(str(raw or "").strip())
        if p.is_dir() and p not in roots:
            roots.append(p)
    paths: list[Path] = []
    for root in roots:
        paths.extend(
            [
                root / "workframe-ui" / "public" / "workframe-build.json",
                root / "apps" / "web" / "dist" / "workframe-build.json",
            ],
        )
    return paths


def _supervisor_build_stamp_paths(project_root: Path) -> list[Path]:
    roots = [project_root]
    for raw in (
        os.environ.get("WORKFRAME_HOST_PROJECT_ROOT", ""),
        os.environ.get("WORKFRAME_PROJECT_ROOT", ""),
        os.environ.get("WORKFRAME_COMPOSE_DIR", ""),
        "/project",
        "/compose",
    ):
        p = Path(str(raw or "").strip())
        if p.is_dir() and p not in roots:
            roots.append(p)
    paths: list[Path] = []
    for root in roots:
        paths.extend(
            [
                root / "workframe-supervisor" / "workframe-supervisor-build.json",
                root / "services" / "workframe-supervisor" / "workframe-supervisor-build.json",
            ],
        )
    return paths


def _first_build_stamp(paths: list[Path]) -> dict[str, str]:
    seen: set[str] = set()
    for candidate in paths:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        stamp = _read_build_stamp_file(candidate)
        if stamp:
            return stamp
    return {}


def _read_api_build_stamp(project_root: Path) -> dict[str, str]:
    return _first_build_stamp(_api_build_stamp_paths(project_root))


def _read_ui_build_stamp(project_root: Path) -> dict[str, str]:
    return _first_build_stamp(_ui_build_stamp_paths(project_root))


def _read_supervisor_build_stamp(project_root: Path) -> dict[str, str]:
    return _first_build_stamp(_supervisor_build_stamp_paths(project_root))


def _normalize_api_env_version(raw: str) -> str:
    text = re.sub(r"^workframe-api-", "", str(raw or "").strip())
    return text


def _workframe_install_integrity(
    installed: dict[str, str],
    project_root: Path,
    observed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    observed = observed or {}
    package_pin = str(installed.get("package") or "").strip()
    api_env = _normalize_api_env_version(str(installed.get("api") or ""))
    api_build = str(
        observed.get("api_build") or _read_api_build_stamp(project_root).get("package_version") or "",
    ).strip()
    ui_build = str(
        observed.get("ui_build") or _read_ui_build_stamp(project_root).get("package_version") or "",
    ).strip()
    supervisor_build = str(
        observed.get("supervisor_build") or _read_supervisor_build_stamp(project_root).get("package_version") or "",
    ).strip()
    drift: list[str] = []

    if package_pin and api_env and package_pin != api_env:
        drift.append(f"compose env is v{api_env} but package pin is v{package_pin}")
    if package_pin and api_build and package_pin != api_build:
        drift.append(f"API files are v{api_build} but package pin is v{package_pin}")
    if package_pin and ui_build and package_pin != ui_build:
        drift.append(f"UI bundle is v{ui_build} but package pin is v{package_pin}")
    if package_pin and supervisor_build and package_pin != supervisor_build:
        drift.append(f"supervisor files are v{supervisor_build} but package pin is v{package_pin}")
    if api_env and api_build and api_env != api_build:
        drift.append(f"API files are v{api_build} but compose env is v{api_env}")

    return {
        "ok": not drift,
        "package_pin": package_pin,
        "api_env": api_env,
        "api_build": api_build,
        "ui_build": ui_build,
        "supervisor_build": supervisor_build,
        "drift_reasons": drift,
    }


def _read_installed_workframe_version(project_root: Path) -> dict[str, str]:
    out = {"api": _api_env_version(), "package": "", "manifest_generator": ""}
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

            out["api"] = _normalize_api_env_version(str(getattr(_server, "VERSION", "")))
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
        Path(f"/opt/install/scripts/workframe/{name}"),
        Path(f"/opt/install/scripts/{name}"),
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


def _supervisor_gateway_release() -> tuple[str, str, str]:
    """Read gateway digest, image ref, and installed Hermes version via supervisor."""
    base = str(os.environ.get("WORKFRAME_SUPERVISOR_URL", "")).rstrip("/")
    token = str(os.environ.get("WORKFRAME_SUPERVISOR_TOKEN", "")).strip()
    if not base or not token:
        return "", "", ""
    req = urllib.request.Request(
        f"{base}/v1/gateway.image",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": "workframe-api"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return "", "", ""
    if not isinstance(data, dict) or not data.get("ok"):
        return "", "", ""
    return (
        str(data.get("digest") or "").strip(),
        str(data.get("ref") or "").strip(),
        str(data.get("agent_version") or "").strip(),
    )


def _supervisor_stack_apply_status(job_id: str = "") -> dict[str, Any]:
    base = str(os.environ.get("WORKFRAME_SUPERVISOR_URL", "")).rstrip("/")
    token = str(os.environ.get("WORKFRAME_SUPERVISOR_TOKEN", "")).strip()
    if not base or not token:
        return {"ok": True, "state": "idle", "job_id": "", "target": ""}
    query = f"?job_id={urllib.parse.quote(job_id)}" if job_id else ""
    req = urllib.request.Request(
        f"{base}/v1/stack.apply/status{query}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": "workframe-api"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return {"ok": False, "state": "unavailable", "job_id": job_id, "target": ""}
    return data if isinstance(data, dict) else {"ok": False, "state": "unknown", "job_id": job_id, "target": ""}


def _supervisor_stack_release() -> dict[str, Any]:
    base = str(os.environ.get("WORKFRAME_SUPERVISOR_URL", "")).rstrip("/")
    token = str(os.environ.get("WORKFRAME_SUPERVISOR_TOKEN", "")).strip()
    if not base or not token:
        return {}
    req = urllib.request.Request(
        f"{base}/v1/stack.release",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": "workframe-api"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) and data.get("ok") else {}


def _supervisor_healthy(*, attempts: int = 4, delay_s: float = 2.0) -> tuple[bool, str | None]:
    base = str(os.environ.get("WORKFRAME_SUPERVISOR_URL", "")).rstrip("/")
    token = str(os.environ.get("WORKFRAME_SUPERVISOR_TOKEN", "")).strip()
    if not base or not token:
        return False, "workframe-supervisor is not configured."
    req = urllib.request.Request(
        f"{base}/health",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": "workframe-api"},
    )
    last_exc: BaseException | None = None
    for attempt in range(max(1, attempts)):
        try:
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                if resp.status == 200:
                    return True, None
                last_exc = OSError(f"HTTP {resp.status}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
        if attempt + 1 < attempts:
            time.sleep(delay_s)
    detail = str(last_exc) if last_exc else "unknown error"
    return False, f"workframe-supervisor is unreachable ({detail})."


STACK_APPLY_LOCK_MAX_AGE_S = 15 * 60


def _stack_apply_in_progress() -> bool:
    """True while apply-update-workframe.sh holds its lock (async apply running)."""
    lock = Path(os.environ.get("WORKFRAME_API_DATA_DIR", "/app/data")) / ".stack-apply.lock.d"
    if not lock.is_dir():
        return False
    try:
        age = time.time() - lock.stat().st_mtime
    except OSError:
        return False
    # Negative age = clock/filesystem skew; still counts as fresh.
    return age < STACK_APPLY_LOCK_MAX_AGE_S


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
    # Prefer the supervisor whenever it is configured. The API container may
    # have docker.sock but only a read-only /compose mount; running the host
    # updater from that container then fails after downloading the release.
    supervisor_reason: str | None = None
    if _supervisor_configured():
        if _script_path("apply-update-workframe.sh") is None and _script_path("apply-update-hermes.sh") is None:
            supervisor_reason = "Stack update scripts are missing from this install."
        else:
            ok, reason = _supervisor_healthy()
            if ok:
                return "supervisor", True, None
            supervisor_reason = reason

    api_docker = Path(DOCKER_SOCK).exists()
    if api_docker:
        ok, reason = _docker_apply_ready()
        if ok:
            return "api_docker", True, None
        if supervisor_reason is None:
            supervisor_reason = reason

    if _supervisor_configured():
        return "supervisor", False, supervisor_reason or "workframe-supervisor is unavailable."
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
    supervisor_release = _supervisor_stack_release() if supervisor_ok else {}
    integrity = _workframe_install_integrity(installed, project_root, supervisor_release)
    apply_job = _supervisor_stack_apply_status() if supervisor_ok else {"ok": True, "state": "idle"}
    supervisor_runtime = str(supervisor_release.get("supervisor_runtime") or "").strip()

    npm_latest = ""
    try:
        npm_latest = _npm_latest_version()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
        pass

    releases = _releases_manifest()
    workframe_latest = str(releases.get("workframe") or releases.get("create_workframe") or npm_latest or "")
    desktop_latest = str(releases.get("desktop") or os.environ.get("WORKFRAME_DESKTOP_LATEST", "0.1.0"))

    installed_pkg = integrity.get("package_pin") or installed.get("package") or installed.get("api") or ""
    workframe_update = bool(workframe_latest and _version_lt(installed_pkg, workframe_latest))
    install_drift = not bool(integrity.get("ok"))
    if install_drift and not workframe_update:
        workframe_update = True

    hermes_digest, hermes_ref, supervisor_agent_version = ("", "", "")
    if api_docker:
        hermes_digest, hermes_ref = _container_image_digest(GATEWAY_CONTAINER)
    elif supervisor_ok:
        hermes_digest, hermes_ref, supervisor_agent_version = _supervisor_gateway_release()
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

    apply_job_state = str(apply_job.get("state") or "").lower()

    agent_version = (
        str(hermes_agent_version or "").strip()
        or supervisor_agent_version
        or _read_hermes_agent_version()
    )
    hermes_current = agent_version or hermes_digest

    if supervisor_runtime:
        integrity["supervisor_runtime"] = supervisor_runtime
        expected_supervisor = str(integrity.get("package_pin") or installed_pkg or "").strip()
        if expected_supervisor and supervisor_runtime != expected_supervisor:
            integrity["ok"] = False
            install_drift = True
            reasons = list(integrity.get("drift_reasons") or [])
            reasons.append(f"running supervisor is v{supervisor_runtime} but package pin is v{expected_supervisor}")
            integrity["drift_reasons"] = reasons
            if not workframe_update:
                workframe_update = True

    # An async apply is running: files may be ahead of the running containers.
    # A Workframe job also remains in progress during its deferred supervisor
    # recreate, even though the update script itself has already exited.
    apply_in_progress = _stack_apply_in_progress() or apply_job_state in {"queued", "running", "restarting"}
    expected_supervisor = str(integrity.get("package_pin") or installed_pkg or "").strip()
    try:
        apply_job_age = time.time() - float(apply_job.get("updated_unix") or 0)
    except (TypeError, ValueError):
        apply_job_age = STACK_APPLY_LOCK_MAX_AGE_S + 1
    if (
        apply_job_state == "succeeded"
        and str(apply_job.get("target") or "") in {"workframe", "all"}
        and 0 <= apply_job_age < 180
        and expected_supervisor
        and supervisor_runtime != expected_supervisor
    ):
        apply_in_progress = True
    if apply_in_progress:
        workframe_can_update = False
        hermes_can_update = False
        install_drift = False
        workframe_reason = ""
        hermes_reason = ""

    return {
        "ok": True,
        "docker_available": apply_ready,
        "docker_sock_on_api": api_docker,
        "supervisor_configured": supervisor_ok,
        "update_apply_channel": apply_channel if apply_ready else None,
        "update_apply_ready": apply_ready,
        "compose_dir": str(compose_dir),
        "project_root": str(project_root),
        "apply_in_progress": apply_in_progress,
        "apply_job": apply_job,
        "workframe": {
            "current": installed_pkg,
            "latest": workframe_latest,
            "update_available": workframe_update,
            "can_update": workframe_can_update,
            "state": "applying"
            if apply_in_progress
            else _product_state(update_available=workframe_update, can_update=workframe_can_update),
            "reason": workframe_reason,
            "update_mode": "docker-compose-rebuild",
            "install_kind": "docker",
            "components": ["ui", "api", "supervisor"],
            "package_pin": integrity.get("package_pin") or "",
            "api_env": integrity.get("api_env") or "",
            "api_build": integrity.get("api_build") or "",
            "ui_build": integrity.get("ui_build") or "",
            "supervisor_build": integrity.get("supervisor_build") or "",
            "supervisor_runtime": integrity.get("supervisor_runtime") or "",
            "install_drift": install_drift,
            "drift_reasons": integrity.get("drift_reasons") or [],
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
            "state": "applying"
            if apply_in_progress
            else _product_state(update_available=hermes_update, can_update=hermes_can_update),
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


def _host_install_paths() -> tuple[str, str]:
    compose = str(os.environ.get("WORKFRAME_HOST_COMPOSE_DIR") or "").strip()
    project = str(os.environ.get("WORKFRAME_HOST_PROJECT_ROOT") or "").strip()
    if compose and project:
        return compose, project
    env_file = _compose_dir() / ".env"
    if env_file.is_file():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key == "WORKFRAME_HOST_COMPOSE_DIR" and not compose:
                compose = value
            elif key == "WORKFRAME_HOST_PROJECT_ROOT" and not project:
                project = value
    return compose, project


def _supervisor_connection_dropped(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        "remote end closed" in text
        or "connection reset" in text
        or "broken pipe" in text
        or "try again" in text
        or "errno -3" in text
    )


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
        target = str(body.get("target") or "all").strip().lower()
        if target in {"workframe", "all"} and _supervisor_connection_dropped(exc):
            return {"ok": True, "accepted": True, "restarting": True, "target": target}
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
            detail = (proc.stderr or proc.stdout).strip().splitlines()
            tail = detail[-1].strip() if detail else f"exit_{proc.returncode}"
            raise ValueError(f"update_failed:{Path(script).name}:{tail[-600:]}")
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
    if update_decision.decision != "allow":
        raise ValueError(update_decision.reason or "cell_update_denied")
    target = str(target or "all").strip().lower()
    if target not in {"hermes", "workframe", "all"}:
        raise ValueError("invalid_update_target")
    # No hard block on the mtime-based lock here: a crashed apply leaves a stale
    # lock the API cannot pid-check across containers. The supervisor and the
    # apply script both hold pid-accurate locks and reject true concurrency.
    channel, apply_ready, apply_reason = _update_apply_channel()
    if not apply_ready:
        raise ValueError(str(apply_reason or "docker_apply_unavailable"))

    workframe_version = ""
    workframe_tarball = ""
    if target in {"workframe", "all"}:
        workframe_version, workframe_tarball = _prepare_workframe_update(channel)

    if channel == "supervisor":
        body: dict[str, Any] = {"target": target}
        host_compose_dir, host_project_root = _host_install_paths()
        if host_compose_dir and host_project_root:
            body["host_compose_dir"] = host_compose_dir
            body["host_project_root"] = host_project_root
        if workframe_version:
            body["workframe_version"] = workframe_version
        if workframe_tarball:
            body["workframe_tarball"] = workframe_tarball
        body["async"] = True
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
    drift = _workframe_install_integrity({"package": "0.1.33", "api": "0.1.29"}, Path("."))
    assert not drift["ok"]
    assert drift["package_pin"] == "0.1.33"
    ch, ready, _ = _update_apply_channel()
    assert ch in {"api_docker", "supervisor", "none"}
    assert ready is False or ch != "none"
    print("updates module ok")
