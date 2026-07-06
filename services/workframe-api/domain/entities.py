"""Workframe domain entities — stable vocabulary for authority, runs, and credentials.

Referenced by WF-009 RunAuthorityGate, WF-NS-P2 runs tables, and public glossary (WF-NS-P0).
Implementation in server.py still uses legacy shapes; migrate incrementally (WF-032).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Mapping, TypeVar

T = TypeVar("T", bound="DomainEntity")


class DomainEntity:
    """Minimal JSON round-trip for dataclass entities."""

    def to_dict(self) -> dict[str, Any]:
        return _encode_value(asdict(self))

    @classmethod
    def from_dict(cls: type[T], data: Mapping[str, Any]) -> T:
        return cls(**dict(data))


def _encode_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _encode_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_encode_value(v) for v in value]
    return value


class DeploymentMode(str, Enum):
    SINGLE_USER_LOCAL = "single_user_local"
    TRUSTED_TEAM = "trusted_team"
    PUBLIC_MULTI_USER = "public_multi_user"


class ActorType(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    WEBHOOK = "webhook"


class RunStatus(str, Enum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DENIED = "denied"


class RunSurface(str, Enum):
    AGENT_RAIL = "agent_rail"
    CHAT = "chat"
    FILES = "files"
    BROWSER = "browser"
    ACTIVITY = "activity"
    KANBAN = "kanban"
    CRON = "cron"
    SLASH = "slash"
    WEBHOOK = "webhook"
    MENTION = "mention"


class RuntimeKind(str, Enum):
    HERMES_MANAGED = "hermes_managed"
    CANDIDATE = "candidate"
    ADAPTER = "adapter"


class RuntimeBindingStatus(str, Enum):
    ACTIVE = "active"
    DETACHED = "detached"
    CANDIDATE = "candidate"


class FundingSource(str, Enum):
    BYOK = "byok"
    COMPANY = "company"
    HYBRID = "hybrid"


class CredentialPolicy(str, Enum):
    BYOK = "byok"
    COMPANY = "company"
    USER_ONLY = "user_only"


class LeaseStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class GrantCapability(str, Enum):
    LLM_TURN = "llm_turn"
    TOOL_CALL = "tool_call"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    RUNTIME_EXEC = "runtime_exec"
    BROKER_EGRESS = "broker_egress"


@dataclass(frozen=True)
class Cell(DomainEntity):
    """One Workframe install/deployment unit (generated project root)."""

    cell_id: str
    install_root: str
    manifest_path: str
    package_name: str
    package_version: str
    deployment_mode: DeploymentMode
    created_at: datetime
    git_ref: str | None = None
    packed_artifact_digest: str | None = None


@dataclass(frozen=True)
class User(DomainEntity):
    user_id: str
    workspace_id: str
    email: str
    display_name: str
    role: Literal["owner", "admin", "member", "guest"] = "member"
    created_at: datetime | None = None


@dataclass(frozen=True)
class Workspace(DomainEntity):
    workspace_id: str
    cell_id: str
    slug: str
    name: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class AgentIdentity(DomainEntity):
    """Persistent Workframe agent — distinct from Hermes profile (WF-013 seam)."""

    agent_id: str
    workspace_id: str
    template_slug: str
    display_name: str
    is_native: bool = False
    created_at: datetime | None = None


@dataclass(frozen=True)
class RuntimeBinding(DomainEntity):
    """Links AgentIdentity to a concrete runtime (Hermes profile today)."""

    binding_id: str
    agent_id: str
    runtime_kind: RuntimeKind
    profile_slug: str
    status: RuntimeBindingStatus = RuntimeBindingStatus.ACTIVE
    detected_at: datetime | None = None


@dataclass(frozen=True)
class Run(DomainEntity):
    """Unit of authority, execution, and economics (WF-009, WF-NS-P2)."""

    run_id: str
    workspace_id: str
    surface: RunSurface
    actor_type: ActorType
    actor_id: str
    triggering_user_id: str
    agent_id: str
    runtime_binding_id: str
    status: RunStatus
    payer_user_id: str
    funding_source: FundingSource
    room_id: str | None = None
    card_id: str | None = None
    engine: str = "hermes"
    runtime: str = "hermes_managed"
    risk_tier: Literal["low", "medium", "high"] = "low"
    budget_usd: float | None = None
    deny_reason: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None


@dataclass(frozen=True)
class RunEvent(DomainEntity):
    event_id: str
    run_id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass(frozen=True)
class CredentialRef(DomainEntity):
    """Vault pointer — never holds raw secret material."""

    ref_id: str
    workspace_id: str
    provider: str
    policy: CredentialPolicy
    user_id: str | None = None
    binding_id: str | None = None
    label_redacted: str | None = None


@dataclass(frozen=True)
class Lease(DomainEntity):
    """Scoped credential lease for one run (maps to turn_credential_leases / wf_rt_*)."""

    lease_id: str
    run_id: str
    workspace_id: str
    payer_user_id: str
    provider: str
    profile_slug: str
    credential_ref_id: str | None
    status: LeaseStatus
    expires_at: datetime
    revoked_at: datetime | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class Grant(DomainEntity):
    """Capability granted to a run before execution (RunAuthorityGate output)."""

    grant_id: str
    run_id: str
    capability: GrantCapability
    scope: dict[str, Any] = field(default_factory=dict)
    granted_by: Literal["run_authority_gate", "cell_authority_gate", "policy"] = (
        "run_authority_gate"
    )
    expires_at: datetime | None = None
    created_at: datetime | None = None
