"""Durable credential-binding lifecycle and generation helpers (WF-048)."""

from __future__ import annotations

import sqlite3
import json
import uuid
from typing import Any

import turn_credentials


def _srv():
    import server as srv

    return srv


def begin_operation(binding_id: str, operation_type: str, *, state: str = "staged", generation: int | None = None, details: dict[str, Any] | None = None) -> str:
    """Persist an idempotent lifecycle marker before filesystem/provider side effects."""
    binding_id = str(binding_id or "").strip()
    if not binding_id:
        raise ValueError("binding_id required")
    conn = sqlite3.connect(str(_srv()._workframe_db_path()), timeout=5.0)
    try:
        row = conn.execute("SELECT capability_generation FROM credential_bindings WHERE id = ?", (binding_id,)).fetchone()
        if not row:
            raise ValueError("credential_binding_not_found")
        current_generation = max(1, int(row[0] or 1))
        operation_id = str(uuid.uuid4())
        now = _srv()._utc_now()
        conn.execute(
            """INSERT INTO credential_lifecycle_operations
               (operation_id, binding_id, operation_type, state, capability_generation, details_json, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (operation_id, binding_id, str(operation_type or "update"), str(state or "staged"),
             max(1, int(generation or current_generation)), json.dumps(details or {}, sort_keys=True), now, now),
        )
        conn.commit()
        return operation_id
    finally:
        conn.close()


def transition_operation(operation_id: str, state: str, *, details: dict[str, Any] | None = None) -> None:
    operation_id = str(operation_id or "").strip()
    if not operation_id:
        return
    conn = sqlite3.connect(str(_srv()._workframe_db_path()), timeout=5.0)
    try:
        now = _srv()._utc_now()
        if details is None:
            conn.execute("UPDATE credential_lifecycle_operations SET state = ?, updated_at = ? WHERE operation_id = ?", (str(state), now, operation_id))
        else:
            conn.execute("UPDATE credential_lifecycle_operations SET state = ?, details_json = ?, updated_at = ? WHERE operation_id = ?", (str(state), json.dumps(details, sort_keys=True), now, operation_id))
        conn.commit()
    finally:
        conn.close()


def recover_pending_operations() -> list[dict[str, Any]]:
    """Mark abandoned pre-publication operations failed; callers may retry by operation type."""
    conn = sqlite3.connect(str(_srv()._workframe_db_path()), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT operation_id, binding_id, operation_type, state, capability_generation FROM credential_lifecycle_operations WHERE state IN ('staged','bound','published','rotating')"
        ).fetchall()
        now = _srv()._utc_now()
        for row in rows:
            conn.execute("UPDATE credential_lifecycle_operations SET state = 'failed', details_json = ?, updated_at = ? WHERE operation_id = ?", (json.dumps({"reason": "recovery_required"}), now, row["operation_id"]))
        conn.commit()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def binding_state(binding_id: str) -> tuple[int, str] | None:
    binding_id = str(binding_id or "").strip()
    if not binding_id:
        return None
    conn = sqlite3.connect(str(_srv()._workframe_db_path()), timeout=5.0)
    try:
        row = conn.execute(
            "SELECT capability_generation, lifecycle_state FROM credential_bindings WHERE id = ?",
            (binding_id,),
        ).fetchone()
        if not row:
            return None
        return max(1, int(row[0] or 1)), str(row[1] or "active")
    finally:
        conn.close()


def advance_generation(binding_id: str, *, state: str = "rotating") -> int:
    """Advance before publishing replacement material and revoke prior leases."""
    binding_id = str(binding_id or "").strip()
    if not binding_id:
        raise ValueError("binding_id required")
    now = _srv()._utc_now()
    conn = sqlite3.connect(str(_srv()._workframe_db_path()), timeout=5.0)
    try:
        row = conn.execute(
            "SELECT capability_generation FROM credential_bindings WHERE id = ?",
            (binding_id,),
        ).fetchone()
        if not row:
            raise ValueError("credential_binding_not_found")
        generation = max(1, int(row[0] or 1)) + 1
        conn.execute(
            """UPDATE credential_bindings
               SET capability_generation = ?, lifecycle_state = ?, lifecycle_updated_at = ?, updated_at = ?
               WHERE id = ?""",
            (generation, str(state or "rotating"), now, now, binding_id),
        )
        conn.commit()
    finally:
        conn.close()
    turn_credentials.revoke_matching_leases(credential_binding_id=binding_id)
    return generation


def mark_active(binding_id: str) -> None:
    binding_id = str(binding_id or "").strip()
    if not binding_id:
        return
    conn = sqlite3.connect(str(_srv()._workframe_db_path()), timeout=5.0)
    try:
        conn.execute(
            "UPDATE credential_bindings SET lifecycle_state = 'active', lifecycle_updated_at = ?, updated_at = ? WHERE id = ?",
            (_srv()._utc_now(), _srv()._utc_now(), binding_id),
        )
        conn.commit()
    finally:
        conn.close()

