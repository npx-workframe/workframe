"""WF-032 extract: aggregate Hermes/workspace snapshot for /api/snapshot."""

from __future__ import annotations

from typing import Any

import crew_registry
import health_monitor
from kanban_cron import cron_data, kanban_data


def _srv():
    import server as srv

    return srv


def build_snapshot() -> dict[str, Any]:
    profiles = _srv()._list_profiles()
    primary = _srv()._primary_profile()
    gateway = _srv().gateway_data(primary) if primary else _srv().gateway_data("")
    crew = crew_registry.crew_data(profiles, primary, gateway)
    activity = _srv().activity_data(profiles, crew)
    health = health_monitor.health_data(primary)
    sessions = _srv().sessions_data(primary) if primary else _srv().sessions_data("")
    kanban = kanban_data()
    cron = cron_data(primary) if primary else cron_data("")
    return {
        "ok": True,
        "generated_at": _srv()._utc_now(),
        "version": _srv().VERSION,
        "project_name": _srv().PROJECT_NAME,
        "native_profile": primary,
        "native_agent_name": _srv()._native_display_name(),
        "native_model": _srv()._profile_model(primary) if primary else "",
        "profiles": profiles,
        "crew": crew,
        "gateway": gateway,
        "sessions": sessions,
        "activity": activity["entries"],
        "agents": activity["agents"],
        "activity_by_day": activity["activity_by_day"],
        "stats": activity["stats"],
        "kanban": kanban,
        "cron": cron,
        "crons": cron,
        "vps": health,
        "health": health,
    }
