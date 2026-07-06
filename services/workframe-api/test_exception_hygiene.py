#!/usr/bin/env python3
"""WF-035 smoke: auth/vault handler paths log structured errors."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
src = (ROOT / "server.py").read_text(encoding="utf-8")
assert "_log_handler_error" in src
assert 'POST /api/auth/start' in src
assert 'POST /api/admin/vault/init' in src
assert "_sync_workspace_messaging_gateway restart" in src
print("exception hygiene self-check ok")
