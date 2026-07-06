"""WF-032 extract: hermes_profiles."""
from __future__ import annotations

import json
import os
import queue
import re
import shlex
import shutil
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from http.server import BaseHTTPRequestHandler

import user_prefs
import rooms

_AGENT_PROFILE_UUID_RE = rooms._AGENT_PROFILE_UUID_RE
_FORBIDDEN_CHILD_SKILLS = frozenset({"botfather", "crew-manager"})


def _srv():
    import server as srv

    return srv


def _list_profiles() -> list[str]:
    profiles_dir = _srv().HERMES_DATA / "profiles"
    if not profiles_dir.is_dir():
        return []
    return sorted(
        p.name
        for p in profiles_dir.iterdir()
        if p.is_dir() and ((p / "profile.yaml").exists() or (p / "config.yaml").exists())
    )


def _native_profile_slug() -> str:
    return str(_srv().NATIVE_PROFILE or "workframe-agent").strip() or "workframe-agent"


def _native_profile_present() -> bool:
    slug = _native_profile_slug()
    prof_dir = _srv()._profile_dir(slug)
    return (prof_dir / "config.yaml").is_file() or (prof_dir / "profile.yaml").is_file()


def _hermes_data_uid_gid() -> tuple[int, int]:
    try:
        st = _srv().HERMES_DATA.stat()
        return int(st.st_uid), int(st.st_gid)
    except OSError:
        return 10000, 10000


def _chown_profile_tree(prof_dir: Path) -> None:
    """Gateway runs as the Agents volume owner — seeded files must match."""
    uid, gid = _hermes_data_uid_gid()
    prof_dir.mkdir(parents=True, exist_ok=True)
    (prof_dir / "logs").mkdir(parents=True, exist_ok=True)
    for path in [prof_dir, *prof_dir.rglob("*")]:
        try:
            os.chown(path, uid, gid)
        except OSError:
            pass


def _seed_native_profile_on_disk(slug: str) -> bool:
    """Filesystem fallback when Hermes CLI cannot run (empty / crash-looping gateway)."""
    slug = _srv().safe_profile_slug(slug)
    prof_dir = _srv()._profile_dir(slug)
    prof_dir.mkdir(parents=True, exist_ok=True)
    config = prof_dir / "config.yaml"
    if not config.is_file():
        proxy = _srv()._llm_proxy_base_url("openrouter")
        config.write_text(
            "model:\n"
            "  default: google/gemini-2.5-flash\n"
            "  provider: custom\n"
            f"  base_url: {proxy}\n",
            encoding="utf-8",
        )
    soul = prof_dir / "SOUL.md"
    if not soul.is_file():
        soul.write_text(
            f"You are the {_srv().PROJECT_NAME} native agent — orchestrator and workspace admin.\n",
            encoding="utf-8",
        )
    _ensure_profile_toolsets(slug)
    _srv()._ensure_profile_terminal_cwd(slug)
    _register_profile_route(
        slug,
        {
            "display_name": f"{_srv().PROJECT_NAME} Agent",
            "role": f"{_srv().PROJECT_NAME} Manager",
        },
    )
    routes_path = _srv().ROUTES_JSON
    if routes_path.is_file():
        try:
            data = json.loads(routes_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and not data.get("default_profile"):
                data["default_profile"] = slug
                routes_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass
    _chown_profile_tree(prof_dir)
    return _native_profile_present()


def _ensure_native_hermes_profile() -> bool:
    """Idempotent: native workframe-agent must exist before gateway boot or DM bootstrap."""
    slug = _native_profile_slug()
    if _native_profile_present():
        return True
    shell = (
        "export HERMES_HOME=/opt/data HOME=/opt/data; "
        f"/opt/hermes/bin/hermes profile create {shlex.quote(slug)} --clone "
        f"--description {shlex.quote(f'{_srv().PROJECT_NAME} native agent')}"
    )
    try:
        code, out = _srv()._gateway_container_exec(["sh", "-lc", shell])
        if code == 0 and _native_profile_present():
            _register_profile_route(
                slug,
                {"display_name": f"{_srv().PROJECT_NAME} Agent", "role": f"{_srv().PROJECT_NAME} Manager"},
            )
            _chown_profile_tree(_srv()._profile_dir(slug))
            return True
        if "already exists" in out.lower() and _native_profile_present():
            _register_profile_route(
                slug,
                {"display_name": f"{_srv().PROJECT_NAME} Agent", "role": f"{_srv().PROJECT_NAME} Manager"},
            )
            _chown_profile_tree(_srv()._profile_dir(slug))
            return True
    except Exception:
        pass
    return _seed_native_profile_on_disk(slug)


def _primary_profile() -> str:
    if _srv().NATIVE_PROFILE and (_srv().HERMES_DATA / "profiles" / _srv().NATIVE_PROFILE).is_dir():
        return _srv().NATIVE_PROFILE
    profiles = _list_profiles()
    return profiles[0] if profiles else ""


def _profile_dir(profile: str) -> Path:
    return _srv().HERMES_DATA / "profiles" / profile


def _profile_gateway_config_path(profile: str) -> Path | None:
    """Hermes gateway reads platforms + model chain from config.yaml only."""
    d = _srv()._profile_dir(profile)
    if not d.is_dir():
        return None
    return d / "config.yaml"


def _ensure_gateway_config_file(profile: str) -> Path:
    path = _profile_gateway_config_path(profile)
    if path is None:
        raise ValueError(f"profile not found: {profile}")
    if path.is_file():
        return path
    provider, model = "", ""
    meta = _srv()._profile_dir(profile) / "profile.yaml"
    if meta.is_file():
        provider, model = _parse_model_fields_from_yaml(meta.read_text(encoding="utf-8"))
    seed = ""
    if model:
        seed = f"model:\n  default: {model}\n"
        if provider:
            seed += f"  provider: {provider}\n"
    path.write_text(seed, encoding="utf-8")
    return path


def _fix_invalid_model_header(raw: str) -> str:
    """Scalar `model: ''` breaks yaml.safe_load when proxy writers add nested keys."""
    lines = raw.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("model:") and not line.startswith((" ", "\t")):
            rest = stripped.split(":", 1)[1].strip().strip("'\"")
            if not rest:
                out.append("model:\n")
                continue
            if not stripped.endswith(":") and rest:
                out.append("model:\n")
                out.append(f"  default: {rest}\n")
                continue
        out.append(line)
    return "".join(out)


def _scrub_orphan_top_level_yaml_lines(profile: str) -> None:
    """Drop root-level list items (e.g. `- provider: openrouter`) left by corrupt writers."""
    config_path = _profile_gateway_config_path(profile)
    if not config_path or not config_path.is_file():
        return
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return
    out: list[str] = []
    changed = False
    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if indent == 0 and stripped.startswith("- "):
            changed = True
            continue
        out.append(line)
    if changed:
        try:
            config_path.write_text("".join(out), encoding="utf-8")
        except OSError:
            return


def _fix_model_child_indent(raw: str) -> str:
    """Re-indent model block keys to 2 spaces — fixes api_key nested under base_url scalar."""
    lines = raw.splitlines(keepends=True)
    out: list[str] = []
    in_model = False
    for line in lines:
        stripped = line.lstrip()
        if not line.startswith((" ", "\t")) and stripped.startswith("model:"):
            in_model = True
            out.append(line if line.endswith("\n") else f"{line}\n")
            continue
        if in_model:
            if stripped and not line.startswith((" ", "\t", "#")):
                in_model = False
                out.append(line)
                continue
            if stripped.startswith(("default:", "provider:", "base_url:", "api_key:")):
                _, _, val = stripped.partition(":")
                out.append(f"  {stripped.split(':', 1)[0]}:{val}\n")
                continue
        out.append(line)
    return "".join(out)


def _normalize_profile_config_yaml(profile: str) -> None:
    """Repair invalid model headers before gateway yaml parsers run (no pyyaml in API image)."""
    config_path = _profile_gateway_config_path(profile)
    if not config_path or not config_path.is_file():
        return
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError:
        return
    fixed = _fix_invalid_model_header(raw)
    fixed = _fix_model_child_indent(fixed)
    if fixed != raw:
        try:
            config_path.write_text(fixed, encoding="utf-8")
        except OSError:
            return
    _srv()._coalesce_profile_model_yaml(profile)
    _scrub_orphan_top_level_yaml_lines(profile)
    _srv()._ensure_profile_terminal_cwd(profile)


def _parse_model_fields_from_yaml(text: str) -> tuple[str, str]:
    provider = ""
    model_name = ""
    in_model_block = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line[:1].isspace() and line.endswith(":"):
            in_model_block = line[:-1].strip() == "model"
            continue
        if not in_model_block or ":" not in line:
            continue
        key, _, value = line.strip().partition(":")
        value = value.strip().strip('"').strip("'")
        if key == "default":
            model_name = value
        elif key == "provider":
            provider = value
    return provider, model_name


def _profile_config_path(profile: str) -> Path | None:
    """Readable profile yaml: prefer gateway config.yaml, else legacy profile.yaml metadata."""
    gateway = _profile_gateway_config_path(profile)
    if gateway and gateway.is_file():
        return gateway
    meta = _srv()._profile_dir(profile) / "profile.yaml"
    return meta if meta.is_file() else None


def _profile_home(profile: str) -> Path:
    return _srv()._profile_dir(profile)


def _render_soul_placeholders(text: str) -> str:
    native_slug = str(_srv().NATIVE_PROFILE or "workframe-agent").strip() or "workframe-agent"
    ctx = {
        "projectName": _srv().PROJECT_NAME,
        "nativeProfileSlug": native_slug,
        "nativeAgentName": _native_display_name(),
    }
    out = str(text or "")
    for key, value in ctx.items():
        out = out.replace(f"{{{key}}}", value)
    return out


def _soul_is_stub(text: str) -> bool:
    """True when SOUL is missing, trivial, unexpanded, or not Workframe identity."""
    body = str(text or "").strip()
    if len(body) < 80:
        return True
    low = body.lower()
    if any(token in low for token in ("{nativeagentname}", "{projectname}", "{nativeprofileslug}")):
        return True
    if "workframe" not in low and "botfather" not in low and "concierge" not in low:
        return True
    return False


def _format_child_template(template: str, **kwargs: str) -> str:
    ctx = {"nativeAgentName": _native_display_name(), **kwargs}
    return _render_soul_placeholders(template.format(**ctx))

_CHILD_SOUL_TEMPLATE = """# {display_name}

## Identity (highest priority)
You are **{display_name}** — a Workframe agent. When greeting or identifying yourself, use **{display_name}** — never the underlying model or provider name.

Mission
- {role}

## Hermes & Workframe
- Read `AGENTS.md` in this profile home for tools, skills, memory, and how to upkeep your `SOUL.md`.
- Read `/workspace/AGENTS.md` for project workspace rules.
- Load Hermes skills from `skills/` before specialized work.
- CLI: `/opt/hermes/.venv/bin/hermes -p <your-runtime-slug> …` via **terminal** tool.

Restrictions
- You are a child agent — you cannot create, delete, spawn, or reconfigure other agents.
- Escalate crew changes to the native Workframe agent ({nativeAgentName}).
"""

_CHILD_AGENTS_TEMPLATE = """# AGENTS — {display_name}

Operating rules for **{display_name}**. Identity lives in `SOUL.md` in this profile home.

## Tools & skills

- Load task-appropriate skills from `skills/` before specialized work.
- CLI: `/opt/hermes/.venv/bin/hermes -p <your-runtime-slug> …` via **terminal**.
- Read `WORKFRAME_COHORT.md` when present — use **runtime_slug** for kanban/delegate.

## Restrictions

- Child agent — **not** Botfather. Escalate crew changes to **{nativeAgentName}**.
- You may refine your own `SOUL.md` and notes when the user asks.

## Memory

- Outcomes in `/workspace`; evolve notes via Hermes memory when asked.
"""


def _soul_is_native_concierge(text: str) -> bool:
    low = str(text or "").lower()
    return "botfather" in low or "concierge" in low


def _strip_forbidden_child_skills(profile: str) -> list[str]:
    """Remove botfather/crew-manager skills from child profiles after native clone."""
    prof = _srv().safe_profile_slug(profile)
    skills_root = _srv()._profile_dir(prof) / "skills"
    if not skills_root.is_dir():
        return []
    removed: list[str] = []

    def walk(dir_path: Path) -> None:
        for entry in list(dir_path.iterdir()):
            if entry.is_dir():
                if entry.name in _FORBIDDEN_CHILD_SKILLS:
                    shutil.rmtree(entry, ignore_errors=True)
                    removed.append(entry.name)
                else:
                    walk(entry)
            elif entry.name == "SKILL.md":
                skill_name = entry.parent.name
                if skill_name in _FORBIDDEN_CHILD_SKILLS:
                    shutil.rmtree(entry.parent, ignore_errors=True)
                    removed.append(skill_name)

    walk(skills_root)
    return sorted(set(removed))


def _seed_native_user_overlay(
    runtime: str,
    template: str,
    *,
    display_name: str = "",
    role: str = "",
    tagline: str = "",
    user_soul: str = "",
) -> None:
    """Keep template SOUL/AGENTS on disk; layer user identity in registry overlay."""
    runtime = _srv().safe_profile_slug(runtime)
    template = _srv().safe_profile_slug(template)
    if not runtime:
        return
    _write_profile_soul_if_stub(runtime, template)
    if display_name.strip() or role.strip() or tagline.strip() or user_soul.strip():
        _apply_profile_identity(
            runtime,
            display_name=display_name,
            role=role,
            tagline=tagline,
            user_soul=user_soul,
        )


def _apply_profile_identity(
    profile: str,
    *,
    display_name: str = "",
    role: str = "",
    tagline: str = "",
    user_soul: str = "",
) -> None:
    prof = _srv().safe_profile_slug(profile)
    patch: dict[str, Any] = {}
    if display_name.strip():
        patch["display_name"] = display_name.strip()
    if role.strip():
        patch["role"] = role.strip()
    if tagline.strip():
        patch["tagline"] = tagline.strip()
    if user_soul.strip():
        patch["user_soul"] = user_soul.strip()
    if patch.get("display_name"):
        aid = _srv()._avatar_id_for_display_name(str(patch["display_name"]))
        if aid:
            patch.update(_srv()._normalize_agent_avatar_patch("", aid))
    if patch:
        _srv()._upsert_agent_registry_row(prof, patch)


def _profile_identity_overlay(profile: str) -> str:
    prof = _srv().safe_profile_slug(profile)
    if _srv()._is_runtime_profile_slug(prof):
        template = _runtime_template_slug(prof)
        reg = {**_srv()._agent_registry_row(template), **_srv()._agent_registry_row(prof)}
    else:
        reg = _srv()._agent_registry_row(prof)
    blocks: list[str] = []
    identity_lines: list[str] = []
    display = str(reg.get("display_name") or "").strip()
    role = str(reg.get("role") or reg.get("description") or "").strip()
    tagline = str(reg.get("tagline") or "").strip()
    if display:
        identity_lines.append(f"- **Name:** {display}")
    if role:
        identity_lines.append(f"- **Role:** {role}")
    if tagline:
        identity_lines.append(f"- **Tagline:** {tagline}")
    if identity_lines:
        blocks.append("## User identity\n" + "\n".join(identity_lines))
    user_soul = str(reg.get("user_soul") or "").strip()
    if user_soul:
        blocks.append("## Additional instructions\n" + user_soul)
    return "\n\n".join(blocks).strip()


def _install_child_base_artifacts(profile: str, *, display_name: str, role: str) -> bool:
    """Write child SOUL/AGENTS when profile was cloned from native concierge."""
    prof = _srv().safe_profile_slug(profile)
    if not prof or _is_native_profile(prof):
        return False
    label = display_name.strip() or _profile_display_name(prof)
    mission = role.strip() or f"{label} specialist for {_srv().PROJECT_NAME}."
    raw = _profile_soul_raw(prof)
    wrote = False
    if _soul_is_stub(raw) or _soul_is_native_concierge(raw):
        body = _format_child_template(_CHILD_SOUL_TEMPLATE, display_name=label, role=mission)
        soul_path = _srv()._profile_dir(prof) / "SOUL.md"
        soul_path.parent.mkdir(parents=True, exist_ok=True)
        soul_path.write_text(body if body.endswith("\n") else f"{body}\n", encoding="utf-8")
        wrote = True
    agents_path = _srv()._profile_dir(prof) / "AGENTS.md"
    if not agents_path.is_file():
        agents_body = _format_child_template(_CHILD_AGENTS_TEMPLATE, display_name=label)
        agents_path.write_text(agents_body.strip() + "\n", encoding="utf-8")
        wrote = True
    return wrote


def _profile_base_soul_text(profile: str) -> str:
    prof = _srv().safe_profile_slug(str(profile or "").strip())
    if not prof:
        return ""
    path = _profile_soul_path(prof)
    raw = ""
    try:
        if path.is_file():
            raw = path.read_text(encoding="utf-8-sig", errors="replace").strip()
    except OSError:
        raw = ""
    template = _runtime_template_slug(prof) if _srv()._is_runtime_profile_slug(prof) else prof
    if _soul_is_stub(raw) and template:
        tpl_path = _srv()._profile_dir(template) / "SOUL.md"
        try:
            if tpl_path.is_file() and tpl_path != path:
                raw = tpl_path.read_text(encoding="utf-8-sig", errors="replace").strip()
        except OSError:
            pass
    if not raw:
        return ""
    return _render_soul_placeholders(raw).strip()


def _profile_soul_text(profile: str) -> str:
    base = _profile_base_soul_text(profile)
    overlay = _profile_identity_overlay(profile)
    if base and overlay:
        return f"{base.rstrip()}\n\n---\n\n{overlay}"
    return overlay or base


def _write_profile_soul_if_stub(profile: str, template: str = "") -> bool:
    """Persist rendered template SOUL when runtime file is stub. Returns True if written."""
    prof = _srv().safe_profile_slug(profile)
    tpl = _srv().safe_profile_slug(template or (_runtime_template_slug(prof) if _srv()._is_runtime_profile_slug(prof) else prof))
    if not prof or not tpl:
        return False
    dst = _srv()._profile_dir(prof) / "SOUL.md"
    try:
        current = dst.read_text(encoding="utf-8-sig", errors="replace") if dst.is_file() else ""
    except OSError:
        current = ""
    if not _soul_is_stub(current):
        return False
    src = _srv()._profile_dir(tpl) / "SOUL.md"
    if not src.is_file():
        return False
    try:
        rendered = _render_soul_placeholders(src.read_text(encoding="utf-8-sig", errors="replace")).strip()
        if not rendered or _soul_is_stub(rendered):
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(rendered if rendered.endswith("\n") else f"{rendered}\n", encoding="utf-8")
        return True
    except OSError:
        return False


def _profile_soul_path(profile: str) -> Path:
    profile_soul = _profile_home(profile) / "SOUL.md"
    if profile_soul.is_file():
        return profile_soul
    if profile == _primary_profile():
        root_soul = _srv().HERMES_DATA / "SOUL.md"
        if root_soul.is_file():
            return root_soul
    return profile_soul


def _profile_soul_raw(profile: str) -> str:
    path = _profile_soul_path(profile)
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace").strip()
    except OSError:
        return ""


def _file_size_mb(path: Path) -> float:
    try:
        return path.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0




def gateway_data(profile: str) -> dict[str, Any]:
    path = _srv()._profile_dir(profile) / "gateway_state.json"
    base: dict[str, Any] = {
        "ok": False,
        "exists": path.is_file(),
        "state": "unknown",
        "platforms": {},
        "active_agents": 0,
        "uptime": None,
        "uptime_seconds": None,
        "updated_at": None,
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
    platforms = raw.get("platforms") or {}
    for name, info in platforms.items():
        if isinstance(info, dict) and "status" not in info:
            info = {**info, "status": info.get("state", "unknown")}
            platforms[name] = info
    base.update(
        {
            "ok": True,
            "state": raw.get("gateway_state") or raw.get("state") or "unknown",
            "kind": raw.get("kind"),
            "pid": raw.get("pid"),
            "platforms": platforms,
            "active_agents": raw.get("active_agents", 0),
            "updated_at": raw.get("updated_at"),
            "uptime": uptime,
            "uptime_seconds": uptime,
            "raw": raw,
        }
    )
    return base


def sessions_data(profile: str) -> dict[str, Any]:
    db = _srv()._profile_dir(profile) / "state.db"
    out: dict[str, Any] = {
        "ok": False,
        "count": 0,
        "session_count": 0,
        "message_count": 0,
        "recent": [],
    }
    conn = _srv()._ro_sqlite_live(db)
    if not conn:
        return out
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS sessions,
                   COALESCE(SUM(message_count), 0) AS messages
            FROM sessions
            """
        ).fetchone()
        recent = conn.execute(
            """
            SELECT id, source, title, started_at, ended_at, message_count,
                   model, estimated_cost_usd
            FROM sessions
            ORDER BY started_at DESC
            LIMIT 25
            """
        ).fetchall()
        count = int(row["sessions"] or 0)
        messages = int(row["messages"] or 0)
        out.update(
            {
                "ok": True,
                "count": count,
                "session_count": count,
                "message_count": messages,
                "recent": [
                    {
                        "id": r["id"],
                        "source": r["source"],
                        "title": r["title"] or "(untitled)",
                        "started_at": r["started_at"],
                        "started_at_iso": _srv()._iso_from_unix(r["started_at"]),
                        "ended_at": r["ended_at"],
                        "message_count": r["message_count"] or 0,
                        "model": r["model"] or "",
                        "cost_usd": r["estimated_cost_usd"],
                    }
                    for r in recent
                ],
            }
        )
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return out


def _profile_slug(profile: str) -> str:
    if profile.endswith("-agent"):
        return profile[: -len("-agent")]
    return profile


def _agent_label(profile: str) -> str:
    return _profile_slug(profile)


def _native_display_name() -> str:
    return f"{_srv().PROJECT_NAME} Agent"


def _is_native_profile(profile: str) -> bool:
    return bool(_srv().NATIVE_PROFILE and profile == _srv().NATIVE_PROFILE)


def _agent_db_display_name(template_slug: str, workspace_id: str = "") -> str:
    template_slug = _srv().safe_profile_slug(str(template_slug or "").strip())
    if not template_slug:
        return ""
    conn = _srv()._workframe_db()
    try:
        if workspace_id:
            row = _srv()._lookup_agent_profile(conn, workspace_id, template_slug)
        else:
            row = conn.execute(
                """
                SELECT display_name FROM agent_profiles
                WHERE slug = ? AND deleted_at IS NULL
                ORDER BY is_native DESC, updated_at DESC
                LIMIT 1
                """,
                (template_slug,),
            ).fetchone()
        if row and str(row["display_name"] or "").strip():
            return str(row["display_name"]).strip()
    finally:
        conn.close()
    return ""


def _profile_display_name(profile: str, workspace_id: str = "") -> str:
    template = _runtime_template_slug(profile) if _srv()._is_runtime_profile_slug(profile) else profile
    db_name = _agent_db_display_name(template, workspace_id)
    if db_name:
        return db_name
    reg = _srv()._agent_registry_row(template)
    if reg.get("display_name"):
        return str(reg["display_name"])
    if _is_native_profile(template):
        return _native_display_name()
    slug = _profile_slug(template)
    return slug.replace("-", " ").title()


def _default_session_title(profile: str) -> str:
    display = _profile_display_name(profile).strip() or "Agent"
    return f"Session with {display}"


def _create_profile_session_via_api(profile: str, session_id: str, title: str) -> tuple[int, Any, str]:
    base_title = (title or "").strip() or _default_session_title(profile)
    candidate = base_title
    for attempt in range(1, 25):
        status, data = _profile_api_request(
            profile,
            "POST",
            "/api/sessions",
            {"session_id": session_id, "title": candidate},
        )
        if status < 300:
            return status, data, candidate
        msg = json.dumps(data).lower() if isinstance(data, dict) else str(data).lower()
        if "invalid_title" not in msg and "already in use" not in msg:
            return status, data, candidate
        if attempt < 12:
            candidate = f"{base_title} ({attempt + 1})"
        else:
            candidate = f"{base_title} {int(time.time())}-{attempt}"
    return status, data, candidate


def _profile_role(profile: str) -> str:
    if _is_native_profile(profile):
        return (
            f"Workframe Manager and orchestrator for {_srv().PROJECT_NAME}. "
            "Routes work to installed specialist profiles."
        )
    slug = _profile_slug(profile)
    return _srv().SPECIALIST_ROLES.get(slug, f"{_profile_display_name(profile)} specialist profile.")


def _profile_code(display_name: str, slug: str) -> str:
    word = (display_name.split()[0] if display_name else slug)[:4]
    return word.upper() or "AGNT"


def safe_profile_slug(value: str) -> str:
    slug = (value or "").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", slug):
        raise ValueError("invalid profile")
    return slug


def profile_exists(profile: str) -> bool:
    return _srv()._profile_dir(profile).is_dir()


def route_status_for_profile(profile: str) -> str:
    if not profile_exists(profile):
        return "not_installed"
    return "available"


def _register_profile_route(profile: str, meta: dict[str, Any] | None = None) -> bool:
    """Append an on-disk profile to routes.json when missing (post profile_create)."""
    prof = _srv().safe_profile_slug(profile)
    if not profile_exists(prof):
        return False
    _srv().ROUTES_JSON.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {"version": 1, "routes": []}
    if _srv().ROUTES_JSON.is_file():
        try:
            parsed = json.loads(_srv().ROUTES_JSON.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                data = parsed
        except (OSError, json.JSONDecodeError):
            pass
    routes = data.get("routes")
    if not isinstance(routes, list):
        routes = []
        data["routes"] = routes
    if any(isinstance(row, dict) and str(row.get("profile") or "") == prof for row in routes):
        return False
    routes.append(_route_record(prof, meta))
    if not data.get("default_profile"):
        data["default_profile"] = _primary_profile()
    _srv().ROUTES_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def _route_record(profile: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = meta or {}
    slug = _srv().safe_profile_slug(profile)
    ident = _srv()._agent_identity_fields(slug)
    row = {
        "id": str(meta.get("id") or slug),
        "profile": slug,
        "display_name": str(ident.get("display_name") or meta.get("display_name") or _profile_display_name(slug)),
        "role": str(ident.get("role") or meta.get("role") or _profile_role(slug)),
        "mode": "lane",
        "route_status": route_status_for_profile(slug),
    }
    if ident.get("avatar_url"):
        row["avatar_url"] = str(ident["avatar_url"])
    if ident.get("avatar_id"):
        row["avatar_id"] = str(ident["avatar_id"])
    _srv()._resolve_avatar_fields(row)
    return row


def load_routes() -> dict[str, Any]:
    default_profile = _primary_profile()
    raw_routes: list[dict[str, Any]] = []
    if _srv().ROUTES_JSON.is_file():
        try:
            data = json.loads(_srv().ROUTES_JSON.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("routes"), list):
                raw_routes = data["routes"]
                if data.get("default_profile"):
                    default_profile = _srv().safe_profile_slug(str(data["default_profile"]))
        except (OSError, json.JSONDecodeError, ValueError):
            raw_routes = []

    routes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in raw_routes:
        if not isinstance(entry, dict):
            continue
        try:
            profile = _srv().safe_profile_slug(str(entry.get("profile") or entry.get("id") or ""))
        except ValueError:
            continue
        if not profile_exists(profile) or profile in seen:
            continue
        seen.add(profile)
        routes.append(_route_record(profile, entry))

    if not routes:
        for profile in _list_profiles():
            if profile in seen:
                continue
            seen.add(profile)
            routes.append(_route_record(profile, {}))

    route_profiles = {r["profile"] for r in routes}
    if default_profile and default_profile not in route_profiles and profile_exists(default_profile):
        routes.insert(0, _route_record(default_profile, {}))
        route_profiles.add(default_profile)
    native = _srv().safe_profile_slug(_srv().NATIVE_PROFILE) if _srv().NATIVE_PROFILE else ""
    if native and native not in route_profiles and profile_exists(native):
        routes.insert(0, _route_record(native, {}))
        route_profiles.add(native)
    if default_profile and default_profile not in route_profiles:
        default_profile = routes[0]["profile"] if routes else default_profile

    return {"ok": True, "default_profile": default_profile, "routes": routes}


def resolve_validated_profile(profile: str) -> str:
    raw = str(profile or _primary_profile()).strip()
    if _AGENT_PROFILE_UUID_RE.match(raw):
        resolved = _srv()._hermes_slug_from_agent_ref(raw)
        if resolved:
            raw = resolved
    slug = _srv().safe_profile_slug(raw)
    allowed = {r["profile"] for r in load_routes()["routes"]}
    if slug not in allowed:
        raise ValueError(f"unknown profile: {slug}")
    if not profile_exists(slug):
        raise ValueError(f"profile not installed: {slug}")
    return slug


_RUNTIME_PROFILE_RE = re.compile(r"^u-[a-z0-9][a-z0-9-]{0,62}$")


def _is_runtime_profile_slug(slug: str) -> bool:
    return bool(_RUNTIME_PROFILE_RE.fullmatch(str(slug or "").strip()))


def _runtime_template_slug(runtime: str) -> str:
    """Map per-user runtime slug u-{user}-{template} back to the template profile."""
    slug = _srv().safe_profile_slug(str(runtime or "").strip())
    if not _srv()._is_runtime_profile_slug(slug):
        return slug
    rest = slug[2:]
    templates: set[str] = {p for p in _list_profiles() if not _srv()._is_runtime_profile_slug(p)}
    templates.update(_srv().load_agent_registry().keys())
    native = _primary_profile()
    if native:
        templates.add(native)
    for template in sorted(templates, key=len, reverse=True):
        if rest == template or rest.endswith(f"-{template}"):
            return template
    return rest


_DEFAULT_CHAT_TOOLSETS = ("hermes-cli", "terminal")


def _chat_toolsets_for_profile(_profile: str = "") -> tuple[str, ...]:
    """Multi-user safety: runtime RBAC + exec credential guards, not disabled terminal."""
    return _DEFAULT_CHAT_TOOLSETS


def _ensure_profile_toolsets(profile: str, toolsets: tuple[str, ...] | None = None) -> None:
    """Ensure Hermes toolsets (e.g. terminal) are enabled on a profile config."""
    prof = _srv().safe_profile_slug(str(profile or "").strip())
    cfg_path = _profile_gateway_config_path(prof)
    if not prof or cfg_path is None:
        return
    _normalize_profile_config_yaml(prof)
    want = list(toolsets if toolsets is not None else _chat_toolsets_for_profile(prof))
    if _srv()._profile_toolsets_ready(prof, want):
        return
    try:
        import yaml

        cfg: dict[str, Any] = {}
        if cfg_path.is_file():
            loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
            cfg = loaded if isinstance(loaded, dict) else {}
        ts = cfg.setdefault("toolsets", [])
        if not isinstance(ts, list):
            ts = []
            cfg["toolsets"] = ts
        pts = cfg.setdefault("platform_toolsets", {})
        if not isinstance(pts, dict):
            pts = {}
            cfg["platform_toolsets"] = pts
        changed = False
        for name in want:
            if name not in ts:
                ts.append(name)
                changed = True
        for platform in ("api_server", "cli"):
            plat = pts.setdefault(platform, [])
            if not isinstance(plat, list):
                plat = []
                pts[platform] = plat
            for name in want:
                if name not in plat:
                    plat.append(name)
                    changed = True
        agent = cfg.setdefault("agent", {})
        if not isinstance(agent, dict):
            agent = {}
            cfg["agent"] = agent
        disabled = agent.get("disabled_toolsets") if isinstance(agent.get("disabled_toolsets"), list) else []
        for name in want:
            if name in disabled:
                disabled = [x for x in disabled if x != name]
                changed = True
        agent["disabled_toolsets"] = disabled
        if changed:
            cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    except (OSError, ImportError):
        return


def resolve_hermes_profile(profile: str) -> str:
    """Resolve a Hermes profile dir for API calls; runtime u-* slugs skip route rail."""
    raw = str(profile or _primary_profile()).strip()
    if _AGENT_PROFILE_UUID_RE.match(raw):
        resolved = _srv()._hermes_slug_from_agent_ref(raw)
        if resolved:
            raw = resolved
    slug = _srv().safe_profile_slug(raw)
    if _srv()._is_runtime_profile_slug(slug):
        if not profile_exists(slug):
            raise ValueError(f"profile not installed: {slug}")
        return slug
    return _srv().resolve_validated_profile(slug)
def profile_create(
    name: str,
    model: str = "",
    description: str = "",
    clone_from: str = "",
    soul: str = "",
    display_name: str = "",
    role: str = "",
    tagline: str = "",
    avatar_url: str = "",
    avatar_id: str = "",
    *,
    user_id: str = "",
    workspace_id: str = "",
    bootstrap_dm: bool = True,
) -> dict[str, Any]:
    """Create a new Hermes profile via docker exec. Returns profile info."""
    # Validate name: lowercase, alphanumeric, hyphens
    import re as _re
    if not _re.match(r'^[a-z][a-z0-9-]{0,63}$', name):
        raise ValueError("profile name must be lowercase alphanumeric, start with a letter, max 64 chars")
    
    # Check if profile already exists — register in workspace and return idempotently.
    pdir = _srv()._profile_dir(name)
    if pdir.exists():
        registry_patch: dict[str, Any] = {}
        if display_name.strip():
            registry_patch["display_name"] = display_name.strip()
        if role.strip():
            registry_patch["role"] = role.strip()
        elif description.strip():
            registry_patch["role"] = description.strip()
        if tagline.strip():
            registry_patch["tagline"] = tagline.strip()
        if description.strip():
            registry_patch["description"] = description.strip()
        if registry_patch:
            _srv()._upsert_agent_registry_row(name, registry_patch)
        _register_profile_route(
            name,
            {
                "display_name": display_name.strip() or name,
                "role": role.strip() or description.strip(),
            },
        )
        prof = _srv().resolve_validated_profile(name)
        _srv()._ensure_workspace_agent_profile_row(
            prof,
            workspace_id=workspace_id,
            display_name=display_name.strip() or prof,
            role=role.strip() or description.strip(),
            tagline=tagline.strip(),
        )
        soul_text = str(soul or "").strip()
        if soul_text:
            _apply_profile_identity(name, user_soul=soul_text)
        results: dict[str, Any] = {
            "ok": True,
            "profile": prof,
            "already_exists": True,
            "steps": [{"step": "reuse_existing_profile", "ok": True}],
        }
        if bootstrap_dm and user_id and workspace_id:
            try:
                lane = _srv().bootstrap_agent_dm_lane(
                    user_id,
                    workspace_id,
                    prof,
                    model=model,
                    bind_session=True,
                    room_name=display_name.strip() or prof,
                    created_by=user_id,
                )
                results["bootstrap"] = lane
                results["room_id"] = lane.get("room_id")
                results["runtime_profile"] = lane.get("runtime")
                results["session_id"] = lane.get("session_id")
                if lane.get("room"):
                    results["room"] = lane["room"]
                results["steps"].extend(lane.get("steps") or [])
            except Exception as exc:
                results["steps"].append({"step": "bootstrap_dm_lane", "ok": False, "error": str(exc)})
        return results
    
    prof = _srv().safe_profile_slug(name)
    if not clone_from.strip():
        try:
            clone_slug = _srv().resolve_validated_profile(_primary_profile())
        except ValueError as exc:
            raise ValueError(f"native agent profile required to spawn children: {exc}") from exc
    else:
        clone_slug = _srv().resolve_validated_profile(clone_from)
    results: dict[str, Any] = {"profile": prof, "steps": []}
    
    # 1. Create profile via hermes CLI — clone native capabilities minus forbidden skills.
    cmd = ["profile", "create", "--clone-from", clone_slug]
    if description:
        cmd.extend(["--description", description])
    cmd.append(prof)

    try:
        code, out = _srv()._gateway_exec(_primary_profile(), cmd)
        results["steps"].append({"step": "hermes_profile_create", "ok": code == 0, "output": out.strip()})
        if code != 0:
            raise ValueError(f"hermes profile create failed: {out.strip()}")
    except Exception as exc:
        results["steps"].append({"step": "hermes_profile_create", "ok": False, "error": str(exc)})
        raise

    removed_skills = _strip_forbidden_child_skills(prof)
    results["steps"].append({"step": "strip_forbidden_skills", "ok": True, "removed": removed_skills})
    child_label = display_name.strip() or prof.replace("-", " ").title()
    child_role = role.strip() or description.strip() or f"{child_label} specialist for {_srv().PROJECT_NAME}."
    if _install_child_base_artifacts(prof, display_name=child_label, role=child_role):
        results["steps"].append({"step": "install_child_base", "ok": True})
    
    # 2. Start the gateway for this profile
    try:
        ok, out, port = _srv()._configure_profile_api(prof)
        results["steps"].append({"step": "configure_api", "ok": ok, "api_port": port, "output": out.strip()})
        if ok:
            ok2, out2 = _srv()._patch_profile_gateway_run_script(prof)
            results["steps"].append({"step": "patch_run_script", "ok": ok2, "output": out2.strip()})
    except Exception as exc:
        results["steps"].append({"step": "configure_api", "ok": False, "error": str(exc)})
    
    # 3–4. Template model/gateway only when not bootstrapping a per-user DM runtime (C1).
    if not bootstrap_dm:
        if model:
            try:
                code, out = _srv()._gateway_exec(prof, ["model", model])
                results["steps"].append({"step": "set_model", "ok": code == 0, "model": model, "output": out.strip()})
            except Exception as exc:
                results["steps"].append({"step": "set_model", "ok": False, "error": str(exc)})
        try:
            state = _srv().profile_gateway_lifecycle(prof, "start")
            results["steps"].append({"step": "gateway_start", "ok": True, "state": state})
        except Exception as exc:
            results["steps"].append({"step": "gateway_start", "ok": False, "error": str(exc)})

    registry_patch: dict[str, Any] = {}
    if display_name.strip():
        registry_patch["display_name"] = display_name.strip()
    if role.strip():
        registry_patch["role"] = role.strip()
    elif description.strip():
        registry_patch["role"] = description.strip()
    if tagline.strip():
        registry_patch["tagline"] = tagline.strip()
    if description.strip():
        registry_patch["description"] = description.strip()
    if registry_patch:
        _srv()._upsert_agent_registry_row(prof, registry_patch)
        results["registry"] = registry_patch

    try:
        avatar = _srv()._assign_agent_avatar(
            prof,
            display_name=display_name.strip() or child_label,
        )
        results["avatar"] = avatar
        results["steps"].append({"step": "assign_avatar", "ok": True, **avatar})
    except Exception as exc:
        results["steps"].append({"step": "assign_avatar", "ok": False, "error": str(exc)})

    explicit_avatar = _srv()._normalize_agent_avatar_patch(avatar_url, avatar_id)
    if explicit_avatar.get("avatar_url") or explicit_avatar.get("avatar_id"):
        _srv()._upsert_agent_registry_row(
            prof,
            {
                **explicit_avatar,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        results["avatar"] = explicit_avatar

    soul_text = str(soul or "").strip()
    if soul_text:
        _apply_profile_identity(prof, user_soul=soul_text)
        results["steps"].append({"step": "seed_user_soul", "ok": True})

    _register_profile_route(
        prof,
        {
            "display_name": display_name.strip() or prof,
            "role": role.strip() or description.strip() or description,
        },
    )
    results["steps"].append({"step": "register_route", "ok": True})

    _srv()._ensure_workspace_agent_profile_row(
        prof,
        workspace_id=workspace_id,
        display_name=display_name.strip() or prof,
        role=role.strip() or description.strip(),
        tagline=tagline.strip(),
    )

    if bootstrap_dm and user_id and workspace_id:
        try:
            lane = _srv().bootstrap_agent_dm_lane(
                user_id,
                workspace_id,
                prof,
                model=model,
                bind_session=True,
                room_name=display_name.strip() or prof,
                created_by=user_id,
            )
            results["bootstrap"] = lane
            results["room_id"] = lane.get("room_id")
            results["runtime_profile"] = lane.get("runtime")
            results["session_id"] = lane.get("session_id")
            if lane.get("room"):
                results["room"] = lane["room"]
            results["steps"].extend(lane.get("steps") or [])
        except Exception as exc:
            results["steps"].append({"step": "bootstrap_dm_lane", "ok": False, "error": str(exc)})

    results["ok"] = True
    return results


def profile_delete(profile: str) -> dict[str, Any]:
    """Delete a child profile: stop gateway, remove directory, clean registries."""
    prof = _srv().resolve_validated_profile(profile)
    if prof == _primary_profile():
        raise ValueError("cannot delete the native profile")

    results: dict[str, Any] = {"profile": prof, "steps": []}

    # 1. Stop the gateway for this profile
    try:
        code, out = _srv()._gateway_exec(prof, ["gateway", "stop"])
        results["steps"].append({"step": "gateway_stop", "ok": code == 0, "output": out.strip()})
    except Exception as exc:
        results["steps"].append({"step": "gateway_stop", "ok": False, "error": str(exc)})

    # 2. Kill any remaining process for this profile
    try:
        cmd = ["pkill", "-f", f"hermes.*-p {prof}.*gateway"]
        code, out = _srv()._docker_exec(_srv().GATEWAY_CONTAINER_NAME, cmd)
        results["steps"].append({"step": "kill_process", "ok": True, "output": out.strip()})
    except Exception:
        results["steps"].append({"step": "kill_process", "ok": True, "output": "no process found"})

    # 3. Remove the profile directory (bypasses Hermes security guard)
    profile_dir = _srv()._profile_dir(prof)
    try:
        if profile_dir.exists():
            shutil.rmtree(str(profile_dir))
            results["steps"].append({"step": "remove_directory", "ok": True, "path": str(profile_dir)})
        else:
            results["steps"].append({"step": "remove_directory", "ok": True, "output": "directory not found"})
    except Exception as exc:
        results["steps"].append({"step": "remove_directory", "ok": False, "error": str(exc)})

    # 4. Remove from agents.json
    agents_json = _srv().HERMES_DATA / "workframe" / "agents.json"
    try:
        if agents_json.exists():
            data = json.loads(agents_json.read_text(encoding="utf-8"))
            if prof in data.get("agents", {}):
                del data["agents"][prof]
                agents_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                results["steps"].append({"step": "clean_agents_json", "ok": True})
            else:
                results["steps"].append({"step": "clean_agents_json", "ok": True, "output": "not in agents.json"})
    except Exception as exc:
        results["steps"].append({"step": "clean_agents_json", "ok": False, "error": str(exc)})

    # 5. Remove from avatar-registry.json
    avatar_json = _srv().HERMES_DATA / "workframe" / "avatar-registry.json"
    try:
        if avatar_json.exists():
            data = json.loads(avatar_json.read_text(encoding="utf-8"))
            changed = False
            if prof in data.get("assignments", {}):
                del data["assignments"][prof]
                changed = True
            if changed:
                avatar_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            results["steps"].append({"step": "clean_avatar_registry", "ok": True})
    except Exception as exc:
        results["steps"].append({"step": "clean_avatar_registry", "ok": False, "error": str(exc)})

    # 6. Remove from routes.json
    routes_json = _srv().HERMES_DATA / "workframe" / "routes.json"
    try:
        if routes_json.exists():
            data = json.loads(routes_json.read_text(encoding="utf-8"))
            original_len = len(data.get("routes", []))
            data["routes"] = [r for r in data.get("routes", []) if r.get("profile") != prof]
            if len(data["routes"]) < original_len:
                routes_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                results["steps"].append({"step": "clean_routes", "ok": True})
            else:
                results["steps"].append({"step": "clean_routes", "ok": True, "output": "not in routes"})
    except Exception as exc:
        results["steps"].append({"step": "clean_routes", "ok": False, "error": str(exc)})

    results["ok"] = all(s.get("ok", False) for s in results["steps"])
    return results
