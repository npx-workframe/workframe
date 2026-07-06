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

WORKFRAME_DB_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    email           TEXT UNIQUE,
    display_name    TEXT NOT NULL DEFAULT '',
    avatar_url      TEXT DEFAULT NULL,
    platform_ids    TEXT DEFAULT '{}',
    role            TEXT NOT NULL DEFAULT 'member',
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS workspaces (
    id              TEXT PRIMARY KEY,
    slug            TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL DEFAULT '',
    description     TEXT DEFAULT '',
    owner_id        TEXT NOT NULL,
    runtime_mode    TEXT NOT NULL DEFAULT 'docker',
    ports           TEXT DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS workspace_memberships (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'member',
    status          TEXT NOT NULL DEFAULT 'active',
    invited_by      TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS credential_bindings (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT DEFAULT NULL,
    user_id         TEXT DEFAULT NULL,
    agent_profile_id TEXT DEFAULT NULL,
    provider        TEXT NOT NULL,
    credential_type TEXT NOT NULL DEFAULT 'api_key',
    credential_ref  TEXT NOT NULL,
    label           TEXT DEFAULT '',
    is_active       INTEGER NOT NULL DEFAULT 1,
    expires_at      TEXT DEFAULT NULL,
    created_by      TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    CHECK (
        (workspace_id IS NOT NULL AND user_id IS NULL AND agent_profile_id IS NULL)
        OR (workspace_id IS NULL AND user_id IS NOT NULL AND agent_profile_id IS NULL)
        OR (workspace_id IS NULL AND user_id IS NULL AND agent_profile_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_credential_bindings_workspace_active
    ON credential_bindings(workspace_id, provider, is_active, deleted_at);

CREATE INDEX IF NOT EXISTS idx_credential_bindings_user_active
    ON credential_bindings(user_id, provider, is_active, deleted_at);

CREATE INDEX IF NOT EXISTS idx_credential_bindings_agent_active
    ON credential_bindings(agent_profile_id, provider, is_active, deleted_at);

CREATE TABLE IF NOT EXISTS audit_events (
    id              TEXT PRIMARY KEY,
    user_id         TEXT DEFAULT NULL,
    event_type      TEXT NOT NULL,
    target_type     TEXT DEFAULT NULL,
    target_id       TEXT DEFAULT NULL,
    summary         TEXT DEFAULT '',
    metadata        TEXT DEFAULT '{}',
    ip_address      TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version         TEXT PRIMARY KEY,
    description     TEXT DEFAULT '',
    applied_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_profiles (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    slug            TEXT NOT NULL,
    display_name    TEXT NOT NULL DEFAULT '',
    tagline         TEXT DEFAULT '',
    role            TEXT DEFAULT '',
    model_provider  TEXT DEFAULT '',
    model_name      TEXT DEFAULT '',
    is_native       INTEGER NOT NULL DEFAULT 0,
    avatar_url      TEXT DEFAULT NULL,
    status          TEXT NOT NULL DEFAULT 'available',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces (id),
    UNIQUE (workspace_id, slug, deleted_at)
);

CREATE INDEX IF NOT EXISTS idx_agent_profiles_workspace
    ON agent_profiles(workspace_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_agent_profiles_slug
    ON agent_profiles(slug)
    WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS rooms (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    agent_profile_id TEXT DEFAULT NULL,
    name            TEXT NOT NULL,
    slug            TEXT NOT NULL,
    topic           TEXT DEFAULT '',
    room_type       TEXT NOT NULL DEFAULT 'lane',
    platform_ids    TEXT DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'active',
    created_by      TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces (id),
    FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles (id),
    FOREIGN KEY (created_by) REFERENCES users (id),
    UNIQUE (workspace_id, slug, deleted_at)
);

CREATE INDEX IF NOT EXISTS idx_rooms_workspace
    ON rooms(workspace_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_rooms_agent_profile
    ON rooms(agent_profile_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_rooms_type
    ON rooms(room_type, workspace_id)
    WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS room_memberships (
    id              TEXT PRIMARY KEY,
    room_id         TEXT NOT NULL,
    user_id         TEXT DEFAULT NULL,
    agent_profile_id TEXT DEFAULT NULL,
    role            TEXT NOT NULL DEFAULT 'participant',
    status          TEXT NOT NULL DEFAULT 'active',
    joined_at       TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    FOREIGN KEY (room_id) REFERENCES rooms (id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles (id),
    CHECK (
        (user_id IS NOT NULL AND agent_profile_id IS NULL)
        OR (user_id IS NULL AND agent_profile_id IS NOT NULL)
    ),
    UNIQUE (room_id, user_id, agent_profile_id, deleted_at)
);

CREATE INDEX IF NOT EXISTS idx_room_memberships_room
    ON room_memberships(room_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_room_memberships_user
    ON room_memberships(user_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_room_memberships_agent
    ON room_memberships(agent_profile_id)
    WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    room_id         TEXT NOT NULL,
    sender_user_id  TEXT DEFAULT NULL,
    sender_agent_id TEXT DEFAULT NULL,
    parent_message_id TEXT DEFAULT NULL,
    content         TEXT NOT NULL DEFAULT '',
    content_type    TEXT NOT NULL DEFAULT 'text',
    metadata        TEXT DEFAULT '{}',
    is_edited       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    FOREIGN KEY (room_id) REFERENCES rooms (id),
    FOREIGN KEY (sender_user_id) REFERENCES users (id),
    FOREIGN KEY (sender_agent_id) REFERENCES agent_profiles (id),
    FOREIGN KEY (parent_message_id) REFERENCES messages (id),
    CHECK (
        (sender_user_id IS NOT NULL AND sender_agent_id IS NULL)
        OR (sender_user_id IS NULL AND sender_agent_id IS NOT NULL)
        OR (sender_user_id IS NULL AND sender_agent_id IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_messages_room_created
    ON messages(room_id, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_memberships_workspace_user_active
    ON workspace_memberships(workspace_id, user_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_workspace_memberships_user_active
    ON workspace_memberships(user_id, deleted_at, status);

CREATE INDEX IF NOT EXISTS idx_workspace_memberships_workspace_active
    ON workspace_memberships(workspace_id, deleted_at, status);

CREATE INDEX IF NOT EXISTS idx_workspace_memberships_workspace_role
    ON workspace_memberships(workspace_id, role)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_workspaces_active
    ON workspaces(deleted_at, status);

INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
VALUES ('1', 'workframe-api runtime schema for /api/me', datetime('now'));
INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
VALUES ('2', 'runtime schema with credential_bindings for credential resolution', datetime('now'));
INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
VALUES ('3', 'runtime schema with agent_profiles, rooms, room_memberships, and messages', datetime('now'));
INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
VALUES ('4', 'agent_runs tracking table with trigger, prompt, result, and cost fields', datetime('now'));

CREATE TABLE IF NOT EXISTS room_sessions (
    id              TEXT PRIMARY KEY,
    room_id         TEXT NOT NULL,
    agent_profile_id TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    gateway_session_id TEXT NOT NULL,
    title           TEXT DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'active',
    forked_from     TEXT DEFAULT NULL,
    created_by      TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    FOREIGN KEY (room_id) REFERENCES rooms (id),
    FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles (id)
);

CREATE INDEX IF NOT EXISTS idx_room_sessions_room
    ON room_sessions(room_id, agent_profile_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_room_sessions_status
    ON room_sessions(room_id, status)
    WHERE deleted_at IS NULL;

INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
VALUES ('5', 'room_sessions table for forkable Hermes sessions per room+agent', datetime('now'));
"""


def _srv():
    import server as srv
    return srv


def _migrate_v6_space_rooms(conn: sqlite3.Connection) -> None:
    applied = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version = '6' LIMIT 1",
    ).fetchone()
    if applied:
        return
    now = str(int(time.time()))
    conn.execute(
        """
        UPDATE rooms
        SET agent_profile_id = NULL, updated_at = ?
        WHERE deleted_at IS NULL
          AND room_type IN ('channel', 'group')
          AND agent_profile_id IS NOT NULL
        """,
        (now,),
    )
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('6', 'channel/group rooms are spaces not agent lanes', datetime('now'))
        """,
    )
def _migrate_v7_space_agent_members(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = '7' LIMIT 1").fetchone():
        return
    rooms = conn.execute(
        """
        SELECT id, workspace_id FROM rooms
        WHERE deleted_at IS NULL AND room_type IN ('channel', 'group')
        """,
    ).fetchall()
    for room in rooms:
        agents = conn.execute(
            """
            SELECT id FROM agent_profiles
            WHERE workspace_id = ? AND deleted_at IS NULL
            """,
            (str(room["workspace_id"]),),
        ).fetchall()
        for agent in agents:
            _srv()._ensure_agent_in_space_room(conn, str(room["id"]), str(agent["id"]))
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('7', 'workspace agents joined to space rooms as members', datetime('now'))
        """,
    )
def _migrate_v13_workspace_members_in_spaces(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = '13' LIMIT 1").fetchone():
        return
    rooms = conn.execute(
        """
        SELECT id, workspace_id FROM rooms
        WHERE deleted_at IS NULL AND room_type IN ('channel', 'group')
        """,
    ).fetchall()
    for room in rooms:
        _srv()._add_workspace_members_to_space_room(conn, str(room["workspace_id"]), str(room["id"]))
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('13', 'workspace members joined to all space rooms', datetime('now'))
        """,
    )
def _migrate_v8_room_avatars(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = '8' LIMIT 1").fetchone():
        return
    cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(rooms)")}
    if "avatar_url" not in cols:
        conn.execute("ALTER TABLE rooms ADD COLUMN avatar_url TEXT DEFAULT NULL")
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('8', 'room avatar_url for space settings', datetime('now'))
        """,
    )
def _migrate_v9_workspace_avatars(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = '9' LIMIT 1").fetchone():
        return
    cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(workspaces)")}
    if "avatar_url" not in cols:
        conn.execute("ALTER TABLE workspaces ADD COLUMN avatar_url TEXT DEFAULT NULL")
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('9', 'workspace avatar_url for workframe settings', datetime('now'))
        """,
    )
def _migrate_v11_delegation_kanban_boards(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = '11' LIMIT 1").fetchone():
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_delegation_grants (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            grantor_user_id TEXT NOT NULL,
            grantee_user_id TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'agents:delegate',
            expires_at TEXT DEFAULT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT DEFAULT NULL,
            FOREIGN KEY (workspace_id) REFERENCES workspaces (id)
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_delegation_grants_active
            ON agent_delegation_grants(workspace_id, grantor_user_id, grantee_user_id, scope)
            WHERE deleted_at IS NULL
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_kanban_boards (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            hermes_board_slug TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT DEFAULT NULL,
            FOREIGN KEY (workspace_id) REFERENCES workspaces (id)
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_kanban_board_active
            ON workspace_kanban_boards(workspace_id)
            WHERE deleted_at IS NULL
        """
    )
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('11', 'agent_delegation_grants and workspace_kanban_boards', datetime('now'))
        """
    )
def _migrate_v12_adopt_install_keys_to_owners(conn: sqlite3.Connection) -> None:
    """Hermes install keys on the primary profile become the workspace owner's personal keys."""
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = '12' LIMIT 1").fetchone():
        return
    primary = _srv()._install_profile_slug()
    adopted = False
    if primary:
        stack_env = _srv()._read_env_map(_srv()._profile_dir(primary) / ".env")
        owner_ids = _srv()._install_key_owner_user_ids(conn)
        for owner_id in owner_ids:
            for spec in _srv().PROVIDER_CONNECT_CATALOG:
                if str(spec.get("category") or "") != "llm":
                    continue
                env_var = str(spec.get("env_var") or "").strip()
                secret = str(stack_env.get(env_var) or "").strip()
                if not env_var or not secret:
                    continue
                if _srv()._adopt_install_llm_key_for_user(
                    conn,
                    owner_id,
                    str(spec["id"]),
                    env_var,
                    secret,
                ):
                    adopted = True
        # ponytail: never strip install-profile .env — install keys stay on workframe-agent;
        # user keys live only in profiles/{user-uuid}/. Never copy from local host Hermes.
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('12', 'adopt primary-profile LLM install keys as owner personal keys', datetime('now'))
        """
    )
def _migrate_v10_workspace_settings_oauth(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = '10' LIMIT 1").fetchone():
        return
    cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(workspaces)")}
    if "settings_json" not in cols:
        conn.execute("ALTER TABLE workspaces ADD COLUMN settings_json TEXT NOT NULL DEFAULT '{}'")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS oauth_pending_states (
            state TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            code_verifier TEXT NOT NULL,
            workspace_id TEXT DEFAULT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES ('10', 'workspace settings_json and oauth_pending_states for user GitHub OAuth', datetime('now'))
        """,
    )



def ensure_workframe_db_schema(open_db: OpenDb) -> None:
    conn = open_db()
    try:
        conn.executescript(WORKFRAME_DB_SCHEMA)
        _migrate_v6_space_rooms(conn)
        _migrate_v7_space_agent_members(conn)
        _migrate_v8_room_avatars(conn)
        _migrate_v9_workspace_avatars(conn)
        _migrate_v10_workspace_settings_oauth(conn)
        _migrate_v11_delegation_kanban_boards(conn)
        _migrate_v12_adopt_install_keys_to_owners(conn)
        _migrate_v13_workspace_members_in_spaces(conn)
        conn.commit()
    finally:
        conn.close()


def ensure_oauth_pending_migrations(open_db: OpenDb) -> None:
    conn = open_db()
    try:
        _migrate_v10_workspace_settings_oauth(conn)
        _migrate_v11_delegation_kanban_boards(conn)
        _migrate_v12_adopt_install_keys_to_owners(conn)
        _migrate_v13_workspace_members_in_spaces(conn)
        conn.commit()
    finally:
        conn.close()
