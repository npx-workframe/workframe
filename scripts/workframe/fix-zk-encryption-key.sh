#!/usr/bin/env bash
# Fix ZK_AUTH_ENCRYPTION_KEY when it was generated as hex instead of base64.
set -euo pipefail
ENV_FILE="${1:-/opt/workframe/MyBusiness/.env}"
FORCE="${2:-}"
python3 - "$ENV_FILE" "$FORCE" <<'PY'
import base64, os, re, sys
from pathlib import Path
env, force = Path(sys.argv[1]), sys.argv[2] == "--force"
text = env.read_text(encoding="utf-8")
m = re.search(r"^ZK_AUTH_ENCRYPTION_KEY=(.*)$", text, re.M)
if not m:
    print("ZK_AUTH_ENCRYPTION_KEY missing"); sys.exit(1)
val = m.group(1).strip()
try:
    ok = len(base64.b64decode(val)) == 32
except Exception:
    ok = False
if ok:
    print("ZK_AUTH_ENCRYPTION_KEY already valid"); sys.exit(0)

zk_db = Path(os.environ.get("WORKFRAME_API_DATA_DIR", "/app/data")) / "zk_auth.db"
if zk_db.is_file() and not force:
    import sqlite3
    n = sqlite3.connect(str(zk_db)).execute("SELECT COUNT(*) FROM identities").fetchone()[0]
    if n > 0:
        print(f"REFUSING: {n} encrypted identities present. Regenerating the KEK will lock "
              f"out every existing user. Re-run with --force to proceed.", file=sys.stderr)
        sys.exit(1)

new_key = base64.b64encode(os.urandom(32)).decode()
text = re.sub(r"^ZK_AUTH_ENCRYPTION_KEY=.*$", f"ZK_AUTH_ENCRYPTION_KEY={new_key}", text, flags=re.M)
env.write_text(text, encoding="utf-8")
print("ZK_AUTH_ENCRYPTION_KEY regenerated (was invalid base64)")
PY
