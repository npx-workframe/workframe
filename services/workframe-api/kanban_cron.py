"""WF-032 extract: kanban_cron."""
from __future__ import annotations

import json
import os
import queue
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from http.server import BaseHTTPRequestHandler

import user_prefs


def _srv():
    import server as srv

    return srv


def _iter_kanban_dbs() -> list[Path]:
    dbs = [_srv().HERMES_DATA / "kanban.db"]
    boards_root = _srv().HERMES_DATA / "kanban" / "boards"
    if boards_root.is_dir():
        for board_dir in boards_root.iterdir():
            if board_dir.is_dir():
                candidate = board_dir / "kanban.db"
                if candidate.is_file():
                    dbs.append(candidate)
    return dbs


def _refresh_active_kanban_assignee_credentials() -> None:
    """Keep kanban worker profile .env aligned with assignee owner (not last chatter)."""
    assignees: set[str] = set()
    for db_path in _iter_kanban_dbs():
        conn = _srv()._ro_sqlite_live(db_path)
        if not conn:
            continue
        try:
            rows = conn.execute(
                """
                SELECT DISTINCT assignee FROM tasks
                WHERE status IN ('ready', 'running', 'scheduled', 'triage')
                  AND assignee LIKE 'u-%'
                """
            ).fetchall()
            for row in rows:
                slug = _srv().safe_profile_slug(str(row["assignee"] or "").strip())
                if slug:
                    assignees.add(slug)
        except sqlite3.Error:
            pass
        finally:
            conn.close()
    for assignee in assignees:
        resolved = _srv()._resolve_runtime_owner(assignee)
        if not resolved:
            continue
        owner_id, workspace_id = resolved
        _srv()._prepare_runtime_profile_credentials(assignee, owner_id, workspace_id)


def _kanban_credential_guard_daemon() -> None:
    while True:
        try:
            _refresh_active_kanban_assignee_credentials()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(5)
def validate_kanban_assignee(
    assignee: str,
    acting_user_id: str,
    workspace_id: str,
    *,
    delegate_user_ids: frozenset[str] | None = None,
    allow_template: bool = False,
) -> tuple[bool, str]:
    """Check whether acting_user may create/dispatch a task to assignee.

    Returns (ok, reason_or_owner_user_id).
    """
    assignee = _srv().safe_profile_slug(str(assignee or "").strip())
    acting = str(acting_user_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if not assignee:
        return False, "assignee_required"
    if not acting or not workspace_id:
        return False, "acting_user_required"
    if delegate_user_ids is None:
        delegate_user_ids = frozenset(_srv()._delegation_grantor_ids_for_grantee(acting, workspace_id))
    if _srv()._is_runtime_profile_slug(assignee):
        owner = _srv()._user_id_for_runtime_slug(assignee, workspace_id)
        if not owner:
            return False, "assignee_not_in_workspace"
        allowed = {acting} | set(delegate_user_ids or ())
        if owner in allowed:
            return True, owner
        return False, "assignee_owner_forbidden"
    if allow_template:
        return True, "template"
    return False, "template_assignee_forbidden"
def _hermes_kanban_db_path(board_slug: str) -> Path:
    slug = _srv().safe_profile_slug(str(board_slug or "default").strip()) or "default"
    if slug == "default":
        return _srv().HERMES_DATA / "kanban.db"
    return _srv().HERMES_DATA / "kanban" / "boards" / slug / "kanban.db"


def _workspace_kanban_board_row(workspace_id: str) -> sqlite3.Row | None:
    conn = _srv()._workframe_db()
    try:
        return conn.execute(
            """
            SELECT * FROM workspace_kanban_boards
            WHERE workspace_id = ? AND deleted_at IS NULL
            LIMIT 1
            """,
            (workspace_id,),
        ).fetchone()
    finally:
        conn.close()


def ensure_workspace_kanban_board(workspace_id: str) -> str:
    workspace_id = str(workspace_id or "").strip()
    row = _workspace_kanban_board_row(workspace_id)
    if row:
        return str(row["hermes_board_slug"])
    conn = _srv()._workframe_db()
    try:
        ws = conn.execute(
            "SELECT slug, display_name FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        if not ws:
            raise ValueError("workspace_not_found")
        board_slug = re.sub(r"[^a-z0-9-]+", "-", str(ws["slug"] or workspace_id).lower()).strip("-")[:40]
        if not board_slug:
            board_slug = f"ws-{workspace_id[:8].lower()}"
        display_name = str(ws["display_name"] or board_slug)
        now = _srv()._utc_now()
        conn.execute(
            """
            INSERT INTO workspace_kanban_boards (
                id, workspace_id, hermes_board_slug, display_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), workspace_id, board_slug, display_name, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    primary = _srv()._primary_profile()
    if primary:
        code, out = _srv()._gateway_exec(
            primary,
            ["kanban", "boards", "create", board_slug, "--name", display_name],
        )
        if code != 0 and "already exists" not in out.lower():
            pass  # ponytail: board row is source of truth; Hermes may already have the board
    return board_slug


def kanban_proxy_list_tasks(workspace_id: str, user_id: str) -> dict[str, Any]:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not _srv()._user_is_workspace_member(user_id, workspace_id):
        raise PermissionError("forbidden")
    row = _workspace_kanban_board_row(workspace_id)
    board_slug = str(row["hermes_board_slug"]) if row else "default"
    db = _hermes_kanban_db_path(board_slug)
    out: dict[str, Any] = {
        "ok": True,
        "board": board_slug,
        "workspace_id": workspace_id,
        "tasks": [],
        "total": 0,
    }
    conn = _srv()._ro_sqlite_live(db)
    if not conn:
        return out
    try:
        rows = conn.execute(
            """
            SELECT id, title, status, assignee, priority, created_at, completed_at
            FROM tasks
            ORDER BY created_at DESC
            LIMIT 100
            """
        ).fetchall()
        tasks = [
            {
                "id": r["id"],
                "title": r["title"],
                "status": r["status"],
                "assignee": r["assignee"] or "",
                "priority": r["priority"] or 0,
                "created_at": _srv()._iso_from_unix(r["created_at"]),
                "completed_at": _srv()._iso_from_unix(r["completed_at"]) if r["completed_at"] else None,
            }
            for r in rows
        ]
        out["tasks"] = tasks
        out["total"] = len(tasks)
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return out


def kanban_proxy_create_task(workspace_id: str, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not _srv()._user_is_workspace_member(user_id, workspace_id):
        raise PermissionError("forbidden")
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("title_required")
    raw_assignee = str(payload.get("assignee") or payload.get("template_slug") or "").strip()
    assignee_owner = str(payload.get("assignee_user_id") or user_id).strip()
    if _srv()._is_runtime_profile_slug(_srv().safe_profile_slug(raw_assignee)):
        runtime = _srv().safe_profile_slug(raw_assignee)
    elif raw_assignee:
        runtime = _srv().resolve_runtime_assignee(raw_assignee, assignee_owner, workspace_id)
    else:
        raise ValueError("assignee_required")
    ok, reason = validate_kanban_assignee(runtime, user_id, workspace_id)
    if not ok:
        raise PermissionError(str(reason))
    board = ensure_workspace_kanban_board(workspace_id)
    orchestrator = _srv().resolve_runtime_assignee("workframe-agent", user_id, workspace_id)
    args = ["kanban", "--board", board, "create", title, "--assignee", runtime]
    workspace_kind = str(payload.get("workspace_kind") or "scratch").strip()
    if workspace_kind:
        args.extend(["--workspace-kind", workspace_kind])
    body = str(payload.get("body") or "").strip()
    if body:
        args.extend(["--body", body])
    code, out = _srv()._gateway_exec(orchestrator, args)
    if code != 0:
        raise ValueError(f"kanban_create_failed: {out.strip()}")
    owner_id = assignee_owner
    if _srv()._is_runtime_profile_slug(runtime):
        resolved = _srv()._resolve_runtime_owner(runtime)
        if resolved:
            owner_id, workspace_id = resolved[0], resolved[1] or workspace_id
    _srv()._prepare_runtime_profile_credentials(runtime, owner_id, workspace_id)
    return {
        "ok": True,
        "board": board,
        "assignee": runtime,
        "title": title,
        "output": out.strip(),
    }
def _cron_plain_english(schedule: str) -> str:
    s = (schedule or "").strip()
    if not s:
        return "No schedule"
    if s.startswith("every "):
        return s.capitalize()
    parts = s.split()
    if len(parts) == 5:
        minute, hour, dom, month, dow = parts
        if dom == "*" and month == "*" and dow == "*":
            return f"Every day at {hour.zfill(2)}:{minute.zfill(2)} UTC"
        if dom == "*" and month == "*" and dow != "*":
            return f"Cron: {s}"
    return f"Cron: {s}"
def kanban_data() -> dict[str, Any]:
    db = _srv().HERMES_DATA / "kanban.db"
    out: dict[str, Any] = {
        "ok": False,
        "total": 0,
        "tasks": [],
        "stats": {"todo": 0, "scheduled": 0, "ready": 0, "running": 0, "blocked": 0, "done": 0},
    }
    conn = _srv()._ro_sqlite_live(db)
    if not conn:
        return out
    try:
        rows = conn.execute(
            """
            SELECT id, title, status, assignee, priority, created_at, completed_at
            FROM tasks
            ORDER BY created_at DESC
            LIMIT 100
            """
        ).fetchall()
        tasks = [
            {
                "id": r["id"],
                "title": r["title"],
                "status": r["status"],
                "assignee": r["assignee"] or "",
                "priority": r["priority"] or 0,
                "created_at": _srv()._iso_from_unix(r["created_at"]),
                "completed_at": _srv()._iso_from_unix(r["completed_at"]) if r["completed_at"] else None,
            }
            for r in rows
        ]
        out["ok"] = True
        out["tasks"] = tasks
        out["total"] = len(tasks)
        for r in rows:
            st = str(r["status"] or "todo").lower()
            if st in out["stats"]:
                out["stats"][st] += 1
            elif st == "triage":
                out["stats"]["todo"] += 1
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return out


def _hermes_cron_jobs(profile: str) -> list[dict[str, Any]]:
    paths = [
        _srv()._profile_dir(profile) / "cron" / "jobs.json",
        _srv().HERMES_DATA / "cron" / "jobs.json",
    ]
    jobs: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(raw, dict):
            items = raw.get("jobs") or raw.get("items") or []
        elif isinstance(raw, list):
            items = raw
        else:
            items = []
        for job in items:
            if not isinstance(job, dict):
                continue
            schedule = job.get("schedule") or job.get("cron") or job.get("every") or ""
            command = job.get("prompt") or job.get("message") or job.get("name") or ""
            jobs.append(
                {
                    "id": job.get("id") or job.get("name") or "",
                    "name": job.get("name") or job.get("id") or "job",
                    "schedule": schedule,
                    "command": command[:200],
                    "enabled": job.get("enabled", True),
                    "owner": "hermes",
                    "label": "hermes",
                    "category": "hermes",
                    "source": str(path),
                    "description": _cron_plain_english(str(schedule)),
                    "prompt_preview": command[:120],
                }
            )
    return jobs


def _system_cron_jobs() -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    candidates = [
        Path("/etc/crontab"),
        Path("/var/spool/cron/crontabs/root"),
    ]
    cron_d = Path("/etc/cron.d")
    if cron_d.is_dir():
        candidates.extend(sorted(cron_d.glob("*")))
    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 5 if path.name == "crontab" or "crontabs" in str(path) else 6)
            if len(parts) < 6:
                continue
            if path.name == "crontab" or "crontabs" in str(path):
                schedule = " ".join(parts[:5])
                command = parts[5] if len(parts) > 5 else ""
            else:
                schedule = " ".join(parts[:5])
                command = parts[-1]
            jobs.append(
                {
                    "name": command.split()[0] if command else "system",
                    "schedule": schedule,
                    "command": command[:200],
                    "owner": "system",
                    "label": "system",
                    "category": "system",
                    "source": str(path),
                    "description": _cron_plain_english(schedule),
                    "enabled": True,
                }
            )
    return jobs[:50]


def cron_data(profile: str) -> dict[str, Any]:
    hermes = _hermes_cron_jobs(profile)
    system = _system_cron_jobs()
    all_jobs = hermes + system
    return {"jobs": all_jobs, "items": all_jobs, "count": len(all_jobs), "hermes": hermes, "system": system}
