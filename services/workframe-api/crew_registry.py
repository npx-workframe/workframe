"""WF-032 extract: workspace crew registry and agent identity resolution."""

from __future__ import annotations

import json
import sqlite3
from typing import Any


CREW_COLORS = [
    "#A78BFA",
    "#7DD3FC",
    "#F472B6",
    "#FBBF24",
    "#E879F9",
    "#5EE2B5",
    "#F26D6D",
    "#38BDF8",
]


def _srv():
    import server as srv

    return srv


def load_agent_registry() -> dict[str, dict[str, Any]]:
    agents_json = _srv().AGENTS_JSON
    if not agents_json.is_file():
        return {}
    try:
        data = json.loads(agents_json.read_text(encoding="utf-8"))
        agents = data.get("agents")
        if isinstance(agents, dict):
            return {str(k): v for k, v in agents.items() if isinstance(v, dict)}
    except (OSError, json.JSONDecodeError, TypeError, ValueError):  # noqa: BLE001
        pass
    return {}


def _agent_registry_row(profile: str) -> dict[str, Any]:
    slug = _srv().safe_profile_slug(profile)
    return load_agent_registry().get(slug, {})


def _workspace_agent_identities(workspace_id: str | None = None) -> dict[str, dict[str, Any]]:
    """Slug → display_name/tagline/role/avatar from agent_profiles + registry."""
    identities: dict[str, dict[str, Any]] = {}
    try:
        conn = _srv()._workframe_db()
        ws_id = str(workspace_id or "").strip()
        if not ws_id:
            ws = conn.execute(
                "SELECT id FROM workspaces WHERE slug = 'default' AND deleted_at IS NULL LIMIT 1",
            ).fetchone()
            ws_id = str(ws["id"]) if ws else ""
        if ws_id:
            rows = conn.execute(
                """
                SELECT slug, display_name, tagline, role, avatar_url
                FROM agent_profiles
                WHERE workspace_id = ? AND deleted_at IS NULL
                """,
                (ws_id,),
            ).fetchall()
            for row in rows:
                slug = str(row["slug"] or "").strip()
                if not slug:
                    continue
                identities[slug] = {
                    "display_name": str(row["display_name"] or ""),
                    "tagline": str(row["tagline"] or ""),
                    "role": str(row["role"] or ""),
                    "avatar_url": str(row["avatar_url"] or "").strip() or None,
                }
        conn.close()
    except (sqlite3.Error, OSError):  # noqa: BLE001
        pass
    registry = load_agent_registry()
    for _slug, ident in list(identities.items()):
        reg = registry.get(_slug) if isinstance(registry.get(_slug), dict) else {}
        if reg.get("display_name"):
            ident["display_name"] = str(reg["display_name"])
        if reg.get("tagline"):
            ident["tagline"] = str(reg["tagline"])
        if reg.get("role"):
            ident["role"] = str(reg["role"])
        if reg.get("avatar_url"):
            ident["avatar_url"] = str(reg["avatar_url"])
        if reg.get("avatar_id"):
            ident["avatar_id"] = str(reg["avatar_id"])
    return identities


def _agent_identity_fields(profile: str, workspace_id: str | None = None, user_id: str = "") -> dict[str, Any]:
    slug = _srv().safe_profile_slug(str(profile or "").strip())
    template = _srv()._runtime_template_slug(slug) if _srv()._is_runtime_profile_slug(slug) else slug
    reg = _agent_registry_row(slug)
    if user_id and template:
        runtime = _srv()._runtime_profile_slug(user_id, template)
        reg_user = _agent_registry_row(runtime)
        if reg_user.get("display_name") or reg_user.get("tagline") or reg_user.get("avatar_url"):
            reg = {**reg, **{k: v for k, v in reg_user.items() if v}}
    ident = _workspace_agent_identities(workspace_id).get(template, {})
    reg_template = _agent_registry_row(template)
    avatar_url: Any = None
    avatar_id: Any = None
    for src in (reg, ident, reg_template):
        u = str(src.get("avatar_url") or "").strip()
        i = str(src.get("avatar_id") or "").strip()
        if u or i:
            avatar_url, avatar_id = u or None, i or None
            break
    out: dict[str, Any] = {
        "display_name": str(
            reg.get("display_name")
            or ident.get("display_name")
            or reg_template.get("display_name")
            or _srv()._profile_display_name(template)
        ),
        "tagline": str(reg.get("tagline") or ident.get("tagline") or reg_template.get("tagline") or ""),
        "role": str(reg.get("role") or ident.get("role") or reg_template.get("role") or _srv()._profile_role(template)),
        "avatar_url": avatar_url,
        "avatar_id": avatar_id,
    }
    _srv()._resolve_avatar_fields(out)
    return out


def _gateway_platform(gateway: dict[str, Any], native: bool) -> str:
    platforms = gateway.get("platforms") or {}
    if native:
        for name in ("telegram", "discord", "web", "localhost"):
            p = platforms.get(name)
            if isinstance(p, dict) and str(p.get("state") or p.get("status") or "").lower() == "connected":
                return name.replace("localhost", "Hermes").title()
        return "Hermes"
    for name in ("discord", "telegram", "web"):
        p = platforms.get(name)
        if isinstance(p, dict) and str(p.get("state") or p.get("status") or "").lower() == "connected":
            return name.title()
    return "Hermes"


def crew_data(profiles: list[str], primary: str, gateway: dict[str, Any]) -> list[dict[str, Any]]:
    registry = load_agent_registry()
    idents = _workspace_agent_identities()
    ordered: list[str] = []
    if primary and primary in profiles:
        ordered.append(primary)
    for profile in sorted(profiles):
        if profile not in ordered:
            ordered.append(profile)
    crew: list[dict[str, Any]] = []
    for index, profile in enumerate(ordered):
        slug = _srv()._profile_slug(profile).lower()
        display = _srv()._profile_display_name(profile)
        native = _srv()._is_native_profile(profile)
        prof_key = _srv().safe_profile_slug(profile)
        reg = registry.get(prof_key) if isinstance(registry.get(prof_key), dict) else {}
        if not reg:
            legacy_row = registry.get(slug)
            if isinstance(legacy_row, dict):
                reg = legacy_row
        if reg.get("display_name"):
            display = str(reg["display_name"])
        ident = idents.get(prof_key, {})
        if ident.get("display_name"):
            display = str(ident["display_name"])
        role = str(ident.get("role") or reg.get("role") or _srv()._profile_role(profile))
        tagline = str(ident.get("tagline") or reg.get("tagline") or "")
        row: dict[str, Any] = {
            "profile": profile,
            "key": slug,
            "display_name": display,
            "code": _srv()._profile_code(display, slug),
            "role": role,
            "tagline": tagline,
            "color": CREW_COLORS[index % len(CREW_COLORS)],
            "is_native": native,
            "platform": _gateway_platform(gateway, native),
            "route_status": _srv().route_status_for_profile(profile),
        }
        if reg.get("avatar_url"):
            row["avatar_url"] = str(reg["avatar_url"])
        if reg.get("avatar_id"):
            row["avatar_id"] = str(reg["avatar_id"])
        if ident.get("avatar_url"):
            row["avatar_url"] = str(ident["avatar_url"])
        if ident.get("avatar_id"):
            row["avatar_id"] = str(ident["avatar_id"])
        _srv()._resolve_avatar_fields(row)
        crew.append(row)
    return crew


def _workspace_crew_profile_names(workspace_id: str | None = None) -> list[str]:
    """ponytail: rail shows workspace agents + primary Hermes profile, not every stale on-disk profile."""
    primary = _srv()._primary_profile()
    on_disk = set(_srv()._list_profiles())
    profiles: list[str] = []
    rows: list[sqlite3.Row] = []
    try:
        conn = _srv()._workframe_db()
        ws_id = str(workspace_id or "").strip()
        if not ws_id:
            ws = conn.execute(
                "SELECT id FROM workspaces WHERE slug = 'default' AND deleted_at IS NULL LIMIT 1",
            ).fetchone()
            ws_id = str(ws["id"]) if ws else ""
        if ws_id:
            rows = conn.execute(
                """
                SELECT slug, is_native
                FROM agent_profiles
                WHERE workspace_id = ? AND deleted_at IS NULL
                ORDER BY created_at ASC
                """,
                (ws_id,),
            ).fetchall()
        conn.close()
    except (sqlite3.Error, OSError):  # noqa: BLE001
        rows = []
    if primary and primary in on_disk:
        profiles.append(primary)
    for row in rows:
        if int(row["is_native"] or 0):
            continue
        slug = str(row["slug"] or "").strip()
        if slug in on_disk and slug not in profiles:
            profiles.append(slug)
    if not profiles:
        if primary and primary in on_disk:
            return [primary]
        return sorted(on_disk)[:1]
    return profiles


def workframe_agents() -> dict[str, Any]:
    profiles = _workspace_crew_profile_names()
    primary = _srv()._primary_profile()
    gateway = _srv().gateway_data(primary) if primary else _srv().gateway_data("")
    crew = crew_data(profiles, primary, gateway)
    return {
        "ok": True,
        "project_name": _srv().PROJECT_NAME,
        "native_profile": primary,
        "crew": crew,
    }
