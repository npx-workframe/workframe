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
from handler_modules import (
    AdminRoutesMixin,
    AuthRoutesMixin,
    ChatRoutesMixin,
    InstallRoutesMixin,
    ProviderRoutesMixin,
    WorkspaceRoutesMixin,
)
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
import chat_bind
import workspace_files
import run_surface_wiring

import workspace_bootstrap

# WF-032: workspace_bootstrap re-exports
_provision_invited_member_agent_runtimes = workspace_bootstrap._provision_invited_member_agent_runtimes
_provision_agent_dm_runtimes = workspace_bootstrap._provision_agent_dm_runtimes
bootstrap_agent_dm_lane = workspace_bootstrap.bootstrap_agent_dm_lane
_onboard_workspace_member_rooms = workspace_bootstrap._onboard_workspace_member_rooms
_join_workspace_default_room = workspace_bootstrap._join_workspace_default_room
_ensure_user_dm_room = workspace_bootstrap._ensure_user_dm_room
_promote_workspace_owner_if_unclaimed = workspace_bootstrap._promote_workspace_owner_if_unclaimed
_sync_workspace_home_room = workspace_bootstrap._sync_workspace_home_room
_ensure_default_workspace = workspace_bootstrap._ensure_default_workspace
_bootstrap_after_setup = workspace_bootstrap._bootstrap_after_setup


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
import avatar_registry
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

# WF-032: avatar_registry re-exports
_load_avatar_catalog = avatar_registry._load_avatar_catalog
_avatar_url_for_id = avatar_registry._avatar_url_for_id
_avatar_id_from_url = avatar_registry._avatar_id_from_url
_normalize_user_avatar_url = avatar_registry._normalize_user_avatar_url
_normalize_logo_url = avatar_registry._normalize_logo_url
_normalize_agent_avatar_patch = avatar_registry._normalize_agent_avatar_patch
_pick_logo_url = avatar_registry._pick_logo_url
_pick_user_avatar_url = avatar_registry._pick_user_avatar_url
_resolve_avatar_fields = avatar_registry._resolve_avatar_fields
_pick_avatar_id = avatar_registry._pick_avatar_id
_upsert_agent_registry_row = avatar_registry._upsert_agent_registry_row
_avatar_id_for_display_name = avatar_registry._avatar_id_for_display_name
_assign_agent_avatar = avatar_registry._assign_agent_avatar

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
_ensure_profile_terminal_cwd = runtime_cohort._ensure_profile_terminal_cwd
_profile_toolsets_ready = runtime_cohort._profile_toolsets_ready

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

# WF-032: chat_bind re-exports
room_chat_bind = chat_bind.room_chat_bind
profile_chat_bind = chat_bind.profile_chat_bind
list_room_sessions = chat_bind.list_room_sessions
profile_chat_activate_room_session = chat_bind.profile_chat_activate_room_session
profile_chat_message = chat_bind.profile_chat_message
_enrich_room_chat_payload = chat_bind._enrich_room_chat_payload
_room_session_rows = chat_bind._room_session_rows
_extract_title = chat_bind._extract_title


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
_ensure_profiles_dir_ready = hermes_profiles._ensure_profiles_dir_ready
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
import hermes_admin
import supervisor_client
import workspace_messaging
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
_USER_LLM_PICKER_TTL_SEC = 60.0
_SESSION_INFO_TTL_SEC = 5.0


def _invalidate_profile_health_cache(profile: str) -> None:
    _profile_health_cache.pop(str(profile or "").strip(), None)


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
_schedule_profile_lease_yaml_reconcile = turn_overlay._schedule_profile_lease_yaml_reconcile
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
_profile_model = chat_sessions._profile_model
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

# WF-032: hermes_admin re-exports
HERMES_COMMANDS = hermes_admin.HERMES_COMMANDS
_known_skill_names = hermes_admin._known_skill_names
_is_known_skill = hermes_admin._is_known_skill
_resolve_command = hermes_admin._resolve_command
hermes_usage = hermes_admin.hermes_usage
hermes_gateway_exec = hermes_admin.hermes_gateway_exec
hermes_profile = hermes_admin.hermes_profile
_agent_db_row = hermes_admin._agent_db_row
hermes_profile_detail = hermes_admin.hermes_profile_detail
hermes_profile_update = hermes_admin.hermes_profile_update
profile_soul_get = hermes_admin.profile_soul_get
profile_soul_set = hermes_admin.profile_soul_set
hermes_debug = hermes_admin.hermes_debug
hermes_insights = hermes_admin.hermes_insights
hermes_gquota = hermes_admin.hermes_gquota
hermes_commands_catalog = hermes_admin.hermes_commands_catalog
hermes_commands_exec = hermes_admin.hermes_commands_exec


# WF-032: supervisor_client re-exports
_supervisor_ready = supervisor_client._supervisor_ready
_supervisor_request = supervisor_client._supervisor_request
_maybe_sync_compose_public_url = supervisor_client._maybe_sync_compose_public_url
_supervisor_gateway_exec = supervisor_client._supervisor_gateway_exec
_supervisor_container_exec = supervisor_client._supervisor_container_exec
_supervisor_profile_lifecycle = supervisor_client._supervisor_profile_lifecycle

# WF-032: workspace_messaging re-exports
_MESSAGING_GATEWAY_ENV = workspace_messaging._MESSAGING_GATEWAY_ENV
_parse_messaging_settings_patch = workspace_messaging._parse_messaging_settings_patch
_workspace_member_platform_ids = workspace_messaging._workspace_member_platform_ids
_merged_messaging_allowed_users = workspace_messaging._merged_messaging_allowed_users
_workspace_messaging_integrations_payload = workspace_messaging._workspace_messaging_integrations_payload
_set_primary_messaging_platforms = workspace_messaging._set_primary_messaging_platforms
_sync_workspace_messaging_gateway = workspace_messaging._sync_workspace_messaging_gateway

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
                """
                SELECT slug, display_name, model_name, model_provider
                FROM agent_profiles WHERE id = ? AND deleted_at IS NULL
                """,
                (agent_id,),
            ).fetchone()
            if agent:
                item["sender_agent_slug"] = str(agent["slug"])
                item["sender_agent_name"] = str(agent["display_name"] or agent["slug"])
                model_name = str(agent["model_name"] or "").strip()
                model_provider = str(agent["model_provider"] or "").strip()
                slug = str(agent["slug"] or "").strip()
                if not model_name and slug:
                    model_name = str(_read_model_block(slug).get("default") or "").strip()
                if not model_provider and slug:
                    model_provider = _llm_billing_provider(slug)
                if model_name:
                    item["model"] = model_name
                if model_provider:
                    item["llm_provider"] = model_provider
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





class Handler(
    AdminRoutesMixin,
    ProviderRoutesMixin,
    AuthRoutesMixin,
    WorkspaceRoutesMixin,
    ChatRoutesMixin,
    InstallRoutesMixin,
    BaseHTTPRequestHandler,
):
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
