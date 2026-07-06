#!/usr/bin/env python3
"""WF-032: extract named functions from server.py into a module with _srv() edges."""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "services" / "workframe-api"
SERVER = API / "server.py"

# ponytail: grow list as py_compile surfaces misses; skip def lines
_SRV_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bHERMES_DATA\b", "_srv().HERMES_DATA"),
    (r"\bPROJECT_NAME\b", "_srv().PROJECT_NAME"),
    (r"\bNATIVE_PROFILE\b", "_srv().NATIVE_PROFILE"),
    (r"\bROUTES_JSON\b", "_srv().ROUTES_JSON"),
    (r"\bAGENTS_JSON\b", "_srv().AGENTS_JSON"),
    (r"\bAVATAR_REGISTRY_JSON\b", "_srv().AVATAR_REGISTRY_JSON"),
    (r"\bGATEWAY_CONTAINER_NAME\b", "_srv().GATEWAY_CONTAINER_NAME"),
    (r"\bSECURE_MODE\b", "_srv().SECURE_MODE"),
    (r"\bSPECIALIST_ROLES\b", "_srv().SPECIALIST_ROLES"),
    (r"\bPROVIDER_CONNECT_CATALOG\b", "_srv().PROVIDER_CONNECT_CATALOG"),
    (r"\b_AGENT_PROFILE_UUID_RE\b", "_srv()._AGENT_PROFILE_UUID_RE"),
    (r"(?<![.\w])_workframe_db\(", "_srv()._workframe_db("),
    (r"(?<![.\w])_gateway_exec\(", "_srv()._gateway_exec("),
    (r"(?<![.\w])_gateway_container_exec\(", "_srv()._gateway_container_exec("),
    (r"(?<![.\w])_docker_exec\(", "_srv()._docker_exec("),
    (r"(?<![.\w])_llm_proxy_base_url\(", "_srv()._llm_proxy_base_url("),
    (r"(?<![.\w])_normalize_profile_config_yaml\(", "_srv()._normalize_profile_config_yaml("),
    (r"(?<![.\w])_coalesce_profile_model_yaml\(", "_srv()._coalesce_profile_model_yaml("),
    (r"(?<![.\w])_ensure_profile_terminal_cwd\(", "_srv()._ensure_profile_terminal_cwd("),
    (r"(?<![.\w])_profile_toolsets_ready\(", "_srv()._profile_toolsets_ready("),
    (r"(?<![.\w])_lookup_agent_profile\(", "_srv()._lookup_agent_profile("),
    (r"(?<![.\w])resolve_validated_profile\(", "_srv().resolve_validated_profile("),
    (r"(?<![.\w])_is_runtime_profile_slug\(", "_srv()._is_runtime_profile_slug("),
    (r"(?<![.\w])_runtime_template_slug\(", "_srv()._runtime_template_slug("),
    (r"(?<![.\w])_hermes_slug_from_agent_ref\(", "_srv()._hermes_slug_from_agent_ref("),
    (r"(?<![.\w])_agent_registry_row\(", "_srv()._agent_registry_row("),
    (r"(?<![.\w])_upsert_agent_registry_row\(", "_srv()._upsert_agent_registry_row("),
    (r"(?<![.\w])_ensure_workspace_agent_profile_row\(", "_srv()._ensure_workspace_agent_profile_row("),
    (r"(?<![.\w])bootstrap_agent_dm_lane\(", "_srv().bootstrap_agent_dm_lane("),
    (r"(?<![.\w])_strip_forbidden_child_skills\(", "_srv()._strip_forbidden_child_skills("),
    (r"(?<![.\w])_install_child_base_artifacts\(", "_srv()._install_child_base_artifacts("),
    (r"(?<![.\w])_apply_profile_identity\(", "_srv()._apply_profile_identity("),
    (r"(?<![.\w])_profile_api_request\(", "_srv()._profile_api_request("),
    (r"(?<![.\w])_ro_sqlite_live\(", "_srv()._ro_sqlite_live("),
    (r"(?<![.\w])_is_space_room\(", "_srv()._is_space_room("),
    (r"(?<![.\w])_room_recent_transcript\(", "_srv()._room_recent_transcript("),
    (r"(?<![.\w])_read_model_block\(", "_srv()._read_model_block("),
    (r"(?<![.\w])_billing_provider_id_from_hermes_config\(", "_srv()._billing_provider_id_from_hermes_config("),
    (r"(?<![.\w])_llm_billing_provider\(", "_srv()._llm_billing_provider("),
    (r"(?<![.\w])_resolve_billing_provider_for_model\(", "_srv()._resolve_billing_provider_for_model("),
    (r"(?<![.\w])_supervisor_profile_lifecycle\(", "_srv()._supervisor_profile_lifecycle("),
    (r"(?<![.\w])gateway_data\(", "_srv().gateway_data("),
    (r"(?<![.\w])_invalidate_gateway_registered_cache\(", "_srv()._invalidate_gateway_registered_cache("),
    (r"(?<![.\w])_invalidate_profile_health_cache\(", "_srv()._invalidate_profile_health_cache("),
    (r"(?<![.\w])_bootstrap_profile_providers\(", "_srv()._bootstrap_profile_providers("),
    (r"(?<![.\w])_configure_profile_api\(", "_srv()._configure_profile_api("),
    (r"(?<![.\w])_patch_profile_gateway_run_script\(", "_srv()._patch_profile_gateway_run_script("),
    (r"(?<![.\w])_profile_api_healthy\(", "_srv()._profile_api_healthy("),
    (r"(?<![.\w])_wait_profile_api_healthy\(", "_srv()._wait_profile_api_healthy("),
    (r"(?<![.\w])_gateway_lifecycle_lock\b", "_srv()._gateway_lifecycle_lock"),
    (r"(?<![.\w])_publish_profile_gateway_secrets\(", "_srv()._publish_profile_gateway_secrets("),
    (r"(?<![.\w])_set_profile_model_api_key\(", "_srv()._set_profile_model_api_key("),
    (r"(?<![.\w])_clear_profile_model_api_key\(", "_srv()._clear_profile_model_api_key("),
    (r"(?<![.\w])_set_profile_model_base_url\(", "_srv()._set_profile_model_base_url("),
    (r"(?<![.\w])_strip_profile_model_proxy_fields\(", "_srv()._strip_profile_model_proxy_fields("),
    (r"(?<![.\w])_set_profile_model_provider\(", "_srv()._set_profile_model_provider("),
    (r"(?<![.\w])_set_profile_model\(", "_srv()._set_profile_model("),
    (r"(?<![.\w])_write_fallback_chain\(", "_srv()._write_fallback_chain("),
    (r"(?<![.\w])_hermes_config_provider_id\(", "_srv()._hermes_config_provider_id("),
    (r"(?<![.\w])_bootstrap_model_after_llm_connect\(", "_srv()._bootstrap_model_after_llm_connect("),
    (r"(?<![.\w])_user_llm_has_provider\(", "_srv()._user_llm_has_provider("),
    (r"(?<![.\w])_provider_connected_for_user\(", "_srv()._provider_connected_for_user("),
    (r"(?<![.\w])_prepare_runtime_profile_credentials\(", "_srv()._prepare_runtime_profile_credentials("),
    (r"(?<![.\w])_sync_oauth_llm_to_profile\(", "_srv()._sync_oauth_llm_to_profile("),
    (r"(?<![.\w])_merge_oauth_auth_into_profile\(", "_srv()._merge_oauth_auth_into_profile("),
    (r"(?<![.\w])_user_hermes_env_path\(", "_srv()._user_hermes_env_path("),
    (r"(?<![.\w])_user_hermes_auth_path\(", "_srv()._user_hermes_auth_path("),
    (r"(?<![.\w])_read_env_map\(", "_srv()._read_env_map("),
    (r"(?<![.\w])_upsert_env_secret\(", "_srv()._upsert_env_secret("),
    (r"(?<![.\w])_user_may_access_runtime_profile\(", "_srv()._user_may_access_runtime_profile("),
    (r"(?<![.\w])_runtime_profile_owner\(", "_srv()._runtime_profile_owner("),
    (r"(?<![.\w])_stack_profile_env\(", "_srv()._stack_profile_env("),
    (r"(?<![.\w])_user_auth_env_keys\(", "_srv()._user_auth_env_keys("),
    (r"(?<![.\w])_default_credential_env_var\(", "_srv()._default_credential_env_var("),
    (r"(?<![.\w])credential_vault\.", "_srv().credential_vault."),
    (r"(?<![.\w])profile_config_yaml\.", "profile_config_yaml."),
    (r"(?<![.\w])turn_credentials\.", "turn_credentials."),
    (r"(?<![.\w])llm_proxy\.", "llm_proxy."),
    (r"(?<![.\w])openrouter_catalog\.", "openrouter_catalog."),
    (r"(?<![.\w])resolve_hermes_profile\(", "_srv().resolve_hermes_profile("),
    (r"(?<![.\w])safe_profile_slug\(", "_srv().safe_profile_slug("),
    (r"(?<![.\w])_utc_now\(", "_srv()._utc_now("),
    (r"(?<![.\w])_user_can_access_room\(", "_srv()._user_can_access_room("),
    (r"(?<![.\w])_resolve_chat_hermes_profile\(", "_srv()._resolve_chat_hermes_profile("),
    (r"(?<![.\w])_resolve_room_agent_chat\(", "_srv()._resolve_room_agent_chat("),
    (r"(?<![.\w])_resolve_bind_profile_arg\(", "_srv()._resolve_bind_profile_arg("),
    (r"(?<![.\w])_get_active_room_session\(", "_srv()._get_active_room_session("),
    (r"(?<![.\w])_default_session_title\(", "_srv()._default_session_title("),
    (r"(?<![.\w])_is_blank_session_title\(", "_srv()._is_blank_session_title("),
    (r"(?<![.\w])_ensure_hermes_session_title\(", "_srv()._ensure_hermes_session_title("),
    (r"(?<![.\w])_upsert_room_session\(", "_srv()._upsert_room_session("),
    (r"(?<![.\w])_resolved_session_title\(", "_srv()._resolved_session_title("),
    (r"(?<![.\w])_create_profile_session_via_api\(", "_srv()._create_profile_session_via_api("),
    (r"(?<![.\w])_session_exists\(", "_srv()._session_exists("),
    (r"(?<![.\w])_session_info\(", "_srv()._session_info("),
    (r"(?<![.\w])_primary_profile\(", "_srv()._primary_profile("),
    (r"(?<![.\w])_profile_api_port\(", "_srv()._profile_api_port("),
    (r"(?<![.\w])_user_can_use_llm\(", "_srv()._user_can_use_llm("),
    (r"(?<![.\w])_lane_registry_json\(", "_srv()._lane_registry_json("),
)


def _header(module: str) -> str:
    return f'''"""WF-032 extract: {module}."""
from __future__ import annotations

import json
import os
import queue
import re
import shlex
import shutil
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from http.server import BaseHTTPRequestHandler

import profile_config_yaml
import user_prefs


def _srv():
    import server as srv

    return srv


'''


def _func_spans(source: str) -> dict[str, tuple[int, int]]:
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    spans: dict[str, tuple[int, int]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno - 1
            end = node.end_lineno or node.lineno
            spans[node.name] = (start, end)
    return spans


def _apply_srv(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("def "):
            out.append(line)
            continue
        for pattern, repl in _SRV_REPLACEMENTS:
            line = re.sub(pattern, repl, line)
        out.append(line)
    return "".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("module")
    parser.add_argument("funcs", nargs="+", help="function names to extract")
    parser.add_argument("--after-import", default="import kanban_cron")
    parser.add_argument("--funcs-file", help="one function name per line")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    funcs = list(args.funcs)
    if args.funcs_file:
        funcs.extend(
            ln.strip()
            for ln in Path(args.funcs_file).read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        )

    source = SERVER.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    spans = _func_spans(source)

    missing = [f for f in funcs if f not in spans]
    if missing:
        print(f"missing functions: {missing}", file=sys.stderr)
        return 1

    remove: set[int] = set()
    extracted_parts: list[str] = []
    for name in funcs:
        start, end = spans[name]
        for i in range(start, end):
            remove.add(i)
        extracted_parts.append("".join(lines[start:end]))
        if end < len(lines) and lines[end].strip() == "":
            extracted_parts.append("\n")

    body = _apply_srv("".join(extracted_parts))
    module_src = _header(args.module) + body

    stub_lines = [f"import {args.module}", "", f"# WF-032: {args.module} re-exports"]
    for name in funcs:
        stub_lines.append(f"{name} = {args.module}.{name}")
    stub_lines.append("")
    stub = "\n".join(stub_lines) + "\n"

    if args.dry_run:
        print(f"Would extract {len(funcs)} functions -> {args.module}.py ({len(body.splitlines())} lines)")
        return 0

    target = API / f"{args.module}.py"
    if target.exists():
        print(f"refusing to overwrite {target}", file=sys.stderr)
        return 1

    target.write_text(module_src, encoding="utf-8")

    new_server: list[str] = []
    inserted = False
    for i, line in enumerate(lines):
        if i in remove:
            continue
        new_server.append(line)
        if not inserted and line.strip() == args.after_import:
            new_server.append(stub)
            inserted = True

    if not inserted:
        print(f"could not find after-import anchor: {args.after_import}", file=sys.stderr)
        target.unlink(missing_ok=True)
        return 1

    SERVER.write_text("".join(new_server), encoding="utf-8")
    print(f"wrote {target.name}; server {len(lines)} -> {len(new_server)} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
