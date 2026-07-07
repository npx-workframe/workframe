"""WF-032 extract: workspace file tree, read/write, revision state."""

from __future__ import annotations

import base64
import mimetypes
import threading
import time
from pathlib import Path
from typing import Any

TREE_SKIP_NAMES = {
    ".git",
    ".next",
    ".turbo",
    ".venv",
    ".workframe-cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "users",  # ponytail: legacy scaffold dir — hide if present
    "content",  # ponytail: legacy nested tree — hide if present
}

PROTECTED_WORKSPACE_FILE_NAMES = {"AGENTS.md", ".hermes.md"}
PROTECTED_PROFILE_CONFIG_FILE_NAMES = {"config.yaml", "profile.yaml"}

_workspace_state_lock = threading.Lock()
_workspace_state_cache: dict[str, Any] = {
    "ok": True,
    "revision": "0:0:",
    "files": 0,
    "updated_at": "",
    "latest_path": "",
    "generation": 0,
}
_workspace_tree_lock = threading.Lock()
_workspace_tree_cache: dict[str, Any] = {
    "revision": "",
    "root": None,
}


def _srv():
    import server as srv

    return srv


def _normalized_workspace_rel(rel: str) -> str:
    return (rel or "").replace("\\", "/").lstrip("/")


def _workspace_root() -> Path:
    return _srv().WORKSPACE.resolve()


def safe_workspace_path(rel: str) -> Path | None:
    rel = rel.replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    root = _workspace_root()
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path


def _workspace_rel(path: Path) -> str:
    return path.resolve().relative_to(_workspace_root()).as_posix()


def _is_env_like_name(name: str) -> bool:
    lower = name.lower()
    return (
        lower == ".env"
        or lower.startswith(".env.")
        or lower.endswith(".env")
        or lower == "environment"
    )


def workspace_protected_reason(rel: str) -> str | None:
    """Return a stable reason when a workspace-relative path is protected."""
    safe = safe_workspace_path(_normalized_workspace_rel(rel))
    workspace = _srv().WORKSPACE.resolve()
    if safe is None:
        return "invalid_path"
    try:
        rel_path = safe.relative_to(workspace)
    except ValueError:
        return "invalid_path"

    parts = rel_path.parts
    if not parts:
        return None

    for part in parts:
        if part in PROTECTED_WORKSPACE_FILE_NAMES:
            return "protected_workspace_file"
        if _is_env_like_name(part):
            return "protected_env_file"

    if len(parts) >= 3 and parts[0] == "profiles" and parts[2] in PROTECTED_PROFILE_CONFIG_FILE_NAMES:
        return "protected_profile_config"
    if len(parts) >= 2 and parts[0] == "profiles" and parts[-1] in PROTECTED_PROFILE_CONFIG_FILE_NAMES:
        return "protected_profile_config"
    return None


def safe_content_path(rel: str) -> Path | None:
    return safe_workspace_path(rel)


def _list_folder_nodes(folder: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        entries = sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except OSError:
        return out
    for p in entries:
        if p.name in TREE_SKIP_NAMES:
            continue
        rel = _workspace_rel(p)
        if workspace_protected_reason(rel):
            continue
        node: dict[str, Any] = {
            "id": rel,
            "name": p.name,
            "type": "folder" if p.is_dir() else "file",
        }
        if p.is_dir():
            node["children"] = []
            node["children_loaded"] = False
        out.append(node)
    return out


def _files_tree_root_name() -> str:
    """Navigator root label follows workspace branding, not WORKFRAME_PROJECT env."""
    try:
        conn = _srv()._workframe_db()
        branding = _srv()._primary_workspace_branding(conn)
        conn.close()
        if branding:
            name = str(branding.get("display_name") or "").strip()
            if name:
                return name
    except Exception:  # noqa: BLE001
        pass
    return _srv().PROJECT_NAME


def files_tree() -> dict[str, Any]:
    workspace = _srv().WORKSPACE
    current_revision = str(workspace_state().get("revision") or "")
    root_name = _files_tree_root_name()
    with _workspace_tree_lock:
        cached_revision = str(_workspace_tree_cache.get("revision") or "")
        cached_root = _workspace_tree_cache.get("root")
        if cached_root and cached_revision == current_revision:
            if str(cached_root.get("name") or "") == root_name:
                return cached_root
            refreshed = dict(cached_root)
            refreshed["name"] = root_name
            _workspace_tree_cache["root"] = refreshed
            return refreshed

    root = {
        "id": "root",
        "name": root_name,
        "type": "folder",
        "children": [],
    }
    if not workspace.is_dir():
        return root
    root["children"] = _list_folder_nodes(workspace)
    with _workspace_tree_lock:
        _workspace_tree_cache["revision"] = current_revision
        _workspace_tree_cache["root"] = root
    return root


def files_list(rel: str = "") -> dict[str, Any]:
    workspace = _srv().WORKSPACE
    folder = workspace if not rel.strip() else safe_workspace_path(rel)
    if folder is None or not folder.exists() or not folder.is_dir():
        raise ValueError("folder not found")
    reason = workspace_protected_reason(rel)
    if reason:
        raise PermissionError(f"protected file: {reason}")
    folder_rel = "" if folder == workspace else _workspace_rel(folder)
    return {
        "ok": True,
        "path": folder_rel,
        "children": _list_folder_nodes(folder),
    }


def _scan_workspace_state() -> dict[str, Any]:
    workspace = _srv().WORKSPACE
    files = 0
    latest_mtime = 0.0
    latest_rel = ""
    if workspace.is_dir():
        try:
            for path in workspace.rglob("*"):
                if not path.is_file():
                    continue
                if path.name in TREE_SKIP_NAMES:
                    continue
                try:
                    rel = _workspace_rel(path)
                except ValueError:
                    continue
                if workspace_protected_reason(rel):
                    continue
                files += 1
                try:
                    mtime = float(path.stat().st_mtime)
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest_mtime = mtime
                    latest_rel = rel
        except OSError:
            pass
    revision = f"{int(latest_mtime)}:{files}:{latest_rel}"
    return {
        "ok": True,
        "revision": revision,
        "files": files,
        "updated_at": _srv()._iso_from_unix(latest_mtime),
        "latest_path": latest_rel,
    }


def _refresh_workspace_state() -> dict[str, Any]:
    state = _scan_workspace_state()
    with _workspace_state_lock:
        generation = int(_workspace_state_cache.get("generation") or 0)
        _workspace_state_cache.update(state)
        _workspace_state_cache["generation"] = generation
        if generation:
            _workspace_state_cache["revision"] = f"{state['revision']}:{generation}"
        return dict(_workspace_state_cache)


def workspace_state() -> dict[str, Any]:
    with _workspace_state_lock:
        return dict(_workspace_state_cache)


def bump_workspace_state(path: Path | None = None) -> None:
    now = time.time()
    rel = ""
    if path is not None:
        try:
            rel = _workspace_rel(path)
        except Exception:  # noqa: BLE001
            rel = ""
    with _workspace_state_lock:
        current_files = int(_workspace_state_cache.get("files") or 0)
        generation = int(_workspace_state_cache.get("generation") or 0) + 1
        _workspace_state_cache.update(
            {
                "ok": True,
                "revision": f"{int(now)}:{current_files}:{rel}:{generation}",
                "updated_at": _srv()._iso_from_unix(now),
                "latest_path": rel,
                "generation": generation,
            }
        )
    with _workspace_tree_lock:
        _workspace_tree_cache["revision"] = ""
        _workspace_tree_cache["root"] = None


def workspace_state_daemon() -> None:
    while True:
        try:
            _refresh_workspace_state()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)


def file_read(rel: str) -> dict[str, Any]:
    reason = workspace_protected_reason(rel)
    if reason:
        raise PermissionError(f"protected file: {reason}")
    fp = safe_workspace_path(rel)
    if not fp or not fp.exists() or not fp.is_file():
        raise ValueError("not found")
    try:
        text = fp.read_text(encoding="utf-8")
        return {"path": _workspace_rel(fp), "content": text}
    except UnicodeDecodeError:
        return {"path": _workspace_rel(fp), "content": ""}


def file_write(rel: str, content: str) -> dict[str, Any]:
    reason = workspace_protected_reason(rel)
    if reason:
        raise PermissionError(f"protected file: {reason}")
    fp = safe_workspace_path(rel)
    if not fp:
        raise ValueError("invalid path")
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8")
    bump_workspace_state(fp)
    return {"ok": True, "path": _workspace_rel(fp)}


def file_upload_binary(rel: str, content_b64: str) -> dict[str, Any]:
    reason = workspace_protected_reason(rel)
    if reason:
        raise PermissionError(f"protected file: {reason}")
    fp = safe_workspace_path(rel)
    if not fp:
        raise ValueError("invalid path")
    try:
        raw = base64.b64decode(content_b64, validate=True)
    except ValueError as exc:
        raise ValueError("invalid base64") from exc
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_bytes(raw)
    bump_workspace_state(fp)
    return {"ok": True, "path": _workspace_rel(fp), "size": len(raw)}


def file_raw(rel: str) -> tuple[bytes, str]:
    reason = workspace_protected_reason(rel)
    if reason:
        raise PermissionError(f"protected file: {reason}")
    fp = safe_workspace_path(rel)
    if not fp or not fp.is_file():
        raise ValueError("not found")
    mime, _ = mimetypes.guess_type(str(fp))
    return fp.read_bytes(), mime or "application/octet-stream"
