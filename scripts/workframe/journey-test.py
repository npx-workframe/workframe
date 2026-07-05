#!/usr/bin/env python3
"""End-to-end single_user_local install journey (ConciergeFlow parity).

Mimics the wizard API path:
  deployment mode -> local-bootstrap -> install/complete -> BYOK -> model -> chat

Requires a running pack install. Set OPENROUTER_API_KEY for the chat step.
Stops at the first failure.
"""
import json
import os
import sys
import urllib.error
import urllib.request
import http.cookiejar

BASE = os.environ.get("WORKFRAME_API_BASE", "http://127.0.0.1:49120")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
PROJECT = os.environ.get("WORKFRAME_PROJECT_NAME", "PackTest")

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
session_id = {"v": ""}


def call(method, path, body=None, stream=False, timeout=120):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if session_id["v"]:
        headers["X-Workframe-Session"] = session_id["v"]
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = opener.open(req, timeout=timeout)
        if stream:
            return resp
        raw = resp.read().decode("utf-8", "replace")
        try:
            return resp.status, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return resp.status, {"_raw": raw}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return e.code, {"_raw": raw}
    except Exception as e:
        return -1, {"_err": str(e)}


def step(name, method, path, body=None, **kw):
    st, data = call(method, path, body, **kw)
    ok = isinstance(st, int) and 200 <= st < 300
    print(f"[{'OK' if ok else 'FAIL'}] {name} -> {st}")
    if not ok:
        print("   " + json.dumps(data)[:600])
        sys.exit(1)
    return data


print(f"=== journey against {BASE} (project={PROJECT}) ===")

print("=== install status ===")
s = step("GET /api/install/status", "GET", "/api/install/status")
print(
    "   install_complete=%s window=%s mode=%s hermes=%s"
    % (s.get("install_complete"), s.get("install_window_open"), s.get("deployment_mode"), s.get("hermes_present"))
)

print("=== wizard: deployment mode single_user_local ===")
step(
    "PATCH /api/install/stack",
    "PATCH",
    "/api/install/stack",
    {"deployment_mode": "single_user_local"},
)

print("=== wizard: /api/setup (early workspace seed) ===")
step(
    "POST /api/setup",
    "POST",
    "/api/setup",
    {"workframe_name": PROJECT, "agent_name": f"{PROJECT} Agent"},
)

print("=== wizard: local-bootstrap (skip SMTP) ===")
boot = step(
    "POST /api/auth/local-bootstrap",
    "POST",
    "/api/auth/local-bootstrap",
    {"display_name": "Owner"},
)
session_id["v"] = boot.get("session_id") or ""
ws = (boot.get("current_workspace") or {}).get("id") or (boot.get("default_workspace") or {}).get("id") or ""
print("   user_id=%s workspace=%s" % (boot.get("user_id"), ws))

print("=== wizard: billing mode BYOK ===")
step(
    f"PATCH /api/workspace/{ws}/integrations",
    "PATCH",
    f"/api/workspace/{ws}/integrations",
    {"credential_mode": "byok", "admin_integrations_done": True},
)

print("=== wizard: business profile ===")
step(
    f"PATCH /api/workspace/{ws}",
    "PATCH",
    f"/api/workspace/{ws}",
    {"display_name": PROJECT, "description": "Pack install journey", "admin_onboarding_done": True},
)

print("=== wizard: owner profile ===")
step(
    "PATCH /api/me",
    "PATCH",
    "/api/me",
    {"display_name": "Owner", "bio": "Journey owner"},
)

print("=== wizard: native agent ===")
step(
    "PATCH /api/me/native-agent",
    "PATCH",
    "/api/me/native-agent",
    {
        "workspace_id": ws,
        "display_name": f"{PROJECT} Agent",
        "tagline": "Workframe Manager",
        "soul": f"You are the Workframe Manager for {PROJECT}.",
    },
)

print("=== finish: /api/install/complete ===")
setup = step(
    "POST /api/install/complete",
    "POST",
    "/api/install/complete",
    {
        "display_name": "Owner",
        "email": "owner@local.workframe",
        "bio": "Journey owner",
        "workframe_name": PROJECT,
        "agent_name": f"{PROJECT} Agent",
        "agent_tagline": "Workframe Manager",
        "agent_soul": f"You are the Workframe Manager for {PROJECT}.",
    },
)
room_id = setup.get("room_id") or ""
runtime = setup.get("runtime_profile") or ""
print(
    "   workspace=%s room=%s runtime=%s install_complete=%s"
    % (setup.get("workspace_id"), room_id, runtime, setup.get("install_complete"))
)
if not room_id:
    print("   steps: " + json.dumps(setup.get("steps") or [])[:600])
    sys.exit(1)

if not OPENROUTER_KEY:
    print("=== SKIP chat (set OPENROUTER_API_KEY to test BYOK + pong) ===")
    print("=== JOURNEY OK (install complete, no chat) ===")
    sys.exit(0)

print("=== connect OpenRouter (user BYOK) ===")
step(
    "POST /api/me/credentials",
    "POST",
    "/api/me/credentials",
    {
        "provider": "openrouter",
        "credential_type": "api_key",
        "secret": OPENROUTER_KEY,
        "env_var": "OPENROUTER_API_KEY",
        "label": "journey",
    },
)

print("=== hermes models ===")
models = step("GET /api/hermes/models", "GET", "/api/hermes/models")
if not models.get("has_llm_provider"):
    print("   BUG: has_llm_provider false after OpenRouter connect")
    sys.exit(1)
or_model = models.get("primary") or "openrouter/owl-alpha"
for row in models.get("suggestions") or []:
    if row.get("provider") == "openrouter" and row.get("model"):
        or_model = row["model"]
        break
print("   model=%s" % or_model)

step("POST /api/hermes/model", "POST", "/api/hermes/model", {"model": or_model, "profile": "", "workspace_id": ws})

print("=== bind DM room ===")
bind = step("POST /api/rooms/%s/bind" % room_id, "POST", "/api/rooms/%s/bind" % room_id, {
    "room_id": room_id,
    "source_id": "ui",
    "client_id": "journey",
    "binding_version": 1,
})
session = bind.get("session_id") or ""
profile = bind.get("profile") or runtime
print("   session=%s profile=%s" % ((session or "")[:12], profile))
if profile == "workframe-agent":
    print("   BUG: bind resolved to template profile, not per-user runtime")
    sys.exit(1)

print("=== stream chat (pong) ===")
resp = call(
    "POST",
    "/api/hermes/profiles/%s/messages/stream" % profile,
    {
        "profile": profile,
        "session_id": session,
        "room_id": room_id,
        "source_id": "ui",
        "client_id": "journey",
        "binding_version": 1,
        "text": "reply with the single word: pong",
    },
    stream=True,
    timeout=180,
)
if isinstance(resp, tuple):
    print("   FAIL stream: " + json.dumps(resp[1])[:300])
    sys.exit(1)

got_text = ""
err = None
try:
    for raw in resp:
        raw = raw.decode("utf-8", "replace")
        for frame in raw.split("\n\n"):
            frame = frame.strip()
            if not frame:
                continue
            data_lines = [line[5:].strip() for line in frame.split("\n") if line.startswith("data:")]
            if not data_lines:
                continue
            try:
                ev = json.loads("\n".join(data_lines))
            except Exception:
                continue
            if "text" in ev:
                got_text += str(ev.get("text") or "")
            if ev.get("error") or ev.get("error_message"):
                err = ev.get("error") or ev.get("error_message")
            if any(line.startswith("event: done") for line in frame.split("\n")):
                break
except Exception as exc:
    print("   stream exc: %s" % exc)
    sys.exit(1)

if err:
    print("   BUG: chat error: %s" % err)
    sys.exit(1)
if not got_text.strip():
    print("   BUG: chat produced no text")
    sys.exit(1)
print("   text=%r" % got_text[:120])
print("=== JOURNEY OK ===")
