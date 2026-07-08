#!/usr/bin/env python3
"""WF-032: extract remaining Handler route groups into handler_modules mixins."""
from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "server.py"

AUTH_METHODS = [
    "_route_post_auth_google_start",
    "_route_post_auth_local_bootstrap",
    "_route_post_auth_bootstrap",
    "_route_post_setup",
    "_route_post_auth_start",
    "_route_post_auth_verify",
    "_route_post_auth_logout",
    "_route_post_auth_refresh",
    "_route_get_auth_hermes_dashboard_gate",
    "_route_get_auth_google_callback",
    "_route_get_oauth_github_callback",
    "_route_get_oauth_discord_callback",
    "_route_get_oauth_stripe_callback",
    "_route_get_me",
    "_route_get_me_onboarding",
    "_route_patch_me",
    "_route_patch_me_native_agent",
]

PROVIDER_METHODS = [
    "_handle_internal_llm_proxy",
    "_handle_internal_action_proxy",
    "_handle_internal_run_record",
    "_route_get_user_credentials",
    "_route_get_me_credentials",
    "_route_get_me_providers",
    "_route_post_me_credentials",
    "_route_post_me_telegram_link",
    "_route_pattern_get_me_oauth_status",
    "_route_pattern_get_agent_credentials",
    "_route_pattern_post_me_oauth_start",
    "_route_pattern_post_me_providers_disconnect",
    "_route_pattern_delete_me_credentials",
]

ADMIN_METHODS = [
    "_route_get_meta",
    "_route_get_health",
    "_route_get_setup_status",
    "_route_get_public_site_meta",
    "_route_get_public_link_preview",
    "_route_get_public_manifest",
    "_route_get_me_cohort",
    "_route_get_agents",
    "_route_get_snapshot",
    "_route_get_activity_detail",
    "_route_get_files_tree",
    "_route_get_files_list",
    "_route_get_files_state",
    "_route_get_files_read",
    "_route_get_files_raw",
    "_route_get_routes",
    "_route_post_files_write",
    "_route_post_files_upload",
    "_route_get_admin_vault_status",
    "_route_get_doctor_agent_dm_runtimes",
    "_route_get_admin_updates",
    "_route_post_admin_updates_apply",
    "_route_post_admin_stack_restart_gateway",
    "_route_post_admin_vault_init",
    "_route_post_admin_vault_unlock",
    "_route_post_admin_vault_seal",
    "_route_post_admin_vault_wipe",
    "_route_get_supervisor_profile_status",
    "_route_get_supervisor_stack_status",
    "_route_get_admin_audit",
    "_route_get_events",
    "_route_pattern_get_public_branding",
    "_supervisor_proxy_post",
    "_route_post_supervisor_profile_start",
    "_route_post_supervisor_profile_stop",
    "_route_post_supervisor_profile_disable",
    "_route_pattern_post_memory",
    "_route_pattern_delete_memory",
    "_route_patch_doctor_repair",
]

MODULE_SPECS: dict[str, tuple[str, str, list[str]]] = {
    "handler_auth.py": (
        "AuthRoutesMixin",
        "Auth / session / OAuth callback route handlers (WF-032 slice).",
        AUTH_METHODS,
    ),
    "handler_provider.py": (
        "ProviderRoutesMixin",
        "Provider credentials / OAuth connect / internal LLM proxy (WF-032 slice).",
        PROVIDER_METHODS,
    ),
    "handler_admin.py": (
        "AdminRoutesMixin",
        "Admin / meta / doctor / supervisor / data-read routes (WF-032 slice).",
        ADMIN_METHODS,
    ),
}

IMPORTS_BY_MODULE = {
    "handler_auth.py": """\
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
from email_sender import APP_BASE_URL
""",
    "handler_provider.py": """\
from __future__ import annotations

import sqlite3
from typing import Any

import action_proxy
import internal_proxy_auth
import llm_proxy
import openrouter_catalog
import platform_auth
import run_surface_wiring
""",
    "handler_admin.py": """\
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import urllib.parse
from pathlib import Path
from typing import Any

import activity_feed
import credential_vault
import doctor_audit
import site_meta
import stack_updates
from supervisor_client import _supervisor_request
""",
}


def _read_server() -> str:
    return SERVER.read_text(encoding="utf-8-sig")


def _server_names() -> set[str]:
    tree = ast.parse(_read_server())
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _extract_handler_methods(source: str, wanted: set[str]) -> dict[str, str]:
    lines = source.splitlines()
    in_handler = False
    class_indent = 0
    body_indent = 4
    current: str | None = None
    buf: list[str] = []
    out: dict[str, list[str]] = {}

    for line in lines:
        if not in_handler:
            if line.startswith("class Handler("):
                in_handler = True
                class_indent = len(line) - len(line.lstrip())
                body_indent = class_indent + 4
            continue
        stripped = line.lstrip()
        if not stripped:
            if current:
                buf.append(line)
            continue
        indent = len(line) - len(stripped)
        if indent <= class_indent and stripped and not stripped.startswith("#"):
            break
        if stripped.startswith("def ") and indent == body_indent:
            if current and current in wanted:
                out[current] = buf
            name = stripped.split("(")[0].replace("def ", "").strip()
            current = name if name in wanted else None
            buf = [line] if current else []
            continue
        if current:
            buf.append(line)

    if current and current in wanted:
        out[current] = buf
    return {k: "\n".join(v).rstrip() + "\n" for k, v in out.items()}


def _rewrite_method_body(method_src: str, server_names: set[str]) -> str:
    lines = method_src.splitlines()
    if not lines:
        return method_src
    def_line = lines[0]
    body_lines = lines[1:]
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)
    if not body_lines:
        return method_src

    body_indent = len(body_lines[0]) - len(body_lines[0].lstrip())
    dedented = textwrap.dedent("\n".join(body_lines))

    # Lazy rewrite: prefix server-level bare names with srv.
    tokens = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", dedented))
    skip = {
        "self",
        "True",
        "False",
        "None",
        "dict",
        "list",
        "str",
        "int",
        "bool",
        "Any",
        "Exception",
        "ValueError",
        "RuntimeError",
        "OSError",
        "sqlite3",
        "json",
        "os",
        "re",
        "time",
        "uuid",
        "secrets",
        "urllib",
        "Path",
        "datetime",
        "timezone",
        "auth_rate_limit",
        "google_auth",
        "stack_config",
        "APP_BASE_URL",
        "action_proxy",
        "internal_proxy_auth",
        "llm_proxy",
        "openrouter_catalog",
        "platform_auth",
        "run_surface_wiring",
        "activity_feed",
        "credential_vault",
        "doctor_audit",
        "site_meta",
        "stack_updates",
        "_supervisor_request",
    }
    replace_names = sorted((tokens & server_names) - skip, key=len, reverse=True)
    for name in replace_names:
        dedented = re.sub(rf"\b{name}\b", f"srv.{name}", dedented)

    new_body = textwrap.indent(
        "srv = _srv()\n" + dedented.rstrip() + "\n",
        " " * body_indent,
    )
    return def_line + "\n" + new_body


def _build_module(filename: str, class_name: str, doc: str, methods: list[str], extracted: dict[str, str], server_names: set[str]) -> str:
    parts = [f'"""{doc}"""', "", IMPORTS_BY_MODULE[filename].rstrip(), "", "", "def _srv():", "    import server", "", "    return server", "", "", f"class {class_name}:"]
    missing = []
    for name in methods:
        if name not in extracted:
            missing.append(name)
            continue
        rewritten = _rewrite_method_body(extracted[name], server_names)
        parts.append("")
        parts.append(textwrap.indent(rewritten.rstrip(), "    "))
    if missing:
        raise SystemExit(f"{filename}: missing methods {missing}")
    return "\n".join(parts) + "\n"


def main() -> None:
    source = _read_server()
    all_methods = set(AUTH_METHODS + PROVIDER_METHODS + ADMIN_METHODS)
    extracted = _extract_handler_methods(source, all_methods)
    server_names = _server_names()

    for filename, (class_name, doc, methods) in MODULE_SPECS.items():
        mod_path = ROOT / "handler_modules" / filename
        mod_path.write_text(_build_module(filename, class_name, doc, methods, extracted, server_names), encoding="utf-8")
        print(f"wrote {mod_path.name} ({len(methods)} methods)")

    # Strip extracted methods from server.py Handler class
    lines = source.splitlines(keepends=True)
    in_handler = False
    class_indent = 0
    body_indent = 4
    skip = False
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not in_handler:
            out.append(line)
            if line.startswith("class Handler("):
                in_handler = True
                class_indent = len(line) - len(line.lstrip())
                body_indent = class_indent + 4
            i += 1
            continue
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if indent <= class_indent and stripped and not stripped.startswith("#"):
            skip = False
            out.append(line)
            i += 1
            continue
        if stripped.startswith("def ") and indent == body_indent:
            name = stripped.split("(")[0].replace("def ", "").strip()
            if name in all_methods:
                skip = True
                i += 1
                continue
            skip = False
            out.append(line)
            i += 1
            continue
        if skip:
            i += 1
            continue
        out.append(line)
        i += 1

    new_source = "".join(out)
    # Update Handler class bases
    new_source = new_source.replace(
        "class Handler(WorkspaceRoutesMixin, ChatRoutesMixin, InstallRoutesMixin, BaseHTTPRequestHandler):",
        "class Handler(\n"
        "    AdminRoutesMixin,\n"
        "    ProviderRoutesMixin,\n"
        "    AuthRoutesMixin,\n"
        "    WorkspaceRoutesMixin,\n"
        "    ChatRoutesMixin,\n"
        "    InstallRoutesMixin,\n"
        "    BaseHTTPRequestHandler,\n"
        "):",
    )
    new_source = new_source.replace(
        "from handler_modules import ChatRoutesMixin, InstallRoutesMixin, WorkspaceRoutesMixin",
        "from handler_modules import (\n"
        "    AdminRoutesMixin,\n"
        "    AuthRoutesMixin,\n"
        "    ChatRoutesMixin,\n"
        "    InstallRoutesMixin,\n"
        "    ProviderRoutesMixin,\n"
        "    WorkspaceRoutesMixin,\n"
        ")",
    )
    # Remove WF-037 comment block before first remaining route if empty gap
    new_source = re.sub(
        r"\n    # WF-037 data-read GET handlers \(registered in route_registry\.ROUTES\)\n\n",
        "\n",
        new_source,
        count=1,
    )
    SERVER.write_text(new_source, encoding="utf-8")
    print(f"patched server.py -> {(len(new_source.splitlines()))} lines")

    init = ROOT / "handler_modules" / "__init__.py"
    init.write_text(
        '"""Handler route mixins extracted from server.Handler (WF-032)."""\n\n'
        "from handler_modules.handler_admin import AdminRoutesMixin\n"
        "from handler_modules.handler_auth import AuthRoutesMixin\n"
        "from handler_modules.handler_chat import ChatRoutesMixin\n"
        "from handler_modules.handler_install import InstallRoutesMixin\n"
        "from handler_modules.handler_provider import ProviderRoutesMixin\n"
        "from handler_modules.handler_workspace import WorkspaceRoutesMixin\n\n"
        '__all__ = [\n'
        '    "AdminRoutesMixin",\n'
        '    "AuthRoutesMixin",\n'
        '    "ChatRoutesMixin",\n'
        '    "InstallRoutesMixin",\n'
        '    "ProviderRoutesMixin",\n'
        '    "WorkspaceRoutesMixin",\n'
        "]\n",
        encoding="utf-8",
    )
    print("updated handler_modules/__init__.py")


if __name__ == "__main__":
    main()
