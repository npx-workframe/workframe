#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import unittest

from handler_modules import handler_workspace


class FailingServer:
    AUTH_DB_PATH = type("P", (), {"parent": "."})()

    @staticmethod
    def _resolve_wid(value: str) -> str:
        return "ws-1"

    @staticmethod
    def _workframe_db():
        raise sqlite3.OperationalError("database unavailable")

    @staticmethod
    def _user_can_access_room(conn, room_id: str, user_id: str) -> bool:
        return True


class Handler(handler_workspace.WorkspaceRoutesMixin):
    auth_user = "user-1"

    def __init__(self) -> None:
        self.responses: list[tuple[int, dict]] = []

    def _json(self, status: int, payload: dict) -> None:
        self.responses.append((status, payload))


class TruthfulFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_srv = handler_workspace._srv
        handler_workspace._srv = lambda: FailingServer

    def tearDown(self) -> None:
        handler_workspace._srv = self.original_srv

    def assert_database_unavailable(self, invoke) -> None:
        handler = Handler()
        invoke(handler)
        self.assertEqual(
            handler.responses,
            [(503, {"ok": False, "error": "database_unavailable"})],
        )

    def test_room_member_failure_is_not_empty_success(self) -> None:
        self.assert_database_unavailable(
            lambda handler: handler._route_pattern_get_room_members(
                "/api/rooms/room-1/members", {}
            )
        )

    def test_room_message_failure_is_not_empty_success(self) -> None:
        self.assert_database_unavailable(
            lambda handler: handler._route_pattern_get_room_messages(
                "/api/rooms/room-1/messages", {"limit": ["50"], "offset": ["0"]}
            )
        )

    def test_workspace_collection_failures_are_not_empty_success(self) -> None:
        routes = (
            ("_route_pattern_get_workspace_invites", "/api/workspace/ws-1/invites"),
            ("_route_pattern_get_workspace_memory", "/api/workspace/ws-1/memory"),
            ("_route_pattern_get_workspace_budget", "/api/workspace/ws-1/budget"),
            ("_route_pattern_get_workspace_grants", "/api/workspace/ws-1/grants"),
        )
        for method_name, path in routes:
            with self.subTest(method=method_name):
                self.assert_database_unavailable(
                    lambda handler, method_name=method_name, path=path: getattr(
                        handler, method_name
                    )(path, {})
                )


if __name__ == "__main__":
    unittest.main()
