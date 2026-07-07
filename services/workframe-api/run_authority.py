"""RunAuthorityGate — single pre-run authority decision (WF-009)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping

from domain.entities import (
    ActorType,
    FundingSource,
    Grant,
    GrantCapability,
    RunSurface,
)

DENY_NO_ACTOR = "no_actor"
DENY_NO_CREDENTIAL_BYOK = "no_credential_byok"
DENY_NO_CREDENTIAL_COMPANY = "no_credential_company"
DENY_PROVIDER_USER_ONLY = "provider_user_only_no_fallback"
DENY_DELEGATION = "delegation_no_grantor_credential"


@dataclass(frozen=True)
class RunAuthorityRequest:
    surface: RunSurface
    actor_type: ActorType
    actor_id: str
    triggering_user_id: str
    profile_slug: str
    workspace_id: str
    provider: str
    room_id: str | None = None
    agent_id: str = ""
    runtime_binding_id: str = ""


@dataclass(frozen=True)
class RunAuthorityContext:
    workspace_credential_mode: str = "byok"
    provider_user_only: bool = False
    user_has_credential: bool = False
    workspace_has_credential: bool = False
    grantor_has_credential: Mapping[str, bool] = field(default_factory=dict)
    oauth_connected: bool = False


@dataclass(frozen=True)
class RunAuthorityDecision:
    allowed: bool
    deny_reason: str | None
    payer_user_id: str
    funding_source: FundingSource
    credential_ref_id: str | None
    credential_scope: str | None
    grants: tuple[Grant, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "deny_reason": self.deny_reason,
            "payer_user_id": self.payer_user_id,
            "funding_source": self.funding_source.value,
            "credential_ref_id": self.credential_ref_id,
            "credential_scope": self.credential_scope,
            "grants": [g.to_dict() for g in self.grants],
        }


def _credential_available(ctx: RunAuthorityContext) -> bool:
    return bool(ctx.user_has_credential or ctx.oauth_connected)


def _grant_llm_turn(run_id: str) -> Grant:
    return Grant(
        grant_id=str(uuid.uuid4()),
        run_id=run_id,
        capability=GrantCapability.LLM_TURN,
        scope={"provider": "pending"},
        granted_by="run_authority_gate",
    )


def evaluate_run_authority(
    request: RunAuthorityRequest,
    ctx: RunAuthorityContext,
    *,
    run_id: str | None = None,
) -> RunAuthorityDecision:
    """Pure gate — no I/O. Caller supplies credential probes."""
    rid = str(run_id or uuid.uuid4())
    actor = str(request.triggering_user_id or "").strip()
    if not actor:
        return RunAuthorityDecision(
            allowed=False,
            deny_reason=DENY_NO_ACTOR,
            payer_user_id="",
            funding_source=FundingSource.BYOK,
            credential_ref_id=None,
            credential_scope=None,
            grants=(),
        )

    mode = str(ctx.workspace_credential_mode or "byok").strip().lower()
    provider = str(request.provider or "openrouter").strip().lower()

    if ctx.provider_user_only:
        if _credential_available(ctx):
            return RunAuthorityDecision(
                allowed=True,
                deny_reason=None,
                payer_user_id=actor,
                funding_source=FundingSource.BYOK,
                credential_ref_id=None,
                credential_scope="user",
                grants=(_grant_llm_turn(rid),),
            )
        return RunAuthorityDecision(
            allowed=False,
            deny_reason=DENY_PROVIDER_USER_ONLY,
            payer_user_id=actor,
            funding_source=FundingSource.BYOK,
            credential_ref_id=None,
            credential_scope=None,
            grants=(),
        )

    if _credential_available(ctx):
        return RunAuthorityDecision(
            allowed=True,
            deny_reason=None,
            payer_user_id=actor,
            funding_source=FundingSource.BYOK,
            credential_ref_id=None,
            credential_scope="user",
            grants=(_grant_llm_turn(rid),),
        )

    if mode == "workspace" and ctx.workspace_has_credential:
        return RunAuthorityDecision(
            allowed=True,
            deny_reason=None,
            payer_user_id=actor,
            funding_source=FundingSource.COMPANY,
            credential_ref_id=None,
            credential_scope="workspace",
            grants=(_grant_llm_turn(rid),),
        )

    for grantor_id, has_cred in ctx.grantor_has_credential.items():
        gid = str(grantor_id or "").strip()
        if gid and has_cred:
            return RunAuthorityDecision(
                allowed=True,
                deny_reason=None,
                payer_user_id=gid,
                funding_source=FundingSource.BYOK,
                credential_ref_id=None,
                credential_scope="user",
                grants=(_grant_llm_turn(rid),),
            )

    if mode == "workspace":
        deny = DENY_NO_CREDENTIAL_COMPANY
    else:
        deny = DENY_NO_CREDENTIAL_BYOK
    return RunAuthorityDecision(
        allowed=False,
        deny_reason=deny,
        payer_user_id=actor,
        funding_source=FundingSource.BYOK,
        credential_ref_id=None,
        credential_scope=None,
        grants=(),
    )


def chat_run_request(
    *,
    triggering_user_id: str,
    profile_slug: str,
    workspace_id: str,
    provider: str,
    room_id: str | None = None,
) -> RunAuthorityRequest:
    return RunAuthorityRequest(
        surface=RunSurface.CHAT,
        actor_type=ActorType.USER,
        actor_id=triggering_user_id,
        triggering_user_id=triggering_user_id,
        profile_slug=profile_slug,
        workspace_id=workspace_id,
        provider=provider,
        room_id=room_id,
        agent_id=profile_slug,
        runtime_binding_id=profile_slug,
    )


def mention_run_request(
    *,
    triggering_user_id: str,
    profile_slug: str,
    workspace_id: str,
    provider: str,
    room_id: str | None = None,
) -> RunAuthorityRequest:
    return RunAuthorityRequest(
        surface=RunSurface.MENTION,
        actor_type=ActorType.USER,
        actor_id=triggering_user_id,
        triggering_user_id=triggering_user_id,
        profile_slug=profile_slug,
        workspace_id=workspace_id,
        provider=provider,
        room_id=room_id,
        agent_id=profile_slug,
        runtime_binding_id=profile_slug,
    )


def slash_run_request(
    *,
    triggering_user_id: str,
    profile_slug: str,
    workspace_id: str,
    provider: str,
    room_id: str | None = None,
) -> RunAuthorityRequest:
    return RunAuthorityRequest(
        surface=RunSurface.SLASH,
        actor_type=ActorType.USER,
        actor_id=triggering_user_id,
        triggering_user_id=triggering_user_id,
        profile_slug=profile_slug,
        workspace_id=workspace_id,
        provider=provider,
        room_id=room_id,
        agent_id=profile_slug,
        runtime_binding_id=profile_slug,
    )


def cron_run_request(
    *,
    triggering_user_id: str,
    profile_slug: str,
    workspace_id: str,
    provider: str,
    actor_id: str = "cron",
    room_id: str | None = None,
) -> RunAuthorityRequest:
    return RunAuthorityRequest(
        surface=RunSurface.CRON,
        actor_type=ActorType.SYSTEM,
        actor_id=actor_id,
        triggering_user_id=triggering_user_id,
        profile_slug=profile_slug,
        workspace_id=workspace_id,
        provider=provider,
        room_id=room_id,
        agent_id=profile_slug,
        runtime_binding_id=profile_slug,
    )


def webhook_run_request(
    *,
    triggering_user_id: str,
    profile_slug: str,
    workspace_id: str,
    provider: str,
    actor_id: str,
    room_id: str | None = None,
) -> RunAuthorityRequest:
    return RunAuthorityRequest(
        surface=RunSurface.WEBHOOK,
        actor_type=ActorType.WEBHOOK,
        actor_id=actor_id,
        triggering_user_id=triggering_user_id,
        profile_slug=profile_slug,
        workspace_id=workspace_id,
        provider=provider,
        room_id=room_id,
        agent_id=profile_slug,
        runtime_binding_id=profile_slug,
    )
