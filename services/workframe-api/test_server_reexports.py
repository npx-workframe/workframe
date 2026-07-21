"""WF-032 guard: server.py must re-export symbols still called from extracted modules."""

from __future__ import annotations

import os
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

os.environ.setdefault("WORKFRAME_API_DATA_DIR", str(API_DIR / ".tmp-test-data"))
os.environ.setdefault("HERMES_DATA", str(API_DIR / ".tmp-test-hermes"))
os.environ.setdefault("DEV_LOCAL_UNSAFE", "true")

import server  # noqa: E402


_REQUIRED = (
    "_parse_workspace_settings",
    "_strip_profile_action_env",
    "_strip_profile_llm_env",
    "_user_action_env_specs",
    "_overlay_turn_user_env",
    "_overlay_turn_provider_env",
    "_llm_proxy_base_url",
    "_require_user_provider",
    "_ensure_profile_llm_proxy",
    "_revoke_turn_credential_lease",
    "_sync_profile_provider_env",
    "_session_info",
    "chat_messages",
    "chat_bootstrap",
    "files_archive",
    "files_delete",
    "_gateway_container_exec",
    "_gateway_container_exec_detached",
    "_docker_exec",
    "_gateway_exec",
    "_hermes_agent_version",
    "ensure_profile_api",
    "hermes_commands_catalog",
    "hermes_commands_exec",
    "hermes_usage",
    "_runtime_profile_slug",
    "ensure_runtime_profile",
    "ensure_user_agent_cohort",
    "resolve_runtime_assignee",
    "cohort_runtime_slugs",
    "_prepare_runtime_profile_credentials",
    "purge_stale_runtime_profiles",
    "list_delegation_grants",
    "create_delegation_grant",
    "revoke_delegation_grant",
    "_delegation_grantor_ids_for_grantee",
    "_runtime_profile_on_disk",
    "_invalidate_gateway_registered_cache",
    "_normalize_user_avatar_url",
    "_normalize_logo_url",
    "_normalize_agent_avatar_patch",
    "_resolve_avatar_fields",
    "_upsert_agent_registry_row",
    "_assign_agent_avatar",
    "_avatar_id_for_display_name",
    "_pick_logo_url",
    "_supervisor_ready",
    "_supervisor_request",
    "_maybe_sync_compose_public_url",
    "_supervisor_gateway_exec",
    "_supervisor_container_exec",
    "_supervisor_profile_lifecycle",
    "_parse_messaging_settings_patch",
    "_workspace_messaging_integrations_payload",
    "_sync_workspace_messaging_gateway",
    "room_chat_bind",
    "profile_chat_bind",
    "list_room_sessions",
    "profile_chat_activate_room_session",
    "profile_chat_message",
    "_enrich_room_chat_payload",
    "_room_session_rows",
    "_extract_title",
    "bootstrap_agent_dm_lane",
    "_provision_agent_dm_runtimes",
    "_ensure_default_workspace",
    "_bootstrap_after_setup",
    "_promote_workspace_owner_if_unclaimed",
    "_sync_workspace_home_room",
    "_onboard_workspace_member_rooms",
    "_profile_model",
    "_USER_LLM_PICKER_TTL_SEC",
    "_invalidate_profile_health_cache",
    "_profile_toolsets_ready",
)


def test_server_wf032_reexports_present() -> None:
    missing = [name for name in _REQUIRED if not hasattr(server, name)]
    assert not missing, f"missing server re-exports: {missing}"


if __name__ == "__main__":
    test_server_wf032_reexports_present()
    print("ok")
