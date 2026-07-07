#!/usr/bin/env python3
"""Remove smoke-test clutter from a dogfood Workframe install.

  python cleanup_dogfood_smoke.py --base http://127.0.0.1:18644 \\
      --data-dir D:\\ab\\projects\\MyBusiness\\workframe-api\\data

ponytail: dogfood on Windows Docker often cannot DELETE rooms via API (sqlite lock);
falls back to direct DB soft-delete and Hermes filesystem/registry cleanup.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from test_dogfood_flows import _mint_session_cookie, _pick_user, _req  # noqa: E402


def _smoke_room_ids(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT id FROM rooms
        WHERE deleted_at IS NULL AND (
          slug LIKE 'smoke-%'
          OR name LIKE 'Smoke %'
          OR topic = 'smoke test'
          OR (name = 'Smoke Agent' AND slug LIKE 'dm-%')
        )
        """
    ).fetchall()
    return [str(r[0]) for r in rows]


def _smoke_agent_slugs(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT slug FROM agent_profiles
        WHERE deleted_at IS NULL AND (
          slug LIKE 'smoke-agent-%' OR display_name = 'Smoke Agent'
        )
        """
    ).fetchall()
    return [str(r[0]) for r in rows if str(r[0]).strip()]


def _smoke_invite_ids(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT id FROM workspace_invites
        WHERE deleted_at IS NULL AND email LIKE '%@workframe.test'
        """
    ).fetchall()
    return [str(r[0]) for r in rows]


def _is_smoke_profile(name: str) -> bool:
    return "smoke-agent" in name


def _soft_delete_rooms_db(conn: sqlite3.Connection) -> int:
    now = str(int(time.time()))
    cur = conn.execute(
        """
        UPDATE rooms SET deleted_at = ?
        WHERE deleted_at IS NULL AND (
          slug LIKE 'smoke-%' OR name LIKE 'Smoke %' OR topic = 'smoke test'
          OR (name = 'Smoke Agent' AND slug LIKE 'dm-%')
        )
        """,
        (now,),
    )
    conn.commit()
    return int(cur.rowcount)


def _soft_delete_agents_db(conn: sqlite3.Connection, slugs: list[str]) -> int:
    if not slugs:
        return 0
    now = str(int(time.time()))
    placeholders = ",".join("?" * len(slugs))
    cur = conn.execute(
        f"UPDATE agent_profiles SET deleted_at = ?, updated_at = ? "
        f"WHERE deleted_at IS NULL AND slug IN ({placeholders})",
        [now, now, *slugs],
    )
    conn.commit()
    return int(cur.rowcount)


def _revoke_invites_db(conn: sqlite3.Connection, invite_ids: list[str]) -> int:
    if not invite_ids:
        return 0
    now = str(int(time.time()))
    placeholders = ",".join("?" * len(invite_ids))
    cur = conn.execute(
        f"UPDATE workspace_invites SET deleted_at = ? WHERE id IN ({placeholders}) AND deleted_at IS NULL",
        [now, *invite_ids],
    )
    conn.commit()
    return int(cur.rowcount)


def _agents_root(data_dir: Path) -> Path | None:
    # MyBusiness dogfood: data is workframe-api/data, Agents is sibling of workframe-api.
    candidate = data_dir.parent.parent / "Agents"
    return candidate if candidate.is_dir() else None


def _cleanup_hermes_fs(agents_root: Path) -> None:
    agents_json = agents_root / "workframe" / "agents.json"
    if agents_json.is_file():
        data = json.loads(agents_json.read_text(encoding="utf-8"))
        agents = data.get("agents", {})
        if isinstance(agents, dict):
            data["agents"] = {k: v for k, v in agents.items() if not _is_smoke_profile(k)}
            agents_json.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for rel in ("avatar-registry.json", "routes.json"):
        path = agents_root / "workframe" / rel
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if rel == "avatar-registry.json":
            assigns = payload.get("assignments", {})
            if isinstance(assigns, dict):
                for key in [k for k in assigns if _is_smoke_profile(k)]:
                    del assigns[key]
        else:
            routes = payload.get("routes", [])
            if isinstance(routes, list):
                payload["routes"] = [
                    r for r in routes if not _is_smoke_profile(str(r.get("profile", "")))
                ]
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    profiles = agents_root / "profiles"
    if profiles.is_dir():
        for entry in profiles.iterdir():
            if entry.is_dir() and _is_smoke_profile(entry.name):
                shutil.rmtree(entry, ignore_errors=True)

    bin_dir = agents_root / ".local" / "bin"
    if bin_dir.is_dir():
        for entry in bin_dir.iterdir():
            if _is_smoke_profile(entry.name):
                entry.unlink(missing_ok=True)


def _prune_lane_registry(data_dir: Path) -> int:
    path = data_dir / "lane-registry.json"
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    lanes = data.get("lanes")
    if not isinstance(lanes, dict):
        return 0
    removed = 0
    for key in [k for k in lanes if _is_smoke_profile(k)]:
        del lanes[key]
        removed += 1
    if removed:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return removed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:18644")
    ap.add_argument("--data-dir", default=r"D:\ab\projects\MyBusiness\workframe-api\data")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    db_path = data_dir / "workframe.db"
    conn = sqlite3.connect(db_path, timeout=30)
    room_ids = _smoke_room_ids(conn)
    agent_slugs = _smoke_agent_slugs(conn)
    invite_ids = _smoke_invite_ids(conn)
    print(f"found {len(room_ids)} smoke rooms, {len(agent_slugs)} smoke agents, {len(invite_ids)} test invites")

    if args.dry_run:
        print("dry-run — no changes")
        conn.close()
        return

    user_id, email = _pick_user(data_dir)
    cookie, session_id = _mint_session_cookie(data_dir, user_id)
    print(f"session as {email} ({user_id[:8]}…)")

    def api(method: str, path: str, body: dict | None = None) -> tuple[int, dict[str, Any]]:
        return _req(args.base, method, path, body=body, cookie=cookie, session_id=session_id, timeout=180)

    api_room_ok = 0
    for rid in room_ids:
        code, payload = api("DELETE", f"/api/rooms/{rid}")
        if code == 200:
            api_room_ok += 1
        else:
            print(f"[warn] api delete room {rid[:8]}… — {payload.get('error')}")

    if api_room_ok < len(room_ids):
        n = _soft_delete_rooms_db(conn)
        print(f"db soft-deleted {n} smoke rooms (api ok={api_room_ok})")

    for slug in agent_slugs:
        code, payload = api("POST", "/api/hermes/profiles/delete", body={"profile": slug})
        if code != 200 or not payload.get("ok"):
            print(f"[warn] api delete profile {slug} — {payload.get('error') or payload}")

    n_agents = _soft_delete_agents_db(conn, agent_slugs)
    print(f"soft-deleted {n_agents} agent_profiles rows")

    n_inv = _revoke_invites_db(conn, invite_ids)
    print(f"revoked {n_inv} test invites")

    agents_root = _agents_root(data_dir)
    if agents_root:
        _cleanup_hermes_fs(agents_root)
        print(f"cleaned Hermes data under {agents_root}")
    else:
        print("[warn] Agents mount not found — skipped Hermes filesystem cleanup")

    pruned = _prune_lane_registry(data_dir)
    if pruned:
        print(f"pruned {pruned} lane-registry entries")

    remaining_rooms = len(_smoke_room_ids(conn))
    remaining_agents = len(_smoke_agent_slugs(conn))
    remaining_invites = len(_smoke_invite_ids(conn))
    conn.close()
    print(
        f"done — remaining smoke rooms={remaining_rooms}, agents={remaining_agents}, invites={remaining_invites}"
    )
    if remaining_rooms or remaining_agents:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
