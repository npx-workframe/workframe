"""WF-032 extract: Hermes admin/profile API and slash command catalog."""
from __future__ import annotations

import sqlite3
import time
from typing import Any

import run_surface_wiring


def _srv():
    import server as srv

    return srv


# Cache installed skill names for /api/hermes/commands/exec slash routing.
_skill_name_cache: dict[str, Any] = {"names": None, "expires_at": 0.0}
_SKILL_CACHE_TTL_SECONDS = 60


def _known_skill_names() -> set[str]:
    now = time.time()
    cached = _skill_name_cache.get("names")
    if cached is not None and _skill_name_cache.get("expires_at", 0) > now:
        return cached
    try:
        names = {str(s.get("name", "")).strip() for s in _srv().hermes_skills() if s.get("name")}
    except Exception:
        names = cached or set()
    _skill_name_cache["names"] = names
    _skill_name_cache["expires_at"] = now + _SKILL_CACHE_TTL_SECONDS
    return names


def _is_known_skill(name: str) -> bool:
    if not name:
        return False
    return name in _known_skill_names()


# Static mirror of Hermes' COMMAND_REGISTRY (hermes_cli/commands.py).
# The BFF does not import hermes_agent; it serves a curated snapshot so the
# Workframe UI has a fast, local source of truth for the slash palette.
# Drift is acceptable: any new command lands here in the same release that
# updates upstream Hermes. See workframe-api dead-code note for context.
HERMES_COMMANDS: list[dict[str, Any]] = [
    # Session
    {"name": "/new", "aliases": ["/reset"], "category": "Session",
     "description": "Fresh session", "args_hint": "",
     "dispatch": "client:startNewSession"},
    {"name": "/clear", "aliases": [], "category": "Session",
     "description": "Clear screen + new session", "args_hint": "",
     "dispatch": "client:clearMessages"},
    {"name": "/retry", "aliases": [], "category": "Session",
     "description": "Resend last message", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/undo", "aliases": [], "category": "Session",
     "description": "Remove last exchange", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/compress", "aliases": [], "category": "Session",
     "description": "Manually compress context", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/stop", "aliases": [], "category": "Session",
     "description": "Kill background processes", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/rollback", "aliases": [], "category": "Session",
     "description": "Restore filesystem checkpoint", "args_hint": "[N]",
     "dispatch": "gateway"},
    {"name": "/snapshot", "aliases": [], "category": "Session",
     "description": "Create or restore state snapshots", "args_hint": "[sub]",
     "dispatch": "gateway"},
    {"name": "/background", "aliases": [], "category": "Session",
     "description": "Run prompt in background", "args_hint": "<prompt>",
     "dispatch": "gateway"},
    {"name": "/queue", "aliases": [], "category": "Session",
     "description": "Queue for next turn", "args_hint": "<prompt>",
     "dispatch": "gateway"},
    {"name": "/steer", "aliases": [], "category": "Session",
     "description": "Inject after the next tool call", "args_hint": "<prompt>",
     "dispatch": "gateway"},
    {"name": "/agents", "aliases": ["/tasks"], "category": "Session",
     "description": "Show active agents and running tasks", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/resume", "aliases": [], "category": "Session",
     "description": "Resume a named session", "args_hint": "[name]",
     "dispatch": "gateway"},
    {"name": "/goal", "aliases": [], "category": "Session",
     "description": "Set a standing goal", "args_hint": "[text|sub]",
     "dispatch": "gateway"},
    {"name": "/redraw", "aliases": [], "category": "Session",
     "description": "Force a full UI repaint", "args_hint": "",
     "dispatch": "client:noOp"},

    # Configuration
    {"name": "/model", "aliases": [], "category": "Configuration",
     "description": "Show or change model", "args_hint": "[name]",
     "dispatch": "client:openModelSwitcher"},
    {"name": "/personality", "aliases": [], "category": "Configuration",
     "description": "Set personality", "args_hint": "[name]",
     "dispatch": "client:openPersonality"},
    {"name": "/reasoning", "aliases": [], "category": "Configuration",
     "description": "Set reasoning", "args_hint": "[level]",
     "dispatch": "gateway"},
    {"name": "/verbose", "aliases": [], "category": "Configuration",
     "description": "Cycle verbose level", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/voice", "aliases": [], "category": "Configuration",
     "description": "Voice mode", "args_hint": "[on|off|tts]",
     "dispatch": "gateway"},
    {"name": "/yolo", "aliases": [], "category": "Configuration",
     "description": "Toggle approval bypass", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/busy", "aliases": [], "category": "Configuration",
     "description": "What Enter does while working", "args_hint": "[sub]",
     "dispatch": "gateway"},
    {"name": "/indicator", "aliases": [], "category": "Configuration",
     "description": "Busy indicator style", "args_hint": "[style]",
     "dispatch": "gateway"},
    {"name": "/footer", "aliases": [], "category": "Configuration",
     "description": "Gateway runtime footer on replies", "args_hint": "[on|off]",
     "dispatch": "gateway"},
    {"name": "/skin", "aliases": [], "category": "Configuration",
     "description": "Change theme (CLI)", "args_hint": "[name]",
     "dispatch": "gateway"},
    {"name": "/statusbar", "aliases": [], "category": "Configuration",
     "description": "Toggle status bar (CLI)", "args_hint": "",
     "dispatch": "gateway"},

    # Tools & Skills
    {"name": "/tools", "aliases": [], "category": "Tools & Skills",
     "description": "Manage tools", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/toolsets", "aliases": [], "category": "Tools & Skills",
     "description": "List toolsets", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/skills", "aliases": [], "category": "Tools & Skills",
     "description": "Search/install skills", "args_hint": "",
     "dispatch": "client:openSkills"},
    {"name": "/skill", "aliases": [], "category": "Tools & Skills",
     "description": "Load a skill into session", "args_hint": "<name>",
     "dispatch": "gateway"},
    {"name": "/reload-skills", "aliases": [], "category": "Tools & Skills",
     "description": "Re-scan ~/.hermes/skills/", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/reload", "aliases": [], "category": "Tools & Skills",
     "description": "Reload .env into running session", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/reload-mcp", "aliases": [], "category": "Tools & Skills",
     "description": "Reload MCP servers", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/cron", "aliases": [], "category": "Tools & Skills",
     "description": "Manage cron jobs", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/curator", "aliases": [], "category": "Tools & Skills",
     "description": "Skill lifecycle", "args_hint": "[sub]",
     "dispatch": "gateway"},
    {"name": "/kanban", "aliases": [], "category": "Tools & Skills",
     "description": "Multi-profile board", "args_hint": "[sub]",
     "dispatch": "gateway"},
    {"name": "/plugins", "aliases": [], "category": "Tools & Skills",
     "description": "List plugins", "args_hint": "",
     "dispatch": "gateway"},

    # Utility
    {"name": "/branch", "aliases": ["/fork"], "category": "Utility",
     "description": "Branch the current session", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/fast", "aliases": [], "category": "Utility",
     "description": "Toggle priority/fast processing", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/browser", "aliases": [], "category": "Utility",
     "description": "Open CDP browser connection", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/history", "aliases": [], "category": "Utility",
     "description": "Show conversation history", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/save", "aliases": [], "category": "Utility",
     "description": "Save conversation to file", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/copy", "aliases": [], "category": "Utility",
     "description": "Copy last assistant reply", "args_hint": "[N]",
     "dispatch": "gateway"},
    {"name": "/paste", "aliases": [], "category": "Utility",
     "description": "Attach clipboard image", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/image", "aliases": [], "category": "Utility",
     "description": "Attach local image file", "args_hint": "",
     "dispatch": "gateway"},

    # Info
    {"name": "/help", "aliases": [], "category": "Info",
     "description": "Show commands", "args_hint": "",
     "dispatch": "client:openHelp"},
    {"name": "/status", "aliases": [], "category": "Info",
     "description": "Session info", "args_hint": "",
     "dispatch": "client:openStatus"},
    {"name": "/usage", "aliases": [], "category": "Info",
     "description": "Token usage for the active session", "args_hint": "",
     "dispatch": "client:openUsage"},
    {"name": "/insights", "aliases": [], "category": "Info",
     "description": "Usage analytics", "args_hint": "[days]",
     "dispatch": "client:openInsights"},
    {"name": "/gquota", "aliases": [], "category": "Info",
     "description": "Google Gemini quota", "args_hint": "",
     "dispatch": "client:openGquota"},
    {"name": "/commands", "aliases": [], "category": "Info",
     "description": "Browse all commands", "args_hint": "[page]",
     "dispatch": "client:openHelp"},
    {"name": "/profile", "aliases": [], "category": "Info",
     "description": "Active profile info", "args_hint": "",
     "dispatch": "client:openProfile"},
    {"name": "/debug", "aliases": [], "category": "Info",
     "description": "Upload debug report", "args_hint": "",
     "dispatch": "client:openDebug"},

    # Exit
    {"name": "/quit", "aliases": ["/exit", "/q"], "category": "Exit",
     "description": "Exit CLI", "args_hint": "",
     "dispatch": "client:noOp"},
]


def _resolve_command(token: str) -> dict[str, Any] | None:
    """Resolve a slash token (with or without leading /) to a wired
    catalog entry. Wip commands are internal-only â€” they live in
    `HERMES_COMMANDS` for the team to track progress, but `_resolve_command`
    treats them as not-found so the user can never accidentally invoke
    something that isn't wired end-to-end.
    """
    if not token:
        return None
    needle = token if token.startswith("/") else f"/{token}"
    for entry in HERMES_COMMANDS:
        if entry.get("wip", False):
            continue
        if entry["name"] == needle or needle in entry.get("aliases", []):
            return entry
    return None




def hermes_usage() -> dict[str, Any]:
    """Token usage for the latest session of the active profile."""
    profile = _srv()._primary_profile()
    if not profile:
        return {"ok": False, "error": "no active profile"}

    session_id = _srv()._latest_session_id(profile)
    if not session_id:
        return {"ok": True, "profile": profile, "session": None}

    db = _srv()._profile_dir(profile) / "state.db"
    conn = _srv()._ro_sqlite_live(db)
    if not conn:
        return {"ok": False, "error": "state.db not reachable"}

    try:
        row = conn.execute(
            "SELECT title, model, message_count, started_at, ended_at, "
            "tool_call_count, input_tokens, output_tokens "
            "FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if not row:
            return {"ok": True, "profile": profile, "session": None}

        input_tokens = int(row["input_tokens"] or 0)
        output_tokens = int(row["output_tokens"] or 0)

        return {
            "ok": True,
            "profile": profile,
            "session": {
                "id": str(session_id)[:12] + "â€¦",
                "title": row["title"] or "(untitled)",
                "model": row["model"] or "â€”",
                "message_count": int(row["message_count"] or 0),
                "tool_call_count": int(row["tool_call_count"] or 0),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "started_at": _srv()._iso_from_unix(row["started_at"]),
                "ended_at": _srv()._iso_from_unix(row["ended_at"]) if row["ended_at"] else None,
            },
        }
    except sqlite3.Error as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def hermes_gateway_exec(
    line: str,
    profile: str = "",
    user_id: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    """Execute a slash command through the Hermes CLI.

    Runs `hermes -p {profile} {cmd}` via Docker exec in the gateway
    container. This bypasses the streaming chat endpoint â€” slash commands
    are processed synchronously by the CLI's command handler and the
    output is returned immediately.
    """
    prof = _srv().resolve_validated_profile(profile) if profile else _srv()._primary_profile()
    if not prof:
        return {"ok": False, "error": "no active profile"}

    if not _srv()._user_may_access_runtime_profile(user_id, prof, workspace_id):
        return {"ok": False, "error": "profile_access_denied", "profile": prof}

    text = (line or "").strip()
    if not text:
        return {"ok": False, "error": "empty command"}

    # Parse the command: first token is the command name (with or without
    # leading /), rest is args.
    parts = text.split(None, 1)
    cmd_token = parts[0].lstrip("/")
    cmd_args = parts[1] if len(parts) > 1 else ""

    # Build the CLI command.
    cli_args = [cmd_token]
    if cmd_args:
        cli_args.extend(cmd_args.split())

    if _srv()._exec_targets_runtime_profile_secrets(cli_args, prof) or _srv()._exec_targets_runtime_profile_secrets(
        ["hermes", "-p", prof, *cli_args], prof,
    ):
        return {"ok": False, "error": "blocked_credential_path", "profile": prof}

    run_id: str | None = None
    try:
        run_id, decision = run_surface_wiring.begin_slash_run(
            cmd_token=cmd_token,
            line=text,
            profile_slug=prof,
            user_id=user_id,
            workspace_id=workspace_id,
        )
        if decision is not None and not decision.allowed:
            return {
                "ok": False,
                "error": str(decision.deny_reason or "run_denied"),
                "run_id": run_id,
                "profile": prof,
                "command": cmd_token,
            }
    except Exception as exc:  # noqa: BLE001
        _srv()._log_handler_error("hermes_gateway_exec.run_ledger", exc)

    try:
        rc, output = _srv()._gateway_exec(prof, cli_args)
        out = output.strip() if output else ""
        if run_id:
            try:
                run_surface_wiring.finish_surface_run(run_id, ok=rc == 0, detail=out)
            except Exception as exc:  # noqa: BLE001
                _srv()._log_handler_error("hermes_gateway_exec.finish_run", exc)
        return {
            "ok": rc == 0,
            "profile": prof,
            "command": cmd_token,
            "rc": rc,
            "output": out,
            "run_id": run_id,
        }
    except Exception as exc:
        if run_id:
            try:
                run_surface_wiring.finish_surface_run(run_id, ok=False, detail=str(exc))
            except Exception as finish_exc:  # noqa: BLE001
                _srv()._log_handler_error("hermes_gateway_exec.finish_run", finish_exc)
        return {"ok": False, "error": str(exc), "run_id": run_id}




def hermes_profile() -> dict[str, Any]:
    """Active profile info for the /profile dialog."""
    profile = _srv()._primary_profile()
    if not profile:
        return {"ok": False, "error": "no active profile"}

    soul_path = _srv()._profile_soul_path(profile)
    description = ""
    if soul_path.is_file():
        try:
            text = soul_path.read_text(encoding="utf-8", errors="replace")
            for raw in text.splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                description = line[:200]
                break
        except Exception:
            description = ""

    try:
        state = _srv().gateway_data(profile)
        gateway_running = bool(state.get("ok")) and str(state.get("state") or "").lower() == "running"
    except Exception:
        gateway_running = False

    session_id = _srv()._latest_session_id(profile)
    session_info = None
    if session_id:
        try:
            info = _srv()._session_info(profile, session_id)
            session_info = {
                "id": str(session_id)[:12] + "â€¦",
                "title": info.get("session_title", ""),
                "message_count": info.get("message_count", 0),
                "model": info.get("model", ""),
            }
        except Exception:
            pass

    return {
        "ok": True,
        "profile": profile,
        "description": description,
        "gateway_running": gateway_running,
        "session": session_info,
    }


def _agent_db_row(template_slug: str, workspace_id: str = "") -> dict[str, Any]:
    template_slug = _srv().safe_profile_slug(str(template_slug or "").strip())
    if not template_slug:
        return {}
    conn = _srv()._workframe_db()
    try:
        if workspace_id:
            row = _srv()._lookup_agent_profile(conn, workspace_id, template_slug)
        else:
            row = conn.execute(
                """
                SELECT display_name, tagline, role, avatar_url
                FROM agent_profiles
                WHERE slug = ? AND deleted_at IS NULL
                ORDER BY is_native DESC, updated_at DESC
                LIMIT 1
                """,
                (template_slug,),
            ).fetchone()
        if not row:
            return {}
        return {
            "display_name": str(row["display_name"] or "").strip(),
            "tagline": str(row["tagline"] or "").strip() if "tagline" in row.keys() else "",
            "role": str(row["role"] or "").strip() if "role" in row.keys() else "",
            "avatar_url": str(row["avatar_url"] or "").strip() if "avatar_url" in row.keys() else "",
        }
    finally:
        conn.close()


def hermes_profile_detail(profile: str, workspace_id: str = "") -> dict[str, Any]:
    """Profile metadata + SOUL + model surface for a specific Hermes profile."""
    prof = _srv().resolve_validated_profile(profile)
    reg = _srv()._agent_registry_row(prof)
    db_row = _agent_db_row(prof, workspace_id)
    soul_text = _srv()._profile_soul_text(prof)
    block = _srv()._read_model_block(prof)
    try:
        state = _srv().gateway_data(prof)
        gateway_running = bool(state.get("ok")) and str(state.get("state") or "").lower() == "running"
        gateway_state = str(state.get("state") or "unknown")
    except Exception:
        gateway_running = False
        gateway_state = "unknown"
    row: dict[str, Any] = {
        "ok": True,
        "profile": prof,
        "display_name": str(
            db_row.get("display_name")
            or reg.get("display_name")
            or _srv()._profile_display_name(prof, workspace_id)
        ),
        "role": str(db_row.get("role") or reg.get("role") or _srv()._profile_role(prof)),
        "tagline": str(db_row.get("tagline") or reg.get("tagline") or ""),
        "description": str(reg.get("description") or ""),
        "soul": soul_text,
        "soul_exists": bool(soul_text),
        "gateway_running": gateway_running,
        "gateway_state": gateway_state,
        "model": block.get("default", ""),
        "provider": block.get("provider", ""),
        "is_native": _srv()._is_native_profile(prof),
    }
    avatar_url = str(db_row.get("avatar_url") or reg.get("avatar_url") or "").strip()
    if avatar_url:
        row["avatar_url"] = avatar_url
    if reg.get("avatar_id"):
        row["avatar_id"] = str(reg["avatar_id"])
    _srv()._resolve_avatar_fields(row)
    return row


def hermes_profile_update(profile: str, body: dict[str, Any]) -> dict[str, Any]:
    """Update Workframe agent registry metadata for a Hermes profile."""
    prof = _srv().resolve_validated_profile(profile)
    allowed = {"display_name", "role", "tagline", "description", "avatar_url", "avatar_id"}
    patch: dict[str, Any] = {}
    for key in allowed:
        if key not in body:
            continue
        value = body[key]
        patch[key] = str(value).strip() if value is not None else ""
    if "avatar_url" in patch:
        _srv()._validate_me_profile_updates({"avatar_url": patch["avatar_url"]})
    if not patch:
        return {"ok": False, "error": "no_allowed_fields"}
    _srv()._upsert_agent_registry_row(prof, patch)
    _srv()._sync_agent_profile_db(prof, patch)
    return {"ok": True, "profile": prof, **patch}


def profile_soul_get(profile: str) -> dict[str, Any]:
    prof = _srv().resolve_validated_profile(profile)
    text = _srv()._profile_soul_text(prof)
    path = _srv()._profile_soul_path(prof)
    return {
        "ok": True,
        "profile": prof,
        "soul": text,
        "path": str(path),
        "exists": path.is_file(),
    }


def profile_soul_set(profile: str, soul: str) -> dict[str, Any]:
    prof = _srv().resolve_validated_profile(profile)
    if _srv()._is_native_profile(prof):
        path = _srv()._profile_soul_path(prof)
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = soul if not soul or soul.endswith("\n") else f"{soul}\n"
        path.write_text(normalized, encoding="utf-8")
        return {"ok": True, "profile": prof, "bytes": len(normalized.encode("utf-8")), "target": "soul_file"}
    lookup = _srv()._runtime_template_slug(prof) if _srv()._is_runtime_profile_slug(prof) else prof
    _srv()._apply_profile_identity(lookup, user_soul=soul)
    return {"ok": True, "profile": prof, "bytes": len(soul.encode("utf-8")), "target": "user_soul_overlay"}


def hermes_debug() -> dict[str, Any]:
    """Debug info for the /debug dialog."""
    profile = _srv()._primary_profile()
    if not profile:
        return {"ok": False, "error": "no active profile"}

    import platform as plat
    import sys

    db = _srv()._profile_dir(profile) / "state.db"
    conn = _srv()._ro_sqlite_live(db)
    session_count = 0
    message_count = 0
    if conn:
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM sessions").fetchone()
            session_count = row["cnt"] if row else 0
            row = conn.execute("SELECT COUNT(*) as cnt FROM messages").fetchone()
            message_count = row["cnt"] if row else 0
        except Exception:
            pass
        finally:
            conn.close()

    return {
        "ok": True,
        "profile": profile,
        "python_version": sys.version,
        "platform": plat.platform(),
        "session_count": session_count,
        "message_count": message_count,
    }


def hermes_insights() -> dict[str, Any]:
    """Usage analytics for the /insights dialog."""
    profile = _srv()._primary_profile()
    if not profile:
        return {"ok": False, "error": "no active profile"}

    db = _srv()._profile_dir(profile) / "state.db"
    conn = _srv()._ro_sqlite_live(db)
    if not conn:
        return {"ok": False, "error": "state.db not reachable"}

    try:
        # Total tokens per day (last 7 days)
        rows = conn.execute(
            "SELECT DATE(started_at, 'unixepoch') as day, "
            "SUM(input_tokens) as input_tok, SUM(output_tokens) as output_tok, "
            "COUNT(*) as sessions "
            "FROM sessions "
            "WHERE started_at > strftime('%s', 'now', '-7 days') "
            "GROUP BY day ORDER BY day DESC"
        ).fetchall()

        daily = []
        for r in rows:
            daily.append({
                "day": r["day"] or "unknown",
                "input_tokens": int(r["input_tok"] or 0),
                "output_tokens": int(r["output_tok"] or 0),
                "sessions": int(r["sessions"] or 0),
            })

        # Model usage breakdown
        model_rows = conn.execute(
            "SELECT model, COUNT(*) as cnt, SUM(input_tokens) as input_tok "
            "FROM sessions GROUP BY model ORDER BY cnt DESC LIMIT 10"
        ).fetchall()

        models = []
        for r in model_rows:
            models.append({
                "model": r["model"] or "unknown",
                "sessions": int(r["cnt"] or 0),
                "input_tokens": int(r["input_tok"] or 0),
            })

        return {"ok": True, "profile": profile, "daily": daily, "models": models}
    except sqlite3.Error as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def hermes_gquota() -> dict[str, Any]:
    """Google Gemini quota info â€” stub until Google API is configured."""
    profile = _srv()._primary_profile()
    if not profile:
        return {"ok": False, "error": "no active profile"}
    return {
        "ok": True,
        "profile": profile,
        "configured": False,
        "message": "Google Gemini quota: not configured. Set GOOGLE_API_KEY in .env to enable.",
    }


def hermes_commands_catalog() -> dict[str, Any]:
    """Categorized slash command catalog for the Workframe composer palette.

    `wip` commands are an internal tracker â€” they exist in
    `HERMES_COMMANDS` so the team can see what's still to wire, but
    they aren't returned here. The UI never sees a half-implemented
    command; either it's wired end-to-end or it's invisible.
    """
    visible = [e for e in HERMES_COMMANDS if not e.get("wip", False)]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in visible:
        grouped.setdefault(entry["category"], []).append(
            {
                "name": entry["name"],
                "aliases": entry.get("aliases", []),
                "description": entry["description"],
                "args_hint": entry.get("args_hint", ""),
                "dispatch": entry["dispatch"],
            }
        )
    categories = [
        {"name": name, "commands": [
            (cmd["name"], cmd["description"]) for cmd in items
        ]}
        for name, items in grouped.items()
    ]
    return {
        "ok": True,
        "categories": categories,
        "entries": [
            {**entry, "wired": True}
            for entry in visible
        ],
    }


def hermes_commands_exec(line: str) -> dict[str, Any]:
    """Resolve a slash command line and return a dispatch decision for the UI.

    The BFF does not run client-side UI effects; it classifies the command
    and returns a hint. The UI executes the hint. For commands that need to
    round-trip the gateway (`/auth`, `/config`, etc.) the BFF returns a
    `gateway` dispatch and the UI calls a separate gateway proxy endpoint.

    Skills (`/skillname` where the skill is installed in Hermes) aren't in
    the static catalog. The BFF falls back to a skill-name lookup so the
    UI gets a clean "this is dispatchable" decision rather than "unknown
    command" for every installed skill.
    """
    raw = (line or "").strip()
    if not raw.startswith("/"):
        return {"ok": False, "error": "not a slash command", "line": raw}
    parts = raw.split(maxsplit=1)
    token = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    entry = _resolve_command(token)
    if entry is None:
        # Fallback: is this an installed skill? Skills route through
        # the gateway once the gateway hookup lands (Slice 2). For now
        # the UI gets a `gateway` dispatch so the user sees the same
        # "real command, gateway side not wired yet" hint as the other
        # gateway-class commands.
        skill_name = token.lstrip("/")
        if _is_known_skill(skill_name):
            return {
                "ok": True,
                "dispatched": "gateway",
                "command": token,
                "args": rest,
                "message": f"Skill: {skill_name} â€” gateway dispatch coming in Slice 2",
            }
        return {
            "ok": False,
            "error": f"unknown command: {token}",
            "suggestion": "/help",
        }
    dispatch = entry["dispatch"]
    if dispatch == "noop":
        return {
            "ok": True,
            "dispatched": "noop",
            "command": entry["name"],
            "args": rest,
            "message": "Not yet wired in Workframe â€” see M2 in the Workframe roadmap.",
        }
    if dispatch.startswith("client:"):
        return {
            "ok": True,
            "dispatched": "client",
            "command": entry["name"],
            "args": rest,
            "handler": dispatch.split(":", 1)[1],
        }
    if dispatch.startswith("bff:"):
        return {
            "ok": True,
            "dispatched": "bff",
            "command": entry["name"],
            "args": rest,
            "handler": dispatch.split(":", 1)[1],
        }
    return {
        "ok": True,
        "dispatched": "gateway",
        "command": entry["name"],
        "args": rest,
    }


