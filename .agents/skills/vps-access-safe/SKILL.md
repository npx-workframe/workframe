---
name: vps-access-safe
description: Safely inspect and access self-hosted VPS deployments over SSH without exposing secrets, personal data, host identity, or tenant details. Use when checking SSH connectivity, inventorying remote Docker or Compose deployments, verifying service health, opening tunnels, or documenting a repeatable VPS access path for public distribution.
---

# Safe VPS access

## Purpose

Use SSH for controlled, read-only inspection first. Keep host-specific values in local operator configuration and use placeholders in public documentation. Treat deployment directories as runtime state, not as source truth.

## Safety boundary

Never print, copy, commit, or place in a public skill:

- private keys, key contents, tokens, passwords, cookies, OTPs, or `.env` values;
- SSH usernames, hostnames, IP addresses, domains, tenant names, project names, or personal filesystem paths;
- Docker environment values, secret mounts, raw logs, database rows, email addresses, or user IDs;
- full `ssh -G`, `docker inspect`, `docker compose config`, or process-environment output.

Redact values at collection time. Report only booleans, counts, exit codes, service-state classes, and generic ordinal labels.

## Resolve and test SSH

Use an operator-supplied SSH alias. Do not discover or print private key material.

```powershell
$alias = '<ssh-alias>'
ssh -G -o BatchMode=yes $alias 2>$null |
  Where-Object { $_ -match '^(user|hostname|port) ' } |
  ForEach-Object { ($_ -split '\s+', 3)[0] + ' [redacted]' }

ssh -o BatchMode=yes -o ConnectTimeout=8 $alias true 1>$null 2>$null
if ($LASTEXITCODE -eq 0) { 'SSH_CONNECT_OK' } else { "SSH_CONNECT_FAILED_EXIT_$LASTEXITCODE" }
```

Use `BatchMode=yes` so the agent cannot wait for an interactive password or silently request a key passphrase. Treat exit 255 as an access failure until the operator fixes the local SSH configuration or network path.

## Read-only deployment inventory

Run a narrow remote probe. Replace the root with a documented deployment root; never scan the entire server filesystem.

```bash
set -eu
root=/opt/<deployment-root>
if [ -d "$root" ]; then
  printf 'ROOT_PRESENT\n'
  printf 'INSTALL_DIRS=%s\n' "$(find "$root" -mindepth 1 -maxdepth 1 -type d | wc -l)"
  printf 'COMPOSE_FILES=%s\n' "$(find "$root" -mindepth 2 -maxdepth 3 -name docker-compose.yml -type f | wc -l)"
  printf 'MANIFESTS=%s\n' "$(find "$root" -mindepth 2 -maxdepth 3 -name manifest.json -type f | wc -l)"
else
  printf 'ROOT_ABSENT\n'
fi
```

For Docker health, return counts only:

```bash
printf 'DOCKER_PRESENT\n'
printf 'RUNNING_CONTAINERS=%s\n' "$(docker ps -q | wc -l)"
printf 'TOTAL_CONTAINERS=%s\n' "$(docker ps -aq | wc -l)"
```

For each documented Compose file, report `DEPLOYMENT_1_RUNNING=... TOTAL=...`. Do not print Compose project names or service names unless the operator explicitly needs a private diagnostic.

## Health verification

Prefer a documented health endpoint or Compose state summary. Use a bounded timeout and suppress response bodies when they may contain user data.

```bash
curl --fail --silent --show-error --max-time 8 \
  -o /dev/null -w 'HTTP_STATUS=%{http_code}\n' \
  'https://<public-host>/<health-path>'
```

Do not treat an HTTP 200 response alone as release proof. Pair it with the deployment's documented evidence: version or manifest identity, required services running, and an approved smoke test.

## SSH tunnels

Use a documented tunnel script or an explicit local-to-loopback port map. Bind local listeners to `127.0.0.1`, enable keepalives, and fail if forwarding cannot be established.

```powershell
ssh -N -o BatchMode=yes -o ExitOnForwardFailure=yes `
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 `
  -L 127.0.0.1:<local-port>:127.0.0.1:<remote-port> `
  <ssh-alias>
```

Do not expose forwarded ports on `0.0.0.0`. Record tunnel state as ports and health status, not host identity or credentials.

## Deployment changes

Do not mutate a VPS during an inventory or access check. For a requested deployment:

1. Read the project release routine and identify the approved artifact path.
2. Confirm the exact target, scope, and whether the action is disposable, staging, or production.
3. Prefer a signed or checksummed package and the documented reinstall/update command.
4. Keep secrets on the server; preserve them through the approved process without reading them.
5. Verify health, version identity, and rollback or recovery status.
6. Report the result with generic labels and redacted evidence.

Avoid ad hoc `scp`, `rsync`, `docker cp`, broad filesystem copies, or remote source checkouts as a substitute for the release path. Never delete a deployment directory without explicit approval and a confirmed recovery plan.

## Public documentation rule

Write examples with placeholders such as `<ssh-alias>`, `<deployment-root>`, `<public-host>`, `<health-path>`, and `<local-port>`. Keep the public skill reusable across providers and applications. Store host-specific procedures in a private operator-controlled document, not in the repository's public skill bundle.
