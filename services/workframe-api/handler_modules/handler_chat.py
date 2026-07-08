"""Chat / Hermes / room route handlers (WF-032 slice)."""

from __future__ import annotations

import json
import queue
import re
import sqlite3
import time
import urllib.parse
import uuid
from typing import Any

import activity_feed
import chat_bind
import chat_sessions
import chat_stream
import hermes_admin
import hermes_profiles
import lane_bindings
import mention_helpers
import model_surface
import profile_gateway
import workspace_bootstrap
from api_meta import hermes_bootstrap, hermes_skills

chat_bootstrap = chat_sessions.chat_bootstrap
chat_messages = chat_sessions.chat_messages
chat_session = chat_sessions.chat_session
chat_resolve = lane_bindings.chat_resolve
chat_dispatch = lane_bindings.chat_dispatch
hermes_commands_catalog = hermes_admin.hermes_commands_catalog
hermes_commands_exec = hermes_admin.hermes_commands_exec
hermes_usage = hermes_admin.hermes_usage
hermes_profile = hermes_admin.hermes_profile
hermes_debug = hermes_admin.hermes_debug
hermes_insights = hermes_admin.hermes_insights
hermes_gquota = hermes_admin.hermes_gquota
hermes_models = model_surface.hermes_models
hermes_model_set = model_surface.hermes_model_set
hermes_apply_default_model_config = model_surface.hermes_apply_default_model_config
hermes_fallback_chain_set = model_surface.hermes_fallback_chain_set
hermes_gateway_exec = hermes_admin.hermes_gateway_exec
hermes_profile_detail = hermes_admin.hermes_profile_detail
hermes_profile_update = hermes_admin.hermes_profile_update
profile_gateway_stop = profile_gateway.profile_gateway_stop
profile_gateway_steer = profile_gateway.profile_gateway_steer
profile_gateway_lifecycle = profile_gateway.profile_gateway_lifecycle
profile_create = hermes_profiles.profile_create
profile_delete = hermes_profiles.profile_delete
profile_soul_get = hermes_admin.profile_soul_get
profile_soul_set = hermes_admin.profile_soul_set
resolve_hermes_profile = hermes_profiles.resolve_hermes_profile
resolve_validated_profile = hermes_profiles.resolve_validated_profile
profile_chat_session = lane_bindings.profile_chat_session
profile_chat_bind = chat_bind.profile_chat_bind
profile_chat_message = chat_bind.profile_chat_message
profile_chat_activate_room_session = chat_bind.profile_chat_activate_room_session
room_chat_bind = chat_bind.room_chat_bind
_enrich_room_chat_payload = chat_bind._enrich_room_chat_payload
stream_profile_chat = chat_stream.stream_profile_chat
list_room_sessions = chat_bind.list_room_sessions
room_activity_data = activity_feed.room_activity_data
bootstrap_agent_dm_lane = workspace_bootstrap.bootstrap_agent_dm_lane
_process_space_message_mentions = mention_helpers.process_space_message_mentions


def _srv():
    import server

    return server


class ChatRoutesMixin:
    _HERMES_PROFILE_RESERVED = frozenset({"status", "create", "start", "stop", "delete", "disable"})

    def _route_get_chat_messages(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        profile = resolve_hermes_profile(qs.get("profile", [""])[0] or srv._primary_profile())
        session = qs.get("session", [""])[0]
        source_id = qs.get("source", ["ui"])[0]
        self._json(200, chat_messages(profile, session, source_id))


    def _route_get_chat_session(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        profile = resolve_hermes_profile(qs.get("profile", [""])[0] or srv._primary_profile())
        session = qs.get("session", [""])[0]
        source_id = qs.get("source", ["ui"])[0]
        self._json(200, chat_session(profile, session, source_id))


    def _route_get_chat_resolve(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        profile = resolve_validated_profile(qs.get("profile", [""])[0] or srv._primary_profile())
        source_id = qs.get("source", ["ui"])[0]
        client_id = qs.get("client", ["default"])[0]
        self._json(
            200,
            chat_resolve({"profile": profile, "source_id": source_id, "client_id": client_id}),
        )


    def _route_get_hermes_skills(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, {"skills": hermes_skills()})


    def _route_get_hermes_commands(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, hermes_commands_catalog())


    def _route_get_hermes_usage(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, hermes_usage())


    def _route_get_hermes_profile(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, hermes_profile())


    def _route_get_hermes_models(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        profile = qs.get("profile", [""])[0]
        user_id = str(getattr(self, "auth_user", "") or "")
        workspace_id = qs.get("workspace_id", [""])[0]
        selection_only = qs.get("selection_only", ["0"])[0] in {"1", "true", "yes"}
        payload = hermes_models(profile, user_id, workspace_id, selection_only=selection_only)
        status = 200 if payload.get("ok", True) else 400
        self._json(status, payload)


    def _route_get_hermes_debug(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, hermes_debug())


    def _route_get_hermes_insights(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, hermes_insights())


    def _route_get_hermes_gquota(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        self._json(200, hermes_gquota())

    # WF-037 auth-flow + hermes/chat + me credentials POST handlers

    def _route_post_hermes_commands_exec(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        line = str(body.get("line", "")).strip()
        if not line:
            self._json(400, {"error": "line required"})
            return
        self._json(200, hermes_commands_exec(line))


    def _route_post_hermes_gateway_exec(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        line = str(body.get("line", "")).strip()
        profile = str(body.get("profile", "")).strip()
        if not line:
            self._json(400, {"error": "line required"})
            return
        user_id = str(getattr(self, "auth_user", "") or "")
        workspace_id = str(body.get("workspace_id", "") or "")
        self._json(
            200,
            hermes_gateway_exec(line, profile, user_id=user_id, workspace_id=workspace_id),
        )


    def _route_post_chat_stop(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        profile = resolve_validated_profile(str(body.get("profile") or srv._primary_profile()))
        run_id = str(body.get("run_id") or "").strip()
        if not run_id:
            run_id = srv._latest_active_run_id(profile)
        if not run_id:
            self._json(400, {"error": "no active run to stop"})
            return
        self._json(200, profile_gateway_stop(profile, run_id))


    def _route_post_chat_steer(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        profile = resolve_validated_profile(str(body.get("profile") or srv._primary_profile()))
        run_id = str(body.get("run_id") or "").strip()
        text = str(body.get("text") or "").strip()
        if not text:
            self._json(400, {"error": "text required"})
            return
        if not run_id:
            run_id = srv._latest_active_run_id(profile)
        self._json(200, profile_gateway_steer(profile, run_id or "", text))


    def _route_post_hermes_model(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        model_id = str(body.get("model", "")).strip()
        profile = str(body.get("profile", "")).strip()
        user_id = str(getattr(self, "auth_user", "") or "")
        workspace_id = str(body.get("workspace_id", "")).strip()
        selection_only = bool(body.get("selection_only"))
        if not model_id:
            self._json(400, {"error": "model required"})
            return
        billing_provider = str(body.get("billing_provider", "")).strip()
        self._json(
            200,
            hermes_model_set(
                profile,
                model_id,
                user_id,
                workspace_id,
                selection_only=selection_only,
                billing_provider=billing_provider,
            ),
        )


    def _route_post_hermes_model_apply_default(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        self._json(200, hermes_apply_default_model_config())


    def _route_post_hermes_fallback_chain(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        profile = str(body.get("profile", "")).strip()
        chain = body.get("chain", [])
        selection_only = bool(body.get("selection_only"))
        user_id = str(getattr(self, "auth_user", "") or "")
        if not isinstance(chain, list):
            self._json(400, {"error": "chain must be a list"})
            return
        if not selection_only and not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        self._json(
            200,
            hermes_fallback_chain_set(
                profile,
                chain,
                selection_only=selection_only,
                user_id=user_id,
            ),
        )


    def _route_post_chat_dispatch(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        self._json(200, chat_dispatch(body))

    # WF-037 admin/install/oauth GET handlers (batch 2)

    def _route_get_chat_bootstrap(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        profile = resolve_validated_profile(qs.get("profile", [""])[0] or srv._primary_profile())
        persistent = qs.get("persistent", [""])[0]
        source_id = qs.get("source", ["ui"])[0]
        self._json(200, chat_bootstrap(profile, persistent, source_id))


    def _route_get_hermes_bootstrap(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        self._json(200, hermes_bootstrap())


    def _route_get_hermes_profiles_status(self, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        profile = resolve_validated_profile(qs.get("profile", [""])[0] or srv._primary_profile())
        if srv.SUPERVISOR_URL:
            self._json(
                *srv._supervisor_request(
                    "GET",
                    f"/v1/profile.status?profile={urllib.parse.quote(profile, safe='')}",
                    timeout=10.0,
                )
            )
            return
        self._json(200, profile_gateway_lifecycle(profile, "status"))








    def _route_pattern_get_hermes_profile_soul(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        profile_soul_match = re.fullmatch(r"/api/hermes/profiles/([^/]+)/soul", path)
        if not profile_soul_match:
            self._json(404, {"error": "not found"})
            return
        profile = resolve_validated_profile(profile_soul_match.group(1))
        self._json(200, profile_soul_get(profile))


    def _route_pattern_get_hermes_profile_detail(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        profile_detail_match = re.fullmatch(r"/api/hermes/profiles/([^/]+)", path)
        if not profile_detail_match or profile_detail_match.group(1) in self._HERMES_PROFILE_RESERVED:
            self._json(404, {"error": "not found"})
            return
        profile = resolve_validated_profile(profile_detail_match.group(1))
        ws_id = ""
        user_id = str(getattr(self, "auth_user", "") or "")
        if user_id:
            try:
                conn = srv._workframe_db()
                row = conn.execute(
                    """
                    SELECT workspace_id FROM workspace_memberships
                    WHERE user_id = ? AND status = 'active' AND deleted_at IS NULL
                    ORDER BY created_at ASC LIMIT 1
                    """,
                    (user_id,),
                ).fetchone()
                conn.close()
                if row:
                    ws_id = str(row["workspace_id"])
            except sqlite3.Error:
                pass
        self._json(200, hermes_profile_detail(profile, ws_id))


    def _route_pattern_get_hermes_profile_sessions(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) < 5:
            self._json(404, {"error": "not found"})
            return
        profile_raw = urllib.parse.unquote(parts[3])
        source_id = qs.get("source", ["ui"])[0]
        client_id = qs.get("client", ["default"])[0]
        self._json(
            200,
            profile_chat_session(
                profile_raw,
                {"source_id": source_id, "client_id": client_id, "new_session": False},
            ),
        )


    def _route_pattern_get_hermes_profile_bind(self, path: str, qs: dict[str, list[str]]) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) < 5:
            self._json(404, {"error": "not found"})
            return
        profile_raw = urllib.parse.unquote(parts[3])
        source_id = qs.get("source", ["ui"])[0]
        client_id = qs.get("client", ["default"])[0]
        self._json(
            200,
            profile_chat_bind(
                profile_raw,
                {"source_id": source_id, "client_id": client_id, "new_session": False},
            ),
        )










    def _route_post_hermes_profiles_create(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not srv._handler_is_active_workspace_member(self):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "workspace_member"})
            return
        name = str(body.get("name") or "").strip()
        if not name:
            self._json(400, {"error": "name required"})
            return
        model = str(body.get("model") or "").strip()
        description = str(body.get("description") or "").strip()
        clone_from = str(body.get("clone_from") or "").strip()
        soul = str(body.get("soul") or "").strip()
        display_name = str(body.get("display_name") or "").strip()
        role = str(body.get("role") or "").strip()
        tagline = str(body.get("tagline") or "").strip()
        avatar_url = str(body.get("avatar_url") or "").strip()
        avatar_id = str(body.get("avatar_id") or "").strip()
        user_id = str(getattr(self, "auth_user", "") or "").strip()
        workspace_id = str(body.get("workspace_id") or "").strip()
        if not workspace_id and user_id:
            workspaces = srv._get_user_workspaces(user_id)
            current = srv._resolve_current_workspace(user_id, workspaces)
            workspace_id = str((current or {}).get("id") or (workspaces[0] or {}).get("id") or "")
        self._json(
            200,
            profile_create(
                name,
                model,
                description,
                clone_from,
                soul,
                display_name,
                role,
                tagline,
                avatar_url,
                avatar_id,
                user_id=user_id,
                workspace_id=workspace_id,
            ),
        )


    def _route_post_hermes_profiles_start(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        profile = resolve_validated_profile(str(body.get("profile") or srv._primary_profile()))
        if srv.SUPERVISOR_URL:
            self._json(*srv._supervisor_request("POST", "/v1/profile.start", body))
            return
        self._json(200, profile_gateway_lifecycle(profile, "start"))


    def _route_post_hermes_profiles_stop(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        profile = resolve_validated_profile(str(body.get("profile") or srv._primary_profile()))
        if srv.SUPERVISOR_URL:
            self._json(*srv._supervisor_request("POST", "/v1/profile.stop", body))
            return
        self._json(200, profile_gateway_lifecycle(profile, "stop"))


    def _route_post_hermes_profiles_delete(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        profile = str(body.get("profile") or "").strip()
        if not profile:
            self._json(400, {"error": "profile required"})
            return
        self._json(200, profile_delete(profile))


    def _route_post_hermes_profiles_disable(self, body: dict) -> None:
        srv = _srv()
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        profile = resolve_validated_profile(str(body.get("profile") or srv._primary_profile()))
        if srv.SUPERVISOR_URL:
            self._json(*srv._supervisor_request("POST", "/v1/profile.disable", body))
            return
        self._json(200, profile_gateway_lifecycle(profile, "disable"))


    def _route_pattern_post_hermes_profile_bootstrap_dm(self, path: str, body: dict) -> None:
        srv = _srv()
        profile_bootstrap_post = re.fullmatch(r"/api/hermes/profiles/([^/]+)/bootstrap-dm", path)
        if not profile_bootstrap_post:
            self._json(404, {"error": "not found"})
            return
        if not srv._check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not srv._handler_is_active_workspace_member(self):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "workspace_member"})
            return
        template = resolve_validated_profile(profile_bootstrap_post.group(1))
        user_id = str(getattr(self, "auth_user", "") or "").strip()
        workspace_id = str(body.get("workspace_id") or "").strip()
        if not workspace_id and user_id:
            workspaces = srv._get_user_workspaces(user_id)
            current = srv._resolve_current_workspace(user_id, workspaces)
            workspace_id = str((current or {}).get("id") or (workspaces[0] or {}).get("id") or "")
        if not user_id or not workspace_id:
            self._json(400, {"error": "workspace_id and session required"})
            return
        model = str(body.get("model") or "").strip()
        soul = str(body.get("soul") or "").strip()
        display_name = str(body.get("display_name") or body.get("room_name") or "").strip()
        role = str(body.get("role") or "").strip()
        tagline = str(body.get("tagline") or "").strip()
        lane = bootstrap_agent_dm_lane(
            user_id,
            workspace_id,
            template,
            model=model,
            soul=soul,
            bind_session=bool(body.get("bind_session", True)),
            room_name=display_name or str(body.get("room_name") or "").strip(),
            role=role,
            tagline=tagline,
            created_by=user_id,
        )
        status = 200 if lane.get("ok") else 500
        self._json(status, lane)


    def _route_pattern_post_hermes_profile_soul(self, path: str, body: dict) -> None:
        srv = _srv()
        profile_soul_post = re.fullmatch(r"/api/hermes/profiles/([^/]+)/soul", path)
        if not profile_soul_post:
            self._json(404, {"error": "not found"})
            return
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        profile = resolve_validated_profile(profile_soul_post.group(1))
        soul = str(body.get("soul", body.get("text", "")))
        self._json(200, profile_soul_set(profile, soul))


    def _route_pattern_post_hermes_profile_bind(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) < 5:
            self._json(404, {"error": "not found"})
            return
        profile_raw = urllib.parse.unquote(parts[3])
        user_id = str(getattr(self, "auth_user", "") or "")
        self._json(200, profile_chat_bind(profile_raw, body, user_id))


    def _route_pattern_post_hermes_profile_sessions(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) < 5:
            self._json(404, {"error": "not found"})
            return
        profile_raw = urllib.parse.unquote(parts[3])
        user_id = str(getattr(self, "auth_user", "") or "")
        self._json(200, profile_chat_session(profile_raw, body, user_id))


    def _route_pattern_post_hermes_profile_messages(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) < 5:
            self._json(404, {"error": "not found"})
            return
        profile_raw = urllib.parse.unquote(parts[3])
        stream_body = _enrich_room_chat_payload(body, str(getattr(self, "auth_user", "") or ""))
        self._json(200, profile_chat_message(profile_raw, stream_body))


    def _route_pattern_post_hermes_profile_messages_stream(self, path: str, body: dict) -> None:
        srv = _srv()
        parts = path.strip("/").split("/")
        if len(parts) < 6:
            self._json(404, {"error": "not found"})
            return
        profile_raw = urllib.parse.unquote(parts[3])
        stream_body = _enrich_room_chat_payload(body, str(getattr(self, "auth_user", "") or ""))
        stream_profile_chat(self, profile_raw, stream_body)


















    def _route_pattern_patch_hermes_profile(self, path: str, body: dict) -> None:
        srv = _srv()
        profile_patch_match = re.fullmatch(r"/api/hermes/profiles/([^/]+)", path)
        if not profile_patch_match or profile_patch_match.group(1) in self._HERMES_PROFILE_RESERVED:
            self._json(404, {"error": "not found"})
            return
        if not srv._role_allows(self, srv.OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        profile = resolve_validated_profile(profile_patch_match.group(1))
        self._json(200, hermes_profile_update(profile, body))

