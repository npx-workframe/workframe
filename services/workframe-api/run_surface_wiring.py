"""WF-NS-P2: run ledger wiring for slash, cron, and webhook surfaces."""

from __future__ import annotations

import uuid
from typing import Any, Mapping

import run_authority
import run_ledger
from domain.entities import ActorType, FundingSource, RunStatus, RunSurface

# ponytail: slash commands that never bill LLM — audit run only, no authority gate
SLASH_NO_AUTHORITY = frozenset(
    {
        "help",
        "status",
        "cron",
        "skills",
        "skill",
        "memory",
        "sessions",
        "profile",
        "auth",
        "config",
        "kanban",
        "board",
        "version",
        "whoami",
        "stop",
        "steer",
    }
)


def _srv():
    import server as srv

    return srv


def authority_context_for_user(
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
        oauth_connected = _srv()._hermes_oauth_tokens_present(
            user, _srv()._hermes_auth_id_for_spec(oauth_spec),
        )
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


def _resolve_workspace_id(user_id: str, workspace_id: str) -> str:
    ws = str(workspace_id or "").strip()
    if ws:
        return ws
    user = str(user_id or "").strip()
    if not user:
        return "default"
    try:
        conn = _srv()._workframe_db()
        row = conn.execute(
            "SELECT current_workspace_id FROM users WHERE id = ? AND deleted_at IS NULL",
            (user,),
        ).fetchone()
        conn.close()
        if row and row["current_workspace_id"]:
            return str(row["current_workspace_id"])
    except Exception:  # noqa: BLE001
        pass
    return "default"


def slash_requires_authority(cmd_token: str) -> bool:
    return str(cmd_token or "").strip().lower() not in SLASH_NO_AUTHORITY


def record_gated_surface_run(
    *,
    surface: RunSurface,
    build_request: Any,
    triggering_user_id: str,
    profile_slug: str,
    workspace_id: str,
    provider: str,
    room_id: str | None = None,
    session_id: str | None = None,
    run_id: str | None = None,
) -> tuple[str, run_authority.RunAuthorityDecision]:
    """Run authority gate + ledger row for user-triggered surfaces (slash with LLM)."""
    rid = str(run_id or uuid.uuid4())
    ws = _resolve_workspace_id(triggering_user_id, workspace_id)
    run_ledger.ensure_schema()
    auth_req = build_request(
        triggering_user_id=triggering_user_id,
        profile_slug=profile_slug,
        workspace_id=ws,
        provider=provider,
        room_id=room_id,
    )
    auth_ctx = authority_context_for_user(triggering_user_id, ws, provider)
    decision = run_authority.evaluate_run_authority(auth_req, auth_ctx, run_id=rid)
    conn = _srv()._workframe_db()
    try:
        run_ledger.record_authority_decision(
            conn,
            run_id=rid,
            request_surface=surface,
            actor_type=auth_req.actor_type,
            actor_id=auth_req.actor_id,
            triggering_user_id=triggering_user_id,
            workspace_id=ws,
            agent_id=auth_req.agent_id,
            runtime_binding_id=auth_req.runtime_binding_id,
            profile_slug=profile_slug,
            provider=provider,
            room_id=room_id,
            session_id=session_id,
            decision=decision,
        )
        conn.commit()
    finally:
        conn.close()
    return rid, decision


def record_audit_surface_run(
    *,
    surface: RunSurface,
    actor_type: ActorType,
    actor_id: str,
    triggering_user_id: str,
    profile_slug: str,
    workspace_id: str,
    event_type: str,
    payload: Mapping[str, Any] | None = None,
    room_id: str | None = None,
    provider: str = "",
    payer_user_id: str = "",
    funding_source: FundingSource = FundingSource.BYOK,
) -> str:
    """Audit-only run row (no LLM authority gate) — slash meta commands, kanban-style."""
    rid = str(uuid.uuid4())
    ws = _resolve_workspace_id(triggering_user_id, workspace_id)
    payer = str(payer_user_id or triggering_user_id or actor_id).strip()
    run_ledger.ensure_schema()
    conn = _srv()._workframe_db()
    try:
        run_ledger.insert_run(
            conn,
            run_id=rid,
            workspace_id=ws,
            surface=surface,
            actor_type=actor_type,
            actor_id=actor_id,
            triggering_user_id=triggering_user_id or payer,
            agent_id=profile_slug,
            runtime_binding_id=profile_slug,
            status=RunStatus.RUNNING,
            payer_user_id=payer,
            funding_source=funding_source,
            room_id=room_id,
            profile_slug=profile_slug,
            provider=provider or None,
        )
        run_ledger.insert_run_event(
            conn,
            run_id=rid,
            event_type=event_type,
            payload=dict(payload or {}),
            room_id=room_id,
        )
        conn.commit()
    finally:
        conn.close()
    return rid


def record_automated_surface_run(body: dict[str, Any]) -> dict[str, Any]:
    """Internal hook for Hermes cron/webhook — POST /internal/runs/record."""
    surface_raw = str(body.get("surface") or "").strip().lower()
    if surface_raw == "cron":
        surface = RunSurface.CRON
        default_actor = ActorType.SYSTEM
    elif surface_raw == "webhook":
        surface = RunSurface.WEBHOOK
        default_actor = ActorType.WEBHOOK
    else:
        raise ValueError("surface must be cron or webhook")

    actor_type_raw = str(body.get("actor_type") or default_actor.value).strip().lower()
    try:
        actor_type = ActorType(actor_type_raw)
    except ValueError as exc:
        raise ValueError("invalid actor_type") from exc

    profile_slug = _srv().safe_profile_slug(str(body.get("profile_slug") or "").strip())
    if not profile_slug:
        raise ValueError("profile_slug required")

    triggering_user_id = str(body.get("triggering_user_id") or "").strip()
    if not triggering_user_id:
        triggering_user_id = _srv()._runtime_profile_owner(profile_slug, str(body.get("workspace_id") or ""))

    workspace_id = _resolve_workspace_id(triggering_user_id, str(body.get("workspace_id") or ""))
    actor_id = str(body.get("actor_id") or f"{surface_raw}:unknown").strip()
    event_type = str(body.get("event_type") or f"{surface_raw}.triggered").strip()
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    room_id = str(body.get("room_id") or "").strip() or None
    provider = str(body.get("provider") or "").strip()
    if not provider:
        block = _srv()._read_model_block(profile_slug)
        provider = _srv()._llm_billing_provider(
            profile_slug,
            user_id=triggering_user_id,
            workspace_id=workspace_id,
            block=block,
        )

    run_id = record_audit_surface_run(
        surface=surface,
        actor_type=actor_type,
        actor_id=actor_id,
        triggering_user_id=triggering_user_id,
        profile_slug=profile_slug,
        workspace_id=workspace_id,
        event_type=event_type,
        payload={**payload, "provider": provider, "actor_id": actor_id},
        room_id=room_id,
        provider=provider,
    )
    finish_surface_run(run_id, ok=True)
    return {"ok": True, "run_id": run_id, "surface": surface.value}


def finish_surface_run(run_id: str, *, ok: bool, detail: str = "") -> None:
    rid = str(run_id or "").strip()
    if not rid:
        return
    run_ledger.ensure_schema()
    conn = _srv()._workframe_db()
    try:
        row = conn.execute(
            "SELECT payer_user_id, funding_source, provider, profile_slug FROM runs WHERE run_id = ?",
            (rid,),
        ).fetchone()
        if not row:
            return
        if ok:
            run_ledger.complete_run(
                conn,
                rid,
                model="",
                provider=str(row["provider"] or ""),
                funding_source=FundingSource(str(row["funding_source"] or FundingSource.BYOK.value)),
                payer_user_id=str(row["payer_user_id"] or ""),
                receipt={"detail": detail[:500]} if detail else {},
            )
        else:
            run_ledger.fail_run(conn, rid, reason=detail[:500] if detail else "failed")
        conn.commit()
    finally:
        conn.close()


def begin_slash_run(
    *,
    cmd_token: str,
    line: str,
    profile_slug: str,
    user_id: str,
    workspace_id: str,
) -> tuple[str | None, run_authority.RunAuthorityDecision | None]:
    """Create slash run ledger row; return (run_id, decision) or (None, None) when anonymous."""
    user = str(user_id or "").strip()
    if not user:
        return None, None

    prof = _srv().safe_profile_slug(profile_slug)
    ws = _resolve_workspace_id(user, workspace_id)
    block = _srv()._read_model_block(prof)
    provider = _srv()._llm_billing_provider(prof, user_id=user, workspace_id=ws, block=block)
    payload = {"command": cmd_token, "line": line[:200]}

    if not slash_requires_authority(cmd_token):
        rid = record_audit_surface_run(
            surface=RunSurface.SLASH,
            actor_type=ActorType.USER,
            actor_id=user,
            triggering_user_id=user,
            profile_slug=prof,
            workspace_id=ws,
            event_type="slash.command",
            payload=payload,
            provider=provider,
        )
        return rid, None

    rid, decision = record_gated_surface_run(
        surface=RunSurface.SLASH,
        build_request=run_authority.slash_run_request,
        triggering_user_id=user,
        profile_slug=prof,
        workspace_id=ws,
        provider=provider,
    )
    run_ledger.ensure_schema()
    conn = _srv()._workframe_db()
    try:
        run_ledger.insert_run_event(
            conn,
            run_id=rid,
            event_type="slash.command",
            payload=payload,
        )
        conn.commit()
    finally:
        conn.close()
    return rid, decision
