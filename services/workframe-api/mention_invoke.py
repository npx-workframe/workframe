"""WF-032 extract: @mention agent invoke streaming in space rooms."""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.parse
import urllib.request
import uuid
from typing import Any

import chat_stream
import lane_bindings
import profile_gateway
import rooms
import run_authority
import run_ledger
from domain.entities import RunStatus


def _srv():
    import server as srv

    return srv


def _room_recent_transcript(conn: sqlite3.Connection, room_id: str, limit: int = 24) -> str:
    rows = conn.execute(
        """
        SELECT m.content, u.display_name AS user_name, ap.display_name AS agent_name
        FROM messages m
        LEFT JOIN users u ON u.id = m.sender_user_id
        LEFT JOIN agent_profiles ap ON ap.id = m.sender_agent_id
        WHERE m.room_id = ? AND m.deleted_at IS NULL
        ORDER BY m.created_at DESC
        LIMIT ?
        """,
        (room_id, limit),
    ).fetchall()
    lines: list[str] = []
    for row in reversed(rows):
        name = str(row["user_name"] or row["agent_name"] or "Member")
        lines.append(f"{name}: {row['content']}")
    return "\n".join(lines)


def _inject_turn_credentials(
    turn_body: dict[str, Any],
    user_id: str,
    workspace_id: str,
    provider: str = "openrouter",
) -> None:
    resolved = _srv()._resolve_credential(user_id, workspace_id, provider)
    if not resolved:
        return
    turn_body["_credential_override"] = resolved["credential_ref"]
    turn_body["_credential_scope"] = resolved["scope"]



def _invoke_room_agent_mention(
    room_id: str,
    workspace_id: str,
    agent_row: dict[str, Any],
    triggered_by_user_id: str,
    parent_message_id: str,
) -> None:
    """Stream a tagged agent turn in a shared space room; fan out live updates to room subscribers."""
    template_slug = str(agent_row.get("slug") or "").strip()
    agent_db_id = str(agent_row.get("id") or "").strip()
    agent_name = str(agent_row.get("display_name") or template_slug).strip() or template_slug
    if triggered_by_user_id:
        personal = _srv()._runtime_display_label(triggered_by_user_id, template_slug, workspace_id)
        if personal:
            agent_name = personal
    if not template_slug or not agent_db_id:
        return
    hermes_slug = _srv()._runtime_profile_slug(triggered_by_user_id, template_slug)
    _srv().ensure_runtime_profile(hermes_slug, template_slug, triggered_by_user_id, workspace_id)

    turn_id = str(uuid.uuid4())
    segments: list[dict[str, Any]] = []
    last_flush = 0.0
    flush_interval = 0.05
    run_id = str(uuid.uuid4())
    session_id = ""
    user_text = ""
    provider = ""
    auth_decision: run_authority.RunAuthorityDecision | None = None
    run_completed_ok = False

    def publish_update(*, force: bool = False, status: str | None = None) -> None:
        nonlocal last_flush
        now = time.time()
        if not force and (now - last_flush) < flush_interval:
            return
        payload: dict[str, Any] = {
            "type": "turn.update",
            "turn_id": turn_id,
            "room_id": room_id,
            "segments": segments,
        }
        if status:
            payload["status"] = status
        rooms._room_live_publish(room_id, payload)
        rooms._room_live_set_turn(
            {
                "type": "turn.snapshot",
                "turn_id": turn_id,
                "room_id": room_id,
                "agent_slug": hermes_slug,
                "agent_name": agent_name,
                "agent_profile_id": agent_db_id,
                "segments": segments,
                "status": status or "",
            }
        )
        last_flush = now

    def finish_turn(message_id: str = "") -> None:
        rooms._room_live_publish(
            room_id,
            {
                "type": "turn.complete",
                "turn_id": turn_id,
                "room_id": room_id,
                "message_id": message_id,
            },
        )
        rooms._room_live_clear_turn(turn_id)

    def fail_turn(error: str, *, persist: bool = True) -> None:
        segments[:] = chat_stream._live_reduce_stream_event(segments, "error", {"error": error})
        publish_update(force=True, status="error")
        if persist:
            try:
                conn = _srv()._workframe_db()
                try:
                    now_ts = str(int(time.time()))
                    mid = str(uuid.uuid4())
                    conn.execute(
                        """
                        INSERT INTO messages (
                            id, room_id, sender_user_id, sender_agent_id, parent_message_id,
                            content, content_type, is_edited, created_at, updated_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            mid,
                            room_id,
                            None,
                            agent_db_id,
                            parent_message_id,
                            error,
                            "text",
                            0,
                            now_ts,
                            now_ts,
                        ),
                    )
                    conn.execute("UPDATE rooms SET updated_at = ? WHERE id = ?", (now_ts, room_id))
                    conn.commit()
                    _srv()._bump_workspace_event_state()
                    finish_turn(mid)
                    return
                finally:
                    conn.close()
            except Exception:  # noqa: BLE001
                pass
        rooms._room_live_publish(
            room_id,
            {
                "type": "turn.error",
                "turn_id": turn_id,
                "room_id": room_id,
                "error": error,
                "segments": segments,
            },
        )
        finish_turn()

    try:
        conn = _srv()._workframe_db()
        try:
            parent = conn.execute(
                "SELECT content FROM messages WHERE id = ? AND room_id = ? AND deleted_at IS NULL",
                (parent_message_id, room_id),
            ).fetchone()
            user_text = str(parent["content"] or "").strip() if parent else ""
        finally:
            conn.close()

        rooms._room_live_publish(
            room_id,
            {
                "type": "turn.started",
                "turn_id": turn_id,
                "room_id": room_id,
                "agent_slug": hermes_slug,
                "agent_name": agent_name,
                "agent_profile_id": agent_db_id,
                "triggered_by_user_id": triggered_by_user_id,
            },
        )
        rooms._room_live_set_turn(
            {
                "type": "turn.snapshot",
                "turn_id": turn_id,
                "room_id": room_id,
                "agent_slug": hermes_slug,
                "agent_name": agent_name,
                "agent_profile_id": agent_db_id,
                "segments": segments,
                "status": "starting",
            }
        )

        session = lane_bindings.profile_chat_session(
            hermes_slug,
            {
                "room_id": room_id,
                "source_id": "room",
                "client_id": room_id,
            },
            triggered_by_user_id,
        )
        session_id = str(session.get("session_id") or "").strip()
        if not session_id:
            raise ValueError("session_bootstrap_failed: could not start agent session for this room")

        turn_body = profile_gateway._profile_turn_payload(hermes_slug, user_text, room_id)
        provider = str(agent_row.get("model_provider") or "").strip()
        if not provider:
            provider = _srv()._llm_billing_provider(
                hermes_slug,
                user_id=triggered_by_user_id,
                workspace_id=workspace_id,
            )
        if triggered_by_user_id:
            run_ledger.ensure_schema()
            auth_req = run_authority.mention_run_request(
                triggering_user_id=triggered_by_user_id,
                profile_slug=hermes_slug,
                workspace_id=workspace_id,
                provider=provider,
                room_id=room_id,
            )
            auth_ctx = chat_stream._run_authority_context_for_chat(
                triggered_by_user_id, workspace_id, provider,
            )
            auth_decision = run_authority.evaluate_run_authority(
                auth_req, auth_ctx, run_id=run_id,
            )
            conn = _srv()._workframe_db()
            try:
                run_ledger.record_authority_decision(
                    conn,
                    run_id=run_id,
                    request_surface=auth_req.surface,
                    actor_type=auth_req.actor_type,
                    actor_id=auth_req.actor_id,
                    triggering_user_id=triggered_by_user_id,
                    workspace_id=workspace_id or "default",
                    agent_id=auth_req.agent_id,
                    runtime_binding_id=auth_req.runtime_binding_id,
                    profile_slug=hermes_slug,
                    provider=provider,
                    room_id=room_id,
                    session_id=session_id,
                    decision=auth_decision,
                )
                conn.commit()
            finally:
                conn.close()
            if not auth_decision.allowed:
                fail_turn(
                    "I can't reply yet — connect an LLM provider in Profile → Connect accounts.",
                    persist=False,
                )
                return

        _srv().ensure_profile_api(
            hermes_slug,
            triggered_by_user_id,
            workspace_id,
            bootstrap_providers=False,
        )
        _srv()._overlay_turn_provider_env(hermes_slug, triggered_by_user_id, workspace_id, provider, run_id)
        _srv()._overlay_turn_user_env(hermes_slug, triggered_by_user_id, workspace_id, run_id)
        _inject_turn_credentials(turn_body, triggered_by_user_id, workspace_id, provider)
        _srv()._ensure_profile_proxy_headers(hermes_slug)

        upstream_body = json.dumps(turn_body).encode("utf-8")
        port = _srv()._profile_api_port(hermes_slug)
        url = f"http://gateway:{port}/api/sessions/{urllib.parse.quote(session_id, safe='')}/chat/stream"
        headers = {
            "Authorization": f"Bearer {_srv()._profile_api_key(hermes_slug)}",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, data=upstream_body, headers=headers, method="POST")
        upstream = urllib.request.urlopen(req, timeout=3600)

        final_text = ""
        try:
            publish_update(force=True, status="thinking")
            for event_name, data in chat_stream._iter_profile_stream_frames(upstream):
                segments[:] = chat_stream._live_reduce_stream_event(segments, event_name, data)
                if event_name in ("message.delta", "assistant.delta"):
                    final_text += chat_stream._live_stream_text(data)
                    publish_update(status="writing")
                elif event_name in ("thinking.delta", "reasoning.delta"):
                    publish_update(status="thinking")
                elif event_name == "tool.started":
                    publish_update(force=True, status=f"tool:{data.get('tool_name') or 'tool'}")
                elif event_name in ("tool.completed", "tool.failed", "tool.progress"):
                    publish_update(force=True)
                elif event_name in ("message.complete", "assistant.completed"):
                    final_text = str(data.get("content") or data.get("text") or final_text)
                    publish_update(force=True, status="writing")
            publish_update(force=True)
        finally:
            upstream.close()

        assistant = final_text.strip() or chat_stream._segments_to_reply_text(segments)
        if not assistant:
            raise ValueError("empty assistant response")

        conn = _srv()._workframe_db()
        try:
            now_ts = str(int(time.time()))
            mid = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO messages (
                    id, room_id, sender_user_id, sender_agent_id, parent_message_id,
                    content, content_type, is_edited, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    mid,
                    room_id,
                    None,
                    agent_db_id,
                    parent_message_id,
                    assistant,
                    "text",
                    0,
                    now_ts,
                    now_ts,
                ),
            )
            conn.execute("UPDATE rooms SET updated_at = ? WHERE id = ?", (now_ts, room_id))
            conn.commit()
        finally:
            conn.close()
        _srv()._bump_workspace_event_state()
        run_completed_ok = True
        finish_turn(mid)
        _srv()._log_agent_run(
            run_id,
            agent_db_id,
            room_id,
            triggered_by_user_id,
            session_id,
            "completed",
            provider,
            str(agent_row.get("model_name") or "default"),
            error=None,
        )
        lane_bindings.chat_dispatch(
            {
                "profile": hermes_slug,
                "session_id": session_id,
                "gateway_session_id": f"api:{hermes_slug}:{session_id}",
                "room_id": room_id,
                "user_id": triggered_by_user_id,
                "source_id": "room",
                "client_id": room_id,
                "text": user_text[:240],
            }
        )
    except Exception as exc:  # noqa: BLE001
        err_text = str(exc)
        if "no_llm_provider_for_user" in err_text:
            reply = (
                "I can't reply yet â€” the member who @mentioned me needs to connect an LLM provider "
                "(Profile â†’ Connect accounts â†’ OpenRouter or another model provider)."
            )
        else:
            reply = err_text
        try:
            _srv()._log_agent_run(
                run_id,
                agent_db_id,
                room_id,
                triggered_by_user_id,
                session_id,
                "failed",
                str(agent_row.get("model_provider") or "openrouter"),
                str(agent_row.get("model_name") or "default"),
                error=err_text,
            )
        except Exception:  # noqa: BLE001
            pass
        fail_turn(reply)
    finally:
        _srv()._revoke_turn_credential_lease(run_id, hermes_slug)
        if triggered_by_user_id and auth_decision and auth_decision.allowed:
            try:
                conn = _srv()._workframe_db()
                try:
                    existing = run_ledger.get_run(conn, run_id)
                    if existing and existing.status == RunStatus.RUNNING:
                        if run_completed_ok:
                            run_ledger.complete_run(
                                conn,
                                run_id,
                                model=str(agent_row.get("model_name") or ""),
                                provider=provider,
                                funding_source=auth_decision.funding_source,
                                payer_user_id=auth_decision.payer_user_id or triggered_by_user_id,
                                receipt={"room_id": room_id, "session_id": session_id},
                            )
                        else:
                            run_ledger.fail_run(conn, run_id, reason="mention_failed")
                        conn.commit()
                finally:
                    conn.close()
            except Exception:  # noqa: BLE001
                pass
