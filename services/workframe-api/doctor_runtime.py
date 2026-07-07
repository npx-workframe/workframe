"""WF-032 extract: doctor audit/repair for agent DM runtime profiles."""

from __future__ import annotations

import sqlite3
from typing import Any


def _srv():
    import server as srv

    return srv


def iter_agent_dm_runtime_slots(conn: sqlite3.Connection) -> list[dict[str, str]]:
    """All (workspace, agent, user) slots that need a u-* runtime for agent DM bind."""
    rows = conn.execute(
        """
        SELECT r.workspace_id, r.agent_profile_id, rm.user_id
        FROM rooms r
        JOIN room_memberships rm ON rm.room_id = r.id AND rm.deleted_at IS NULL
        WHERE r.deleted_at IS NULL
          AND r.room_type = 'direct'
          AND r.agent_profile_id IS NOT NULL
          AND TRIM(r.agent_profile_id) != ''
        """,
    ).fetchall()
    seen: set[tuple[str, str, str]] = set()
    slots: list[dict[str, str]] = []
    for row in rows:
        workspace_id = str(row["workspace_id"] or "").strip()
        agent_ref = str(row["agent_profile_id"] or "").strip()
        user_id = str(row["user_id"] or "").strip()
        if not workspace_id or not agent_ref or not user_id:
            continue
        key = (workspace_id, agent_ref, user_id)
        if key in seen:
            continue
        seen.add(key)
        agent_row = _srv()._lookup_agent_profile(conn, workspace_id, agent_ref)
        if not agent_row:
            continue
        template = str(agent_row["slug"] or "").strip()
        if not template:
            continue
        runtime = _srv()._runtime_profile_slug(user_id, template)
        slots.append({
            "workspace_id": workspace_id,
            "agent_profile_id": str(agent_row["id"]),
            "user_id": user_id,
            "template": template,
            "runtime": runtime,
            "on_disk": _srv()._runtime_profile_on_disk(runtime),
        })
    return slots


def doctor_audit_agent_dm_runtimes() -> dict[str, Any]:
    """Report missing u-* runtimes for agent DM rooms — no mutations."""
    conn = _srv()._workframe_db()
    try:
        slots = iter_agent_dm_runtime_slots(conn)
    finally:
        conn.close()
    missing = [s for s in slots if not s["on_disk"]]
    return {
        "ok": True,
        "total": len(slots),
        "present": len(slots) - len(missing),
        "missing": missing,
    }


def doctor_repair_agent_dm_runtimes(*, repair: bool = True) -> dict[str, Any]:
    """Explicit repair — provision missing u-* runtimes for agent DM rooms."""
    conn = _srv()._workframe_db()
    try:
        slots = iter_agent_dm_runtime_slots(conn)
    finally:
        conn.close()
    missing = [s for s in slots if not s["on_disk"]]
    if not repair:
        return doctor_audit_agent_dm_runtimes()
    repaired: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    for slot in missing:
        runtime = slot["runtime"]
        try:
            _srv().ensure_runtime_profile(
                runtime,
                slot["template"],
                slot["user_id"],
                slot["workspace_id"],
            )
            if _srv()._runtime_profile_on_disk(runtime):
                repaired.append(slot)
            else:
                failed.append({**slot, "error": "runtime_still_missing"})
        except Exception as exc:  # noqa: BLE001
            failed.append({**slot, "error": str(exc)})
    still_missing = [s for s in missing if not _srv()._runtime_profile_on_disk(s["runtime"])]
    return {
        "ok": not failed and not still_missing,
        "total": len(slots),
        "missing_before": len(missing),
        "repaired": repaired,
        "failed": failed,
        "still_missing": still_missing,
    }
