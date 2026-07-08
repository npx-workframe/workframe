#!/usr/bin/env python3
"""
Workframe API - fast Hermes-native backend for Workframe UI.

Hermes stores (read-only): state.db, kanban.db, gateway_state.json, cron/jobs.json
Local stores: board.db (optional operator tasks), Files/ workspace (/workspace)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import queue
import re
import secrets
import shlex
import sqlite3
import shutil
import signal
import socket
import threading
import time
import urllib.parse
import uuid
import urllib.request
import http.client
import urllib.error
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

from email_sender import APP_BASE_URL, send_branded_invite_email, send_email, send_verification_email
import profile_config_yaml
import route_registry
import db_schema

WORKFRAME_DB_SCHEMA = db_schema.WORKFRAME_DB_SCHEMA
_migrate_v6_space_rooms = db_schema._migrate_v6_space_rooms
_migrate_v7_space_agent_members = db_schema._migrate_v7_space_agent_members
_migrate_v8_room_avatars = db_schema._migrate_v8_room_avatars
_migrate_v9_workspace_avatars = db_schema._migrate_v9_workspace_avatars
_migrate_v10_workspace_settings_oauth = db_schema._migrate_v10_workspace_settings_oauth
_migrate_v11_delegation_kanban_boards = db_schema._migrate_v11_delegation_kanban_boards
_migrate_v12_adopt_install_keys_to_owners = db_schema._migrate_v12_adopt_install_keys_to_owners
_migrate_v13_workspace_members_in_spaces = db_schema._migrate_v13_workspace_members_in_spaces

import auth_gate
import user_prefs
import rooms
import kanban_cron
import hermes_profiles
import profile_gateway
import profile_api_lifecycle
import model_surface
import provider_bootstrap
import chat_stream
import lane_bindings
import workspace_files
import run_surface_wiring

# WF-032: workspace_files re-exports
TREE_SKIP_NAMES = workspace_files.TREE_SKIP_NAMES
PROTECTED_WORKSPACE_FILE_NAMES = workspace_files.PROTECTED_WORKSPACE_FILE_NAMES
PROTECTED_PROFILE_CONFIG_FILE_NAMES = workspace_files.PROTECTED_PROFILE_CONFIG_FILE_NAMES
_workspace_state_lock = workspace_files._workspace_state_lock
_workspace_state_cache = workspace_files._workspace_state_cache
_workspace_tree_lock = workspace_files._workspace_tree_lock
_workspace_tree_cache = workspace_files._workspace_tree_cache
_safe_workspace_path = workspace_files.safe_workspace_path
_safe_content_path = workspace_files.safe_content_path
_workspace_protected_reason = workspace_files.workspace_protected_reason
files_tree = workspace_files.files_tree
files_list = workspace_files.files_list
workspace_state = workspace_files.workspace_state
_bump_workspace_state = workspace_files.bump_workspace_state
_workspace_state_daemon = workspace_files.workspace_state_daemon
file_read = workspace_files.file_read
file_write = workspace_files.file_write
file_upload_binary = workspace_files.file_upload_binary
file_raw = workspace_files.file_raw

import activity_feed

ACTIVITY_ROOM_LIMIT = activity_feed.ACTIVITY_ROOM_LIMIT
ACTIVITY_WORKSPACE_LIMIT = activity_feed.ACTIVITY_WORKSPACE_LIMIT
_crew_lookup = activity_feed._crew_lookup
_resolve_agent = activity_feed._resolve_agent
_tool_call_label = activity_feed._tool_call_label
_message_activity = activity_feed._message_activity
_session_activity = activity_feed._session_activity
_kanban_activity = activity_feed._kanban_activity
activity_data = activity_feed.activity_data
activity_detail = activity_feed.activity_detail
_message_activity_for_sessions = activity_feed._message_activity_for_sessions
room_activity_data = activity_feed.room_activity_data
workspace_activity_data = activity_feed.workspace_activity_data

import crew_registry
import runtime_cohort
import health_monitor
import snapshot_feed
import doctor_runtime
import api_meta

CREW_COLORS = crew_registry.CREW_COLORS
load_agent_registry = crew_registry.load_agent_registry
_agent_registry_row = crew_registry._agent_registry_row
_workspace_agent_identities = crew_registry._workspace_agent_identities
_agent_identity_fields = crew_registry._agent_identity_fields
_gateway_platform = crew_registry._gateway_platform
crew_data = crew_registry.crew_data
_workspace_crew_profile_names = crew_registry._workspace_crew_profile_names
workframe_agents = crew_registry.workframe_agents

# WF-032: runtime_cohort re-exports
_runtime_profile_slug = runtime_cohort._runtime_profile_slug
_prepare_runtime_profile_credentials = runtime_cohort._prepare_runtime_profile_credentials
_resolve_runtime_owner = runtime_cohort._resolve_runtime_owner
_user_handle = runtime_cohort._user_handle
_user_owner_name = runtime_cohort._user_owner_name
_runtime_display_label = runtime_cohort._runtime_display_label
_cohort_alias = runtime_cohort._cohort_alias
resolve_runtime_assignee = runtime_cohort.resolve_runtime_assignee
_user_id_for_runtime_slug = runtime_cohort._user_id_for_runtime_slug
cohort_runtime_slugs = runtime_cohort.cohort_runtime_slugs
_user_is_workspace_member = runtime_cohort._user_is_workspace_member
_delegation_grantor_ids_for_grantee = runtime_cohort._delegation_grantor_ids_for_grantee
_delegation_grant_payload = runtime_cohort._delegation_grant_payload
list_delegation_grants = runtime_cohort.list_delegation_grants
create_delegation_grant = runtime_cohort.create_delegation_grant
revoke_delegation_grant = runtime_cohort.revoke_delegation_grant
_allowed_runtime_profiles_for_workspace = runtime_cohort._allowed_runtime_profiles_for_workspace
purge_stale_runtime_profiles = runtime_cohort.purge_stale_runtime_profiles
_cohort_manifest_markdown = runtime_cohort._cohort_manifest_markdown
_write_workframe_cohort_manifest = runtime_cohort._write_workframe_cohort_manifest
ensure_user_agent_cohort = runtime_cohort.ensure_user_agent_cohort
_runtime_gateway_registered = runtime_cohort._runtime_gateway_registered
_invalidate_gateway_registered_cache = runtime_cohort._invalidate_gateway_registered_cache
_runtime_profile_on_disk = runtime_cohort._runtime_profile_on_disk
_runtime_profile_ready = runtime_cohort._runtime_profile_ready
_purge_runtime_profile = runtime_cohort._purge_runtime_profile
_register_runtime_profile = runtime_cohort._register_runtime_profile
_inherit_runtime_profile_config = runtime_cohort._inherit_runtime_profile_config
ensure_runtime_profile = runtime_cohort.ensure_runtime_profile

health_data = health_monitor.health_data
build_snapshot = snapshot_feed.build_snapshot
doctor_audit_agent_dm_runtimes = doctor_runtime.doctor_audit_agent_dm_runtimes
doctor_repair_agent_dm_runtimes = doctor_runtime.doctor_repair_agent_dm_runtimes
workframe_meta = api_meta.workframe_meta
hermes_bootstrap = api_meta.hermes_bootstrap
hermes_skills = api_meta.hermes_skills
_hermes_dashboard_gate_status = api_meta.hermes_dashboard_gate_status

# WF-032: lane_bindings re-exports
_load_lane_registry = lane_bindings._load_lane_registry
_save_lane_registry = lane_bindings._save_lane_registry
_binding_version = lane_bindings._binding_version
_binding_row_for = lane_bindings._binding_row_for
_binding_session_for = lane_bindings._binding_session_for
profile_chat_session = lane_bindings.profile_chat_session
_sync_lane_binding = lane_bindings._sync_lane_binding
_source_binding_key = lane_bindings._source_binding_key
_registry_profile_bucket = lane_bindings._registry_profile_bucket
chat_resolve = lane_bindings.chat_resolve
chat_dispatch = lane_bindings.chat_dispatch


# WF-032: chat_stream re-exports
_live_stream_text = chat_stream._live_stream_text
_live_strip_placeholders = chat_stream._live_strip_placeholders
_live_reduce_stream_event = chat_stream._live_reduce_stream_event
_segments_to_reply_text = chat_stream._segments_to_reply_text
_parse_profile_stream_frame = chat_stream._parse_profile_stream_frame
_iter_profile_stream_frames = chat_stream._iter_profile_stream_frames
_emit_stream_chat_error = chat_stream._emit_stream_chat_error
_open_profile_stream = chat_stream._open_profile_stream
_emit_stream_error_body = chat_stream._emit_stream_error_body
_emit_stream_concierge = chat_stream._emit_stream_concierge
_log_llm_failure = chat_stream._log_llm_failure
_run_authority_context_for_chat = chat_stream._run_authority_context_for_chat
stream_profile_chat = chat_stream.stream_profile_chat


def _log_handler_error(route: str, exc: BaseException) -> None:
    """WF-035: stderr context for auth/vault/provider-sync handler failures."""
    print(f"workframe-api [{route}] {type(exc).__name__}: {exc}", file=sys.stderr)


# WF-032: provider_bootstrap re-exports
_load_profile_auth_json = provider_bootstrap._load_profile_auth_json
_provider_pool_entry = provider_bootstrap._provider_pool_entry
_runtime_provider_pool_entry = provider_bootstrap._runtime_provider_pool_entry
_provider_pool_has_entries = provider_bootstrap._provider_pool_has_entries
_connected_provider_names = provider_bootstrap._connected_provider_names
_user_llm_providers_for_picker = provider_bootstrap._user_llm_providers_for_picker
_user_has_llm_provider = provider_bootstrap._user_has_llm_provider
_user_llm_has_provider = provider_bootstrap._user_llm_has_provider
_workspace_has_llm_provider = provider_bootstrap._workspace_has_llm_provider
_user_can_use_llm = provider_bootstrap._user_can_use_llm
_overlay_chat_llm_env = provider_bootstrap._overlay_chat_llm_env
_reconcile_profile_llm_for_user = provider_bootstrap._reconcile_profile_llm_for_user
_ensure_profile_auth_pool = provider_bootstrap._ensure_profile_auth_pool
_bootstrap_profile_providers = provider_bootstrap._bootstrap_profile_providers


# WF-032: model_surface re-exports
_resolve_models_profile = model_surface._resolve_models_profile
_model_suggestion_row = model_surface._model_suggestion_row
_augment_model_suggestions = model_surface._augment_model_suggestions
_billing_provider_from_block = model_surface._billing_provider_from_block
_llm_billing_provider = model_surface._llm_billing_provider
_profile_llm_proxy_matches_billing = model_surface._profile_llm_proxy_matches_billing
_profile_routing_matches_billing = model_surface._profile_routing_matches_billing
_billing_provider_id_from_hermes_config = model_surface._billing_provider_id_from_hermes_config
_catalog_tags_for_billing_provider = model_surface._catalog_tags_for_billing_provider
_catalog_row_for_billing_provider = model_surface._catalog_row_for_billing_provider
_provider_display_label = model_surface._provider_display_label
_model_catalog_rows_for_provider = model_surface._model_catalog_rows_for_provider
_suggestions_for_connected_llm_providers = model_surface._suggestions_for_connected_llm_providers
_model_id_vendor_and_bare = model_surface._model_id_vendor_and_bare
_persisted_model_id = model_surface._persisted_model_id
_apply_model_persisted = model_surface._apply_model_persisted
_mirror_template_model_to_runtime = model_surface._mirror_template_model_to_runtime
_resolve_billing_provider_for_model = model_surface._resolve_billing_provider_for_model
_strip_profile_model_proxy_fields = model_surface._strip_profile_model_proxy_fields
_apply_model_for_billing_provider = model_surface._apply_model_for_billing_provider
_hermes_config_provider_id = model_surface._hermes_config_provider_id
_first_connected_llm_provider = model_surface._first_connected_llm_provider
_apply_mvp_model_for_provider = model_surface._apply_mvp_model_for_provider
_bootstrap_model_after_llm_connect = model_surface._bootstrap_model_after_llm_connect
_set_profile_model = model_surface._set_profile_model
_set_profile_model_provider = model_surface._set_profile_model_provider
_parse_model_block_from_disk = model_surface._parse_model_block_from_disk
_read_model_block = model_surface._read_model_block
_sync_runtime_model_from_template = model_surface._sync_runtime_model_from_template
_write_fallback_chain = model_surface._write_fallback_chain
hermes_models = model_surface.hermes_models
hermes_apply_default_model_config = model_surface.hermes_apply_default_model_config
hermes_model_set = model_surface.hermes_model_set
hermes_fallback_chain_set = model_surface.hermes_fallback_chain_set
HERMES_DEFAULT_PRIMARY = model_surface.HERMES_DEFAULT_PRIMARY
HERMES_DEFAULT_FALLBACK_CHAIN = model_surface.HERMES_DEFAULT_FALLBACK_CHAIN
PROVIDER_MVP_MODELS = model_surface.PROVIDER_MVP_MODELS


# WF-032: profile_gateway re-exports
_reload_runtime_profile_gateway = profile_gateway._reload_runtime_profile_gateway
_schedule_gateway_reload = profile_gateway._schedule_gateway_reload
_restart_runtime_profile_gateway = profile_gateway._restart_runtime_profile_gateway
_profile_api_port = profile_gateway._profile_api_port
_configure_profile_api = profile_gateway._configure_profile_api
_patch_profile_gateway_run_script = profile_gateway._patch_profile_gateway_run_script
_disable_profile = profile_gateway._disable_profile
profile_gateway_lifecycle = profile_gateway.profile_gateway_lifecycle
_profile_api_key = profile_gateway._profile_api_key
_profile_turn_payload = profile_gateway._profile_turn_payload
_profile_api_request = profile_gateway._profile_api_request
_is_transient_profile_api_error = profile_gateway._is_transient_profile_api_error
_profile_api_healthy = profile_gateway._profile_api_healthy
_wait_profile_api_healthy = profile_gateway._wait_profile_api_healthy
profile_gateway_stop = profile_gateway.profile_gateway_stop
profile_gateway_steer = profile_gateway.profile_gateway_steer

# WF-032: profile_api_lifecycle re-exports
ensure_profile_api = profile_api_lifecycle.ensure_profile_api


_AGENT_PROFILE_UUID_RE = rooms._AGENT_PROFILE_UUID_RE

# WF-032: hermes_profiles re-exports
_list_profiles = hermes_profiles._list_profiles
_native_profile_slug = hermes_profiles._native_profile_slug
_native_profile_present = hermes_profiles._native_profile_present
_hermes_data_uid_gid = hermes_profiles._hermes_data_uid_gid
_chown_profile_tree = hermes_profiles._chown_profile_tree
_seed_native_profile_on_disk = hermes_profiles._seed_native_profile_on_disk
_ensure_native_hermes_profile = hermes_profiles._ensure_native_hermes_profile
_primary_profile = hermes_profiles._primary_profile
_profile_dir = hermes_profiles._profile_dir
_profile_gateway_config_path = hermes_profiles._profile_gateway_config_path
_ensure_gateway_config_file = hermes_profiles._ensure_gateway_config_file
_fix_invalid_model_header = hermes_profiles._fix_invalid_model_header
_scrub_orphan_top_level_yaml_lines = hermes_profiles._scrub_orphan_top_level_yaml_lines
_fix_model_child_indent = hermes_profiles._fix_model_child_indent
_normalize_profile_config_yaml = hermes_profiles._normalize_profile_config_yaml
_parse_model_fields_from_yaml = hermes_profiles._parse_model_fields_from_yaml
_profile_config_path = hermes_profiles._profile_config_path
_profile_home = hermes_profiles._profile_home
_render_soul_placeholders = hermes_profiles._render_soul_placeholders
_soul_is_stub = hermes_profiles._soul_is_stub
_format_child_template = hermes_profiles._format_child_template
_soul_is_native_concierge = hermes_profiles._soul_is_native_concierge
_strip_forbidden_child_skills = hermes_profiles._strip_forbidden_child_skills
_seed_native_user_overlay = hermes_profiles._seed_native_user_overlay
_apply_profile_identity = hermes_profiles._apply_profile_identity
_profile_identity_overlay = hermes_profiles._profile_identity_overlay
_install_child_base_artifacts = hermes_profiles._install_child_base_artifacts
_profile_base_soul_text = hermes_profiles._profile_base_soul_text
_profile_soul_text = hermes_profiles._profile_soul_text
_write_profile_soul_if_stub = hermes_profiles._write_profile_soul_if_stub
_profile_soul_path = hermes_profiles._profile_soul_path
_profile_soul_raw = hermes_profiles._profile_soul_raw
_file_size_mb = hermes_profiles._file_size_mb
gateway_data = hermes_profiles.gateway_data
sessions_data = hermes_profiles.sessions_data
_profile_slug = hermes_profiles._profile_slug
_agent_label = hermes_profiles._agent_label
_native_display_name = hermes_profiles._native_display_name
_is_native_profile = hermes_profiles._is_native_profile
_agent_db_display_name = hermes_profiles._agent_db_display_name
_profile_display_name = hermes_profiles._profile_display_name
_default_session_title = hermes_profiles._default_session_title
_create_profile_session_via_api = hermes_profiles._create_profile_session_via_api
_profile_role = hermes_profiles._profile_role
_profile_code = hermes_profiles._profile_code
safe_profile_slug = hermes_profiles.safe_profile_slug
profile_exists = hermes_profiles.profile_exists
route_status_for_profile = hermes_profiles.route_status_for_profile
_register_profile_route = hermes_profiles._register_profile_route
_route_record = hermes_profiles._route_record
load_routes = hermes_profiles.load_routes
resolve_validated_profile = hermes_profiles.resolve_validated_profile
_is_runtime_profile_slug = hermes_profiles._is_runtime_profile_slug
_runtime_template_slug = hermes_profiles._runtime_template_slug
_chat_toolsets_for_profile = hermes_profiles._chat_toolsets_for_profile
_ensure_profile_toolsets = hermes_profiles._ensure_profile_toolsets
resolve_hermes_profile = hermes_profiles.resolve_hermes_profile
profile_create = hermes_profiles.profile_create
profile_delete = hermes_profiles.profile_delete


# WF-032: kanban_cron re-exports
_iter_kanban_dbs = kanban_cron._iter_kanban_dbs
_refresh_active_kanban_assignee_credentials = kanban_cron._refresh_active_kanban_assignee_credentials
_kanban_credential_guard_daemon = kanban_cron._kanban_credential_guard_daemon
validate_kanban_assignee = kanban_cron.validate_kanban_assignee
_hermes_kanban_db_path = kanban_cron._hermes_kanban_db_path
_workspace_kanban_board_row = kanban_cron._workspace_kanban_board_row
ensure_workspace_kanban_board = kanban_cron.ensure_workspace_kanban_board
kanban_proxy_list_tasks = kanban_cron.kanban_proxy_list_tasks
kanban_proxy_create_task = kanban_cron.kanban_proxy_create_task
_cron_plain_english = kanban_cron._cron_plain_english
kanban_data = kanban_cron.kanban_data
_hermes_cron_jobs = kanban_cron._hermes_cron_jobs
_system_cron_jobs = kanban_cron._system_cron_jobs
cron_data = kanban_cron.cron_data


# WF-032: rooms re-exports
_room_live_subscribe = rooms._room_live_subscribe
_room_live_unsubscribe = rooms._room_live_unsubscribe
_room_live_publish = rooms._room_live_publish
_room_live_set_turn = rooms._room_live_set_turn
_room_live_clear_turn = rooms._room_live_clear_turn
_room_live_active_for_room = rooms._room_live_active_for_room
_room_payload = rooms._room_payload
_sanitize_space_room_agent_fields = rooms._sanitize_space_room_agent_fields
_workspace_payload = rooms._workspace_payload
_normalize_room_slug = rooms._normalize_room_slug
_parse_room_platform_ids = rooms._parse_room_platform_ids
_resolve_wid = rooms._resolve_wid
_workspace_exists = rooms._workspace_exists
_workspace_member_payload = rooms._workspace_member_payload
_workspace_member_lookup_sql = rooms._workspace_member_lookup_sql
_workspace_member_role = rooms._workspace_member_role
_resolve_workspace_integrations_role = rooms._resolve_workspace_integrations_role
_can_read_workspace_members = rooms._can_read_workspace_members
_can_manage_workspace_members = rooms._can_manage_workspace_members
_list_workspace_members = rooms._list_workspace_members
_active_owner_count = rooms._active_owner_count
_workspace_membership_update_payload = rooms._workspace_membership_update_payload
_patch_workspace_members = rooms._patch_workspace_members
_lookup_agent_profile = rooms._lookup_agent_profile
_hermes_slug_from_agent_ref = rooms._hermes_slug_from_agent_ref
_enrich_rooms_hermes_profile = rooms._enrich_rooms_hermes_profile
_ensure_workspace_agent_profile_row = rooms._ensure_workspace_agent_profile_row
_room_api_payload = rooms._room_api_payload
_agent_profile_belongs = rooms._agent_profile_belongs
_room_slug_available = rooms._room_slug_available
_list_rooms = rooms._list_rooms
_patch_room = rooms._patch_room
_get_workspace = rooms._get_workspace
_patch_workspace = rooms._patch_workspace
_patch_workspace_integrations = rooms._patch_workspace_integrations
_get_room = rooms._get_room
_create_room = rooms._create_room
_default_workspace_room = rooms._default_workspace_room
_ensure_user_in_room = rooms._ensure_user_in_room
_workspace_credential_mode = rooms._workspace_credential_mode
_user_can_access_room = rooms._user_can_access_room
_user_can_manage_room_members = rooms._user_can_manage_room_members
_get_active_room_session = rooms._get_active_room_session
_list_room_sessions = rooms._list_room_sessions
_resolve_latest_room_session = rooms._resolve_latest_room_session
_archive_room_sessions = rooms._archive_room_sessions
_upsert_room_session = rooms._upsert_room_session
_room_session_context = rooms._room_session_context
_resolve_agent_room_for_user = rooms._resolve_agent_room_for_user
_resolve_room_agent_chat = rooms._resolve_room_agent_chat


# WF-032: user_prefs re-exports
_parse_user_platform_ids = user_prefs.parse_user_platform_ids
_merge_user_platform_ids = user_prefs.merge_user_platform_ids
_read_user_llm_prefs = user_prefs.read_user_llm_prefs
_write_user_llm_prefs = user_prefs.write_user_llm_prefs
_user_payload = user_prefs.user_payload
_display_name_from_email = user_prefs.display_name_from_email
_workspace_membership_payload = user_prefs.workspace_membership_payload
_validate_me_profile_updates = user_prefs.validate_me_profile_updates
_apply_me_profile_updates = user_prefs.apply_me_profile_updates
_sync_workframe_user_profile = user_prefs.sync_workframe_user_profile
current_user_me = user_prefs.current_user_me
_get_workframe_user = user_prefs.get_workframe_user
_onboarding_payload = user_prefs.onboarding_payload
_session_profile_payload = user_prefs.session_profile_payload


# WF-032: auth_gate re-exports (session, CORS/host, deployment mode)
SECURE_MODE = auth_gate.SECURE_MODE
DEV_LOCAL_UNSAFE = auth_gate.DEV_LOCAL_UNSAFE
DEPLOYMENT_MODE = auth_gate.DEPLOYMENT_MODE
DEPLOYMENT_MODES = auth_gate.DEPLOYMENT_MODES
OWNER_ADMIN_ROLES = auth_gate.OWNER_ADMIN_ROLES
AUTH_TOKEN = auth_gate.AUTH_TOKEN
CORS_ALLOW_ORIGINS = auth_gate.CORS_ALLOW_ORIGINS
ALLOWED_HOSTS = auth_gate.ALLOWED_HOSTS
DEFAULT_ALLOWED_HOSTS = auth_gate.DEFAULT_ALLOWED_HOSTS
_is_truthy = auth_gate._is_truthy
_dashboard_session_token = auth_gate._dashboard_session_token
_resolve_mode_flags = auth_gate._resolve_mode_flags
_require_auth_token = auth_gate._require_auth_token
_resolve_deployment_mode = auth_gate._resolve_deployment_mode
_invite_only_login_enforced = auth_gate._invite_only_login_enforced
_pending_invite_for_email = auth_gate._pending_invite_for_email
_email_allowed_to_authenticate = auth_gate.email_allowed_to_authenticate
_invite_token_allows_email = auth_gate.invite_token_allows_email
_deployment_security_errors = auth_gate.deployment_security_errors
_deployment_security_warnings = auth_gate.deployment_security_warnings
_session_cookie_secure = auth_gate.session_cookie_secure
_get_auth_token = auth_gate.get_auth_token
_check_auth = auth_gate.check_auth
_host_without_port = auth_gate.host_without_port
_allowed_hosts = auth_gate.allowed_hosts
_loopback_ui_origins = auth_gate.loopback_ui_origins
_install_setup_route = auth_gate.install_setup_route
_secure_host_origin_ok = auth_gate.secure_host_origin_ok
_validate_host = auth_gate.validate_host
_origin_host = auth_gate.origin_host
_origin_allowed = auth_gate.origin_allowed
_validate_origin = auth_gate.validate_origin
_validate_host_origin = auth_gate.validate_host_origin
_admin_write_allowed = auth_gate.admin_write_allowed
_cors_origin_for = auth_gate.cors_origin_for
_deployment_allows_sessionless_data_get = auth_gate.deployment_allows_sessionless_data_get
_sessionless_get_allowed = auth_gate.sessionless_get_allowed
_is_public_get = auth_gate.is_public_get
_cookie_session_id = auth_gate.cookie_session_id
_session_id_from_request = auth_gate.session_id_from_request
_auth_check = auth_gate.authorize_request
_workspace_role_for_user = auth_gate.workspace_role_for_user
_apply_session_user = auth_gate.apply_session_user
_user_is_stack_operator = auth_gate.user_is_stack_operator
_user_can_access_hermes_dashboard = auth_gate.user_can_access_hermes_dashboard
_role_allows = auth_gate.role_allows
_handler_is_active_workspace_member = auth_gate.handler_is_active_workspace_member

import stack_config
import site_meta
import google_auth
import platform_auth
import credential_vault
import turn_credentials
import llm_proxy
import action_proxy
import internal_proxy_auth
import concierge
import llm_error_glossary
import openrouter_catalog
import updates as stack_updates
import install_api
import run_authority
import run_ledger
import runtime_tokens
import oauth_pending
import mention_helpers
import provider_bindings
import provider_catalog
import oauth_redirect
import mention_invoke
import credential_resolve
import credential_store
import turn_overlay
import chat_sessions
import docker_gateway
from domain.entities import RunStatus

HERMES_DATA = Path(os.environ.get("HERMES_DATA", "/opt/data"))
WORKSPACE = Path(os.environ.get("WORKSPACE", "/workspace"))
DATA_DIR = Path(
    os.environ.get("WORKFRAME_API_DATA_DIR")
    or os.environ.get("MISSION_DATA_DIR")
    or str(Path(__file__).resolve().parent / "data")
)
BOARD_DB = Path(os.environ.get("BOARD_DB", str(DATA_DIR / "board.db")))
CONTENT_ROOT = WORKSPACE
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8080"))
NATIVE_PROFILE = os.environ.get("WORKFRAME_NATIVE_PROFILE", "").strip()
PROJECT_NAME = os.environ.get("WORKFRAME_PROJECT", "Workframe")
PUBLIC_DIR = Path(__file__).resolve().parent / "public"
SSE_INTERVAL = float(os.environ.get("SSE_INTERVAL", "5"))
VERSION = "workframe-api-0.1.0"
DELEGATION_SCOPE_AGENTS_DELEGATE = "agents:delegate"
ROUTES_JSON = HERMES_DATA / "workframe" / "routes.json"
AGENTS_JSON = HERMES_DATA / "workframe" / "agents.json"
AVATAR_REGISTRY_JSON = HERMES_DATA / "workframe" / "avatar-registry.json"
_CATALOG_DIR = Path(__file__).resolve().parent / "catalog"
AVATAR_CATALOG_JSON = _CATALOG_DIR / "avatar-catalog.json"
USER_AVATAR_CATALOG_JSON = _CATALOG_DIR / "user-avatar-catalog.json"
LOGO_CATALOG_JSON = _CATALOG_DIR / "logo-catalog.json"
def _lane_registry_json() -> Path:
    # ponytail: must follow DATA_DIR â€” tests patch DATA_DIR after import
    return DATA_DIR / "lane-registry.json"
DOCKER_SOCK = os.environ.get("DOCKER_SOCK", "/var/run/docker.sock")
GATEWAY_CONTAINER_NAME = os.environ.get("WORKFRAME_GATEWAY_CONTAINER", "workframe-gateway")
SUPERVISOR_URL = os.environ.get("WORKFRAME_SUPERVISOR_URL", "http://workframe-supervisor:8090").rstrip("/")
SUPERVISOR_TOKEN = (
    os.environ.get("WORKFRAME_SUPERVISOR_TOKEN")
    or os.environ.get("SUPERVISOR_TOKEN")
    or ""
).strip()

# Auth config
AUTH_DB_PATH = DATA_DIR / "auth.db"
WORKFRAME_AUTH_PASSWORD = os.environ.get("WORKFRAME_AUTH_PASSWORD", "")
WORKFRAME_AUTH_INSECURE = os.environ.get("WORKFRAME_AUTH_INSECURE", "0").strip() in {"1", "true", "yes"}
WORKFRAME_SESSION_TTL = int(os.environ.get("WORKFRAME_SESSION_TTL", "2592000"))
WORKFRAME_REFRESH_TTL = int(os.environ.get("WORKFRAME_REFRESH_TTL", str(14 * 86400)))
DASHBOARD_HTTP_TIMEOUT = float(os.environ.get("HERMES_DASHBOARD_HTTP_TIMEOUT", "15"))
WORKFRAME_REFRESH_WINDOW = 300  # refresh session ID when expires within 5 min
WORKFRAME_RUNTIME_TOKEN_TTL = runtime_tokens.DEFAULT_TTL
WORKFRAME_LLM_PROXY_INTERNAL = os.environ.get(
    "WORKFRAME_LLM_PROXY_INTERNAL", "http://workframe-api:8080"
).rstrip("/")

import zk_auth as _zk



_profile_health_cache: dict[str, tuple[bool, float]] = {}
_PROFILE_HEALTH_TTL_SEC = 8.0
_user_llm_picker_cache: dict[str, tuple[frozenset[str], float]] = {}
_SESSION_INFO_TTL_SEC = 5.0


def _install_window_open() -> bool:
    try:
        return install_api.install_window_open(str(DATA_DIR / "workframe.db"))
    except Exception:
        return False


def _install_complete() -> bool:
  """Stack install wizard finished â€” distinct from per-user onboarding gates."""
  return not _install_window_open()


def _install_owner_session_ok(handler: BaseHTTPRequestHandler) -> bool:
    """During install, stack mutations require the verified owner after bootstrap."""
    if not _install_window_open():
        return _role_allows(handler, OWNER_ADMIN_ROLES)
    if not install_api.install_mutations_require_owner(str(_workframe_db_path())):
        return True
    user_id = str(getattr(handler, "auth_user", "") or "").strip()
    return bool(user_id) and _role_allows(handler, OWNER_ADMIN_ROLES)



def _primary_workspace_row(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, display_name FROM workspaces
        WHERE deleted_at IS NULL
        ORDER BY CASE WHEN slug = 'default' THEN 0 ELSE 1 END, created_at ASC
        LIMIT 1
        """,
    ).fetchone()


def _primary_workspace_branding(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, display_name, description, avatar_url, settings_json
        FROM workspaces
        WHERE deleted_at IS NULL
        ORDER BY CASE WHEN slug = 'default' THEN 0 ELSE 1 END, created_at ASC
        LIMIT 1
        """,
    ).fetchone()
    if not row:
        return None
    settings = _parse_workspace_settings(row)
    return {
        "display_name": str(row["display_name"] or "").strip(),
        "description": str(row["description"] or "").strip(),
        "avatar_url": str(row["avatar_url"] or "").strip(),
        "tagline": str(settings.get("tagline") or "").strip(),
    }


def _public_site_meta_payload() -> dict[str, Any]:
    cfg = stack_config.get_stack_config()
    env_base = str(APP_BASE_URL or "").strip().rstrip("/")
    cfg_base = str(cfg.get("app_base_url") or "").strip().rstrip("/")
    # ponytail: HTTPS env wins over loopback stack_config (wizard often saves slot URL first).
    if env_base.startswith("https://"):
        app_base = env_base
    elif cfg_base.startswith("https://"):
        app_base = cfg_base
    elif cfg_base and "127.0.0.1" not in cfg_base and "localhost" not in cfg_base.lower():
        app_base = cfg_base
    else:
        app_base = env_base or cfg_base
    workspace = None
    if _install_complete():
        try:
            conn = _workframe_db()
            workspace = _primary_workspace_branding(conn)
            conn.close()
        except sqlite3.Error:
            workspace = None
    return site_meta.resolve_site_meta(
        app_base_url=app_base,
        install_complete=_install_complete(),
        workspace=workspace,
        normalize_logo=_normalize_logo_url,
    )







def _admin_write_allowed(handler: BaseHTTPRequestHandler) -> bool:
    """DEV_LOCAL_UNSAFE: admin POST requires X-Workframe-Local (browsers cannot set cross-origin)."""
    if SECURE_MODE or not DEV_LOCAL_UNSAFE:
        return True
    return handler.headers.get("X-Workframe-Local", "").strip() == "1"


def _apply_stack_update(target: str, *, user_ack: bool = False) -> dict[str, Any]:
    return stack_updates.apply_update(target, user_ack=user_ack)


def _restart_stack_gateway() -> dict[str, Any]:
    return stack_updates.restart_gateway()




def _is_json_content_type(value: str) -> bool:
    return value.split(";", 1)[0].strip().lower() == "application/json"


def _resolve_workspace_id(slug_or_id: str) -> str | None:
    """Resolve a workspace slug or UUID to its canonical UUID.
    Returns None if workspace not found or deleted.
    """
    sid = str(slug_or_id or "").strip()
    if not sid:
        return None
    try:
        conn = _workframe_db()
        row = conn.execute(
            "SELECT id FROM workspaces WHERE (id = ? OR slug = ?) AND deleted_at IS NULL",
            (sid, sid),
        ).fetchone()
        conn.close()
        return row["id"] if row else None
    except Exception:
        return None


def _supervisor_ready() -> bool:
    return bool(SUPERVISOR_URL) and bool(SUPERVISOR_TOKEN)


def _supervisor_request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[int, Any]:
    """Proxy a JSON request to workframe-supervisor."""
    if not SUPERVISOR_URL:
        return 503, {"ok": False, "error": "WORKFRAME_SUPERVISOR_URL not configured"}
    if not SUPERVISOR_TOKEN:
        return 503, {"ok": False, "error": "WORKFRAME_SUPERVISOR_TOKEN not configured"}
    url = f"{SUPERVISOR_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return int(resp.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return int(exc.code), json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return int(exc.code), {"ok": False, "error": raw}
    except (urllib.error.URLError, TimeoutError) as exc:
        return 503, {
            "ok": False,
            "error": "supervisor_unavailable",
            "hint": "On the server: cd infra/compose/workframe && docker compose up -d",
            "detail": str(exc),
        }


def _maybe_sync_compose_public_url(public_url: str, *, restart: bool | None = None) -> dict[str, Any] | None:
    """Write APP_BASE_URL into host compose .env; optionally recreate API/gateway (not supervisor)."""
    url = str(public_url or "").strip()
    if not url:
        return None
    lowered = url.lower()
    if "127.0.0.1" in lowered or "localhost" in lowered:
        return None
    if not _supervisor_ready():
        return None
    if not str(os.environ.get("WORKFRAME_HOST_COMPOSE_DIR") or "").strip():
        return None
    if restart is None:
        restart = not _install_window_open()
    status, data = _supervisor_request(
        "POST",
        "/v1/host.set_compose_public_url",
        {"url": url, "restart": restart},
        timeout=180.0,
    )
    if status >= 400:
        return data if isinstance(data, dict) else {"ok": False, "error": "compose_sync_failed"}
    return data if isinstance(data, dict) else {"ok": True}


def _supervisor_gateway_exec(profile: str, args: list[str]) -> tuple[int, str]:
    if not _supervisor_ready():
        raise RuntimeError(
            "Docker socket access is disabled in SECURE_MODE; "
            "configure WORKFRAME_SUPERVISOR_URL and WORKFRAME_SUPERVISOR_TOKEN"
        )
    status, data = _supervisor_request(
        "POST",
        "/v1/gateway.exec",
        {"profile": profile, "args": args},
        timeout=120.0,
    )
    if status >= 300:
        err = data.get("error") if isinstance(data, dict) else str(data)
        raise ValueError(err or f"supervisor gateway.exec failed ({status})")
    if not isinstance(data, dict):
        raise ValueError("supervisor gateway.exec returned invalid payload")
    exit_code = data.get("exit_code")
    try:
        code = int(exit_code if exit_code is not None else 1)
    except (TypeError, ValueError):
        code = 1
    return code, str(data.get("output") or "")


def _supervisor_container_exec(cmd: list[str], *, detach: bool = False) -> tuple[int, str]:
    if not _supervisor_ready():
        raise RuntimeError(
            "Docker socket access is disabled in SECURE_MODE; "
            "configure WORKFRAME_SUPERVISOR_URL and WORKFRAME_SUPERVISOR_TOKEN"
        )
    status, data = _supervisor_request(
        "POST",
        "/v1/gateway.container_exec",
        {"args": [str(part) for part in cmd], "detach": detach},
        timeout=30.0 if detach else 120.0,
    )
    if status >= 300:
        err = data.get("error") if isinstance(data, dict) else str(data)
        raise ValueError(err or f"supervisor gateway.container_exec failed ({status})")
    if not isinstance(data, dict):
        raise ValueError("supervisor gateway.container_exec returned invalid payload")
    if detach:
        return 0, str(data.get("output") or "")
    exit_code = data.get("exit_code")
    try:
        code = int(exit_code if exit_code is not None else 1)
    except (TypeError, ValueError):
        code = 1
    return code, str(data.get("output") or "")


def _supervisor_profile_lifecycle(profile: str, action: str) -> dict[str, Any]:
    if not _supervisor_ready():
        raise RuntimeError(
            "Docker socket access is disabled in SECURE_MODE; "
            "configure WORKFRAME_SUPERVISOR_URL and WORKFRAME_SUPERVISOR_TOKEN"
        )
    if action == "status":
        q = urllib.parse.quote(profile, safe="")
        status, data = _supervisor_request("GET", f"/v1/profile.status?profile={q}", timeout=15.0)
    else:
        status, data = _supervisor_request("POST", f"/v1/profile.{action}", {"profile": profile}, timeout=60.0)
    if status >= 300:
        err = data.get("error") if isinstance(data, dict) else str(data)
        raise ValueError(err or f"supervisor {action} failed ({status})")
    if not isinstance(data, dict):
        raise ValueError(f"supervisor {action} returned invalid payload")
    return data


SPECIALIST_ROLES: dict[str, str] = {
    "visionary": "Clarifies product purpose, positioning, strategy, user value, and long-term alignment.",
    "architect": "Defines system design, technical boundaries, implementation plans, and code-review standards.",
    "docs": "Maintains AGENTS.md, .hermes.md, docs indexes, source-of-truth maps, and change summaries.",
    "dev": "Builds and modifies project files, scripts, tests, and implementation artifacts.",
    "research": "Performs technical research, market research, references, competitive analysis, and R&D notes.",
    "designer": "Handles UI direction, design docs, visual assets, image prompts, brand direction, and layout feedback.",
}



_board_lock = threading.Lock()
_cpu_cache: dict[str, Any] = {"at": 0.0, "percent": 0.0}
_workspace_event_lock = threading.Lock()
_workspace_event_state: dict[str, int] = {"version": 0}
_room_live_lock = rooms._room_live_lock
_room_live_queues = rooms._room_live_queues
_room_live_turns = rooms._room_live_turns
_gateway_lifecycle_lock = threading.Lock()





def _exec_targets_runtime_profile_secrets(cmd: list[str], acting_profile: str = "") -> bool:
    """Return True when gateway shell command targets sibling profile secrets."""
    if DEPLOYMENT_MODE == "single_user_local":
        return False
    from profile_secret_policy import exec_blocked_for_profile

    return exec_blocked_for_profile(cmd, acting_profile)


def _runtime_profile_owner(runtime: str, workspace_id: str = "") -> str:
    runtime = safe_profile_slug(str(runtime or "").strip())
    workspace_id = str(workspace_id or "").strip()
    if workspace_id:
        owner = _user_id_for_runtime_slug(runtime, workspace_id)
        if owner:
            return owner
    resolved = _resolve_runtime_owner(runtime)
    return resolved[0] if resolved else ""


def _user_may_access_runtime_profile(user_id: str, profile: str, workspace_id: str = "") -> bool:
    """RBAC for per-user u-* Hermes profile dirs (BFF + gateway exec)."""
    prof = safe_profile_slug(str(profile or "").strip())
    if not _is_runtime_profile_slug(prof):
        return True
    if DEPLOYMENT_MODE == "single_user_local":
        return True
    user_id = str(user_id or "").strip()
    if not user_id:
        return False
    if DEPLOYMENT_MODE == "trusted_team" and _user_is_stack_operator(user_id):
        return True
    owner = _runtime_profile_owner(prof, workspace_id)
    return bool(owner) and owner == user_id


def _stack_profile_env() -> dict[str, str]:
    primary = _primary_profile()
    if not primary:
        return {}
    return _read_env_map(_profile_dir(primary) / ".env")


def _user_auth_env_keys(user_id: str) -> set[str]:
    keys = _read_env_keys(_user_hermes_env_path(user_id))
    auth_path = _user_hermes_auth_path(user_id)
    if not auth_path.is_file():
        return keys
    try:
        loaded = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return keys
    creds = loaded.get("credentials") if isinstance(loaded, dict) else None
    if not isinstance(creds, list):
        return keys
    for row in creds:
        if not isinstance(row, dict):
            continue
        ref = str(row.get("credential_ref") or "")
        if ref.startswith("env:"):
            keys.add(ref[4:])
        env_var = str(row.get("env_var") or "")
        if env_var:
            keys.add(env_var)
    return keys


def _provider_connected_for_user(
    user_id: str,
    spec: dict[str, Any],
    bindings: dict[str, dict[str, Any]],
    env_keys: set[str],
) -> bool:
    provider_id = str(spec["id"])
    env_var = str(spec.get("env_var") or "")
    hermes_auth_id = str(spec.get("hermes_auth_id") or provider_id)
    if bindings.get(provider_id):
        return True
    if env_var and env_var in env_keys:
        return True
    auth_path = _user_hermes_auth_path(user_id)
    if auth_path.is_file():
        try:
            loaded = json.loads(auth_path.read_text(encoding="utf-8"))
            creds = loaded.get("credentials") if isinstance(loaded, dict) else None
            if isinstance(creds, list):
                for row in creds:
                    if not isinstance(row, dict):
                        continue
                    pid = str(row.get("provider") or row.get("id") or "").lower()
                    if pid in {provider_id, hermes_auth_id, hermes_auth_id.replace("-", "")}:
                        return True
        except (OSError, json.JSONDecodeError):
            pass
    if spec.get("user_only"):
        return False
    return False


def _user_hermes_dir_slug(user_id: str) -> str:
    raw = str(user_id or "").strip()
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw) or "user"


def _user_hermes_home(user_id: str) -> Path:
    return HERMES_DATA / "profiles" / _user_hermes_dir_slug(user_id)


def _user_hermes_env_path(user_id: str) -> Path:
    return _user_hermes_home(user_id) / ".env"


def _user_hermes_auth_path(user_id: str) -> Path:
    return _user_hermes_home(user_id) / "auth.json"



# Hermes gateway reads these from the primary profile .env; vault is source of truth.
_MESSAGING_GATEWAY_ENV: dict[str, dict[str, str]] = {
    "discord": {
        "token": "DISCORD_BOT_TOKEN",
        "home_channel": "DISCORD_HOME_CHANNEL",
        "allowed_users": "DISCORD_ALLOWED_USERS",
    },
    "telegram": {
        "token": "TELEGRAM_BOT_TOKEN",
        "home_channel": "TELEGRAM_HOME_CHANNEL",
        "allowed_users": "TELEGRAM_ALLOWED_USERS",
    },
}




def _parse_messaging_settings_patch(body: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    """Merge admin messaging channel/allowlist config into workspace settings."""
    raw = body.get("messaging")
    if not isinstance(raw, dict):
        return settings
    messaging = settings.get("messaging") if isinstance(settings.get("messaging"), dict) else {}
    merged = dict(messaging)
    for provider in ("discord", "telegram"):
        block = raw.get(provider)
        if not isinstance(block, dict):
            continue
        current = merged.get(provider) if isinstance(merged.get(provider), dict) else {}
        row = dict(current)
        if "home_channel" in block:
            row["home_channel"] = str(block.get("home_channel") or "").strip()
        if "allowed_users" in block:
            row["allowed_users"] = str(block.get("allowed_users") or "").strip()
        merged[provider] = row
    settings["messaging"] = merged
    return settings


def _workspace_member_platform_ids(workspace_id: str) -> dict[str, set[str]]:
    """Collect linked Discord/Telegram user IDs for workspace members."""
    workspace_id = str(workspace_id or "").strip()
    out: dict[str, set[str]] = {"discord": set(), "telegram": set(), "slack": set()}
    if not workspace_id:
        return out
    conn = _workframe_db()
    try:
        rows = conn.execute(
            """
            SELECT u.platform_ids
            FROM users u
            JOIN workspace_memberships wm ON wm.user_id = u.id
            WHERE wm.workspace_id = ?
              AND wm.deleted_at IS NULL
              AND u.deleted_at IS NULL
              AND wm.status = 'active'
            """,
            (workspace_id,),
        ).fetchall()
    finally:
        conn.close()
    for row in rows:
        raw = row[0] if row else "{}"
        try:
            parsed = json.loads(str(raw or "{}"))
        except (TypeError, json.JSONDecodeError):
            parsed = {}
        if not isinstance(parsed, dict):
            continue
        for platform in out:
            val = str(parsed.get(platform) or "").strip()
            if val:
                out[platform].add(val)
    return out


def _merged_messaging_allowed_users(workspace_id: str, provider: str, seed: str) -> str:
    """Admin seed allowlist + member-linked platform IDs for gateway env."""
    provider = str(provider or "").strip().lower()
    ids: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[\s,;]+", str(seed or "").strip()):
        token = part.strip()
        if token and token not in seen:
            seen.add(token)
            ids.append(token)
    for member_id in sorted(_workspace_member_platform_ids(workspace_id).get(provider, set())):
        if member_id not in seen:
            seen.add(member_id)
            ids.append(member_id)
    return ",".join(ids)


def _workspace_messaging_integrations_payload(workspace_id: str, settings: dict[str, Any]) -> dict[str, Any]:
    messaging = settings.get("messaging") if isinstance(settings.get("messaging"), dict) else {}
    payload: dict[str, Any] = {}
    for provider, env_map in _MESSAGING_GATEWAY_ENV.items():
        block = messaging.get(provider) if isinstance(messaging.get(provider), dict) else {}
        resolved = _resolve_credential("", workspace_id, provider)
        has_token = bool(resolved and _credential_secret(resolved, ""))
        payload[provider] = {
            "bot_token_configured": has_token,
            "home_channel": str(block.get("home_channel") or ""),
            "allowed_users": str(block.get("allowed_users") or ""),
        }
    return payload


def _set_primary_messaging_platforms(enabled: dict[str, bool]) -> tuple[bool, str]:
    primary = _primary_profile()
    if not primary:
        return False, "no_primary_profile"
    flags = {name: bool(enabled.get(name)) for name in ("discord", "telegram")}
    cfg_path = _profile_gateway_config_path(primary)
    if cfg_path is None:
        return False, "no_primary_profile"
    try:
        import yaml

        cfg: dict[str, Any] = {}
        if cfg_path.is_file():
            loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
            cfg = loaded if isinstance(loaded, dict) else {}
        plats = cfg.setdefault("platforms", {})
        if not isinstance(plats, dict):
            plats = {}
            cfg["platforms"] = plats
        for name, on in flags.items():
            row = plats.get(name) if isinstance(plats.get(name), dict) else {}
            row["enabled"] = bool(on)
            plats[name] = row
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        return True, "ok"
    except (OSError, ImportError) as exc:
        return False, str(exc)


def _sync_workspace_messaging_gateway(workspace_id: str) -> dict[str, Any]:
    """Vault â†’ primary profile .env overlay + platform toggles + gateway restart."""
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return {"ok": False, "error": "workspace_id_required"}
    primary = _primary_profile()
    if not primary:
        return {"ok": False, "error": "no_primary_profile"}
    try:
        conn = _workframe_db()
        row = conn.execute(
            "SELECT settings_json FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        conn.close()
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"db_error: {exc}"}
    settings = _parse_workspace_settings(row) if row else {}
    messaging = settings.get("messaging") if isinstance(settings.get("messaging"), dict) else {}
    env_path = _profile_dir(primary) / ".env"
    enabled: dict[str, bool] = {}
    for provider, env_map in _MESSAGING_GATEWAY_ENV.items():
        token_var = env_map["token"]
        resolved = _resolve_credential("", workspace_id, provider)
        secret = _credential_secret(resolved, "") if resolved else ""
        block = messaging.get(provider) if isinstance(messaging.get(provider), dict) else {}
        if secret:
            _upsert_env_secret(env_path, token_var, secret)
            enabled[provider] = True
            home = str(block.get("home_channel") or "").strip()
            if home:
                _upsert_env_secret(env_path, env_map["home_channel"], home)
            else:
                _remove_env_secret(env_path, env_map["home_channel"])
            allowed = _merged_messaging_allowed_users(
                workspace_id,
                provider,
                str(block.get("allowed_users") or ""),
            )
            if allowed:
                _upsert_env_secret(env_path, env_map["allowed_users"], allowed)
            else:
                _remove_env_secret(env_path, env_map["allowed_users"])
        else:
            enabled[provider] = False
            for key in env_map.values():
                _remove_env_secret(env_path, key)
    ok, out = _set_primary_messaging_platforms(enabled)
    if not ok:
        return {"ok": False, "error": f"messaging_platform_config_failed: {out}"}
    try:
        restart = _restart_stack_gateway()
    except (ValueError, OSError, RuntimeError) as exc:
        _log_handler_error("_sync_workspace_messaging_gateway restart", exc)
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "gateway": restart}


def _read_env_keys(env_path: Path) -> set[str]:
    return set(_read_env_map(env_path).keys())


def _read_env_map(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, _sep, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and value:
            values[key] = value
    return values


def _llm_provider_env_vars() -> list[str]:
    names: list[str] = []
    for spec in PROVIDER_CONNECT_CATALOG:
        if str(spec.get("category") or "") != "llm":
            continue
        env_var = str(spec.get("env_var") or "").strip()
        if env_var:
            names.append(env_var)
    return names


def _hermes_user_home_container(user_id: str) -> str:
    return f"/opt/data/profiles/{_user_hermes_dir_slug(user_id)}"


def _hermes_user_exec(user_id: str, args: list[str]) -> tuple[int, str]:
    home = _hermes_user_home_container(user_id)
    _user_hermes_home(user_id).mkdir(parents=True, exist_ok=True)
    if SECURE_MODE:
        if not _supervisor_ready():
            raise RuntimeError(
                "Docker socket access is disabled in SECURE_MODE; "
                "configure WORKFRAME_SUPERVISOR_URL and WORKFRAME_SUPERVISOR_TOKEN"
            )
        status, data = _supervisor_request(
            "POST",
            "/v1/hermes.user_exec",
            {"home": home, "args": [str(part) for part in args]},
            timeout=120.0,
        )
        if status >= 300:
            err = data.get("error") if isinstance(data, dict) else str(data)
            raise ValueError(err or f"supervisor hermes.user_exec failed ({status})")
        if not isinstance(data, dict):
            raise ValueError("supervisor hermes.user_exec returned invalid payload")
        exit_code = data.get("exit_code")
        try:
            code = int(exit_code if exit_code is not None else 1)
        except (TypeError, ValueError):
            code = 1
        return code, str(data.get("output") or "")
    inner = " ".join(shlex.quote(part) for part in args)
    shell = (
        f"export HERMES_HOME={shlex.quote(home)} HOME={shlex.quote(home)}; "
        f"mkdir -p {shlex.quote(home)}; cd {shlex.quote(home)}; "
        f"/opt/hermes/bin/hermes {inner}"
    )
    return _docker_exec(GATEWAY_CONTAINER_NAME, ["sh", "-lc", shell], acting_profile=_user_hermes_dir_slug(user_id))




# WF-032: provider_bindings re-exports
_user_provider_bindings = provider_bindings._user_provider_bindings
_DEVICE_OAUTH_PROVIDER_IDS = provider_bindings._DEVICE_OAUTH_PROVIDER_IDS
_hermes_auth_id_for_spec = provider_bindings._hermes_auth_id_for_spec
_hermes_oauth_auth_keys = provider_bindings._hermes_oauth_auth_keys
_oauth_llm_provider_spec = provider_bindings._oauth_llm_provider_spec
_auth_json_has_oauth_material = provider_bindings._auth_json_has_oauth_material
_extract_oauth_block_from_auth = provider_bindings._extract_oauth_block_from_auth
_merge_oauth_auth_into_profile = provider_bindings._merge_oauth_auth_into_profile
_sync_oauth_llm_to_profile = provider_bindings._sync_oauth_llm_to_profile
_hermes_oauth_tokens_present = provider_bindings._hermes_oauth_tokens_present
_load_user_hermes_auth = provider_bindings._load_user_hermes_auth
_read_gateway_data_file = provider_bindings._read_gateway_data_file
_user_provider_connected = provider_bindings._user_provider_connected
_remove_hermes_oauth_provider = provider_bindings._remove_hermes_oauth_provider
_parse_device_oauth_log = provider_bindings._parse_device_oauth_log
_sync_user_oauth_provider_to_runtime_profiles = provider_bindings._sync_user_oauth_provider_to_runtime_profiles
_finalize_hermes_device_oauth = provider_bindings._finalize_hermes_device_oauth
_device_oauth_session_get = provider_bindings._device_oauth_session_get
_device_oauth_session_patch = provider_bindings._device_oauth_session_patch
_spawn_hermes_device_oauth = provider_bindings._spawn_hermes_device_oauth
_start_device_oauth = provider_bindings._start_device_oauth
list_user_providers = provider_bindings.list_user_providers
disconnect_user_credential = provider_bindings.disconnect_user_credential
disconnect_user_provider = provider_bindings.disconnect_user_provider
device_oauth_status = provider_bindings.device_oauth_status
start_user_oauth = provider_bindings.start_user_oauth

# WF-032: provider_catalog re-exports
PROVIDER_CONNECT_CATALOG = provider_catalog.PROVIDER_CONNECT_CATALOG
_USER_ONLY_PROVIDER_IDS = provider_catalog._USER_ONLY_PROVIDER_IDS
_catalog_provider = provider_catalog.catalog_provider
_catalog_provider_for_llm = provider_catalog.catalog_provider_for_llm
_provider_user_only = provider_catalog.provider_user_only
_provider_env_vars = provider_catalog.provider_env_vars
GITHUB_OAUTH_SCOPES = oauth_redirect.GITHUB_OAUTH_SCOPES
STRIPE_CONNECT_SCOPES = oauth_redirect.STRIPE_CONNECT_SCOPES
_parse_workspace_settings = oauth_redirect._parse_workspace_settings
_stripe_connect_app_config = oauth_redirect._stripe_connect_app_config
_stripe_connect_configured = oauth_redirect._stripe_connect_configured
_stripe_oauth_redirect_uri = oauth_redirect._stripe_oauth_redirect_uri
_github_oauth_app_config = oauth_redirect._github_oauth_app_config
_github_oauth_configured = oauth_redirect._github_oauth_configured
_github_oauth_redirect_uri = oauth_redirect._github_oauth_redirect_uri
_start_github_oauth = oauth_redirect._start_github_oauth
_complete_github_oauth = oauth_redirect._complete_github_oauth
_start_stripe_oauth = oauth_redirect._start_stripe_oauth
_complete_stripe_oauth = oauth_redirect._complete_stripe_oauth
_start_discord_oauth = oauth_redirect._start_discord_oauth
_complete_discord_oauth = oauth_redirect._complete_discord_oauth

WORKSPACE_MEMBER_ROLES = {"owner", "admin", "editor", "viewer", "member"}
WORKSPACE_MEMBER_STATUSES = {"active", "invited", "removed"}




def _workframe_db_path() -> Path:
    return AUTH_DB_PATH.parent / "workframe.db"


def _workframe_db() -> sqlite3.Connection:
    """Open the Workframe domain DB. Tables are ensured by schema migrations."""
    db_path = _workframe_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn




def _workspace_event_revision(conn: sqlite3.Connection, workspace_id: str) -> str:
    row = conn.execute(
        """
        SELECT
            COALESCE((SELECT MAX(updated_at) FROM rooms WHERE workspace_id = ? AND deleted_at IS NULL), '0') AS rooms_max,
            COALESCE((SELECT MAX(updated_at) FROM workspace_memberships WHERE workspace_id = ? AND deleted_at IS NULL), '0') AS workspace_memberships_max,
            COALESCE((SELECT MAX(rm.updated_at)
                      FROM room_memberships rm
                      JOIN rooms r ON r.id = rm.room_id
                      WHERE r.workspace_id = ? AND r.deleted_at IS NULL AND rm.deleted_at IS NULL), '0') AS room_memberships_max,
            COALESCE((SELECT MAX(m.updated_at)
                      FROM messages m
                      JOIN rooms r ON r.id = m.room_id
                      WHERE r.workspace_id = ? AND r.deleted_at IS NULL AND m.deleted_at IS NULL), '0') AS messages_max
        """,
        (workspace_id, workspace_id, workspace_id, workspace_id),
    ).fetchone()
    if not row:
        return '0:0:0:0'
    return f"{row['rooms_max']}:{row['workspace_memberships_max']}:{row['room_memberships_max']}:{row['messages_max']}"


def _workspace_sse_revision(conn: sqlite3.Connection, workspace_id: str) -> str:
    db_rev = _workspace_event_revision(conn, workspace_id)
    files_rev = str(workspace_state().get("revision") or "")
    return f"{db_rev}|{files_rev}"


def _workspace_event_payload(workspace_id: str, revision: str) -> dict[str, Any]:
    return {
        "type": "workspace.changed",
        "workspace_id": workspace_id,
        "revision": revision,
        "files_revision": str(workspace_state().get("revision") or ""),
        "ts": int(time.time()),
    }


def _bump_workspace_event_state() -> None:
    with _workspace_event_lock:
        _workspace_event_state["version"] += 1


def _workspace_event_version() -> int:
    with _workspace_event_lock:
        return _workspace_event_state["version"]




def _provision_invited_member_agent_runtimes(workspace_id: str, user_id: str) -> None:
    """Provision u-* runtimes for workspace agents when a member joins."""
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not workspace_id or not user_id:
        return
    try:
        conn = _workframe_db()
        rows = conn.execute(
            """
            SELECT id FROM agent_profiles
            WHERE workspace_id = ? AND deleted_at IS NULL AND status = 'available'
            """,
            (workspace_id,),
        ).fetchall()
        conn.close()
    except Exception:  # noqa: BLE001
        return
    for row in rows:
        _provision_agent_dm_runtimes(workspace_id, str(row["id"]), [user_id])


def _provision_agent_dm_runtimes(
    workspace_id: str,
    agent_profile_id: str,
    user_ids: list[str],
) -> None:
    """Create u-* runtime profiles when an agent DM room is created â€” install/onboarding only, not bind."""
    workspace_id = str(workspace_id or "").strip()
    agent_profile_id = str(agent_profile_id or "").strip()
    if not workspace_id or not agent_profile_id:
        return
    try:
        conn = _workframe_db()
        agent_row = _lookup_agent_profile(conn, workspace_id, agent_profile_id)
        conn.close()
    except Exception:  # noqa: BLE001
        return
    if not agent_row:
        return
    template = str(agent_row["slug"] or "").strip()
    if not template:
        return
    try:
        template = resolve_validated_profile(template)
    except ValueError as exc:
        print(
            f"[provision_agent_dm_runtimes] skip {agent_profile_id}: invalid template {template!r}: {exc}",
            flush=True,
        )
        return
    for uid in user_ids:
        user = str(uid or "").strip()
        if not user:
            continue
        runtime = _runtime_profile_slug(user, template)
        if _runtime_profile_on_disk(runtime):
            continue
        try:
            ensure_runtime_profile(runtime, template, user, workspace_id)
        except Exception as exc:  # noqa: BLE001
            print(
                f"[provision_agent_dm_runtimes] failed {runtime} for {user}: {exc}",
                flush=True,
            )


def bootstrap_agent_dm_lane(
    user_id: str,
    workspace_id: str,
    template_slug: str,
    *,
    model: str = "",
    soul: str = "",
    bind_session: bool = True,
    room_name: str = "",
    role: str = "",
    tagline: str = "",
    created_by: str = "",
) -> dict[str, Any]:
    """Provision u-* runtime, model/proxy, DM room, and optional session bind â€” install/create-agent parity."""
    user_id = str(user_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if not _native_profile_present():
        _ensure_native_hermes_profile()
    template = resolve_validated_profile(str(template_slug or "").strip())
    if not user_id or not workspace_id:
        return {"ok": False, "error": "user_id and workspace_id required"}
    runtime = _runtime_profile_slug(user_id, template)
    steps: list[dict[str, Any]] = []
    try:
        ensure_runtime_profile(runtime, template, user_id, workspace_id)
        steps.append({"step": "runtime_profile", "ok": True, "runtime": runtime})
    except Exception as exc:
        steps.append({"step": "runtime_profile", "ok": False, "error": str(exc)})
        return {"ok": False, "template": template, "runtime": runtime, "steps": steps, "error": str(exc)}

    model_id = str(model or "").strip()
    if model_id:
        try:
            applied = hermes_model_set(runtime, model_id, user_id, workspace_id)
            steps.append(
                {
                    "step": "set_runtime_model",
                    "ok": bool(applied.get("ok")),
                    "model": model_id,
                    **({"error": applied.get("error")} if not applied.get("ok") else {}),
                },
            )
            if not applied.get("ok"):
                return {
                    "ok": False,
                    "template": template,
                    "runtime": runtime,
                    "steps": steps,
                    "error": str(applied.get("error") or "set_runtime_model_failed"),
                }
        except Exception as exc:
            steps.append({"step": "set_runtime_model", "ok": False, "error": str(exc)})
            return {
                "ok": False,
                "template": template,
                "runtime": runtime,
                "steps": steps,
                "error": str(exc),
            }
    else:
        try:
            _bootstrap_profile_providers(runtime, user_id, workspace_id)
            steps.append({"step": "bootstrap_providers", "ok": True})
            user_primary, user_chain = _read_user_llm_prefs(user_id)
            if user_primary:
                applied = hermes_model_set(runtime, user_primary, user_id, workspace_id)
                steps.append(
                    {
                        "step": "user_default_model",
                        "ok": bool(applied.get("ok")),
                        "model": user_primary,
                    },
                )
            if user_chain:
                chained = hermes_fallback_chain_set(runtime, user_chain, user_id=user_id)
                steps.append(
                    {
                        "step": "user_default_fallbacks",
                        "ok": bool(chained.get("ok")),
                        "count": len(user_chain),
                    },
                )
        except Exception as exc:
            steps.append({"step": "bootstrap_providers", "ok": False, "error": str(exc)})

    soul_text = str(soul or "").strip()
    identity_role = str(role or "").strip()
    identity_tagline = str(tagline or "").strip()
    identity_name = room_name.strip()
    if soul_text or identity_name or identity_role or identity_tagline:
        _seed_native_user_overlay(
            runtime,
            template,
            display_name=identity_name,
            role=identity_role,
            tagline=identity_tagline,
            user_soul=soul_text,
        )

    gateway_started = False
    last_gw_exc: Exception | None = None
    for attempt in range(3):
        try:
            ensure_profile_api(runtime, user_id, workspace_id, bootstrap_providers=False)
            step_row: dict[str, Any] = {"step": "start_gateway", "ok": True, "runtime": runtime}
            if attempt:
                step_row["retried"] = True
            steps.append(step_row)
            gateway_started = True
            break
        except Exception as exc:
            last_gw_exc = exc
            if attempt < 2:
                time.sleep(1.5)
    if not gateway_started:
        steps.append({"step": "start_gateway", "ok": False, "error": str(last_gw_exc)})
        return {
            "ok": False,
            "template": template,
            "runtime": runtime,
            "steps": steps,
            "error": str(last_gw_exc),
        }

    display = _runtime_display_label(user_id, template, workspace_id)
    _ensure_workspace_agent_profile_row(
        template,
        workspace_id=workspace_id,
        display_name=room_name.strip() or display,
        role=identity_role,
        tagline=identity_tagline,
        is_native=_is_native_profile(template),
    )
    status, room_payload = _create_room(
        workspace_id,
        {
            "name": room_name.strip() or display,
            "room_type": "direct",
            "agent_profile_id": template,
            "member_user_ids": [user_id],
        },
        created_by or user_id,
    )
    room = room_payload.get("room") if isinstance(room_payload.get("room"), dict) else {}
    room_id = str(room.get("id") or "").strip()
    dm_error = ""
    if not room_id:
        dm_error = str(
            room_payload.get("error")
            or room_payload.get("detail")
            or ("dm_room_failed" if status not in (200, 201) else "dm_room_missing_id"),
        ).strip()
    steps.append(
        {
            "step": "dm_room",
            "ok": status in (200, 201) and bool(room_id),
            "room_id": room_id,
            "status": status,
            **({"error": dm_error} if dm_error else {}),
        },
    )
    if not room_id:
        return {
            "ok": False,
            "template": template,
            "runtime": runtime,
            "steps": steps,
            "error": dm_error or "dm_room_failed",
            "room_error": room_payload,
        }

    session_id = ""
    if bind_session:
        bind_payload: dict[str, Any] = {
            "workspace_id": workspace_id,
            "source_id": "ui",
            "client_id": "default",
            "new_session": False,
        }
        if template == _primary_profile():
            bind_payload["binding_version"] = 2
        try:
            bound = room_chat_bind(room_id, bind_payload, user_id)
            session_id = str(bound.get("session_id") or "").strip()
            steps.append({"step": "room_chat_bind", "ok": bool(session_id), "session_id": session_id})
        except Exception as exc:
            steps.append({"step": "room_chat_bind", "ok": False, "error": str(exc)})

    bind_ok = not bind_session or bool(session_id)
    steps_ok = all(s.get("ok") is not False for s in steps)
    return {
        "ok": bind_ok and steps_ok,
        "template": template,
        "runtime": runtime,
        "room_id": room_id,
        "room": room,
        "session_id": session_id,
        "steps": steps,
        **({"error": "room_chat_bind_failed"} if bind_session and not session_id else {}),
    }


def _resolve_chat_hermes_profile(
    template_slug: str,
    user_id: str = "",
    room_id: str = "",
    workspace_id: str = "",
) -> str:
    """Agent DM â†’ per-user runtime profile; spaces and lanes keep the template slug."""
    template = resolve_validated_profile(template_slug)
    room_id = str(room_id or "").strip()
    user_id = str(user_id or "").strip()
    if not room_id or not user_id:
        return template
    conn = _workframe_db()
    try:
        room = conn.execute(
            "SELECT room_type, agent_profile_id, workspace_id FROM rooms WHERE id = ? AND deleted_at IS NULL",
            (room_id,),
        ).fetchone()
    finally:
        conn.close()
    if not room:
        return template
    if _is_space_room(str(room["room_type"]), room["agent_profile_id"]):
        return template
    agent_ref = str(room["agent_profile_id"] or "").strip()
    if str(room["room_type"]) != "direct" or not agent_ref:
        return template
    ws = str(workspace_id or room["workspace_id"] or "").strip()
    runtime = _runtime_profile_slug(user_id, template)
    if not _runtime_profile_on_disk(runtime):
        ensure_runtime_profile(runtime, template, user_id, ws)
    if not _runtime_profile_on_disk(runtime):
        raise ValueError("runtime_profile_not_provisioned")
    return runtime




def _is_space_room(room_type: str, agent_profile_id: str | None = None) -> bool:
    # ponytail: agent_profile_id ignored â€” legacy rows may still carry it; type defines a space.
    _ = agent_profile_id
    return str(room_type or "") in {"channel", "group"}


_mention_handle = mention_helpers.mention_handle
_room_agents_for_mentions = mention_helpers.room_agents_for_mentions
_room_users_for_mentions = mention_helpers.room_users_for_mentions
_parse_room_mentions = mention_helpers.parse_room_mentions
_process_space_message_mentions = mention_helpers.process_space_message_mentions
_parse_mentions = mention_helpers.parse_mentions


def _ensure_agent_in_space_room(conn: sqlite3.Connection, room_id: str, agent_profile_id: str) -> bool:
    agent_profile_id = str(agent_profile_id or "").strip()
    room_id = str(room_id or "").strip()
    if not agent_profile_id or not room_id:
        return False
    existing = conn.execute(
        """
        SELECT id FROM room_memberships
        WHERE room_id = ? AND agent_profile_id = ? AND deleted_at IS NULL
        """,
        (room_id, agent_profile_id),
    ).fetchone()
    if existing:
        return False
    now = str(int(time.time()))
    conn.execute(
        """
        INSERT INTO room_memberships (id, room_id, agent_profile_id, role, status, joined_at, updated_at)
        VALUES (?, ?, ?, 'agent', 'active', ?, ?)
        """,
        (str(uuid.uuid4()), room_id, agent_profile_id, now, now),
    )
    return True


def _add_workspace_agents_to_space_rooms(conn: sqlite3.Connection, workspace_id: str, agent_profile_id: str) -> None:
    workspace_id = str(workspace_id or "").strip()
    agent_profile_id = str(agent_profile_id or "").strip()
    if not workspace_id or not agent_profile_id:
        return
    rooms = conn.execute(
        """
        SELECT id FROM rooms
        WHERE workspace_id = ? AND deleted_at IS NULL AND room_type IN ('channel', 'group')
        """,
        (workspace_id,),
    ).fetchall()
    for room in rooms:
        _ensure_agent_in_space_room(conn, str(room["id"]), agent_profile_id)


def _add_workspace_member_to_space_rooms(conn: sqlite3.Connection, workspace_id: str, user_id: str) -> int:
    workspace_id = str(workspace_id or "").strip()
    user_id = str(user_id or "").strip()
    if not workspace_id or not user_id:
        return 0
    rooms = conn.execute(
        """
        SELECT id FROM rooms
        WHERE workspace_id = ? AND deleted_at IS NULL AND room_type IN ('channel', 'group')
        """,
        (workspace_id,),
    ).fetchall()
    joined = 0
    for room in rooms:
        if _ensure_user_in_room(conn, str(room["id"]), user_id):
            joined += 1
    return joined


def _add_workspace_members_to_space_room(conn: sqlite3.Connection, workspace_id: str, room_id: str) -> int:
    workspace_id = str(workspace_id or "").strip()
    room_id = str(room_id or "").strip()
    if not workspace_id or not room_id:
        return 0
    members = conn.execute(
        """
        SELECT user_id FROM workspace_memberships
        WHERE workspace_id = ? AND deleted_at IS NULL AND status = 'active'
        """,
        (workspace_id,),
    ).fetchall()
    joined = 0
    for member in members:
        uid = str(member["user_id"] or "").strip()
        if uid and _ensure_user_in_room(conn, room_id, uid):
            joined += 1
    return joined


def _onboard_workspace_member_rooms(
    conn: sqlite3.Connection,
    workspace_id: str,
    user_id: str,
    *,
    inviter_user_id: str | None = None,
) -> dict[str, Any]:
    room_join = _join_workspace_default_room(
        conn,
        workspace_id,
        user_id,
        inviter_user_id=inviter_user_id,
    )
    spaces_joined = _add_workspace_member_to_space_rooms(conn, workspace_id, user_id)
    return {**room_join, "spaces_joined": spaces_joined}












def _install_key_owner_user_ids(conn: sqlite3.Connection) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for row in conn.execute(
        "SELECT owner_id FROM workspaces WHERE owner_id IS NOT NULL AND owner_id != '' AND status = 'active'",
    ):
        uid = str(row[0] or "").strip()
        if uid and uid not in seen:
            seen.add(uid)
            ordered.append(uid)
    for row in conn.execute(
        """
        SELECT DISTINCT user_id FROM workspace_memberships
        WHERE role = 'owner' AND status = 'active' AND user_id IS NOT NULL AND user_id != ''
        """,
    ):
        uid = str(row[0] or "").strip()
        if uid and uid not in seen:
            seen.add(uid)
            ordered.append(uid)
    return ordered


def _upsert_user_credential_binding(
    conn: sqlite3.Connection,
    user_id: str,
    provider: str,
    credential_type: str,
    credential_ref: str,
    label: str,
) -> str:
    now = _utc_now()
    existing = conn.execute(
        """SELECT id FROM credential_bindings
           WHERE user_id = ? AND provider = ? AND credential_type = ?
             AND credential_ref = ? AND deleted_at IS NULL
           ORDER BY updated_at DESC, created_at DESC LIMIT 1""",
        (user_id, provider, credential_type, credential_ref),
    ).fetchone()
    if existing:
        cred_id = str(existing[0])
        conn.execute(
            """UPDATE credential_bindings
               SET label = ?, is_active = 1, updated_at = ?, deleted_at = NULL
               WHERE id = ?""",
            (label, now, cred_id),
        )
        return cred_id
    cred_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO credential_bindings
           (id, workspace_id, user_id, agent_profile_id, provider, credential_type,
            credential_ref, label, is_active, created_by, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cred_id, None, user_id, None, provider, credential_type, credential_ref, label, 1, user_id, now, now),
    )
    return cred_id


def _adopt_install_llm_key_for_user(
    conn: sqlite3.Connection,
    user_id: str,
    provider_id: str,
    env_var: str,
    secret: str,
) -> bool:
    """Copy one Hermes-install LLM key into a user's personal store (idempotent)."""
    if _user_provider_connected(user_id, _catalog_provider(provider_id) or {"id": provider_id, "category": "llm"}):
        return False
    label = f"{provider_id} (from install)"
    payload = _store_user_credential(user_id, provider_id, "api_key", secret, env_var, label)
    _upsert_user_credential_binding(
        conn,
        user_id,
        provider_id,
        "api_key",
        str(payload["credential_ref"]),
        label,
    )
    return True


def _install_profile_slug() -> str:
    """Profile that holds legacy Hermes-install .env keys (native concierge)."""
    primary = _primary_profile()
    if primary:
        return primary
    for slug in (NATIVE_PROFILE, "workframe-agent"):
        if slug and (_profile_dir(slug) / ".env").is_file():
            return slug
    return primary








# WF-032: credential_resolve re-exports
_default_credential_env_var = credential_resolve._default_credential_env_var
_provider_env_var = credential_resolve._provider_env_var
_credential_secret = credential_resolve._credential_secret
_resolve_secret_for_lease = credential_resolve._resolve_secret_for_lease
_credential_binding_payload = credential_resolve._credential_binding_payload
_resolve_credential = credential_resolve._resolve_credential

# WF-032: credential_store re-exports
_quote_env_value = credential_store._quote_env_value
_upsert_env_secret = credential_store._upsert_env_secret
_publish_profile_gateway_secrets = credential_store._publish_profile_gateway_secrets
_upsert_auth_metadata = credential_store._upsert_auth_metadata
_remove_env_secret = credential_store._remove_env_secret
_remove_auth_metadata = credential_store._remove_auth_metadata
_store_user_credential = credential_store._store_user_credential
_store_workspace_credential = credential_store._store_workspace_credential

# WF-032: turn_overlay re-exports
PROXY_HEADER_TEMPLATE = turn_overlay.PROXY_HEADER_TEMPLATE
_llm_proxy_base_url = turn_overlay._llm_proxy_base_url
_upsert_model_default_header = turn_overlay._upsert_model_default_header
_ensure_profile_proxy_headers = turn_overlay._ensure_profile_proxy_headers
_set_profile_model_base_url = turn_overlay._set_profile_model_base_url
_proxy_fallback_chain = turn_overlay._proxy_fallback_chain
_coalesce_profile_model_yaml = turn_overlay._coalesce_profile_model_yaml
_profile_llm_proxy_ready = turn_overlay._profile_llm_proxy_ready
_ensure_profile_llm_proxy = turn_overlay._ensure_profile_llm_proxy
_set_profile_model_api_key = turn_overlay._set_profile_model_api_key
_clear_profile_model_api_key = turn_overlay._clear_profile_model_api_key
_profile_lease_env_var = turn_overlay._profile_lease_env_var
_read_profile_lease_token = turn_overlay._read_profile_lease_token
_lease_reusable_for_turn = turn_overlay._lease_reusable_for_turn
_read_config_model_api_key = turn_overlay._read_config_model_api_key
_sync_profile_model_api_key = turn_overlay._sync_profile_model_api_key
_apply_turn_credential_lease = turn_overlay._apply_turn_credential_lease
_action_proxy_base_url = turn_overlay._action_proxy_base_url
_action_proxy_env_var = turn_overlay._action_proxy_env_var
_user_action_env_specs = turn_overlay._user_action_env_specs
_overlay_turn_user_env = turn_overlay._overlay_turn_user_env
_apply_action_credential_lease = turn_overlay._apply_action_credential_lease
_revoke_turn_credential_lease = turn_overlay._revoke_turn_credential_lease
_require_user_provider = turn_overlay._require_user_provider
_require_runtime_owner_provider = turn_overlay._require_runtime_owner_provider
_strip_profile_llm_env = turn_overlay._strip_profile_llm_env
_strip_profile_action_env = turn_overlay._strip_profile_action_env
_overlay_turn_provider_env = turn_overlay._overlay_turn_provider_env
_try_overlay_turn_provider_env = turn_overlay._try_overlay_turn_provider_env
_sync_profile_provider_env = turn_overlay._sync_profile_provider_env

# WF-032: chat_sessions re-exports
_invalidate_session_info_cache = chat_sessions._invalidate_session_info_cache
_parse_multimodal_content = chat_sessions._parse_multimodal_content
_parse_user_content_segments = chat_sessions._parse_user_content_segments
_parse_tool_content = chat_sessions._parse_tool_content
_message_row_segments = chat_sessions._message_row_segments
_llm_attribution_for_profile = chat_sessions._llm_attribution_for_profile
_latest_session_id = chat_sessions._latest_session_id
_session_info = chat_sessions._session_info
_is_blank_session_title = chat_sessions._is_blank_session_title
_resolved_session_title = chat_sessions._resolved_session_title
_ensure_hermes_session_title = chat_sessions._ensure_hermes_session_title
_session_info_display = chat_sessions._session_info_display
_latest_api_session_id = chat_sessions._latest_api_session_id
_latest_active_run_id = chat_sessions._latest_active_run_id
_session_exists = chat_sessions._session_exists
chat_session = chat_sessions.chat_session
chat_bootstrap = chat_sessions.chat_bootstrap
chat_messages = chat_sessions.chat_messages

# WF-032: docker_gateway re-exports
_UnixHTTPConnection = docker_gateway._UnixHTTPConnection
_docker_request = docker_gateway._docker_request
_docker_exec_detached = docker_gateway._docker_exec_detached
_docker_exec = docker_gateway._docker_exec
_gateway_container_exec = docker_gateway._gateway_container_exec
_gateway_container_exec_detached = docker_gateway._gateway_container_exec_detached
_gateway_exec = docker_gateway._gateway_exec
_hermes_agent_version = docker_gateway._hermes_agent_version

# WF-032: mention_invoke re-exports
_room_recent_transcript = mention_invoke._room_recent_transcript
_inject_turn_credentials = mention_invoke._inject_turn_credentials
_invoke_room_agent_mention = mention_invoke._invoke_room_agent_mention

def _enrich_room_messages(conn: sqlite3.Connection, messages: list[Any]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in messages:
        item = dict(row)
        agent_id = str(item.get("sender_agent_id") or "").strip()
        if agent_id:
            agent = conn.execute(
                "SELECT slug, display_name FROM agent_profiles WHERE id = ? AND deleted_at IS NULL",
                (agent_id,),
            ).fetchone()
            if agent:
                item["sender_agent_slug"] = str(agent["slug"])
                item["sender_agent_name"] = str(agent["display_name"] or agent["slug"])
        enriched.append(item)
    return enriched


def _enrich_room_members(conn: sqlite3.Connection, members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for member in members:
        row = dict(member)
        user_id = str(row.get("user_id") or "").strip()
        agent_id = str(row.get("agent_profile_id") or "").strip()
        if user_id:
            user = conn.execute(
                "SELECT display_name, email, avatar_url FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if user:
                row["display_name"] = user["display_name"]
                row["email"] = user["email"]
                prof = _zk.get_profile(user_id)
                zk_avatar = str(prof.get("avatar_url") or "").strip() if isinstance(prof, dict) else ""
                if zk_avatar:
                    row["avatar_url"] = _normalize_user_avatar_url(zk_avatar)
                else:
                    row["avatar_url"] = user["avatar_url"]
                row["handle"] = _mention_handle(str(user["display_name"] or ""), str(user["email"] or ""))
        if agent_id:
            agent = conn.execute(
                "SELECT slug, display_name FROM agent_profiles WHERE id = ? AND deleted_at IS NULL",
                (agent_id,),
            ).fetchone()
            if agent:
                row["display_name"] = agent["display_name"]
                row["hermes_profile"] = agent["slug"]
                label = str(agent["display_name"] or agent["slug"] or "").strip()
                row["mention_handle"] = _mention_handle(label, str(agent["slug"] or "")) or str(agent["slug"] or "")
                row["handle"] = row["mention_handle"]
        enriched.append(row)
    return enriched




def _sync_agent_profile_db(profile: str, fields: dict[str, Any]) -> None:
    """Mirror Hermes registry metadata onto workframe.db agent_profiles."""
    slug = safe_profile_slug(profile)
    if not slug or not fields:
        return
    column_map = {
        "display_name": "display_name",
        "tagline": "tagline",
        "role": "role",
        "avatar_url": "avatar_url",
    }
    updates = {column: fields[key] for key, column in column_map.items() if key in fields}
    if not updates:
        return
    conn = _workframe_db()
    try:
        now_ts = str(int(time.time()))
        sets = [f"{col} = ?" for col in updates]
        vals = list(updates.values()) + [now_ts, slug]
        conn.execute(
            f"UPDATE agent_profiles SET {', '.join(sets)}, updated_at = ? WHERE slug = ? AND deleted_at IS NULL",
            vals,
        )
        conn.commit()
    finally:
        conn.close()


def _join_workspace_default_room(
    conn: sqlite3.Connection,
    workspace_id: str,
    user_id: str,
    *,
    inviter_user_id: str | None = None,
) -> dict[str, Any]:
    room = _default_workspace_room(conn, workspace_id)
    if not room:
        return {"room_id": None, "joined": False}
    room_id = str(room["id"])
    joined = _ensure_user_in_room(conn, room_id, user_id)
    inviter_joined = False
    if inviter_user_id and inviter_user_id != user_id:
        inviter_joined = _ensure_user_in_room(conn, room_id, inviter_user_id)
    return {
        "room_id": room_id,
        "room_slug": str(room["slug"]),
        "joined": joined,
        "inviter_joined": inviter_joined,
    }


def _ensure_user_dm_room(
    conn: sqlite3.Connection,
    workspace_id: str,
    user_a: str,
    user_b: str,
) -> dict[str, Any]:
    """Idempotent DM between two workspace users (no agent)."""
    left_id, right_id = sorted([str(user_a).strip(), str(user_b).strip()])
    if not left_id or not right_id or left_id == right_id:
        return {"room_id": None, "created": False}
    existing = conn.execute(
        """
        SELECT id FROM rooms
        WHERE workspace_id = ?
          AND room_type = 'direct'
          AND deleted_at IS NULL
          AND agent_profile_id IS NULL
          AND EXISTS (
              SELECT 1 FROM room_memberships rm
              WHERE rm.room_id = rooms.id AND rm.deleted_at IS NULL AND rm.user_id = ?
          )
          AND EXISTS (
              SELECT 1 FROM room_memberships rm
              WHERE rm.room_id = rooms.id AND rm.deleted_at IS NULL AND rm.user_id = ?
          )
          AND NOT EXISTS (
              SELECT 1 FROM room_memberships rm
              WHERE rm.room_id = rooms.id AND rm.deleted_at IS NULL AND rm.user_id NOT IN (?, ?)
          )
        LIMIT 1
        """,
        (workspace_id, left_id, right_id, left_id, right_id),
    ).fetchone()
    if existing:
        return {"room_id": str(existing["id"]), "created": False}
    now = str(int(time.time()))
    room_id = str(uuid.uuid4())
    slug = _normalize_room_slug(f"dm-{left_id}-{right_id}", "dm")
    conn.execute(
        """
        INSERT INTO rooms
            (id, workspace_id, agent_profile_id, name, slug, topic, room_type, status, created_by, created_at, updated_at)
        VALUES (?, ?, NULL, ?, ?, '', 'direct', 'active', ?, ?, ?)
        """,
        (room_id, workspace_id, f"DM", slug, left_id, now, now),
    )
    for uid in (left_id, right_id):
        _ensure_user_in_room(conn, room_id, uid)
    return {"room_id": room_id, "created": True}


def _promote_workspace_owner_if_unclaimed(conn: sqlite3.Connection, workspace_id: str, user_id: str) -> bool:
    if not _install_window_open():
        return False
    row = conn.execute(
        "SELECT owner_id FROM workspaces WHERE id = ? AND deleted_at IS NULL",
        (workspace_id,),
    ).fetchone()
    if not row:
        return False
    if str(row["owner_id"] or "").strip():
        return False
    now = str(int(time.time()))
    conn.execute(
        "UPDATE workspaces SET owner_id = ?, updated_at = ? WHERE id = ?",
        (user_id, now, workspace_id),
    )
    mem = conn.execute(
        "SELECT id FROM workspace_memberships WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL",
        (workspace_id, user_id),
    ).fetchone()
    if mem:
        conn.execute(
            "UPDATE workspace_memberships SET role = ?, updated_at = ? WHERE id = ?",
            ("owner", now, mem["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO workspace_memberships
            (id, workspace_id, user_id, role, status, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (str(uuid.uuid4()), workspace_id, user_id, "owner", "active", now, now),
        )
    return True


def _sync_workspace_home_room(conn: sqlite3.Connection, workspace_id: str) -> None:
    """Keep slug=general space aligned with workspace display_name, tagline, avatar."""
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return
    ws_row = conn.execute(
        "SELECT display_name, avatar_url, settings_json FROM workspaces WHERE id = ? AND deleted_at IS NULL",
        (workspace_id,),
    ).fetchone()
    if not ws_row:
        return
    settings = _parse_workspace_settings(ws_row)
    name = str(ws_row["display_name"] or "").strip() or "Workspace"
    tagline = str(settings.get("tagline") or "").strip()
    avatar = str(ws_row["avatar_url"] or "").strip() or None
    now = str(int(time.time()))
    room = conn.execute(
        """
        SELECT id FROM rooms
        WHERE workspace_id = ? AND slug = 'general' AND deleted_at IS NULL
        """,
        (workspace_id,),
    ).fetchone()
    if room:
        conn.execute(
            """
            UPDATE rooms
            SET name = ?, topic = ?, avatar_url = COALESCE(?, avatar_url), updated_at = ?
            WHERE id = ?
            """,
            (name, tagline, avatar, now, str(room["id"])),
        )


def _ensure_default_workspace() -> bool:
    """Idempotent first-run DB seed: Workframe workspace + native agent + General room."""
    project_name = str(os.environ.get("WORKFRAME_PROJECT", "Workframe") or "Workframe").strip() or "Workframe"
    native_slug = str(NATIVE_PROFILE or "workframe-agent").strip() or "workframe-agent"
    native_display = f"{project_name} Agent"
    conn = _workframe_db()
    try:
        ws = conn.execute(
            "SELECT id FROM workspaces WHERE slug = 'default' AND deleted_at IS NULL",
        ).fetchone()
        now = str(int(time.time()))
        if not ws:
            ws_id = str(uuid.uuid4())
            settings = json.dumps({
                "credential_mode": "byok",
                "admin_onboarding_done": False,
                "admin_integrations_done": False,
            })
            ws_logo = _pick_logo_url() or None
            conn.execute(
                """
                INSERT INTO workspaces (
                    id, slug, display_name, description, owner_id, status,
                    settings_json, avatar_url, created_at, updated_at
                ) VALUES (?, 'default', ?, '', '', 'active', ?, ?, ?, ?)
                """,
                (ws_id, project_name, settings, ws_logo, now, now),
            )
        else:
            ws_id = str(ws["id"])
        ws_row = conn.execute(
            "SELECT display_name, avatar_url, settings_json FROM workspaces WHERE id = ?",
            (ws_id,),
        ).fetchone()
        settings = _parse_workspace_settings(ws_row) if ws_row else {}
        home_name = str(ws_row["display_name"] or "").strip() if ws_row else project_name
        home_name = home_name or project_name
        home_tagline = str(settings.get("tagline") or "").strip()
        home_avatar = str(ws_row["avatar_url"] or "").strip() if ws_row else ""
        if not home_avatar:
            home_avatar = _pick_logo_url() or ""
        room = conn.execute(
            """
            SELECT id FROM rooms
            WHERE workspace_id = ? AND slug = 'general' AND deleted_at IS NULL
            """,
            (ws_id,),
        ).fetchone()
        if not room:
            conn.execute(
                """
                INSERT INTO rooms (
                    id, workspace_id, name, slug, topic, avatar_url, room_type, status, created_at, updated_at
                ) VALUES (?, ?, ?, 'general', ?, ?, 'channel', 'active', ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    ws_id,
                    home_name,
                    home_tagline,
                    home_avatar or None,
                    now,
                    now,
                ),
            )
        _sync_workspace_home_room(conn, ws_id)
        conn.commit()
    finally:
        conn.close()
    _ensure_workspace_agent_profile_row(
        native_slug,
        display_name=native_display,
        role="native",
        is_native=True,
    )
    return True


def _bootstrap_after_setup(agent_personality: str = "") -> dict[str, Any]:
    """ponytail: verify native gateway after setup; optional SOUL overlay from onboarding text."""
    profile = _primary_profile()
    result: dict[str, Any] = {"profile": profile}
    personality = str(agent_personality or "").strip()
    if personality:
        _seed_native_user_overlay(profile, profile, user_soul=personality)
        result["soul_seeded"] = True
    return result






BOARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    priority TEXT DEFAULT 'medium',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_from_unix(ts: float | int | None) -> str:
    if ts is None:
        return ""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def _read_model_from_config(profile: str) -> tuple[str, str]:
    """Parse `model.default` and `model.provider` from config.yaml (gateway truth)."""
    gateway = _profile_gateway_config_path(profile)
    if gateway and gateway.is_file():
        try:
            return _parse_model_fields_from_yaml(gateway.read_text(encoding="utf-8"))
        except OSError:
            return "", ""
    meta = _profile_dir(profile) / "profile.yaml"
    if meta.is_file():
        try:
            return _parse_model_fields_from_yaml(meta.read_text(encoding="utf-8"))
        except OSError:
            pass
    return "", ""


def _ro_sqlite(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.is_file():
        return None
    # Hermes keeps state.db open â€” immutable snapshot reads work while the gateway writes.
    uri_candidates = [
        f"file:{db_path.as_posix()}?immutable=1",
        f"file://{db_path.as_posix()}?immutable=1",
        f"file:{db_path.as_posix()}?mode=ro&nolock=1",
        f"file:{db_path.as_posix()}?mode=ro",
    ]
    for uri in uri_candidates:
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=2.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=1")
            return conn
        except sqlite3.Error:
            continue
    return None


def _rw_sqlite(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.executescript(BOARD_SCHEMA)
    conn.commit()
    return conn


def _ro_sqlite_live(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.is_file():
        return None
    try:
        conn = sqlite3.connect(str(db_path), timeout=2.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=1")
        conn.execute("SELECT 1").fetchone()
        return conn
    except sqlite3.Error:
        try:
            conn.close()  # type: ignore[name-defined]
        except Exception:  # noqa: BLE001
            pass
        return _ro_sqlite(db_path)




def _resolve_bind_profile_arg(
    profile: str,
    user_id: str = "",
    room_id: str = "",
    workspace_id: str = "",
) -> tuple[str, str]:
    """Return (hermes_profile, template_profile) for chat bind/session/message paths."""
    raw = urllib.parse.unquote(str(profile or _primary_profile()).strip())
    slug = safe_profile_slug(raw)
    user_id = str(user_id or "").strip()
    room_id = str(room_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if _is_runtime_profile_slug(slug):
        template = _runtime_template_slug(slug)
        resolve_validated_profile(template)
        if room_id and user_id:
            if not workspace_id:
                try:
                    conn = _workframe_db()
                    row = conn.execute(
                        "SELECT workspace_id FROM rooms WHERE id = ? AND deleted_at IS NULL",
                        (room_id,),
                    ).fetchone()
                    conn.close()
                    if row:
                        workspace_id = str(row["workspace_id"])
                except Exception:  # noqa: BLE001
                    pass
            ensure_runtime_profile(slug, template, user_id, workspace_id)
        elif not profile_exists(slug):
            raise ValueError(f"profile not installed: {slug}")
        return slug, template
    template = resolve_validated_profile(slug)
    if room_id and user_id:
        hermes = _resolve_chat_hermes_profile(template, user_id, room_id, workspace_id)
        return hermes, template
    return template, template





_avatar_catalog_cache: dict[str, Any] | None = None


def _load_avatar_catalog() -> dict[str, Any]:
    global _avatar_catalog_cache
    if _avatar_catalog_cache is not None:
        return _avatar_catalog_cache
    fallback: dict[str, Any] = {"public_base": "/assets/avatars", "avatars": []}
    if not AVATAR_CATALOG_JSON.is_file():
        _avatar_catalog_cache = fallback
        return fallback
    try:
        data = json.loads(AVATAR_CATALOG_JSON.read_text(encoding="utf-8"))
        _avatar_catalog_cache = data if isinstance(data, dict) else fallback
    except Exception:  # noqa: BLE001
        _avatar_catalog_cache = fallback
    return _avatar_catalog_cache


def _avatar_path_from_url(avatar_url: str) -> str:
    raw = str(avatar_url or "").strip()
    if "://" in raw:
        try:
            parsed = urllib.parse.urlparse(raw)
            raw = parsed.path or raw
        except Exception:  # noqa: BLE001
            pass
    return raw.split("?", 1)[0].split("#", 1)[0]


def _catalog_url_for_id(
    catalog: dict[str, Any],
    avatar_id: str,
    *,
    items_key: str = "avatars",
    default_base: str = "/assets",
) -> str:
    avatar_id = str(avatar_id or "").strip()
    base = str(catalog.get("public_base") or default_base).rstrip("/")
    for row in catalog.get(items_key) or []:
        if isinstance(row, dict) and str(row.get("id")) == avatar_id:
            file_name = str(row.get("file") or f"{avatar_id}.png")
            return f"{base}/{file_name}"
    return f"{base}/{avatar_id}.png"


def _id_from_catalog_url(
    catalog: dict[str, Any],
    avatar_url: str,
    *,
    items_key: str = "avatars",
) -> str:
    path = _avatar_path_from_url(avatar_url)
    basename = path.rsplit("/", 1)[-1]
    if not basename:
        return ""
    rows = [row for row in catalog.get(items_key) or [] if isinstance(row, dict)]
    base = str(catalog.get("public_base") or "").rstrip("/")
    for row in rows:
        if str(row.get("file") or f"{row.get('id')}.png") == basename:
            return str(row.get("id") or "")
    if base:
        stable = re.match(rf"^{re.escape(base)}/([^/]+)\.png$", path, re.I)
        if stable:
            stem = stable.group(1)
            for row in rows:
                if str(row.get("id") or "") == stem:
                    return str(row.get("id") or "")
                file_stem = str(row.get("file") or f"{row.get('id')}.png").replace(".png", "")
                if file_stem == stem:
                    return str(row.get("id") or "")
    hashed = re.match(r"/assets/([a-z0-9]+)-[A-Za-z0-9_]+\.png$", path, re.I)
    if hashed:
        prefix = hashed.group(1)
        for row in rows:
            if str(row.get("id") or "") == prefix:
                return str(row.get("id") or "")
            file_stem = str(row.get("file") or f"{row.get('id')}.png").replace(".png", "")
            if file_stem == prefix:
                return str(row.get("id") or "")
    return ""


def _normalize_catalog_avatar_patch(
    catalog: dict[str, Any],
    avatar_url: str = "",
    avatar_id: str = "",
    *,
    items_key: str = "avatars",
    default_base: str = "/assets",
    include_id: bool = True,
) -> dict[str, str]:
    aid = str(avatar_id or "").strip()
    raw = str(avatar_url or "").strip()
    if raw.startswith("data:"):
        out = {"avatar_url": raw}
        if include_id:
            out["avatar_id"] = ""
        return out
    path = _avatar_path_from_url(raw)
    if not path and not aid:
        out = {"avatar_url": ""}
        if include_id:
            out["avatar_id"] = ""
        return out
    if not aid and path:
        aid = _id_from_catalog_url(catalog, path, items_key=items_key)
    if aid:
        stable = _catalog_url_for_id(catalog, aid, items_key=items_key, default_base=default_base)
        out = {"avatar_url": stable}
        if include_id:
            out["avatar_id"] = aid
        return out
    out = {"avatar_url": path or raw}
    if include_id:
        out["avatar_id"] = ""
    return out


def _avatar_url_for_id(avatar_id: str) -> str:
    return _catalog_url_for_id(
        _load_avatar_catalog(),
        avatar_id,
        items_key="avatars",
        default_base="/assets/avatars",
    )


def _avatar_id_from_url(avatar_url: str) -> str:
    return _id_from_catalog_url(_load_avatar_catalog(), avatar_url, items_key="avatars")


def _normalize_user_avatar_url(avatar_url: str) -> str:
    catalog = _load_preset_catalog(USER_AVATAR_CATALOG_JSON)
    return _normalize_catalog_avatar_patch(
        catalog,
        avatar_url,
        items_key="avatars",
        default_base="/assets/avatars",
        include_id=False,
    )["avatar_url"]


def _normalize_logo_url(avatar_url: str) -> str:
    catalog = _load_preset_catalog(LOGO_CATALOG_JSON)
    return _normalize_catalog_avatar_patch(
        catalog,
        avatar_url,
        items_key="logos",
        default_base="/assets/project-logos",
        include_id=False,
    )["avatar_url"]


def _normalize_agent_avatar_patch(
    avatar_url: str = "",
    avatar_id: str = "",
) -> dict[str, str]:
    """Persist stable catalog id + nginx path â€” not vite hash or absolute origin."""
    return _normalize_catalog_avatar_patch(
        _load_avatar_catalog(),
        avatar_url,
        avatar_id,
        items_key="avatars",
        default_base="/assets/avatars",
        include_id=True,
    )


_preset_catalog_cache: dict[str, dict[str, Any]] = {}


def _load_preset_catalog(path: Path) -> dict[str, Any]:
    key = str(path)
    if key in _preset_catalog_cache:
        return _preset_catalog_cache[key]
    fallback: dict[str, Any] = {"public_base": "", "avatars": [], "logos": []}
    if not path.is_file():
        _preset_catalog_cache[key] = fallback
        return fallback
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        _preset_catalog_cache[key] = data if isinstance(data, dict) else fallback
    except Exception:  # noqa: BLE001
        _preset_catalog_cache[key] = fallback
    return _preset_catalog_cache[key]


def _pick_preset_url(catalog_path: Path, *, items_key: str = "avatars") -> str:
    catalog = _load_preset_catalog(catalog_path)
    base = str(catalog.get("public_base") or "").rstrip("/")
    items = [row for row in catalog.get(items_key) or [] if isinstance(row, dict) and row.get("id")]
    if not items or not base:
        return ""
    pick = secrets.choice(items)
    file_name = str(pick.get("file") or f"{pick['id']}.png")
    return f"{base}/{file_name}"


def _pick_logo_url() -> str:
    return _pick_preset_url(LOGO_CATALOG_JSON, items_key="logos")


def _pick_user_avatar_url() -> str:
    return _pick_preset_url(USER_AVATAR_CATALOG_JSON, items_key="avatars")


def _resolve_avatar_fields(row: dict[str, Any]) -> None:
    avatar_id = str(row.get("avatar_id") or "").strip()
    if avatar_id:
        row["avatar_url"] = _avatar_url_for_id(avatar_id)
        return
    explicit = str(row.get("avatar_url") or "").strip()
    if explicit:
        row["avatar_url"] = explicit


def _load_avatar_registry() -> dict[str, Any]:
    if not AVATAR_REGISTRY_JSON.is_file():
        return {"version": 1, "weights": {}, "assignments": {}}
    try:
        data = json.loads(AVATAR_REGISTRY_JSON.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("weights", {})
            data.setdefault("assignments", {})
            return data
    except Exception:  # noqa: BLE001
        pass
    return {"version": 1, "weights": {}, "assignments": {}}


def _save_avatar_registry(data: dict[str, Any]) -> None:
    AVATAR_REGISTRY_JSON.parent.mkdir(parents=True, exist_ok=True)
    AVATAR_REGISTRY_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _pick_avatar_id() -> str:
    catalog = _load_avatar_catalog()
    avatars = [row for row in catalog.get("avatars") or [] if isinstance(row, dict) and row.get("id")]
    if not avatars:
        return "steve"
    registry = _load_avatar_registry()
    agents = load_agent_registry()
    assigned = {str(v) for v in registry.get("assignments", {}).values()}
    for row in agents.values():
        aid = str(row.get("avatar_id") or "").strip()
        if aid:
            assigned.add(aid)
    pool = [row for row in avatars if str(row["id"]) not in assigned] or avatars
    weights = registry.get("weights") or {}
    min_weight = min(int(weights.get(str(row["id"]), 0)) for row in pool)
    candidates = [row for row in pool if int(weights.get(str(row["id"]), 0)) <= min_weight]
    pick = secrets.choice(candidates)
    return str(pick["id"])


def _upsert_agent_registry_row(profile: str, patch: dict[str, Any]) -> None:
    prof_key = safe_profile_slug(profile)
    if "avatar_url" in patch or "avatar_id" in patch:
        norm = _normalize_agent_avatar_patch(
            str(patch.get("avatar_url") or ""),
            str(patch.get("avatar_id") or ""),
        )
        patch = {**patch, **norm}
    AGENTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {"version": 1, "owner_profile": _primary_profile(), "agents": {}}
    if AGENTS_JSON.is_file():
        try:
            loaded = json.loads(AGENTS_JSON.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except Exception:  # noqa: BLE001
            pass
    agents = data.setdefault("agents", {})
    current = agents.get(prof_key) if isinstance(agents.get(prof_key), dict) else {}
    agents[prof_key] = {**current, **patch, "profile": prof_key}
    data["agents"] = agents
    AGENTS_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _avatar_id_for_display_name(display_name: str) -> str:
    """Map a chosen agent name to catalog id when labels match (e.g. Ada â†’ ada)."""
    needle = str(display_name or "").strip().lower()
    if not needle:
        return ""
    for row in _load_avatar_catalog().get("avatars") or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip().lower()
        aid = str(row.get("id") or "").strip().lower()
        if needle in (label, aid):
            return str(row["id"])
    return ""


def _assign_agent_avatar(profile: str, *, display_name: str = "") -> dict[str, str]:
    """Pick catalog avatar and persist to agents.json + avatar-registry.json."""
    prof = safe_profile_slug(profile)
    native_slug = safe_profile_slug(str(NATIVE_PROFILE or "workframe-agent"))
    name = str(display_name or "").strip() or str(_agent_registry_row(prof).get("display_name") or "").strip()
    by_name = _avatar_id_for_display_name(name)
    if by_name:
        avatar_id = by_name
    elif prof == native_slug:
        avatar_id = "steve"
    else:
        avatar_id = _pick_avatar_id()
    avatar_url = _avatar_url_for_id(avatar_id)
    _upsert_agent_registry_row(
        prof,
        {
            "avatar_id": avatar_id,
            "avatar_url": avatar_url,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    registry = _load_avatar_registry()
    registry.setdefault("assignments", {})[prof] = avatar_id
    weights = registry.setdefault("weights", {})
    weights[avatar_id] = int(weights.get(avatar_id, 0)) + 1
    _save_avatar_registry(registry)
    return {"avatar_id": avatar_id, "avatar_url": avatar_url}












    return {"ok": True, "session_id": sid, "session": session, "messages": turns}













def room_chat_bind(room_id: str, payload: dict[str, Any], user_id: str = "") -> dict[str, Any]:
    """Room-scoped bind â€” identity from room.agent_profile_id, not the URL."""
    body = dict(payload or {})
    body["room_id"] = str(room_id or "").strip()
    return profile_chat_bind("", body, user_id)


def profile_chat_bind(profile: str, payload: dict[str, Any], user_id: str = "") -> dict[str, Any]:
    session = profile_chat_session(profile, payload, user_id)
    sid = str(session.get("session_id") or "").strip()
    hermes_prof = str(session.get("profile") or resolve_validated_profile(profile))
    template_prof = str(session.get("template_profile") or "").strip()
    if not template_prof:
        template_prof = (
            _runtime_template_slug(hermes_prof)
            if _is_runtime_profile_slug(hermes_prof)
            else resolve_validated_profile(profile)
        )
    workspace_id = str(session.get("workspace_id") or payload.get("workspace_id") or "").strip()
    history = chat_messages(hermes_prof, sid)
    # ponytail: cohort manifest is lazy â€” GET /api/me/cohort; bind must stay fast
    cohort: list[dict[str, Any]] = []
    display_name = (
        _runtime_display_label(user_id, template_prof, workspace_id)
        if user_id and _is_runtime_profile_slug(hermes_prof)
        else _profile_display_name(hermes_prof, workspace_id)
    )
    return {
        "ok": True,
        "profile": session.get("profile") or profile,
        "template_profile": template_prof,
        "agent_display_name": display_name,
        "cohort": cohort,
        "session_id": sid,
        "title": session.get("title") or "",
        "created": bool(session.get("created")),
        "api_port": session.get("api_port"),
        "llm_ready": bool(session.get("llm_ready")),
        "has_llm_provider": bool(session.get("has_llm_provider")),
        "messages": history.get("messages") or [],
        "session": history.get("session") or {},
    }


def _room_session_rows(conn: sqlite3.Connection, room_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT rs.*, ap.slug AS agent_slug, ap.display_name AS agent_display_name
        FROM room_sessions rs
        LEFT JOIN agent_profiles ap ON ap.id = rs.agent_profile_id
        WHERE rs.room_id = ? AND rs.deleted_at IS NULL
        ORDER BY rs.updated_at DESC, rs.created_at DESC
        """,
        (room_id,),
    ).fetchall()


def list_room_sessions(room_id: str, user_id: str) -> dict[str, Any]:
    room_id = str(room_id or "").strip()
    user_id = str(user_id or "").strip()
    if not room_id or not user_id:
        raise ValueError("room_id and user required")
    conn = _workframe_db()
    try:
        room = conn.execute(
            "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
            (room_id,),
        ).fetchone()
        if not room:
            raise ValueError("room_not_found")
        if not _user_can_access_room(conn, room_id, user_id):
            raise ValueError("room_access_denied")
        workspace_id = str(room["workspace_id"])
        rows = _room_session_rows(conn, room_id)
    finally:
        conn.close()

    sessions: list[dict[str, Any]] = []
    for row in rows:
        template_slug = str(row["agent_slug"] or "").strip()
        agent_db_id = str(row["agent_profile_id"] or "").strip()
        if not template_slug or not agent_db_id:
            continue
        sid = str(row["session_id"] or "").strip()
        try:
            hermes_prof = _resolve_chat_hermes_profile(template_slug, user_id, room_id, workspace_id)
            if not sid or not _session_exists(hermes_prof, sid):
                continue
            info = _session_info(hermes_prof, sid)
        except ValueError:
            # ponytail: skip orphaned bindings (e.g. deleted smoke-agent profiles)
            continue
        sessions.append(
            {
                "id": str(row["id"]),
                "room_id": room_id,
                "agent_profile_id": agent_db_id,
                "agent_slug": template_slug,
                "hermes_profile": hermes_prof,
                "session_id": sid,
                "title": _resolved_session_title(hermes_prof, sid, str(row["title"] or "")),
                "status": str(row["status"] or "active"),
                "message_count": int(info.get("message_count") or 0),
                "created_at": _iso_from_unix(row["created_at"]),
                "updated_at": _iso_from_unix(row["updated_at"]),
                "active": str(row["status"] or "") == "active",
            }
        )
    return {"ok": True, "room_id": room_id, "sessions": sessions}


def profile_chat_activate_room_session(
    room_id: str,
    session_id: str,
    user_id: str,
    template_prof: str = "",
    *,
    source_id: str = "ui",
    client_id: str = "default",
    binding_version: int = 0,
) -> dict[str, Any]:
    room_id = str(room_id or "").strip()
    session_id = str(session_id or "").strip()
    user_id = str(user_id or "").strip()
    if not room_id or not session_id or not user_id:
        raise ValueError("room_id, session_id, and user required")

    conn = _workframe_db()
    try:
        room = conn.execute(
            "SELECT * FROM rooms WHERE id = ? AND deleted_at IS NULL",
            (room_id,),
        ).fetchone()
        if not room:
            raise ValueError("room_not_found")
        if not _user_can_access_room(conn, room_id, user_id):
            raise ValueError("room_access_denied")
        workspace_id = str(room["workspace_id"])
        row = conn.execute(
            """
            SELECT rs.*, ap.slug AS agent_slug
            FROM room_sessions rs
            LEFT JOIN agent_profiles ap ON ap.id = rs.agent_profile_id
            WHERE rs.room_id = ? AND rs.session_id = ? AND rs.deleted_at IS NULL
            LIMIT 1
            """,
            (room_id, session_id),
        ).fetchone()
        if not row:
            raise ValueError("room_session_not_found")
        template_slug = str(template_prof or row["agent_slug"] or "").strip()
        if not template_slug:
            raise ValueError("agent_profile_not_found")
        agent_db_id = str(row["agent_profile_id"] or "").strip()
        hermes_prof = _resolve_chat_hermes_profile(template_slug, user_id, room_id, workspace_id)
        if not _session_exists(hermes_prof, session_id):
            raise ValueError("session_not_found")
        gateway_sid = str(row["gateway_session_id"] or f"api:{hermes_prof}:{session_id}").strip()
        title = str(_session_info(hermes_prof, session_id).get("title") or row["title"] or "")
        _upsert_room_session(
            conn,
            room_id=room_id,
            agent_profile_id=agent_db_id,
            session_id=session_id,
            gateway_session_id=gateway_sid,
            created_by=user_id,
            title=title,
        )
        conn.commit()
    finally:
        conn.close()

    _sync_lane_binding(
        hermes_prof,
        source_id,
        client_id,
        binding_version,
        session_id,
        gateway_sid,
    )

    if user_id:
        _reconcile_profile_llm_for_user(hermes_prof, user_id, workspace_id)
    llm_provider = _llm_billing_provider(hermes_prof, user_id=user_id, workspace_id=workspace_id)
    llm_ready = _overlay_chat_llm_env(hermes_prof, user_id, workspace_id, llm_provider)

    history = chat_messages(hermes_prof, session_id)
    cohort = ensure_user_agent_cohort(user_id, workspace_id)
    return {
        "ok": True,
        "profile": hermes_prof,
        "template_profile": template_slug,
        "agent_display_name": _runtime_display_label(user_id, template_slug, workspace_id),
        "cohort": cohort,
        "room_id": room_id,
        "session_id": session_id,
        "title": title,
        "created": False,
        "resumed": True,
        "llm_ready": llm_ready,
        "has_llm_provider": llm_ready,
        "messages": history.get("messages") or [],
        "session": history.get("session") or {},
    }





def profile_chat_message(profile: str, payload: dict[str, Any]) -> dict[str, Any]:
    source_id = str(payload.get("source_id") or "ui").strip() or "ui"
    client_id = str(payload.get("client_id") or "default").strip() or "default"
    session_id = str(payload.get("session_id") or "").strip()
    text = str(payload.get("text") or "").strip()
    if not session_id:
        raise ValueError("session_id required")
    if not text:
        raise ValueError("text required")
    payer = str(payload.get("user_id") or "").strip()
    workspace_id = str(payload.get("workspace_id") or "").strip()
    room_id = str(payload.get("room_id") or "").strip()
    hermes_prof, _template_prof = _resolve_bind_profile_arg(
        profile, payer, room_id, workspace_id,
    )
    if payer:
        _reconcile_profile_llm_for_user(hermes_prof, payer, workspace_id)
    llm_provider = _llm_billing_provider(hermes_prof, user_id=payer, workspace_id=workspace_id)
    lifecycle = ensure_profile_api(
        hermes_prof,
        payer,
        workspace_id,
    )
    turn_run_id = str(uuid.uuid4())
    try:
        if payer:
            _overlay_turn_provider_env(
                hermes_prof, payer, workspace_id, llm_provider, turn_run_id,
            )
            _overlay_turn_user_env(hermes_prof, payer, workspace_id, turn_run_id)
        turn_body = _profile_turn_payload(hermes_prof, text, room_id)
        if payer and workspace_id:
            _inject_turn_credentials(turn_body, payer, workspace_id, llm_provider)
        status, data = _profile_api_request(
            hermes_prof,
            "POST",
            f"/api/sessions/{urllib.parse.quote(session_id, safe='')}/chat",
            turn_body,
        )
        if status >= 300:
            raise ValueError(f"session chat failed: {data}")
        assistant = ""
        if isinstance(data, dict):
            msg = data.get("message")
            if isinstance(msg, dict):
                assistant = str(msg.get("content") or "")
        chat_dispatch(
            {
                "profile": hermes_prof,
                "session_id": session_id,
                "gateway_session_id": f"api:{hermes_prof}:{session_id}",
                "source_id": source_id,
                "client_id": client_id,
                "room_id": room_id,
                "user_id": payer,
                "text": text,
            }
        )
        return {
            "ok": True,
            "profile": hermes_prof,
            "session_id": session_id,
            "api_port": lifecycle["api_port"],
            "assistant": assistant,
        }
    finally:
        if payer:
            _revoke_turn_credential_lease(turn_run_id, hermes_prof)


def _enrich_room_chat_payload(payload: dict[str, Any], user_id: str) -> dict[str, Any]:
    body = dict(payload) if isinstance(payload, dict) else {}
    body["user_id"] = user_id
    room_id = str(body.get("room_id") or "").strip()
    if room_id and not str(body.get("workspace_id") or "").strip():
        try:
            conn = _workframe_db()
            row = conn.execute(
                "SELECT workspace_id FROM rooms WHERE id = ? AND deleted_at IS NULL",
                (room_id,),
            ).fetchone()
            conn.close()
            if row:
                body["workspace_id"] = str(row["workspace_id"])
        except Exception:  # noqa: BLE001
            pass
    return body














def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+)$", line.strip())
        if m:
            return m.group(1).strip()
    return fallback


def content_list() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    if not WORKSPACE.is_dir():
        return docs
    for path in sorted(WORKSPACE.rglob("*.md")):
        if not path.is_file():
            continue
        rel = path.resolve().relative_to(_workspace_root()).as_posix()
        if _workspace_protected_reason(rel):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            mtime = path.stat().st_mtime
            size = path.stat().st_size
        except OSError:
            continue
        docs.append(
            {
                "agent": "workspace",
                "filename": rel,
                "title": _extract_title(text, Path(rel).stem.replace("-", " ")),
                "modified_at": _iso_from_unix(mtime),
                "size": size,
                "path": rel,
            }
        )
    docs.sort(key=lambda d: d.get("modified_at") or "", reverse=True)
    return docs


def board_list() -> list[dict[str, Any]]:
    with _board_lock:
        conn = _rw_sqlite(BOARD_DB)
        try:
            rows = conn.execute(
                "SELECT id, title, status, priority, notes, created_at, updated_at FROM tasks ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def board_create(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("title required")
    now = _utc_now()
    task = {
        "id": str(uuid.uuid4()),
        "title": title,
        "status": str(payload.get("status") or "pending"),
        "priority": str(payload.get("priority") or "medium"),
        "notes": str(payload.get("notes") or ""),
        "created_at": now,
        "updated_at": now,
    }
    with _board_lock:
        conn = _rw_sqlite(BOARD_DB)
        try:
            conn.execute(
                "INSERT INTO tasks (id, title, status, priority, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (
                    task["id"],
                    task["title"],
                    task["status"],
                    task["priority"],
                    task["notes"],
                    task["created_at"],
                    task["updated_at"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return task


def board_update(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {"title", "status", "priority", "notes"}
    fields = {k: payload[k] for k in allowed if k in payload}
    if not fields:
        raise ValueError("no fields to update")
    fields["updated_at"] = _utc_now()
    sets = ", ".join(f"{k}=?" for k in fields)
    with _board_lock:
        conn = _rw_sqlite(BOARD_DB)
        try:
            conn.execute(f"UPDATE tasks SET {sets} WHERE id=?", (*fields.values(), task_id))
            conn.commit()
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row:
                raise ValueError("not found")
            return dict(row)
        finally:
            conn.close()


def board_delete(task_id: str) -> None:
    with _board_lock:
        conn = _rw_sqlite(BOARD_DB)
        try:
            conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            conn.commit()
        finally:
            conn.close()





# Cache installed skill names for /api/hermes/commands/exec slash routing.
_skill_name_cache: dict[str, Any] = {"names": None, "expires_at": 0.0}
_SKILL_CACHE_TTL_SECONDS = 60


def _known_skill_names() -> set[str]:
    import time
    now = time.time()
    cached = _skill_name_cache.get("names")
    if cached is not None and _skill_name_cache.get("expires_at", 0) > now:
        return cached
    try:
        names = {str(s.get("name", "")).strip() for s in hermes_skills() if s.get("name")}
    except Exception:
        names = cached or set()
    _skill_name_cache["names"] = names
    _skill_name_cache["expires_at"] = now + _SKILL_CACHE_TTL_SECONDS
    return names


def _is_known_skill(name: str) -> bool:
    if not name:
        return False
    return name in _known_skill_names()


# Static mirror of Hermes' COMMAND_REGISTRY (hermes_cli/commands.py).
# The BFF does not import hermes_agent; it serves a curated snapshot so the
# Workframe UI has a fast, local source of truth for the slash palette.
# Drift is acceptable: any new command lands here in the same release that
# updates upstream Hermes. See workframe-api dead-code note for context.
HERMES_COMMANDS: list[dict[str, Any]] = [
    # Session
    {"name": "/new", "aliases": ["/reset"], "category": "Session",
     "description": "Fresh session", "args_hint": "",
     "dispatch": "client:startNewSession"},
    {"name": "/clear", "aliases": [], "category": "Session",
     "description": "Clear screen + new session", "args_hint": "",
     "dispatch": "client:clearMessages"},
    {"name": "/retry", "aliases": [], "category": "Session",
     "description": "Resend last message", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/undo", "aliases": [], "category": "Session",
     "description": "Remove last exchange", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/compress", "aliases": [], "category": "Session",
     "description": "Manually compress context", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/stop", "aliases": [], "category": "Session",
     "description": "Kill background processes", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/rollback", "aliases": [], "category": "Session",
     "description": "Restore filesystem checkpoint", "args_hint": "[N]",
     "dispatch": "gateway"},
    {"name": "/snapshot", "aliases": [], "category": "Session",
     "description": "Create or restore state snapshots", "args_hint": "[sub]",
     "dispatch": "gateway"},
    {"name": "/background", "aliases": [], "category": "Session",
     "description": "Run prompt in background", "args_hint": "<prompt>",
     "dispatch": "gateway"},
    {"name": "/queue", "aliases": [], "category": "Session",
     "description": "Queue for next turn", "args_hint": "<prompt>",
     "dispatch": "gateway"},
    {"name": "/steer", "aliases": [], "category": "Session",
     "description": "Inject after the next tool call", "args_hint": "<prompt>",
     "dispatch": "gateway"},
    {"name": "/agents", "aliases": ["/tasks"], "category": "Session",
     "description": "Show active agents and running tasks", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/resume", "aliases": [], "category": "Session",
     "description": "Resume a named session", "args_hint": "[name]",
     "dispatch": "gateway"},
    {"name": "/goal", "aliases": [], "category": "Session",
     "description": "Set a standing goal", "args_hint": "[text|sub]",
     "dispatch": "gateway"},
    {"name": "/redraw", "aliases": [], "category": "Session",
     "description": "Force a full UI repaint", "args_hint": "",
     "dispatch": "client:noOp"},

    # Configuration
    {"name": "/model", "aliases": [], "category": "Configuration",
     "description": "Show or change model", "args_hint": "[name]",
     "dispatch": "client:openModelSwitcher"},
    {"name": "/personality", "aliases": [], "category": "Configuration",
     "description": "Set personality", "args_hint": "[name]",
     "dispatch": "client:openPersonality"},
    {"name": "/reasoning", "aliases": [], "category": "Configuration",
     "description": "Set reasoning", "args_hint": "[level]",
     "dispatch": "gateway"},
    {"name": "/verbose", "aliases": [], "category": "Configuration",
     "description": "Cycle verbose level", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/voice", "aliases": [], "category": "Configuration",
     "description": "Voice mode", "args_hint": "[on|off|tts]",
     "dispatch": "gateway"},
    {"name": "/yolo", "aliases": [], "category": "Configuration",
     "description": "Toggle approval bypass", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/busy", "aliases": [], "category": "Configuration",
     "description": "What Enter does while working", "args_hint": "[sub]",
     "dispatch": "gateway"},
    {"name": "/indicator", "aliases": [], "category": "Configuration",
     "description": "Busy indicator style", "args_hint": "[style]",
     "dispatch": "gateway"},
    {"name": "/footer", "aliases": [], "category": "Configuration",
     "description": "Gateway runtime footer on replies", "args_hint": "[on|off]",
     "dispatch": "gateway"},
    {"name": "/skin", "aliases": [], "category": "Configuration",
     "description": "Change theme (CLI)", "args_hint": "[name]",
     "dispatch": "gateway"},
    {"name": "/statusbar", "aliases": [], "category": "Configuration",
     "description": "Toggle status bar (CLI)", "args_hint": "",
     "dispatch": "gateway"},

    # Tools & Skills
    {"name": "/tools", "aliases": [], "category": "Tools & Skills",
     "description": "Manage tools", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/toolsets", "aliases": [], "category": "Tools & Skills",
     "description": "List toolsets", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/skills", "aliases": [], "category": "Tools & Skills",
     "description": "Search/install skills", "args_hint": "",
     "dispatch": "client:openSkills"},
    {"name": "/skill", "aliases": [], "category": "Tools & Skills",
     "description": "Load a skill into session", "args_hint": "<name>",
     "dispatch": "gateway"},
    {"name": "/reload-skills", "aliases": [], "category": "Tools & Skills",
     "description": "Re-scan ~/.hermes/skills/", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/reload", "aliases": [], "category": "Tools & Skills",
     "description": "Reload .env into running session", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/reload-mcp", "aliases": [], "category": "Tools & Skills",
     "description": "Reload MCP servers", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/cron", "aliases": [], "category": "Tools & Skills",
     "description": "Manage cron jobs", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/curator", "aliases": [], "category": "Tools & Skills",
     "description": "Skill lifecycle", "args_hint": "[sub]",
     "dispatch": "gateway"},
    {"name": "/kanban", "aliases": [], "category": "Tools & Skills",
     "description": "Multi-profile board", "args_hint": "[sub]",
     "dispatch": "gateway"},
    {"name": "/plugins", "aliases": [], "category": "Tools & Skills",
     "description": "List plugins", "args_hint": "",
     "dispatch": "gateway"},

    # Utility
    {"name": "/branch", "aliases": ["/fork"], "category": "Utility",
     "description": "Branch the current session", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/fast", "aliases": [], "category": "Utility",
     "description": "Toggle priority/fast processing", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/browser", "aliases": [], "category": "Utility",
     "description": "Open CDP browser connection", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/history", "aliases": [], "category": "Utility",
     "description": "Show conversation history", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/save", "aliases": [], "category": "Utility",
     "description": "Save conversation to file", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/copy", "aliases": [], "category": "Utility",
     "description": "Copy last assistant reply", "args_hint": "[N]",
     "dispatch": "gateway"},
    {"name": "/paste", "aliases": [], "category": "Utility",
     "description": "Attach clipboard image", "args_hint": "",
     "dispatch": "gateway"},
    {"name": "/image", "aliases": [], "category": "Utility",
     "description": "Attach local image file", "args_hint": "",
     "dispatch": "gateway"},

    # Info
    {"name": "/help", "aliases": [], "category": "Info",
     "description": "Show commands", "args_hint": "",
     "dispatch": "client:openHelp"},
    {"name": "/status", "aliases": [], "category": "Info",
     "description": "Session info", "args_hint": "",
     "dispatch": "client:openStatus"},
    {"name": "/usage", "aliases": [], "category": "Info",
     "description": "Token usage for the active session", "args_hint": "",
     "dispatch": "client:openUsage"},
    {"name": "/insights", "aliases": [], "category": "Info",
     "description": "Usage analytics", "args_hint": "[days]",
     "dispatch": "client:openInsights"},
    {"name": "/gquota", "aliases": [], "category": "Info",
     "description": "Google Gemini quota", "args_hint": "",
     "dispatch": "client:openGquota"},
    {"name": "/commands", "aliases": [], "category": "Info",
     "description": "Browse all commands", "args_hint": "[page]",
     "dispatch": "client:openHelp"},
    {"name": "/profile", "aliases": [], "category": "Info",
     "description": "Active profile info", "args_hint": "",
     "dispatch": "client:openProfile"},
    {"name": "/debug", "aliases": [], "category": "Info",
     "description": "Upload debug report", "args_hint": "",
     "dispatch": "client:openDebug"},

    # Exit
    {"name": "/quit", "aliases": ["/exit", "/q"], "category": "Exit",
     "description": "Exit CLI", "args_hint": "",
     "dispatch": "client:noOp"},
]


def _resolve_command(token: str) -> dict[str, Any] | None:
    """Resolve a slash token (with or without leading /) to a wired
    catalog entry. Wip commands are internal-only â€” they live in
    `HERMES_COMMANDS` for the team to track progress, but `_resolve_command`
    treats them as not-found so the user can never accidentally invoke
    something that isn't wired end-to-end.
    """
    if not token:
        return None
    needle = token if token.startswith("/") else f"/{token}"
    for entry in HERMES_COMMANDS:
        if entry.get("wip", False):
            continue
        if entry["name"] == needle or needle in entry.get("aliases", []):
            return entry
    return None




def hermes_usage() -> dict[str, Any]:
    """Token usage for the latest session of the active profile."""
    profile = _primary_profile()
    if not profile:
        return {"ok": False, "error": "no active profile"}

    session_id = _latest_session_id(profile)
    if not session_id:
        return {"ok": True, "profile": profile, "session": None}

    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    if not conn:
        return {"ok": False, "error": "state.db not reachable"}

    try:
        row = conn.execute(
            "SELECT title, model, message_count, started_at, ended_at, "
            "tool_call_count, input_tokens, output_tokens "
            "FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if not row:
            return {"ok": True, "profile": profile, "session": None}

        input_tokens = int(row["input_tokens"] or 0)
        output_tokens = int(row["output_tokens"] or 0)

        return {
            "ok": True,
            "profile": profile,
            "session": {
                "id": str(session_id)[:12] + "â€¦",
                "title": row["title"] or "(untitled)",
                "model": row["model"] or "â€”",
                "message_count": int(row["message_count"] or 0),
                "tool_call_count": int(row["tool_call_count"] or 0),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "started_at": _iso_from_unix(row["started_at"]),
                "ended_at": _iso_from_unix(row["ended_at"]) if row["ended_at"] else None,
            },
        }
    except sqlite3.Error as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def hermes_gateway_exec(
    line: str,
    profile: str = "",
    user_id: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    """Execute a slash command through the Hermes CLI.

    Runs `hermes -p {profile} {cmd}` via Docker exec in the gateway
    container. This bypasses the streaming chat endpoint â€” slash commands
    are processed synchronously by the CLI's command handler and the
    output is returned immediately.
    """
    prof = resolve_validated_profile(profile) if profile else _primary_profile()
    if not prof:
        return {"ok": False, "error": "no active profile"}

    if not _user_may_access_runtime_profile(user_id, prof, workspace_id):
        return {"ok": False, "error": "profile_access_denied", "profile": prof}

    text = (line or "").strip()
    if not text:
        return {"ok": False, "error": "empty command"}

    # Parse the command: first token is the command name (with or without
    # leading /), rest is args.
    parts = text.split(None, 1)
    cmd_token = parts[0].lstrip("/")
    cmd_args = parts[1] if len(parts) > 1 else ""

    # Build the CLI command.
    cli_args = [cmd_token]
    if cmd_args:
        cli_args.extend(cmd_args.split())

    if _exec_targets_runtime_profile_secrets(cli_args, prof) or _exec_targets_runtime_profile_secrets(
        ["hermes", "-p", prof, *cli_args], prof,
    ):
        return {"ok": False, "error": "blocked_credential_path", "profile": prof}

    run_id: str | None = None
    try:
        run_id, decision = run_surface_wiring.begin_slash_run(
            cmd_token=cmd_token,
            line=text,
            profile_slug=prof,
            user_id=user_id,
            workspace_id=workspace_id,
        )
        if decision is not None and not decision.allowed:
            return {
                "ok": False,
                "error": str(decision.deny_reason or "run_denied"),
                "run_id": run_id,
                "profile": prof,
                "command": cmd_token,
            }
    except Exception as exc:  # noqa: BLE001
        _log_handler_error("hermes_gateway_exec.run_ledger", exc)

    try:
        rc, output = _gateway_exec(prof, cli_args)
        out = output.strip() if output else ""
        if run_id:
            try:
                run_surface_wiring.finish_surface_run(run_id, ok=rc == 0, detail=out)
            except Exception as exc:  # noqa: BLE001
                _log_handler_error("hermes_gateway_exec.finish_run", exc)
        return {
            "ok": rc == 0,
            "profile": prof,
            "command": cmd_token,
            "rc": rc,
            "output": out,
            "run_id": run_id,
        }
    except Exception as exc:
        if run_id:
            try:
                run_surface_wiring.finish_surface_run(run_id, ok=False, detail=str(exc))
            except Exception as finish_exc:  # noqa: BLE001
                _log_handler_error("hermes_gateway_exec.finish_run", finish_exc)
        return {"ok": False, "error": str(exc), "run_id": run_id}




def hermes_profile() -> dict[str, Any]:
    """Active profile info for the /profile dialog."""
    profile = _primary_profile()
    if not profile:
        return {"ok": False, "error": "no active profile"}

    soul_path = _profile_soul_path(profile)
    description = ""
    if soul_path.is_file():
        try:
            text = soul_path.read_text(encoding="utf-8", errors="replace")
            for raw in text.splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                description = line[:200]
                break
        except Exception:
            description = ""

    try:
        state = gateway_data(profile)
        gateway_running = bool(state.get("ok")) and str(state.get("state") or "").lower() == "running"
    except Exception:
        gateway_running = False

    session_id = _latest_session_id(profile)
    session_info = None
    if session_id:
        try:
            info = _session_info(profile, session_id)
            session_info = {
                "id": str(session_id)[:12] + "â€¦",
                "title": info.get("session_title", ""),
                "message_count": info.get("message_count", 0),
                "model": info.get("model", ""),
            }
        except Exception:
            pass

    return {
        "ok": True,
        "profile": profile,
        "description": description,
        "gateway_running": gateway_running,
        "session": session_info,
    }


def _agent_db_row(template_slug: str, workspace_id: str = "") -> dict[str, Any]:
    template_slug = safe_profile_slug(str(template_slug or "").strip())
    if not template_slug:
        return {}
    conn = _workframe_db()
    try:
        if workspace_id:
            row = _lookup_agent_profile(conn, workspace_id, template_slug)
        else:
            row = conn.execute(
                """
                SELECT display_name, tagline, role, avatar_url
                FROM agent_profiles
                WHERE slug = ? AND deleted_at IS NULL
                ORDER BY is_native DESC, updated_at DESC
                LIMIT 1
                """,
                (template_slug,),
            ).fetchone()
        if not row:
            return {}
        return {
            "display_name": str(row["display_name"] or "").strip(),
            "tagline": str(row["tagline"] or "").strip() if "tagline" in row.keys() else "",
            "role": str(row["role"] or "").strip() if "role" in row.keys() else "",
            "avatar_url": str(row["avatar_url"] or "").strip() if "avatar_url" in row.keys() else "",
        }
    finally:
        conn.close()


def hermes_profile_detail(profile: str, workspace_id: str = "") -> dict[str, Any]:
    """Profile metadata + SOUL + model surface for a specific Hermes profile."""
    prof = resolve_validated_profile(profile)
    reg = _agent_registry_row(prof)
    db_row = _agent_db_row(prof, workspace_id)
    soul_text = _profile_soul_text(prof)
    block = _read_model_block(prof)
    try:
        state = gateway_data(prof)
        gateway_running = bool(state.get("ok")) and str(state.get("state") or "").lower() == "running"
        gateway_state = str(state.get("state") or "unknown")
    except Exception:
        gateway_running = False
        gateway_state = "unknown"
    row: dict[str, Any] = {
        "ok": True,
        "profile": prof,
        "display_name": str(
            db_row.get("display_name")
            or reg.get("display_name")
            or _profile_display_name(prof, workspace_id)
        ),
        "role": str(db_row.get("role") or reg.get("role") or _profile_role(prof)),
        "tagline": str(db_row.get("tagline") or reg.get("tagline") or ""),
        "description": str(reg.get("description") or ""),
        "soul": soul_text,
        "soul_exists": bool(soul_text),
        "gateway_running": gateway_running,
        "gateway_state": gateway_state,
        "model": block.get("default", ""),
        "provider": block.get("provider", ""),
        "is_native": _is_native_profile(prof),
    }
    avatar_url = str(db_row.get("avatar_url") or reg.get("avatar_url") or "").strip()
    if avatar_url:
        row["avatar_url"] = avatar_url
    if reg.get("avatar_id"):
        row["avatar_id"] = str(reg["avatar_id"])
    _resolve_avatar_fields(row)
    return row


def hermes_profile_update(profile: str, body: dict[str, Any]) -> dict[str, Any]:
    """Update Workframe agent registry metadata for a Hermes profile."""
    prof = resolve_validated_profile(profile)
    allowed = {"display_name", "role", "tagline", "description", "avatar_url", "avatar_id"}
    patch: dict[str, Any] = {}
    for key in allowed:
        if key not in body:
            continue
        value = body[key]
        patch[key] = str(value).strip() if value is not None else ""
    if "avatar_url" in patch:
        _validate_me_profile_updates({"avatar_url": patch["avatar_url"]})
    if not patch:
        return {"ok": False, "error": "no_allowed_fields"}
    _upsert_agent_registry_row(prof, patch)
    _sync_agent_profile_db(prof, patch)
    return {"ok": True, "profile": prof, **patch}


def profile_soul_get(profile: str) -> dict[str, Any]:
    prof = resolve_validated_profile(profile)
    text = _profile_soul_text(prof)
    path = _profile_soul_path(prof)
    return {
        "ok": True,
        "profile": prof,
        "soul": text,
        "path": str(path),
        "exists": path.is_file(),
    }


def profile_soul_set(profile: str, soul: str) -> dict[str, Any]:
    prof = resolve_validated_profile(profile)
    if _is_native_profile(prof):
        path = _profile_soul_path(prof)
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = soul if not soul or soul.endswith("\n") else f"{soul}\n"
        path.write_text(normalized, encoding="utf-8")
        return {"ok": True, "profile": prof, "bytes": len(normalized.encode("utf-8")), "target": "soul_file"}
    lookup = _runtime_template_slug(prof) if _is_runtime_profile_slug(prof) else prof
    _apply_profile_identity(lookup, user_soul=soul)
    return {"ok": True, "profile": prof, "bytes": len(soul.encode("utf-8")), "target": "user_soul_overlay"}


def hermes_debug() -> dict[str, Any]:
    """Debug info for the /debug dialog."""
    profile = _primary_profile()
    if not profile:
        return {"ok": False, "error": "no active profile"}

    import platform as plat
    import sys

    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    session_count = 0
    message_count = 0
    if conn:
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM sessions").fetchone()
            session_count = row["cnt"] if row else 0
            row = conn.execute("SELECT COUNT(*) as cnt FROM messages").fetchone()
            message_count = row["cnt"] if row else 0
        except Exception:
            pass
        finally:
            conn.close()

    return {
        "ok": True,
        "profile": profile,
        "python_version": sys.version,
        "platform": plat.platform(),
        "session_count": session_count,
        "message_count": message_count,
    }


def hermes_insights() -> dict[str, Any]:
    """Usage analytics for the /insights dialog."""
    profile = _primary_profile()
    if not profile:
        return {"ok": False, "error": "no active profile"}

    db = _profile_dir(profile) / "state.db"
    conn = _ro_sqlite_live(db)
    if not conn:
        return {"ok": False, "error": "state.db not reachable"}

    try:
        # Total tokens per day (last 7 days)
        rows = conn.execute(
            "SELECT DATE(started_at, 'unixepoch') as day, "
            "SUM(input_tokens) as input_tok, SUM(output_tokens) as output_tok, "
            "COUNT(*) as sessions "
            "FROM sessions "
            "WHERE started_at > strftime('%s', 'now', '-7 days') "
            "GROUP BY day ORDER BY day DESC"
        ).fetchall()

        daily = []
        for r in rows:
            daily.append({
                "day": r["day"] or "unknown",
                "input_tokens": int(r["input_tok"] or 0),
                "output_tokens": int(r["output_tok"] or 0),
                "sessions": int(r["sessions"] or 0),
            })

        # Model usage breakdown
        model_rows = conn.execute(
            "SELECT model, COUNT(*) as cnt, SUM(input_tokens) as input_tok "
            "FROM sessions GROUP BY model ORDER BY cnt DESC LIMIT 10"
        ).fetchall()

        models = []
        for r in model_rows:
            models.append({
                "model": r["model"] or "unknown",
                "sessions": int(r["cnt"] or 0),
                "input_tokens": int(r["input_tok"] or 0),
            })

        return {"ok": True, "profile": profile, "daily": daily, "models": models}
    except sqlite3.Error as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def hermes_gquota() -> dict[str, Any]:
    """Google Gemini quota info â€” stub until Google API is configured."""
    profile = _primary_profile()
    if not profile:
        return {"ok": False, "error": "no active profile"}
    return {
        "ok": True,
        "profile": profile,
        "configured": False,
        "message": "Google Gemini quota: not configured. Set GOOGLE_API_KEY in .env to enable.",
    }


def hermes_commands_catalog() -> dict[str, Any]:
    """Categorized slash command catalog for the Workframe composer palette.

    `wip` commands are an internal tracker â€” they exist in
    `HERMES_COMMANDS` so the team can see what's still to wire, but
    they aren't returned here. The UI never sees a half-implemented
    command; either it's wired end-to-end or it's invisible.
    """
    visible = [e for e in HERMES_COMMANDS if not e.get("wip", False)]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in visible:
        grouped.setdefault(entry["category"], []).append(
            {
                "name": entry["name"],
                "aliases": entry.get("aliases", []),
                "description": entry["description"],
                "args_hint": entry.get("args_hint", ""),
                "dispatch": entry["dispatch"],
            }
        )
    categories = [
        {"name": name, "commands": [
            (cmd["name"], cmd["description"]) for cmd in items
        ]}
        for name, items in grouped.items()
    ]
    return {
        "ok": True,
        "categories": categories,
        "entries": [
            {**entry, "wired": True}
            for entry in visible
        ],
    }


def hermes_commands_exec(line: str) -> dict[str, Any]:
    """Resolve a slash command line and return a dispatch decision for the UI.

    The BFF does not run client-side UI effects; it classifies the command
    and returns a hint. The UI executes the hint. For commands that need to
    round-trip the gateway (`/auth`, `/config`, etc.) the BFF returns a
    `gateway` dispatch and the UI calls a separate gateway proxy endpoint.

    Skills (`/skillname` where the skill is installed in Hermes) aren't in
    the static catalog. The BFF falls back to a skill-name lookup so the
    UI gets a clean "this is dispatchable" decision rather than "unknown
    command" for every installed skill.
    """
    raw = (line or "").strip()
    if not raw.startswith("/"):
        return {"ok": False, "error": "not a slash command", "line": raw}
    parts = raw.split(maxsplit=1)
    token = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    entry = _resolve_command(token)
    if entry is None:
        # Fallback: is this an installed skill? Skills route through
        # the gateway once the gateway hookup lands (Slice 2). For now
        # the UI gets a `gateway` dispatch so the user sees the same
        # "real command, gateway side not wired yet" hint as the other
        # gateway-class commands.
        skill_name = token.lstrip("/")
        if _is_known_skill(skill_name):
            return {
                "ok": True,
                "dispatched": "gateway",
                "command": token,
                "args": rest,
                "message": f"Skill: {skill_name} â€” gateway dispatch coming in Slice 2",
            }
        return {
            "ok": False,
            "error": f"unknown command: {token}",
            "suggestion": "/help",
        }
    dispatch = entry["dispatch"]
    if dispatch == "noop":
        return {
            "ok": True,
            "dispatched": "noop",
            "command": entry["name"],
            "args": rest,
            "message": "Not yet wired in Workframe â€” see M2 in the Workframe roadmap.",
        }
    if dispatch.startswith("client:"):
        return {
            "ok": True,
            "dispatched": "client",
            "command": entry["name"],
            "args": rest,
            "handler": dispatch.split(":", 1)[1],
        }
    if dispatch.startswith("bff:"):
        return {
            "ok": True,
            "dispatched": "bff",
            "command": entry["name"],
            "args": rest,
            "handler": dispatch.split(":", 1)[1],
        }
    return {
        "ok": True,
        "dispatched": "gateway",
        "command": entry["name"],
        "args": rest,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "WorkframeAPI/0.1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def do_OPTIONS(self) -> None:  # noqa: N802
        cors_origin = _cors_origin_for(self.headers)
        if not DEV_LOCAL_UNSAFE and not cors_origin:
            self.send_response(405)
            for name, value in self._security_headers():
                self.send_header(name, value)
            self.end_headers()
            return
        self.send_response(204)
        for name, value in self._security_headers():
            self.send_header(name, value)
        self.send_header("Access-Control-Allow-Origin", cors_origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        try:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            cors_origin = _cors_origin_for(self.headers)
            if cors_origin:
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            # Client disconnected before the response could be completed.
            return

    def _json(self, code: int, payload: Any, extra_headers: list[tuple[str, str]] | None = None) -> None:
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            for name, value in self._security_headers():
                self.send_header(name, value)
            cors_origin = _cors_origin_for(self.headers)
            if cors_origin:
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Vary", "Origin")
            if extra_headers:
                for name, value in extra_headers:
                    self.send_header(name, value)
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}

    # ------------------------------------------------------------------
    # Security headers (Sprint B: helmet equivalent)
    # ------------------------------------------------------------------
    def _security_headers(self) -> list[tuple[str, str]]:
        """Return security headers for every response."""
        headers = [
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Referrer-Policy", "strict-origin-when-cross-origin"),
        ]
        if SECURE_MODE:
            headers += [
                ("Strict-Transport-Security", "max-age=31536000; includeSubDomains"),
                ("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'"),
            ]
        return headers

    # ------------------------------------------------------------------
    # Audit logging (Sprint B: mutation audit)
    # ------------------------------------------------------------------
    def _log_audit(self, event_type: str, target_type: str = "", target_id: str = "",
                   summary: str = "", metadata: dict | None = None) -> None:
        """Append an audit event to the audit_events table."""
        try:
            uid = str(uuid.uuid4())
            user_id = str(getattr(self, "auth_user", "") or "")
            ip = self.client_address[0] if self.client_address else ""
            now_ts = int(time.time())
            conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
            conn.execute(
                """INSERT INTO audit_events
                   (id, user_id, event_type, target_type, target_id, summary, metadata, ip_address, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (uid, user_id, event_type, target_type, target_id, summary,
                 json.dumps(metadata or {}), ip, now_ts),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # audit logging must never block the response

    def _file_public(self, rel: str) -> None:
        safe = Path(rel.lstrip("/"))
        if ".." in safe.parts:
            self._json(403, {"error": "forbidden"})
            return
        path = PUBLIC_DIR / safe
        if not path.is_file():
            self._json(404, {"error": "not found"})
            return
        ctype = "text/html; charset=utf-8"
        if path.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        elif path.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        self._send(200, path.read_bytes(), ctype)

    def _handle_internal_llm_proxy(self, method: str, path: str) -> bool:
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
            resolve_secret=_resolve_secret_for_lease,
        )

    def _handle_internal_action_proxy(self, method: str, path: str) -> bool:
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
            resolve_secret=_resolve_secret_for_lease,
        )

    def _handle_internal_run_record(self, path: str) -> bool:
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
            _log_handler_error("internal.runs.record", exc)
            self._json(500, {"ok": False, "error": str(exc)})
        return True

    # WF-037 data-read GET handlers (registered in route_registry.ROUTES)
    def _route_get_meta(self, qs: dict[str, list[str]]) -> None:
        self._json(200, workframe_meta())

    def _route_get_health(self, qs: dict[str, list[str]]) -> None:
        vault_stat = credential_vault.vault_status()
        self._json(
            200,
            {
                "ok": True,
                "version": VERSION,
                "mode": "dev_unsafe" if DEV_LOCAL_UNSAFE else "secure",
                "secure_mode": SECURE_MODE,
                "deployment_mode": DEPLOYMENT_MODE,
                "admin_updates_enabled": os.environ.get("WORKFRAME_ENABLE_ADMIN_UPDATES") == "1",
                "docker_sock_on_api": Path("/var/run/docker.sock").exists(),
                "proxy_token_configured": internal_proxy_auth.proxy_token_configured(),
                "vault_sealed": vault_stat.get("sealed"),
                "vault_envelope": not vault_stat.get("sealed"),
                "install_window_open": _install_window_open(),
                "workframe_e2e": os.environ.get("WORKFRAME_E2E") == "1",
                "dev_local_unsafe": DEV_LOCAL_UNSAFE,
            },
        )

    def _route_get_setup_status(self, qs: dict[str, list[str]]) -> None:
        try:
            db = _workframe_db()
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

    def _route_get_install_status(self, qs: dict[str, list[str]]) -> None:
        if install_api.install_window_open(str(_workframe_db_path())):
            try:
                _ensure_native_hermes_profile()
            except Exception:
                pass
        payload = install_api.install_status_payload(
            DEPLOYMENT_MODE,
            SECURE_MODE,
            DEV_LOCAL_UNSAFE,
            str(_workframe_db_path()),
        )
        self._json(200, payload)

    def _route_get_public_site_meta(self, qs: dict[str, list[str]]) -> None:
        self._json(200, _public_site_meta_payload())

    def _route_get_public_link_preview(self, qs: dict[str, list[str]]) -> None:
        meta = _public_site_meta_payload()
        html = site_meta.link_preview_html(meta).encode("utf-8")
        self._send(200, html, "text/html; charset=utf-8")

    def _route_get_public_manifest(self, qs: dict[str, list[str]]) -> None:
        meta = _public_site_meta_payload()
        body = json.dumps(site_meta.manifest_payload(meta), indent=2).encode("utf-8")
        self._send(200, body, "application/manifest+json; charset=utf-8")

    def _route_get_me_cohort(self, qs: dict[str, list[str]]) -> None:
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        workspace_id = str(qs.get("workspace_id", [""])[0] or "").strip()
        if not workspace_id:
            self._json(400, {"ok": False, "error": "workspace_id_required"})
            return
        ws_id = _resolve_wid(workspace_id) or workspace_id
        if not _user_is_workspace_member(user_id, ws_id):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        cohort = ensure_user_agent_cohort(user_id, ws_id)
        self._json(
            200,
            {
                "ok": True,
                "workspace_id": ws_id,
                "user_id": user_id,
                "cohort": cohort,
            },
        )

    def _route_get_user_credentials(self, qs: dict[str, list[str]]) -> None:
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            if DEV_LOCAL_UNSAFE:
                user_id = "dev"
            else:
                self._json(401, {"ok": False, "error": "no_authenticated_user"})
                return
        try:
            conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            creds = conn.execute(
                "SELECT id, workspace_id, user_id, agent_profile_id, provider, credential_type, label, is_active, created_at, updated_at FROM credential_bindings WHERE user_id = ? AND deleted_at IS NULL ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            conn.close()
        except Exception:
            creds = []
        self._json(200, {"ok": True, "credentials": [dict(c) for c in creds]})

    def _route_get_agents(self, qs: dict[str, list[str]]) -> None:
        self._json(200, workframe_agents())

    def _route_get_snapshot(self, qs: dict[str, list[str]]) -> None:
        self._json(200, build_snapshot())

    def _route_get_activity_detail(self, qs: dict[str, list[str]]) -> None:
        profile = qs.get("profile", [""])[0].strip()
        tool_call_id = qs.get("tool_call_id", [""])[0].strip()
        session_id = qs.get("session_id", [""])[0].strip()
        message_id = qs.get("message_id", [""])[0].strip()
        self._json(200, activity_detail(profile, tool_call_id, session_id, message_id))

    def _route_get_board(self, qs: dict[str, list[str]]) -> None:
        self._json(200, board_list())

    def _route_get_content(self, qs: dict[str, list[str]]) -> None:
        self._json(200, content_list())

    def _route_get_content_get(self, qs: dict[str, list[str]]) -> None:
        rel = qs.get("path", [""])[0]
        reason = _workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        fp = _safe_content_path(rel)
        if not fp or not fp.is_file():
            self._json(404, {"error": "not found"})
            return
        text = fp.read_text(encoding="utf-8", errors="replace")
        self._json(200, {"path": rel, "content": text, "text": text})

    def _route_get_files_tree(self, qs: dict[str, list[str]]) -> None:
        self._json(200, {"root": files_tree()})

    def _route_get_files_list(self, qs: dict[str, list[str]]) -> None:
        rel = qs.get("path", [""])[0]
        reason = _workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        self._json(200, files_list(rel))

    def _route_get_files_state(self, qs: dict[str, list[str]]) -> None:
        self._json(200, workspace_state())

    def _route_get_files_read(self, qs: dict[str, list[str]]) -> None:
        rel = qs.get("path", [""])[0]
        reason = _workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        self._json(200, file_read(rel))

    def _route_get_files_raw(self, qs: dict[str, list[str]]) -> None:
        rel = qs.get("path", [""])[0]
        reason = _workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        try:
            data, mime = file_raw(rel)
        except ValueError:
            self._json(404, {"error": "not found"})
            return
        self._send(200, data, mime)

    def _route_pattern_get_files_workspace(self, path: str, qs: dict[str, list[str]]) -> None:
        prefix = "/api/files/workspace/"
        if not path.startswith(prefix):
            self._json(404, {"error": "not found"})
            return
        rel = urllib.parse.unquote(path[len(prefix) :].lstrip("/"))
        reason = _workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        try:
            data, mime = file_raw(rel)
        except ValueError:
            self._json(404, {"error": "not found"})
            return
        self._send(200, data, mime)

    def _route_get_routes(self, qs: dict[str, list[str]]) -> None:
        self._json(200, load_routes())

    def _route_get_chat_messages(self, qs: dict[str, list[str]]) -> None:
        profile = resolve_hermes_profile(qs.get("profile", [""])[0] or _primary_profile())
        session = qs.get("session", [""])[0]
        source_id = qs.get("source", ["ui"])[0]
        self._json(200, chat_messages(profile, session, source_id))

    def _route_get_chat_session(self, qs: dict[str, list[str]]) -> None:
        profile = resolve_hermes_profile(qs.get("profile", [""])[0] or _primary_profile())
        session = qs.get("session", [""])[0]
        source_id = qs.get("source", ["ui"])[0]
        self._json(200, chat_session(profile, session, source_id))

    def _route_get_chat_resolve(self, qs: dict[str, list[str]]) -> None:
        profile = resolve_validated_profile(qs.get("profile", [""])[0] or _primary_profile())
        source_id = qs.get("source", ["ui"])[0]
        client_id = qs.get("client", ["default"])[0]
        self._json(
            200,
            chat_resolve({"profile": profile, "source_id": source_id, "client_id": client_id}),
        )

    def _route_get_hermes_skills(self, qs: dict[str, list[str]]) -> None:
        self._json(200, {"skills": hermes_skills()})

    def _route_get_hermes_commands(self, qs: dict[str, list[str]]) -> None:
        self._json(200, hermes_commands_catalog())

    def _route_get_hermes_usage(self, qs: dict[str, list[str]]) -> None:
        self._json(200, hermes_usage())

    def _route_get_hermes_profile(self, qs: dict[str, list[str]]) -> None:
        self._json(200, hermes_profile())

    def _route_get_me(self, qs: dict[str, list[str]]) -> None:
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        payload = _session_profile_payload(user_id)
        if not payload:
            self._json(404, {"ok": False, "error": "user_not_found"})
            return
        self._json(200, payload)

    def _route_get_me_onboarding(self, qs: dict[str, list[str]]) -> None:
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        self._json(200, _onboarding_payload(user_id))

    def _route_get_me_credentials(self, qs: dict[str, list[str]]) -> None:
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        try:
            conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
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
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        workspace_id = qs.get("workspace_id", [""])[0]
        self._json(200, list_user_providers(user_id, workspace_id))

    def _route_get_hermes_models(self, qs: dict[str, list[str]]) -> None:
        profile = qs.get("profile", [""])[0]
        user_id = str(getattr(self, "auth_user", "") or "")
        workspace_id = qs.get("workspace_id", [""])[0]
        selection_only = qs.get("selection_only", ["0"])[0] in {"1", "true", "yes"}
        payload = hermes_models(profile, user_id, workspace_id, selection_only=selection_only)
        status = 200 if payload.get("ok", True) else 400
        self._json(status, payload)

    def _route_get_hermes_debug(self, qs: dict[str, list[str]]) -> None:
        self._json(200, hermes_debug())

    def _route_get_hermes_insights(self, qs: dict[str, list[str]]) -> None:
        self._json(200, hermes_insights())

    def _route_get_hermes_gquota(self, qs: dict[str, list[str]]) -> None:
        self._json(200, hermes_gquota())

    # WF-037 auth-flow + hermes/chat + me credentials POST handlers
    def _route_post_auth_google_start(self, body: dict) -> None:
        invite_email = str(body.get("email") or "").strip().lower()
        invite_token = str(body.get("invite_token") or "")
        if invite_email:
            allowed, deny_meta = _email_allowed_to_authenticate(invite_email)
            if not allowed and not _invite_token_allows_email(invite_token, invite_email):
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
        if DEPLOYMENT_MODE != "single_user_local" or not _install_window_open():
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
            _log_handler_error("POST /api/auth/local-bootstrap", exc)
            self._json(500, {"ok": False, "error": str(exc)})
            return
        user_id = str(result["user_id"])
        self.auth_user = user_id
        self._ensure_user(user_id, display, email)
        self._first_owner_bootstrap(user_id, display, email)
        use_secure = _session_cookie_secure()
        cookie_val = _zk.session_cookie_value(result["session_id"], secure=use_secure)
        me_payload = _session_profile_payload(user_id)
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
        if not SECURE_MODE:
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
        data = body if isinstance(body, dict) else {}
        agent_name = str(data.get("agent_name", "")).strip()
        workframe_name = str(data.get("workframe_name", "")).strip()
        if not agent_name:
            self._json(400, {"ok": False, "error": "agent_name required"})
            return
        try:
            db = _workframe_db()
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
            hermes = _bootstrap_after_setup(str(data.get("agent_personality", "")))
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
        email = str(body.get("email", "")).strip().lower()
        if not email or "@" not in email:
            self._json(400, {"ok": False, "error": "email required"})
            return
        client_ip = str(self.client_address[0] if self.client_address else "")
        import auth_rate_limit

        if not auth_rate_limit.allow_auth_request("start", client_ip, email):
            self._json(429, {"ok": False, "error": "too_many_requests"})
            return
        allowed, deny_meta = _email_allowed_to_authenticate(email)
        if not allowed:
            self._log_audit("login_denied_private", "user", email, str(deny_meta.get("error") or ""))
            self._json(403, {"ok": False, **deny_meta})
            return
        try:
            base = APP_BASE_URL.strip().lower()
            loopback = base.startswith("http://127.0.0.1") or base.startswith("http://localhost")
            expose_otp = (
                os.environ.get("WORKFRAME_E2E") == "1"
                and _install_window_open()
                and loopback
            )
            result = _zk.start_email_verification(
                email,
                dev_local_unsafe=DEV_LOCAL_UNSAFE,
                expose_otp=expose_otp,
            )
        except (RuntimeError, OSError, sqlite3.Error) as exc:
            _log_handler_error("POST /api/auth/start", exc)
            self._json(500, {"ok": False, "error": str(exc)})
            return
        if not DEV_LOCAL_UNSAFE and not expose_otp:
            result.pop("otp_code", None)
            result.pop("_dev_warning", None)
        result.pop("_e2e_warning", None)
        self._log_audit("otp_requested", "user", email, f"challenge={result.get('challenge_id','')}")
        self._json(200, {"ok": True, "status": "verification_sent", **result})

    def _route_post_auth_verify(self, body: dict) -> None:
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
        allowed, deny_meta = _email_allowed_to_authenticate(email)
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
            _log_handler_error("POST /api/auth/verify", exc)
            self._json(500, {"ok": False, "error": str(exc)})
            return
        use_secure = _session_cookie_secure()
        cookie_val = _zk.session_cookie_value(result["session_id"], secure=use_secure)
        self.auth_user = result["user_id"]
        self._ensure_user(result["user_id"], email, email)
        if _install_window_open():
            stack_config.mark_install_admin_verified(email)
        self._log_audit("login", "session", result["session_id"],
                        f"user={result['user_id']} new={result['is_new_user']}")
        me_payload = _session_profile_payload(result["user_id"])
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
        sid = _session_id_from_request(self)
        user_id = str(getattr(self, "auth_user", "") or "")
        if sid:
            try:
                _zk.logout_session(sid)
            except (RuntimeError, OSError, sqlite3.Error) as exc:
                _log_handler_error("POST /api/auth/logout", exc)
        use_secure = _session_cookie_secure()
        cookie_val = _zk.clear_session_cookie(secure=use_secure)
        self._log_audit("logout", "session", sid, f"user={user_id}")
        self._json(200, {"ok": True}, extra_headers=[("Set-Cookie", cookie_val)])

    def _route_post_auth_refresh(self, body: dict) -> None:
        refresh_token = str(body.get("refresh_token", "")).strip()
        if not refresh_token:
            sid = _session_id_from_request(self)
            if not sid:
                self._json(400, {"ok": False, "error": "refresh_token required"})
                return
            validated = _zk.validate_session_token(sid)
            if not validated:
                self._json(401, {"ok": False, "error": "session_expired"})
                return
            use_secure = _session_cookie_secure()
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
            _log_handler_error("POST /api/auth/refresh", exc)
            self._json(500, {"ok": False, "error": str(exc)})
            return
        use_secure = _session_cookie_secure()
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

    def _route_post_me_credentials(self, body: dict) -> None:
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        provider = str(body.get("provider", "")).strip()
        credential_type = str(body.get("credential_type", "api_key")).strip() or "api_key"
        secret = str(body.get("secret", "")).strip()
        spec = _catalog_provider(provider)
        if spec:
            credential_type = str(spec.get("connect_mode") or credential_type)
        env_var = str(body.get("env_var", "")).strip() or (
            str(spec.get("env_var") or "") if spec else ""
        ) or _default_credential_env_var(provider, credential_type)
        label = str(body.get("label", "")).strip() or env_var
        if not provider:
            self._json(400, {"ok": False, "error": "provider required"})
            return
        if not secret:
            self._json(400, {"ok": False, "error": "secret required"})
            return
        payload = _store_user_credential(user_id, provider, credential_type, secret, env_var, label)
        cred_ref = str(payload["credential_ref"])
        now = _utc_now()
        try:
            conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
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
        self._log_audit("credential_stored", "credential_binding", cred_id, f"provider={provider}")
        health: dict[str, Any] = {}
        if provider == "openrouter":
            secret_probe = _credential_secret(
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
            _bootstrap_model_after_llm_connect(user_id, str(body.get("workspace_id") or ""), provider)
        except (OSError, RuntimeError, ValueError) as exc:
            _log_handler_error("POST /api/me/credentials provider bootstrap", exc)
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
            _merge_user_platform_ids(user_id, {str(k): str(v) for k, v in patch.items()})
        self._json(200, {"ok": True, "provider": "telegram", "platform_ids": patch})

    def _route_post_hermes_commands_exec(self, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        line = str(body.get("line", "")).strip()
        if not line:
            self._json(400, {"error": "line required"})
            return
        self._json(200, hermes_commands_exec(line))

    def _route_post_hermes_gateway_exec(self, body: dict) -> None:
        if not _check_auth(self):
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
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        profile = resolve_validated_profile(str(body.get("profile") or _primary_profile()))
        run_id = str(body.get("run_id") or "").strip()
        if not run_id:
            run_id = _latest_active_run_id(profile)
        if not run_id:
            self._json(400, {"error": "no active run to stop"})
            return
        self._json(200, profile_gateway_stop(profile, run_id))

    def _route_post_chat_steer(self, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        profile = resolve_validated_profile(str(body.get("profile") or _primary_profile()))
        run_id = str(body.get("run_id") or "").strip()
        text = str(body.get("text") or "").strip()
        if not text:
            self._json(400, {"error": "text required"})
            return
        if not run_id:
            run_id = _latest_active_run_id(profile)
        self._json(200, profile_gateway_steer(profile, run_id or "", text))

    def _route_post_hermes_model(self, body: dict) -> None:
        if not _check_auth(self):
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
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        self._json(200, hermes_apply_default_model_config())

    def _route_post_hermes_fallback_chain(self, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        profile = str(body.get("profile", "")).strip()
        chain = body.get("chain", [])
        selection_only = bool(body.get("selection_only"))
        user_id = str(getattr(self, "auth_user", "") or "")
        if not isinstance(chain, list):
            self._json(400, {"error": "chain must be a list"})
            return
        if not selection_only and not _role_allows(self, OWNER_ADMIN_ROLES):
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

    def _route_post_board(self, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        self._json(201, board_create(body))

    def _route_post_board_update(self, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        qs = getattr(self, "_post_qs", {})
        task_id = qs.get("id", [""])[0]
        if not task_id:
            self._json(400, {"error": "id required"})
            return
        self._json(200, board_update(task_id, body))

    def _route_post_board_delete(self, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        qs = getattr(self, "_post_qs", {})
        task_id = qs.get("id", [""])[0]
        if not task_id:
            self._json(400, {"error": "id required"})
            return
        board_delete(task_id)
        self._json(200, {"ok": True})

    def _route_post_content_save(self, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        rel = str(body.get("path") or "").strip()
        reason = _workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        content = str(body.get("content") or "")
        fp = _safe_content_path(rel)
        if not fp:
            self._json(400, {"error": "invalid path"})
            return
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        _bump_workspace_state(fp)
        self._json(200, {"ok": True, "path": rel.replace("\\", "/")})

    def _route_post_content_delete(self, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        qs = getattr(self, "_post_qs", {})
        rel = qs.get("path", [""])[0] or str(body.get("path") or "")
        reason = _workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        fp = _safe_content_path(rel)
        if not fp or not fp.is_file():
            self._json(404, {"error": "not found"})
            return
        fp.unlink()
        _bump_workspace_state(fp.parent)
        self._json(200, {"ok": True})

    def _route_post_files_write(self, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        rel = str(body.get("path") or "").strip()
        reason = _workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        content = str(body.get("content") or "")
        self._json(200, file_write(rel, content))

    def _route_post_files_upload(self, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        rel = str(body.get("path") or "").strip()
        reason = _workspace_protected_reason(rel)
        if reason:
            self._json(403, {"ok": False, "error": "protected_file", "reason": reason})
            return
        content_b64 = str(body.get("content_base64") or body.get("content") or "")
        self._json(200, file_upload_binary(rel, content_b64))

    def _route_post_chat_dispatch(self, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        self._json(200, chat_dispatch(body))

    # WF-037 admin/install/oauth GET handlers (batch 2)
    def _route_get_admin_vault_status(self, qs: dict[str, list[str]]) -> None:
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        self._json(200, {"ok": True, **credential_vault.vault_status()})

    def _route_get_doctor_agent_dm_runtimes(self, qs: dict[str, list[str]]) -> None:
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        self._json(200, doctor_audit_agent_dm_runtimes())

    def _route_get_admin_updates(self, qs: dict[str, list[str]]) -> None:
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        desktop_version = str((qs.get("desktop_version") or [""])[0] or "").strip()
        try:
            self._json(
                200,
                stack_updates.updates_available(
                    desktop_version=desktop_version,
                    hermes_agent_version=_hermes_agent_version(),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"ok": False, "error": str(exc)})

    def _route_get_auth_hermes_dashboard_gate(self, qs: dict[str, list[str]]) -> None:
        status = _hermes_dashboard_gate_status(self)
        if status == 204:
            self.send_response(204)
            self.end_headers()
            return
        self._json(403, {"ok": False, "error": "dashboard_forbidden"})

    def _route_get_install_stack(self, qs: dict[str, list[str]]) -> None:
        if not _install_window_open() and not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        payload = stack_config.public_stack_payload()
        payload["wizard"] = install_api.install_wizard_public_payload(str(_workframe_db_path()))
        self._json(200, {"ok": True, **payload})

    def _route_get_install_url_test(self, qs: dict[str, list[str]]) -> None:
        if not _install_window_open():
            self._json(403, {"ok": False, "error": "install_closed"})
            return
        url = (qs.get("url") or [""])[0] or stack_config.get_stack_config().get("app_base_url") or ""
        self._json(200, install_api.url_test(str(url)))

    def _route_get_install_publish_hints(self, qs: dict[str, list[str]]) -> None:
        if not _install_window_open():
            self._json(403, {"ok": False, "error": "install_closed"})
            return
        url = (qs.get("url") or [""])[0] or stack_config.get_stack_config().get("app_base_url") or ""
        self._json(200, install_api.publish_hints_payload(str(url)))

    def _route_get_auth_google_callback(self, qs: dict[str, list[str]]) -> None:
        code = (qs.get("code") or [""])[0]
        state = (qs.get("state") or [""])[0]
        if not code or not state:
            self._json(400, {"ok": False, "error": "missing code or state"})
            return
        try:
            profile = google_auth.exchange_google_code(code, state)
            invite_token = str(profile.get("invite_token") or "")
            allowed, deny_meta = _email_allowed_to_authenticate(profile["email"])
            if not allowed and not _invite_token_allows_email(invite_token, profile["email"]):
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
            use_secure = _session_cookie_secure()
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
            cors_origin = _cors_origin_for(self.headers)
            if cors_origin:
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
        except (RuntimeError, OSError, ValueError) as exc:
            _log_handler_error("GET /api/auth/google/callback", exc)
            self._json(401, {"ok": False, "error": str(exc)})

    def _route_get_oauth_github_callback(self, qs: dict[str, list[str]]) -> None:
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        code = qs.get("code", [""])[0]
        state = qs.get("state", [""])[0]
        result = _complete_github_oauth(user_id, str(code or ""), str(state or ""))
        status = "ok" if result.get("ok") else "error"
        message = urllib.parse.quote(str(result.get("error") or "connected"))
        location = f"{APP_BASE_URL.rstrip('/')}/?provider_connect=github&status={status}&message={message}"
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def _route_get_oauth_discord_callback(self, qs: dict[str, list[str]]) -> None:
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        code = qs.get("code", [""])[0]
        state = qs.get("state", [""])[0]
        result = _complete_discord_oauth(user_id, str(code or ""), str(state or ""))
        status = "ok" if result.get("ok") else "error"
        message = urllib.parse.quote(str(result.get("error") or "connected"))
        location = f"{APP_BASE_URL.rstrip('/')}/?provider_connect=discord&status={status}&message={message}"
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def _route_get_oauth_stripe_callback(self, qs: dict[str, list[str]]) -> None:
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        code = qs.get("code", [""])[0]
        state = qs.get("state", [""])[0]
        result = _complete_stripe_oauth(user_id, str(code or ""), str(state or ""))
        status = "ok" if result.get("ok") else "error"
        message = urllib.parse.quote(str(result.get("error") or "connected"))
        location = f"{APP_BASE_URL.rstrip('/')}/?provider_connect=stripe&status={status}&message={message}"
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    # WF-037 admin/install POST handlers (batch 2)
    def _route_post_install_email_test(self, body: dict) -> None:
        if not _install_window_open():
            self._json(403, {"ok": False, "error": "install_closed"})
            return
        if not _install_owner_session_ok(self):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        try:
            to_email = str(body.get("email", "")).strip()
            result = install_api.smtp_test_send(to_email)
            self._json(200, result)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc), "hint": install_api.smtp_error_hint(exc)})
        except Exception as exc:
            self._json(500, {"ok": False, "error": str(exc), "hint": install_api.smtp_error_hint(exc)})

    def _route_post_install_url_test(self, body: dict) -> None:
        if not _install_window_open():
            self._json(403, {"ok": False, "error": "install_closed"})
            return
        url = str(body.get("url") or body.get("app_base_url") or "").strip()
        self._json(200, install_api.url_test(url))

    def _route_post_install_setup_https(self, body: dict) -> None:
        if not _install_window_open():
            self._json(403, {"ok": False, "error": "install_closed"})
            return
        try:
            host, port = install_api.normalize_setup_https(
                str(body.get("host") or body.get("url") or body.get("app_base_url") or ""),
                body.get("port"),
            )
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        if not _supervisor_ready():
            self._json(503, {"ok": False, "error": "supervisor_unavailable"})
            return
        status, data = _supervisor_request(
            "POST",
            "/v1/host.setup_public_https",
            {"host": host, "port": port},
            timeout=600.0,
        )
        if status < 400:
            sync = _maybe_sync_compose_public_url(f"https://{host}")
            if isinstance(data, dict) and sync:
                data = {**data, "compose_sync": sync}
        self._json(status, data if isinstance(data, dict) else {"ok": False, "error": "invalid_response"})

    def _route_post_install_complete(self, body: dict) -> None:
        user_id = str(getattr(self, "auth_user", "") or "").strip()
        if not user_id and DEPLOYMENT_MODE != "single_user_local":
            self._json(401, {"ok": False, "error": "no_session"})
            return
        self._json(200, self._complete_install(user_id, body))

    def _route_post_install_stack_branding_asset(self, body: dict) -> None:
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        kind = str(body.get("kind") or "").strip().lower()
        if kind not in {"og", "favicon"}:
            self._json(400, {"ok": False, "error": "invalid_kind"})
            return
        raw_b64 = str(body.get("data_base64") or "").strip()
        if raw_b64.startswith("data:"):
            header, _, encoded = raw_b64.partition(",")
            content_type = header.split(";")[0].replace("data:", "").strip()
            raw_b64 = encoded
        else:
            content_type = str(body.get("content_type") or "").strip()
        try:
            data = base64.b64decode(raw_b64, validate=False)
        except Exception:
            self._json(400, {"ok": False, "error": "invalid_base64"})
            return
        try:
            site_meta.save_branding_asset(kind, data, content_type)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        meta = _public_site_meta_payload()
        self._json(
            200,
            {
                "ok": True,
                "kind": kind,
                "og_image": meta.get("og_image"),
                "favicon": meta.get("favicon"),
            },
        )

    def _route_post_admin_updates_apply(self, body: dict) -> None:
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        if not _admin_write_allowed(self):
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
            result = _apply_stack_update(target, user_ack=user_ack)
            self._log_audit("stack_update_apply", "stack", target, str(result.get("ok")))
            self._json(200 if result.get("ok") else 500, result)
        except (OSError, RuntimeError, ValueError) as exc:
            _log_handler_error("POST /api/admin/updates/apply", exc)
            self._json(500, {"ok": False, "error": str(exc)})

    def _route_post_admin_stack_restart_gateway(self, body: dict) -> None:
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        if not _admin_write_allowed(self):
            self._json(403, {"ok": False, "error": "admin_write_forbidden", "hint": "X-Workframe-Local required in dev-unsafe"})
            return
        try:
            result = _restart_stack_gateway()
            self._log_audit("stack_restart_gateway", "stack", "gateway", str(result.get("ok")))
            self._json(200 if result.get("ok") else 500, result)
        except (OSError, RuntimeError, ValueError) as exc:
            _log_handler_error("POST /api/admin/stack/restart-gateway", exc)
            self._json(500, {"ok": False, "error": str(exc)})

    def _route_post_admin_vault_init(self, body: dict) -> None:
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        if not _admin_write_allowed(self):
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
            _log_handler_error("POST /api/admin/vault/init", exc)
            self._json(500, {"ok": False, "error": str(exc)})

    def _route_post_admin_vault_unlock(self, body: dict) -> None:
        if not _role_allows(self, OWNER_ADMIN_ROLES):
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
            _log_handler_error("POST /api/admin/vault/unlock", exc)
            self._json(500, {"ok": False, "error": str(exc)})

    def _route_post_admin_vault_seal(self, body: dict) -> None:
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        if not _admin_write_allowed(self):
            self._json(403, {"ok": False, "error": "admin_write_forbidden"})
            return
        status = credential_vault.seal_vault()
        self._log_audit("vault_seal", "vault", "meta", "sealed")
        self._json(200, {"ok": True, **status})

    def _route_post_admin_vault_wipe(self, body: dict) -> None:
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        if not _admin_write_allowed(self):
            self._json(403, {"ok": False, "error": "admin_write_forbidden"})
            return
        if not body.get("confirm"):
            self._json(400, {"ok": False, "error": "confirm required"})
            return
        deleted = credential_vault.wipe_all_secrets()
        credential_vault.seal_vault()
        self._log_audit("vault_wipe", "vault", "secrets", f"deleted={deleted}")
        self._json(200, {"ok": True, "deleted": deleted, **credential_vault.vault_status()})

    # WF-037 batch 3 â€” bootstrap, hermes profiles, supervisor, audit, pattern routes
    _HERMES_PROFILE_RESERVED = frozenset({"status", "create", "start", "stop", "delete", "disable"})

    def _route_get_chat_bootstrap(self, qs: dict[str, list[str]]) -> None:
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        profile = resolve_validated_profile(qs.get("profile", [""])[0] or _primary_profile())
        persistent = qs.get("persistent", [""])[0]
        source_id = qs.get("source", ["ui"])[0]
        self._json(200, chat_bootstrap(profile, persistent, source_id))

    def _route_get_hermes_bootstrap(self, qs: dict[str, list[str]]) -> None:
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        self._json(200, hermes_bootstrap())

    def _route_get_hermes_profiles_status(self, qs: dict[str, list[str]]) -> None:
        profile = resolve_validated_profile(qs.get("profile", [""])[0] or _primary_profile())
        if SUPERVISOR_URL:
            self._json(
                *_supervisor_request(
                    "GET",
                    f"/v1/profile.status?profile={urllib.parse.quote(profile, safe='')}",
                    timeout=10.0,
                )
            )
            return
        self._json(200, profile_gateway_lifecycle(profile, "status"))

    def _route_get_supervisor_profile_status(self, qs: dict[str, list[str]]) -> None:
        profile = qs.get("profile", [""])[0]
        if not profile:
            self._json(400, {"error": "profile required"})
            return
        if SUPERVISOR_URL:
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
        if SUPERVISOR_URL:
            self._json(*_supervisor_request("GET", "/v1/stack.status", timeout=15.0))
            return
        self._json(503, {"ok": False, "error": "WORKFRAME_SUPERVISOR_URL not configured"})

    def _route_get_admin_audit(self, qs: dict[str, list[str]]) -> None:
        if SECURE_MODE and not _role_allows(self, OWNER_ADMIN_ROLES):
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
            conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
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
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        cors_origin = _cors_origin_for(self.headers)
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        try:
            while True:
                payload = json.dumps(build_snapshot())
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
                time.sleep(SSE_INTERVAL)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _route_pattern_get_workspace(self, path: str, qs: dict[str, list[str]]) -> None:
        match = re.fullmatch(r"/api/workspace/([^/]+)", path)
        if not match:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        user_id = str(getattr(self, "auth_user", "") or "")
        ws_id = _resolve_wid(match.group(1))
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        self._json(*_get_workspace(ws_id, user_id))

    def _route_pattern_get_workspace_rooms(self, path: str, qs: dict[str, list[str]]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        include_members = qs.get("include_members", [""])[0].lower() in {"1", "true", "yes"}
        self._json(*_list_rooms(ws_id, include_members=include_members))

    def _route_pattern_get_room(self, path: str, qs: dict[str, list[str]]) -> None:
        rid = path.strip("/").split("/")[-1]
        self._json(*_get_room(rid))

    def _route_pattern_get_room_members(self, path: str, qs: dict[str, list[str]]) -> None:
        rid = path.strip("/").split("/")[-2]
        viewer_id = str(getattr(self, "auth_user", "") or "")
        try:
            conn = _workframe_db()
            conn.row_factory = sqlite3.Row
            if not _user_can_access_room(conn, rid, viewer_id):
                conn.close()
                self._json(403, {"ok": False, "error": "forbidden"})
                return
            members = conn.execute(
                "SELECT * FROM room_memberships WHERE room_id = ? AND deleted_at IS NULL",
                (rid,),
            ).fetchall()
            payload = _enrich_room_members(conn, [dict(m) for m in members])
            conn.close()
        except Exception:
            payload = []
        self._json(200, {"ok": True, "room_id": rid, "members": payload})

    def _route_pattern_get_workspace_members(self, path: str, qs: dict[str, list[str]]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        self._json(*_list_workspace_members(ws_id, self))

    def _route_pattern_get_public_branding(self, path: str, qs: dict[str, list[str]]) -> None:
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

    def _route_pattern_get_hermes_profile_soul(self, path: str, qs: dict[str, list[str]]) -> None:
        profile_soul_match = re.fullmatch(r"/api/hermes/profiles/([^/]+)/soul", path)
        if not profile_soul_match:
            self._json(404, {"error": "not found"})
            return
        profile = resolve_validated_profile(profile_soul_match.group(1))
        self._json(200, profile_soul_get(profile))

    def _route_pattern_get_hermes_profile_detail(self, path: str, qs: dict[str, list[str]]) -> None:
        profile_detail_match = re.fullmatch(r"/api/hermes/profiles/([^/]+)", path)
        if not profile_detail_match or profile_detail_match.group(1) in self._HERMES_PROFILE_RESERVED:
            self._json(404, {"error": "not found"})
            return
        profile = resolve_validated_profile(profile_detail_match.group(1))
        ws_id = ""
        user_id = str(getattr(self, "auth_user", "") or "")
        if user_id:
            try:
                conn = _workframe_db()
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

    def _route_pattern_get_me_oauth_status(self, path: str, qs: dict[str, list[str]]) -> None:
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
        self._json(200, device_oauth_status(user_id, provider_id, session_id))

    def _route_pattern_get_room_live(self, path: str, qs: dict[str, list[str]]) -> None:
        rid = path.strip("/").split("/")[-2]
        user_id = str(getattr(self, "auth_user", "") or "")
        try:
            conn = _workframe_db()
            if not _user_can_access_room(conn, rid, user_id):
                conn.close()
                self._json(403, {"ok": False, "error": "forbidden"})
                return
            conn.close()
        except Exception:
            self._json(500, {"ok": False, "error": "db_error"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        cors_origin = _cors_origin_for(self.headers)
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
        self.send_header("Vary", "Origin")
        self.end_headers()
        sub = _room_live_subscribe(rid)
        try:
            for turn in _room_live_active_for_room(rid):
                payload = json.dumps(turn)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
            while True:
                try:
                    line = sub.get(timeout=15)
                    self.wfile.write(f"data: {line}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    heartbeat = json.dumps(
                        {"type": "heartbeat", "room_id": rid, "ts": int(time.time())}
                    )
                    self.wfile.write(f"data: {heartbeat}\n\n".encode("utf-8"))
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            _room_live_unsubscribe(rid, sub)

    def _route_pattern_get_room_activity(self, path: str, qs: dict[str, list[str]]) -> None:
        rid = path.strip("/").split("/")[-2]
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        try:
            activity = room_activity_data(rid, user_id)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        self._json(200, {"ok": True, "room_id": rid, "activity": activity})

    def _route_pattern_get_workspace_activity(self, path: str, qs: dict[str, list[str]]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        wid = _resolve_wid(parts[2])
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        if not wid:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            activity = workspace_activity_data(wid, user_id)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        self._json(200, {"ok": True, "workspace_id": wid, "activity": activity})

    def _route_pattern_get_workspace_kanban_tasks(self, path: str, qs: dict[str, list[str]]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 5:
            self._json(404, {"error": "not_found"})
            return
        wid = _resolve_wid(parts[2])
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        if not wid:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            payload = kanban_proxy_list_tasks(wid, user_id)
        except PermissionError as exc:
            self._json(403, {"ok": False, "error": str(exc)})
            return
        self._json(200, payload)

    def _route_pattern_get_workspace_delegation_grants(self, path: str, qs: dict[str, list[str]]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        wid = _resolve_wid(parts[2])
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        if not wid:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            payload = list_delegation_grants(wid, user_id)
        except PermissionError as exc:
            self._json(403, {"ok": False, "error": str(exc)})
            return
        self._json(200, payload)

    def _route_pattern_get_room_sessions(self, path: str, qs: dict[str, list[str]]) -> None:
        rid = path.strip("/").split("/")[-2]
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        try:
            payload = list_room_sessions(rid, user_id)
        except ValueError as exc:
            err = str(exc)
            if "not_found" in err:
                self._json(404, {"ok": False, "error": err})
                return
            if "denied" in err or "forbidden" in err:
                self._json(403, {"ok": False, "error": err})
                return
            self._json(400, {"ok": False, "error": err})
            return
        self._json(200, payload)

    def _route_pattern_get_workspace_invites(self, path: str, qs: dict[str, list[str]]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        wid = parts[2]
        ws_id = _resolve_wid(wid)
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            invites = conn.execute(
                "SELECT id, workspace_id, email, role, invited_by_user_id, expires_at, created_at, accepted_at, deleted_at FROM workspace_invites WHERE workspace_id = ? AND deleted_at IS NULL ORDER BY created_at DESC",
                (ws_id,)).fetchall()
            conn.close()
        except Exception:
            invites = []
        self._json(200, {"ok": True, "invites": [dict(i) for i in invites]})

    def _route_pattern_get_invite(self, path: str, qs: dict[str, list[str]]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 3:
            self._json(404, {"error": "not_found"})
            return
        token = parts[2]
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        try:
            conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            inv = conn.execute(
                "SELECT id, workspace_id, email, role, invited_by_user_id, expires_at, created_at, accepted_at, deleted_at FROM workspace_invites WHERE token_hash = ? AND deleted_at IS NULL",
                (token_hash,)).fetchone()
            conn.close()
        except Exception:
            inv = None
        if not inv:
            self._json(404, {"ok": False, "error": "invite_not_found"})
            return
        self._json(200, {"ok": True, "invite": dict(inv)})

    def _route_pattern_get_workspace_memory(self, path: str, qs: dict[str, list[str]]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        wid = parts[2]
        ws_id = _resolve_wid(wid)
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            items = conn.execute(
                "SELECT * FROM memory_items WHERE workspace_id = ? AND deleted_at IS NULL ORDER BY created_at DESC",
                (ws_id,)).fetchall()
            conn.close()
        except Exception:
            items = []
        self._json(200, {"ok": True, "items": [dict(i) for i in items]})

    def _route_pattern_get_workspace_budget(self, path: str, qs: dict[str, list[str]]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            policies = conn.execute(
                "SELECT * FROM budget_policies WHERE workspace_id = ? ORDER BY created_at DESC",
                (ws_id,)).fetchall()
            conn.close()
        except Exception:
            policies = []
        self._json(200, {"ok": True, "budget_policies": [dict(p) for p in policies]})

    def _route_pattern_get_workspace_grants(self, path: str, qs: dict[str, list[str]]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            grants = conn.execute(
                "SELECT cg.*, cb.provider AS binding_provider FROM credential_grants cg LEFT JOIN credential_bindings cb ON cb.id = cg.credential_binding_id WHERE cb.workspace_id = ? OR cg.grantee_id = ? ORDER BY cg.created_at DESC",
                (ws_id, ws_id)).fetchall()
            conn.close()
        except Exception:
            grants = []
        self._json(200, {"ok": True, "grants": [dict(g) for g in grants]})

    def _route_pattern_get_room_messages(self, path: str, qs: dict[str, list[str]]) -> None:
        slug_or_id = path.strip("/").split("/")[-2]
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        limit = int(qs.get("limit", ["50"])[0])
        offset = int(qs.get("offset", ["0"])[0])
        try:
            conn = _workframe_db()
            room = conn.execute(
                "SELECT id FROM rooms WHERE (id = ? OR slug = ?) AND deleted_at IS NULL",
                (slug_or_id, slug_or_id),
            ).fetchone()
            if not room:
                conn.close()
                self._json(404, {"error": "room_not_found"})
                return
            rid = room["id"]
            if not _user_can_access_room(conn, rid, user_id):
                conn.close()
                self._json(403, {"ok": False, "error": "forbidden"})
                return
            messages = conn.execute(
                """
                SELECT * FROM (
                    SELECT * FROM messages
                    WHERE room_id = ? AND deleted_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                ) AS recent
                ORDER BY created_at ASC
                """,
                (rid, limit, offset),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE room_id = ? AND deleted_at IS NULL",
                (rid,),
            ).fetchone()[0]
            payload = _enrich_room_messages(conn, messages)
            conn.close()
        except Exception:
            messages = []
            total = 0
            payload = []
        self._json(200, {"ok": True, "messages": payload, "total": total, "limit": limit, "offset": offset})

    def _route_pattern_get_workspace_events(self, path: str, qs: dict[str, list[str]]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) < 4:
            self._json(404, {"error": "not_found"})
            return
        wid = parts[2]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        cors_origin = _cors_origin_for(self.headers)
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
        self.send_header("Vary", "Origin")
        self.end_headers()
        last_revision = ""
        last_heartbeat = time.time()
        try:
            while True:
                try:
                    conn = _workframe_db()
                    revision = _workspace_sse_revision(conn, wid)
                    conn.close()
                except Exception:
                    revision = "error"
                if revision != last_revision:
                    payload = json.dumps(_workspace_event_payload(wid, revision))
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    last_revision = revision
                    last_heartbeat = time.time()
                elif time.time() - last_heartbeat >= 15:
                    heartbeat = json.dumps({"type": "heartbeat", "workspace_id": wid, "ts": int(time.time())})
                    self.wfile.write(f"data: {heartbeat}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    last_heartbeat = time.time()
                time.sleep(1)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _route_pattern_get_workspace_credentials(self, path: str, qs: dict[str, list[str]]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        try:
            conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT id, workspace_id, user_id, agent_profile_id, provider,
                          credential_type, credential_ref, label, is_active,
                          expires_at, created_by, created_at, updated_at
                   FROM credential_bindings
                   WHERE workspace_id = ? AND deleted_at IS NULL
                   ORDER BY created_at DESC""",
                (ws_id,),
            ).fetchall()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"ok": False, "error": str(exc)})
            return
        self._json(200, {
            "ok": True,
            "scope": "workspace",
            "workspace_id": ws_id,
            "credentials": [dict(r) for r in rows],
        })

    def _route_pattern_get_agent_credentials(self, path: str, qs: dict[str, list[str]]) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        agent_id = parts[2]
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        try:
            conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
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

    def _route_post_hermes_profiles_create(self, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not _handler_is_active_workspace_member(self):
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
            workspaces = _get_user_workspaces(user_id)
            current = _resolve_current_workspace(user_id, workspaces)
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
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        profile = resolve_validated_profile(str(body.get("profile") or _primary_profile()))
        if SUPERVISOR_URL:
            self._json(*_supervisor_request("POST", "/v1/profile.start", body))
            return
        self._json(200, profile_gateway_lifecycle(profile, "start"))

    def _route_post_hermes_profiles_stop(self, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        profile = resolve_validated_profile(str(body.get("profile") or _primary_profile()))
        if SUPERVISOR_URL:
            self._json(*_supervisor_request("POST", "/v1/profile.stop", body))
            return
        self._json(200, profile_gateway_lifecycle(profile, "stop"))

    def _route_post_hermes_profiles_delete(self, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        profile = str(body.get("profile") or "").strip()
        if not profile:
            self._json(400, {"error": "profile required"})
            return
        self._json(200, profile_delete(profile))

    def _route_post_hermes_profiles_disable(self, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        profile = resolve_validated_profile(str(body.get("profile") or _primary_profile()))
        if SUPERVISOR_URL:
            self._json(*_supervisor_request("POST", "/v1/profile.disable", body))
            return
        self._json(200, profile_gateway_lifecycle(profile, "disable"))

    def _supervisor_proxy_post(self, subpath: str, body: dict) -> None:
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        if SUPERVISOR_URL:
            self._json(*_supervisor_request("POST", subpath, body))
            return
        self._json(503, {"ok": False, "error": "WORKFRAME_SUPERVISOR_URL not configured"})

    def _route_post_supervisor_profile_start(self, body: dict) -> None:
        self._supervisor_proxy_post("/v1/profile.start", body)

    def _route_post_supervisor_profile_stop(self, body: dict) -> None:
        self._supervisor_proxy_post("/v1/profile.stop", body)

    def _route_post_supervisor_profile_disable(self, body: dict) -> None:
        self._supervisor_proxy_post("/v1/profile.disable", body)

    def _route_pattern_post_hermes_profile_bootstrap_dm(self, path: str, body: dict) -> None:
        profile_bootstrap_post = re.fullmatch(r"/api/hermes/profiles/([^/]+)/bootstrap-dm", path)
        if not profile_bootstrap_post:
            self._json(404, {"error": "not found"})
            return
        if not _check_auth(self):
            self._json(401, {"error": "unauthorized"})
            return
        if not _handler_is_active_workspace_member(self):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "workspace_member"})
            return
        template = resolve_validated_profile(profile_bootstrap_post.group(1))
        user_id = str(getattr(self, "auth_user", "") or "").strip()
        workspace_id = str(body.get("workspace_id") or "").strip()
        if not workspace_id and user_id:
            workspaces = _get_user_workspaces(user_id)
            current = _resolve_current_workspace(user_id, workspaces)
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
        profile_soul_post = re.fullmatch(r"/api/hermes/profiles/([^/]+)/soul", path)
        if not profile_soul_post:
            self._json(404, {"error": "not found"})
            return
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        profile = resolve_validated_profile(profile_soul_post.group(1))
        soul = str(body.get("soul", body.get("text", "")))
        self._json(200, profile_soul_set(profile, soul))

    def _route_pattern_post_hermes_profile_bind(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) < 5:
            self._json(404, {"error": "not found"})
            return
        profile_raw = urllib.parse.unquote(parts[3])
        user_id = str(getattr(self, "auth_user", "") or "")
        self._json(200, profile_chat_bind(profile_raw, body, user_id))

    def _route_pattern_post_hermes_profile_sessions(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) < 5:
            self._json(404, {"error": "not found"})
            return
        profile_raw = urllib.parse.unquote(parts[3])
        user_id = str(getattr(self, "auth_user", "") or "")
        self._json(200, profile_chat_session(profile_raw, body, user_id))

    def _route_pattern_post_hermes_profile_messages(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) < 5:
            self._json(404, {"error": "not found"})
            return
        profile_raw = urllib.parse.unquote(parts[3])
        stream_body = _enrich_room_chat_payload(body, str(getattr(self, "auth_user", "") or ""))
        self._json(200, profile_chat_message(profile_raw, stream_body))

    def _route_pattern_post_hermes_profile_messages_stream(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) < 6:
            self._json(404, {"error": "not found"})
            return
        profile_raw = urllib.parse.unquote(parts[3])
        stream_body = _enrich_room_chat_payload(body, str(getattr(self, "auth_user", "") or ""))
        stream_profile_chat(self, profile_raw, stream_body)

    def _route_pattern_post_me_oauth_start(self, path: str, body: dict) -> None:
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
        self._json(200, start_user_oauth(user_id, provider_id, workspace_id))

    def _route_pattern_post_me_providers_disconnect(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 5 or parts[2] != "providers" or parts[4] != "disconnect":
            self._json(404, {"error": "not_found"})
            return
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        self._json(200, disconnect_user_provider(user_id, parts[3]))

    def _route_pattern_post_workspace_credentials_store(self, path: str, body: dict) -> None:
        # POST /api/workspace/:wid/credentials/store
        parts = path.strip("/").split("/")
        if len(parts) < 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        provider = str(body.get("provider", "")).strip().lower()
        api_key = str(body.get("api_key", "") or body.get("secret", "")).strip()
        label = str(body.get("label", "") or provider)
        if not provider or not api_key:
            self._json(400, {"error": "provider and api_key required"})
            return
        spec = _catalog_provider(provider)
        if not spec:
            self._json(400, {"error": "provider_not_found"})
            return
        if spec.get("user_only"):
            self._json(403, {"ok": False, "error": "provider_user_only"})
            return
        env_var = str(spec.get("env_var") or _default_credential_env_var(provider, "api_key"))
        try:
            payload = _store_workspace_credential(
                ws_id,
                provider,
                "api_key",
                api_key,
                env_var,
                label,
                str(getattr(self, "auth_user", "") or ""),
            )
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        cred_id = str(payload["credential_id"])
        self._log_audit("credential_stored", "credential_binding", cred_id, f"provider={provider}")
        try:
            _bootstrap_model_after_llm_connect("", ws_id, provider)
        except (OSError, RuntimeError, ValueError) as exc:
            _log_handler_error("POST workspace credentials/store bootstrap", exc)
        if str(spec.get("category") or "") == "messaging":
            sync_result = _sync_workspace_messaging_gateway(ws_id)
            if not sync_result.get("ok"):
                self._json(500, {"ok": False, "error": sync_result.get("error") or "messaging_sync_failed"})
                return
        self._json(200, {"ok": True, "credential_id": cred_id, "credential_ref": payload["credential_ref"]})

    def _route_pattern_post_workspace_credentials_revoke(self, path: str, body: dict) -> None:
        # POST /api/workspace/:wid/credentials/:bindingId/revoke
        parts = path.strip("/").split("/")
        if len(parts) < 5:
            self._json(404, {"error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        binding_id = parts[4]
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        try:
            conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT provider FROM credential_bindings WHERE id = ? AND workspace_id = ?",
                (binding_id, ws_id),
            ).fetchone()
            provider = str(row["provider"] or "").strip().lower() if row else ""
            cur = conn.execute(
                "UPDATE credential_bindings SET is_active = 0, updated_at = ? WHERE id = ? AND workspace_id = ?",
                (str(int(time.time())), binding_id, ws_id),
            )
            conn.commit()
            affected = cur.rowcount
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        if not affected:
            self._json(404, {"error": "credential_not_found"})
            return
        self._log_audit("credential_revoked", "credential_binding", binding_id, f"workspace={ws_id}")
        spec = _catalog_provider(provider)
        if spec and str(spec.get("category") or "") == "messaging":
            sync_result = _sync_workspace_messaging_gateway(ws_id)
            if not sync_result.get("ok"):
                self._json(500, {"ok": False, "error": sync_result.get("error") or "messaging_sync_failed"})
                return
        self._json(200, {"ok": True, "credential_id": binding_id, "status": "revoked"})

    def _route_pattern_post_workspace_rooms(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        created_by = str(getattr(self, "auth_user", "") or "")
        if not _handler_is_active_workspace_member(self, ws_id):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "workspace_member"})
            return
        status, payload = _create_room(ws_id, body, created_by)
        if status == 201:
            self._log_audit("room_created", "room", payload["room"]["id"], f"name={payload['room']['name']}")
        self._json(status, payload)

    def _route_pattern_post_workspace_rooms_create(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) < 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        name = str(body.get("name", "")).strip()
        slug = str(body.get("slug", "") or name.lower().replace(" ", "-")).strip()
        room_type = str(body.get("room_type", "channel")).strip()
        topic = str(body.get("topic", "")).strip()
        agent_id = str(body.get("agent_profile_id", "")).strip()
        if not name:
            self._json(400, {"error": "name required"})
            return
        rid = str(uuid.uuid4())
        now_ts = str(int(time.time()))
        try:
            conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.execute(
                "INSERT INTO rooms (id, workspace_id, agent_profile_id, name, slug, topic, room_type, status, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (rid, ws_id, agent_id or None, name, slug, topic, room_type, "active", getattr(self, "auth_user", ""), now_ts, now_ts),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        self._log_audit("room_created", "room", rid, f"name={name}")
        self._json(200, {"ok": True, "room_id": rid})

    def _route_pattern_post_room_members(self, path: str, body: dict) -> None:
        rid = path.strip("/").split("/")[-2]
        actor_id = str(getattr(self, "auth_user", "") or "")
        if not actor_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        user_id_to_add = str(body.get("user_id", "")).strip()
        role = str(body.get("role", "member")).strip()
        if not user_id_to_add:
            self._json(400, {"error": "user_id required"})
            return
        mid = str(uuid.uuid4())
        now_ts = str(int(time.time()))
        try:
            conn = _workframe_db()
            if not _user_can_manage_room_members(conn, rid, actor_id):
                conn.close()
                self._json(403, {"ok": False, "error": "forbidden"})
                return
            conn.execute(
                "INSERT INTO room_memberships (id, room_id, user_id, role, status, joined_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (mid, rid, user_id_to_add, role, "active", now_ts, now_ts),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        self._log_audit("room_member_added", "room_membership", mid, f"room={rid} user={user_id_to_add}")
        self._json(200, {"ok": True, "membership_id": mid})

    def _route_pattern_post_room_bind(self, path: str, body: dict) -> None:
        rid = path.strip("/").split("/")[-2]
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        try:
            self._json(200, room_chat_bind(rid, body, user_id))
        except ValueError as exc:
            err = str(exc)
            if "not_found" in err:
                self._json(404, {"ok": False, "error": err})
            elif "denied" in err or "forbidden" in err:
                self._json(403, {"ok": False, "error": err})
            else:
                self._json(400, {"ok": False, "error": err})

    def _route_pattern_post_room_sessions_activate(self, path: str, body: dict) -> None:
        rid = path.strip("/").split("/")[-3]
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        session_id = str(body.get("session_id", "")).strip()
        template_prof = str(body.get("profile", "")).strip()
        source_id = str(body.get("source_id") or "ui").strip() or "ui"
        client_id = str(body.get("client_id") or "default").strip() or "default"
        binding_version = _binding_version(body.get("binding_version"))
        if not session_id:
            self._json(400, {"error": "session_id required"})
            return
        try:
            payload = profile_chat_activate_room_session(
                rid,
                session_id,
                user_id,
                template_prof,
                source_id=source_id,
                client_id=client_id,
                binding_version=binding_version,
            )
        except ValueError as exc:
            err = str(exc)
            if "not_found" in err:
                self._json(404, {"ok": False, "error": err})
            elif "denied" in err:
                self._json(403, {"ok": False, "error": err})
            else:
                self._json(400, {"ok": False, "error": err})
            return
        self._json(200, payload)

    def _route_pattern_post_room_messages_send(self, path: str, body: dict) -> None:
        slug_or_id = path.strip("/").split("/")[-3]
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        sender_agent = str(body.get("sender_agent_id", "")).strip()
        content = str(body.get("content", "")).strip()
        content_type = str(body.get("content_type", "text")).strip()
        parent_id = str(body.get("parent_message_id", "") or None)
        if not content:
            self._json(400, {"error": "content required"})
            return
        try:
            conn = _workframe_db()
            room = conn.execute(
                """
                SELECT id, workspace_id, room_type, agent_profile_id
                FROM rooms WHERE (id = ? OR slug = ?) AND deleted_at IS NULL
                """,
                (slug_or_id, slug_or_id),
            ).fetchone()
            if not room:
                conn.close()
                self._json(404, {"error": "room_not_found"})
                return
            rid = str(room["id"])
            workspace_id = str(room["workspace_id"])
            if not _user_can_access_room(conn, rid, user_id):
                conn.close()
                self._json(403, {"ok": False, "error": "forbidden"})
                return
            if sender_agent:
                sender_user = ""
                agent_member = conn.execute(
                    """
                    SELECT 1 FROM room_memberships
                    WHERE room_id = ? AND agent_profile_id = ? AND deleted_at IS NULL
                    """,
                    (rid, sender_agent),
                ).fetchone()
                if not agent_member:
                    conn.close()
                    self._json(403, {"ok": False, "error": "agent_not_in_room"})
                    return
            else:
                sender_user = str(body.get("sender_user_id", "") or user_id).strip()
                if sender_user != user_id:
                    conn.close()
                    self._json(403, {"ok": False, "error": "forbidden"})
                    return
            mid = str(uuid.uuid4())
            now_ts = str(int(time.time()))
            conn.execute(
                "INSERT INTO messages (id, room_id, sender_user_id, sender_agent_id, parent_message_id, content, content_type, is_edited, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (mid, rid, sender_user or None, sender_agent or None, parent_id, content, content_type, 0, now_ts, now_ts),
            )
            conn.execute("UPDATE rooms SET updated_at = ? WHERE id = ?", (now_ts, rid))
            mention_meta: dict[str, Any] = {}
            if _is_space_room(str(room["room_type"]), room["agent_profile_id"]) and not sender_agent:
                invoke_agents = body.get("invoke_agents", True)
                if isinstance(invoke_agents, str):
                    invoke_agents = invoke_agents.lower() not in ("0", "false", "no")
                mention_meta = _process_space_message_mentions(
                    rid,
                    workspace_id,
                    user_id,
                    content,
                    mid,
                    invoke_agents=bool(invoke_agents),
                )
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        self._log_audit("message_sent", "message", mid, f"room={rid}")
        self._json(200, {"ok": True, "message_id": mid, **mention_meta})

    def _route_pattern_post_workspace_invites(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        email = str(body.get("email", "")).strip()
        role = str(body.get("role", "member")).strip()
        if not email:
            self._json(400, {"error": "email required"})
            return
        invite_id = str(uuid.uuid4())
        token = secrets.token_hex(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now_ts = str(int(time.time()))
        expires_at = str(int(time.time()) + 86400 * 7)
        try:
            conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.execute(
                "INSERT INTO workspace_invites (id, workspace_id, email, role, token_hash, invited_by_user_id, expires_at, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (invite_id, ws_id, email, role, token_hash, getattr(self, "auth_user", ""), expires_at, now_ts),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        invite_url = f"{APP_BASE_URL}/?invite_token={urllib.parse.quote(token)}&email={urllib.parse.quote(email)}"
        email_sent = False
        email_error = None
        ws_name = ws_id
        logo_url = ""
        try:
            conn = sqlite3.connect(str(_workframe_db_path()), timeout=3.0)
            conn.row_factory = sqlite3.Row
            ws_row = conn.execute(
                "SELECT display_name, avatar_url FROM workspaces WHERE id = ?",
                (ws_id,),
            ).fetchone()
            conn.close()
            if ws_row:
                ws_name = str(ws_row["display_name"] or ws_id)
                logo_url = str(ws_row["avatar_url"] or "")
        except sqlite3.Error:
            pass
        try:
            send_branded_invite_email(email, ws_name, invite_url, logo_url)
            email_sent = True
        except Exception as exc:
            email_error = str(exc)
        self._log_audit("invite_created", "workspace_invite", invite_id, f"workspace={ws_id} email={email}")
        payload = {"ok": True, "invite_id": invite_id, "token": token, "email": email, "role": role, "expires_at": expires_at, "invite_url": invite_url, "email_sent": email_sent}
        if email_error:
            payload["email_error"] = email_error
        self._json(201, payload)

    def _route_pattern_post_invites_accept(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4 or parts[3] != "accept":
            self._json(404, {"error": "not_found"})
            return
        token = parts[2]
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            if DEV_LOCAL_UNSAFE:
                user_id = "dev"
            else:
                self._json(401, {"ok": False, "error": "no_authenticated_user"})
                return
        try:
            conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            inv = conn.execute(
                "SELECT * FROM workspace_invites WHERE token_hash = ? AND deleted_at IS NULL AND accepted_at IS NULL",
                (token_hash,)).fetchone()
            if not inv:
                conn.close()
                self._json(404, {"ok": False, "error": "invite_not_found_or_expired"})
                return
            if int(inv["expires_at"]) < int(time.time()):
                conn.close()
                self._json(410, {"ok": False, "error": "invite_expired"})
                return
            wid = inv["workspace_id"]
            role = inv["role"]
            membership_id = str(uuid.uuid4())
            now_ts = str(int(time.time()))
            inviter_id = str(inv["invited_by_user_id"] or "").strip()
            existing = conn.execute(
                "SELECT id FROM workspace_memberships WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL",
                (wid, user_id)).fetchone()
            if existing:
                room_join = _onboard_workspace_member_rooms(
                    conn,
                    wid,
                    user_id,
                    inviter_user_id=inviter_id or None,
                )
                dm_room = _ensure_user_dm_room(conn, wid, user_id, inviter_id)
                conn.execute("UPDATE workspace_invites SET accepted_by_user_id = ?, accepted_at = ?, deleted_at = ? WHERE id = ?",
                             (user_id, now_ts, now_ts, inv["id"]))
                conn.commit()
                conn.close()
                _set_user_current_workspace(user_id, wid)
                self._json(200, {"ok": True, "already_member": True, "workspace_id": wid, "room": room_join, "dm_room": dm_room})
                return
            conn.execute(
                "INSERT INTO workspace_memberships (id, workspace_id, user_id, role, status, invited_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (membership_id, wid, user_id, role, "active", inv["invited_by_user_id"], now_ts, now_ts),
            )
            room_join = _onboard_workspace_member_rooms(
                conn,
                wid,
                user_id,
                inviter_user_id=inviter_id or None,
            )
            dm_room = _ensure_user_dm_room(conn, wid, user_id, inviter_id)
            conn.execute("UPDATE workspace_invites SET accepted_by_user_id = ?, accepted_at = ?, deleted_at = ? WHERE id = ?",
                         (user_id, now_ts, now_ts, inv["id"]))
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        _provision_invited_member_agent_runtimes(wid, user_id)
        _set_user_current_workspace(user_id, wid)
        self._log_audit("invite_accepted", "workspace_invite", inv["id"], f"workspace={wid} user={user_id}")
        self._json(
            200,
            {
                "ok": True,
                "workspace_id": wid,
                "role": role,
                "membership_id": membership_id,
                "room": room_join,
                "dm_room": dm_room,
            },
        )

    def _route_pattern_post_workspace_members(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        target_user_id = str(body.get("user_id", "") or body.get("email", "")).strip()
        role = str(body.get("role", "member")).strip()
        if not target_user_id:
            self._json(400, {"ok": False, "error": "user_id required"})
            return
        # Check if membership already exists
        try:
            db = _workframe_db()
            existing = db.execute("SELECT id FROM workspace_memberships WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL", (ws_id, target_user_id)).fetchone()
            db.close()
        except Exception:
            existing = None
        if existing:
            # Update existing membership
            status, payload = _patch_workspace_members(ws_id, {"user_id": target_user_id, "role": role}, self)
        else:
            # Create new membership
            mid = str(uuid.uuid4())
            now_ts = str(int(time.time()))
            try:
                db = _workframe_db()
                db.execute("INSERT INTO workspace_memberships (id, workspace_id, user_id, role, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)", (mid, ws_id, target_user_id, role, "active", now_ts, now_ts))
                _onboard_workspace_member_rooms(db, ws_id, target_user_id)
                db.commit()
                db.close()
                status, payload = 200, {"ok": True, "membership_id": mid, "user_id": target_user_id, "role": role}
            except sqlite3.Error as exc:
                status, payload = 500, {"ok": False, "error": str(exc)}
        if status == 200:
            self._log_audit("workspace_member_added", "workspace_membership", f"{ws_id}/{target_user_id}", f"workspace={ws_id} user={target_user_id}")
        self._json(status, payload)

    def _route_pattern_post_workspace_kanban_tasks(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 5:
            self._json(404, {"error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        try:
            payload = kanban_proxy_create_task(ws_id, user_id, body)
        except PermissionError as exc:
            self._json(403, {"ok": False, "error": str(exc)})
            return
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        self._json(201, payload)

    def _route_pattern_post_workspace_delegation_grants(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        grantee_user_id = str(body.get("grantee_user_id") or "").strip()
        scope = str(body.get("scope") or DELEGATION_SCOPE_AGENTS_DELEGATE).strip()
        try:
            payload = create_delegation_grant(ws_id, user_id, grantee_user_id, scope=scope)
        except PermissionError as exc:
            self._json(403, {"ok": False, "error": str(exc)})
            return
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        self._json(201, payload)

    def _route_pattern_post_workspace_runtime_profiles_purge(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 5:
            self._json(404, {"error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        conn = _workframe_db()
        try:
            role = _workspace_member_role(conn, ws_id, user_id)
        finally:
            conn.close()
        if role not in OWNER_ADMIN_ROLES:
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        try:
            payload = purge_stale_runtime_profiles(ws_id)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        self._json(200, payload)

    def _route_pattern_post_workspace_memory(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        content = str(body.get("content", "")).strip()
        if not content:
            self._json(400, {"error": "content required"})
            return
        agent_profile_id = str(body.get("agent_profile_id", "") or None)
        scope = str(body.get("scope", "workspace")).strip()
        room_id = str(body.get("room_id") or None) if body.get("room_id") else None
        user_id_mem = str(body.get("user_id") or None) if body.get("user_id") else None
        visibility = str(body.get("visibility", "shared")).strip()
        mem_id = str(uuid.uuid4())
        now_ts = str(int(time.time()))
        try:
            conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.execute(
                "INSERT INTO memory_items (id, workspace_id, agent_profile_id, scope, room_id, user_id, content, visibility, created_by_user_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (mem_id, ws_id, agent_profile_id, scope, room_id, user_id_mem, content, visibility, getattr(self, "auth_user", ""), now_ts, now_ts),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        self._log_audit("memory_created", "memory_item", mem_id, f"workspace={ws_id} scope={scope}")
        self._json(201, {"ok": True, "memory_id": mem_id})

    def _route_pattern_post_memory(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 3:
            self._json(404, {"error": "not_found"})
            return
        mem_id = parts[2]
        user_id = str(getattr(self, "auth_user", "") or "")
        try:
            conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.row_factory = sqlite3.Row
            item = conn.execute("SELECT * FROM memory_items WHERE id = ? AND deleted_at IS NULL", (mem_id,)).fetchone()
            if not item:
                conn.close()
                self._json(404, {"error": "memory_not_found"})
                return
            if not DEV_LOCAL_UNSAFE and str(item["created_by_user_id"]) != user_id:
                auth_role = str(getattr(self, "auth_role", ""))
                if auth_role not in OWNER_ADMIN_ROLES:
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

    def _route_pattern_post_workspace_budget(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        subject_type = str(body.get("subject_type", "workspace")).strip()
        subject_id = str(body.get("subject_id") or ws_id)
        provider = str(body.get("provider", "") or None)
        daily_limit = body.get("daily_limit_cents")
        monthly_limit = body.get("monthly_limit_cents")
        allowed_models = str(body.get("allowed_models", "") or None)
        now_ts = str(int(time.time()))
        policy_id = str(uuid.uuid4())
        try:
            conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.execute(
                "INSERT INTO budget_policies (id, workspace_id, subject_type, subject_id, provider, daily_limit_cents, monthly_limit_cents, allowed_models, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (policy_id, ws_id, subject_type, subject_id, provider, daily_limit, monthly_limit, allowed_models, now_ts, now_ts),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        self._log_audit("budget_created", "budget_policy", policy_id, f"workspace={ws_id} subject={subject_type}")
        self._json(201, {"ok": True, "budget_policy_id": policy_id})

    def _route_pattern_post_workspace_grants(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        credential_binding_id = str(body.get("credential_binding_id", "")).strip()
        if not credential_binding_id:
            self._json(400, {"error": "credential_binding_id required"})
            return
        grantee_type = str(body.get("grantee_type", "user")).strip()
        grantee_id = str(body.get("grantee_id", "")).strip()
        if not grantee_id:
            self._json(400, {"error": "grantee_id required"})
            return
        provider = str(body.get("provider", "") or None)
        max_daily = body.get("max_daily_cents")
        max_total = body.get("max_total_cents")
        allowed_models = str(body.get("allowed_models", "") or None)
        allowed_agent_ids = str(body.get("allowed_agent_profile_ids", "") or None)
        allowed_room_ids = str(body.get("allowed_room_ids", "") or None)
        expires_at = str(body.get("expires_at") or None) if body.get("expires_at") else None
        grant_id = str(uuid.uuid4())
        now_ts = str(int(time.time()))
        user_id = str(getattr(self, "auth_user", "") or "")
        try:
            conn = sqlite3.connect(str(AUTH_DB_PATH.parent / "workframe.db"), timeout=3.0)
            conn.execute(
                "INSERT INTO credential_grants (id, credential_binding_id, granted_by_user_id, grantee_type, grantee_id, provider, max_daily_cents, max_total_cents, allowed_models, allowed_agent_profile_ids, allowed_room_ids, expires_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (grant_id, credential_binding_id, user_id, grantee_type, grantee_id, provider, max_daily, max_total, allowed_models, allowed_agent_ids, allowed_room_ids, expires_at, now_ts),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            self._json(500, {"error": f"db_error: {exc}"})
            return
        self._log_audit("grant_created", "credential_grant", grant_id, f"workspace={ws_id} grantee={grantee_type}:{grantee_id}")
        self._json(201, {"ok": True, "grant_id": grant_id})

    def _route_pattern_patch_room(self, path: str, body: dict) -> None:
        room_patch_match = re.fullmatch(r"/api/rooms/([^/]+)", path)
        if room_patch_match:
            user_id = str(getattr(self, "auth_user", "") or "")
            status, payload = _patch_room(room_patch_match.group(1), body, user_id)
            if status == 200:
                self._log_audit(
                    "room_updated",
                    "room",
                    room_patch_match.group(1),
                    f"room={room_patch_match.group(1)}",
                    {"changes": body},
                )
            self._json(status, payload)

    def _route_pattern_patch_workspace_members(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"ok": False, "error": "not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        status, payload = _patch_workspace_members(ws_id, body, self)
        if status == 200:
            self._log_audit(
                "workspace_member_updated",
                "workspace_membership",
                ws_id,
                f"workspace={ws_id}",
                {"workspace_id": ws_id, "changes": body},
            )
        self._json(status, payload)

    def _route_pattern_patch_workspace_integrations(self, path: str, body: dict) -> None:
        workspace_integrations_match = re.fullmatch(r"/api/workspace/([^/]+)/integrations", path)
        if workspace_integrations_match:
            user_id = str(getattr(self, "auth_user", "") or "")
            ws_id = _resolve_wid(workspace_integrations_match.group(1))
            if not ws_id:
                self._json(404, {"ok": False, "error": "workspace_not_found"})
                return
            status, payload = _patch_workspace_integrations(ws_id, body, user_id)
            if status == 200:
                self._log_audit(
                    "workspace_integrations_updated",
                    "workspace",
                    ws_id,
                    f"workspace={ws_id}",
                    {"changes": list(body.keys())},
                )
            self._json(status, payload)

    def _route_pattern_patch_workspace(self, path: str, body: dict) -> None:
        workspace_patch_match = re.fullmatch(r"/api/workspace/([^/]+)", path)
        if workspace_patch_match:
            user_id = str(getattr(self, "auth_user", "") or "")
            ws_id = _resolve_wid(workspace_patch_match.group(1))
            if not ws_id:
                self._json(404, {"ok": False, "error": "workspace_not_found"})
                return
            status, payload = _patch_workspace(ws_id, body, user_id)
            if status == 200:
                self._log_audit(
                    "workspace_updated",
                    "workspace",
                    ws_id,
                    f"workspace={ws_id}",
                    {"changes": body},
                )
            self._json(status, payload)

    def _route_pattern_delete_workspace_members(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        ws_id = _resolve_wid(parts[2])
        if not ws_id:
            self._json(404, {"ok": False, "error": "workspace_not_found"})
            return
        target_user_id = str(body.get("user_id", "")).strip()
        if not target_user_id:
            self._json(400, {"ok": False, "error": "user_id required"})
            return
        try:
            db = _workframe_db()
            cur = db.execute(
                "UPDATE workspace_memberships SET deleted_at = ?, status = 'removed' WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL",
                (str(int(time.time())), ws_id, target_user_id),
            )
            db.commit()
            affected = cur.rowcount
            db.close()
        except Exception:
            self._json(500, {"ok": False, "error": "delete_failed"})
            return
        if not affected:
            self._json(404, {"ok": False, "error": "member_not_found"})
            return
        self._log_audit(
            "workspace_member_removed",
            "workspace_membership",
            f"{ws_id}/{target_user_id}",
            f"workspace={ws_id} user={target_user_id}",
        )
        self._json(200, {"ok": True, "user_id": target_user_id, "status": "removed"})

    def _route_pattern_delete_memory(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 3:
            self._json(404, {"ok": False, "error": "memory_not_found"})
            return
        mem_id = parts[2]
        try:
            db = _workframe_db()
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

    def _route_pattern_delete_room(self, path: str, body: dict) -> None:
        rid = path.strip("/").split("/")[-1]
        try:
            db = _workframe_db()
            cur = db.execute(
                "UPDATE rooms SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
                (str(int(time.time())), rid),
            )
            db.commit()
            affected = cur.rowcount
            db.close()
        except Exception:
            self._json(500, {"ok": False, "error": "delete_failed"})
            return
        if not affected:
            self._json(404, {"ok": False, "error": "room_not_found"})
            return
        self._log_audit("room_deleted", "room", rid, f"room={rid}")
        self._json(200, {"ok": True, "room_id": rid, "status": "deleted"})

    def _route_pattern_delete_me_credentials(self, path: str, body: dict) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4 or parts[2] != "credentials":
            self._json(404, {"error": "not_found"})
            return
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        self._json(200, disconnect_user_credential(user_id, parts[3]))

    def _route_patch_me(self, body: dict) -> None:
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        try:
            _apply_me_profile_updates(user_id, body)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        payload = _session_profile_payload(user_id)
        if not payload:
            self._json(404, {"ok": False, "error": "user_not_found"})
            return
        self._json(200, payload)

    def _route_patch_me_native_agent(self, body: dict) -> None:
        user_id = str(getattr(self, "auth_user", "") or "")
        if not user_id:
            self._json(401, {"ok": False, "error": "no_session"})
            return
        native_slug = str(NATIVE_PROFILE or "workframe-agent")
        runtime = _runtime_profile_slug(user_id, native_slug)
        soul = (
            str(body.get("soul") or body.get("soul_md") or "").strip()
            if ("soul" in body or "soul_md" in body)
            else ""
        )
        display = str(body.get("display_name") or "").strip() if "display_name" in body else ""
        tagline = str(body.get("tagline") or "").strip() if "tagline" in body else ""
        _seed_native_user_overlay(
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
            _sync_agent_profile_db(native_slug, profile_patch)
        if "avatar_url" in body or "avatar_id" in body:
            avatar_patch = _normalize_agent_avatar_patch(
                str(body.get("avatar_url") or ""),
                str(body.get("avatar_id") or ""),
            )
            if avatar_patch.get("avatar_url") or avatar_patch.get("avatar_id"):
                stamp = datetime.now(timezone.utc).isoformat()
                row_patch = {**avatar_patch, "updated_at": stamp}
                _upsert_agent_registry_row(native_slug, row_patch)
                _upsert_agent_registry_row(runtime, row_patch)
                _sync_agent_profile_db(native_slug, {"avatar_url": avatar_patch.get("avatar_url", "")})
        self._json(200, {"ok": True, "runtime_profile": runtime})

    def _route_patch_doctor_repair(self, body: dict) -> None:
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        repair = body.get("repair", True) is not False
        result = doctor_repair_agent_dm_runtimes(repair=repair)
        if repair:
            self._log_audit(
                "doctor_repair_agent_dm_runtimes",
                "runtime_profile",
                "",
                f"repaired={len(result.get('repaired') or [])} failed={len(result.get('failed') or [])}",
            )
        self._json(200, result)

    def _route_patch_install_stack(self, body: dict) -> None:
        if not _install_window_open() and not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        if not _install_owner_session_ok(self):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        try:
            global DEPLOYMENT_MODE
            updated = stack_config.patch_stack_config(body if isinstance(body, dict) else {})
            compose_sync = None
            if isinstance(body, dict) and body.get("app_base_url"):
                compose_sync = _maybe_sync_compose_public_url(str(body.get("app_base_url") or ""))
            DEPLOYMENT_MODE = _resolve_deployment_mode()
            payload: dict[str, Any] = {"ok": True, **updated}
            if compose_sync is not None:
                payload["compose_sync"] = compose_sync
            self._json(200, payload)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})

    def _route_pattern_patch_hermes_profile(self, path: str, body: dict) -> None:
        profile_patch_match = re.fullmatch(r"/api/hermes/profiles/([^/]+)", path)
        if not profile_patch_match or profile_patch_match.group(1) in self._HERMES_PROFILE_RESERVED:
            self._json(404, {"error": "not found"})
            return
        if not _role_allows(self, OWNER_ADMIN_ROLES):
            self._json(403, {"ok": False, "error": "forbidden", "required_role": "owner_or_admin"})
            return
        profile = resolve_validated_profile(profile_patch_match.group(1))
        self._json(200, hermes_profile_update(profile, body))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if self._handle_internal_llm_proxy("GET", path):
            return
        if self._handle_internal_action_proxy("GET", path):
            return

        # Auth middleware â€” returns 401 if session required and missing/invalid.
        # In DEV_LOCAL_UNSAFE mode this is a no-op.
        if not _auth_check(self):
            return self._json(401, {"ok": False, "error": "no_session"})

        if SECURE_MODE:
            if not _secure_host_origin_ok(self.command, path, self.headers):
                if not _validate_host(self.headers):
                    return self._json(403, {"error": "invalid host"})
                return self._json(403, {"error": "invalid origin"})

        try:
            if route_registry.dispatch_get(self, path, qs):
                return
            if route_registry.dispatch_pattern("GET", self, path, qs=qs):
                return

            # Serve static files and UI
            if path in ("", "/") or not path.startswith("/api/") and not path.startswith("/assets/") and not path.startswith("/static/"):
                return self._file_public("index.html")
            if path.startswith("/assets/"):
                return self._file_public(path.lstrip("/"))

            return self._json(404, {"error": "not found"})
        except ValueError as exc:
            return self._json(400, {"error": str(exc)})
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
        except Exception as exc:  # noqa: BLE001
            return self._json(500, {"ok": False, "error": str(exc)})

    # ------------------------------------------------------------------
    # First-owner bootstrap (Sprint C: secure single-user install)
    # ------------------------------------------------------------------
    def _first_owner_bootstrap(self, user_id: str, display_name: str, email: str = "") -> dict:
        """Create the owner user + default workspace if no users exist.

        Called by /api/auth/start on first login and by /api/auth/bootstrap.
        Idempotent: if users already exist, returns existing state.
        """
        try:
            conn = _workframe_db()
            existing = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
            if existing and existing["c"] > 0:
                conn.close()
                return {"ok": True, "already_initialized": True, "user_id": user_id}

            now_ts = int(time.time())
            project_name = str(os.environ.get("WORKFRAME_PROJECT", "Workframe") or "Workframe").strip() or "Workframe"
            user_avatar = _pick_user_avatar_url() or None
            ws_logo = _pick_logo_url() or None
            room_logo = ws_logo
            # Create user
            conn.execute(
                "INSERT INTO users (id, email, display_name, avatar_url, role, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (user_id, email, display_name, user_avatar, "owner", "active", str(now_ts), str(now_ts)),
            )
            # Create default workspace
            ws_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO workspaces (id, slug, display_name, owner_id, avatar_url, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (ws_id, "default", project_name, user_id, ws_logo, "active", str(now_ts), str(now_ts)),
            )
            # Create workspace membership
            conn.execute(
                "INSERT INTO workspace_memberships (id, workspace_id, user_id, role, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), ws_id, user_id, "owner", "active", str(now_ts), str(now_ts)),
            )
            # Sprint F: Seed default room
            room_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO rooms (id, workspace_id, name, slug, avatar_url, room_type, status, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (room_id, ws_id, project_name, "general", room_logo, "channel", "active", user_id, str(now_ts), str(now_ts)),
            )
            # Sprint F: Seed default agent profile
            agent_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO agent_profiles (id, workspace_id, slug, display_name, role, model_provider, model_name, is_native, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (agent_id, ws_id, "assistant", "Assistant", "assistant", "openrouter", "default", 0, "active", str(now_ts), str(now_ts)),
            )
            _ensure_user_in_room(conn, room_id, user_id, role="admin")
            _ensure_agent_in_space_room(conn, room_id, agent_id)
            conn.commit()

            # Verify
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            ws_count = conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]
            conn.close()
            return {"ok": True, "already_initialized": False, "user_id": user_id, "workspace_id": ws_id, "workspace_slug": "default", "user_count": user_count, "workspace_count": ws_count}
        except Exception as exc:
            import traceback
            traceback.print_exc()
            return {"ok": False, "error": str(exc)}

    def _complete_install(self, user_id: str, body: dict[str, Any]) -> dict[str, Any]:
        global DEPLOYMENT_MODE
        if not _native_profile_present():
            _ensure_native_hermes_profile()
        data = body if isinstance(body, dict) else {}
        if not user_id:
            return {"ok": False, "error": "no_session"}
        ws_id = _primary_workspace_id(user_id)
        workframe_name = str(data.get("workframe_name") or "").strip()
        if ws_id and workframe_name:
            try:
                conn = _workframe_db()
                conn.execute(
                    """
                    UPDATE workspaces
                    SET display_name = ?, updated_at = ?
                    WHERE id = ? AND deleted_at IS NULL
                    """,
                    (workframe_name, str(int(time.time())), ws_id),
                )
                _sync_workspace_home_room(conn, ws_id)
                conn.commit()
                conn.close()
            except Exception:
                pass
        native_slug = str(NATIVE_PROFILE or "workframe-agent")
        runtime = _runtime_profile_slug(user_id, native_slug)
        agent_id = _ensure_workspace_agent_profile_row(
            native_slug,
            workspace_id=ws_id,
            display_name=str(data.get("agent_name") or f"{native_slug} Agent"),
            role=str(data.get("agent_role") or data.get("agent_tagline") or "Workframe Manager"),
            tagline=str(data.get("agent_tagline") or "Workframe Manager"),
            is_native=True,
        ) or ""
        if not agent_id and ws_id:
            try:
                conn = _workframe_db()
                row = conn.execute(
                    """SELECT id FROM agent_profiles
                       WHERE workspace_id = ? AND is_native = 1 AND deleted_at IS NULL LIMIT 1""",
                    (ws_id,),
                ).fetchone()
                conn.close()
                if row:
                    agent_id = str(row["id"])
            except Exception:
                pass
        room_id = ""
        session_id = ""
        bootstrap_error = ""
        lane: dict[str, Any] = {}
        if ws_id and agent_id:
            try:
                soul = str(data.get("agent_soul") or data.get("bio") or "").strip()
                model = str(data.get("model") or "").strip()
                if not model:
                    model = str(hermes_models("", user_id, ws_id).get("primary") or "").strip()
                lane = bootstrap_agent_dm_lane(
                    user_id,
                    ws_id,
                    native_slug,
                    model=model,
                    soul=soul,
                    bind_session=False,
                    room_name=str(data.get("agent_name") or "Agent").strip() or "Agent",
                    role=str(data.get("agent_role") or data.get("agent_tagline") or "Workframe Manager").strip(),
                    tagline=str(data.get("agent_tagline") or "").strip(),
                    created_by=user_id,
                )
                if not str(lane.get("room_id") or "").strip():
                    bootstrap_error = str(lane.get("error") or "native_agent_dm_bootstrap_failed")
                else:
                    room_id = str(lane["room_id"])
                    session_id = str(lane.get("session_id") or "")
            except Exception as exc:
                bootstrap_error = str(exc)
        if bootstrap_error:
            return {
                "ok": False,
                "error": bootstrap_error,
                "user_id": user_id,
                "workspace_id": ws_id,
                "agent_profile_id": agent_id,
                "runtime_profile": runtime,
                "install_complete": False,
                "steps": lane.get("steps", []) if isinstance(lane, dict) else [],
            }
        stack_config.patch_stack_config({"install_complete": True})
        if ws_id:
            _mark_workspace_install_onboarding_done(ws_id)
        DEPLOYMENT_MODE = _resolve_deployment_mode()
        pub_url = str(stack_config.get_stack_config().get("app_base_url") or "").strip()
        compose_sync = _maybe_sync_compose_public_url(pub_url, restart=True) if pub_url else None
        result: dict[str, Any] = {
            "ok": True,
            "user_id": user_id,
            "workspace_id": ws_id,
            "agent_profile_id": agent_id,
            "runtime_profile": runtime,
            "room_id": room_id,
            "session_id": session_id or _session_id_from_request(self) or "",
            "install_complete": True,
            "steps": lane.get("steps", []) if isinstance(lane, dict) else [],
        }
        if compose_sync is not None:
            result["compose_sync"] = compose_sync
        return result

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------
    def _ensure_user(self, user_id: str, display_name: str, email: str = "") -> None:
        """Ensure a user row + default workspace membership exist. Idempotent."""
        try:
            db = _workframe_db()
            now = str(int(time.time()))
            normalized_email = str(email or "").strip().lower()
            resolved_display_name = str(display_name or "").strip()
            if not resolved_display_name or "@" in resolved_display_name:
                resolved_display_name = _display_name_from_email(normalized_email) or resolved_display_name
            db.execute(
                "INSERT OR IGNORE INTO users (id, email, display_name, role, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (user_id, normalized_email or f"{user_id}@local", resolved_display_name or "Member", "user", "active", now, now),
            )
            if normalized_email:
                db.execute(
                    "UPDATE users SET email = ?, updated_at = ? WHERE id = ?",
                    (normalized_email, now, user_id),
                )
            if resolved_display_name:
                db.execute(
                    """UPDATE users
                       SET display_name = ?, updated_at = ?
                       WHERE id = ?
                         AND (COALESCE(display_name, '') = '' OR display_name LIKE '%@%')""",
                    (resolved_display_name, now, user_id),
                )
            # Ensure membership in default workspace
            ws = db.execute("SELECT id FROM workspaces WHERE slug = ? AND deleted_at IS NULL", ("default",)).fetchone()
            if ws:
                ws_id = str(ws["id"])
                _promote_workspace_owner_if_unclaimed(db, ws_id, user_id)
                existing_membership = db.execute(
                    "SELECT id, role FROM workspace_memberships WHERE workspace_id = ? AND user_id = ? AND deleted_at IS NULL",
                    (ws_id, user_id),
                ).fetchone()
                if existing_membership:
                    _onboard_workspace_member_rooms(db, ws_id, user_id)
                elif not _invite_only_login_enforced():
                    db.execute(
                        "INSERT INTO workspace_memberships (id, workspace_id, user_id, role, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                        (str(uuid.uuid4()), ws_id, user_id, "member", "active", now, now),
                    )
                    _onboard_workspace_member_rooms(db, ws_id, user_id)
            db.commit()
            db.close()
        except Exception:
            pass

    def do_DELETE(self) -> None:  # noqa: N802
        """Route DELETE requests: rooms, members, memory."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if not _auth_check(self):
            return self._json(401, {"ok": False, "error": "no_session"})

        body = self._read_json() if self.headers.get("Content-Length") else {}
        if route_registry.dispatch_pattern(
            "DELETE", self, path, body=body if isinstance(body, dict) else {},
        ):
            return

        return self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if self._handle_internal_llm_proxy("POST", path):
            return
        if self._handle_internal_action_proxy("POST", path):
            return
        if self._handle_internal_run_record(path):
            return

        if SECURE_MODE:
            if not _secure_host_origin_ok(self.command, path, self.headers):
                if not _validate_host(self.headers):
                    return self._json(403, {"error": "invalid host"})
                return self._json(403, {"error": "invalid origin"})
        ct = self.headers.get("Content-Type", "")
        if SECURE_MODE and not _is_json_content_type(ct):
            return self._json(415, {"error": "Content-Type must be application/json"})

        # Auth middleware â€” returns 401 if session required and missing/invalid.
        if not _auth_check(self):
            return self._json(401, {"ok": False, "error": "no_session"})

        try:
            body = self._read_json()
            post_body = body if isinstance(body, dict) else {}
            self._post_qs = qs

            if route_registry.dispatch_post(self, path, post_body):
                return
            if route_registry.dispatch_pattern("POST", self, path, body=post_body):
                return
            return self._json(404, {"error": "not found"})
        except ValueError as exc:
            return self._json(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            return self._json(500, {"ok": False, "error": str(exc)})

    def do_PATCH(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if SECURE_MODE:
            if not _secure_host_origin_ok(self.command, path, self.headers):
                if not _validate_host(self.headers):
                    return self._json(403, {"error": "invalid host"})
                return self._json(403, {"error": "invalid origin"})
        ct = self.headers.get("Content-Type", "")
        if SECURE_MODE and not _is_json_content_type(ct):
            return self._json(415, {"error": "Content-Type must be application/json"})

        if not _auth_check(self):
            return self._json(401, {"ok": False, "error": "no_session"})

        try:
            body = self._read_json()
            if route_registry.dispatch_patch(self, path, body if isinstance(body, dict) else {}):
                return
            if route_registry.dispatch_pattern(
                "PATCH", self, path, body=body if isinstance(body, dict) else {},
            ):
                return

            return self._json(404, {"error": "not found"})
        except ValueError as exc:
            return self._json(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            return self._json(500, {"ok": False, "error": str(exc)})




_ensure_runtime_tokens_table = runtime_tokens.ensure_schema
_create_runtime_token = runtime_tokens.create_token
_validate_runtime_token = runtime_tokens.validate_token

def _log_agent_run(run_id: str, agent_profile_id: str, room_id: str, user_id: str,
                   session_id: str, status: str, model_provider: str, model_name: str,
                   input_tokens: int = 0, output_tokens: int = 0, cost_usd: float = 0.0,
                   credential_binding_id: str = None, error: str = None):
    """Record an agent run in the agent_runs table."""
    now = _utc_now()
    conn = _workframe_db()
    conn.execute(
        """INSERT INTO agent_runs (id, agent_profile_id, room_id, triggered_by_user_id, session_id,
           status, trigger_source, model_provider, model_name, input_tokens, output_tokens,
           cost_usd, error_message, started_at, completed_at, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (run_id, agent_profile_id, room_id, user_id, session_id, status, "chat",
         model_provider, model_name, input_tokens, output_tokens, cost_usd, error,
         now, now if status in ("completed", "failed") else None, now, now)
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Sprint G-K: Agent runs, invites, memory, policies, budgets, grants
# ---------------------------------------------------------------------------

# --- Sprint G: Context package v0 ---
def _build_context_package(user_id: str, workspace_id: str, room_id: str | None = None) -> dict:
    """Assemble context package for an agent run."""
    ctx: dict[str, Any] = {"user_id": user_id, "workspace_id": workspace_id}
    conn = None
    try:
        conn = _workframe_db()
        conn.row_factory = sqlite3.Row
        ws = conn.execute("SELECT id, slug, display_name FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        if ws:
            ctx["workspace"] = dict(ws)
        if room_id:
            room = conn.execute("SELECT id, name, slug, topic FROM rooms WHERE id = ?", (room_id,)).fetchone()
            if room:
                ctx["room"] = dict(room)
        # Sprint I: memory items
        mem_items = conn.execute(
            "SELECT content, scope FROM memory_items WHERE workspace_id = ? AND deleted_at IS NULL ORDER BY updated_at DESC LIMIT 20",
            (workspace_id,)
        ).fetchall()
        if mem_items:
            ctx["memory"] = [dict(m) for m in mem_items]
    except Exception:
        pass
    finally:
        if conn:
            conn.close()
    return ctx


# --- Sprint Gâ€“K: schema migrations live in db_schema.py (WF-032) ---
def _ensure_agent_runs_schema() -> None:
    db_schema.ensure_agent_runs_schema(_workframe_db)


def _ensure_invites_schema() -> None:
    db_schema.ensure_invites_schema(_workframe_db)


def _ensure_memory_schema() -> None:
    db_schema.ensure_memory_schema(_workframe_db)


def _ensure_policies_schema() -> None:
    db_schema.ensure_policies_schema(_workframe_db)


def _ensure_user_prefs_schema() -> None:
    db_schema.ensure_user_prefs_schema(_workframe_db)


def _ensure_budgets_grants_schema() -> None:
    db_schema.ensure_budgets_grants_schema(_workframe_db)


def _set_user_current_workspace(user_id: str, workspace_id: str) -> None:
    user_id = str(user_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if not user_id or not workspace_id:
        return
    try:
        conn = _workframe_db()
        now = str(int(time.time()))
        conn.execute(
            "UPDATE users SET current_workspace_id = ?, updated_at = ? WHERE id = ?",
            (workspace_id, now, user_id),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _resolve_current_workspace(user_id: str, workspaces: list[dict[str, Any]]) -> dict[str, Any] | None:
    user = _get_workframe_user(user_id)
    pref_id = str((user or {}).get("current_workspace_id") or "").strip()
    if pref_id:
        match = next((ws for ws in workspaces if ws.get("id") == pref_id), None)
        if match:
            return match
    default_workspace = next((ws for ws in workspaces if ws.get("slug") == "default"), None)
    return default_workspace or (workspaces[0] if workspaces else None)


def _primary_workspace_id(user_id: str = "") -> str:
    """Default workspace id for this install â€” one DB lookup, ponytail constant for single-ws dogfood."""
    user_id = str(user_id or "").strip()
    if user_id:
        workspaces = _get_user_workspaces(user_id)
        ws = _resolve_current_workspace(user_id, workspaces)
        if ws:
            return str(ws.get("id") or "")
    conn = _workframe_db()
    try:
        row = conn.execute(
            """
            SELECT id FROM workspaces
            WHERE deleted_at IS NULL
            ORDER BY CASE WHEN slug = 'default' THEN 0 ELSE 1 END, created_at ASC
            LIMIT 1
            """,
        ).fetchone()
        return str(row["id"]) if row else ""
    finally:
        conn.close()


def _ensure_workframe_db_schema() -> None:
    """Base workframe.db tables (users, workspaces, schema_migrations, â€¦)."""
    db_schema.ensure_workframe_db_schema(_workframe_db)


def _ensure_workspace_readme() -> None:
    """Seed README.md and AGENTS.md when workspace is empty â€” matches create-workframe scaffold."""
    try:
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        readme = WORKSPACE / "README.md"
        if not readme.is_file():
            readme.write_text(
                f"# {PROJECT_NAME}\n\n"
                "Welcome to Workframe â€” your team's social AI collaboration space.\n\n"
                "Use this file to keep a living record of what this project is, who is on the team, "
                "sub-projects, agents, kanban guidelines, and anything else newcomers should know.\n",
                encoding="utf-8",
            )
        agents = WORKSPACE / "AGENTS.md"
        if agents.is_file():
            return
        native = _native_display_name()
        native_slug = str(NATIVE_PROFILE or "workframe-agent").strip() or "workframe-agent"
        agents.write_text(
            f"# AGENTS â€” {PROJECT_NAME}\n\n"
            "Shared project workspace (`/workspace` â†’ `/opt/data/workspace`). "
            "All users and agents persist deliverables here.\n\n"
            f"## Native agent\n\n"
            f"**{native}** (`{native_slug}`) â€” concierge and orchestrator.\n\n"
            "## Layout\n\n"
            "| Path | Role |\n"
            "|------|------|\n"
            "| `/workspace/` (here) | Project artifacts â€” source of truth for files |\n"
            "| `/opt/data/profiles/<slug>/` | Hermes profile home â€” SOUL, skills, credentials |\n\n"
            "## Rules\n\n"
            "- **All deliverables** (HTML, code, docs, assets) go under `/workspace/`, never profile home.\n"
            "- Use subfolders (`/workspace/games/`, `/workspace/docs/`) to stay organized.\n"
            "- Profile `AGENTS.md` / `SOUL.md` are identity and tooling â€” not project output.\n"
            "- Credentials never in chat â€” use Workframe secure UI.\n"
            "- Chat is intake; `/workspace` is the system of record.\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _assert_api_module_contract() -> None:
    """ponytail: fail fast when dogfood mounts a mismatched API file set."""
    required = (
        "dispatch_get",
        "dispatch_post",
        "dispatch_patch",
        "dispatch_pattern",
        "ROUTE_PATTERNS",
    )
    missing = [name for name in required if not hasattr(route_registry, name)]
    if missing:
        raise SystemExit(
            "stale workframe-api install: route_registry missing "
            + ", ".join(missing)
            + " â€” re-sync services/workframe-api to the install mount"
        )


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_workspace_readme()
    if NATIVE_PROFILE:
        _ensure_profile_terminal_cwd(NATIVE_PROFILE)
    if not PUBLIC_DIR.is_dir():
        raise SystemExit(f"Missing public dir: {PUBLIC_DIR}")
    _assert_api_module_contract()
    _ensure_workframe_db_schema()
    _ensure_default_workspace()
    # Sprint G-K: Ensure all schemas are up to date
    _ensure_agent_runs_schema()
    _ensure_invites_schema()
    _ensure_memory_schema()
    _ensure_policies_schema()
    _ensure_budgets_grants_schema()
    _ensure_user_prefs_schema()
    _ensure_runtime_tokens_table()
    credential_vault.ensure_schema()
    credential_vault.bootstrap_vault(
        allow_generate_file=DEPLOYMENT_MODE != "public_multi_user",
    )
    internal_proxy_auth.bootstrap_proxy_token(
        allow_generate_file=DEPLOYMENT_MODE != "public_multi_user",
    )
    turn_credentials.ensure_schema()
    run_ledger.ensure_schema()
    for warning in _deployment_security_warnings():
        print(f"  WARN deployment: {warning}", flush=True)
    deploy_errors = _deployment_security_errors()
    if deploy_errors:
        raise SystemExit(
            "WORKFRAME_DEPLOYMENT_MODE security violations:\n  - " + "\n  - ".join(deploy_errors)
        )
    threading.Thread(target=_workspace_state_daemon, name="workspace-state", daemon=True).start()
    threading.Thread(target=_kanban_credential_guard_daemon, name="kanban-credential-guard", daemon=True).start()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Workframe API {VERSION} on http://{HOST}:{PORT}")
    print(f"  Hermes: {HERMES_DATA}  Workspace: {WORKSPACE}  Board: {BOARD_DB}")
    print(f"  Deployment: {DEPLOYMENT_MODE}  Secure: {SECURE_MODE}  DevUnsafe: {DEV_LOCAL_UNSAFE}")
    httpd.serve_forever()


def _get_user_workspaces(user_id: str) -> list:
    """Get workspace memberships for a user from the workframe DB."""
    try:
        db = _workframe_db()
        rows = db.execute(
            """SELECT DISTINCT w.id, w.slug, w.display_name, w.description, w.avatar_url, w.settings_json, wm.role
               FROM workspace_memberships wm
               JOIN workspaces w ON w.id = wm.workspace_id
               WHERE wm.user_id = ? AND wm.deleted_at IS NULL AND wm.status = 'active'
               ORDER BY w.slug""",
            (user_id,),
        ).fetchall()
        db.close()
        out = []
        for r in rows:
            settings = _parse_workspace_settings(r) if "settings_json" in r.keys() else {}
            out.append(
                {
                    "id": r["id"],
                    "slug": r["slug"],
                    "display_name": r["display_name"],
                    "description": r["description"] if "description" in r.keys() else "",
                    "tagline": str(settings.get("tagline") or ""),
                    "avatar_url": r["avatar_url"] if "avatar_url" in r.keys() else None,
                    "role": r["role"],
                }
            )
        return out
    except Exception:
        return []




def _mark_workspace_install_onboarding_done(workspace_id: str) -> None:
    """Persist admin wizard progress when install/complete succeeds."""
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return
    try:
        conn = _workframe_db()
        row = conn.execute(
            "SELECT settings_json FROM workspaces WHERE id = ? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        if not row:
            conn.close()
            return
        settings = _parse_workspace_settings(row)
        settings["admin_integrations_done"] = True
        settings["admin_onboarding_done"] = True
        conn.execute(
            "UPDATE workspaces SET settings_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(settings, sort_keys=True), str(int(time.time())), workspace_id),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error:
        pass




if __name__ == "__main__":
    main()
