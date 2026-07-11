"""Install wizard resume + admin verify persistence self-check."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import install_api  # noqa: E402
import stack_config  # noqa: E402

td = Path(tempfile.mkdtemp())
stack_config.DATA_DIR = td
stack_config.CONFIG_PATH = td / "stack_config.json"
db_path = str(td / "workframe.db")

assert install_api.resolve_install_wizard_step(db_path) == "intro"

# Registered admin + stale saved smtp must not skip deployment.
import sqlite3

conn = sqlite3.connect(db_path)
conn.executescript(
    """
    CREATE TABLE workspaces (
        id TEXT PRIMARY KEY, slug TEXT, display_name TEXT, owner_id TEXT,
        settings_json TEXT, deleted_at INTEGER, status TEXT, created_at TEXT, updated_at TEXT
    );
    """
)
conn.execute(
    "INSERT INTO workspaces (id, slug, display_name, owner_id, settings_json, deleted_at, status, created_at, updated_at) "
    "VALUES ('ws1', 'default', 'Workframe', 'u1', '{}', NULL, 'active', '1', '1')",
)
conn.commit()
conn.close()

stack_config.patch_stack_config(
    {"smtp": {"admin_email": "owner@example.com"}, "wizard_step": "smtp"},
)
assert install_api.install_owner_claimed(db_path)
assert install_api.resolve_install_wizard_step(db_path) == "welcome"

# SMTP saved + tested
stack_config.patch_stack_config(
    {
        "deployment_mode": "public_multi_user",
        "app_base_url": "https://dev.example.com",
        "smtp": {
            "host": "smtp.example.com",
            "port": 587,
            "user": "relay@example.com",
            "password": "secret",
            "from": "noreply@example.com",
        },
    }
)
stack_config.mark_smtp_tested()
stack_config.patch_stack_config({"smtp": {"admin_email": "owner@example.com"}})

assert stack_config.smtp_setup_complete()
assert not stack_config.install_admin_verified()
assert install_api.resolve_install_wizard_step(db_path) == "admin_auth"

# Registered owner before verify still resumes at OTP (register ≠ verify).
assert install_api.install_owner_claimed(db_path)
assert install_api.resolve_install_wizard_step(db_path) == "admin_auth"

stack_config.mark_install_admin_verified("owner@example.com")
assert stack_config.install_admin_verified()
raw = stack_config.read_stack_raw()
assert raw["smtp"]["admin_email"] == "owner@example.com"
assert raw.get("wizard_step") == "workframe"

payload = stack_config.public_stack_payload()
assert payload["smtp"]["admin_email"] == "owner@example.com"
assert payload["smtp"]["admin_verified"] is True

wizard = install_api.install_wizard_public_payload(db_path)
assert wizard["admin_verified"] is True
assert wizard["owner_claimed"] is True
assert wizard["resume_step"] == "workframe"

allowed, _ = install_api.install_auth_email_allowed("owner@example.com")
assert allowed
denied, deny = install_api.install_auth_email_allowed("other@example.com")
assert not denied and deny.get("error") == "install_admin_email_required"

# Workspace progress → billing
conn = sqlite3.connect(db_path)
settings = {"admin_onboarding_done": True}
conn.execute(
    "UPDATE workspaces SET settings_json = ? WHERE id = 'ws1'",
    (json.dumps(settings),),
)
conn.commit()
conn.close()

assert install_api.resolve_install_wizard_step(db_path) == "billing"

print("test_install_wizard_resume: ok")
