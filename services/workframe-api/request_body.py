"""Bounded request-body and pagination parsing for the Workframe HTTP API."""
from __future__ import annotations

import json
import os
import re
from typing import Any, BinaryIO, Mapping


_LENGTH_RE = re.compile(r"^(0|[1-9][0-9]{0,11})$")


def _configured_max_body_bytes() -> int:
    raw = str(os.environ.get("WORKFRAME_MAX_JSON_BODY_BYTES", "1048576") or "").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 1048576
    return min(max(value, 1024), 16 * 1024 * 1024)


MAX_JSON_BODY_BYTES = _configured_max_body_bytes()


class RequestBodyError(ValueError):
    """Public, nonsecret request-body failure."""

    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = int(status)
        self.code = str(code)


def content_length(headers: Mapping[str, Any]) -> int:
    transfer = str(headers.get("Transfer-Encoding") or "").strip()
    if transfer:
        raise RequestBodyError(400, "unsupported_transfer_encoding")
    raw = str(headers.get("Content-Length") or "").strip()
    if not raw:
        return 0
    if not _LENGTH_RE.fullmatch(raw):
        raise RequestBodyError(400, "invalid_content_length")
    return int(raw)


def read_body_bytes(
    stream: BinaryIO,
    headers: Mapping[str, Any],
    *,
    max_bytes: int = MAX_JSON_BODY_BYTES,
) -> bytes:
    limit = max(1, int(max_bytes))
    length = content_length(headers)
    if length > limit:
        raise RequestBodyError(413, "payload_too_large")
    if length == 0:
        return b""

    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = stream.read(min(remaining, 64 * 1024))
        if not chunk:
            raise RequestBodyError(400, "incomplete_body")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_json_object(
    stream: BinaryIO,
    headers: Mapping[str, Any],
    *,
    max_bytes: int = MAX_JSON_BODY_BYTES,
) -> dict[str, Any]:
    raw = read_body_bytes(stream, headers, max_bytes=max_bytes)
    if not raw:
        return {}
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise RequestBodyError(400, "invalid_utf8") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RequestBodyError(400, "invalid_json") from exc
    if not isinstance(value, dict):
        raise RequestBodyError(400, "json_object_required")
    return value


def parse_pagination(
    query: Mapping[str, list[str]],
    *,
    default_limit: int = 50,
    max_limit: int = 200,
    max_offset: int = 100_000,
) -> tuple[int, int]:
    try:
        limit = int((query.get("limit") or [str(default_limit)])[0])
        offset = int((query.get("offset") or ["0"])[0])
    except (TypeError, ValueError, IndexError) as exc:
        raise RequestBodyError(400, "invalid_pagination") from exc
    if limit < 1 or limit > max_limit or offset < 0 or offset > max_offset:
        raise RequestBodyError(400, "invalid_pagination")
    return limit, offset
