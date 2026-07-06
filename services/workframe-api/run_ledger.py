"""Workframe-owned run ledger — runs, run_events, run_line_items (WF-NS-P2, WF-016)."""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from domain.entities import (
    ActorType,
    FundingSource,
    Run,
    RunEvent,
    RunStatus,
    RunSurface,
)
from run_authority import RunAuthorityDecision

DATA_DIR = Path(os.environ.get("WORKFRAME_API_DATA_DIR", "/app/data"))
WORKFRAME_DB = DATA_DIR / "workframe.db"

_SCHEMA_READY: set[str] = set()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(WORKFRAME_DB), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_ts() -> str:
    return str(int(time.time()))


def ensure_schema() -> None:
    key = str(WORKFRAME_DB)
    if key in _SCHEMA_READY:
        return
    conn = _connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                description TEXT,
                applied_at TEXT
            );

            CREATE TABLE IF NOT EXISTS runs (
                run_id              TEXT PRIMARY KEY,
                workspace_id        TEXT NOT NULL,
                surface             TEXT NOT NULL,
                actor_type          TEXT NOT NULL,
                actor_id            TEXT NOT NULL,
                triggering_user_id  TEXT NOT NULL,
                agent_id            TEXT NOT NULL DEFAULT '',
                runtime_binding_id  TEXT NOT NULL DEFAULT '',
                status              TEXT NOT NULL,
                payer_user_id       TEXT NOT NULL,
                funding_source      TEXT NOT NULL,
                room_id             TEXT DEFAULT NULL,
                card_id             TEXT DEFAULT NULL,
                engine              TEXT NOT NULL DEFAULT 'hermes',
                runtime             TEXT NOT NULL DEFAULT 'hermes_managed',
                risk_tier           TEXT NOT NULL DEFAULT 'low',
                budget_usd          REAL DEFAULT NULL,
                deny_reason         TEXT DEFAULT NULL,
                profile_slug        TEXT DEFAULT NULL,
                provider            TEXT DEFAULT NULL,
                credential_ref_id   TEXT DEFAULT NULL,
                credential_scope    TEXT DEFAULT NULL,
                session_id          TEXT DEFAULT NULL,
                created_at          TEXT NOT NULL,
                started_at          TEXT DEFAULT NULL,
                ended_at            TEXT DEFAULT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_runs_workspace
                ON runs(workspace_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_runs_room
                ON runs(room_id, created_at DESC)
                WHERE room_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_runs_status
                ON runs(status, created_at DESC);

            CREATE TABLE IF NOT EXISTS run_events (
                event_id        TEXT PRIMARY KEY,
                run_id          TEXT NOT NULL,
                event_type      TEXT NOT NULL,
                payload_json    TEXT NOT NULL DEFAULT '{}',
                room_id         TEXT DEFAULT NULL,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs (run_id)
            );

            CREATE INDEX IF NOT EXISTS idx_run_events_run
                ON run_events(run_id, created_at ASC);
            CREATE INDEX IF NOT EXISTS idx_run_events_room
                ON run_events(room_id, created_at DESC)
                WHERE room_id IS NOT NULL;

            CREATE TABLE IF NOT EXISTS run_line_items (
                line_item_id    TEXT PRIMARY KEY,
                run_id          TEXT NOT NULL,
                kind            TEXT NOT NULL,
                provider        TEXT DEFAULT NULL,
                payer_user_id   TEXT NOT NULL,
                funding_source  TEXT NOT NULL,
                amount_usd      REAL DEFAULT NULL,
                units           REAL DEFAULT NULL,
                unit_label      TEXT DEFAULT NULL,
                model           TEXT DEFAULT NULL,
                receipt_json    TEXT NOT NULL DEFAULT '{}',
                created_at      TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs (run_id)
            );

            CREATE INDEX IF NOT EXISTS idx_run_line_items_run
                ON run_line_items(run_id, created_at ASC);

            INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
            VALUES ('14', 'runs, run_events, run_line_items ledger tables', datetime('now'));
            """
        )
        conn.commit()
    finally:
        conn.close()
    _SCHEMA_READY.add(key)


def _row_to_run(row: sqlite3.Row) -> Run:
    return Run(
        run_id=str(row["run_id"]),
        workspace_id=str(row["workspace_id"]),
        surface=RunSurface(str(row["surface"])),
        actor_type=ActorType(str(row["actor_type"])),
        actor_id=str(row["actor_id"]),
        triggering_user_id=str(row["triggering_user_id"]),
        agent_id=str(row["agent_id"] or ""),
        runtime_binding_id=str(row["runtime_binding_id"] or ""),
        status=RunStatus(str(row["status"])),
        payer_user_id=str(row["payer_user_id"]),
        funding_source=FundingSource(str(row["funding_source"])),
        room_id=str(row["room_id"]) if row["room_id"] else None,
        card_id=str(row["card_id"]) if row["card_id"] else None,
        engine=str(row["engine"] or "hermes"),
        runtime=str(row["runtime"] or "hermes_managed"),
        risk_tier=str(row["risk_tier"] or "low"),  # type: ignore[arg-type]
        budget_usd=row["budget_usd"],
        deny_reason=str(row["deny_reason"]) if row["deny_reason"] else None,
        created_at=None,
        started_at=None,
        ended_at=None,
    )


def insert_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    workspace_id: str,
    surface: RunSurface,
    actor_type: ActorType,
    actor_id: str,
    triggering_user_id: str,
    agent_id: str,
    runtime_binding_id: str,
    status: RunStatus,
    payer_user_id: str,
    funding_source: FundingSource,
    room_id: str | None = None,
    profile_slug: str | None = None,
    provider: str | None = None,
    deny_reason: str | None = None,
    credential_ref_id: str | None = None,
    credential_scope: str | None = None,
    session_id: str | None = None,
) -> None:
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO runs (
            run_id, workspace_id, surface, actor_type, actor_id, triggering_user_id,
            agent_id, runtime_binding_id, status, payer_user_id, funding_source,
            room_id, profile_slug, provider, deny_reason, credential_ref_id,
            credential_scope, session_id, created_at, started_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            workspace_id,
            surface.value,
            actor_type.value,
            actor_id,
            triggering_user_id,
            agent_id,
            runtime_binding_id,
            status.value,
            payer_user_id,
            funding_source.value,
            room_id,
            profile_slug,
            provider,
            deny_reason,
            credential_ref_id,
            credential_scope,
            session_id,
            now,
            now if status in (RunStatus.RUNNING, RunStatus.AUTHORIZED) else None,
        ),
    )


def insert_run_event(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    event_type: str,
    payload: Mapping[str, Any] | None = None,
    room_id: str | None = None,
    event_id: str | None = None,
) -> RunEvent:
    eid = str(event_id or uuid.uuid4())
    conn.execute(
        """
        INSERT INTO run_events (event_id, run_id, event_type, payload_json, room_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (eid, run_id, event_type, json.dumps(dict(payload or {})), room_id, _utc_now()),
    )
    return RunEvent(event_id=eid, run_id=run_id, event_type=event_type, payload=dict(payload or {}))


def update_run_status(
    conn: sqlite3.Connection,
    run_id: str,
    status: RunStatus,
    *,
    deny_reason: str | None = None,
) -> None:
    ended = status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.DENIED)
    conn.execute(
        """
        UPDATE runs
        SET status = ?, deny_reason = COALESCE(?, deny_reason), ended_at = ?
        WHERE run_id = ?
        """,
        (status.value, deny_reason, _utc_now() if ended else None, run_id),
    )


def insert_line_item(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    kind: str,
    payer_user_id: str,
    funding_source: FundingSource,
    provider: str | None = None,
    amount_usd: float | None = None,
    units: float | None = None,
    unit_label: str | None = None,
    model: str | None = None,
    receipt: Mapping[str, Any] | None = None,
    line_item_id: str | None = None,
) -> str:
    lid = str(line_item_id or uuid.uuid4())
    conn.execute(
        """
        INSERT INTO run_line_items (
            line_item_id, run_id, kind, provider, payer_user_id, funding_source,
            amount_usd, units, unit_label, model, receipt_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lid,
            run_id,
            kind,
            provider,
            payer_user_id,
            funding_source.value,
            amount_usd,
            units,
            unit_label,
            model,
            json.dumps(dict(receipt or {})),
            _utc_now(),
        ),
    )
    return lid


def record_authority_decision(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    request_surface: RunSurface,
    actor_type: ActorType,
    actor_id: str,
    triggering_user_id: str,
    workspace_id: str,
    agent_id: str,
    runtime_binding_id: str,
    profile_slug: str,
    provider: str,
    room_id: str | None,
    session_id: str | None,
    decision: RunAuthorityDecision,
) -> None:
    status = RunStatus.AUTHORIZED if decision.allowed else RunStatus.DENIED
    if decision.allowed:
        status = RunStatus.RUNNING
    insert_run(
        conn,
        run_id=run_id,
        workspace_id=workspace_id,
        surface=request_surface,
        actor_type=actor_type,
        actor_id=actor_id,
        triggering_user_id=triggering_user_id,
        agent_id=agent_id,
        runtime_binding_id=runtime_binding_id,
        status=status,
        payer_user_id=decision.payer_user_id or triggering_user_id,
        funding_source=decision.funding_source,
        room_id=room_id,
        profile_slug=profile_slug,
        provider=provider,
        deny_reason=decision.deny_reason,
        credential_ref_id=decision.credential_ref_id,
        credential_scope=decision.credential_scope,
        session_id=session_id,
    )
    event_type = "run.authorized" if decision.allowed else "run.denied"
    insert_run_event(
        conn,
        run_id=run_id,
        event_type=event_type,
        payload={
            "payer_user_id": decision.payer_user_id,
            "funding_source": decision.funding_source.value,
            "deny_reason": decision.deny_reason,
            "profile_slug": profile_slug,
            "provider": provider,
        },
        room_id=room_id,
    )


def complete_run(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    model: str = "",
    provider: str = "",
    funding_source: FundingSource,
    payer_user_id: str,
    receipt: Mapping[str, Any] | None = None,
) -> None:
    update_run_status(conn, run_id, RunStatus.COMPLETED)
    insert_run_event(conn, run_id=run_id, event_type="run.completed", payload=dict(receipt or {}))
    insert_line_item(
        conn,
        run_id=run_id,
        kind="llm_turn",
        payer_user_id=payer_user_id,
        funding_source=funding_source,
        provider=provider or None,
        model=model or None,
        unit_label="turn",
        units=1.0,
        receipt={
            "run_id": run_id,
            "model": model,
            "provider": provider,
            "payer_user_id": payer_user_id,
            "funding_source": funding_source.value,
            **dict(receipt or {}),
        },
    )


def fail_run(conn: sqlite3.Connection, run_id: str, *, reason: str = "") -> None:
    update_run_status(conn, run_id, RunStatus.FAILED, deny_reason=reason or None)
    insert_run_event(conn, run_id=run_id, event_type="run.failed", payload={"reason": reason})


def list_run_events_for_room(room_id: str, *, limit: int = 40) -> list[dict[str, Any]]:
    room_id = str(room_id or "").strip()
    if not room_id:
        return []
    ensure_schema()
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT e.event_id, e.run_id, e.event_type, e.payload_json, e.created_at,
                   r.profile_slug, r.payer_user_id, r.funding_source, r.status AS run_status
            FROM run_events e
            JOIN runs r ON r.run_id = e.run_id
            WHERE COALESCE(e.room_id, r.room_id) = ?
            ORDER BY e.created_at DESC
            LIMIT ?
            """,
            (room_id, max(1, limit)),
        ).fetchall()
    finally:
        conn.close()
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(str(row["payload_json"] or "{}"))
        except json.JSONDecodeError:
            payload = {}
        out.append(
            {
                "id": f"run_event:{row['event_id']}",
                "kind": "run_event",
                "event_type": str(row["event_type"]),
                "run_id": str(row["run_id"]),
                "run_status": str(row["run_status"]),
                "profile": str(row["profile_slug"] or ""),
                "payer_user_id": str(row["payer_user_id"] or ""),
                "funding_source": str(row["funding_source"] or ""),
                "task_description": _event_description(str(row["event_type"]), payload),
                "status": str(row["run_status"]),
                "created_at": str(row["created_at"]),
                "source": "run_ledger",
                "payload": payload,
            }
        )
    return out


def _event_description(event_type: str, payload: Mapping[str, Any]) -> str:
    if event_type == "run.authorized":
        fs = str(payload.get("funding_source") or "")
        return f"Run authorized ({fs})" if fs else "Run authorized"
    if event_type == "run.denied":
        return f"Run denied: {payload.get('deny_reason') or 'policy'}"
    if event_type == "run.completed":
        return "Chat turn completed"
    if event_type == "run.failed":
        return f"Run failed: {payload.get('reason') or 'error'}"
    return event_type


def get_run(conn: sqlite3.Connection, run_id: str) -> Run | None:
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if not row:
        return None
    return _row_to_run(row)
