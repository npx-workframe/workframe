"""WF-007 CellAuthorityGate self-check."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cell_authority import (  # noqa: E402
    evaluate_adopt,
    evaluate_connect,
    evaluate_create,
    evaluate_open,
    evaluate_update,
    load_cell_from_manifest,
)


def test_create_deny_nonempty() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "existing.txt").write_text("x", encoding="utf-8")
        decision = evaluate_create(root)
        assert decision.decision == "deny"
        assert decision.reason == "target_not_empty"


def test_create_allow_empty() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "newcell"
        decision = evaluate_create(root, package_version="0.1.0")
        assert decision.decision == "allow"
        assert decision.mutation_plan


def test_open_readonly() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "Files").mkdir()
        manifest = {
            "install_id": "cell-1",
            "package_name": "create-workframe",
            "package_version": "0.1.0",
            "layout": {"workspace": "Files", "runtime": "Agents"},
        }
        (root / "workframe-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        cell = load_cell_from_manifest(root)
        assert cell is not None
        decision = evaluate_open(root)
        assert decision.decision == "allow_readonly"


def test_update_needs_ack() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "Files").mkdir()
        (root / "workframe-manifest.json").write_text(
            json.dumps({"layout": {"workspace": "Files"}}),
            encoding="utf-8",
        )
        decision = evaluate_update(root, user_ack=False)
        assert decision.decision == "needs_user_action"


def test_adopt_denied() -> None:
    assert evaluate_adopt(runtime_kind="cursor").reason == "adapter_not_proven"
    assert evaluate_connect(remote_attested=False).decision == "deny"


if __name__ == "__main__":
    test_create_deny_nonempty()
    test_create_allow_empty()
    test_open_readonly()
    test_update_needs_ack()
    test_adopt_denied()
    print("test_cell_authority: ok")
