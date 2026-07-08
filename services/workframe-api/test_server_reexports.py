"""WF-032 guard: server.py must re-export symbols still called from extracted modules."""

from __future__ import annotations

import os
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

os.environ.setdefault("WORKFRAME_API_DATA_DIR", str(API_DIR / ".tmp-test-data"))
os.environ.setdefault("HERMES_DATA", str(API_DIR / ".tmp-test-hermes"))
os.environ.setdefault("DEV_LOCAL_UNSAFE", "true")

import server  # noqa: E402


_REQUIRED = (
    "_parse_workspace_settings",
    "_strip_profile_action_env",
    "_user_action_env_specs",
    "_overlay_turn_user_env",
)


def test_server_wf032_reexports_present() -> None:
    missing = [name for name in _REQUIRED if not hasattr(server, name)]
    assert not missing, f"missing server re-exports: {missing}"


if __name__ == "__main__":
    test_server_wf032_reexports_present()
    print("ok")
