"""WF-039 domain entity self-check — fails if round-trip or imports break."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from domain.entities import (  # noqa: E402
    ActorType,
    AgentIdentity,
    Cell,
    CredentialPolicy,
    CredentialRef,
    DeploymentMode,
    FundingSource,
    Grant,
    GrantCapability,
    Lease,
    LeaseStatus,
    Run,
    RunEvent,
    RunStatus,
    RunSurface,
    RuntimeBinding,
    RuntimeBindingStatus,
    RuntimeKind,
    User,
    Workspace,
)


def _ts() -> datetime:
    return datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)


def test_round_trip() -> None:
    cell = Cell(
        cell_id="cell-1",
        install_root="/tmp/wf/MyBusiness",
        manifest_path="/tmp/wf/MyBusiness/workframe-manifest.json",
        package_name="create-workframe",
        package_version="0.1.12",
        deployment_mode=DeploymentMode.SINGLE_USER_LOCAL,
        created_at=_ts(),
    )
    payload = cell.to_dict()
    assert payload["deployment_mode"] == "single_user_local"
    assert payload["cell_id"] == "cell-1"
    json.dumps(payload)

    run = Run(
        run_id="run-1",
        workspace_id="ws-default",
        surface=RunSurface.CHAT,
        actor_type=ActorType.USER,
        actor_id="user-1",
        triggering_user_id="user-1",
        agent_id="agent-native",
        runtime_binding_id="bind-1",
        status=RunStatus.PENDING,
        payer_user_id="user-1",
        funding_source=FundingSource.BYOK,
        created_at=_ts(),
    )
    run_payload = run.to_dict()
    assert run_payload["surface"] == "chat"
    assert run_payload["status"] == "pending"

    lease = Lease(
        lease_id="wf_rt_test",
        run_id="run-1",
        workspace_id="ws-default",
        payer_user_id="user-1",
        provider="openrouter",
        profile_slug="u-user-1-native",
        credential_ref_id="cred-1",
        status=LeaseStatus.ACTIVE,
        expires_at=_ts(),
    )
    assert Lease.from_dict(lease.to_dict()).provider == "openrouter"


def test_schema_file_present() -> None:
    schema = Path(__file__).resolve().parent / "domain" / "schema" / "workframe-domain.schema.json"
    data = json.loads(schema.read_text(encoding="utf-8"))
    defs = data["$defs"]
    for name in (
        "Cell",
        "User",
        "Workspace",
        "AgentIdentity",
        "RuntimeBinding",
        "Run",
        "RunEvent",
        "Lease",
        "Grant",
        "CredentialRef",
    ):
        assert name in defs, f"missing schema def: {name}"


def test_agent_runtime_seam_types() -> None:
    agent = AgentIdentity(
        agent_id="agent-1",
        workspace_id="ws-1",
        template_slug="dev",
        display_name="Dev",
    )
    binding = RuntimeBinding(
        binding_id="bind-1",
        agent_id=agent.agent_id,
        runtime_kind=RuntimeKind.HERMES_MANAGED,
        profile_slug="u-alice-dev",
        status=RuntimeBindingStatus.ACTIVE,
    )
    assert binding.agent_id == agent.agent_id

    grant = Grant(
        grant_id="grant-1",
        run_id="run-1",
        capability=GrantCapability.LLM_TURN,
    )
    assert grant.capability == GrantCapability.LLM_TURN

    user = User(
        user_id="u-1",
        workspace_id="ws-1",
        email="a@example.com",
        display_name="Alice",
    )
    ws = Workspace(workspace_id="ws-1", cell_id="cell-1", slug="default", name="Workframe")
    cred = CredentialRef(
        ref_id="cred-1",
        workspace_id=ws.workspace_id,
        provider="openrouter",
        policy=CredentialPolicy.BYOK,
    )
    assert cred.provider == "openrouter"

    event = RunEvent(event_id="ev-1", run_id="run-1", event_type="run.authorized")
    assert event.event_type == "run.authorized"


if __name__ == "__main__":
    test_round_trip()
    test_schema_file_present()
    test_agent_runtime_seam_types()
    print("test_domain_entities: ok")
