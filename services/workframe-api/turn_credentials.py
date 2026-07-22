"""Per-run credential leases — opaque tokens for Hermes; real secrets stay in API vault."""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import credential_vault

DATA_DIR = Path(os.environ.get("WORKFRAME_API_DATA_DIR", "/app/data"))
WORKFRAME_DB = DATA_DIR / "workframe.db"
LEASE_PREFIX = "wf_rt_"
DEFAULT_TTL = int(os.environ.get("WORKFRAME_TURN_LEASE_TTL", "900"))
# LLM authorization belongs to a user-specific runtime profile, not to an
# individual chat turn.  Keep that opaque broker credential long-lived and
# explicitly revocable; rotating it on every message forces Hermes to restart
# its gateway and can drop the in-flight response.
RUNTIME_TTL = int(os.environ.get("WORKFRAME_RUNTIME_LEASE_TTL", "2592000"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(WORKFRAME_DB), timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


# ponytail: schema DDL ran on every validate_lease/issue — ~38ms/call on bind-mounted
# sqlite. Guard by DB path so it runs once per process (tests reassign WORKFRAME_DB → re-run).
_SCHEMA_READY: set[str] = set()


def ensure_schema() -> None:
    credential_vault.ensure_schema()
    key = str(WORKFRAME_DB)
    if key in _SCHEMA_READY:
        return
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS turn_credential_leases (
                run_id TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL UNIQUE,
                payer_user_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                credential_binding_id TEXT DEFAULT NULL,
                profile_slug TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT DEFAULT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_turn_leases_token "
            "ON turn_credential_leases(token_hash)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_turn_leases_expiry "
            "ON turn_credential_leases(expires_at)"
        )
        conn.commit()
    finally:
        conn.close()
    _SCHEMA_READY.add(key)


def _hash_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _expired(expires_at: str) -> bool:
    value = str(expires_at or "").strip()
    if not value:
        return True
    if value.isdigit():
        return int(value) < int(time.time())
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) < datetime.now(timezone.utc)
    except ValueError:
        return True


def issue_lease(
    run_id: str,
    payer_user_id: str,
    workspace_id: str,
    provider: str,
    profile_slug: str,
    credential_binding_id: str | None,
    *,
    ttl_seconds: int = DEFAULT_TTL,
) -> str:
    """Create lease; return full token value for profile env (wf_rt_…)."""
    run_id = str(run_id or "").strip()
    payer_user_id = str(payer_user_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    provider = str(provider or "openrouter").strip().lower()
    profile_slug = str(profile_slug or "").strip()
    if not run_id or not payer_user_id or not profile_slug:
        raise ValueError("run_id, payer_user_id, and profile_slug required")
    ttl = int(ttl_seconds or DEFAULT_TTL)
    if ttl <= 0:
        raise ValueError("ttl_seconds must be positive")

    ensure_schema()
    raw = secrets.token_hex(32)
    token = f"{LEASE_PREFIX}{raw}"
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(seconds=ttl)).isoformat()
    created_at = now.isoformat()
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO turn_credential_leases (
                run_id, token_hash, payer_user_id, workspace_id, provider,
                credential_binding_id, profile_slug, expires_at, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(run_id) DO UPDATE SET
                token_hash = excluded.token_hash,
                payer_user_id = excluded.payer_user_id,
                workspace_id = excluded.workspace_id,
                provider = excluded.provider,
                credential_binding_id = excluded.credential_binding_id,
                profile_slug = excluded.profile_slug,
                expires_at = excluded.expires_at,
                revoked_at = NULL,
                created_at = excluded.created_at
            """,
            (
                run_id,
                _hash_token(token),
                payer_user_id,
                workspace_id,
                provider,
                str(credential_binding_id or "") or None,
                profile_slug,
                expires_at,
                created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return token


def parse_lease_token(value: str) -> str:
    raw = str(value or "").strip()
    if raw.startswith(LEASE_PREFIX):
        return raw
    if raw and not raw.startswith(LEASE_PREFIX):
        return f"{LEASE_PREFIX}{raw}"
    return ""


def _lease_row_to_meta(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "run_id": str(row["run_id"]),
        "payer_user_id": str(row["payer_user_id"]),
        "workspace_id": str(row["workspace_id"]),
        "provider": str(row["provider"]),
        "credential_binding_id": str(row["credential_binding_id"] or ""),
        "profile_slug": str(row["profile_slug"]),
    }


def inspect_lease(token: str) -> tuple[str | None, dict[str, Any] | None]:
    """Return (deny_reason, lease_meta). deny_reason is None when the lease is active."""
    token = parse_lease_token(token)
    if not token:
        return "missing_token", None
    ensure_schema()
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT run_id, payer_user_id, workspace_id, provider,
                   credential_binding_id, profile_slug, expires_at, revoked_at
            FROM turn_credential_leases
            WHERE token_hash = ?
            """,
            (_hash_token(token),),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return "not_found", None
    meta = _lease_row_to_meta(row)
    if row["revoked_at"]:
        return "revoked", meta
    if _expired(str(row["expires_at"] or "")):
        return "expired", meta
    return None, meta


def validate_lease(token: str) -> dict[str, Any] | None:
    """Return lease metadata if token is active (not revoked/expired)."""
    deny_reason, lease = inspect_lease(token)
    return lease if deny_reason is None else None


def revoke_lease(run_id: str) -> None:
    run_id = str(run_id or "").strip()
    if not run_id:
        return
    ensure_schema()
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        conn.execute(
            "UPDATE turn_credential_leases SET revoked_at = ? WHERE run_id = ? AND revoked_at IS NULL",
            (now, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def revoke_matching_leases(
    *,
    payer_user_id: str = "",
    workspace_id: str = "",
    provider: str = "",
    credential_binding_id: str = "",
) -> int:
    """Revoke active broker credentials after an ownership/binding change."""
    clauses = ["revoked_at IS NULL"]
    params: list[str] = []
    for column, value in (
        ("payer_user_id", payer_user_id),
        ("workspace_id", workspace_id),
        ("provider", str(provider or "").strip().lower()),
        ("credential_binding_id", credential_binding_id),
    ):
        normalized = str(value or "").strip()
        if normalized:
            clauses.append(f"{column} = ?")
            params.append(normalized)
    if len(clauses) == 1:
        return 0
    ensure_schema()
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        cur = conn.execute(
            f"UPDATE turn_credential_leases SET revoked_at = ? WHERE {' AND '.join(clauses)}",
            (now, *params),
        )
        conn.commit()
        return int(cur.rowcount or 0)
    finally:
        conn.close()


def resolve_lease_secret(lease: dict[str, Any], resolve_secret_fn) -> tuple[str, str]:
    """resolve_secret_fn(user_id, workspace_id, provider, binding_id) -> (env_var, secret)."""
    binding_id = str(lease.get("credential_binding_id") or "").strip()
    provider = str(lease.get("provider") or "openrouter")
    payer = str(lease.get("payer_user_id") or "")
    workspace = str(lease.get("workspace_id") or "")
    return resolve_secret_fn(payer, workspace, provider, binding_id)


if __name__ == "__main__":
    ensure_schema()
    rid = "run-selfcheck"
    tok = issue_lease(rid, "user-a", "ws-1", "openrouter", "u-user-a-architect", "bind-1")
    assert tok.startswith(LEASE_PREFIX)
    meta = validate_lease(tok)
    assert meta and meta["run_id"] == rid
    revoke_lease(rid)
    assert validate_lease(tok) is None
    print("turn_credentials ok")
