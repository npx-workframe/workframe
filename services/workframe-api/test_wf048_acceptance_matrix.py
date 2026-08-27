"""WF-048 acceptance matrix — deterministic capability lifecycle fixtures.

Run: WORKFRAME_API_DATA_DIR=/tmp/wf-048 HERMES_DATA=/tmp/wf-048-hermes python services/workframe-api/test_wf048_acceptance_matrix.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

DATA_DIR = Path(tempfile.mkdtemp(prefix="wf-048-matrix-"))
HERMES_DIR = Path(tempfile.mkdtemp(prefix="wf-048-hermes-"))
os.environ["WORKFRAME_API_DATA_DIR"] = str(DATA_DIR)
os.environ["HERMES_DATA"] = str(HERMES_DIR)

import broker_audit
import credential_broker
import credential_lifecycle
import credential_resolve
import credential_store
import credential_vault
import provider_bindings
import turn_credentials


def _install_server_stub() -> ModuleType:
    db_path = DATA_DIR / "workframe.db"
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
        {
            "id": "codex",
            "label": "Codex",
            "category": "llm",
            "connect_mode": "oauth",
            "oauth_provider": "codex",
            "hermes_auth_id": "openai-codex",
        },
        {
            "id": "github",
            "label": "GitHub",
            "category": "integration",
            "connect_mode": "oauth",
            "oauth_provider": "github",
            "env_var": "GITHUB_TOKEN",
        },
    )

    def _catalog_provider(provider_id: str) -> dict | None:
        for spec in fake.PROVIDER_CONNECT_CATALOG:
            if str(spec["id"]) == str(provider_id):
                return dict(spec)
        return None

    fake._catalog_provider = _catalog_provider  # type: ignore[attr-defined]
    fake._user_hermes_dir_slug = lambda user_id: str(user_id).replace("/", "_")  # type: ignore[attr-defined]
    fake._user_hermes_home = lambda user_id: HERMES_DIR / "profiles" / fake._user_hermes_dir_slug(user_id)  # type: ignore[attr-defined]
    fake._user_hermes_auth_path = lambda user_id: fake._user_hermes_home(user_id) / "auth.json"  # type: ignore[attr-defined]
    fake._user_hermes_env_path = lambda user_id: fake._user_hermes_home(user_id) / ".env"  # type: ignore[attr-defined]
    fake._primary_profile = lambda: "primary"  # type: ignore[attr-defined]
    fake._profile_dir = lambda profile: HERMES_DIR / "profiles" / str(profile)  # type: ignore[attr-defined]
    fake._workframe_db = lambda: sqlite3.connect(str(db_path), timeout=5.0)  # type: ignore[attr-defined]
    fake._read_env_map = lambda _path: {}  # type: ignore[attr-defined]
    fake._stack_profile_env = lambda: {}  # type: ignore[attr-defined]
    fake._remove_env_secret = credential_store._remove_env_secret  # type: ignore[attr-defined]
    fake._invalidate_user_llm_picker_cache = lambda _user_id: None  # type: ignore[attr-defined]
    sys.modules["server"] = fake
    return fake


def _ensure_binding_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
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
        """
    )


class Wf048AcceptanceMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = _install_server_stub()
        credential_vault.DATA_DIR = DATA_DIR
        credential_vault.VAULT_DB = DATA_DIR / "credential_vault.db"
        credential_vault._SCHEMA_READY.clear()
        credential_vault.unseal_for_tests()
        credential_vault.ensure_schema()
        turn_credentials.WORKFRAME_DB = DATA_DIR / "workframe.db"
        turn_credentials._SCHEMA_READY.clear()
        turn_credentials.ensure_schema()
        broker_audit.WORKFRAME_DB = DATA_DIR / "workframe.db"
        broker_audit._SCHEMA_READY.clear()
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        _ensure_binding_schema(conn)
        conn.execute("INSERT OR IGNORE INTO users (id, deleted_at) VALUES ('user-1', NULL)")
        conn.commit()
        conn.close()

    def _auth_metadata_text(self, user_id: str) -> str:
        path = self.server._user_hermes_auth_path(user_id)
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def test_user_api_key_store_metadata_only_and_lease_use(self) -> None:
        result = credential_store._store_user_credential(
            "user-1",
            "openrouter",
            "api_key",
            "sk-user-secret",
            "OPENROUTER_API_KEY",
            "User key",
        )
        binding_id = str(result["credential_id"])
        auth_text = self._auth_metadata_text("user-1")
        self.assertIn("vault:", auth_text)
        self.assertNotIn("sk-user-secret", auth_text)
        self.assertEqual(
            credential_vault.read_secret_result(binding_id).secret,
            "sk-user-secret",
        )
        token = turn_credentials.issue_lease(
            "run-user",
            "user-1",
            "ws-1",
            "openrouter",
            "u-user-1-dev",
            binding_id,
        )
        auth = credential_broker.authorize_broker_lease(
            "openrouter",
            {
                "Authorization": f"Bearer {token}",
                "X-Workframe-Profile": "u-user-1-dev",
            },
            resolve_secret=credential_resolve._resolve_secret_for_lease,
        )
        self.assertTrue(auth.ok)
        self.assertEqual(auth.secret, "sk-user-secret")

    def test_workspace_api_key_store_metadata_only(self) -> None:
        (HERMES_DIR / "profiles" / "primary").mkdir(parents=True, exist_ok=True)
        result = credential_store._store_workspace_credential(
            "ws-1",
            "openrouter",
            "api_key",
            "sk-workspace-secret",
            "OPENROUTER_API_KEY",
            "Workspace key",
            "admin-1",
        )
        binding_id = str(result["credential_id"])
        self.assertEqual(
            credential_vault.read_secret_result(binding_id).secret,
            "sk-workspace-secret",
        )
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        row = conn.execute(
            "SELECT lifecycle_state, is_active FROM credential_bindings WHERE id = ?",
            (binding_id,),
        ).fetchone()
        conn.close()
        self.assertEqual(row, ("active", 1))

    def test_oauth_redirect_bundle_stays_in_vault_not_runtime(self) -> None:
        binding_id = "oauth-github-1"
        bundle = json.dumps(
            {
                "kind": "oauth",
                "access_token": "gh-live",
                "refresh_token": "gh-refresh",
                "token_url": "https://github.com/login/oauth/access_token",
                "client_id": "cid",
            },
            sort_keys=True,
        )
        credential_vault.store_secret(binding_id, bundle, provider="github", scope="user", user_id="user-1")
        now = self.server._utc_now()
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        conn.execute(
            """INSERT INTO credential_bindings
               (id, workspace_id, user_id, agent_profile_id, provider, credential_type,
                credential_ref, label, is_active, lifecycle_state, created_by, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                binding_id,
                None,
                "user-1",
                None,
                "github",
                "oauth",
                credential_vault.vault_ref(binding_id),
                "GitHub OAuth",
                1,
                "active",
                "user-1",
                now,
                now,
            ),
        )
        conn.commit()
        conn.close()
        credential_store._upsert_auth_metadata(
            self.server._user_hermes_auth_path("user-1"),
            {
                "provider": "github",
                "credential_type": "oauth",
                "credential_ref": credential_vault.vault_ref(binding_id),
                "env_var": "GITHUB_TOKEN",
                "label": "GitHub OAuth",
                "updated_at": now,
            },
        )
        auth_text = self._auth_metadata_text("user-1")
        self.assertNotIn("gh-live", auth_text)
        self.assertNotIn("gh-refresh", auth_text)
        materialized, status = credential_broker.materialize_provider_secret("github", binding_id, bundle)
        self.assertEqual(status, "ok")
        self.assertEqual(materialized, "gh-live")

    def test_device_oauth_quarantine_scrub_and_broker_unsupported(self) -> None:
        user_home = self.server._user_hermes_home("user-1")
        user_home.mkdir(parents=True, exist_ok=True)
        auth_path = user_home / "auth.json"
        auth_path.write_text(
            json.dumps(
                {
                    "providers": {
                        "openai-codex": {
                            "tokens": {"access_token": "codex-live", "refresh_token": "codex-refresh"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        spec = self.server._catalog_provider("codex")
        result = provider_bindings._oauth_broker_unsupported("user-1", "codex", spec, "sess-1")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "oauth_broker_unsupported")
        scrubbed = json.loads(auth_path.read_text(encoding="utf-8"))
        self.assertFalse(provider_bindings._runtime_auth_contains_raw_authority(scrubbed))

    def test_oauth_refresh_advances_generation_and_revokes_leases(self) -> None:
        binding_id = "oauth-refresh-1"
        bundle = json.dumps(
            {
                "kind": "oauth",
                "access_token": "old",
                "refresh_token": "refresh",
                "expires_at": 1,
                "token_url": "https://example.com/token",
                "client_id": "cid",
            },
            sort_keys=True,
        )
        credential_vault.store_secret(binding_id, bundle, provider="github", scope="user", user_id="user-1")
        now = self.server._utc_now()
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        conn.execute(
            """INSERT INTO credential_bindings
               (id, workspace_id, user_id, agent_profile_id, provider, credential_type,
                credential_ref, label, is_active, lifecycle_state, capability_generation,
                created_by, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                binding_id,
                None,
                "user-1",
                None,
                "github",
                "oauth",
                credential_vault.vault_ref(binding_id),
                "GitHub OAuth",
                1,
                "active",
                1,
                "user-1",
                now,
                now,
            ),
        )
        conn.commit()
        conn.close()
        token = turn_credentials.issue_lease(
            "run-refresh",
            "user-1",
            "ws-1",
            "github",
            "u-user-1-dev",
            binding_id,
        )
        refreshed_bundle = json.dumps(
            {
                "kind": "oauth",
                "access_token": "new-live",
                "refresh_token": "refresh",
                "expires_at": time.time() + 3600,
            },
            sort_keys=True,
        )
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
                {"access_token": "new-live", "expires_in": 3600}
            ).encode()
            materialized, status = credential_broker.materialize_provider_secret(
                "github",
                binding_id,
                bundle,
            )
        self.assertEqual(status, "ok")
        self.assertEqual(materialized, "new-live")
        reason, _ = turn_credentials.inspect_lease(token)
        self.assertIn(reason, {"stale_generation", "revoked"})
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        generation = conn.execute(
            "SELECT capability_generation FROM credential_bindings WHERE id = ?",
            (binding_id,),
        ).fetchone()[0]
        conn.close()
        self.assertGreaterEqual(int(generation), 2)

    def test_interruption_recovery_marks_incomplete_binding_failed(self) -> None:
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        conn.execute(
            """INSERT INTO credential_bindings
               (id, workspace_id, user_id, provider, credential_type, credential_ref,
                label, is_active, lifecycle_state, capability_generation, created_by, created_at, updated_at)
               VALUES ('bind-interrupt', NULL, 'user-1', 'openrouter', 'api_key', 'vault:bind-interrupt',
                       'x', 0, 'staged', 1, 'user-1', 't', 't')"""
        )
        conn.commit()
        conn.close()
        operation_id = credential_lifecycle.begin_operation("bind-interrupt", "create", state="bound")
        pending = credential_lifecycle.recover_pending_operations()
        self.assertTrue(any(item["operation_id"] == operation_id for item in pending))
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        state = conn.execute(
            "SELECT state FROM credential_lifecycle_operations WHERE operation_id = ?",
            (operation_id,),
        ).fetchone()[0]
        binding = conn.execute(
            "SELECT lifecycle_state, is_active FROM credential_bindings WHERE id = 'bind-interrupt'",
        ).fetchone()
        conn.close()
        self.assertEqual(state, "failed")
        self.assertEqual(binding, ("revoked", 0))

    def test_interruption_recovery_completes_published_binding(self) -> None:
        binding_id = "bind-published"
        credential_vault.store_secret(binding_id, "sk-published", provider="openrouter")
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        conn.execute(
            """INSERT INTO credential_bindings
               (id, workspace_id, user_id, provider, credential_type, credential_ref,
                label, is_active, lifecycle_state, capability_generation, created_by, created_at, updated_at)
               VALUES (?, NULL, 'user-1', 'openrouter', 'api_key', ?, 'x', 0, 'published', 1, 'user-1', 't', 't')""",
            (binding_id, credential_vault.vault_ref(binding_id)),
        )
        conn.commit()
        conn.close()
        operation_id = credential_lifecycle.begin_operation(binding_id, "create", state="published")
        credential_lifecycle.recover_pending_operations()
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        state = conn.execute(
            "SELECT state FROM credential_lifecycle_operations WHERE operation_id = ?",
            (operation_id,),
        ).fetchone()[0]
        binding = conn.execute(
            "SELECT lifecycle_state, is_active FROM credential_bindings WHERE id = ?",
            (binding_id,),
        ).fetchone()
        conn.close()
        self.assertEqual(state, "completed")
        self.assertEqual(binding, ("active", 1))

    def test_replacement_revokes_active_lease(self) -> None:
        binding_id = "bind-replace"
        credential_vault.store_secret(binding_id, "sk-old", provider="openrouter")
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        conn.execute(
            """INSERT INTO credential_bindings
               (id, workspace_id, user_id, provider, credential_type, credential_ref,
                label, is_active, lifecycle_state, capability_generation, created_by, created_at, updated_at)
               VALUES (?, NULL, 'user-1', 'openrouter', 'api_key', ?, 'x', 1, 'active', 1, 'user-1', 't', 't')""",
            (binding_id, credential_vault.vault_ref(binding_id)),
        )
        conn.commit()
        conn.close()
        token = turn_credentials.issue_lease(
            "run-replace",
            "user-1",
            "ws-1",
            "openrouter",
            "u-user-1-dev",
            binding_id,
        )
        credential_lifecycle.advance_generation(binding_id, state="rotating")
        reason, _ = turn_credentials.inspect_lease(token)
        self.assertIn(reason, {"stale_generation", "revoked"})

    def test_disconnect_and_expiry_revoke_bindings(self) -> None:
        binding_id = "bind-expire"
        credential_vault.store_secret(binding_id, "sk-expire", provider="openrouter")
        past = "1970-01-01T00:00:00+00:00"
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        conn.execute(
            """INSERT INTO credential_bindings
               (id, workspace_id, user_id, provider, credential_type, credential_ref,
                label, is_active, lifecycle_state, capability_generation, expires_at,
                created_by, created_at, updated_at)
               VALUES (?, NULL, 'user-1', 'openrouter', 'api_key', ?, 'x', 1, 'active', 1, ?, 'user-1', 't', 't')""",
            (binding_id, credential_vault.vault_ref(binding_id), past),
        )
        conn.commit()
        conn.close()
        expired = credential_lifecycle.expire_bindings()
        self.assertEqual(expired, 1)
        self.assertEqual(credential_vault.read_secret_result(binding_id).status, credential_vault.CredentialReadStatus.MISSING)

    def test_vault_failure_states_are_distinct(self) -> None:
        self.assertEqual(
            credential_vault.read_secret_result("missing-binding").status,
            credential_vault.CredentialReadStatus.MISSING,
        )
        credential_vault.unseal_for_tests()
        credential_vault.store_secret("sealed-binding", "sk-sealed", provider="openrouter")
        with mock.patch("vault_kek.kek_in_memory", return_value=False), mock.patch(
            "credential_vault.vault_status",
            return_value={"passphrase_enabled": True, "sealed": True, "initialized": True},
        ):
            self.assertEqual(
                credential_vault.read_secret_result("sealed-binding").status,
                credential_vault.CredentialReadStatus.SEALED,
            )
        credential_vault.unseal_for_tests()
        credential_vault.store_secret("corrupt-binding", "sk-corrupt", provider="openrouter")
        conn = sqlite3.connect(str(credential_vault.VAULT_DB))
        conn.execute(
            "UPDATE credential_secrets SET encrypted_secret = ? WHERE binding_id = ?",
            (json.dumps({"v": 2, "broken": True}), "corrupt-binding"),
        )
        conn.commit()
        conn.close()
        self.assertEqual(
            credential_vault.read_secret_result("corrupt-binding").status,
            credential_vault.CredentialReadStatus.CORRUPT,
        )

    def test_malformed_auth_metadata_fails_closed_without_erase(self) -> None:
        path = Path(tempfile.mkdtemp(prefix="wf-048-auth-")) / "auth.json"
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            credential_store._upsert_auth_metadata(
                path,
                {"credential_ref": "vault:test", "provider": "openrouter", "credential_type": "api_key"},
            )
        self.assertEqual(path.read_text(encoding="utf-8"), "{broken")

    def test_boot_migration_scrubs_legacy_runtime_oauth(self) -> None:
        profiles = HERMES_DIR / "profiles"
        user_dir = profiles / "user-1"
        user_dir.mkdir(parents=True, exist_ok=True)
        auth_path = user_dir / "auth.json"
        auth_path.write_text(
            json.dumps(
                {
                    "providers": {
                        "openai-codex": {
                            "tokens": {"access_token": "legacy-live", "refresh_token": "legacy-refresh"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        result = provider_bindings.migrate_legacy_runtime_oauth_authority(HERMES_DIR)
        self.assertGreaterEqual(result["scrubbed"], 1)
        scrubbed = json.loads(auth_path.read_text(encoding="utf-8"))
        self.assertFalse(provider_bindings._runtime_auth_contains_raw_authority(scrubbed))

    def test_raw_authority_scan_never_returns_secret_values(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="wf-048-scan-"))
        profile = root / "profiles" / "u-user-1-dev"
        profile.mkdir(parents=True)
        (profile / "auth.json").write_text(
            json.dumps({"providers": {"github": {"access_token": "scan-secret"}}}),
            encoding="utf-8",
        )
        findings = provider_bindings._scan_runtime_auth_files(root / "profiles")
        self.assertEqual({item["kind"] for item in findings}, {"raw_authority"})
        self.assertNotIn("scan-secret", repr(findings))

    def test_broker_returns_typed_failure_for_sealed_vault(self) -> None:
        binding_id = "bind-sealed-broker"
        credential_vault.unseal_for_tests()
        credential_vault.store_secret(binding_id, "sk-sealed-broker", provider="openrouter")
        now = self.server._utc_now()
        conn = sqlite3.connect(str(DATA_DIR / "workframe.db"))
        conn.execute(
            """INSERT INTO credential_bindings
               (id, workspace_id, user_id, provider, credential_type, credential_ref,
                label, is_active, lifecycle_state, capability_generation, created_by, created_at, updated_at)
               VALUES (?, NULL, 'user-1', 'openrouter', 'api_key', ?, 'x', 1, 'active', 1, 'user-1', ?, ?)""",
            (binding_id, credential_vault.vault_ref(binding_id), now, now),
        )
        conn.commit()
        conn.close()
        token = turn_credentials.issue_lease(
            "run-sealed",
            "user-1",
            "ws-1",
            "openrouter",
            "u-user-1-dev",
            binding_id,
        )
        credential_vault.seal_vault()
        with mock.patch(
            "credential_vault.read_secret_result",
            return_value=credential_vault.CredentialReadResult(
                credential_vault.CredentialReadStatus.SEALED
            ),
        ):
            auth = credential_broker.authorize_broker_lease(
                "openrouter",
                {
                    "Authorization": f"Bearer {token}",
                    "X-Workframe-Profile": "u-user-1-dev",
                },
                resolve_secret=credential_resolve._resolve_secret_for_lease,
            )
        self.assertFalse(auth.ok)
        self.assertEqual(auth.credential_status, "sealed")
        credential_vault.unseal_for_tests()

    def test_security_docs_exclude_host_compromise_claim(self) -> None:
        security_doc = Path(__file__).resolve().parents[2] / "docs" / "public" / "security.md"
        text = security_doc.read_text(encoding="utf-8").lower()
        self.assertIn("host", text)
        self.assertIn("memory", text)
        self.assertIn("non-retrieval", text)
        self.assertTrue(
            "not a host-compromise guarantee" in text
            or ("outside" in text and "host" in text)
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
