#!/usr/bin/env python3
from __future__ import annotations

import io
import unittest

import request_body


class RequestBodyTests(unittest.TestCase):
    def read_json(self, raw: bytes, *, length: str | None = None, max_bytes: int = 1024):
        headers: dict[str, str] = {}
        if length is not None:
            headers["Content-Length"] = length
        return request_body.read_json_object(io.BytesIO(raw), headers, max_bytes=max_bytes)

    def assert_error(self, code: str, status: int, fn) -> None:
        with self.assertRaises(request_body.RequestBodyError) as caught:
            fn()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(caught.exception.status, status)

    def test_empty_and_object_bodies(self) -> None:
        self.assertEqual(self.read_json(b"", length="0"), {})
        self.assertEqual(self.read_json(b'{"ok":true}', length="11"), {"ok": True})

    def test_malformed_or_nonobject_json_is_rejected(self) -> None:
        self.assert_error("invalid_json", 400, lambda: self.read_json(b"{", length="1"))
        self.assert_error("invalid_body", 400, lambda: self.read_json(b"[]", length="2"))
        self.assert_error("invalid_utf8", 400, lambda: self.read_json(b"\xff", length="1"))

    def test_content_length_is_strict_and_bounded(self) -> None:
        self.assert_error(
            "invalid_content_length",
            400,
            lambda: self.read_json(b"{}", length="-1"),
        )
        self.assert_error(
            "invalid_content_length",
            400,
            lambda: self.read_json(b"{}", length="abc"),
        )
        self.assert_error(
            "payload_too_large",
            413,
            lambda: self.read_json(b"{}", length="2", max_bytes=1),
        )
        self.assert_error(
            "incomplete_body",
            400,
            lambda: self.read_json(b"{}", length="3"),
        )
        self.assert_error(
            "unsupported_transfer_encoding",
            400,
            lambda: request_body.read_json_object(
                io.BytesIO(b"{}"),
                {"Transfer-Encoding": "chunked"},
            ),
        )

    def test_pagination_is_bounded(self) -> None:
        self.assertEqual(request_body.parse_pagination({}), (50, 0))
        self.assertEqual(
            request_body.parse_pagination({"limit": ["20"], "offset": ["10"]}),
            (20, 10),
        )
        for query in (
            {"limit": ["0"]},
            {"limit": ["201"]},
            {"limit": ["x"]},
            {"offset": ["-1"]},
            {"offset": ["100001"]},
        ):
            self.assert_error(
                "invalid_pagination",
                400,
                lambda query=query: request_body.parse_pagination(query),
            )


if __name__ == "__main__":
    unittest.main()
