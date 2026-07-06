"""WF-009 RunAuthorityGate self-check."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from domain.entities import ActorType, FundingSource, RunSurface  # noqa: E402
from run_authority import (  # noqa: E402
    DENY_DELEGATION,
    DENY_NO_CREDENTIAL_BYOK,
    DENY_NO_CREDENTIAL_COMPANY,
    DENY_PROVIDER_USER_ONLY,
    RunAuthorityContext,
    RunAuthorityRequest,
    evaluate_run_authority,
)


def _req() -> RunAuthorityRequest:
    return RunAuthorityRequest(
        surface=RunSurface.CHAT,
        actor_type=ActorType.USER,
        actor_id="user-1",
        triggering_user_id="user-1",
        profile_slug="u-user-1-native",
        workspace_id="ws-1",
        provider="openrouter",
    )


def test_byok_user_cred() -> None:
    decision = evaluate_run_authority(
        _req(),
        RunAuthorityContext(user_has_credential=True),
        run_id="run-1",
    )
    assert decision.allowed
    assert decision.payer_user_id == "user-1"
    assert decision.funding_source == FundingSource.BYOK


def test_byok_no_cred_denied() -> None:
    decision = evaluate_run_authority(_req(), RunAuthorityContext())
    assert not decision.allowed
    assert decision.deny_reason == DENY_NO_CREDENTIAL_BYOK


def test_company_workspace_cred() -> None:
    decision = evaluate_run_authority(
        _req(),
        RunAuthorityContext(workspace_credential_mode="workspace", workspace_has_credential=True),
    )
    assert decision.allowed
    assert decision.funding_source == FundingSource.COMPANY
    assert decision.credential_scope == "workspace"


def test_company_user_cred_wins() -> None:
    decision = evaluate_run_authority(
        _req(),
        RunAuthorityContext(
            workspace_credential_mode="workspace",
            user_has_credential=True,
            workspace_has_credential=True,
        ),
    )
    assert decision.allowed
    assert decision.funding_source == FundingSource.BYOK


def test_user_only_no_fallback() -> None:
    decision = evaluate_run_authority(
        _req(),
        RunAuthorityContext(provider_user_only=True, workspace_has_credential=True),
    )
    assert not decision.allowed
    assert decision.deny_reason == DENY_PROVIDER_USER_ONLY


def test_delegation_grantor() -> None:
    decision = evaluate_run_authority(
        _req(),
        RunAuthorityContext(grantor_has_credential={"owner-1": True}),
    )
    assert decision.allowed
    assert decision.payer_user_id == "owner-1"


def test_delegation_no_grantor_cred() -> None:
    decision = evaluate_run_authority(
        _req(),
        RunAuthorityContext(
            workspace_credential_mode="workspace",
            grantor_has_credential={"owner-1": False},
        ),
    )
    assert not decision.allowed
    assert decision.deny_reason == DENY_NO_CREDENTIAL_COMPANY


if __name__ == "__main__":
    test_byok_user_cred()
    test_byok_no_cred_denied()
    test_company_workspace_cred()
    test_company_user_cred_wins()
    test_user_only_no_fallback()
    test_delegation_grantor()
    test_delegation_no_grantor_cred()
    print("test_run_authority: ok")
