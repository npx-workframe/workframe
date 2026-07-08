"""WF-032 extract: avatar catalog, preset picks, and agent avatar registry."""

from __future__ import annotations

import json
import re
import secrets
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _srv():
    import server as srv

    return srv


_avatar_catalog_cache: dict[str, Any] | None = None
_preset_catalog_cache: dict[str, dict[str, Any]] = {}


def _load_avatar_catalog() -> dict[str, Any]:
    global _avatar_catalog_cache
    if _avatar_catalog_cache is not None:
        return _avatar_catalog_cache
    fallback: dict[str, Any] = {"public_base": "/assets/avatars", "avatars": []}
    catalog_path = _srv().AVATAR_CATALOG_JSON
    if not catalog_path.is_file():
        _avatar_catalog_cache = fallback
        return fallback
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        _avatar_catalog_cache = data if isinstance(data, dict) else fallback
    except Exception:  # noqa: BLE001
        _avatar_catalog_cache = fallback
    return _avatar_catalog_cache


def _avatar_path_from_url(avatar_url: str) -> str:
    raw = str(avatar_url or "").strip()
    if "://" in raw:
        try:
            parsed = urllib.parse.urlparse(raw)
            raw = parsed.path or raw
        except Exception:  # noqa: BLE001
            pass
    return raw.split("?", 1)[0].split("#", 1)[0]


def _catalog_url_for_id(
    catalog: dict[str, Any],
    avatar_id: str,
    *,
    items_key: str = "avatars",
    default_base: str = "/assets",
) -> str:
    avatar_id = str(avatar_id or "").strip()
    base = str(catalog.get("public_base") or default_base).rstrip("/")
    for row in catalog.get(items_key) or []:
        if isinstance(row, dict) and str(row.get("id")) == avatar_id:
            file_name = str(row.get("file") or f"{avatar_id}.png")
            return f"{base}/{file_name}"
    return f"{base}/{avatar_id}.png"


def _id_from_catalog_url(
    catalog: dict[str, Any],
    avatar_url: str,
    *,
    items_key: str = "avatars",
) -> str:
    path = _avatar_path_from_url(avatar_url)
    basename = path.rsplit("/", 1)[-1]
    if not basename:
        return ""
    rows = [row for row in catalog.get(items_key) or [] if isinstance(row, dict)]
    base = str(catalog.get("public_base") or "").rstrip("/")
    for row in rows:
        if str(row.get("file") or f"{row.get('id')}.png") == basename:
            return str(row.get("id") or "")
    if base:
        stable = re.match(rf"^{re.escape(base)}/([^/]+)\.png$", path, re.I)
        if stable:
            stem = stable.group(1)
            for row in rows:
                if str(row.get("id") or "") == stem:
                    return str(row.get("id") or "")
                file_stem = str(row.get("file") or f"{row.get('id')}.png").replace(".png", "")
                if file_stem == stem:
                    return str(row.get("id") or "")
    hashed = re.match(r"/assets/([a-z0-9]+)-[A-Za-z0-9_]+\.png$", path, re.I)
    if hashed:
        prefix = hashed.group(1)
        for row in rows:
            if str(row.get("id") or "") == prefix:
                return str(row.get("id") or "")
            file_stem = str(row.get("file") or f"{row.get('id')}.png").replace(".png", "")
            if file_stem == prefix:
                return str(row.get("id") or "")
    return ""


def _normalize_catalog_avatar_patch(
    catalog: dict[str, Any],
    avatar_url: str = "",
    avatar_id: str = "",
    *,
    items_key: str = "avatars",
    default_base: str = "/assets",
    include_id: bool = True,
) -> dict[str, str]:
    aid = str(avatar_id or "").strip()
    raw = str(avatar_url or "").strip()
    if raw.startswith("data:"):
        out = {"avatar_url": raw}
        if include_id:
            out["avatar_id"] = ""
        return out
    path = _avatar_path_from_url(raw)
    if not path and not aid:
        out = {"avatar_url": ""}
        if include_id:
            out["avatar_id"] = ""
        return out
    if not aid and path:
        aid = _id_from_catalog_url(catalog, path, items_key=items_key)
    if aid:
        stable = _catalog_url_for_id(catalog, aid, items_key=items_key, default_base=default_base)
        out = {"avatar_url": stable}
        if include_id:
            out["avatar_id"] = aid
        return out
    out = {"avatar_url": path or raw}
    if include_id:
        out["avatar_id"] = ""
    return out


def _avatar_url_for_id(avatar_id: str) -> str:
    return _catalog_url_for_id(
        _load_avatar_catalog(),
        avatar_id,
        items_key="avatars",
        default_base="/assets/avatars",
    )


def _avatar_id_from_url(avatar_url: str) -> str:
    return _id_from_catalog_url(_load_avatar_catalog(), avatar_url, items_key="avatars")


def _load_preset_catalog(path: Path) -> dict[str, Any]:
    key = str(path)
    if key in _preset_catalog_cache:
        return _preset_catalog_cache[key]
    fallback: dict[str, Any] = {"public_base": "", "avatars": [], "logos": []}
    if not path.is_file():
        _preset_catalog_cache[key] = fallback
        return fallback
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        _preset_catalog_cache[key] = data if isinstance(data, dict) else fallback
    except Exception:  # noqa: BLE001
        _preset_catalog_cache[key] = fallback
    return _preset_catalog_cache[key]


def _normalize_user_avatar_url(avatar_url: str) -> str:
    catalog = _load_preset_catalog(_srv().USER_AVATAR_CATALOG_JSON)
    return _normalize_catalog_avatar_patch(
        catalog,
        avatar_url,
        items_key="avatars",
        default_base="/assets/avatars",
        include_id=False,
    )["avatar_url"]


def _normalize_logo_url(avatar_url: str) -> str:
    catalog = _load_preset_catalog(_srv().LOGO_CATALOG_JSON)
    return _normalize_catalog_avatar_patch(
        catalog,
        avatar_url,
        items_key="logos",
        default_base="/assets/project-logos",
        include_id=False,
    )["avatar_url"]


def _normalize_agent_avatar_patch(
    avatar_url: str = "",
    avatar_id: str = "",
) -> dict[str, str]:
    """Persist stable catalog id + nginx path — not vite hash or absolute origin."""
    return _normalize_catalog_avatar_patch(
        _load_avatar_catalog(),
        avatar_url,
        avatar_id,
        items_key="avatars",
        default_base="/assets/avatars",
        include_id=True,
    )


def _pick_preset_url(catalog_path: Path, *, items_key: str = "avatars") -> str:
    catalog = _load_preset_catalog(catalog_path)
    base = str(catalog.get("public_base") or "").rstrip("/")
    items = [row for row in catalog.get(items_key) or [] if isinstance(row, dict) and row.get("id")]
    if not items or not base:
        return ""
    pick = secrets.choice(items)
    file_name = str(pick.get("file") or f"{pick['id']}.png")
    return f"{base}/{file_name}"


def _pick_logo_url() -> str:
    return _pick_preset_url(_srv().LOGO_CATALOG_JSON, items_key="logos")


def _pick_user_avatar_url() -> str:
    return _pick_preset_url(_srv().USER_AVATAR_CATALOG_JSON, items_key="avatars")


def _resolve_avatar_fields(row: dict[str, Any]) -> None:
    avatar_id = str(row.get("avatar_id") or "").strip()
    if avatar_id:
        row["avatar_url"] = _avatar_url_for_id(avatar_id)
        return
    explicit = str(row.get("avatar_url") or "").strip()
    if explicit:
        row["avatar_url"] = explicit


def _load_avatar_registry() -> dict[str, Any]:
    registry_path = _srv().AVATAR_REGISTRY_JSON
    if not registry_path.is_file():
        return {"version": 1, "weights": {}, "assignments": {}}
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("weights", {})
            data.setdefault("assignments", {})
            return data
    except Exception:  # noqa: BLE001
        pass
    return {"version": 1, "weights": {}, "assignments": {}}


def _save_avatar_registry(data: dict[str, Any]) -> None:
    registry_path = _srv().AVATAR_REGISTRY_JSON
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _pick_avatar_id() -> str:
    catalog = _load_avatar_catalog()
    avatars = [row for row in catalog.get("avatars") or [] if isinstance(row, dict) and row.get("id")]
    if not avatars:
        return "steve"
    registry = _load_avatar_registry()
    agents = _srv().load_agent_registry()
    assigned = {str(v) for v in registry.get("assignments", {}).values()}
    for row in agents.values():
        aid = str(row.get("avatar_id") or "").strip()
        if aid:
            assigned.add(aid)
    pool = [row for row in avatars if str(row["id"]) not in assigned] or avatars
    weights = registry.get("weights") or {}
    min_weight = min(int(weights.get(str(row["id"]), 0)) for row in pool)
    candidates = [row for row in pool if int(weights.get(str(row["id"]), 0)) <= min_weight]
    pick = secrets.choice(candidates)
    return str(pick["id"])


def _upsert_agent_registry_row(profile: str, patch: dict[str, Any]) -> None:
    prof_key = _srv().safe_profile_slug(profile)
    if "avatar_url" in patch or "avatar_id" in patch:
        norm = _normalize_agent_avatar_patch(
            str(patch.get("avatar_url") or ""),
            str(patch.get("avatar_id") or ""),
        )
        patch = {**patch, **norm}
    agents_json = _srv().AGENTS_JSON
    agents_json.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {"version": 1, "owner_profile": _srv()._primary_profile(), "agents": {}}
    if agents_json.is_file():
        try:
            loaded = json.loads(agents_json.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except Exception:  # noqa: BLE001
            pass
    agents = data.setdefault("agents", {})
    current = agents.get(prof_key) if isinstance(agents.get(prof_key), dict) else {}
    agents[prof_key] = {**current, **patch, "profile": prof_key}
    data["agents"] = agents
    agents_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _avatar_id_for_display_name(display_name: str) -> str:
    """Map a chosen agent name to catalog id when labels match (e.g. Ada → ada)."""
    needle = str(display_name or "").strip().lower()
    if not needle:
        return ""
    for row in _load_avatar_catalog().get("avatars") or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip().lower()
        aid = str(row.get("id") or "").strip().lower()
        if needle in (label, aid):
            return str(row["id"])
    return ""


def _assign_agent_avatar(profile: str, *, display_name: str = "") -> dict[str, str]:
    """Pick catalog avatar and persist to agents.json + avatar-registry.json."""
    prof = _srv().safe_profile_slug(profile)
    native_slug = _srv().safe_profile_slug(str(_srv().NATIVE_PROFILE or "workframe-agent"))
    name = str(display_name or "").strip() or str(_srv()._agent_registry_row(prof).get("display_name") or "").strip()
    by_name = _avatar_id_for_display_name(name)
    if by_name:
        avatar_id = by_name
    elif prof == native_slug:
        avatar_id = "steve"
    else:
        avatar_id = _pick_avatar_id()
    avatar_url = _avatar_url_for_id(avatar_id)
    _upsert_agent_registry_row(
        prof,
        {
            "avatar_id": avatar_id,
            "avatar_url": avatar_url,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    registry = _load_avatar_registry()
    registry.setdefault("assignments", {})[prof] = avatar_id
    weights = registry.setdefault("weights", {})
    weights[avatar_id] = int(weights.get(avatar_id, 0)) + 1
    _save_avatar_registry(registry)
    return {"avatar_id": avatar_id, "avatar_url": avatar_url}
