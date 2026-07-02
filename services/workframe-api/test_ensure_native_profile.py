"""ponytail self-check: empty Hermes data must seed workframe-agent for gateway boot.

Run: python services/workframe-api/test_ensure_native_profile.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402

td = Path(tempfile.mkdtemp())
os.environ["HERMES_DATA"] = str(td)
server.HERMES_DATA = td
server.ROUTES_JSON = td / "workframe" / "routes.json"

slug = server._native_profile_slug()
assert slug == "workframe-agent"
assert not server._native_profile_present()
assert server._seed_native_profile_on_disk(slug)
assert server._native_profile_present()
assert (td / "profiles" / slug / "config.yaml").is_file()
routes = json.loads((td / "workframe" / "routes.json").read_text(encoding="utf-8"))
assert any(row.get("profile") == slug for row in routes.get("routes", []))

print("ensure native profile self-check ok")
