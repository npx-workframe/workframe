# Workframe End-to-End Smoke

Use this checklist inside a **generated project** after scaffold or transport changes.

For full contributor smoke tests (monorepo, pytest, public deploy preflight), see the repository [contributing guide](https://github.com/npx-workframe/workframe/blob/main/docs/public/contributing.md).

## 1. Scaffold

```bash
npx create-workframe@0.1.2 SmokeDemo
cd SmokeDemo
```

Expected:

- `workframe-manifest.json`: `"pack": "native"`, one bootstrap profile `{slug}-agent`
- Four compose services: `gateway`, `dashboard`, `workframe-api`, `workframe`

## 2. Native bootstrap

After Hermes setup:

```bash
./Workframe/scripts/bootstrap-native.sh
```

Expected: `Agents/SOUL.md`, `Agents/profiles/{slug}-agent/SOUL.md`, `terminal.cwd` → `/workspace`.

## 3. Runtime

```bash
docker compose up -d
npx workframe doctor
```

Expected: UI loads, dashboard loads, API health OK.

## 4. Session routing

Same profile + different browser tab (`client_id`) → different sessions. Same tab → persisted session.

## 5. Specialist lifecycle

```bash
node Workframe/scripts/agent-lifecycle.mjs create --slug qa-proof --display-name "QA Proof" --role "Smoke-test child"
node Workframe/scripts/agent-lifecycle.mjs delete --slug qa-proof
```

## 6. Final pass

```bash
npx workframe doctor
```

Expected: native-first layout and compose topology validate.
