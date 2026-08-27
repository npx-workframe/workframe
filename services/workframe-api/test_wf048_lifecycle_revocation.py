"""WF-048 lifecycle revocation and restore fixtures.

Run: WORKFRAME_API_DATA_DIR=/tmp/wf-048-revoke HERMES_DATA=/tmp/wf-048-revoke-hermes \\
     python services/workframe-api/test_wf048_lifecycle_revocation.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from handler_modules import handler_provider, handler_workspace

DATA_DIR = Path(tempfile.mkdtemp(prefix="wf-048-revoke-"))
HERMES_DIR = Path(tempfile.mkdtemp(prefix="wf-048-revoke-hermes-"))
os.environ["WORKFRAME_API_DATA_DIR"] = str(DATA_DIR)
os.environ["HERMES_DATA"] = str(HERMES_DIR)

import credential_lifecycle
import credential_restore
import credential_revocation
import credential_store
import credential_vault
import provider_bindings
import rooms
import turn_credentials


def _install_server_stub() -> ModuleType:
    db_path = DATA_DIR / "workframe.db"

    def _db_with_rows() -> sqlite3.Connection:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    fake = ModuleType("server")
    fake._workframe_db_path = lambda: db_path  # type: ignore[attr-defined]
    fake._utc_now = lambda: "2026-08-27T00:00:00+00:00"  # type: ignore[attr-defined]
    fake.HERMES_DATA = HERMES_DIR  # type: ignore[attr-defined]
    fake.PROVIDER_CONNECT_CATALOG = (  # type: ignore[attr-defined]
        {
            "id": "openrouter",
            "label": "OpenRouter",
            "category": "llm",
            "connect_mode": "api_key",
            "env_var": "OPENROUTER_API_KEY",
        },
    )
    fake._catalog_provider = lambda provider_id: dict(fake.PROVIDER_CONNECT_CATALOG[0])  # type: ignore[attr-defined]
    fake._user_hermes_dir_slug = lambda user_id: str(user_id).replace("/", "_")  # type: ignore[attr-defined]
    fake._user_hermes_home = lambda user_id: HERMES_DIR / "profiles" / fake._user_hermes_dir_slug(user_id)  # type: ignore[attr-defined]
    fake._user_hermes_auth_path = lambda user_id: fake._user_hermes_home(user_id) / "auth.json"  # type: ignore[attr-defined]
    fake._user_hermes_env_path = lambda user_id: fake._user_hermes_home(user_id) / ".env"  # type: ignore[attr-defined]
    fake._primary_profile = lambda: "primary"  # type: ignore[attr-defined]
    fake._profile_dir = lambda profile: HERMES_DIR / "profiles" / str(profile)  # type: ignore[attr-defined]
    fake._workframe_db = lambda: _db_with_rows()  # type: ignore[attr-defined]
    fake._read_env_map = lambda _path: {}  # type: ignore[attr-defined]
    fake._stack_profile_env = lambda: {}  # type: ignore[attr-defined]
    fake._remove_env_secret = credential_store._remove_env_secret  # type: ignore[attr-defined]
    fake._remove_auth_metadata = lambda *_args, **_kwargs: None  # type: ignore[attr-defined]
    fake._revoke_runtime_llm_leases = lambda **_kwargs: 0  # type: ignore[attr-defined]
    fake.OWNER_ADMIN_ROLES = frozenset({"owner", "admin"})  # type: ignore[attr-defined]
    sys.modules["server"] = fake
    return fake


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT,
            display_name TEXT,
            avatar_url TEXT,
            deleted_at TEXT
        );
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            slug TEXT,
            display_name TEXT,
            owner_id TEXT,
            settings_json TEXT,
            deleted_at TEXT,
            status TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS workspace_memberships (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL,
            invited_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT
        );
        CREATE TABLE IF NOT EXISTS credential_bindings (
            id TEXT PRIMARY KEY,
            workspace_id TEXT,
            user_id TEXT,
            agent_profile_id TEXT,
            provider TEXT NOT NULL,
            credential_type TEXT NOT NULL,
            credential_ref TEXT NOT NULL,
            label TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            expires_at TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT,
            capability_generation INTEGER NOT NULL DEFAULT 1,
            lifecycle_state TEXT NOT NULL DEFAULT 'active',
            lifecycle_updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS credential_lifecycle_operations (
            operation_id TEXT PRIMARY KEY,
            binding_id TEXT NOT NULL,
            operation_type TEXT NOT NULL,
            state TEXT NOT NULL,
            capability_generation INTEGER NOT NULL,
            details_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agent_profiles (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            slug TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            is_native INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'available',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT
        );
        """
    )


def _insert_binding(
    conn: sqlite3.Connection,
    binding_id: str,
    *,
    workspace_id: str | None = None,
    user_id: str | None = None,
    agent_profile_id: str | None = None,
    provider: str = "openrouter",
    generation: int = 1,
) -> None:
    secret = f"sk-{binding_id}"
    credential_vault.store_secret(binding_id, secret, provider=provider, scope="user", user_id=user_id or "")
    now = "2026-08-27T00:00:00+00:00"
    conn.execute(
        """INSERT INTO credential_bindings
           (id, workspace_id, user_id, agent_profile_id, provider, credential_type,
            credential_ref, label, is_active, lifecycle_state, capability_generation,
            created_by, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            binding_id,
            workspace_id,
            user_id,
            agent_profile_id,
            provider,
            "api_key",
            credential_vault.vault_ref(binding_id),
            binding_id,
            1,
            "active",
            generation,
            user_id or "system",
            now,
            now,
        ),
    )
    conn.commit()


def _issue_lease(binding_id: str, *, user_id: str = "user-1", workspace_id: str = "ws-1") -> str:
    return turn_credentials.issue_lease(
        f"run-{binding_id}",
        user_id,
        workspace_id,
        "openrouter",
        f"u-{user_id}-dev",
        binding_id,
    )


def _lease_active(token: str) -> bool:
    reason, _ = turn_credentials.inspect_lease(token)
    return reason is None


def _binding_state(conn: sqlite3.Connection, binding_id: str) -> tuple[int, str, int]:
    row = conn.execute(
        "SELECT capability_generation, lifecycle_state, is_active FROM credential_bindings WHERE id = ?",
        (binding_id,),
    ).fetchone()
    return int(row[0]), str(row[1]), int(row[2])


class _DeleteHandler(handler_workspace.WorkspaceRoutesMixin, handler_provider.ProviderRoutesMixin):
    auth_user = "user-1"

    def __init__(self) -> None:
        self.responses: list[tuple[int, dict]] = []

    def _json(self, status: int, payload: dict) -> None:
        self.responses.append((status, payload))

    def _log_audit(self, *_args, **_kwargs) -> None:
        return None


class Wf048LifecycleRevocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = _install_server_stub()
        credential_vault.DATA_DIR = DATA_DIR
        credential_vault.VAULT_DB = DATA_DIR / "credential_vault.db"
        credential_vault._SCHEMA_READY.clear()
        credential_vault.unseal_for_tests()
        credential_vault.ensure_schema()
        turn_credentials.WORKFRAME_DB = DATA_DIR / "workframe.db"
        turn_credentials._SCHEMA_READY.clear()
        if (DATA_DIR / "workframe.db").exists():
            (DATA_DIR / "workframe.db").unlink()
        if (DATA_DIR / "credential_vault.db").exists():
            (DATA_DIR / "credential_vault.db").unlink()
        credential_vault._SCHEMA_READY.clear()
        credential_vault.unseal_for_tests()
        credential_vault.ensure_schema()
        turn_credentials.ensure_schema()
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        _ensure_schema(conn)
        conn.execute("INSERT INTO users (id, email) VALUES ('user-1', 'u1@example.com'), ('user-2', 'u2@example.com')")
        conn.execute(
            "INSERT INTO workspaces (id, slug, display_name, owner_id, settings_json, status, created_at, updated_at) "
            "VALUES ('ws-1', 'ws-1', 'Workspace', 'user-1', '{\"credential_mode\":\"workspace\"}', 'active', 't', 't')"
        )
        conn.execute(
            """INSERT INTO workspace_memberships
               (id, workspace_id, user_id, role, status, created_at, updated_at)
               VALUES ('m-admin', 'ws-1', 'user-1', 'owner', 'active', 't', 't'),
                      ('m-member', 'ws-1', 'user-2', 'member', 'active', 't', 't')"""
        )
        conn.execute(
            """INSERT INTO agent_profiles
               (id, workspace_id, slug, display_name, is_native, status, created_at, updated_at)
               VALUES ('agent-1', 'ws-1', 'agent-one', 'Agent One', 0, 'available', 't', 't')"""
        )
        conn.commit()
        conn.close()
        self.server._resolve_wid = lambda ref: str(ref)  # type: ignore[attr-defined]
        self.server._workspace_member_role = rooms._workspace_member_role  # type: ignore[attr-defined]
        self.server._install_window_open = lambda: False  # type: ignore[attr-defined]
        self.server._promote_workspace_owner_if_unclaimed = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
        self.server._delete_workspace = rooms._delete_workspace  # type: ignore[attr-defined]
        self.server._delete_agent_profile = rooms._delete_agent_profile  # type: ignore[attr-defined]
        self.server._log_audit = lambda *_args, **_kwargs: None  # type: ignore[attr-defined]
        self.server._parse_workspace_settings = lambda row: json.loads(str(row["settings_json"]))  # type: ignore[attr-defined]
        self.server._parse_messaging_settings_patch = lambda body, settings: settings  # type: ignore[attr-defined]
        self.server._sync_workspace_messaging_gateway = lambda _ws: {"ok": True}  # type: ignore[attr-defined]
        self.server._github_oauth_app_config = lambda _ws="": {}  # type: ignore[attr-defined]
        self.server._github_oauth_configured = lambda _ws="": False  # type: ignore[attr-defined]
        self.server._workspace_messaging_integrations_payload = (  # type: ignore[attr-defined]
            lambda _workspace_id, _settings: {"configured": False, "channels": []}
        )

    def test_member_removal_revokes_workspace_leaves_binding_intact(self) -> None:
        _insert_binding(sqlite3.connect(str(DATA_DIR / "workframe.db")), "bind-member", user_id="user-2")
        token = _issue_lease("bind-member", user_id="user-2")
        self.assertTrue(_lease_active(token))
        result = credential_revocation.revoke_member_workspace_access("user-2", "ws-1")
        self.assertGreaterEqual(result["leases_revoked"], 1)
        self.assertFalse(_lease_active(token))
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        generation, lifecycle_state, is_active = _binding_state(conn, "bind-member")
        conn.close()
        self.assertEqual((generation, lifecycle_state, is_active), (1, "active", 1))
        self.assertEqual(credential_vault.read_secret_result("bind-member").secret, "sk-bind-member")

    def test_role_downgrade_revokes_workspace_leases(self) -> None:
        _insert_binding(sqlite3.connect(str(DATA_DIR / "workframe.db")), "bind-downgrade", user_id="user-1")
        token = _issue_lease("bind-downgrade", user_id="user-1")
        result = credential_revocation.revoke_member_role_downgrade(
            "user-1",
            "ws-1",
            previous_role="owner",
            new_role="member",
        )
        self.assertGreaterEqual(result["leases_revoked"], 1)
        self.assertFalse(_lease_active(token))

    def test_role_lateral_move_keeps_active_lease(self) -> None:
        _insert_binding(sqlite3.connect(str(DATA_DIR / "workframe.db")), "bind-lateral", user_id="user-2")
        token = _issue_lease("bind-lateral", user_id="user-2")
        result = credential_revocation.revoke_member_role_downgrade(
            "user-2",
            "ws-1",
            previous_role="member",
            new_role="guest",
        )
        self.assertEqual(result["leases_revoked"], 0)
        self.assertTrue(_lease_active(token))

    def test_provider_disconnect_revokes_binding_and_leases(self) -> None:
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        _insert_binding(conn, "bind-disconnect", user_id="user-1")
        conn.close()
        token = _issue_lease("bind-disconnect", user_id="user-1")
        result = provider_bindings.disconnect_user_credential("user-1", "bind-disconnect")
        self.assertTrue(result["ok"])
        self.assertFalse(_lease_active(token))
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        generation, lifecycle_state, is_active = _binding_state(conn, "bind-disconnect")
        conn.close()
        self.assertGreaterEqual(generation, 2)
        self.assertEqual(lifecycle_state, "revoked")
        self.assertEqual(is_active, 0)
        self.assertEqual(credential_vault.read_secret_result("bind-disconnect").status, credential_vault.CredentialReadStatus.MISSING)
        auth_path = self.server._user_hermes_auth_path("user-1")
        if auth_path.is_file():
            self.assertNotIn("sk-bind-disconnect", auth_path.read_text(encoding="utf-8"))

    def test_workspace_delete_handler_revokes_bindings_and_leases(self) -> None:
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        _insert_binding(conn, "bind-ws", workspace_id="ws-1")
        conn.close()
        token = _issue_lease("bind-ws", workspace_id="ws-1")
        handler = _DeleteHandler()
        with mock.patch.object(handler_workspace, "_srv", return_value=self.server), mock.patch.object(
            rooms, "_srv", return_value=self.server
        ):
            handler._route_pattern_delete_workspace("/api/workspace/ws-1", {})
        self.assertEqual(handler.responses, [(200, {"ok": True, "workspace_id": "ws-1", "status": "deleted"})])
        self.assertFalse(_lease_active(token))
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        generation, lifecycle_state, is_active = _binding_state(conn, "bind-ws")
        ws_row = conn.execute("SELECT deleted_at, status FROM workspaces WHERE id = 'ws-1'").fetchone()
        conn.close()
        self.assertEqual(lifecycle_state, "revoked")
        self.assertEqual(is_active, 0)
        self.assertGreaterEqual(generation, 2)
        self.assertIsNotNone(ws_row[0])
        self.assertEqual(ws_row[1], "deleted")

    def test_agent_delete_handler_revokes_bindings_and_leases(self) -> None:
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        _insert_binding(conn, "bind-agent", agent_profile_id="agent-1")
        conn.close()
        token = _issue_lease("bind-agent", user_id="user-1")
        handler = _DeleteHandler()
        with mock.patch.object(handler_provider, "_srv", return_value=self.server), mock.patch.object(
            rooms, "_srv", return_value=self.server
        ):
            handler._route_pattern_delete_agent("/api/agents/agent-1", {})
        self.assertEqual(
            handler.responses,
            [(200, {"ok": True, "agent_profile_id": "agent-1", "status": "deleted"})],
        )
        self.assertFalse(_lease_active(token))
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        generation, lifecycle_state, is_active = _binding_state(conn, "bind-agent")
        agent_row = conn.execute(
            "SELECT deleted_at, status FROM agent_profiles WHERE id = 'agent-1'"
        ).fetchone()
        conn.close()
        self.assertEqual(lifecycle_state, "revoked")
        self.assertEqual(is_active, 0)
        self.assertIsNotNone(agent_row[0])
        self.assertEqual(agent_row[1], "deleted")

    def test_payer_mode_change_revokes_workspace_leases(self) -> None:
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        _insert_binding(conn, "bind-payer", workspace_id="ws-1")
        conn.close()
        token = _issue_lease("bind-payer", workspace_id="ws-1")
        result = credential_revocation.revoke_payer_mode_change("ws-1")
        self.assertGreaterEqual(result["leases_revoked"], 1)
        self.assertFalse(_lease_active(token))
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        generation, lifecycle_state, is_active = _binding_state(conn, "bind-payer")
        conn.close()
        self.assertEqual((lifecycle_state, is_active), ("active", 1))

    def test_expiry_revokes_binding_and_leaves_db_recoverable(self) -> None:
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        credential_vault.store_secret("bind-expire", "sk-expire", provider="openrouter")
        conn.execute(
            """INSERT INTO credential_bindings
               (id, workspace_id, user_id, provider, credential_type, credential_ref, label,
                is_active, lifecycle_state, capability_generation, expires_at, created_by, created_at, updated_at)
               VALUES ('bind-expire', NULL, 'user-1', 'openrouter', 'api_key', ?, 'x', 1, 'active', 1,
                       '1970-01-01T00:00:00+00:00', 'user-1', 't', 't')""",
            (credential_vault.vault_ref("bind-expire"),),
        )
        conn.commit()
        conn.close()
        expired = credential_lifecycle.expire_bindings()
        self.assertEqual(expired, 1)
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        generation, lifecycle_state, is_active = _binding_state(conn, "bind-expire")
        conn.close()
        self.assertEqual(lifecycle_state, "revoked")
        self.assertEqual(is_active, 0)
        self.assertEqual(credential_vault.read_secret_result("bind-expire").status, credential_vault.CredentialReadStatus.MISSING)

    def test_restore_full_consistency_ok(self) -> None:
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        _insert_binding(conn, "bind-restore-ok", workspace_id="ws-1", generation=2)
        conn.close()
        result = credential_restore.validate_restore_consistency(
            DATA_DIR / "workframe.db",
            vault_db=DATA_DIR / "credential_vault.db",
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.status, credential_restore.RestoreValidationStatus.OK)

    def test_restore_partial_missing_secret_fails_visibly(self) -> None:
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        _insert_binding(conn, "bind-restore-partial", workspace_id="ws-1")
        conn.close()
        credential_vault.delete_secret("bind-restore-partial")
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        conn.execute("DELETE FROM turn_credential_leases WHERE credential_binding_id = 'bind-restore-partial'")
        conn.commit()
        conn.close()
        result = credential_restore.validate_restore_consistency(
            DATA_DIR / "workframe.db",
            vault_db=DATA_DIR / "credential_vault.db",
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.status, credential_restore.RestoreValidationStatus.MISSING_SECRET)
        self.assertTrue(any("bind-restore-partial" in issue for issue in result.issues))

    def test_restore_generation_mismatch_fails_visibly(self) -> None:
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        _insert_binding(conn, "bind-restore-gen", workspace_id="ws-1", generation=1)
        conn.close()
        _issue_lease("bind-restore-gen", workspace_id="ws-1")
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        conn.execute("UPDATE credential_bindings SET capability_generation = 1 WHERE id = 'bind-restore-gen'")
        conn.execute(
            "UPDATE turn_credential_leases SET capability_generation = 3 WHERE credential_binding_id = 'bind-restore-gen'"
        )
        conn.commit()
        conn.close()
        result = credential_restore.validate_restore_consistency(
            DATA_DIR / "workframe.db",
            vault_db=DATA_DIR / "credential_vault.db",
        )
        self.assertEqual(result.status, credential_restore.RestoreValidationStatus.GENERATION_MISMATCH)
        self.assertTrue(any("bind-restore-gen" in issue for issue in result.issues))

    def test_membership_patch_removal_hook_revokes_leases(self) -> None:
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        conn.row_factory = sqlite3.Row
        _insert_binding(conn, "bind-patch-remove", user_id="user-2")
        conn.close()
        token = _issue_lease("bind-patch-remove", user_id="user-2")
        handler = SimpleNamespace(auth_user="user-1")
        with mock.patch.object(rooms, "_srv", return_value=self.server), mock.patch.object(
            rooms, "_workspace_exists", return_value=True
        ), mock.patch.object(rooms, "_can_manage_workspace_members", return_value=True):
            status, payload = rooms._patch_workspace_members(
                "ws-1",
                {"user_id": "user-2", "status": "removed"},
                handler,
            )
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertFalse(_lease_active(token))

    def test_payer_mode_integration_hook_revokes_leases(self) -> None:
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        _insert_binding(conn, "bind-payer-hook", workspace_id="ws-1")
        conn.close()
        token = _issue_lease("bind-payer-hook", workspace_id="ws-1")
        with mock.patch.object(rooms, "_srv", return_value=self.server), mock.patch.object(
            rooms, "_workspace_exists", return_value=True
        ), mock.patch.object(rooms, "_resolve_workspace_integrations_role", return_value="owner"):
            status, payload = rooms._patch_workspace_integrations(
                "ws-1",
                {"credential_mode": "byok"},
                "user-1",
            )
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertFalse(_lease_active(token))


if __name__ == "__main__":
    unittest.main(verbosity=2)
