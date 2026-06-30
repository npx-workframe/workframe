# VPS Deployment

**Target product version:** see [docs/VERSION.md](../docs/VERSION.md). Deploy from git clone + `pnpm build:web` (or `npx create-workframe` on the host).

Set `WORKFRAME_VPS_HOST` (e.g. `root@YOUR_VPS_HOST`) for remote deploy scripts. Optional local tunnel: `scripts/workframe/open-vps-tunnel.ps1`.

```text
/opt/workframe/repo
├─ services/workframe-api   (Docker build)
├─ apps/web/dist            (nginx UI mount — build locally or on VPS)
├─ runtime/Agents           → /opt/data   (not in git)
├─ runtime/Files            → /workspace  (not in git)
└─ infra/compose/workframe  (.env secrets — not in git)
```

## Auth model (GitHub ≠ npm)

| Surface | Credential | Notes |
|---------|------------|--------|
| **Private GitHub** | Read-only **deploy key** on the VPS | Repo stays private; VPS only needs `git clone` |
| **Your machine** | `git push` via your normal GitHub login | Never commit tokens; agents must not read `git credential` without you |
| **npm publish** (later) | `NPM_TOKEN` in CI or local `npm login` | Public package ≠ public GitHub; VPS does not need npm publish access |

## One-time: deploy key (manual — do this yourself)

On the VPS:

```bash
bash scripts/workframe/vps-setup-deploy-key.sh
# prints ~/.ssh/workframe_deploy.pub
```

In GitHub: **npx-workframe/workframe → Settings → Deploy keys → Add deploy key**

- Title: e.g. `workframe-vps-deploy-key`
- Key: paste the printed `ssh-ed25519 …` line
- **Allow write access:** off (read-only is enough)

Verify from the VPS:

```bash
GIT_SSH_COMMAND='ssh -i ~/.ssh/workframe_deploy -o IdentitiesOnly=yes' \
  git ls-remote git@github.com:npx-workframe/workframe.git HEAD
```

Do **not** give agents your GitHub PAT or run `git credential fill` to register keys for you.

## Deploy (preferred — git on VPS)

After deploy key is installed:

```bash
ssh root@YOUR_VPS
bash /opt/workframe/repo/scripts/workframe/vps-git-pull-deploy.sh
```

Shallow-clones `main`, preserves `runtime/`, `infra/compose/workframe/.env`, and `apps/web/dist`, then runs `vps-deploy.sh`.

`apps/web/dist` is **not in git**. Build before deploy:

```powershell
pnpm build:web
```

If `dist` is missing, nginx returns **403 Forbidden** (empty `/usr/share/nginx/html`).

First-time slot-2 ports on a host that still has slot-1 `.env`:

```bash
bash scripts/workframe/vps-slot2-migrate.sh
```

## Deploy (fallback — private repo, no git on server)

From a dev machine with the repo checked out:

```powershell
powershell -File scripts\workframe\vps-pull-deploy.ps1
```

Streams `git archive main` to the VPS (no GitHub credentials on the server). Same runtime / `.env` / `dist` preservation.

## Compose secrets

```bash
cd /opt/workframe/repo/infra/compose/workframe
cp .env.example .env   # first time only
# SECURE_MODE=true, WORKFRAME_SUPERVISOR_TOKEN, ZK_AUTH_*, SMTP_* — edit before production
# Public URL with untrusted users: WORKFRAME_DEPLOYMENT_MODE=public_multi_user — see PUBLIC_DEPLOY.md
# See docs/public/operations.md
bash ../../../scripts/workframe/vps-deploy.sh
```

Public multi-user checklist: `infra/compose/workframe/PUBLIC_DEPLOY.md`  
Preflight script: `bash scripts/workframe/verify-public-deploy.sh`

## Local tunnel smoke

```powershell
powershell -File scripts\workframe\open-vps-tunnel.ps1
# UI http://127.0.0.1:28644/  API http://127.0.0.1:29120/api/health
```

## npm publish (when ready)

- Publish `packages/create-workframe` from CI or your machine with `NPM_TOKEN`.
- GitHub can stay private; the published tarball is what users `npx create-workframe` installs.
- Rotate/revoke deploy keys and PATs independently of npm tokens.
