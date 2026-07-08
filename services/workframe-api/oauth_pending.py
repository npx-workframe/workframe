"""WF-032 extract: OAuth PKCE pending state (short-lived callback handshake)."""

from __future__ import annotations

import base64
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

import db_schema


def _srv():
    import server as srv

    return srv


def ensure_schema() -> None:
    db_schema.ensure_oauth_pending_migrations(_srv()._workframe_db)


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return verifier, challenge


def store_pending(
    state: str,
    user_id: str,
    provider: str,
    code_verifier: str,
    workspace_id: str = "",
) -> None:
    ensure_schema()
    now = _srv()._utc_now()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    conn = _srv()._workframe_db()
    try:
        conn.execute(
            """
            INSERT INTO oauth_pending_states (state, user_id, provider, code_verifier, workspace_id, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(state) DO UPDATE SET
                user_id = excluded.user_id,
                provider = excluded.provider,
                code_verifier = excluded.code_verifier,
                workspace_id = excluded.workspace_id,
                expires_at = excluded.expires_at,
                created_at = excluded.created_at
            """,
            (state, user_id, provider, code_verifier, workspace_id or None, expires, now),
        )
        conn.commit()
    finally:
        conn.close()


def take_pending(state: str) -> dict[str, Any] | None:
    ensure_schema()
    conn = _srv()._workframe_db()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM oauth_pending_states WHERE state = ?",
            (str(state or "").strip(),),
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM oauth_pending_states WHERE state = ?", (row["state"],))
        conn.commit()
        expires_at = str(row["expires_at"] or "")
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at.replace("Z", "+00:00")) < datetime.now(timezone.utc):
                    return None
            except ValueError:
                pass
        return dict(row)
    finally:
        conn.close()
