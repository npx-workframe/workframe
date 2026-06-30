-- =============================================================================
-- Workframe Multi-User Database Schema
-- =============================================================================
-- Target: SQLite (Hermes-native runtime)
-- Purpose: Multi-user project collaboration, workspace management, agent
--          orchestration, room-based chat, credential storage, run tracking,
--          runtime token issuance, and audit logging.
--
-- Design decisions:
--   - SQLite-compatible types (TEXT, INTEGER, REAL, BLOB).
--   - Timestamps stored as TEXT (ISO-8601, UTC) for Hermes alignment.
--   - UUIDs stored as TEXT(36); no auto-increment PKs for portability.
--   - Soft deletes via `deleted_at` (NULL = active, NOT NULL = deleted).
--   - Foreign keys are NOT enforced by SQLite pragma (Hermes convention)
--    but are declared for documentation and future migration.
--   - All tables use `IF NOT EXISTS` for idempotent migration.
-- =============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- =============================================================================
-- 1. users
-- =============================================================================
-- Human operators and service accounts that can access Workframe.
-- Each user has a unique identity and optional platform-specific IDs.

CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,                       -- UUIDv4
    email           TEXT UNIQUE,                            -- nullable for service accounts
    display_name    TEXT NOT NULL DEFAULT '',
    avatar_url      TEXT DEFAULT NULL,
    platform_ids    TEXT DEFAULT '{}',                      -- JSON: {discord: "...", telegram: "..."}
    role            TEXT NOT NULL DEFAULT 'member',         -- owner | admin | member | guest
    status          TEXT NOT NULL DEFAULT 'active',         -- active | suspended | deactivated
    created_at      TEXT NOT NULL,                          -- ISO-8601 UTC
    updated_at      TEXT NOT NULL,                          -- ISO-8601 UTC
    deleted_at      TEXT DEFAULT NULL                       -- soft delete
);

CREATE INDEX IF NOT EXISTS idx_users_email
    ON users (email)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_users_status
    ON users (status)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_users_role
    ON users (role)
    WHERE deleted_at IS NULL;

-- =============================================================================
-- 2. workspaces
-- =============================================================================
-- A workspace = one Workframe project instance. Each project folder pair
-- (Agents/ + /workspace) maps to one workspace row.

CREATE TABLE IF NOT EXISTS workspaces (
    id              TEXT PRIMARY KEY,                       -- UUIDv4
    slug            TEXT UNIQUE NOT NULL,                   -- URL-safe, e.g. "aifred"
    display_name    TEXT NOT NULL DEFAULT '',
    description     TEXT DEFAULT '',
    owner_id        TEXT NOT NULL,                          -- FK → users.id
    runtime_mode    TEXT NOT NULL DEFAULT 'docker',         -- docker | native
    ports           TEXT DEFAULT '{}',                      -- JSON: {gateway, dashboard, api, ui}
    status          TEXT NOT NULL DEFAULT 'active',         -- active | archived | suspended
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    FOREIGN KEY (owner_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS idx_workspaces_slug
    ON workspaces (slug)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_workspaces_owner
    ON workspaces (owner_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_workspaces_status
    ON workspaces (status)
    WHERE deleted_at IS NULL;

-- =============================================================================
-- 3. workspace_memberships
-- =============================================================================
-- Many-to-many join: which users belong to which workspaces, and with what
-- permission level.

CREATE TABLE IF NOT EXISTS workspace_memberships (
    id              TEXT PRIMARY KEY,                       -- UUIDv4
    workspace_id    TEXT NOT NULL,                          -- FK → workspaces.id
    user_id         TEXT NOT NULL,                          -- FK → users.id
    role            TEXT NOT NULL DEFAULT 'member',         -- owner | admin | editor | viewer
    status          TEXT NOT NULL DEFAULT 'active',         -- active | invited | removed
    invited_by      TEXT DEFAULT NULL,                      -- FK → users.id
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces (id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (invited_by) REFERENCES users (id),
    UNIQUE (workspace_id, user_id, deleted_at)              -- one active membership per user/workspace
);

CREATE INDEX IF NOT EXISTS idx_workspace_memberships_workspace
    ON workspace_memberships (workspace_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_workspace_memberships_user
    ON workspace_memberships (user_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_workspace_memberships_role
    ON workspace_memberships (role, workspace_id)
    WHERE deleted_at IS NULL;

-- =============================================================================
-- 4. agent_profiles
-- =============================================================================
-- One row per Hermes profile (agent) registered to a workspace.
-- Maps to `Agents/profiles/{slug}/` directory on disk plus SOUL.md.

CREATE TABLE IF NOT EXISTS agent_profiles (
    id              TEXT PRIMARY KEY,                       -- UUIDv4
    workspace_id    TEXT NOT NULL,                          -- FK → workspaces.id
    slug            TEXT NOT NULL,                          -- Hermes profile slug, e.g. "dev", "workframe-agent"
    display_name    TEXT NOT NULL DEFAULT '',
    tagline         TEXT DEFAULT '',
    role            TEXT DEFAULT '',                         -- human-readable role description
    model_provider  TEXT DEFAULT '',
    model_name      TEXT DEFAULT '',
    is_native       INTEGER NOT NULL DEFAULT 0,             -- 1 = project orchestrator; 0 = specialist
    avatar_url      TEXT DEFAULT NULL,
    status          TEXT NOT NULL DEFAULT 'available',       -- available | busy | paused | retired
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces (id),
    UNIQUE (workspace_id, slug, deleted_at)
);

CREATE INDEX IF NOT EXISTS idx_agent_profiles_workspace
    ON agent_profiles (workspace_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_agent_profiles_slug
    ON agent_profiles (slug)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_agent_profiles_status
    ON agent_profiles (status)
    WHERE deleted_at IS NULL;

-- =============================================================================
-- 5. rooms
-- =============================================================================
-- A room is a chat context: a named conversation space that belongs to a
-- workspace. Rooms may be bound to an agent_profile (lane/channel room) or
-- a freeform multi-agent space. Maps to Discord channels / TG topics.

CREATE TABLE IF NOT EXISTS rooms (
    id              TEXT PRIMARY KEY,                       -- UUIDv4
    workspace_id    TEXT NOT NULL,                          -- FK → workspaces.id
    agent_profile_id TEXT DEFAULT NULL,                     -- FK → agent_profiles.id (NULL = multi-agent room)
    name            TEXT NOT NULL,                          -- display name, e.g. "#dev"
    slug            TEXT NOT NULL,                          -- URL-safe channel slug
    topic           TEXT DEFAULT '',
    room_type       TEXT NOT NULL DEFAULT 'lane',           -- lane | group | direct | channel
    platform_ids    TEXT DEFAULT '{}',                      -- JSON: {discord_channel_id: "...", telegram_topic_id: "..."}
    status          TEXT NOT NULL DEFAULT 'active',         -- active | archived | locked
    created_by      TEXT DEFAULT NULL,                      -- FK → users.id
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces (id),
    FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles (id),
    FOREIGN KEY (created_by) REFERENCES users (id),
    UNIQUE (workspace_id, slug, deleted_at)
);

CREATE INDEX IF NOT EXISTS idx_rooms_workspace
    ON rooms (workspace_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_rooms_agent_profile
    ON rooms (agent_profile_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_rooms_type
    ON rooms (room_type, workspace_id)
    WHERE deleted_at IS NULL;

-- =============================================================================
-- 6. room_memberships
-- =============================================================================
-- Which users (and agent profiles acting as users) are members of a room.

CREATE TABLE IF NOT EXISTS room_memberships (
    id              TEXT PRIMARY KEY,                       -- UUIDv4
    room_id         TEXT NOT NULL,                          -- FK → rooms.id
    user_id         TEXT DEFAULT NULL,                      -- FK → users.id (for human members)
    agent_profile_id TEXT DEFAULT NULL,                     -- FK → agent_profiles.id (for agent members)
    role            TEXT NOT NULL DEFAULT 'participant',    -- owner | moderator | participant
    status          TEXT NOT NULL DEFAULT 'active',         -- active | muted | removed
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
    ON room_memberships (room_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_room_memberships_user
    ON room_memberships (user_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_room_memberships_agent
    ON room_memberships (agent_profile_id)
    WHERE deleted_at IS NULL;

-- =============================================================================
-- 7. messages
-- =============================================================================
-- All chat messages across rooms. Messages come from humans or agent profiles.
-- Supports threading via `parent_message_id`.

CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,                       -- UUIDv4
    room_id         TEXT NOT NULL,                          -- FK → rooms.id
    sender_user_id  TEXT DEFAULT NULL,                      -- FK → users.id
    sender_agent_id TEXT DEFAULT NULL,                      -- FK → agent_profiles.id
    parent_message_id TEXT DEFAULT NULL,                    -- FK → messages.id (thread reply)
    content         TEXT NOT NULL DEFAULT '',
    content_type    TEXT NOT NULL DEFAULT 'text',           -- text | markdown | file | system | tool_result
    metadata        TEXT DEFAULT '{}',                      -- JSON: {attachments, reactions, edits, ...}
    is_edited       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,                      -- soft delete (hide content)
    FOREIGN KEY (room_id) REFERENCES rooms (id),
    FOREIGN KEY (sender_user_id) REFERENCES users (id),
    FOREIGN KEY (sender_agent_id) REFERENCES agent_profiles (id),
    FOREIGN KEY (parent_message_id) REFERENCES messages (id),
    CHECK (
        (sender_user_id IS NOT NULL AND sender_agent_id IS NULL)
        OR (sender_user_id IS NULL AND sender_agent_id IS NOT NULL)
        OR (sender_user_id IS NULL AND sender_agent_id IS NULL)  -- system messages
    )
);

CREATE INDEX IF NOT EXISTS idx_messages_room_created
    ON messages (room_id, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_messages_sender_user
    ON messages (sender_user_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_messages_sender_agent
    ON messages (sender_agent_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_messages_parent
    ON messages (parent_message_id)
    WHERE parent_message_id IS NOT NULL AND deleted_at IS NULL;

-- Full-text search virtual table (content stored, no index bloat on main table)
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5 (
    content,
    content='messages',
    content_rowid='rowid',
    tokenize='unicode61'
);

-- =============================================================================
-- 8. credential_bindings
-- =============================================================================
-- Stores encrypted (or externally-referenced) credentials bound to:
--   - A workspace (global provider key for the project)
--   - A user  (user-specific OAuth / token)
--   - An agent_profile (profile-specific model provider key)
--
-- SECURITY: Secret values MUST be stored via Hermes native auth store (.env,
-- Agents/ auth files), never as plaintext here. This table stores the binding
-- metadata only — i.e., which provider credential exists for which entity.

CREATE TABLE IF NOT EXISTS credential_bindings (
    id              TEXT PRIMARY KEY,                       -- UUIDv4
    workspace_id    TEXT DEFAULT NULL,                      -- FK → workspaces.id
    user_id         TEXT DEFAULT NULL,                      -- FK → users.id
    agent_profile_id TEXT DEFAULT NULL,                     -- FK → agent_profiles.id
    provider        TEXT NOT NULL,                          -- openai | anthropic | openrouter | discord | telegram | ...
    credential_type TEXT NOT NULL DEFAULT 'api_key',        -- api_key | oauth_token | bot_token | certificate
    credential_ref  TEXT NOT NULL,                          -- opaque reference to Hermes auth store entry (NOT the secret)
    label           TEXT DEFAULT '',
    is_active       INTEGER NOT NULL DEFAULT 1,
    expires_at      TEXT DEFAULT NULL,                      -- ISO-8601 UTC, NULL = no expiry
    created_by      TEXT DEFAULT NULL,                      -- FK → users.id
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT DEFAULT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces (id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles (id),
    FOREIGN KEY (created_by) REFERENCES users (id),
    CHECK (
        (workspace_id IS NOT NULL AND user_id IS NULL AND agent_profile_id IS NULL)
        OR (workspace_id IS NULL AND user_id IS NOT NULL AND agent_profile_id IS NULL)
        OR (workspace_id IS NULL AND user_id IS NULL AND agent_profile_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_credential_bindings_workspace
    ON credential_bindings (workspace_id)
    WHERE deleted_at IS NULL AND is_active = 1;

CREATE INDEX IF NOT EXISTS idx_credential_bindings_user
    ON credential_bindings (user_id)
    WHERE deleted_at IS NULL AND is_active = 1;

CREATE INDEX IF NOT EXISTS idx_credential_bindings_agent
    ON credential_bindings (agent_profile_id)
    WHERE deleted_at IS NULL AND is_active = 1;

CREATE INDEX IF NOT EXISTS idx_credential_bindings_provider
    ON credential_bindings (provider)
    WHERE deleted_at IS NULL AND is_active = 1;

-- =============================================================================
-- 9. agent_runs
-- =============================================================================
-- Tracks individual agent execution runs (Hermes sessions / run invocations).
-- Maps to an agent_profile + room + triggering user. Enables cost tracking,
-- duration analysis, and debugging.

CREATE TABLE IF NOT EXISTS agent_runs (
    id              TEXT PRIMARY KEY,                       -- UUIDv4
    agent_profile_id TEXT NOT NULL,                         -- FK → agent_profiles.id
    room_id         TEXT DEFAULT NULL,                      -- FK → rooms.id
    triggered_by_user_id TEXT DEFAULT NULL,                 -- FK → users.id
    session_id      TEXT DEFAULT NULL,                      -- Hermes-native session ID (from state.db)
    status          TEXT NOT NULL DEFAULT 'pending',        -- pending | running | completed | failed | cancelled | timed_out
    trigger_source  TEXT NOT NULL DEFAULT 'manual',         -- manual | cron | webhook | dispatch
    prompt_text     TEXT DEFAULT '',                        -- first user message or trigger text
    result_summary  TEXT DEFAULT '',
    model_provider  TEXT DEFAULT '',
    model_name      TEXT DEFAULT '',
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    cost_usd        REAL DEFAULT 0.0,
    error_message   TEXT DEFAULT '',
    started_at      TEXT NOT NULL,
    completed_at    TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles (id),
    FOREIGN KEY (room_id) REFERENCES rooms (id),
    FOREIGN KEY (triggered_by_user_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_agent
    ON agent_runs (agent_profile_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_runs_room
    ON agent_runs (room_id, created_at DESC)
    WHERE room_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_runs_status
    ON agent_runs (status);

CREATE INDEX IF NOT EXISTS idx_agent_runs_session
    ON agent_runs (session_id)
    WHERE session_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_runs_triggered_by
    ON agent_runs (triggered_by_user_id)
    WHERE triggered_by_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at
    ON agent_runs (started_at DESC);

-- =============================================================================
-- 10. provider_runtime_tokens
-- =============================================================================
-- Short-lived bearer tokens issued by workframe-api for Hermes provider/runtime
-- integrations. The raw token is returned once to the caller and never stored;
-- only a SHA-256 hash is persisted for validation and one-time redemption.

CREATE TABLE IF NOT EXISTS provider_runtime_tokens (
    id              TEXT PRIMARY KEY,                       -- UUIDv4
    run_id          TEXT NOT NULL,                          -- Hermes run/session identifier
    token_hash      TEXT NOT NULL UNIQUE,                   -- SHA-256 hash of raw bearer token
    expires_at      TEXT NOT NULL,                          -- ISO-8601 UTC or epoch seconds
    used_at         TEXT DEFAULT NULL,                      -- ISO-8601 UTC when redeemed
    revoked_at      TEXT DEFAULT NULL,                      -- ISO-8601 UTC when revoked
    created_at      TEXT NOT NULL                           -- ISO-8601 UTC
);

CREATE INDEX IF NOT EXISTS idx_provider_runtime_tokens_run
    ON provider_runtime_tokens (run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_provider_runtime_tokens_expiry
    ON provider_runtime_tokens (expires_at);

-- =============================================================================
-- 11. audit_events
-- =============================================================================
-- Append-only audit log for all security-relevant and operational events
-- across the platform. Read-only for humans; written by workframe-api and agent tools.

CREATE TABLE IF NOT EXISTS audit_events (
    id              TEXT PRIMARY KEY,                       -- UUIDv4
    workspace_id    TEXT DEFAULT NULL,                      -- FK → workspaces.id (nullable for global events)
    user_id         TEXT DEFAULT NULL,                      -- FK → users.id (who triggered it)
    agent_profile_id TEXT DEFAULT NULL,                     -- FK → agent_profiles.id
    room_id         TEXT DEFAULT NULL,                      -- FK → rooms.id
    event_type      TEXT NOT NULL,                          -- see canonical list below
    target_type     TEXT DEFAULT NULL,                      -- table name or resource type
    target_id       TEXT DEFAULT NULL,                      -- PK of the affected row
    summary         TEXT NOT NULL DEFAULT '',               -- human-readable one-liner
    metadata        TEXT DEFAULT '{}',                      -- JSON payload with context
    ip_address      TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces (id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles (id),
    FOREIGN KEY (room_id) REFERENCES rooms (id)
);

-- Canonical event types (enforced at application layer):
--   user.login, user.logout, user.created, user.updated, user.deleted,
--   user.role_changed, user.suspended,
--   workspace.created, workspace.updated, workspace.archived,
--   workspace.member_added, workspace.member_removed, workspace.member_role_changed,
--   agent_profile.created, agent_profile.updated, agent_profile.deleted,
--   agent_profile.started, agent_profile.stopped,
--   room.created, room.archived, room.member_joined, room.member_left,
--   message.sent, message.deleted, message.edited,
--   credential_bound, credential_revoked, credential_expired,
--   agent_run.started, agent_run.completed, agent_run.failed, agent_run.cancelled,
--   config.changed, security.alert, permission.denied

CREATE INDEX IF NOT EXISTS idx_audit_events_workspace
    ON audit_events (workspace_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_events_user
    ON audit_events (user_id, created_at DESC)
    WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_audit_events_type
    ON audit_events (event_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_events_target
    ON audit_events (target_type, target_id)
    WHERE target_type IS NOT NULL AND target_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_audit_events_agent
    ON audit_events (agent_profile_id, created_at DESC)
    WHERE agent_profile_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_audit_events_created
    ON audit_events (created_at DESC);

-- =============================================================================
-- Schema version tracking
-- =============================================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    version         INTEGER PRIMARY KEY,
    applied_at      TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT ''
);

INSERT OR IGNORE INTO schema_migrations (version, applied_at, description)
VALUES (1, datetime('now'), 'Initial schema: users, workspaces, workspace_memberships,
agent_profiles, rooms, room_memberships, messages, credential_bindings, agent_runs, audit_events');

INSERT OR IGNORE INTO schema_migrations (version, applied_at, description)
VALUES (2, datetime('now'), 'Runtime token table: provider_runtime_tokens');
