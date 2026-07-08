"""Admin / meta / doctor / supervisor / data-read routes (WF-032 slice)."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import urllib.parse
from pathlib import Path
from typing import Any

import credential_vault
import site_meta
import stack_updates
from supervisor_client import _supervisor_request


def _srv():
    import server

    return server


class AdminRoutesMixin:

    def _route_get_meta(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, srv.workframe_meta())

    def _route_get_health(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        vault_stat = credential_vault.vault_status()
        self._json(
            200,
            {
                "ok": True,
                "version": srv.VERSION,
                "mode": "dev_unsafe" if srv.DEV_LOCAL_UNSAFE else "secure",
                "secure_mode": srv.SECURE_MODE,
                "deployment_mode": srv.DEPLOYMENT_MODE,
                "admin_updates_enabled": os.environ.get("WORKFRAME_ENABLE_ADMIN_UPDATES") == "1",
                "docker_sock_on_api": Path("/var/run/docker.sock").exists(),
                "proxy_token_configured": internal_proxy_auth.proxy_token_configured(),
                "vault_sealed": vault_stat.get("sealed"),
                "vault_envelope": not vault_stat.get("sealed"),
                "install_window_open": srv._install_window_open(),
                "workframe_e2e": os.environ.get("WORKFRAME_E2E") == "1",
                "dev_local_unsafe": srv.DEV_LOCAL_UNSAFE,
            },
        )

    def _route_get_setup_status(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        try:
            db = srv._workframe_db()
            ws = db.execute("SELECT id FROM workspaces WHERE slug='default' AND deleted_at IS NULL").fetchone()
            if not ws:
                db.close()
                self._json(200, {"setup_complete": False})
                return
            agents = db.execute(
                "SELECT COUNT(*) AS c FROM agent_profiles WHERE workspace_id = ? AND deleted_at IS NULL",
                (ws["id"],),
            ).fetchone()
            db.close()
            self._json(200, {"setup_complete": bool(agents and agents["c"] > 0)})
        except Exception:
            self._json(200, {"setup_complete": False})

    def _route_get_public_site_meta(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, srv._public_site_meta_payload())

    def _route_get_public_link_preview(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        meta = srv._public_site_meta_payload()
        html = site_meta.link_preview_html(meta).encode("utf-8")
        self._send(200, html, "text/html; charset=utf-8")

    def _route_get_public_manifest(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        meta = srv._public_site_meta_payload()
        body = json.dumps(site_meta.manifest_payload(meta), indent=2).encode("utf-8")
        self._send(200, body, "application/manifest+json; charset=utf-8")

    def _route_get_me_cohort(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        workspace_id = str(qs.get("workspace_id", [""])[0] or "").strip()
        if not workspace_id:
            self._json(400, {"ok": False, "error": "workspace_id_required"})
            return
        ws_id = srv._resolve_wid(workspace_id) or workspace_id
        if not srv._user_is_workspace_member(user_id, ws_id):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        cohort = srv.ensure_user_agent_cohort(user_id, ws_id)
        self._json(
            200,
            {
                "ok": True,
                "workspace_id": ws_id,
                "user_id": user_id,
                "cohort": cohort,
            },
        )

    def _route_get_agents(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, srv.workframe_agents())

    def _route_get_snapshot(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, srv.build_snapshot())

    def _route_get_activity_detail(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        profile = qs.get("profile", [""])[0].strip()
        tool_call_id = qs.get("tool_call_id", [""])[0].strip()
        session_id = qs.get("session_id", [""])[0].strip()
        message_id = qs.get("message_id", [""])[0].strip()
        self._json(200, srv.activity_detail(profile, tool_call_id, session_id, message_id))

    def _route_get_files_tree(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, {"root": srv.files_tree()})

    def _route_get_files_list(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        rel = qs.get("path", [""])[0]
        reason = srv._workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        self._json(200, srv.files_list(rel))

    def _route_get_files_state(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, srv.workspace_state())

    def _route_get_files_read(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        rel = qs.get("path", [""])[0]
        reason = srv._workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        self._json(200, srv.file_read(rel))

    def _route_get_files_raw(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        rel = qs.get("path", [""])[0]
        reason = srv._workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        try:
            data, mime = srv.file_raw(rel)
        except ValueError:
            self._json(404, {"error": "not found"})
            return
        self._send(200, data, mime)

    def _route_get_routes(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, srv.load_routes())

    def _route_post_files_write(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        rel = str(body.get("path") or "").strip()
        reason = srv._workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        content = str(body.get("content") or "")
        self._json(200, srv.file_write(rel, content))

    def _route_post_files_upload(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        rel = str(body.get("path") or "").strip()
        reason = srv._workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        content_b64 = str(body.get("content_base64") or body.get("content") or "")
        self._json(200, srv.file_upload_binary(rel, content_b64))

    def _route_get_admin_vault_status(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        self._json(200, {"ok": True, **credential_vault.vault_status()})

    def _route_get_doctor_agent_dm_runtimes(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        self._json(200, srv.doctor_audit_agent_dm_runtimes())

    def _route_get_admin_updates(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        desktop_version = str((qs.get("desktop_version") or [""])[0] or "").strip()
        try:
            self._json(
                200,
                stack_updates.updates_available(
                    desktop_version=desktop_version,
                    hermes_agent_version=srv._hermes_agent_version(),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"ok": False, "error": str(exc)})

    def _route_post_admin_updates_apply(self, body: dict) -> None:
        srv = _srv()
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        if not srv._admin_write_allowed(self):
            self._json(403, {"ok": False, "error": "admin_write_forbidden", "hint": "X-Workframe-Local required in dev-unsafe"})
            return
        target = str(body.get("target") or "all").strip().lower()
        if target not in {"hermes", "workframe", "all"}:
            self._json(400, {"ok": False, "error": "invalid_target"})
            return
        user_ack = body.get("user_ack") is True or str(body.get("user_ack") or "").lower() in {
            "1",
            "true",
            "yes",
        }
        try:
            result = srv._apply_stack_update(target, user_ack=user_ack)
            self._log_audit("stack_update_apply", "stack", target, str(result.get("ok")))
            self._json(200 if result.get("ok") else 500, result)
        except (OSError, RuntimeError, ValueError) as exc:
            srv._log_handler_error("POST /api/admin/updates/apply", exc)
            self._json(500, {"ok": False, "error": str(exc)})

    def _route_post_admin_stack_restart_gateway(self, body: dict) -> None:
        srv = _srv()
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        if not srv._admin_write_allowed(self):
            self._json(403, {"ok": False, "error": "admin_write_forbidden", "hint": "X-Workframe-Local required in dev-unsafe"})
            return
        try:
            result = srv._restart_stack_gateway()
            self._log_audit("stack_restart_gateway", "stack", "gateway", str(result.get("ok")))
            self._json(200 if result.get("ok") else 500, result)
        except (OSError, RuntimeError, ValueError) as exc:
            srv._log_handler_error("POST /api/admin/stack/restart-gateway", exc)
            self._json(500, {"ok": False, "error": str(exc)})

    def _route_post_admin_vault_init(self, body: dict) -> None:
        srv = _srv()
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        if not srv._admin_write_allowed(self):
            self._json(403, {"ok": False, "error": "admin_write_forbidden"})
            return
        passphrase = str(body.get("passphrase") or "").strip()
        if not passphrase:
            self._json(400, {"ok": False, "error": "passphrase required"})
            return
        try:
            status = credential_vault.init_vault_passphrase(passphrase)
            self._log_audit("vault_passphrase_init", "vault", "meta", "passphrase_enabled")
            self._json(200, {"ok": True, **status})
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
        except (RuntimeError, OSError) as exc:
            srv._log_handler_error("POST /api/admin/vault/init", exc)
            self._json(500, {"ok": False, "error": str(exc)})

    def _route_post_admin_vault_unlock(self, body: dict) -> None:
        srv = _srv()
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        passphrase = str(body.get("passphrase") or "").strip()
        if not passphrase:
            self._json(400, {"ok": False, "error": "passphrase required"})
            return
        try:
            status = credential_vault.unlock_vault(passphrase)
            self._log_audit("vault_unlock", "vault", "meta", "unsealed")
            self._json(200, {"ok": True, **status})
        except ValueError as exc:
            self._log_audit("vault_unlock_failed", "vault", "meta", str(exc))
            self._json(403, {"ok": False, "error": str(exc)})
        except (RuntimeError, OSError) as exc:
            srv._log_handler_error("POST /api/admin/vault/unlock", exc)
            self._json(500, {"ok": False, "error": str(exc)})

    def _route_post_admin_vault_seal(self, body: dict) -> None:
        srv = _srv()
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        if not srv._admin_write_allowed(self):
            self._json(403, {"ok": False, "error": "admin_write_forbidden"})
            return
        status = credential_vault.seal_vault()
        self._log_audit("vault_seal", "vault", "meta", "sealed")
        self._json(200, {"ok": True, **status})

    def _route_post_admin_vault_wipe(self, body: dict) -> None:
        srv = _srv()
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        if not srv._admin_write_allowed(self):
            self._json(403, {"ok": False, "error": "admin_write_forbidden"})
            return
        if not body.get("confirm"):
            self._json(400, {"ok": False, "error": "confirm required"})
            return
        deleted = credential_vault.wipe_all_secrets()
        credential_vault.seal_vault()
        self._log_audit("vault_wipe", "vault", "secrets", f"deleted={deleted}")
        self._json(200, {"ok": True, "deleted": deleted, **credential_vault.vault_status()})

    def _route_get_supervisor_profile_status(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        profile = qs.get("profile", [""])[0]
        if not profile:
            self._json(400, {"error": "profile required"})
            return
        if srv.SUPERVISOR_URL:
            self._json(
                *_supervisor_request(
                    "GET",
                    f"/v1/profile.status?profile={urllib.parse.quote(profile, safe='')}",
                    timeout=10.0,
                )
            )
            return
        self._json(503, {"ok": False, "error": "WORKFRAME_SUPERVISOR_URL not configured"})

    def _route_get_supervisor_stack_status(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        if srv.SUPERVISOR_URL:
            self._json(*_supervisor_request("GET", "/v1/stack.status", timeout=15.0))
            return
        self._json(503, {"ok": False, "error": "WORKFRAME_SUPERVISOR_URL not configured"})

    def _route_get_admin_audit(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        if srv.SECURE_MODE and not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        try:
            limit = min(int(qs.get("limit", ["50"])[0]), 200)
            offset = max(int(qs.get("offset", ["0"])[0]), 0)
        except (ValueError, IndexError):
            limit, offset = 50, 0
        event_type_filter = str(qs.get("event_type", [""])[0]).strip()
        user_filter = str(qs.get("user_id", [""])[0]).strip()
        try:
            conn = sqlite3.connect(str(srv._workframe_db_path()), timeout=3.0)
            conn.row_factory = sqlite3.Row
            where_clauses: list[str] = []
            params: list = []
            if event_type_filter:
                where_clauses.append("event_type = ?")
                params.append(event_type_filter)
            if user_filter:
                where_clauses.append("user_id = ?")
                params.append(user_filter)
            where_str = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            rows = conn.execute(
                f"""SELECT id, user_id, event_type, target_type, target_id,
                            summary, metadata, ip_address, created_at
                     FROM audit_events
                     {where_str}
                     ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                params + [limit, offset],
            ).fetchall()
            total = conn.execute(
                f"SELECT COUNT(*) AS c FROM audit_events {where_str}",
                params,
            ).fetchone()["c"]
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"ok": False, "error": str(exc)})
            return
        self._json(200, {
            "ok": True,
            "total": total,
            "limit": limit,
            "offset": offset,
            "events": [dict(r) for r in rows],
        })

    def _route_get_events(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        cors_origin = srv._cors_origin_for(self.headers)
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        try:
            while True:
                payload = json.dumps(srv.build_snapshot())
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
                time.sleep(srv.SSE_INTERVAL)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _route_pattern_get_public_branding(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        branding_match = re.fullmatch(r"/api/public/branding/(og|favicon)", path)
        if not branding_match:
            self._json(404, {"ok": False, "error": "not_found"})
            return
        asset = site_meta.branding_asset_bytes(branding_match.group(1))
        if not asset:
            self._json(404, {"ok": False, "error": "not_found"})
            return
        data, ctype = asset
        self._send(200, data, ctype)

    def _supervisor_proxy_post(self, subpath: str, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        if srv.SUPERVISOR_URL:
            self._json(*_supervisor_request("POST", subpath, body))
            return
        self._json(503, {"ok": False, "error": "WORKFRAME_SUPERVISOR_URL not configured"})

    def _route_post_supervisor_profile_start(self, body: dict) -> None:
        srv = _srv()
        self._supervisor_proxy_post("/v1/profile.start", body)

    def _route_post_supervisor_profile_stop(self, body: dict) -> None:
        srv = _srv()
        self._supervisor_proxy_post("/v1/profile.stop", body)

    def _route_post_supervisor_profile_disable(self, body: dict) -> None:
        srv = _srv()
        self._supervisor_proxy_post("/v1/profile.disable", body)

    def _route_pattern_post_memory(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 3:
            self._json(404, {"error": "not_found"})
            return
        mem_id = parts[2]
        user_id = str(getattr(self, "auth_user", "") or "")
        try:
            conn = sqlite3.connect(str(srv.AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            item = conn.execute("SELECT * FROM memory_items WHERE id = ? AND deleted_at IS NULL", (mem_id,)).fetchone()
            if not item:
                conn.close()
                self._json(404, {"error": "memory_not_found"})
                return
            if not srv.DEV_LOCAL_UNSAFE and str(item["created_by_user_id"]) != user_id:
                auth_role = str(getattr(self, "auth_role", ""))
                if auth_role not in srv.OWNER_ADMIN_ROLES:
                    conn.close()
                    self._json(403, {"error": "forbidden"})
                    return
            now_ts = str(int(time.time()))
            conn.execute("UPDATE memory_items SET deleted_at = ?, updated_at = ? WHERE id = ?", (now_ts, now_ts, mem_id))
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        self._log_audit("memory_deleted", "memory_item", mem_id, f"user={user_id}")
        self._json(200, {"ok": True, "memory_id": mem_id, "status": "deleted"})

    def _route_pattern_delete_memory(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 3:
            self._json(404, {"ok": False, "error": "memory_not_found"})
            return
        mem_id = parts[2]
        try:
            db = srv._workframe_db()
            cur = db.execute(
                "UPDATE memory_items SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
                (str(int(time.time())), mem_id),
            )
            db.commit()
            affected = cur.rowcount
            db.close()
        except Exception:
            self._json(500, {"ok": False, "error": "delete_failed"})
            return
        if not affected:
            self._json(404, {"ok": False, "error": "memory_not_found"})
            return
        self._json(200, {"ok": True, "memory_id": mem_id, "status": "deleted"})

    def _route_patch_doctor_repair(self, body: dict) -> None:
        srv = _srv()
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        repair = body.get("repair", True) is not False
        result = srv.doctor_repair_agent_dm_runtimes(repair=repair)
        if repair:
            self._log_audit(
                "doctor_repair_agent_dm_runtimes",
                "runtime_profile",
                "",
                f"repaired={len(result.get('repaired') or [])} failed={len(result.get('failed') or [])}",
            )
        self._json(200, result)
