# Workframe End-to-End Smoke

Use this checklist inside a **generated project** after scaffold or transport changes.

For monorepo contributor checks (scaffold regression, install gate, public deploy preflight), see the repository [contributing guide](https://github.com/npx-workframe/workframe/blob/main/docs/public/contributing.md).

## 1. Scaffold

```bash
npx create-workframe@0.1.3 SmokeDemo
cd SmokeDemo
```

Expected:

- `workframe-manifest.json`: `"pack": "native"`, one bootstrap profile `{slug}-agent`
- `docker-compose.yml`: five services — `gateway`, `dashboard`, `workframe-api`, `workframe-supervisor`, `workframe`

## 2. Native bootstrap

After Hermes setup:

```bash
./scripts/bootstrap-native.sh
./scripts/verify-bootstrap.sh
```

Expected: `Agents/SOUL.md`, `Agents/profiles/{slug}-agent/SOUL.md`, `terminal.cwd` → `/workspace`.

## 3. Runtime

```bash
docker compose up -d
node scripts/workframe.mjs doctor
```

Expected: UI loads, dashboard loads, API health OK.

## 4. Session routing

Same profile + different browser tab (`client_id`) → different sessions. Same tab → persisted session.

## 5. Specialist lifecycle

```bash
node scripts/agent-lifecycle.mjs create --slug qa-proof --display-name "QA Proof" --role "Smoke-test child"
node scripts/agent-lifecycle.mjs delete --slug qa-proof
```

## 6. Final pass

```bash
node scripts/workframe.mjs doctor
```

Expected: native-first layout and compose topology validate.
