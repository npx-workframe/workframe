# Workframe Supervisor Service — Design Document

> **Implementation status (2026-06-20):** Supervisor ships in `infra/compose/workframe/docker-compose.yml` as `workframe-supervisor`. Required when `SECURE_MODE=true`. API delegates `_gateway_exec` and `_hermes_user_exec` via `POST /v1/gateway.exec` and `POST /v1/hermes.user_exec`. Operational summary: `RUNTIME_OPERATIONS.md`.

## Problem

The current Workframe operation model requires operators to exec into the gateway container or use the Hermes TUI for any runtime management: starting/stopping specialist gateways, checking profile status, inspecting containers, or restarting crashed services. This is slow, error-prone, and forces every operator to have shell access to the production Docker host.

The browser-based Workframe UI (workframe-api) already has one foot in the Docker world — it mounts `/var/run/docker.sock` to exec `hermes gateway start/stop/status` and `hermes profile` commands into the gateway container. But this socket access is implicit, unauthenticated from the API layer's perspective, and gives the workframe-api container unconstrained exec access inside `workframe-gateway`.

The **workframe-supervisor** replaces this ad-hoc Docker socket access with a single-purpose, token-authenticated HTTP service that owns all Docker operations and exposes them through well-defined API endpoints.

---

## Design Goals

1. **Replace Docker socket access** — workframe-api no longer mounts `/var/run/docker.sock`. The supervisor is the only container that holds the socket.
2. **Token authentication** — All supervisor endpoints require `WORKFRAME_SUPERVISOR_TOKEN`. No unauthenticated management operations.
3. **Narrow scope** — The supervisor does only profile lifecycle and Docker introspection. It does not serve files, run chat, or manage the UI.
4. **Compose-native** — Runs as a fifth service in `docker-compose.yml`, same network, same restart policy.
5. **Hermes-native calls** — Under the hood, the supervisor execs `hermes -p <profile> gateway <action>` inside the gateway container, exactly as workframe-api does today. Same containers, same binaries, same config. We are adding an auth layer and removing the socket, not reimplementing lifecycle logic.

---

## Service Placement

### Before (current)

```
workframe-api  --mounts-->  /var/run/docker.sock
                            |
                            v
                     exec into workframe-gateway
                     (hermes gateway start/stop/status)
```

### After (with supervisor)

```
workframe-api  --HTTP+token-->  workframe-supervisor  --mounts--> /var/run/docker.sock
                                      |                                     |
                                      v                                     v
                                auth check                           exec into gateway
                                rate limit                           (same hermes CLI)
                                input validation
```

**Key change:** `workframe-api` drops its Docker socket mount entirely. The supervisor is the only socket holder.

---

## Docker Compose Addition

```yaml
  workframe-supervisor:
    image: python:3-alpine
    container_name: workframe-supervisor
    restart: unless-stopped
    working_dir: /app
    command: ["python3", "server.py"]
    labels:
      com.workframe.project: "Workframe"
      com.workframe.role: supervisor
    volumes:
      - ./workframe-supervisor/server.py:/app/server.py:ro
      - ./workframe-supervisor/data:/app/data
      - /var/run/docker.sock:/var/run/docker.sock
      - ../Agents:/opt/data:ro
      - .:/workspace:ro
    environment:
      - HERMES_DATA=/opt/data
      - WORKSPACE=/workspace
      - SUPERVISOR_TOKEN=${WORKFRAME_SUPERVISOR_TOKEN}
      - WORKFRAME_GATEWAY_CONTAINER=workframe-gateway
      - HOST=0.0.0.0
      - PORT=8090
    depends_on:
      - gateway
    networks:
      - workframe-net
```

### Key differences from workframe-api

| Aspect | workframe-api | workframe-supervisor |
|--------|--------------|---------------------|
| Docker socket | Mounted (being removed) | Mounted (sole holder) |
| Auth | None for profile ops | `WORKFRAME_SUPERVISOR_TOKEN` required |
| File serving | Yes (`/workspace`, `/app/public`) | No — management only |
| Chat proxy | Yes (to gateway) | No |
| Profile lifecycle | Yes (via `_docker_exec`) | Yes (replaces it) |
| Port | 8080 (workframe-api) | 8090 (supervisor) |

---

## Authentication

### Token: `WORKFRAME_SUPERVISOR_TOKEN`

- Set in `.env` as `WORKFRAME_SUPERVISOR_TOKEN` (generated at setup time, e.g. `openssl rand -hex 32`).
- Read by compose into the container env as `SUPERVISOR_TOKEN`.
- Every supervisor endpoint checks the token. No token = 401.

### Token delivery

Clients send the token as a bearer token:

```
Authorization: Bearer <token>
```

### Request validation

- Token must match `SUPERVISOR_TOKEN` env var exactly (constant-time comparison).
- All endpoints also require `Content-Type: application/json` for POST bodies.
- Profile names are validated against the known-routes allowlist (same `resolve_validated_profile` logic as workframe-api today).

### Token generation (setup-time)

```bash
# scripts/setup-supervisor.sh (new)
TOKEN=$(openssl rand -hex 32)
echo "WORKFRAME_SUPERVISOR_TOKEN=${TOKEN}" >> ./.env
echo "Supervisor token generated. Store it securely."
```

---

## API Endpoints

All endpoints return JSON. All errors return `{"ok": false, "error": "<message>"}` with appropriate HTTP status.

### 1. `GET /health`

No auth required. Used by compose healthchecks and monitoring.

**Response:**
```json
{
  "ok": true,
  "service": "workframe-supervisor",
  "version": "0.1.0"
}
```

### 2. `GET /v1/profile.status?profile=<name>`

Return the gateway status for a profile: state, PID, uptime, connected platforms.

**Request:**
- Query param: `profile` (required) — the Hermes profile slug.
- Auth: Bearer token.

**Response:**
```json
{
  "ok": true,
  "profile": "architect",
  "state": "running",
  "pid": 4821,
  "uptime_seconds": 3600,
  "uptime": "1h 0m",
  "platforms": {},
  "api_port": 18639,
  "updated_at": "2026-06-13T14:30:00+00:00"
}
```

**Implementation:** Reads `gateway_state.json` from the profile directory (same as `gateway_data()` in workframe-api today). Falls back to checking the gateway process via Docker exec if `gateway_state.json` is stale.

### 3. `POST /v1/profile.start`

Start the gateway for a specialist profile. No-op if already running.

**Request body:**
```json
{
  "profile": "architect"
}
```

**Response (started):**
```json
{
  "ok": true,
  "profile": "architect",
  "action": "start",
  "state": "started",
  "api_port": 18639
}
```

**Response (already running):**
```json
{
  "ok": true,
  "profile": "architect",
  "action": "start",
  "state": "running",
  "api_port": 18639,
  "detail": "already running"
}
```

**Implementation steps (matching `profile_gateway_lifecycle("start")`):**
1. Resolve profile, validate against routes allowlist.
2. Configure the profile's `config.yaml` for API-only mode (disable Discord/Telegram/Slack/WhatsApp, enable `api_server` on the stable port).
3. Patch the gateway run script to inject env-unset for platform tokens.
4. Exec `hermes -p <profile> gateway start` inside the gateway container.
5. Wait for the API health check on the profile port (poll `/v1/health` up to 10s).

### 4. `POST /v1/profile.stop`

Stop the gateway for a specialist profile. Cannot stop the native (primary) profile.

**Request body:**
```json
{
  "profile": "architect"
}
```

**Response:**
```json
{
  "ok": true,
  "profile": "architect",
  "action": "stop",
  "state": "stopped"
}
```

**Errors:**
- 400 if profile is the primary/native profile.
- 400 if profile is not running.

**Implementation:** Exec `hermes -p <profile> gateway stop` inside the gateway container, then verify the process exited.

### 5. `POST /v1/profile.disable`

Stop the gateway AND disable the profile's platforms (set all platform configs to `enabled: false`). A disabled profile won't auto-restart on the next compose up.

**Request body:**
```json
{
  "profile": "architect"
}
```

**Response:**
```json
{
  "ok": true,
  "profile": "architect",
  "action": "disable",
  "state": "disabled"
}
```

**Implementation:**
1. Call `profile.stop` (exec `hermes gateway stop`).
2. Write the profile's `config.yaml` to set all platforms to `enabled: false`.
3. Write a marker file `profiles/<name>/.disabled`.

**Note:** This is distinct from `stop` — stop is temporary. Disable survives container restarts. To re-enable, use `profile.start` (which re-enables the platforms).

### 6. `GET /v1/stack.status`

Return the status of the entire compose stack: all containers, their state, and per-profile gateway health.

**Response:**
```json
{
  "ok": true,
  "containers": [
    {
      "name": "workframe-gateway",
      "image": "nousresearch/hermes-agent:latest",
      "state": "running",
      "status": "Up 2 hours",
      "ports": ["127.0.0.1:18972->8642/tcp"]
    },
    {
      "name": "workframe-api",
      "image": "python:3-alpine",
      "state": "running",
      "status": "Up 2 hours"
    }
  ],
  "profiles": [
    {
      "profile": "workframe-agent",
      "native": true,
      "state": "running",
      "api_port": 8642
    },
    {
      "profile": "architect",
      "native": false,
      "state": "stopped",
      "api_port": 18639
    }
  ],
  "generated_at": "2026-06-13T14:30:00+00:00"
}
```

**Implementation:**
1. Call `GET /containers/json` on the Docker socket to list all containers.
2. For each known profile (from routes.json), check `gateway_state.json` or the API health endpoint.
3. Combine into one response.

---

## How It Replaces Docker Socket Access from the Browser

### Current flow (workframe-api with socket)

```
Browser  -->  POST /api/hermes/profiles/start  -->  workframe-api
                                                        |
                                                        v
                                                   _docker_exec("workframe-gateway",
                                                     ["hermes", "-p", "architect", "gateway", "start"])
                                                        |
                                                   (via mounted /var/run/docker.sock)
```

Problem: workframe-api has raw exec access inside the gateway container. Any bug or injection in workframe-api becomes a container escape. The socket mount also means workframe-api implicitly trusts all callers (no auth on internal endpoints).

### New flow (supervisor replaces socket)

```
Browser  -->  POST /api/supervisor/v1/profile.start  -->  workframe-api  (BFF, no socket)
  [Authorization: Bearer <token>]                           |
                                                            v
                                                      POST /v1/profile.start  -->  workframe-supervisor
                                                      [Authorization: Bearer <token>]       |
                                                                                           v
                                                                                    token check
                                                                                    profile validation
                                                                                    _docker_exec(...)
                                                                                    (via mounted socket)
```

**What changes:**
1. workframe-api drops `/var/run/docker.sock` from its compose volume mounts.
2. workframe-api's profile lifecycle endpoints become thin HTTP proxies to the supervisor (forwarding the bearer token).
3. The supervisor is the only service that holds the socket — reduced attack surface.
4. Every management call requires `WORKFRAME_SUPERVISOR_TOKEN` — even from the UI's BFF.
5. The supervisor runs read-only for `/opt/data` and `/workspace` — it can inspect profiles and gateway_state but cannot write project work artifacts.

---

## Migration Path

### Phase 1 — Supervisor sidecar (this sprint)

1. Create `workframe-supervisor/server.py` (new file, ~400 lines).
2. Add `workframe-supervisor` service to `docker-compose.yml`.
3. Generate `.env` token entry.
4. Verify: `curl -H "Authorization: Bearer $TOKEN" http://localhost:8090/health` → 200.
5. Verify: supervisor can start/stop specialist profiles.

### Phase 2 — workframe-api adapter (next sprint)

1. Add proxy endpoints to `workframe-api/server.py`:
   - `POST /api/supervisor/profile.start` → proxies to supervisor
   - `POST /api/supervisor/profile.stop` → proxies to supervisor
   - (etc.)
2. These endpoints read `WORKFRAME_SUPERVISOR_TOKEN` from env or `.env` and forward it.
3. Keep the existing `/api/hermes/profiles/start|stop|status` endpoints as deprecated aliases.

### Phase 3 — Remove socket from workframe-api (next sprint)

1. Validate that no workframe-api code path touches `_docker_exec` or `_docker_request` directly.
2. Remove `- /var/run/docker.sock:/var/run/docker.sock` from workframe-api compose volumes.
3. Remove `DOCKER_SOCK` and `GATEWAY_CONTAINER_NAME` env vars from workframe-api.
4. Remove the socket-dependent helper functions from workframe-api (or mark them as dead code).

---

## Files to Create or Modify

### New files

| File | Purpose |
|------|---------|
| `workframe-supervisor/server.py` | Supervisor service — token auth, Docker exec, profile lifecycle |
| `scripts/setup-supervisor.sh` | Generate `WORKFRAME_SUPERVISOR_TOKEN` and append to `.env` |
| `scripts/generate-supervisor-token.ps1` | Windows equivalent |
| `workframe-supervisor/tests/test_supervisor.py` | Unit tests for auth, input validation |

### Modified files

| File | Change |
|------|--------|
| `docker-compose.yml` | Add `workframe-supervisor` service |
| `.env` / `.env.example` | Add `WORKFRAME_SUPERVISOR_TOKEN=` entry (blank in example, generated at setup) |
| `workframe-api/server.py` | Phase 2: Add proxy endpoints; Phase 3: Remove socket mount code |

---

## Verification Steps

### 1. Supervisor starts and healthcheck passes

```bash
docker compose up -d workframe-supervisor
sleep 5
curl http://localhost:8090/health
# Expected: {"ok": true, "service": "workframe-supervisor", "version": "0.1.0"}
```

### 2. Token enforcement works

```bash
# No token → 401
curl http://localhost:8090/v1/profile.status?profile=architect
# Expected: {"ok": false, "error": "unauthorized"}

# Wrong token → 401
curl -H "Authorization: Bearer ${INVALID_EXAMPLE_TOKEN}" http://localhost:8090/v1/profile.status?profile=architect
# Expected: {"ok": false, "error": "unauthorized"}

# Correct token → 200
curl -H "Authorization: Bearer $TOKEN" http://localhost:8090/v1/profile.status?profile=architect
# Expected: {ok: true, profile: architect, state: ...}
```

### 3. Profile lifecycle works

```bash
# Stop architect
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"profile":"architect"}' http://localhost:8090/v1/profile.stop

# Verify stopped
curl -H "Authorization: Bearer $TOKEN" http://localhost:8090/v1/profile.status?profile=architect
# Expected: state: stopped

# Start architect
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"profile":"architect"}' http://localhost:8090/v1/profile.start

# Verify running
curl -H "Authorization: Bearer $TOKEN" http://localhost:8090/v1/profile.status?profile=architect
# Expected: state: running
```

### 4. Stack status works

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8090/v1/stack.status | jq .
# Expected: full compose stack + all profiles
```

### 5. Native profile cannot be stopped

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"profile":"workframe-agent"}' http://localhost:8090/v1/profile.stop
# Expected: 400 {"ok": false, "error": "cannot stop the native profile"}
```

### 6. workframe-api socket removed (Phase 3)

```bash
# Verify workframe-api container has no Docker socket
docker exec workframe-api ls /var/run/docker.sock 2>&1
# Expected: No such file or directory
```

---

## Risks and Edge Cases

### 1. Token leakage

If `WORKFRAME_SUPERVISOR_TOKEN` is logged, committed to git, or exposed in browser devtools, an attacker can control the compose stack. Mitigations:
- Add `WORKFRAME_SUPERVISOR_TOKEN` to `.gitignore` (if not already).
- Never log the token in server code.
- The supervisor strips the `Authorization` header from any error responses.
- Token rotation: change `.env` value and `docker compose up -d workframe-supervisor`.

### 2. Supervisor single point of failure

If the supervisor container is down, management operations fail. Mitigation:
- `restart: unless-stopped` in compose.
- The Hermes TUI (`docker exec workframe-gateway hermes ...`) remains a fallback — Docker socket access via `docker exec` on the host still works for operators with host access.

### 3. Stale gateway_state.json

If the gateway process crashes without cleaning up `gateway_state.json`, `profile.status` reports stale state. Mitigation:
- The supervisor double-checks: if the PID in `gateway_state.json` is not running, it reports `state: crashed` and cleans the file.

### 4. Race conditions on start/stop

Concurrent `start` and `stop` for the same profile could leave the gateway in an inconsistent state. Mitigation:
- Use a per-profile threading lock in the supervisor.
- Check current state before acting (no double-start, no stop-if-not-running).

### 5. Specialist profile not configured for API mode

Before starting a specialist, `_configure_profile_api` must set `api_server.enabled: true` and disable all messaging platforms. If this step fails (e.g. malformed `config.yaml`), the supervisor returns 500 with the error and the profile remains stopped. This is the same logic as workframe-api's `_configure_profile_api` today — we are reusing the same approach.

### 6. Port collision

The stable port hash (`18610 + (sum(ord(c)) % 100)`) could theoretically collide for two profiles. In practice, profile names differ enough. If it happens, the `hermes gateway start` will fail with a port-in-use error, which the supervisor surfaces to the caller.

---

## Out of Scope

- The supervisor does **not** manage Workframe UI's file operations, chat proxy, or session routing. Those stay in workframe-api.
- The supervisor does **not** create or delete profiles. Profile creation stays in workframe-api's `POST /api/hermes/profiles/create` and `profile_delete()`.
- The supervisor does **not** manage the gateway or dashboard containers themselves. Only Hermes profile gateways.
- The supervisor is **not** a general-purpose Docker management API. It only runs `hermes` commands and reads `gateway_state.json`. No arbitrary container create/destroy.
