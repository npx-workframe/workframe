"""Sprint G–K workframe.db schema migrations (WF-032)."""
from __future__ import annotations

import sqlite3
from collections.abc import Callable

OpenDb = Callable[[], sqlite3.Connection]


def ensure_agent_runs_schema(open_db: OpenDb) -> None:
    """Create or migrate the Workframe agent_runs tracking table."""
    conn = open_db()
    try:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if "agent_runs" not in tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id TEXT PRIMARY KEY,
                    agent_profile_id TEXT NOT NULL,
                    room_id TEXT DEFAULT NULL,
                    triggered_by_user_id TEXT DEFAULT NULL,
                    session_id TEXT DEFAULT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    trigger_source TEXT NOT NULL DEFAULT 'manual',
                    prompt_text TEXT DEFAULT '',
                    result_summary TEXT DEFAULT '',
                    model_provider TEXT DEFAULT '',
                    model_name TEXT DEFAULT '',
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0.0,
                    error_message TEXT DEFAULT '',
                    started_at TEXT NOT NULL,
                    completed_at TEXT DEFAULT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles (id),
                    FOREIGN KEY (room_id) REFERENCES rooms (id),
                    FOREIGN KEY (triggered_by_user_id) REFERENCES users (id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_runs_agent "
                "ON agent_runs(agent_profile_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_runs_room "
                "ON agent_runs(room_id, created_at DESC) WHERE room_id IS NOT NULL"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_runs_session "
                "ON agent_runs(session_id) WHERE session_id IS NOT NULL"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_runs_triggered_by "
                "ON agent_runs(triggered_by_user_id) WHERE triggered_by_user_id IS NOT NULL"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at "
                "ON agent_runs(started_at DESC)"
            )
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations "
                "(version, description, applied_at) VALUES "
                "('4', 'agent_runs tracking table with trigger, prompt, result, and cost fields', datetime('now'))"
            )
            conn.commit()
            return

        cols = {c["name"] for c in conn.execute("PRAGMA table_info(agent_runs)").fetchall()}
        column_specs = {
            "trigger_source": "TEXT NOT NULL DEFAULT 'manual'",
            "prompt_text": "TEXT DEFAULT ''",
            "result_summary": "TEXT DEFAULT ''",
            "model_provider": "TEXT DEFAULT ''",
            "model_name": "TEXT DEFAULT ''",
            "input_tokens": "INTEGER DEFAULT 0",
            "output_tokens": "INTEGER DEFAULT 0",
            "cost_usd": "REAL DEFAULT 0.0",
            "error_message": "TEXT DEFAULT ''",
            "started_at": "TEXT DEFAULT ''",
            "completed_at": "TEXT DEFAULT NULL",
            "created_at": "TEXT DEFAULT ''",
            "updated_at": "TEXT DEFAULT ''",
        }
        for column, spec in column_specs.items():
            if column not in cols:
                conn.execute(f"ALTER TABLE agent_runs ADD COLUMN {column} {spec}")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_agent "
            "ON agent_runs(agent_profile_id, created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_room "
            "ON agent_runs(room_id, created_at DESC) WHERE room_id IS NOT NULL"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_session "
            "ON agent_runs(session_id) WHERE session_id IS NOT NULL"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_triggered_by "
            "ON agent_runs(triggered_by_user_id) WHERE triggered_by_user_id IS NOT NULL"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at "
            "ON agent_runs(started_at DESC)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations "
            "(version, description, applied_at) VALUES "
            "('4', 'agent_runs tracking table with trigger, prompt, result, and cost fields', datetime('now'))"
        )
        conn.commit()
    finally:
        conn.close()


def ensure_invites_schema(open_db: OpenDb) -> None:
    """Create workspace_invites table if not exists."""
    conn = open_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS workspace_invites (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'member',
        token_hash TEXT NOT NULL,
        invited_by_user_id TEXT,
        accepted_by_user_id TEXT,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        accepted_at TEXT,
        deleted_at TEXT
    )""")
    conn.commit()
    conn.close()


def ensure_memory_schema(open_db: OpenDb) -> None:
    """Create memory_items table if not exists."""
    conn = open_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS memory_items (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        agent_profile_id TEXT,
        scope TEXT NOT NULL CHECK(scope IN ('workspace', 'agent_profile', 'room', 'user_agent')),
        room_id TEXT,
        user_id TEXT,
        content TEXT NOT NULL,
        source_message_id TEXT,
        visibility TEXT NOT NULL DEFAULT 'shared' CHECK(visibility IN ('shared', 'private')),
        created_by_user_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT
    )""")
    conn.commit()
    conn.close()


def ensure_policies_schema(open_db: OpenDb) -> None:
    """Create workspace_provider_policies table if not exists."""
    conn = open_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS workspace_provider_policies (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        allow_user_credentials INTEGER NOT NULL DEFAULT 1,
        allow_workspace_fallback INTEGER NOT NULL DEFAULT 1,
        default_model TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(workspace_id, provider)
    )""")
    conn.commit()
    conn.close()


def ensure_user_prefs_schema(open_db: OpenDb) -> None:
    """Add users.current_workspace_id for active workspace selection."""
    conn = open_db()
    try:
        cols = {c[1] for c in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "current_workspace_id" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN current_workspace_id TEXT DEFAULT NULL")
            conn.commit()
        conn.execute(
            """
            UPDATE users
            SET current_workspace_id = (
                SELECT wi.workspace_id
                FROM workspace_invites wi
                WHERE wi.accepted_by_user_id = users.id
                  AND wi.accepted_at IS NOT NULL
                ORDER BY wi.accepted_at DESC
                LIMIT 1
            )
            WHERE COALESCE(current_workspace_id, '') = ''
              AND EXISTS (
                SELECT 1 FROM workspace_invites wi
                WHERE wi.accepted_by_user_id = users.id AND wi.accepted_at IS NOT NULL
              )
            """
        )
        conn.commit()
    finally:
        conn.close()


def ensure_budgets_grants_schema(open_db: OpenDb) -> None:
    """Create budget_policies and credential_grants tables if not exists."""
    conn = open_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS budget_policies (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        subject_type TEXT NOT NULL CHECK(subject_type IN ('workspace', 'user', 'agent_profile')),
        subject_id TEXT,
        provider TEXT,
        daily_limit_cents INTEGER,
        monthly_limit_cents INTEGER,
        allowed_models TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS credential_grants (
        id TEXT PRIMARY KEY,
        credential_binding_id TEXT NOT NULL,
        granted_by_user_id TEXT NOT NULL,
        grantee_type TEXT NOT NULL CHECK(grantee_type IN ('user', 'workspace', 'agent_profile', 'room')),
        grantee_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        max_daily_cents INTEGER,
        max_total_cents INTEGER,
        allowed_models TEXT,
        allowed_agent_profile_ids TEXT,
        allowed_room_ids TEXT,
        expires_at TEXT,
        revoked_at TEXT,
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()
