"""ponytail: install window must ignore compose SMTP env (clean install, not migration).

Run: python services/workframe-api/test_stack_config_install_smtp.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stack_config  # noqa: E402

td = Path(tempfile.mkdtemp())
stack_config.DATA_DIR = td
stack_config.CONFIG_PATH = td / "stack_config.json"

os.environ["SMTP_HOST"] = "smtp.ghost.example"
os.environ["SMTP_USER"] = "ghost@example.com"
os.environ["SMTP_PASS"] = "secret"

# Fresh install: no stack file, install window open → env ignored
assert stack_config._install_window_open()
resolved = stack_config.resolved_smtp()
assert resolved.get("source") == "none", resolved
assert not stack_config.smtp_configured()

# Wizard saves SMTP to stack file
stack_config.patch_stack_config(
    {
        "smtp": {
            "host": "smtp.wizard.example",
            "port": 587,
            "user": "admin@wizard.example",
            "password": "wizard-pass",
            "from": "admin@wizard.example",
        }
    }
)
resolved = stack_config.resolved_smtp()
assert resolved.get("host") == "smtp.wizard.example", resolved
assert resolved.get("source") == "stack_config", resolved

# After install complete, env wins for ops overrides
stack_config.patch_stack_config({"install_complete": True})
assert not stack_config._install_window_open()
resolved = stack_config.resolved_smtp()
assert resolved.get("host") == "smtp.ghost.example", resolved
assert resolved.get("source") == "env", resolved

# Wizard deployment_mode persists over compose .env default
os.environ["WORKFRAME_DEPLOYMENT_MODE"] = "trusted_team"
stack_config.patch_stack_config({"deployment_mode": "single_user_local"})
assert stack_config.resolve_deployment_mode() == "single_user_local"

print("stack_config install-window smtp self-check ok")
