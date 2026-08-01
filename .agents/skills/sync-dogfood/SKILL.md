---
name: sync-dogfood
description: Synchronize canonical Workframe source into the installer package and validate it in the generated local Docker dogfood install. Use when UI or API changes need a browser-visible preview, installer-pack verification, wizard/chat sign-off, or a safe source-to-dogfood update.
---

# Sync dogfood

## Source boundary

Edit canonical source in the repository:

- `apps/web/src/` for the product UI;
- `services/workframe-api/` for the API;
- `services/workframe-supervisor/` for supervisor changes;
- `packages/create-workframe/` only for installer-owned code and templates.

Do not treat `MyBusiness`, generated installs, or copied package mirrors as source truth.

## Full sign-off loop

Use the full loop when proving a release candidate or when the user asks for install sign-off:

```text
edit source
  -> build web when UI changed
  -> sync API/supervisor into create-workframe
  -> bundle UI into create-workframe
  -> run install-gate
  -> reset generated dogfood
  -> complete browser wizard and first chat
  -> record release evidence
```

From the repository root, run:

```powershell
.\scripts\workframe\sign-off-install.ps1
```

This runs the quick install gate and then `reset-dogfood-docker.ps1 -Confirm`. The reset creates a generated install through `npx create-workframe` using the local package path, not an arbitrary manual copy.

## Pre-publish gate without reset

Use this when only the source-to-package artifact must be checked:

```powershell
.\scripts\workframe\install-gate.ps1
```

The gate builds the web app, runs `sync-canonical-to-package.mjs`, bundles the UI, runs API and scaffold tests, creates an npm tarball in `.install-gate/`, checks required installer files and shell line endings, and runs package-install evidence.

Use the focused commands only when the task scope permits:

```powershell
pnpm build:web
node packages/create-workframe/scripts/sync-canonical-to-package.mjs
node packages/create-workframe/scripts/bundle-workframe-ui.mjs
```

Run the web build and UI bundle for UI changes. Run canonical sync for API or supervisor changes. Rebuild affected Docker images before checking a live stack when image contents changed.

## Local dogfood reset

Preview destructive effects first:

```powershell
.\scripts\workframe\reset-dogfood-docker.ps1 -WhatIf
```

Execute only with explicit confirmation:

```powershell
.\scripts\workframe\reset-dogfood-docker.ps1 -Confirm
```

The reset removes the prior generated install, stops legacy compose at the documented slot, and creates a fresh Docker install. It must not touch the repository source or the host Hermes directory. Finish setup in the browser and send a test chat.

Verify the generated install with bounded health checks and browser exercise, for example:

```powershell
Invoke-RestMethod http://127.0.0.1:19120/api/health
```

Use `127.0.0.1`, not `localhost`, when checking the local session-bearing UI.

## Routine update versus reset

Do not reset the install for every routine change. After a published version exists, use the in-app Admin -> Updates path for normal updates; it preserves generated users, files, environment, vault state, and gateway profiles.

Reserve wipe-and-reinstall for first boot, corrupted state, disaster recovery, or release sign-off. A green running stack is evidence only; it does not replace pack, install, wizard, chat, and release-gate evidence.

## Hard boundaries

- Never use `robocopy /MIR` or broad tree copies into the generated install.
- Never edit installer mirrors first and call that a source change.
- Do not use `scp`, `rsync`, or manual `docker cp` as the dogfood sync path.
- Do not touch host Hermes state.
- Do not mark the dogfood gate passed without completing the browser wizard and first chat, or without valid current-version evidence.
- Do not publish or update a VPS unless the user explicitly asks for that separate action; dogfood sync is local validation.

## Report completion

State the source files changed, sync/build commands run, install or update mode used, health checks, browser checks, evidence result, and any remaining blocker. Keep generated-install paths and credentials out of public notes unless they are already approved public documentation.
