"""Durable credential-binding lifecycle and generation helpers (WF-048)."""

from __future__ import annotations

import sqlite3
from typing import Any

import turn_credentials


def _srv():
    import server as srv

    return srv


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

