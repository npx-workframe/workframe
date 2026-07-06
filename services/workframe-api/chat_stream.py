"""WF-032 extract: chat_stream."""
from __future__ import annotations

import json
import os
import queue
import re
import secrets
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
from typing import Any, Iterator

from http.server import BaseHTTPRequestHandler

import concierge
import lane_bindings
import llm_error_glossary
import run_authority
import run_ledger
import turn_credentials
import user_prefs
from domain.entities import RunStatus


def _srv():
    import server as srv

    return srv


def _live_stream_text(data: dict[str, Any]) -> str:
    return str(data.get("delta") or data.get("text") or data.get("content") or "")


def _live_strip_placeholders(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        segment
        for segment in segments
        if not (
            segment.get("kind") == "text"
            and str(segment.get("text") or "") in ("Thinking…", "…", "")
        )
    ]


def _live_reduce_stream_event(
    segments: list[dict[str, Any]],
    event: str,
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    if event in ("thinking.delta", "reasoning.delta"):
        text = _live_stream_text(data)
        if not text:
            return segments
        base = _live_strip_placeholders(segments)
        if base and base[-1].get("kind") == "thinking":
            merged = dict(base[-1])
            merged["text"] = str(merged.get("text") or "") + text
            return [*base[:-1], merged]
        return [*base, {"kind": "thinking", "text": text}]
    if event in ("message.delta", "assistant.delta"):
        text = _live_stream_text(data)
        if not text:
            return segments
        base = _live_strip_placeholders(segments)
        if base and base[-1].get("kind") == "text":
            merged = dict(base[-1])
            merged["text"] = str(merged.get("text") or "") + text
            return [*base[:-1], merged]
        return [*base, {"kind": "text", "text": text}]
    if event == "tool.started":
        name = str(data.get("tool_name") or "tool")
        preview = str(data.get("preview") or "")
        base = _live_strip_placeholders(segments)
        for idx in range(len(base) - 1, -1, -1):
            segment = base[idx]
            if segment.get("kind") == "tool" and segment.get("name") == name:
                updated = dict(segment)
                updated["status"] = "running"
                if preview:
                    updated["preview"] = preview
                return [*base[:idx], updated, *base[idx + 1 :]]
        tool = {"kind": "tool", "name": name, "status": "running"}
        if preview:
            tool["preview"] = preview
        return [*base, tool]
    if event in ("tool.completed", "tool.failed"):
        name = str(data.get("tool_name") or "tool")
        output = str(data.get("preview") or data.get("output") or "")
        base = _live_strip_placeholders(segments)
        for idx in range(len(base) - 1, -1, -1):
            segment = base[idx]
            if segment.get("kind") == "tool" and segment.get("name") == name:
                updated = dict(segment)
                updated["status"] = "done"
                updated["output"] = output or str(segment.get("output") or segment.get("preview") or "")
                updated.pop("preview", None)
                return [*base[:idx], updated, *base[idx + 1 :]]
        return [*base, {"kind": "tool", "name": name, "status": "done", "output": output}]
    if event == "tool.progress":
        name = str(data.get("tool_name") or "tool")
        if name == "_thinking":
            return segments
        preview = _live_stream_text(data)
        base = _live_strip_placeholders(segments)
        for idx in range(len(base) - 1, -1, -1):
            segment = base[idx]
            if segment.get("kind") == "tool" and segment.get("name") == name:
                updated = dict(segment)
                updated["status"] = "running"
                if preview:
                    updated["preview"] = preview
                return [*base[:idx], updated, *base[idx + 1 :]]
        tool = {"kind": "tool", "name": name, "status": "running"}
        if preview:
            tool["preview"] = preview
        return [*base, tool]
    if event in ("message.complete", "assistant.completed"):
        final = str(data.get("content") or data.get("text") or "").strip()
        if not final:
            return segments
        base = _live_strip_placeholders(segments)
        if base and base[-1].get("kind") == "text":
            merged = dict(base[-1])
            merged["text"] = final
            return [*base[:-1], merged]
        return [*base, {"kind": "text", "text": final}]
    if event == "error":
        text = str(data.get("error") or data.get("message") or "Stream error")
        return _live_strip_placeholders(segments) + [{"kind": "text", "text": text}]
    return segments


def _segments_to_reply_text(segments: list[dict[str, Any]]) -> str:
    return "".join(
        str(segment.get("text") or "")
        for segment in segments
        if segment.get("kind") == "text"
    ).strip()


def _parse_profile_stream_frame(frame: bytes) -> tuple[str, dict[str, Any]] | None:
    text = frame.decode("utf-8", errors="replace")
    lines = text.splitlines()
    event_name = ""
    data_lines: list[str] = []
    for line in lines:
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if not event_name and not data_lines:
        return None
    data: dict[str, Any] = {}
    if data_lines:
        try:
            parsed = json.loads("\n".join(data_lines))
            data = parsed if isinstance(parsed, dict) else {"text": str(parsed)}
        except Exception:  # noqa: BLE001
            data = {"text": "\n".join(data_lines)}
    normalized = event_name
    if event_name in ("assistant.delta", "message.delta"):
        normalized = "message.delta"
    elif event_name in ("assistant.completed", "message.complete"):
        normalized = "message.complete"
    elif event_name in ("thinking.delta", "reasoning.delta"):
        normalized = "thinking.delta"
    return normalized, data


def _iter_profile_stream_frames(upstream: Any) -> Iterator[tuple[str, dict[str, Any]]]:
    buffer = b""
    while True:
        chunk = upstream.read(4096)
        if not chunk:
            break
        buffer += chunk
        while True:
            sep = buffer.find(b"\n\n")
            crlf_sep = buffer.find(b"\r\n\r\n")
            if sep == -1 and crlf_sep == -1:
                break
            if crlf_sep != -1 and (sep == -1 or crlf_sep < sep):
                idx = crlf_sep
                delimiter_len = 4
            else:
                idx = sep
                delimiter_len = 2
            frame = buffer[:idx]
            buffer = buffer[idx + delimiter_len :]
            parsed = _parse_profile_stream_frame(frame)
            if parsed:
                yield parsed
    tail = buffer.strip()
    if tail:
        parsed = _parse_profile_stream_frame(tail)
        if parsed:
            yield parsed

def _emit_stream_chat_error(
    handler: BaseHTTPRequestHandler,
    message: str = "",
    *,
    entry: dict[str, Any] | None = None,
) -> None:
    """SSE error frame — structured playbook when entry supplied."""
    payload = llm_error_glossary.notice_payload(entry) if entry else {}
    if not payload:
        text = str(message or "").strip() or "Chat failed."
        payload = {"error": text, "text": text, "message": text}
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.end_headers()
        body = json.dumps(payload)
        handler.wfile.write(f"event: error\ndata: {body}\n\n".encode("utf-8"))
        handler.wfile.write(b"event: done\ndata: {}\n\n")
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return


def _open_profile_stream(
    handler: BaseHTTPRequestHandler,
    prof: str,
    *,
    model_used: str,
    llm_provider: str,
    api_port: int,
) -> None:
    """Flush SSE headers + run.started before blocking on gateway/model."""
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "keep-alive")
    handler.send_header("X-Workframe-Profile", prof)
    handler.send_header("X-Workframe-Api-Port", str(api_port))
    handler.end_headers()
    handler.wfile.write(
        (
            "event: run.started\n"
            f"data: {json.dumps({'text': 'Contacting model...', 'model': model_used, 'llm_provider': llm_provider})}\n\n"
        ).encode("utf-8"),
    )
    handler.wfile.flush()


def _emit_stream_error_body(
    handler: BaseHTTPRequestHandler,
    *,
    entry: dict[str, Any] | None = None,
    message: str = "",
) -> None:
    """Error/done frames when SSE headers were already sent."""
    payload = llm_error_glossary.notice_payload(entry) if entry else {}
    if not payload:
        text = str(message or "").strip() or "Chat failed."
        payload = {"error": text, "text": text, "message": text}
    try:
        body = json.dumps(payload)
        handler.wfile.write(f"event: error\ndata: {body}\n\n".encode("utf-8"))
        handler.wfile.write(b"event: done\ndata: {}\n\n")
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return


def _emit_stream_concierge(handler: BaseHTTPRequestHandler, entry: dict[str, Any]) -> None:
    """Deterministic assistant reply when LLM path is unavailable."""
    payload = llm_error_glossary.notice_payload(entry)
    text = str(payload.get("message") or "")
    hint = str(payload.get("hint") or "").strip()
    if hint:
        text = f"{text}\n\n{hint}"
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.end_headers()
        handler.wfile.write(
            f"event: concierge\ndata: {json.dumps(payload)}\n\n".encode("utf-8"),
        )
        handler.wfile.write(
            f"event: message.complete\ndata: {json.dumps({'content': text, 'text': text})}\n\n".encode(
                "utf-8",
            ),
        )
        handler.wfile.write(b"event: done\ndata: {}\n\n")
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return


def _log_llm_failure(
    handler: BaseHTTPRequestHandler,
    code: str,
    *,
    provider: str = "",
    model: str = "",
    profile: str = "",
) -> None:
    if hasattr(handler, "_log_audit"):
        handler._log_audit(  # type: ignore[attr-defined]
            "llm_failure",
            "llm",
            profile or provider or "unknown",
            f"code={code} provider={provider} model={model}",
        )


def _run_authority_context_for_chat(
    user_id: str,
    workspace_id: str,
    provider: str,
) -> run_authority.RunAuthorityContext:
    user = str(user_id or "").strip()
    ws = str(workspace_id or "").strip()
    provider_name = str(provider or "openrouter").strip().lower()
    mode = _srv()._workspace_credential_mode(None, ws)
    user_only = _srv()._provider_user_only(provider_name)
    oauth_connected = False
    oauth_spec = _srv()._oauth_llm_provider_spec(provider_name)
    if oauth_spec and user:
        oauth_connected = _srv()._hermes_oauth_tokens_present(user, _srv()._hermes_auth_id_for_spec(oauth_spec))
    user_resolved = _srv()._resolve_credential(user, ws, provider_name, user_only=True) if user else None
    user_has = bool(user_resolved and _srv()._credential_secret(user_resolved, user))
    ws_has = False
    if ws and not user_only:
        ws_resolved = _srv()._resolve_credential(user, ws, provider_name, user_only=False)
        ws_has = bool(ws_resolved and _srv()._credential_secret(ws_resolved, user))
    grantors: dict[str, bool] = {}
    if user and ws:
        for grantor_id in _srv()._delegation_grantor_ids_for_grantee(user, ws):
            g_resolved = _srv()._resolve_credential(grantor_id, ws, provider_name, user_only=True)
            grantors[grantor_id] = bool(g_resolved and _srv()._credential_secret(g_resolved, grantor_id))
    return run_authority.RunAuthorityContext(
        workspace_credential_mode=mode,
        provider_user_only=user_only,
        user_has_credential=user_has,
        workspace_has_credential=ws_has,
        grantor_has_credential=grantors,
        oauth_connected=oauth_connected,
    )


def stream_profile_chat(handler: BaseHTTPRequestHandler, profile: str, payload: dict[str, Any]) -> None:
    _triggering_user = str(payload.get("user_id", "") or "")
    _workspace_id = str(payload.get("workspace_id", "") or "")
    _room_id = str(payload.get("room_id") or "").strip()
    _turn_run_id = str(uuid.uuid4())
    prof, _template_prof = _srv()._resolve_bind_profile_arg(
        profile, _triggering_user, _room_id, _workspace_id,
    )
    session_id = str(payload.get("session_id") or "").strip()
    text = str(payload.get("text") or "").strip()
    if not session_id:
        raise ValueError("session_id required")
    if not text:
        raise ValueError("text required")
    model_block = _srv()._read_model_block(prof)
    llm_provider = _srv()._llm_billing_provider(
        prof, user_id=_triggering_user, workspace_id=_workspace_id, block=model_block,
    )
    model_used = str(model_block.get("default") or "").strip()
    _auth_decision: run_authority.RunAuthorityDecision | None = None
    if _triggering_user:
        run_ledger.ensure_schema()
        auth_req = run_authority.chat_run_request(
            triggering_user_id=_triggering_user,
            profile_slug=prof,
            workspace_id=_workspace_id,
            provider=llm_provider,
            room_id=_room_id or None,
        )
        auth_ctx = _run_authority_context_for_chat(_triggering_user, _workspace_id, llm_provider)
        _auth_decision = run_authority.evaluate_run_authority(
            auth_req, auth_ctx, run_id=_turn_run_id,
        )
        conn = _srv()._workframe_db()
        try:
            run_ledger.record_authority_decision(
                conn,
                run_id=_turn_run_id,
                request_surface=auth_req.surface,
                actor_type=auth_req.actor_type,
                actor_id=auth_req.actor_id,
                triggering_user_id=_triggering_user,
                workspace_id=_workspace_id or "default",
                agent_id=auth_req.agent_id,
                runtime_binding_id=auth_req.runtime_binding_id,
                profile_slug=prof,
                provider=llm_provider,
                room_id=_room_id or None,
                session_id=session_id,
                decision=_auth_decision,
            )
            conn.commit()
        finally:
            conn.close()
        if not _auth_decision.allowed:
            entry = concierge.respond(text, situation="no_provider")
            _log_llm_failure(
                handler,
                str(_auth_decision.deny_reason or "run_denied"),
                provider=llm_provider,
                profile=prof,
            )
            _emit_stream_concierge(handler, entry)
            return
    llm_ready = bool(
        _triggering_user
        and _srv()._user_can_use_llm(_triggering_user, _workspace_id, llm_provider)
    )
    if _triggering_user and not llm_ready:
        entry = concierge.respond(text, situation="no_provider")
        _log_llm_failure(handler, str(entry.get("code") or "no_llm_provider"), provider=llm_provider, profile=prof)
        _emit_stream_concierge(handler, entry)
        return
    api_port = _srv()._profile_api_port(prof)
    _open_profile_stream(
        handler,
        prof,
        model_used=model_used,
        llm_provider=llm_provider,
        api_port=api_port,
    )
    try:
        _srv().ensure_profile_api(
            prof,
            _triggering_user,
            _workspace_id,
        )
        if _triggering_user:
            _srv()._require_user_provider(_triggering_user, _workspace_id, llm_provider)
            _srv()._overlay_turn_provider_env(
                prof, _triggering_user, _workspace_id, llm_provider, _turn_run_id,
            )
            _srv()._overlay_turn_user_env(prof, _triggering_user, _workspace_id, _turn_run_id)
    except ValueError as exc:
        err_text = str(exc)
        if "no_llm_provider_for_user" in err_text:
            entry = concierge.respond(text, situation="no_provider")
            _log_llm_failure(handler, "no_llm_provider", provider=llm_provider, profile=prof)
            _emit_stream_error_body(handler, entry=entry)
            return
        entry = llm_error_glossary.classify_exception_text(err_text)
        _log_llm_failure(handler, str(entry.get("code") or ""), provider=llm_provider, profile=prof)
        _emit_stream_error_body(handler, entry=entry)
        return
    upstream_body = json.dumps(_srv()._profile_turn_payload(prof, text, _room_id)).encode("utf-8")

    if _triggering_user and _workspace_id:
        _resolved_cred = _srv()._resolve_credential(
            _triggering_user,
            _workspace_id,
            llm_provider,
            user_only=True,
        )
        if _resolved_cred:
            try:
                _body = json.loads(upstream_body)
                _body["_credential_override"] = _resolved_cred["credential_ref"]
                _body["_credential_scope"] = _resolved_cred["scope"]
                upstream_body = json.dumps(_body).encode("utf-8")
            except Exception:
                pass

    url = f"http://gateway:{api_port}/api/sessions/{urllib.parse.quote(session_id, safe='')}/chat/stream"
    headers = {
        "Authorization": f"Bearer {_srv()._profile_api_key(prof)}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=upstream_body, headers=headers, method="POST")
    saw_complete = False
    complete_text = ""
    try:
        upstream = urllib.request.urlopen(req, timeout=3600)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except Exception:  # noqa: BLE001
            data = {"error": raw or f"upstream stream failed: {exc.code}"}
        entry = llm_error_glossary.classify_exception_text(str(data))
        _emit_stream_error_body(handler, entry=entry)
        return
    except OSError as exc:
        entry = llm_error_glossary.classify_exception_text(str(exc))
        _emit_stream_error_body(handler, entry=entry)
        return

    try:
        buffer = b""

        def _rewrite_event_frame(frame: bytes) -> bytes:
            nonlocal saw_complete, complete_text
            text = frame.decode("utf-8", errors="replace")
            lines = text.splitlines()
            event_name = ""
            data_lines: list[str] = []
            other_lines: list[str] = []
            for line in lines:
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
                elif line.strip():
                    other_lines.append(line)

            normalized = event_name
            if event_name in ("assistant.delta", "message.delta"):
                normalized = "message.delta"
            elif event_name in ("assistant.completed", "message.complete"):
                normalized = "message.complete"
                saw_complete = True
                if data_lines:
                    try:
                        payload = json.loads("\n".join(data_lines))
                        complete_text = str(
                            payload.get("content") or payload.get("text") or ""
                        ).strip()
                    except Exception:  # noqa: BLE001
                        complete_text = ""
            elif event_name in ("thinking.delta", "reasoning.delta"):
                normalized = "thinking.delta"
            elif event_name in ("run.failed",):
                normalized = "error"
            elif event_name == "error":
                normalized = "error"

            output_lines: list[str] = []
            if normalized:
                output_lines.append(f"event: {normalized}")
            output_lines.extend(other_lines)
            output_lines.extend(f"data: {line}" for line in data_lines)
            return ("\n".join(output_lines) + "\n\n").encode("utf-8") if output_lines else b""

        while True:
            chunk = upstream.read(4096)
            if not chunk:
                break
            buffer += chunk
            while True:
                sep = buffer.find(b"\n\n")
                crlf_sep = buffer.find(b"\r\n\r\n")
                if sep == -1 and crlf_sep == -1:
                    break
                if crlf_sep != -1 and (sep == -1 or crlf_sep < sep):
                    idx = crlf_sep
                    delimiter_len = 4
                else:
                    idx = sep
                    delimiter_len = 2
                frame = buffer[:idx]
                buffer = buffer[idx + delimiter_len :]
                rewritten = _rewrite_event_frame(frame)
                if rewritten:
                    handler.wfile.write(rewritten)
                    handler.wfile.flush()
        tail = buffer.strip()
        if tail:
            rewritten = _rewrite_event_frame(tail)
            if rewritten:
                handler.wfile.write(rewritten)
                handler.wfile.flush()
        if not saw_complete or not complete_text:
            config_key = _srv()._read_config_model_api_key(prof)
            _, model_name = _srv()._read_model_from_config(prof)
            if config_key.startswith(turn_credentials.LEASE_PREFIX) and not turn_credentials.validate_lease(
                config_key,
            ):
                entry = llm_error_glossary.playbook_entry("invalid_lease")
            else:
                entry = llm_error_glossary.playbook_entry("provider_empty_reply")
            _log_llm_failure(
                handler,
                str(entry.get("code") or "provider_empty_reply"),
                provider=llm_provider,
                model=str(model_name or ""),
                profile=prof,
            )
            err_payload = json.dumps(llm_error_glossary.notice_payload(entry))
            handler.wfile.write(f"event: error\ndata: {err_payload}\n\n".encode("utf-8"))
            handler.wfile.flush()
        handler.wfile.write(b"event: done\ndata: {}\n\n")
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return
    finally:
        try:
            upstream.close()
        except Exception:  # noqa: BLE001
            pass
        if _triggering_user:
            try:
                _srv()._revoke_turn_credential_lease(_turn_run_id, prof)
            except Exception:  # noqa: BLE001
                pass
            if _auth_decision and _auth_decision.allowed:
                try:
                    conn = _srv()._workframe_db()
                    try:
                        existing = run_ledger.get_run(conn, _turn_run_id)
                        if existing and existing.status == RunStatus.RUNNING:
                            if saw_complete and complete_text:
                                run_ledger.complete_run(
                                    conn,
                                    _turn_run_id,
                                    model=model_used,
                                    provider=llm_provider,
                                    funding_source=_auth_decision.funding_source,
                                    payer_user_id=_auth_decision.payer_user_id,
                                    receipt={
                                        "session_id": session_id,
                                        "room_id": _room_id,
                                        "credential_scope": _auth_decision.credential_scope,
                                    },
                                )
                            else:
                                run_ledger.fail_run(
                                    conn, _turn_run_id, reason="stream_incomplete",
                                )
                            conn.commit()
                    finally:
                        conn.close()
                except Exception:  # noqa: BLE001
                    pass

    room_id = str(payload.get("room_id") or "").strip()
    if room_id:
        try:
            conn = _srv()._workframe_db()
            try:
                row = conn.execute(
                    """
                    SELECT id FROM room_sessions
                    WHERE room_id = ? AND session_id = ? AND deleted_at IS NULL
                    LIMIT 1
                    """,
                    (room_id, session_id),
                ).fetchone()
                if row:
                    now = str(int(time.time()))
                    conn.execute(
                        "UPDATE room_sessions SET updated_at = ? WHERE id = ?",
                        (now, row["id"]),
                    )
                    conn.commit()
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            lane_bindings._sync_lane_binding(
                prof,
                str(payload.get("source_id") or "ui").strip() or "ui",
                str(payload.get("client_id") or "default").strip() or "default",
                lane_bindings._binding_version(payload.get("binding_version")),
                session_id,
                f"api:{prof}:{session_id}",
                str(payload.get("text") or ""),
            )
        except Exception:  # noqa: BLE001
            pass
        return
    # ponytail: legacy global rebind when room_id omitted
    try:
        latest = _srv()._latest_api_session_id(prof)
        if latest and latest != session_id:
            source_id = str(payload.get("source_id") or "ui").strip() or "ui"
            client_id = str(payload.get("client_id") or "default").strip() or "default"
            binding_version = lane_bindings._binding_version(payload.get("binding_version"))
            lane_bindings.chat_dispatch({
                "profile": prof,
                "session_id": latest,
                "gateway_session_id": f"api:{prof}:{latest}",
                "source_id": source_id,
                "client_id": client_id,
                "binding_version": binding_version,
                "text": "",
            })
    except Exception:  # noqa: BLE001
        pass
