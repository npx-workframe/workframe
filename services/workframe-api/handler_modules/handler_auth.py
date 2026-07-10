"""Auth / session / OAuth callback route handlers (WF-032 slice)."""

from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
from typing import Any

import auth_rate_limit
import google_auth
import stack_config
import zk_auth as _zk
from email_sender import APP_BASE_URL


def _srv():
    import server

    return server


class AuthRoutesMixin:

    def _route_post_auth_google_start(self, body: dict) -> None:
        srv = _srv()
        invite_email = str(body.get("email") or "").strip().lower()
        invite_token = str(body.get("invite_token") or "")
        if invite_email:
            allowed, deny_meta = srv._email_allowed_to_authenticate(invite_email)
            if not allowed and not srv._invite_token_allows_email(invite_token, invite_email):
                self._log_audit(
                    "login_denied_private",
                    "user",
                    invite_email,
                    str(deny_meta.get("error") or ""),
                )
                self._json(403, {"ok": False, **deny_meta})
                return
        try:
            payload = google_auth.start_google_auth(invite_email, invite_token)
            self._json(200, payload)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})

    def _route_post_auth_local_bootstrap(self, body: dict) -> None:
        srv = _srv()
        if srv.DEPLOYMENT_MODE != "single_user_local" or not srv._install_window_open():
            self._json(403, {"ok": False, "error": "local_bootstrap_unavailable"})
            return
        email = str(body.get("email") or "").strip().lower()
        if not email or "@" not in email:
            self._json(400, {"ok": False, "error": "email_required"})
            return
        display = str(body.get("display_name") or "").strip() or email.split("@", 1)[0]
        try:
            result = _zk.create_session_for_email(email)
        except (RuntimeError, OSError, sqlite3.Error) as exc:
            srv._log_handler_error("POST /api/auth/local-bootstrap", exc)
            self._json(500, {"ok": False, "error": str(exc)})
            return
        user_id = str(result["user_id"])
        self.auth_user = user_id
        self._ensure_user(user_id, display, email)
        self._first_owner_bootstrap(user_id, display, email)
        use_secure = srv._session_cookie_secure()
        cookie_val = _zk.session_cookie_value(result["session_id"], secure=use_secure)
        me_payload = srv._session_profile_payload(user_id)
        self._json(
            200,
            {
                "ok": True,
                "user_id": user_id,
                "session_id": result["session_id"],
                "refresh_token": result["refresh_token"],
                **(me_payload or {}),
            },
            extra_headers=[("Set-Cookie", cookie_val)],
        )

    def _route_post_auth_bootstrap(self, body: dict) -> None:
        srv = _srv()
        if not srv.SECURE_MODE:
            self._json(501, {"ok": False, "error": "bootstrap_requires_secure_mode"})
            return
        data = body if isinstance(body, dict) else {}
        user_id = str(data.get("user_id", "") or secrets.token_hex(8))
        user_email = str(data.get("email", ""))
        user_display = str(data.get("display_name", "") or "Owner")
        result = self._first_owner_bootstrap(user_id, user_display, user_email)
        self._log_audit("user_created", "user", user_id, f"first-owner bootstrap: {user_display}")
        self._json(200, result)

    def _route_post_setup(self, body: dict) -> None:
        srv = _srv()
        data = body if isinstance(body, dict) else {}
        agent_name = str(data.get("agent_name", "")).strip()
        workframe_name = str(data.get("workframe_name", "")).strip()
        if not agent_name:
            self._json(400, {"ok": False, "error": "agent_name required"})
            return
        try:
            db = srv._workframe_db()
            ws = db.execute("SELECT * FROM workspaces WHERE slug='default' AND deleted_at IS NULL").fetchone()
            if not ws:
                ws_id = str(uuid.uuid4())
                now = str(int(time.time()))
                workspace_display_name = workframe_name or "Default Workspace"
                ws_settings = stack_config.github_oauth_for_workspace_settings({})
                settings_json = json.dumps(ws_settings, sort_keys=True) if ws_settings else "{}"
                db.execute(
                    "INSERT INTO workspaces (id, slug, display_name, description, owner_id, status, created_at, updated_at, settings_json) VALUES (?, 'default', ?, '', '', 'active', ?, ?, ?)",
                    (ws_id, workspace_display_name, now, now, settings_json),
                )
                ws = db.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,)).fetchone()
            elif workframe_name and str(ws["display_name"] or "").strip() != workframe_name:
                now = str(int(time.time()))
                db.execute(
                    "UPDATE workspaces SET display_name = ?, updated_at = ? WHERE id = ?",
                    (workframe_name, now, ws["id"]),
                )
                ws = db.execute("SELECT * FROM workspaces WHERE id = ?", (ws["id"],)).fetchone()
            ws_id = ws["id"]
            existing_agents = db.execute("SELECT COUNT(*) AS c FROM agent_profiles WHERE workspace_id = ? AND deleted_at IS NULL", (ws_id,)).fetchone()
            if existing_agents and existing_agents["c"] > 0:
                if agent_name:
                    now = str(int(time.time()))
                    db.execute(
                        """
                        UPDATE agent_profiles
                        SET display_name = ?, updated_at = ?
                        WHERE workspace_id = ? AND is_native = 1 AND deleted_at IS NULL
                        """,
                        (agent_name, now, ws_id),
                    )
                    db.commit()
                db.close()
                self._json(200, {"ok": True, "already_initialized": True, "workspace_id": ws_id})
                return
            import re as _re
            agent_slug = _re.sub(r"[^a-z0-9-]", "", agent_name.lower().replace(" ", "-"))[:40]
            agent_id = str(uuid.uuid4())
            now = str(int(time.time()))
            db.execute(
                "INSERT INTO agent_profiles (id, workspace_id, slug, display_name, tagline, role, is_native, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, 'active', ?, ?)",
                (agent_id, ws_id, agent_slug, agent_name, str(data.get("agent_personality", "")), "native", now, now),
            )
            room_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO rooms (id, workspace_id, name, slug, topic, room_type, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'channel', 'active', ?, ?)",
                (room_id, ws_id, "General", "general", "General discussion", now, now),
            )
            db.commit()
            db.close()
            hermes = srv._bootstrap_after_setup(str(data.get("agent_personality", "")))
            self._json(
                200,
                {
                    "ok": True,
                    "workspace_id": ws_id,
                    "agent_id": agent_id,
                    "room_id": room_id,
                    "hermes": hermes,
                },
            )
        except Exception as exc:
            self._json(500, {"ok": False, "error": str(exc)})

    def _route_post_auth_start(self, body: dict) -> None:
        srv = _srv()
        email = str(body.get("email", "")).strip().lower()
        if not email or "@" not in email:
            self._json(400, {"ok": False, "error": "email required"})
            return
        client_ip = str(self.client_address[0] if self.client_address else "")
        import auth_rate_limit

        if not auth_rate_limit.allow_auth_request("start", client_ip, email):
            self._json(429, {"ok": False, "error": "too_many_requests"})
            return
        allowed, deny_meta = srv._email_allowed_to_authenticate(email)
        if not allowed:
            self._log_audit("login_denied_private", "user", email, str(deny_meta.get("error") or ""))
            self._json(403, {"ok": False, **deny_meta})
            return
        try:
            base = APP_BASE_URL.strip().lower()
            loopback = base.startswith("http://127.0.0.1") or base.startswith("http://localhost")
            expose_otp = (
                os.environ.get("WORKFRAME_E2E") == "1"
                and srv._install_window_open()
                and loopback
            )
            result = _zk.start_email_verification(
                email,
                dev_local_unsafe=srv.DEV_LOCAL_UNSAFE,
                expose_otp=expose_otp,
            )
        except (RuntimeError, OSError, sqlite3.Error) as exc:
            srv._log_handler_error("POST /api/auth/start", exc)
            self._json(500, {"ok": False, "error": str(exc)})
            return
        if not srv.DEV_LOCAL_UNSAFE and not expose_otp:
            result.pop("otp_code", None)
            result.pop("_dev_warning", None)
        result.pop("_e2e_warning", None)
        self._log_audit("otp_requested", "user", email, f"challenge={result.get('challenge_id','')}")
        self._json(200, {"ok": True, "status": "verification_sent", **result})

    def _route_post_auth_verify(self, body: dict) -> None:
        srv = _srv()
        email = str(body.get("email", "")).strip().lower()
        code = str(body.get("code", "")).strip()
        if not email or not code:
            self._json(400, {"ok": False, "error": "email and code required"})
            return
        client_ip = str(self.client_address[0] if self.client_address else "")
        import auth_rate_limit

        if not auth_rate_limit.allow_auth_request("verify", client_ip, email):
            self._json(429, {"ok": False, "error": "too_many_requests"})
            return
        allowed, deny_meta = srv._email_allowed_to_authenticate(email)
        if not allowed:
            self._log_audit("login_denied_private", "user", email, str(deny_meta.get("error") or ""))
            self._json(403, {"ok": False, **deny_meta})
            return
        try:
            result = _zk.verify_email_code(email, code)
        except ValueError as exc:
            self._log_audit("login_failed", "user", email, f"verify failed: {exc}")
            self._json(401, {"ok": False, "error": str(exc)})
            return
        except (RuntimeError, OSError, sqlite3.Error) as exc:
            srv._log_handler_error("POST /api/auth/verify", exc)
            self._json(500, {"ok": False, "error": str(exc)})
            return
        use_secure = srv._session_cookie_secure()
        cookie_val = _zk.session_cookie_value(result["session_id"], secure=use_secure)
        self.auth_user = result["user_id"]
        self._ensure_user(result["user_id"], email, email)
        if srv._install_window_open():
            stack_config.mark_install_admin_verified(email)
        self._log_audit("login", "session", result["session_id"],
                        f"user={result['user_id']} new={result['is_new_user']}")
        me_payload = srv._session_profile_payload(result["user_id"])
        self._json(
            200,
            {
                "ok": True,
                "user_id": result["user_id"],
                "session_id": result["session_id"],
                "refresh_token": result["refresh_token"],
                "expires_at": result["expires_at"],
                "is_new_user": result["is_new_user"],
                **(me_payload or {}),
            },
            extra_headers=[("Set-Cookie", cookie_val)],
        )

    def _route_post_auth_logout(self, body: dict) -> None:
        srv = _srv()
        sid = srv._session_id_from_request(self)
        user_id = str(getattr(self, "auth_user", "") or "")
        if sid:
            try:
                _zk.logout_session(sid)
            except (RuntimeError, OSError, sqlite3.Error) as exc:
                srv._log_handler_error("POST /api/auth/logout", exc)
        use_secure = srv._session_cookie_secure()
        cookie_val = _zk.clear_session_cookie(secure=use_secure)
        self._log_audit("logout", "session", sid, f"user={user_id}")
        self._json(200, {"ok": True}, extra_headers=[("Set-Cookie", cookie_val)])

    def _route_post_auth_refresh(self, body: dict) -> None:
        srv = _srv()
        refresh_token = str(body.get("refresh_token", "")).strip()
        if not refresh_token:
            sid = srv._session_id_from_request(self)
            if not sid:
                self._json(400, {"ok": False, "error": "refresh_token required"})
                return
            validated = _zk.validate_session_token(sid)
            if not validated:
                self._json(401, {"ok": False, "error": "session_expired"})
                return
            use_secure = srv._session_cookie_secure()
            cookie_val = _zk.session_cookie_value(validated["session_id"], secure=use_secure)
            self._json(
                200,
                {
                    "ok": True,
                    "user_id": validated["user_id"],
                    "session_id": validated["session_id"],
                    "expires_at": validated["expires_at"],
                },
                extra_headers=[("Set-Cookie", cookie_val)],
            )
            return
        try:
            result = _zk.refresh_session(refresh_token)
        except ValueError as exc:
            self._json(401, {"ok": False, "error": str(exc)})
            return
        except (RuntimeError, OSError, sqlite3.Error) as exc:
            srv._log_handler_error("POST /api/auth/refresh", exc)
            self._json(500, {"ok": False, "error": str(exc)})
            return
        use_secure = srv._session_cookie_secure()
        cookie_val = _zk.session_cookie_value(result["session_id"], secure=use_secure)
        self._log_audit("session_refreshed", "session", result["session_id"],
                        f"user={result['user_id']}")
        self._json(
            200,
            {
                "ok": True,
                "user_id": result["user_id"],
                "session_id": result["session_id"],
                "refresh_token": result["refresh_token"],
                "expires_at": result["expires_at"],
            },
            extra_headers=[("Set-Cookie", cookie_val)],
        )

    def _route_get_auth_hermes_dashboard_gate(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        status = srv._hermes_dashboard_gate_status(self)
        if status == 204:
            self.send_response(204)
            self.end_headers()
            return
        self._json(403, {"ok": False, "error": "dashboard_forbidden"})

    def _route_get_auth_google_callback(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        code = (qs.get("code") or [""])[0]
        state = (qs.get("state") or [""])[0]
        if not code or not state:
            self._json(400, {"ok": False, "error": "missing code or state"})
            return
        try:
            profile = google_auth.exchange_google_code(code, state)
            invite_token = str(profile.get("invite_token") or "")
            allowed, deny_meta = srv._email_allowed_to_authenticate(profile["email"])
            if not allowed and not srv._invite_token_allows_email(invite_token, profile["email"]):
                self._log_audit(
                    "login_denied_private",
                    "user",
                    profile["email"],
                    str(deny_meta.get("error") or ""),
                )
                self._json(403, {"ok": False, **deny_meta})
                return
            result = _zk.create_session_for_email(profile["email"])
            self.auth_user = result["user_id"]
            self._ensure_user(
                result["user_id"],
                profile.get("display_name") or profile["email"],
                profile["email"],
            )
            invite_token = str(profile.get("invite_token") or "")
            use_secure = srv._session_cookie_secure()
            cookie_val = _zk.session_cookie_value(result["session_id"], secure=use_secure)
            redirect_to = f"{APP_BASE_URL.rstrip('/')}/onboarding"
            if invite_token:
                redirect_to = (
                    f"{APP_BASE_URL.rstrip('/')}/?invite_token="
                    f"{urllib.parse.quote(invite_token)}&email={urllib.parse.quote(profile['email'])}"
                )
            self.send_response(302)
            self.send_header("Location", redirect_to)
            self.send_header("Set-Cookie", cookie_val)
            cors_origin = srv._cors_origin_for(self.headers)
            if cors_origin:
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
        except (RuntimeError, OSError, ValueError) as exc:
            srv._log_handler_error("GET /api/auth/google/callback", exc)
            self._json(401, {"ok": False, "error": str(exc)})

    def _redirect_provider_connect(self, provider: str, *, ok: bool, message: str = "") -> None:
        status = "ok" if ok else "error"
        detail = message or ("connected" if ok else "failed")
        location = (
            f"{APP_BASE_URL.rstrip('/')}/?provider_connect={urllib.parse.quote(provider)}"
            f"&status={status}&message={urllib.parse.quote(detail)}"
        )
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def _route_get_oauth_github_callback(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._redirect_provider_connect("github", ok=False, message="no_session")
            return
        code = qs.get("code", [""])[0]
        state = qs.get("state", [""])[0]
        result = srv._complete_github_oauth(user_id, str(code or ""), str(state or ""))
        if result.get("ok"):
            self._redirect_provider_connect("github", ok=True)
            return
        self._redirect_provider_connect("github", ok=False, message=str(result.get("error") or "failed"))

    def _route_get_oauth_discord_callback(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._redirect_provider_connect("discord", ok=False, message="no_session")
            return
        code = qs.get("code", [""])[0]
        state = qs.get("state", [""])[0]
        result = srv._complete_discord_oauth(user_id, str(code or ""), str(state or ""))
        if result.get("ok"):
            self._redirect_provider_connect("discord", ok=True)
            return
        self._redirect_provider_connect("discord", ok=False, message=str(result.get("error") or "failed"))

    def _route_get_oauth_stripe_callback(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._redirect_provider_connect("stripe", ok=False, message="no_session")
            return
        code = qs.get("code", [""])[0]
        state = qs.get("state", [""])[0]
        result = srv._complete_stripe_oauth(user_id, str(code or ""), str(state or ""))
        if result.get("ok"):
            self._redirect_provider_connect("stripe", ok=True)
            return
        self._redirect_provider_connect("stripe", ok=False, message=str(result.get("error") or "failed"))

    def _route_get_me(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        payload = srv._session_profile_payload(user_id)
        if not payload:
            self._json(404, {"ok": False, "error": "user_not_found"})
            return
        self._json(200, payload)

    def _route_get_me_onboarding(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        self._json(200, srv._onboarding_payload(user_id))

    def _route_patch_me(self, body: dict) -> None:
        srv = _srv()
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        try:
            srv._apply_me_profile_updates(user_id, body)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        payload = srv._session_profile_payload(user_id)
        if not payload:
            self._json(404, {"ok": False, "error": "user_not_found"})
            return
        self._json(200, payload)

    def _route_patch_me_native_agent(self, body: dict) -> None:
        srv = _srv()
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        native_slug = str(srv.NATIVE_PROFILE or "workframe-agent")
        runtime = srv._runtime_profile_slug(user_id, native_slug)
        soul = (
            str(body.get("soul") or body.get("soul_md") or "").strip()
            if ("soul" in body or "soul_md" in body)
            else ""
        )
        display = str(body.get("display_name") or "").strip() if "display_name" in body else ""
        tagline = str(body.get("tagline") or "").strip() if "tagline" in body else ""
        srv._seed_native_user_overlay(
            runtime,
            native_slug,
            display_name=display,
            tagline=tagline,
            user_soul=soul,
        )
        profile_patch: dict[str, Any] = {}
        if display:
            profile_patch["display_name"] = display
        if tagline:
            profile_patch["tagline"] = tagline
        if profile_patch:
            srv._sync_agent_profile_db(native_slug, profile_patch)
        if "avatar_url" in body or "avatar_id" in body:
            avatar_patch = srv._normalize_agent_avatar_patch(
                str(body.get("avatar_url") or ""),
                str(body.get("avatar_id") or ""),
            )
            if avatar_patch.get("avatar_url") or avatar_patch.get("avatar_id"):
                stamp = datetime.now(timezone.utc).isoformat()
                row_patch = {**avatar_patch, "updated_at": stamp}
                srv._upsert_agent_registry_row(native_slug, row_patch)
                srv._upsert_agent_registry_row(runtime, row_patch)
                srv._sync_agent_profile_db(native_slug, {"avatar_url": avatar_patch.get("avatar_url", "")})
        self._json(200, {"ok": True, "runtime_profile": runtime})
