"""Structured audit events for credential broker requests."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.environ.get("WORKFRAME_API_DATA_DIR", "/app/data"))
WORKFRAME_DB = DATA_DIR / "workframe.db"

_SCHEMA_READY: set[str] = set()


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(WORKFRAME_DB), timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema() -> None:
    key = str(WORKFRAME_DB)
    if key in _SCHEMA_READY:
        return
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS broker_audit_events (
                id              TEXT PRIMARY KEY,
                created_at      TEXT NOT NULL,
                broker_kind     TEXT NOT NULL,
                user_id         TEXT DEFAULT '',
                workspace_id    TEXT DEFAULT '',
                profile_slug    TEXT DEFAULT '',
                run_id          TEXT DEFAULT '',
                provider        TEXT NOT NULL,
                upstream_host   TEXT DEFAULT '',
                status          INTEGER NOT NULL,
                deny_reason     TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_broker_audit_created "
            "ON broker_audit_events(created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_broker_audit_provider "
            "ON broker_audit_events(provider, created_at DESC)"
        )
        conn.commit()
    finally:
        conn.close()
    _SCHEMA_READY.add(key)


def record_broker_event(
    *,
    broker_kind: str,
    provider: str,
    upstream_host: str,
    status: int,
    deny_reason: str = "",
    lease: dict[str, Any] | None = None,
) -> None:
    """Persist one broker hop — never raises."""
    try:
        ensure_schema()
        meta = lease or {}
        now = datetime.now(timezone.utc).isoformat()
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO broker_audit_events (
                    id, created_at, broker_kind, user_id, workspace_id,
                    profile_slug, run_id, provider, upstream_host, status, deny_reason
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    str(uuid.uuid4()),
                    now,
                    str(broker_kind or "").strip().lower(),
                    str(meta.get("payer_user_id") or ""),
                    str(meta.get("workspace_id") or ""),
                    str(meta.get("profile_slug") or ""),
                    str(meta.get("run_id") or ""),
                    str(provider or "").strip().lower(),
                    str(upstream_host or "").strip().lower(),
                    int(status),
                    str(deny_reason or "").strip(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def list_broker_events(*, limit: int = 100, provider: str = "") -> list[dict[str, Any]]:
    """Recent broker events for deploy audit / diagnostics."""
    ensure_schema()
    limit = max(1, min(int(limit or 100), 500))
    conn = _connect()
    try:
        if provider:
            rows = conn.execute(
                """
                SELECT created_at, broker_kind, user_id, workspace_id, profile_slug,
                       run_id, provider, upstream_host, status, deny_reason
                FROM broker_audit_events
                WHERE provider = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (str(provider).strip().lower(), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT created_at, broker_kind, user_id, workspace_id, profile_slug,
                       run_id, provider, upstream_host, status, deny_reason
                FROM broker_audit_events
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    import tempfile

    td = tempfile.mkdtemp()
    os.environ["WORKFRAME_API_DATA_DIR"] = td
    globals()["DATA_DIR"] = Path(td)
    globals()["WORKFRAME_DB"] = Path(td) / "workframe.db"
    _SCHEMA_READY.clear()
    record_broker_event(
        broker_kind="llm",
        provider="openrouter",
        upstream_host="openrouter.ai",
        status=401,
        deny_reason="expired",
        lease={
            "payer_user_id": "u1",
            "workspace_id": "ws1",
            "profile_slug": "u-u1-dev",
            "run_id": "run-1",
        },
    )
    events = list_broker_events(limit=5)
    assert len(events) == 1 and events[0]["deny_reason"] == "expired"
    print("broker_audit ok")
