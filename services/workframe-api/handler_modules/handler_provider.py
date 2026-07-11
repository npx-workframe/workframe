"""Provider credentials / OAuth connect / internal LLM proxy (WF-032 slice)."""

from __future__ import annotations

import sqlite3
from typing import Any

import action_proxy
import internal_proxy_auth
import llm_proxy
import openrouter_catalog
import platform_auth
import run_surface_wiring


def _srv():
    import server

    return server


class ProviderRoutesMixin:

    def _handle_internal_llm_proxy(self, method: str, path: str) -> bool:
        srv = _srv()
        if not path.startswith("/internal/llm/"):
            return False
        body: bytes | None = None
        if method.upper() in {"POST", "PUT", "PATCH"}:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length > 0 else b""
        return llm_proxy.handle_proxy_request(
            self,
            path,
            method,
            body,
            resolve_secret=srv._resolve_secret_for_lease,
        )

    def _handle_internal_action_proxy(self, method: str, path: str) -> bool:
        srv = _srv()
        if not path.startswith("/internal/action/"):
            return False
        body: bytes | None = None
        if method.upper() in {"POST", "PUT", "PATCH"}:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length > 0 else b""
        return action_proxy.handle_proxy_request(
            self,
            path,
            method,
            body,
            resolve_secret=srv._resolve_secret_for_lease,
        )

    def _handle_internal_run_record(self, path: str) -> bool:
        srv = _srv()
        if path != "/internal/runs/record":
            return False
        ok, err = internal_proxy_auth.authorize_internal_proxy(self)
        if not ok:
            self._json(403, {"error": err or "forbidden"})
            return True
        try:
            body = self._read_json()
            if not isinstance(body, dict):
                raise ValueError("body must be a JSON object")
            result = run_surface_wiring.record_automated_surface_run(body)
            self._json(200, result)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            srv._log_handler_error("internal.runs.record", exc)
            self._json(500, {"ok": False, "error": str(exc)})
        return True

    def _route_get_user_credentials(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            if srv.DEV_LOCAL_UNSAFE:
                user_id = "dev"
            else:
                self._json(401, {"ok": False, "error": "no_authenticated_user"})
                return
        try:
            conn = sqlite3.connect(str(srv.AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            creds = conn.execute(
                "SELECT id, workspace_id, user_id, agent_profile_id, provider, credential_type, label, is_active, created_at, updated_at FROM credential_bindings WHERE user_id = ? AND deleted_at IS NULL ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            conn.close()
        except Exception:
            creds = []
        self._json(200, {"ok": True, "credentials": [dict(c) for c in creds]})

    def _route_get_me_credentials(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        try:
            conn = sqlite3.connect(str(srv._workframe_db_path()), timeout=3.0)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT id, workspace_id, user_id, agent_profile_id, provider, credential_type,
                       credential_ref, label, is_active, created_at, updated_at
                   FROM credential_bindings
                   WHERE user_id = ? AND deleted_at IS NULL
                   ORDER BY updated_at DESC, created_at DESC""",
                (user_id,),
            ).fetchall()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"ok": False, "error": f"db_error: {exc}"})
            return
        self._json(200, {"ok": True, "credentials": [dict(row) for row in rows]})

    def _route_get_me_providers(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        workspace_id = qs.get("workspace_id", [""])[0]
        self._json(200, srv.list_user_providers(user_id, workspace_id))

    def _route_post_me_credentials(self, body: dict) -> None:
        srv = _srv()
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        provider = str(body.get("provider", "")).strip()
        credential_type = str(body.get("credential_type", "api_key")).strip() or "api_key"
        secret = str(body.get("secret", "")).strip()
        spec = srv._catalog_provider(provider)
        if spec:
            credential_type = str(spec.get("connect_mode") or credential_type)
        env_var = str(body.get("env_var", "")).strip() or (
            str(spec.get("env_var") or "") if spec else ""
        ) or srv._default_credential_env_var(provider, credential_type)
        label = str(body.get("label", "")).strip() or env_var
        if not provider:
            self._json(400, {"ok": False, "error": "provider required"})
            return
        if not secret:
            self._json(400, {"ok": False, "error": "secret required"})
            return
        payload = srv._store_user_credential(user_id, provider, credential_type, secret, env_var, label)
        cred_ref = str(payload["credential_ref"])
        now = srv._utc_now()
        try:
            conn = sqlite3.connect(str(srv._workframe_db_path()), timeout=3.0)
            conn.row_factory = sqlite3.Row
            existing = conn.execute(
                """SELECT id FROM credential_bindings
                   WHERE user_id = ? AND provider = ? AND credential_type = ?
                     AND credential_ref = ? AND deleted_at IS NULL
                   ORDER BY updated_at DESC, created_at DESC LIMIT 1""",
                (user_id, provider, credential_type, cred_ref),
            ).fetchone()
            if existing:
                cred_id = str(existing["id"])
                conn.execute(
                    """UPDATE credential_bindings
                       SET label = ?, is_active = 1, updated_at = ?, deleted_at = NULL
                       WHERE id = ?""",
                    (label, now, cred_id),
                )
            else:
                cred_id = str(payload["credential_id"])
                conn.execute(
                    """INSERT INTO credential_bindings
                       (id, workspace_id, user_id, agent_profile_id, provider, credential_type,
                        credential_ref, label, is_active, created_by, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (cred_id, None, user_id, None, provider, credential_type, cred_ref, label, 1, user_id, now, now),
                )
            conn.execute(
                """UPDATE credential_bindings
                   SET is_active = 0, deleted_at = ?, updated_at = ?
                   WHERE user_id = ? AND provider = ? AND deleted_at IS NULL AND id != ?""",
                (now, now, user_id, provider, cred_id),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"ok": False, "error": f"db_error: {exc}"})
            return
        srv._invalidate_user_llm_picker_cache(user_id)
        self._log_audit("credential_stored", "credential_binding", cred_id, f"provider={provider}")
        health: dict[str, Any] = {}
        if provider == "openrouter":
            secret_probe = srv._credential_secret(
                {
                    "credential_ref": cred_ref,
                    "scope": "user",
                    "user_id": user_id,
                },
                user_id,
            )
            if secret_probe:
                health = openrouter_catalog.probe_account(secret_probe)
        try:
            srv._bootstrap_model_after_llm_connect(user_id, str(body.get("workspace_id") or ""), provider)
        except (OSError, RuntimeError, ValueError) as exc:
            srv._log_handler_error("POST /api/me/credentials provider bootstrap", exc)
        self._json(200, {
            "ok": True,
            "credential_id": cred_id,
            "provider": provider,
            "credential_type": credential_type,
            "label": label,
            "is_active": 1,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
            "health": health,
            **payload,
        })

    def _route_post_me_telegram_link(self, body: dict) -> None:
        srv = _srv()
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        result = platform_auth.verify_telegram_login(body if isinstance(body, dict) else {})
        if not result.get("ok"):
            self._json(400, {"ok": False, "error": result.get("error") or "telegram_link_failed"})
            return
        patch = result.get("platform_ids") if isinstance(result.get("platform_ids"), dict) else {}
        if patch:
            srv._merge_user_platform_ids(user_id, {str(k): str(v) for k, v in patch.items()})
        self._json(200, {"ok": True, "provider": "telegram", "platform_ids": patch})

    def _route_pattern_get_me_oauth_status(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 5 or parts[2] != "oauth" or parts[4] != "status":
            self._json(404, {"error": "not_found"})
            return
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        provider_id = parts[3]
        session_id = str(qs.get("session_id", [""])[0] or "").strip()
        if not session_id:
            self._json(400, {"ok": False, "error": "session_id required"})
            return
        self._json(200, srv.device_oauth_status(user_id, provider_id, session_id))

    def _route_pattern_get_agent_credentials(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        agent_id = parts[2]
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        try:
            conn = sqlite3.connect(str(srv._workframe_db_path()), timeout=3.0)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT id, workspace_id, user_id, agent_profile_id, provider,
                      credential_type, credential_ref, label, is_active,
                      expires_at, created_by, created_at, updated_at
                   FROM credential_bindings
                   WHERE agent_profile_id = ? AND deleted_at IS NULL
                   ORDER BY created_at DESC""",
                (agent_id,),
            ).fetchall()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"ok": False, "error": str(exc)})
            return
        self._json(200, {
            "ok": True,
            "scope": "agent_profile",
            "agent_profile_id": agent_id,
            "credentials": [dict(r) for r in rows],
        })

    def _route_pattern_post_me_oauth_start(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 5 or parts[2] != "oauth" or parts[4] != "start":
            self._json(404, {"error": "not_found"})
            return
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        provider_id = parts[3]
        workspace_id = str(body.get("workspace_id") or "")
        self._json(200, srv.start_user_oauth(user_id, provider_id, workspace_id))

    def _route_pattern_post_me_providers_disconnect(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 5 or parts[2] != "providers" or parts[4] != "disconnect":
            self._json(404, {"error": "not_found"})
            return
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        self._json(200, srv.disconnect_user_provider(user_id, parts[3]))

    def _route_pattern_delete_me_credentials(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) != 4 or parts[2] != "credentials":
            self._json(404, {"error": "not_found"})
            return
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        self._json(200, srv.disconnect_user_credential(user_id, parts[3]))
