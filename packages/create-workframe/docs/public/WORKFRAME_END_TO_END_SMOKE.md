# Workframe End-to-End Smoke

Use this checklist after major changes to scaffold, transport, or gateway lifecycle.

## 1. Scaffold

Generate a fresh project:

```bash
node packages/create-workframe/scripts/new-project.mjs SmokeDemo --out /tmp --force
```

Expected:

- `workframe-manifest.json` has:
  - `"pack": "native"` by default
  - one installed bootstrap profile: `{slug}-agent`
  - specialist catalog entries present
- `Workframe/docker-compose.yml` has exactly 4 services:
  - `gateway`
  - `dashboard`
  - `workframe-api`
  - `workframe`
- no per-profile dashboard services

## 2. Native bootstrap

Run Hermes setup, then:

```bash
./Workframe/scripts/bootstrap-native.sh
```

Expected:

- `Agents/SOUL.md` exists
- `Agents/profiles/{slug}-agent/SOUL.md` exists
- `Agents/profiles/{slug}-agent/profile.yaml` exists
- `terminal.cwd` resolves to `/workspace`

## 3. Runtime

Start the stack:

```bash
docker compose up -d
```

Expected:

- UI loads
- `/hermes-dashboard/` loads
- workframe-api responds
- `.env` exposes `WORKFRAME_API_PORT`
- `workframe doctor` passes

## 4. Native-first topology

Confirm:

- native gateway owns Discord / Telegram
- specialist profiles are not preinstalled by default
- specialist catalog is still available through seeds and lifecycle scripts

## 5. Specialist lifecycle

Create and delete a child agent:

```bash
node Workframe/scripts/agent-lifecycle.mjs create --slug qa-proof --display-name "QA Proof" --role "Smoke-test child"
node Workframe/scripts/agent-lifecycle.mjs delete --slug qa-proof
```

Expected:

- create assigns avatar and writes SOUL/profile metadata
- delete removes runtime profile and registry record

## 6. Session routing

Create lane sessions through workframe-api:

- same profile + different `client_id` => different sessions
- same profile + same `client_id` => same persisted session
- duplicate titles auto-suffix:
  - `Session with Dev`
  - `Session with Dev (2)`

## 7. Specialist transport

Send a message through:

```text
/api/hermes/profiles/{profile}/messages
```

Expected:

- reply comes from the real specialist profile
- refresh shows the same persisted turn
- no false “failed send, later appears on refresh” behavior

## 8. Child gateway hygiene

When a specialist API gateway starts:

- no Discord token ownership error
- no Telegram token ownership error
- child run script unsets messaging env vars before `gateway run`

## 9. Kanban

Create a proof task and dispatch:

```bash
hermes kanban create ...
hermes kanban dispatch --json
```

Expected:

- `created`
- `claimed`
- `spawned`
- `completed`

## 10. Final pass

Run:

```bash
npx workframe doctor
node packages/create-workframe/scripts/test-scaffold.mjs
```

Expected:

- doctor validates native-first layout and live compose topology
- scaffold tests pass for `native`, `core`, `product`, `engineering`, and `vanilla`
