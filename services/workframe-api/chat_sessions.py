"""WF-032 extract: Hermes session info, chat bootstrap, and message turns."""

from __future__ import annotations

import json
import re
import sqlite3
import time
import urllib.parse
from pathlib import Path
from typing import Any

import api_meta
import provider_catalog


def _srv():
    import server as srv

    return srv


_session_info_cache: dict[str, tuple[dict[str, Any], float]] = {}
_SESSION_INFO_TTL_SEC = 5.0


def _invalidate_session_info_cache(profile: str = "", session_id: str = "") -> None:
    if profile and session_id:
        _session_info_cache.pop(f"{_srv().safe_profile_slug(profile)}:{session_id}", None)
    elif profile:
        prefix = f"{_srv().safe_profile_slug(profile)}:"
        for key in list(_session_info_cache):
            if key.startswith(prefix):
                _session_info_cache.pop(key, None)
    else:
        _session_info_cache.clear()

_USER_IMAGE_RE = re.compile(
    r"\[User attached image:\s*([^\]]+)\]|ðŸ“Ž\s*Attached image:\s*(\S+)",
    re.IGNORECASE,
)


def _parse_multimodal_content(content: str) -> list[dict[str, Any]]:
    text = (content or "").strip()
    if not text.startswith("["):
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    segments: list[dict[str, Any]] = []
    for part in data:
        if not isinstance(part, dict):
            continue
        kind = str(part.get("type") or "")
        if kind in {"image_url", "input_image", "image"}:
            url = ""
            if isinstance(part.get("image_url"), dict):
                url = str(part["image_url"].get("url") or "")
            elif isinstance(part.get("image_url"), str):
                url = part["image_url"]
            path = str(part.get("path") or url or "image")
            segments.append({"kind": "image", "path": path, "name": Path(path).name})
        elif kind in {"text", "input_text", "output_text"}:
            body = str(part.get("text") or part.get("content") or "").strip()
            if body:
                segments.append({"kind": "text", "text": body})
    return segments


def _parse_user_content_segments(content: str) -> list[dict[str, Any]]:
    text = (content or "").strip()
    if not text:
        return []
    multimodal = _parse_multimodal_content(text)
    if multimodal:
        return multimodal
    segments: list[dict[str, Any]] = []
    remainder = text
    for match in _USER_IMAGE_RE.finditer(text):
        name = (match.group(1) or match.group(2) or "").strip()
        if name:
            segments.append({"kind": "image", "path": name, "name": Path(name).name})
        remainder = remainder.replace(match.group(0), " ").strip()
    if remainder:
        segments.append({"kind": "text", "text": remainder})
    elif not segments:
        segments.append({"kind": "text", "text": text})
    return segments


def _parse_tool_content(content: str) -> dict[str, Any]:
    """Parse Hermes tool row JSON when present."""
    text = (content or "").strip()
    if not text:
        return {"output": "", "exit_code": None, "error": None}
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            output = data.get("output")
            if output is None:
                output = data.get("result")
            if output is None and "files" in data:
                output = json.dumps(data, ensure_ascii=False)
            elif output is None:
                output = text
            return {
                "output": str(output or ""),
                "exit_code": data.get("exit_code"),
                "error": data.get("error"),
            }
    except json.JSONDecodeError:
        pass
    return {"output": text, "exit_code": None, "error": None}


def _message_row_segments(m: sqlite3.Row) -> list[dict[str, Any]]:
    """Map one state.db messages row to structured UI segments."""
    role = str(m["role"] or "")
    if role == "session_meta":
        return []

    segments: list[dict[str, Any]] = []
    reasoning = (m["reasoning_content"] or "").strip()
    content = (m["content"] or "").strip()
    tool_name = (m["tool_name"] or "").strip()

    if reasoning:
        segments.append({"kind": "thinking", "text": reasoning})

    if role == "tool":
        parsed = _parse_tool_content(content)
        exit_code = parsed.get("exit_code")
        status = "error" if parsed.get("error") or (exit_code not in (None, 0)) else "done"
        segments.append(
            {
                "kind": "tool",
                "name": tool_name or "tool",
                "status": status,
                "output": parsed.get("output") or "",
            }
        )
    elif role == "user":
        segments.extend(_parse_user_content_segments(content))
    elif content:
        segments.append({"kind": "text", "text": content})

    return segments


def _profile_model(profile: str) -> str:
    """Read configured model from Hermes profile yaml, else latest session model."""
    block = _srv()._read_model_block(profile)
    configured = str(block.get("default") or "").strip()
    if configured:
        return configured
    for name in ("config.yaml", "profile.yaml"):
        path = _srv()._profile_dir(profile) / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        flat = re.search(r"^[ \t]*model:[ \t]*['\"]?([^'\"#\n]+)['\"]?[ \t]*(?:#.*)?$", text, re.MULTILINE)
        if flat:
            value = flat.group(1).strip()
            if value and not value.endswith(":"):
                return value

    db = _srv()._profile_dir(profile) / "state.db"
    conn = _srv()._ro_sqlite_live(db)
    if not conn:
        return ""
    try:
        row = conn.execute(
            "SELECT model FROM sessions WHERE model IS NOT NULL AND model != '' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return ""
        model = str(row["model"] or "").strip()
        if model.startswith("default:"):
            model = model.split(":", 1)[1].strip()
        return model
    except sqlite3.Error:
        return ""
    finally:
        conn.close()


def _llm_attribution_for_profile(profile: str, session_model: str = "") -> tuple[str, str]:
    """Resolve model id + billing provider for chat turn footers."""
    _ = session_model  # ponytail: Hermes sessions.model is profile slug, not LLM id
    try:
        prof = _srv().resolve_hermes_profile(str(profile or "").strip())
    except ValueError:
        return "", ""
    block = _srv()._read_model_block(prof)
    model = str(block.get("default") or "").strip()
    billing = _srv()._billing_provider_id_from_hermes_config(str(block.get("provider") or ""))
    if not billing:
        billing = _srv()._llm_billing_provider(prof)
    if not billing and model:
        infer_llm = {
            str(spec["id"]).lower()
            for spec in provider_catalog.PROVIDER_CONNECT_CATALOG
            if str(spec.get("category") or "") == "llm"
        }
        billing = _srv()._resolve_billing_provider_for_model(model, infer_llm)
    return model, str(billing or "").strip()


def _latest_session_id(profile: str) -> str:
    """Most recent session â€” prefer active (ended_at IS NULL), then by started_at."""
    db = _srv()._profile_dir(profile) / "state.db"
    conn = _srv()._ro_sqlite_live(db)
    if not conn:
        return ""
    try:
        row = conn.execute(
            """
            SELECT id FROM sessions
            ORDER BY (ended_at IS NULL) DESC, started_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        return str(row["id"]) if row else ""
    except sqlite3.Error:
        return ""
    finally:
        conn.close()


def _session_info(profile: str, session_id: str) -> dict[str, Any]:
    sid = str(session_id or "").strip()
    prof = _srv().safe_profile_slug(str(profile or "").strip())
    cache_key = f"{prof}:{sid}"
    now = time.monotonic()
    cached = _session_info_cache.get(cache_key)
    if cached and now - cached[1] < _SESSION_INFO_TTL_SEC:
        return dict(cached[0])
    empty: dict[str, Any] = {
        "session_id": session_id,
        "title": "",
        "active": False,
        "message_count": 0,
    }
    db = _srv()._profile_dir(prof) / "state.db"
    conn = _srv()._ro_sqlite_live(db)
    if not conn:
        return empty
    try:
        row = conn.execute(
            """
            SELECT id, title, started_at, ended_at, message_count
            FROM sessions WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
        if not row:
            _session_info_cache[cache_key] = (empty, now)
            return empty
        result = {
            "session_id": str(row["id"]),
            "title": (row["title"] or "").strip(),
            "active": row["ended_at"] is None,
            "message_count": int(row["message_count"] or 0),
            "started_at": _srv()._iso_from_unix(row["started_at"]),
        }
        _session_info_cache[cache_key] = (result, now)
        return result
    except sqlite3.Error:
        _session_info_cache[cache_key] = (empty, now)
        return empty
    finally:
        conn.close()


def _is_blank_session_title(title: str) -> bool:
    t = str(title or "").strip()
    return not t or t == "(untitled)"


def _resolved_session_title(hermes_prof: str, session_id: str, fallback: str = "") -> str:
    """Hermes state.db title, else room_sessions / default â€” not the (untitled) sentinel."""
    info = _session_info(hermes_prof, session_id)
    title = str(info.get("title") or "").strip()
    if not _is_blank_session_title(title):
        return title
    fb = str(fallback or "").strip()
    if fb and not _is_blank_session_title(fb):
        return fb
    template = (
        _srv()._runtime_template_slug(hermes_prof)
        if _srv()._is_runtime_profile_slug(hermes_prof)
        else hermes_prof
    )
    return _srv()._default_session_title(template)


def _ensure_hermes_session_title(profile: str, session_id: str, title: str) -> None:
    """Backfill empty Hermes session titles on bind via profile API (state.db is often gateway-locked)."""
    sid = str(session_id or "").strip()
    want = str(title or "").strip()
    if not sid or _is_blank_session_title(want):
        return
    if not _is_blank_session_title(str(_session_info(profile, sid).get("title") or "")):
        return
    try:
        path = f"/api/sessions/{urllib.parse.quote(sid, safe='')}"
        status, _ = _srv()._profile_api_request(profile, "PATCH", path, {"title": want})
        if status < 300:
            return
    except Exception:  # noqa: BLE001
        pass


def _session_info_display(profile: str, session_id: str, fallback: str = "") -> dict[str, Any]:
    """Like _session_info but title is never blank â€” for API responses that show humans a label."""
    info = _session_info(profile, session_id)
    title = _resolved_session_title(profile, session_id, fallback)
    info["title"] = title if not _is_blank_session_title(title) else "(untitled)"
    return info


def _latest_api_session_id(profile: str) -> str:
    """Most recent api_server session â€” prefer active, then by started_at."""
    db = _srv()._profile_dir(profile) / "state.db"
    conn = _srv()._ro_sqlite_live(db)
    if not conn:
        return ""
    try:
        row = conn.execute(
            """
            SELECT id FROM sessions
            WHERE source = 'api_server'
            ORDER BY (ended_at IS NULL) DESC, started_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        return str(row["id"]) if row else ""
    except sqlite3.Error:
        return ""
    finally:
        conn.close()


def _latest_active_run_id(profile: str) -> str:
    """Most recent active (ended_at IS NULL) api_server run session (run_ prefixed)."""
    db = _srv()._profile_dir(profile) / "state.db"
    conn = _srv()._ro_sqlite_live(db)
    if not conn:
        return ""
    try:
        row = conn.execute(
            """
            SELECT id FROM sessions
            WHERE source = 'api_server' AND ended_at IS NULL
            AND id LIKE 'run%'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        return str(row["id"]) if row else ""
    except sqlite3.Error:
        return ""
    finally:
        conn.close()

def _session_exists(profile: str, session_id: str) -> bool:
    sid = (session_id or "").strip()
    if not sid:
        return False
    db = _srv()._profile_dir(profile) / "state.db"
    conn = _srv()._ro_sqlite_live(db)
    if not conn:
        return False
    try:
        row = conn.execute("SELECT 1 FROM sessions WHERE id = ?", (sid,)).fetchone()
        return row is not None
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def chat_session(profile: str, session_id: str = "", source_id: str = "ui") -> dict[str, Any]:
    sid = (session_id or "").strip() or _latest_session_id(profile)
    if not sid:
        return {"ok": True, "session_id": "", "title": "", "active": False, "message_count": 0}
    info = _session_info(profile, sid)
    return {"ok": True, **info}


def chat_bootstrap(profile: str, persistent: str = "", source_id: str = "ui") -> dict[str, Any]:
    """Resolve native profile + latest/persistent Hermes session ids + dashboard WS bootstrap."""
    prof = (profile or "").strip() or _srv()._primary_profile()
    latest_id = _latest_session_id(prof)
    persistent_id = (persistent or "").strip()
    persistent_valid = persistent_id and _session_exists(prof, persistent_id)

    active_id = persistent_id if persistent_valid else ""
    latest_info = _session_info(prof, latest_id) if latest_id else {}
    persistent_info = _session_info(prof, persistent_id) if persistent_valid else {}
    active_info = _session_info(prof, active_id) if active_id else {}

    try:
        hermes = api_meta.hermes_bootstrap(prof)
    except ValueError as exc:
        hermes = {"ok": False, "error": str(exc)}

    display = _srv()._profile_display_name(prof) if prof else _srv()._native_display_name()
    return {
        "ok": True,
        "profile": prof,
        "native_agent_name": display,
        "latest_session_id": latest_id,
        "latest_session": latest_info,
        "persistent_session_id": persistent_id if persistent_valid else "",
        "persistent_session": persistent_info,
        "active_session_id": active_id,
        "active_session": active_info,
        "hermes": hermes,
    }


def chat_messages(profile: str, session_id: str = "", source_id: str = "ui") -> dict[str, Any]:
    """Recent chat turns for one Hermes session â€” grouped agent turns with segments."""
    sid = (session_id or "").strip() or _latest_session_id(profile)
    session = _session_info(profile, sid) if sid else {}
    db = _srv()._profile_dir(profile) / "state.db"
    conn = _srv()._ro_sqlite_live(db)
    if not conn or not sid:
        return {"ok": True, "session_id": sid, "session": session, "messages": []}
    turns: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    author_profile = (
        _srv()._runtime_template_slug(profile) if _srv()._is_runtime_profile_slug(profile) else profile
    )
    display = _srv()._profile_display_name(profile)
    attr_model, attr_provider = _llm_attribution_for_profile(profile)
    try:
        raw = conn.execute(
            """
            SELECT m.id, m.role, m.content, m.reasoning_content, m.tool_name,
                   m.timestamp, m.token_count, s.model AS session_model
            FROM messages m
            LEFT JOIN sessions s ON s.id = m.session_id
            WHERE m.role IN ('user', 'assistant', 'tool') AND m.session_id = ?
            ORDER BY m.timestamp ASC, m.id ASC
            LIMIT 200
            """,
            (sid,),
        ).fetchall()
        for m in raw:
            role = str(m["role"] or "")
            segments = _message_row_segments(m)
            if not segments:
                continue
            tokens = int(m["token_count"] or 0)
            ts = _srv()._iso_from_unix(m["timestamp"])

            if role == "user":
                if current:
                    turns.append(current)
                    current = None
                turns.append(
                    {
                        "id": f"msg-{m['id']}",
                        "authorId": "user",
                        "authorName": "You",
                        "role": "user",
                        "segments": segments,
                        "timestamp": ts,
                        "tokens": tokens,
                    }
                )
                continue

            if current and current["role"] == "agent":
                current["segments"].extend(segments)
                current["tokens"] += tokens
                if attr_model:
                    current["model"] = attr_model
                    current["llm_provider"] = attr_provider
            else:
                if current:
                    turns.append(current)
                current = {
                    "id": f"turn-{m['id']}",
                    "authorId": author_profile,
                    "authorName": display,
                    "role": "agent",
                    "segments": list(segments),
                    "timestamp": ts,
                    "tokens": tokens,
                    "model": attr_model,
                    "llm_provider": attr_provider,
                }
        if current:
            turns.append(current)
    except sqlite3.Error:
        return {"ok": True, "session_id": sid, "session": session, "messages": []}
    finally:
        conn.close()
    return {"ok": True, "session_id": sid, "session": session, "messages": turns}
