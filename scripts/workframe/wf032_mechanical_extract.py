#!/usr/bin/env python3
"""Mechanical WF-032 extraction: cut server.py ranges into a module with _srv() edges."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "services" / "workframe-api"
SERVER = API / "server.py"

# ponytail: regex edges — add patterns when py_compile surfaces misses
_SRV_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"(?<![.\w])_workframe_db\(", "_srv()._workframe_db("),
    (r"(?<![.\w])_parse_workspace_settings\(", "_srv()._parse_workspace_settings("),
    (r"(?<![.\w])_github_oauth_app_config\(", "_srv()._github_oauth_app_config("),
    (r"(?<![.\w])_github_oauth_configured\(", "_srv()._github_oauth_configured("),
    (r"(?<![.\w])_normalize_logo_url\(", "_srv()._normalize_logo_url("),
    (r"(?<![.\w])_validate_me_profile_updates\(", "_srv()._validate_me_profile_updates("),
    (r"(?<![.\w])_lookup_agent_profile\(", "_srv()._lookup_agent_profile("),
    (r"(?<![.\w])resolve_validated_profile\(", "_srv().resolve_validated_profile("),
    (r"(?<![.\w])_resolve_chat_hermes_profile\(", "_srv()._resolve_chat_hermes_profile("),
    (r"(?<![.\w])_runtime_profile_on_disk\(", "_srv()._runtime_profile_on_disk("),
    (r"(?<![.\w])_is_space_room\(", "_srv()._is_space_room("),
    (r"(?<![.\w])_ro_sqlite_live\(", "_srv()._ro_sqlite_live("),
    (r"(?<![.\w])_resolve_runtime_owner\(", "_srv()._resolve_runtime_owner("),
    (r"(?<![.\w])_prepare_runtime_profile_credentials\(", "_srv()._prepare_runtime_profile_credentials("),
    (r"(?<![.\w])safe_profile_slug\(", "_srv().safe_profile_slug("),
    (r"(?<![.\w])_user_is_workspace_member\(", "_srv()._user_is_workspace_member("),
    (r"(?<![.\w])resolve_runtime_assignee\(", "_srv().resolve_runtime_assignee("),
    (r"(?<![.\w])_is_runtime_profile_slug\(", "_srv()._is_runtime_profile_slug("),
    (r"(?<![.\w])_delegation_grantor_ids_for_grantee\(", "_srv()._delegation_grantor_ids_for_grantee("),
    (r"(?<![.\w])_user_id_for_runtime_slug\(", "_srv()._user_id_for_runtime_slug("),
    (r"(?<![.\w])ensure_user_agent_cohort\(", "_srv().ensure_user_agent_cohort("),
    (r"(?<![.\w])_workspace_member_role\(", "_srv()._workspace_member_role("),
    (r"(?<![.\w])_gateway_exec\(", "_srv()._gateway_exec("),
    (r"(?<![.\w])_profile_dir\(", "_srv()._profile_dir("),
    (r"(?<![.\w])_iso_from_unix\(", "_srv()._iso_from_unix("),
    (r"\bHERMES_DATA\b", "_srv().HERMES_DATA"),
    (r"\bNATIVE_PROFILE\b", "_srv().NATIVE_PROFILE"),
    (r"\bPROJECT_NAME\b", "_srv().PROJECT_NAME"),
    (r"\bROUTES_JSON\b", "_srv().ROUTES_JSON"),
    (r"\bGATEWAY_CONTAINER_NAME\b", "_srv().GATEWAY_CONTAINER_NAME"),
    (r"\b_AGENT_PROFILE_UUID_RE\b", "_srv()._AGENT_PROFILE_UUID_RE"),
    (r"(?<![.\w])_gateway_container_exec\(", "_srv()._gateway_container_exec("),
    (r"(?<![.\w])_docker_exec\(", "_srv()._docker_exec("),
    (r"(?<![.\w])_llm_proxy_base_url\(", "_srv()._llm_proxy_base_url("),
    (r"(?<![.\w])_coalesce_profile_model_yaml\(", "_srv()._coalesce_profile_model_yaml("),
    (r"(?<![.\w])_ensure_profile_terminal_cwd\(", "_srv()._ensure_profile_terminal_cwd("),
    (r"(?<![.\w])_profile_toolsets_ready\(", "_srv()._profile_toolsets_ready("),
    (r"(?<![.\w])_hermes_slug_from_agent_ref\(", "_srv()._hermes_slug_from_agent_ref("),
    (r"(?<![.\w])_agent_identity_fields\(", "_srv()._agent_identity_fields("),
    (r"(?<![.\w])_resolve_avatar_fields\(", "_srv()._resolve_avatar_fields("),
    (r"(?<![.\w])load_agent_registry\(", "_srv().load_agent_registry("),
    (r"(?<![.\w])_upsert_agent_registry_row\(", "_srv()._upsert_agent_registry_row("),
    (r"(?<![.\w])_agent_registry_row\(", "_srv()._agent_registry_row("),
    (r"(?<![.\w])bootstrap_agent_dm_lane\(", "_srv().bootstrap_agent_dm_lane("),
    (r"(?<![.\w])_ensure_workspace_agent_profile_row\(", "_srv()._ensure_workspace_agent_profile_row("),
    (r"(?<![.\w])_ro_sqlite\(", "_srv()._ro_sqlite("),
    (r"(?<![.\w])resolve_hermes_profile\(", "_srv().resolve_hermes_profile("),
    (r"(?<![.\w])_primary_profile\(", "_srv()._primary_profile("),
    (r"(?<![.\w])_is_runtime_profile_slug\(", "_srv()._is_runtime_profile_slug("),
    (r"(?<![.\w])_normalize_profile_config_yaml\(", "_srv()._normalize_profile_config_yaml("),
    (r"(?<![.\w])_bootstrap_profile_providers\(", "_srv()._bootstrap_profile_providers("),
    (r"(?<![.\w])_supervisor_profile_lifecycle\(", "_srv()._supervisor_profile_lifecycle("),
    (r"(?<![.\w])gateway_data\(", "_srv().gateway_data("),
    (r"(?<![.\w])_invalidate_profile_health_cache\(", "_srv()._invalidate_profile_health_cache("),
    (r"(?<![.\w])_invalidate_gateway_registered_cache\(", "_srv()._invalidate_gateway_registered_cache("),
    (r"(?<![.\w])ensure_profile_api\(", "_srv().ensure_profile_api("),
    (r"(?<![.\w])resolve_validated_profile\(", "_srv().resolve_validated_profile("),
    (r"\bSECURE_MODE\b", "_srv().SECURE_MODE"),
    (r"(?<![.\w])_profile_health_cache\b", "_srv()._profile_health_cache"),
    (r"(?<![.\w])_PROFILE_HEALTH_TTL_SEC\b", "_srv()._PROFILE_HEALTH_TTL_SEC"),
    (r"(?<![.\w])_gateway_lifecycle_lock\b", "_srv()._gateway_lifecycle_lock"),
    (r"(?<![.\w])profile_gateway_lifecycle\(", "_srv().profile_gateway_lifecycle("),
    (r"(?<![.\w])profile_gateway_stop\(", "_srv().profile_gateway_stop("),
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
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from http.server import BaseHTTPRequestHandler

import user_prefs


def _srv():
    import server as srv

    return srv


'''


def _apply_srv_replacements(text: str) -> str:
    out_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("def "):
            out_lines.append(line)
            continue
        for pattern, repl in _SRV_REPLACEMENTS:
            line = re.sub(pattern, repl, line)
        out_lines.append(line)
    return "".join(out_lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("module")
    parser.add_argument("ranges", nargs="+", help="e.g. 2745-4328")
    parser.add_argument(
        "--after-import",
        default="import user_prefs",
        help="insert re-export stub after this line in server.py",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target = API / f"{args.module}.py"
    lines = SERVER.read_text(encoding="utf-8").splitlines(keepends=True)

    extracted: list[str] = []
    remove: set[int] = set()
    for spec in args.ranges:
        start, end = map(int, spec.split("-", 1))
        for i in range(start - 1, end):
            extracted.append(lines[i])
            remove.add(i)

    body = _apply_srv_replacements("".join(extracted))
    module_src = _header(args.module) + body

    fn_names = re.findall(r"^def ([a-zA-Z_][\w]*)", body, re.M)
    stub_lines = [f"import {args.module}", "", f"# WF-032: {args.module} re-exports"]
    for name in fn_names:
        stub_lines.append(f"{name} = {args.module}.{name}")
    stub_lines.append("")
    stub = "\n".join(stub_lines) + "\n"

    if args.dry_run:
        print(f"Would write {target} ({len(extracted)} lines, {len(fn_names)} defs)")
        return 0

    if target.exists():
        print(f"refusing to overwrite {target}")
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

    SERVER.write_text("".join(new_server), encoding="utf-8")
    print(f"wrote {target.name} ({len(extracted)} lines); server {len(lines)} -> {len(new_server)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
