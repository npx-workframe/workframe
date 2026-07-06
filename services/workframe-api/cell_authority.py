"""CellAuthorityGate — install/cell authority (WF-007)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from domain.entities import Cell, DeploymentMode, Grant, GrantCapability

CellOperation = Literal["create", "open", "update", "connect", "adopt"]
CellDecisionKind = Literal["allow", "allow_readonly", "deny", "needs_user_action"]


@dataclass(frozen=True)
class CellAuthorityDecision:
    operation: CellOperation
    decision: CellDecisionKind
    reason: str
    cell: Cell | None
    mutation_plan: tuple[str, ...] = field(default_factory=tuple)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_cell_from_manifest(install_root: str | Path) -> Cell | None:
    root = Path(install_root).resolve()
    manifest_path = root / "workframe-manifest.json"
    data = _read_json(manifest_path)
    if not data:
        return None
    layout = data.get("layout") if isinstance(data.get("layout"), dict) else {}
    security = data.get("security") if isinstance(data.get("security"), dict) else {}
    docker = data.get("docker") if isinstance(data.get("docker"), dict) else {}
    mode_raw = str(security.get("deployment_mode") or data.get("deployment_mode") or "single_user_local")
    try:
        mode = DeploymentMode(mode_raw)
    except ValueError:
        mode = DeploymentMode.SINGLE_USER_LOCAL
    return Cell(
        cell_id=str(data.get("install_id") or data.get("project_name") or root.name),
        install_root=str(root),
        manifest_path=str(manifest_path),
        package_name=str(data.get("package_name") or "create-workframe"),
        package_version=str(data.get("package_version") or ""),
        deployment_mode=mode,
        created_at=None,  # type: ignore[arg-type]
        git_ref=data.get("git_ref"),
        packed_artifact_digest=data.get("packed_artifact_digest"),
    )


def _dir_nonempty(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        return any(path.iterdir())
    except OSError:
        return False


def evaluate_create(
    target: str | Path,
    *,
    force: bool = False,
    package_version: str = "",
    packed_digest: str | None = None,
) -> CellAuthorityDecision:
    root = Path(target).resolve()
    if root.exists() and _dir_nonempty(root) and not force:
        return CellAuthorityDecision(
            operation="create",
            decision="deny",
            reason="target_not_empty",
            cell=None,
            mutation_plan=(),
        )
    plan = (
        "assert target writable",
        "write scaffold tree",
        f"record package_version={package_version or 'unknown'}",
        "atomic write workframe-manifest.json",
        "verify layout Agents/ Files/",
    )
    cell = Cell(
        cell_id=root.name,
        install_root=str(root),
        manifest_path=str(root / "workframe-manifest.json"),
        package_name="create-workframe",
        package_version=package_version,
        deployment_mode=DeploymentMode.SINGLE_USER_LOCAL,
        created_at=None,  # type: ignore[arg-type]
        packed_artifact_digest=packed_digest,
    )
    return CellAuthorityDecision(
        operation="create",
        decision="allow",
        reason="empty_target_or_force",
        cell=cell,
        mutation_plan=plan,
    )


def evaluate_open(install_root: str | Path, *, doctor_report: dict[str, Any] | None = None) -> CellAuthorityDecision:
    root = Path(install_root).resolve()
    cell = load_cell_from_manifest(root)
    if not cell:
        return CellAuthorityDecision(
            operation="open",
            decision="deny",
            reason="manifest_missing",
            cell=None,
        )
    manifest_layout = _read_json(Path(cell.manifest_path)) or {}
    layout = manifest_layout.get("layout") if isinstance(manifest_layout.get("layout"), dict) else {}
    expected_ws = str(layout.get("workspace") or "Files")
    if not (root / expected_ws).is_dir():
        return CellAuthorityDecision(
            operation="open",
            decision="deny",
            reason="workspace_mount_missing",
            cell=cell,
        )
    if doctor_report and doctor_report.get("decision") == "needs_user_action":
        return CellAuthorityDecision(
            operation="open",
            decision="needs_user_action",
            reason="doctor_prerequisites",
            cell=cell,
        )
    return CellAuthorityDecision(
        operation="open",
        decision="allow_readonly",
        reason="manifest_and_layout_ok",
        cell=cell,
    )


def evaluate_update(
    install_root: str | Path,
    *,
    open_decision: CellAuthorityDecision | None = None,
    user_ack: bool = False,
) -> CellAuthorityDecision:
    opened = open_decision or evaluate_open(install_root)
    if opened.decision != "allow_readonly":
        return CellAuthorityDecision(
            operation="update",
            decision="deny",
            reason=f"open_blocked:{opened.reason}",
            cell=opened.cell,
        )
    if not user_ack:
        return CellAuthorityDecision(
            operation="update",
            decision="needs_user_action",
            reason="explicit_user_ack_required",
            cell=opened.cell,
            mutation_plan=(
                "snapshot manifest digest",
                "apply bounded file mutations",
                "verify health",
                "record evidence artifact",
            ),
        )
    return CellAuthorityDecision(
        operation="update",
        decision="allow",
        reason="open_ok_and_ack",
        cell=opened.cell,
        mutation_plan=(
            "snapshot manifest digest",
            "apply bounded file mutations",
            "verify health",
            "record evidence artifact",
        ),
    )


def evaluate_connect(*, remote_attested: bool = False) -> CellAuthorityDecision:
    if not remote_attested:
        return CellAuthorityDecision(
            operation="connect",
            decision="deny",
            reason="remote_not_attested",
            cell=None,
        )
    return CellAuthorityDecision(
        operation="connect",
        decision="allow_readonly",
        reason="remote_attested",
        cell=None,
    )


def evaluate_adopt(*, runtime_kind: str = "") -> CellAuthorityDecision:
    # ponytail: adopt blocked until WF-014/NS-P4 — always deny non-proven adapters
    if runtime_kind and runtime_kind not in ("hermes_managed", ""):
        return CellAuthorityDecision(
            operation="adopt",
            decision="deny",
            reason="adapter_not_proven",
            cell=None,
        )
    return CellAuthorityDecision(
        operation="adopt",
        decision="deny",
        reason="adopt_deferred_wf014",
        cell=None,
    )


def file_write_grant(cell: Cell) -> Grant:
    return Grant(
        grant_id=f"cell-fw-{cell.cell_id}",
        run_id="",
        capability=GrantCapability.FILE_WRITE,
        scope={"install_root": cell.install_root},
        granted_by="cell_authority_gate",
    )


def cell_id_from_env() -> str:
    return str(os.environ.get("WORKFRAME_PROJECT") or os.environ.get("PROJECT_NAME") or "default")
