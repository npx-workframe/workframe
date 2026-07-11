"""WF-032 extract: runtime profiles, user cohort, and delegation grants."""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

import yaml


# ponytail: docker exec per bind was ~10s; cache gateway registration briefly.
_gateway_registered_cache: dict[str, tuple[bool, float]] = {}
_GATEWAY_REG_TTL_SEC = 45.0


def _srv():
    import server as srv

    return srv


def _runtime_profile_slug(user_id: str, template_slug: str) -> str:
    template_slug = _srv().safe_profile_slug(template_slug)
    user_part = re.sub(r"[^a-z0-9]+", "-", _srv()._user_hermes_dir_slug(user_id).lower()).strip("-")[:20] or "user"
    slug = f"u-{user_part}-{template_slug}"
    if len(slug) > 64:
        slug = slug[:64].rstrip("-")
    return _srv().safe_profile_slug(slug)


def _prepare_runtime_profile_credentials(
    runtime: str,
    user_id: str,
    workspace_id: str = "",
) -> bool:
    """Strip stale profile secrets, then overlay the runtime profile owner's keys.

    Delegation assigns work to another user's runtime slug; provider keys and
    billing follow the profile owner (assignee), not the user who delegated.
    """
    runtime = _srv().safe_profile_slug(str(runtime or "").strip())
    user = str(user_id or "").strip()
    if not runtime or not user or not _srv()._is_runtime_profile_slug(runtime):
        return False
    try:
        _srv().resolve_hermes_profile(runtime)
    except ValueError:
        return False
    _srv()._strip_profile_llm_env(runtime)
    _srv()._strip_profile_action_env(runtime)
    _srv()._reconcile_profile_llm_for_user(runtime, user, workspace_id)
    prov = _srv()._llm_billing_provider(runtime, user_id=user, workspace_id=workspace_id)
    _srv()._ensure_profile_llm_proxy(runtime, prov)
    return _srv()._user_can_use_llm(user, workspace_id, prov)


def _resolve_runtime_owner(runtime: str) -> tuple[str, str] | None:
    """Map a u-* runtime slug to (owner_user_id, workspace_id)."""
    runtime = _srv().safe_profile_slug(str(runtime or "").strip())
    if not _srv()._is_runtime_profile_slug(runtime):
        return None
    conn = _srv()._workframe_db()
    try:
        for row in conn.execute("SELECT id FROM workspaces WHERE deleted_at IS NULL").fetchall():
            wid = str(row["id"])
            uid = _user_id_for_runtime_slug(runtime, wid)
            if uid:
                return uid, wid
    finally:
        conn.close()
    return None


def _user_handle(user_id: str) -> str:
    """Short lowercase handle for cohort aliases (display_name or email local-part)."""
    user_id = str(user_id or "").strip()
    if not user_id:
        return "user"
    conn = _srv()._workframe_db()
    try:
        row = conn.execute(
            "SELECT display_name, email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return "user"
    display = str(row["display_name"] or "").strip()
    if display:
        handle = re.sub(r"[^a-z0-9]+", "-", display.lower()).strip("-")[:24]
        if handle:
            return handle
    email = str(row["email"] or "").strip().lower()
    if "@" in email:
        handle = re.sub(r"[^a-z0-9]+", "-", email.split("@", 1)[0]).strip("-")[:24]
        if handle:
            return handle
    return "user"


def _user_owner_name(user_id: str) -> str:
    return _user_handle(user_id).replace("-", " ").strip().title() or "User"


def _runtime_display_label(user_id: str, template_slug: str, workspace_id: str = "") -> str:
    template = _srv().safe_profile_slug(str(template_slug or "").strip())
    user_id = str(user_id or "").strip()
    if user_id:
        runtime = _runtime_profile_slug(user_id, template)
        reg_runtime = _srv()._agent_registry_row(runtime)
        if str(reg_runtime.get("display_name") or "").strip():
            return str(reg_runtime["display_name"]).strip()
    custom = _srv()._agent_db_display_name(template, workspace_id)
    if custom:
        return custom
    reg = _srv()._agent_registry_row(template)
    if reg.get("display_name"):
        return str(reg["display_name"])
    if _srv()._is_native_profile(template) or template.endswith("-agent"):
        return f"{_user_owner_name(user_id)}'s {_srv()._native_display_name().replace(' Agent', '')} Agent"
    role = _srv()._agent_db_display_name(template, workspace_id) or _srv()._agent_registry_row(template).get("display_name")
    if not role:
        role = template.replace("-", " ").title()
    return f"{_user_owner_name(user_id)}'s {role}"


def _cohort_alias(user_id: str, template_slug: str) -> str:
    """Human alias for docs/prompts — not the Hermes profile dir slug."""
    template = _srv().safe_profile_slug(template_slug)
    short = _srv()._profile_slug(template).replace("_", "-")
    return f"{_user_handle(user_id)}-{short}"


def resolve_runtime_assignee(template_slug: str, user_id: str, workspace_id: str = "") -> str:
    """Map template specialist slug → per-user runtime profile (has overlaid credentials)."""
    user_id = str(user_id or "").strip()
    template = _srv().safe_profile_slug(str(template_slug or "").strip())
    if not user_id:
        return template
    runtime = _runtime_profile_slug(user_id, template)
    ensure_runtime_profile(runtime, template, user_id, workspace_id)
    return runtime


def _user_id_for_runtime_slug(runtime: str, workspace_id: str) -> str | None:
    """Resolve owning user for a per-user runtime Hermes profile slug."""
    runtime = _srv().safe_profile_slug(str(runtime or "").strip())
    workspace_id = str(workspace_id or "").strip()
    if not _srv()._is_runtime_profile_slug(runtime) or not workspace_id:
        return None
    conn = _srv()._workframe_db()
    try:
        members = [
            str(row["user_id"] or "").strip()
            for row in conn.execute(
                """
            SELECT user_id FROM workspace_memberships
            WHERE workspace_id = ? AND status = 'active' AND deleted_at IS NULL
            """,
                (workspace_id,),
            ).fetchall()
            if str(row["user_id"] or "").strip()
        ]
        templates = [
            str(row["slug"] or "").strip()
            for row in conn.execute(
                """
            SELECT slug FROM agent_profiles
            WHERE workspace_id = ? AND deleted_at IS NULL
            """,
                (workspace_id,),
            ).fetchall()
            if str(row["slug"] or "").strip()
        ]
    finally:
        conn.close()
    for uid in members:
        for template in templates:
            if _runtime_profile_slug(uid, template) == runtime:
                return uid
    return None


def cohort_runtime_slugs(user_id: str, workspace_id: str) -> set[str]:
    """Runtime Hermes slugs this user may assign kanban/cron/delegation to (own cohort)."""
    return {
        str(row.get("runtime_slug") or "").strip()
        for row in ensure_user_agent_cohort(user_id, workspace_id)
        if str(row.get("runtime_slug") or "").strip()
    }


def _user_is_workspace_member(user_id: str, workspace_id: str) -> bool:
    user_id = str(user_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if not user_id or not workspace_id:
        return False
    conn = _srv()._workframe_db()
    try:
        return _srv()._workspace_member_role(conn, workspace_id, user_id) is not None
    finally:
        conn.close()


def _delegation_grantor_ids_for_grantee(
    grantee_user_id: str,
    workspace_id: str,
    scope: str | None = None,
) -> set[str]:
    grantee_user_id = str(grantee_user_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if scope is None:
        scope = _srv().DELEGATION_SCOPE_AGENTS_DELEGATE
    if not grantee_user_id or not workspace_id:
        return set()
    conn = _srv()._workframe_db()
    try:
        rows = conn.execute(
            """
            SELECT grantor_user_id FROM agent_delegation_grants
            WHERE workspace_id = ? AND grantee_user_id = ? AND scope = ?
              AND deleted_at IS NULL
              AND (expires_at IS NULL OR expires_at > datetime('now'))
            """,
            (workspace_id, grantee_user_id, scope),
        ).fetchall()
    finally:
        conn.close()
    return {str(row["grantor_user_id"]).strip() for row in rows if str(row["grantor_user_id"] or "").strip()}


def _delegation_grant_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "grantor_user_id": row["grantor_user_id"],
        "grantee_user_id": row["grantee_user_id"],
        "scope": row["scope"],
        "expires_at": row["expires_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_delegation_grants(workspace_id: str, user_id: str) -> dict[str, Any]:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not _user_is_workspace_member(user_id, workspace_id):
        raise PermissionError("forbidden")
    conn = _srv()._workframe_db()
    try:
        rows = conn.execute(
            """
            SELECT * FROM agent_delegation_grants
            WHERE workspace_id = ? AND deleted_at IS NULL
              AND (grantor_user_id = ? OR grantee_user_id = ?)
            ORDER BY created_at DESC
            """,
            (workspace_id, user_id, user_id),
        ).fetchall()
    finally:
        conn.close()
    return {
        "ok": True,
        "workspace_id": workspace_id,
        "grants": [_delegation_grant_payload(row) for row in rows],
    }


def create_delegation_grant(
    workspace_id: str,
    grantor_user_id: str,
    grantee_user_id: str,
    scope: str | None = None,
) -> dict[str, Any]:
    workspace_id = str(workspace_id or "").strip()
    grantor_user_id = str(grantor_user_id or "").strip()
    grantee_user_id = str(grantee_user_id or "").strip()
    if scope is None:
        scope = _srv().DELEGATION_SCOPE_AGENTS_DELEGATE
    scope = str(scope or _srv().DELEGATION_SCOPE_AGENTS_DELEGATE).strip()
    if not workspace_id or not grantor_user_id or not grantee_user_id:
        raise ValueError("grantor_grantee_required")
    if grantor_user_id == grantee_user_id:
        raise ValueError("self_grant_forbidden")
    if scope != _srv().DELEGATION_SCOPE_AGENTS_DELEGATE:
        raise ValueError("unsupported_scope")
    if not _user_is_workspace_member(grantor_user_id, workspace_id):
        raise PermissionError("forbidden")
    if not _user_is_workspace_member(grantee_user_id, workspace_id):
        raise ValueError("grantee_not_member")
    now = _srv()._utc_now()
    conn = _srv()._workframe_db()
    try:
        existing = conn.execute(
            """
            SELECT id FROM agent_delegation_grants
            WHERE workspace_id = ? AND grantor_user_id = ? AND grantee_user_id = ?
              AND scope = ? AND deleted_at IS NULL
            """,
            (workspace_id, grantor_user_id, grantee_user_id, scope),
        ).fetchone()
        if existing:
            grant_id = str(existing["id"])
            conn.execute(
                "UPDATE agent_delegation_grants SET updated_at = ?, expires_at = NULL WHERE id = ?",
                (now, grant_id),
            )
        else:
            grant_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO agent_delegation_grants (
                    id, workspace_id, grantor_user_id, grantee_user_id, scope,
                    expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (grant_id, workspace_id, grantor_user_id, grantee_user_id, scope, now, now),
            )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM agent_delegation_grants WHERE id = ?",
            (grant_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise ValueError("grant_persist_failed")
    return {"ok": True, "grant": _delegation_grant_payload(row)}


def revoke_delegation_grant(workspace_id: str, grant_id: str, user_id: str) -> dict[str, Any]:
    workspace_id = str(workspace_id or "").strip()
    grant_id = str(grant_id or "").strip()
    user_id = str(user_id or "").strip()
    conn = _srv()._workframe_db()
    try:
        row = conn.execute(
            """
            SELECT * FROM agent_delegation_grants
            WHERE id = ? AND workspace_id = ? AND deleted_at IS NULL
            """,
            (grant_id, workspace_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        if user_id not in {str(row["grantor_user_id"]), str(row["grantee_user_id"])}:
            raise PermissionError("forbidden")
        now = _srv()._utc_now()
        conn.execute(
            "UPDATE agent_delegation_grants SET deleted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, grant_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "id": grant_id}


def _allowed_runtime_profiles_for_workspace(workspace_id: str) -> set[str]:
    allowed: set[str] = set()
    conn = _srv()._workframe_db()
    try:
        members = [
            str(row["user_id"] or "").strip()
            for row in conn.execute(
                """
                SELECT user_id FROM workspace_memberships
                WHERE workspace_id = ? AND status = 'active' AND deleted_at IS NULL
                """,
                (workspace_id,),
            ).fetchall()
            if str(row["user_id"] or "").strip()
        ]
        templates = [
            str(row["slug"] or "").strip()
            for row in conn.execute(
                """
                SELECT slug FROM agent_profiles
                WHERE workspace_id = ? AND deleted_at IS NULL
                """,
                (workspace_id,),
            ).fetchall()
            if str(row["slug"] or "").strip()
        ]
    finally:
        conn.close()
    for uid in members:
        for template in templates:
            allowed.add(_runtime_profile_slug(uid, template))
    return allowed


def purge_stale_runtime_profiles(workspace_id: str) -> dict[str, Any]:
    workspace_id = str(workspace_id or "").strip()
    allowed = _allowed_runtime_profiles_for_workspace(workspace_id)
    purged: list[str] = []
    for profile in _srv()._list_profiles():
        if not _srv()._is_runtime_profile_slug(profile):
            continue
        if profile in allowed:
            continue
        _purge_runtime_profile(profile)
        purged.append(profile)
    for orphan in ("u-testalan-workframe-agent", "andy"):
        if orphan in _srv()._list_profiles() and orphan not in allowed and orphan not in purged:
            _purge_runtime_profile(orphan)
            purged.append(orphan)
    profiles_dir = _srv().HERMES_DATA / "profiles"
    if profiles_dir.is_dir():
        for entry in profiles_dir.iterdir():
            name = entry.name
            if not entry.is_dir() or name in allowed or name in purged:
                continue
            if name == "andy" or (name.startswith("u-test") and _srv()._is_runtime_profile_slug(name)):
                _purge_runtime_profile(name)
                purged.append(name)
    return {"ok": True, "purged": purged, "allowed_count": len(allowed)}


def _cohort_manifest_markdown(user_id: str, cohort: list[dict[str, Any]]) -> str:
    owner = _user_owner_name(user_id)
    lines = [
        f"# {owner}'s Workframe cohort",
        "",
        "This file is auto-generated by Workframe. Read it before kanban, cron, or delegation.",
        "",
        "## Rules",
        "",
        "- Use **runtime_slug** (column below) for kanban `--assignee`, cron agent targets, and `delegate_task` profile — never bare template names like `architect`.",
        "- Template profiles (`architect`, `dev`, …) are shared disks **without your API keys**; workers exit immediately.",
        "- Only interact with profiles listed here. Do not read other users' `u-*` profile `.env` files.",
        "- Valid kanban `workspace_kind`: `scratch`, `dir:/absolute/path`, `worktree` — not `project`.",
        "- Kanban workers must call `kanban_complete` or `kanban_block` before exit.",
        "- Hermes CLI: `/opt/hermes/.venv/bin/hermes -p <runtime_slug> …`",
        "",
        "## Your agents",
        "",
        "| Role | You call them | runtime_slug (kanban/delegate) | alias |",
        "|------|---------------|--------------------------------|-------|",
    ]
    for row in cohort:
        lines.append(
            f"| {row.get('role', '')} | {row.get('display_name', '')} | `{row.get('runtime_slug', '')}` | `{row.get('alias', '')}` |"
        )
    lines.extend(["", f"Owner user_id: `{user_id}`", ""])
    return "\n".join(lines)


def _write_workframe_cohort_manifest(user_id: str, workspace_id: str, cohort: list[dict[str, Any]]) -> None:
    if not cohort:
        return
    body = _cohort_manifest_markdown(user_id, cohort)
    for row in cohort:
        runtime = str(row.get("runtime_slug") or "").strip()
        if not runtime:
            continue
        path = _srv()._profile_dir(runtime) / "WORKFRAME_COHORT.md"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        except OSError:
            pass


def ensure_user_agent_cohort(user_id: str, workspace_id: str) -> list[dict[str, Any]]:
    """Provision runtime profiles + credentials for every workspace agent this user may orchestrate."""
    user_id = str(user_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if not user_id or not workspace_id:
        return []
    cohort: list[dict[str, Any]] = []
    conn = _srv()._workframe_db()
    try:
        rows = conn.execute(
            """
            SELECT slug, display_name, tagline, role, avatar_url, is_native
            FROM agent_profiles
            WHERE workspace_id = ? AND deleted_at IS NULL
            ORDER BY is_native DESC, created_at ASC
            """,
            (workspace_id,),
        ).fetchall()
    finally:
        conn.close()
    for row in rows:
        template = str(row["slug"] or "").strip()
        if not template:
            continue
        runtime = _runtime_profile_slug(user_id, template)
        if not _runtime_profile_ready(runtime):
            try:
                ensure_runtime_profile(runtime, template, user_id, workspace_id)
            except ValueError:
                continue
        ident = _srv()._agent_identity_fields(template, workspace_id, user_id)
        role = str(ident.get("role") or row["display_name"] or template).strip()
        cohort.append(
            {
                "template_slug": template,
                "runtime_slug": runtime,
                "display_name": _runtime_display_label(user_id, template, workspace_id),
                "kanban_assignee": runtime,
                "alias": _cohort_alias(user_id, template),
                "role": role,
                "tagline": str(ident.get("tagline") or row["tagline"] or ""),
                "avatar_url": ident.get("avatar_url"),
                "avatar_id": ident.get("avatar_id"),
                "is_native": bool(int(row["is_native"] or 0)),
            }
        )
    _write_workframe_cohort_manifest(user_id, workspace_id, cohort)
    return cohort


def _runtime_gateway_registered(runtime: str) -> bool:
    runtime = _srv().safe_profile_slug(str(runtime or "").strip())
    if not runtime:
        return False
    now = time.monotonic()
    cached = _gateway_registered_cache.get(runtime)
    if cached and now - cached[1] < _GATEWAY_REG_TTL_SEC:
        return cached[0]
    if _srv().SECURE_MODE and os.environ.get("WORKFRAME_SUPERVISOR_ALLOW_RAW_EXEC", "0") != "1":
        state = str(_srv().gateway_data(runtime).get("state") or "").lower()
        ok = state in {"running", "starting"} or _srv()._profile_api_healthy(runtime, timeout=0.8)
        _gateway_registered_cache[runtime] = (ok, now)
        return ok
    script = (
        "from pathlib import Path\n"
        f"p=Path('/run/service/gateway-{runtime}/run')\n"
        "raise SystemExit(0 if p.is_file() else 1)\n"
    )
    code, _ = _srv()._gateway_container_exec(["/opt/hermes/.venv/bin/python", "-c", script])
    ok = code == 0
    _gateway_registered_cache[runtime] = (ok, now)
    return ok


def _invalidate_gateway_registered_cache(runtime: str = "") -> None:
    if runtime:
        _gateway_registered_cache.pop(_srv().safe_profile_slug(runtime), None)
    else:
        _gateway_registered_cache.clear()


def _runtime_profile_on_disk(runtime: str) -> bool:
    p = _srv()._profile_dir(runtime)
    return p.is_dir() and _srv()._profile_config_path(runtime) is not None


def _runtime_profile_ready(runtime: str) -> bool:
    return _runtime_profile_on_disk(runtime) and _runtime_gateway_registered(runtime)


def _purge_runtime_profile(runtime: str) -> None:
    """Drop Hermes registry entry and on-disk dir (best-effort)."""
    try:
        _srv()._gateway_exec(_srv()._primary_profile(), ["profile", "delete", "-y", runtime])
    except Exception:  # noqa: BLE001
        pass
    shutil.rmtree(_srv()._profile_dir(runtime), ignore_errors=True)


def _register_runtime_profile(runtime: str, template: str) -> None:
    _srv()._ensure_profiles_dir_ready()
    cmd = ["profile", "create", "--clone-from", template, runtime]
    code, out = _srv()._gateway_exec(_srv()._primary_profile(), cmd)
    if code == 0:
        _inherit_runtime_profile_config(runtime, template)
        _srv()._chown_profile_tree(_srv()._profile_dir(runtime))
        return
    out_l = out.lower()
    if "already exists" in out_l:
        if _srv()._profile_config_path(runtime) is not None:
            return  # ponytail: Hermes registry + on-disk clone — adopt, don't recreate
        _purge_runtime_profile(runtime)
        code, out = _srv()._gateway_exec(_srv()._primary_profile(), cmd)
        if code == 0:
            _inherit_runtime_profile_config(runtime, template)
            _srv()._chown_profile_tree(_srv()._profile_dir(runtime))
            return
    if code != 0:
        raise ValueError(f"runtime profile create failed: {out.strip()}")


def _copy_tree_missing(src: Path, dst: Path) -> None:
    """Copy files from src into dst only when dst path is absent (never overwrite SOUL edits)."""
    if not src.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(src)
        target = dst / rel
        if target.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(item, target)
        except OSError:
            pass


def _copy_text_without_bom(src: Path, dst: Path) -> None:
    """Copy markdown identity files without UTF-8 BOM (Hermes blocks BOM in context files)."""
    raw = src.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(raw)


def _ensure_profile_terminal_cwd(profile: str, *, cwd: str = "/workspace") -> None:
    """Hermes terminal + code_execution project root must be the shared workspace."""
    config_path = _srv()._profile_gateway_config_path(profile)
    if not config_path or not config_path.is_file():
        return
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError:
        return
    fixed = re.sub(r"(?m)^  cwd: .*$", f"  cwd: {cwd}", raw, count=1)
    if fixed == raw:
        return
    try:
        config_path.write_text(fixed, encoding="utf-8")
    except OSError:
        pass


def _backfill_runtime_identity(runtime: str, template: str) -> None:
    """Fill missing SOUL/skills from template — credentials overlay never touches these."""
    runtime = _srv().safe_profile_slug(runtime)
    template = _srv().safe_profile_slug(template)
    rdir = _srv()._profile_dir(runtime)
    tdir = _srv()._profile_dir(template)
    if not rdir.is_dir() or not tdir.is_dir():
        return
    for name in ("SOUL.md", "AGENTS.md", "SETUP.md"):
        src = tdir / name
        dst = rdir / name
        if name == "SOUL.md":
            if _srv()._write_profile_soul_if_stub(runtime, template):
                continue
        if src.is_file() and not dst.is_file():
            try:
                _copy_text_without_bom(src, dst)
            except OSError:
                pass
    _copy_tree_missing(tdir / "skills", rdir / "skills")
    _ensure_profile_terminal_cwd(runtime)


def _load_profile_yaml_dict(profile: str) -> dict[str, Any]:
    _srv()._normalize_profile_config_yaml(profile)
    cfg = _srv()._profile_config_path(profile)
    if not cfg or not cfg.is_file():
        return {}
    try:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _profile_toolsets_ready(profile: str, want: tuple[str, ...] | list[str]) -> bool:
    cfg = _load_profile_yaml_dict(profile)
    if not cfg:
        return False
    names = [str(n) for n in want if str(n).strip()]
    if not names:
        return True
    ts = cfg.get("toolsets") if isinstance(cfg.get("toolsets"), list) else []
    if not all(name in ts for name in names):
        return False
    pts = cfg.get("platform_toolsets") if isinstance(cfg.get("platform_toolsets"), dict) else {}
    for platform in ("api_server", "cli"):
        plat = pts.get(platform) if isinstance(pts.get(platform), list) else []
        if not all(name in plat for name in names):
            return False
    agent = cfg.get("agent") if isinstance(cfg.get("agent"), dict) else {}
    disabled = agent.get("disabled_toolsets") if isinstance(agent.get("disabled_toolsets"), list) else []
    return not any(name in disabled for name in names)


def _inherit_runtime_profile_config(runtime: str, template: str) -> None:
    """Hermes clone-from copies .env/SOUL/skills but may omit profile.yaml on u-* slugs."""
    runtime = _srv().safe_profile_slug(runtime)
    template = _srv().safe_profile_slug(template)
    if _srv()._profile_config_path(runtime) is not None:
        return
    src = _srv()._profile_config_path(template)
    if src is None:
        raise ValueError(f"template profile has no config: {template}")
    dst = _srv()._profile_dir(runtime) / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def ensure_runtime_profile(
    runtime_slug: str,
    template_slug: str,
    user_id: str,
    workspace_id: str = "",
) -> None:
    _srv()._ensure_profiles_dir_ready()
    runtime = _srv().safe_profile_slug(runtime_slug)
    template = _srv().resolve_validated_profile(template_slug)
    if _runtime_profile_on_disk(runtime):
        if not _runtime_gateway_registered(runtime):
            try:
                _register_runtime_profile(runtime, template)
            except ValueError:
                pass
            ok, out, _port = _srv()._configure_profile_api(runtime)
            if not ok:
                raise ValueError(f"runtime profile api config failed: {out}")
        skills_dir = _srv()._profile_dir(runtime) / "skills"
        if not skills_dir.is_dir() or not any(skills_dir.iterdir()):
            _backfill_runtime_identity(runtime, template)
        if not _profile_toolsets_ready(runtime, _srv()._chat_toolsets_for_profile(runtime)):
            _srv()._ensure_profile_toolsets(runtime)
        _ensure_profile_terminal_cwd(runtime)
        # Existing profiles still need invariant repair.  This deliberately does
        # not copy template model preferences; reconciliation keeps the agent's
        # model when the acting user can use it and falls back to that user's
        # connected providers otherwise.
        _prepare_runtime_profile_credentials(runtime, user_id, workspace_id)
        _srv()._ensure_profile_proxy_headers(runtime)
        return
    _purge_runtime_profile(runtime)
    _register_runtime_profile(runtime, template)
    _srv()._chown_profile_tree(_srv()._profile_dir(runtime))
    if _srv()._profile_config_path(runtime) is None:
        raise ValueError(f"runtime profile bootstrap failed: {runtime}")
    # SOUL: clone inherits template at profile create; do not auto-overwrite on disk later.
    soul_src = _srv()._profile_dir(template) / "SOUL.md"
    soul_dst = _srv()._profile_dir(runtime) / "SOUL.md"
    if soul_src.is_file() and soul_dst.parent.is_dir() and not soul_dst.is_file():
        try:
            shutil.copy2(soul_src, soul_dst)
        except OSError:
            pass
    _srv()._write_profile_soul_if_stub(runtime, template)
    _backfill_runtime_identity(runtime, template)
    _srv()._strip_profile_llm_env(runtime)
    _srv()._strip_profile_action_env(runtime)
    ok, out, _port = _srv()._configure_profile_api(runtime)
    if not ok:
        raise ValueError(f"runtime profile api config failed: {out}")
    _srv()._ensure_profile_toolsets(runtime)
    _ensure_profile_terminal_cwd(runtime)
    _prepare_runtime_profile_credentials(runtime, user_id, workspace_id)
