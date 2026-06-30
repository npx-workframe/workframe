"""In-process auth endpoint throttle — trust boundary (0022 N5)."""
from __future__ import annotations

import time
from collections import deque

_BUCKETS: dict[str, deque[float]] = {}
_MINUTE_WINDOW = 60.0
_MINUTE_MAX = 5
_HOUR_WINDOW = 3600.0
_HOUR_MAX = 20


def _bucket_key(kind: str, client_ip: str, email: str) -> str:
    return f"{kind}:{client_ip}:{email.strip().lower()}"


def _prune(queue: deque[float], now: float, window: float) -> None:
    while queue and now - queue[0] > window:
        queue.popleft()


def allow_auth_request(kind: str, client_ip: str, email: str) -> bool:
    now = time.time()
    key = _bucket_key(kind, client_ip, email)
    queue = _BUCKETS.setdefault(key, deque())
    _prune(queue, now, _HOUR_WINDOW)
    if len(queue) >= _HOUR_MAX:
        return False
    recent = deque(queue)
    _prune(recent, now, _MINUTE_WINDOW)
    if len(recent) >= _MINUTE_MAX:
        return False
    queue.append(now)
    return True


def reset_for_tests() -> None:
    _BUCKETS.clear()


if __name__ == "__main__":
    reset_for_tests()
    ip = "203.0.113.1"
    email = "a@example.com"
    for _ in range(_MINUTE_MAX):
        assert allow_auth_request("start", ip, email)
    assert not allow_auth_request("start", ip, email)
    print("auth_rate_limit ok")
