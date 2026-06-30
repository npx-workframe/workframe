# SECURE_MODE Flag System Design

> **Implementation status (2026-06-20):** `SECURE_MODE` and `DEV_LOCAL_UNSAFE` are implemented in `services/workframe-api/server.py`. Default when neither is set: **secure**. Docker socket calls from the API are blocked in secure mode; specialist profile lifecycle goes through `workframe-supervisor` when `WORKFRAME_SUPERVISOR_URL` and `WORKFRAME_SUPERVISOR_TOKEN` are set. See `RUNTIME_OPERATIONS.md`.

## Problem

The Workframe BFF (`workframe-api/server.py`) currently runs with no security boundary: CORS is wide open (`Access-Control-Allow-Origin: *`), every API endpoint is unauthenticated, and the Docker socket is always accessible. This is fine for local development but dangerous if the container is ever exposed beyond `127.0.0.1`. We need a two-mode system:

- **`SECURE_MODE=true`** — production posture: strict CORS, auth required on all mutating endpoints, Docker socket access gated.
- **`DEV_LOCAL_UNSAFE=true`** — development posture: current behavior preserved (open CORS, no auth, Docker socket open).

These two flags are mutually exclusive. Exactly one must be set.

---

## 1. Flag Semantics

### Environment variables

| Variable | Default | Effect |
|---|---|---|
| `SECURE_MODE` | *(unset)* | When set to a truthy value (`1`, `true`, `yes`, `on`), enables production security posture. |
| `DEV_LOCAL_UNSAFE` | *(unset)* | When set to a truthy value, explicitly opts into the insecure development posture. |

### Truthy values

Any of: `1`, `true`, `yes`, `on` (case-insensitive). Everything else is falsy.

### Mutual exclusion

```
SECURE_MODE=true  + DEV_LOCAL_UNSAFE=<unset>   → secure (production)
SECURE_MODE=<unset> + DEV_LOCAL_UNSAFE=true    → insecure (development)
SECURE_MODE=<unset> + DEV_LOCAL_UNSAFE=<unset> → secure (safe default)
SECURE_MODE=true  + DEV_LOCAL_UNSAFE=true       → refuse to start (conflict)
```

The safe-default rule: if neither flag is set, the server starts in secure mode. This prevents accidental exposure.

### Startup validation (in `main()`)

```python
_secure_mode, _dev_local_unsafe = _resolve_mode_flags()
if _secure_mode and _dev_local_unsafe:
    raise SystemExit(
        "SECURE_MODE and DEV_LOCAL_UNSAFE are mutually exclusive. "
        "Set one or neither (neither defaults to secure)."
    )
```

---

## 2. Environment Variable Handling in `server.py`

### New module-level constants (after existing `DOCKER_SOCK` / `GATEWAY_CONTAINER_NAME` block)

```python
def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_mode_flags() -> tuple[bool, bool]:
    secure = _is_truthy(os.environ.get("SECURE_MODE"))
    dev_unsafe = _is_truthy(os.environ.get("DEV_LOCAL_UNSAFE"))
    if secure and dev_unsafe:
        raise SystemExit(
            "SECURE_MODE and DEV_LOCAL_UNSAFE are mutually exclusive. "
            "Set one or neither (neither defaults to secure)."
        )
    # Default: secure when neither is set
    if not secure and not dev_unsafe:
        secure = True
    return secure, dev_unsafe


SECURE_MODE, DEV_LOCAL_UNSAFE = _resolve_mode_flags()
```

### Auth token for secure mode

In secure mode, mutating endpoints require a bearer token. The token is derived from the Hermes session token (scraped from the dashboard HTML, same mechanism already used by `_dashboard_session_token()`). The BFF reads it at startup and stores it in a module-level constant.

```python
def _require_auth_token() -> str:
    """Load or derive the auth token for secure mode."""
    token = os.environ.get("WORKFRAME_API_TOKEN", "").strip()
    if token:
        return token
    # Fallback: derive from Hermes dashboard session token
    dashboard_url = os.environ.get("HERMES_DASHBOARD_URL", "http://127.0.0.1:9119")
    return _dashboard_session_token(dashboard_url)


# Set at module level; only used when SECURE_MODE is True
AUTH_TOKEN: str = ""
if SECURE_MODE:
    try:
        AUTH_TOKEN = _require_auth_token()
    except Exception as exc:
        raise SystemExit(f"SECURE_MODE: failed to obtain auth token: {exc}")
```

---

## 3. How the Flag Controls Behavior

### 3a. CORS

**Current behavior (always):**
```python
self.send_header("Access-Control-Allow-Origin", "*")
```

**New behavior:**

| Mode | `Access-Control-Allow-Origin` | Preflight (`OPTIONS`) |
|---|---|---|
| `DEV_LOCAL_UNSAFE` | `*` (unchanged) | Not handled (browser handles it) |
| `SECURE_MODE` | `null` — omit the header entirely | Return `405` or handle with explicit origin whitelist |

In secure mode, the `_send()` method omits the CORS header entirely (browsers will block cross-origin requests, which is the desired behavior when the API is same-origin only). If the UI is served from a known origin, we can set it explicitly:

```python
CORS_ALLOW_ORIGIN = os.environ.get("CORS_ALLOW_ORIGIN", "").strip()
```

Implementation in `_send()`:

```python
def _send(self, code: int, body: bytes, content_type: str) -> None:
    self.send_response(code)
    self.send_header("Content-Type", content_type)
    self.send_header("Cache-Control", "no-store")
    if DEV_LOCAL_UNSAFE:
        self.send_header("Access-Control-Allow-Origin", "*")
    elif CORS_ALLOW_ORIGIN:
        self.send_header("Access-Control-Allow-Origin", CORS_ALLOW_ORIGIN)
    # In secure mode with no explicit origin: omit the header entirely
    self.end_headers()
    self.wfile.write(body)
```

For preflight `OPTIONS` requests (currently not handled — the server returns 405), in secure mode we add an explicit handler that returns the correct CORS headers only for allowed origins:

```python
def do_OPTIONS(self) -> None:  # noqa: N802
    if DEV_LOCAL_UNSAFE:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
    elif CORS_ALLOW_ORIGIN:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", CORS_ALLOW_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
    else:
        self.send_response(405)
        self.end_headers()
```

### 3b. Auth Requirements

**Read-only GET endpoints** (e.g., `/api/snapshot`, `/api/routes`, `/api/chat/messages`): remain unauthenticated in both modes. These are informational and don't mutate state or access sensitive surfaces.

**Mutating POST endpoints** (e.g., `/api/board`, `/api/content/save`, `/api/files/write`, `/api/chat/dispatch`, `/api/hermes/profiles/start`, `/api/hermes/profiles/stop`): require `Authorization: Bearer <token>` in secure mode.

**Docker-adjacent endpoints** (`/api/hermes/profiles/start|stop`): require auth in secure mode (see 3c).

Auth check helper:

```python
def _check_auth(self) -> bool:
    """Return True if auth is valid or not required."""
    if DEV_LOCAL_UNSAFE:
        return True
    auth_header = self.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and auth_header[7:] == AUTH_TOKEN:
        return True
    return False
```

Applied in `do_POST` at the top of each mutating handler:

```python
if not self._check_auth():
    return self._json(401, {"error": "unauthorized"})
```

### 3c. Docker Socket Access

The Docker socket is mounted into the `workframe-api` container at `/var/run/docker.sock` (see `docker-compose.yml` line 69). The server uses it via `_docker_request()` and `_docker_exec()` to manage profile gateways.

**In `SECURE_MODE`:** Docker socket access is gated. The `_docker_request()` function checks the flag and raises an error if secure mode is active:

```python
def _docker_request(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    if SECURE_MODE:
        raise RuntimeError("Docker socket access is disabled in SECURE_MODE")
    # ... existing implementation unchanged
```

This means the `/api/hermes/profiles/start` and `/api/hermes/profiles/stop` endpoints will return an error in secure mode. This is intentional: in production, gateway lifecycle should be managed by Docker Compose / orchestration, not by the BFF.

**In `DEV_LOCAL_UNSAFE`:** Docker socket access works as today (no change).

**Alternative (softer):** If we want Docker access in secure mode but gated behind auth, we can skip the `_docker_request` guard and rely solely on the auth check in `do_POST`. This is a design decision — the hard block is safer but less flexible.

**Recommendation:** Hard block in `_docker_request()` for now. If a use case emerges for Docker access in secure mode, we can relax it later.

---

## 4. Docker Compose Changes

### `docker-compose.yml` — `workframe-api` service

Add the `SECURE_MODE` environment variable. In development, set `DEV_LOCAL_UNSAFE=true`. In production, set `SECURE_MODE=true` or leave both unset (defaults to secure).

```yaml
  workframe-api:
    # ... existing config unchanged
    environment:
      - HERMES_DATA=/opt/data
      - WORKSPACE=/workspace
      - WORKFRAME_API_DATA_DIR=/app/data
      - BOARD_DB=/app/data/board.db
      - HOST=0.0.0.0
      - PORT=8080
      - WORKFRAME_NATIVE_PROFILE=workframe-agent
      - WORKFRAME_PROJECT=Workframe
      - HERMES_DASHBOARD_URL=http://dashboard:9119
      - HERMES_DASHBOARD_PUBLIC_URL=http://127.0.0.1:${WORKFRAME_UI_PORT}/hermes-dashboard
      - WORKFRAME_GATEWAY_CONTAINER=workframe-gateway
      # Security mode — set ONE of these, or neither (defaults to secure):
      - DEV_LOCAL_UNSAFE=true          # development only
      # - SECURE_MODE=true             # production
```

### `.env.example`

Add documentation for the new flags:

```bash
# Security mode for workframe-api container.
# Set ONE of the following, or leave both unset (defaults to secure):
#   DEV_LOCAL_UNSAFE=true  — open CORS, no auth, Docker socket accessible (development)
#   SECURE_MODE=true       — strict CORS, auth required, Docker socket blocked (production)
# SECURE_MODE=true
# DEV_LOCAL_UNSAFE=true
```

---

## 5. Files to Modify

| File | Change |
|---|---|
| `workframe-api/server.py` | Add `_is_truthy()`, `_resolve_mode_flags()`, `SECURE_MODE`/`DEV_LOCAL_UNSAFE` constants, `_check_auth()`, modify `_send()`, add `do_OPTIONS()`, guard `_docker_request()`, add auth checks to mutating POST handlers |
| `docker-compose.yml` | Add `DEV_LOCAL_UNSAFE=true` or `SECURE_MODE=true` to `workframe-api` environment block |
| `.env.example` | Add documentation for the two flags |
| `mission-control/server.py` | Same changes (mirrors workframe-api; both servers should have identical security posture) |

---

## 6. Verification Steps

### Test 1: Default (neither flag set) → secure mode
```bash
cd /workspace
docker compose up workframe-api
# Server should start in secure mode
# Verify: POST /api/board without Authorization → 401
# Verify: GET /api/snapshot without Authorization → 200 (read-only)
# Verify: No Access-Control-Allow-Origin header on responses
```

### Test 2: DEV_LOCAL_UNSAFE=true → open mode
```bash
DEV_LOCAL_UNSAFE=true docker compose up workframe-api
# Server should start in dev mode
# Verify: POST /api/board without Authorization → 201 (works)
# Verify: Access-Control-Allow-Origin: * present
# Verify: Docker socket endpoints work
```

### Test 3: Both flags set → refuse to start
```bash
SECURE_MODE=true DEV_LOCAL_UNSAFE=true docker compose up workframe-api
# Server should exit with: "SECURE_MODE and DEV_LOCAL_UNSAFE are mutually exclusive"
```

### Test 4: SECURE_MODE=true with valid token
```bash
SECURE_MODE=true WORKFRAME_API_TOKEN=test-token docker compose up workframe-api
# Verify: POST /api/board with Authorization: Bearer test-token → 201
# Verify: POST /api/board with Authorization: Bearer wrong → 401
# Verify: POST /api/board without Authorization → 401
```

### Test 5: Docker socket blocked in secure mode
```bash
SECURE_MODE=true docker compose up workframe-api
# Verify: POST /api/hermes/profiles/start → 500 with "Docker socket access is disabled in SECURE_MODE"
```

---

## 7. Risks and Edge Cases

1. **Token leakage via environment**: `WORKFRAME_API_TOKEN` is set as an env var, visible in `docker inspect` and `/proc/<pid>/environ`. This is acceptable for a local-first tool but would need a secrets manager in a true production deployment.

2. **CORS preflight breakage**: The current server has no `do_OPTIONS` handler. Adding one in secure mode could break existing browser clients that rely on simple CORS (no preflight). Since secure mode is same-origin, this is unlikely to be an issue — but test with the actual UI.

3. **Docker socket mount still present**: Even when `_docker_request` is blocked, the socket is still mounted in the container. A determined attacker with container access could bypass the Python guard. For true hardening, remove the Docker socket mount entirely in secure mode (requires a second docker-compose profile or override file).

4. **Read-only endpoints leak data**: In secure mode, GET endpoints remain unauthenticated. If the API is exposed on a network, anyone can read session data, kanban state, etc. This is acceptable for the current threat model (localhost-only) but would need network-level protection (firewall, reverse proxy with auth) for broader exposure.

5. **Mission control vs workframe-api drift**: Both `mission-control/server.py` and `workframe-api/server.py` need the same changes. Consider extracting the security logic into a shared module (`workframe-api/security.py`) to prevent drift.

6. **Startup ordering**: The auth token is derived from the Hermes dashboard at startup. If the dashboard isn't ready when `workframe-api` starts, the server will exit. This is correct behavior — fail fast rather than start insecure.
