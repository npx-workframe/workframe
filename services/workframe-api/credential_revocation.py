"""WF-048 authority-changing revocation hooks."""

from __future__ import annotations

import sqlite3
from typing import Any

import credential_lifecycle
import turn_credentials

PRIVILEGED_MEMBER_ROLES = frozenset({"owner", "admin"})


def _srv():
    import server as srv

    return srv


def _active_binding_ids(*, clauses: list[str], params: list[Any]) -> list[str]:
    conn = sqlite3.connect(str(_srv()._workframe_db_path()), timeout=5.0)
    try:
        rows = conn.execute(
            f"""SELECT id FROM credential_bindings
                WHERE deleted_at IS NULL AND is_active = 1
                  AND {' AND '.join(clauses)}""",
            params,
        ).fetchall()
    finally:
        conn.close()
    return [str(row[0]) for row in rows]


def revoke_member_workspace_access(user_id: str, workspace_id: str) -> dict[str, int]:
    """Membership removal revokes the removed member's workspace-scoped runtime leases."""
    user_id = str(user_id or "").strip()
    workspace_id = str(workspace_id or "").strip()
    if not user_id or not workspace_id:
        return {"leases_revoked": 0, "bindings_revoked": 0}
    leases = turn_credentials.revoke_matching_leases(payer_user_id=user_id, workspace_id=workspace_id)
    return {"leases_revoked": leases, "bindings_revoked": 0}


def revoke_member_role_downgrade(
    user_id: str,
    workspace_id: str,
    *,
    previous_role: str,
    new_role: str,
) -> dict[str, int]:
    """Downgrade from owner/admin revokes workspace broker leases for that member."""
    prev = str(previous_role or "").strip().lower()
    new = str(new_role or "").strip().lower()
    if prev in PRIVILEGED_MEMBER_ROLES and new not in PRIVILEGED_MEMBER_ROLES:
        return revoke_member_workspace_access(user_id, workspace_id)
    return {"leases_revoked": 0, "bindings_revoked": 0}


def revoke_workspace_authority(workspace_id: str) -> dict[str, int]:
    """Workspace deletion retires every active workspace binding and lease."""
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return {"leases_revoked": 0, "bindings_revoked": 0}
    binding_ids = _active_binding_ids(clauses=["workspace_id = ?"], params=[workspace_id])
    bindings_revoked = sum(
        1 for binding_id in binding_ids if credential_lifecycle.revoke_binding(binding_id, reason="workspace_deleted")
    )
    leases = turn_credentials.revoke_matching_leases(workspace_id=workspace_id)
    return {"bindings_revoked": bindings_revoked, "leases_revoked": leases}


def revoke_agent_profile_authority(agent_profile_id: str) -> dict[str, int]:
    """Agent deletion retires agent-scoped bindings and their leases."""
    agent_profile_id = str(agent_profile_id or "").strip()
    if not agent_profile_id:
        return {"leases_revoked": 0, "bindings_revoked": 0}
    binding_ids = _active_binding_ids(clauses=["agent_profile_id = ?"], params=[agent_profile_id])
    bindings_revoked = sum(
        1 for binding_id in binding_ids if credential_lifecycle.revoke_binding(binding_id, reason="agent_deleted")
    )
    leases = 0
    for binding_id in binding_ids:
        leases += turn_credentials.revoke_matching_leases(credential_binding_id=binding_id)
    return {"bindings_revoked": bindings_revoked, "leases_revoked": leases}


def revoke_payer_mode_change(workspace_id: str) -> dict[str, int]:
    """Credential/payer mode changes revoke workspace-scoped runtime leases."""
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return {"leases_revoked": 0, "bindings_revoked": 0}
    leases = turn_credentials.revoke_matching_leases(workspace_id=workspace_id)
    return {"leases_revoked": leases, "bindings_revoked": 0}


def revoke_provider_disconnect(
    *,
    binding_id: str,
    user_id: str = "",
    workspace_id: str = "",
    provider: str = "",
) -> dict[str, int]:
    """Provider disconnect retires the binding boundary and matching leases."""
    binding_id = str(binding_id or "").strip()
    if not binding_id:
        return {"leases_revoked": 0, "bindings_revoked": 0}
    revoked = credential_lifecycle.revoke_binding(binding_id, reason="provider_disconnect")
    leases = turn_credentials.revoke_matching_leases(
        payer_user_id=str(user_id or "").strip(),
        workspace_id=str(workspace_id or "").strip(),
        provider=str(provider or "").strip().lower(),
        credential_binding_id=binding_id,
    )
    return {"bindings_revoked": 1 if revoked else 0, "leases_revoked": leases}
