"""WF-032 extract: host health metrics for snapshot/dashboard."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

_cpu_cache: dict[str, Any] = {"at": 0.0, "percent": 0.0}


def _srv():
    import server as srv

    return srv


def _read_proc_stat() -> tuple[float, float]:
    try:
        line = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0]
        parts = [int(x) for x in line.split()[1:]]
        idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
        return float(sum(parts)), float(idle)
    except (OSError, ValueError, IndexError):
        return 0.0, 0.0


def health_data(profile: str) -> dict[str, Any]:
    global _cpu_cache
    mem_total_kb = mem_avail_kb = 0
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                mem_total_kb = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                mem_avail_kb = int(line.split()[1])
    except OSError:
        pass
    mem_total_mb = mem_total_kb / 1024
    mem_used_mb = max(0.0, mem_total_mb - mem_avail_kb / 1024)
    workspace = _srv().WORKSPACE
    hermes_data = _srv().HERMES_DATA
    disk_total = disk_free = 0
    try:
        st = os.statvfs(str(workspace if workspace.exists() else hermes_data))
        disk_total = st.f_blocks * st.f_frsize
        disk_free = st.f_bavail * st.f_frsize
    except OSError:
        pass
    disk_total_gb = disk_total / (1024**3)
    disk_used_gb = max(0.0, (disk_total - disk_free) / (1024**3))

    now = time.time()
    if now - float(_cpu_cache.get("at") or 0) > 3.0:
        t1, i1 = _read_proc_stat()
        time.sleep(0.12)
        t2, i2 = _read_proc_stat()
        cpu_pct = 0.0
        if t2 > t1:
            cpu_pct = max(0.0, min(100.0, (1.0 - (i2 - i1) / (t2 - t1)) * 100.0))
        _cpu_cache = {"at": now, "percent": round(cpu_pct, 1)}
    cpu_pct = float(_cpu_cache.get("percent") or 0.0)
    mem_pct = max(0.0, min(100.0, (mem_used_mb / mem_total_mb * 100) if mem_total_mb else 0.0))
    disk_pct = max(0.0, min(100.0, (disk_used_gb / disk_total_gb * 100) if disk_total_gb else 0.0))
    db_path = _srv()._profile_dir(profile) / "state.db" if profile else hermes_data / "state.db"

    return {
        "cpu_percent": cpu_pct,
        "memory_percent": round(mem_pct, 1),
        "disk_percent": round(disk_pct, 1),
        "cpu_pct": cpu_pct,
        "mem_pct": round(mem_pct, 1),
        "disk_pct": round(disk_pct, 1),
        "mem_used_mb": round(mem_used_mb, 1),
        "mem_total_mb": round(mem_total_mb, 1),
        "disk_used_gb": round(disk_used_gb, 2),
        "disk_total_gb": round(disk_total_gb, 2),
        "db_size_mb": round(_srv()._file_size_mb(db_path), 2),
    }
