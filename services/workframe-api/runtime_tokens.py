"""WF-032 extract: provider runtime tokens (opaque per-run bearer tokens)."""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Any

DEFAULT_TTL = int(os.environ.get("WORKFRAME_RUNTIME_TOKEN_TTL", "3600"))


def _srv():
    import server as srv

    return srv


def ensure_schema() -> None:
    """Create provider_runtime_tokens table and indexes if needed."""
    conn = _srv()._workframe_db()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS provider_runtime_tokens (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        used_at TEXT,
        revoked_at TEXT,
        created_at TEXT NOT NULL
    )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_provider_runtime_tokens_run "
        "ON provider_runtime_tokens(run_id, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_provider_runtime_tokens_expiry "
        "ON provider_runtime_tokens(expires_at)"
    )
    conn.commit()
    conn.close()


def hash_token(token: str) -> str:
    """Hash a bearer runtime token before storing it."""
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def token_expired(expires_at: str) -> bool:
    """Return True when an expires_at value is expired or invalid."""
    value = str(expires_at or "").strip()
    if not value:
        return True
    if value.isdigit():
        return int(value) < int(time.time())
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) < datetime.now(timezone.utc)
    except ValueError:
        return True


def create_token(run_id: str, ttl_seconds: int = DEFAULT_TTL) -> str:
    """Create a short-lived runtime token for an agent run. Returns the token."""
    run = str(run_id or "").strip()
    if not run:
        raise ValueError("run_id required")
    ttl = int(ttl_seconds or DEFAULT_TTL)
    if ttl <= 0:
        raise ValueError("ttl_seconds must be positive")

    ensure_schema()
    token = secrets.token_hex(32)
    now = _srv()._utc_now()
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat()
    conn = _srv()._workframe_db()
    conn.execute(
        "INSERT INTO provider_runtime_tokens "
        "(id, run_id, token_hash, expires_at, created_at) VALUES (?,?,?,?,?)",
        (secrets.token_hex(16), run, hash_token(token), expires_at, now),
    )
    conn.commit()
    conn.close()
    return token


def validate_token(token: str) -> dict[str, Any] | None:
    """Validate a runtime token once. Returns {"run_id": str} or None."""
    raw = str(token or "").strip()
    if not raw:
        return None

    ensure_schema()
    conn = _srv()._workframe_db()
    conn.row_factory = sqlite3.Row
    token_hash = hash_token(raw)
    row = conn.execute(
        "SELECT id, run_id, expires_at, revoked_at, used_at "
        "FROM provider_runtime_tokens WHERE token_hash = ?",
        (token_hash,),
    ).fetchone()
    if not row:
        conn.close()
        return None

    now = _srv()._utc_now()
    if row["revoked_at"] or row["used_at"] or token_expired(row["expires_at"]):
        conn.close()
        return None

    cursor = conn.execute(
        "UPDATE provider_runtime_tokens "
        "SET used_at = ? "
        "WHERE id = ? AND revoked_at IS NULL AND used_at IS NULL AND expires_at > ?",
        (now, row["id"], now),
    )
    if cursor.rowcount != 1:
        conn.close()
        return None
    conn.commit()
    run_id = row["run_id"]
    conn.close()
    return {"run_id": run_id}
