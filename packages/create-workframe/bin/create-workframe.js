#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import readline from 'node:readline/promises';
import { stdin as input, stdout as output } from 'node:process';
import { spawn, spawnSync } from 'node:child_process';
import { allocateInstall, envFileLines, portsForSlot, detectHermesHome, resolveDeployMode } from '../scripts/lib/install-identity.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PKG_ROOT = path.resolve(__dirname, '..');
const PKG_VERSION = JSON.parse(fs.readFileSync(path.join(PKG_ROOT, 'package.json'), 'utf8')).version;
const PACKS_PATH = path.join(PKG_ROOT, 'shared', 'WORKFRAME_AGENT_PACKS.json');
const PROFILES_DIR = path.join(PKG_ROOT, 'profiles');

const PROJECT_AGENT_SLOT = 'project-agent';
const NATIVE_SOUL_TEMPLATE = 'workframe-agent';
// Hermes HERMES_WRITE_SAFE_ROOT=/opt/data — bind Files under /opt/data/workspace; symlink /workspace.
const WORKSPACE_DATA_MOUNT = '/opt/data/workspace';

/** Bash: auto-apply public overlay when .env says public_multi_user. */
function composeUpBashBlock() {
  return `compose_file_args() {
  local args=(-f docker-compose.yml)
  if [ -f .env ] && grep -q '^WORKFRAME_DEPLOYMENT_MODE=public_multi_user' .env; then
    args+=(-f docker-compose.public.yml)
  fi
  printf '%s\\n' "\${args[@]}"
}
mapfile -t COMPOSE_FILE_ARGS < <(compose_file_args)
docker compose "\${COMPOSE_FILE_ARGS[@]}" up -d`;
}

/** PowerShell: public overlay + Windows host-bindings overlay. */
function composeUpPs1Block() {
  return `$composeArgs = @('-f', 'docker-compose.yml')
if ((Test-Path '.env') -and (Select-String -Path '.env' -Pattern '^WORKFRAME_DEPLOYMENT_MODE=public_multi_user' -Quiet)) {
  $composeArgs += '-f', 'docker-compose.public.yml'
}
if (Test-Path 'docker-compose.host-bindings.yml') {
  $composeArgs += '-f', 'docker-compose.host-bindings.yml'
}
docker compose @composeArgs up -d`;
}

const PROFILE_DESCRIPTIONS = {
  visionary: 'Clarifies product purpose, positioning, strategy, user value, and long-term alignment.',
  architect: 'Defines system design, technical boundaries, implementation plans, and code-review standards.',
  docs: 'Maintains AGENTS.md, .hermes.md, docs indexes, source-of-truth maps, and change summaries.',
  dev: 'Builds and modifies project files, scripts, tests, and implementation artifacts.',
  research: 'Performs technical research, market research, references, competitive analysis, and R&D notes.',
  designer: 'Handles UI direction, design docs, visual assets, image prompts, brand direction, and layout feedback.',
};

const GITIGNORE = `# Runtime state: do not commit instance data
Agents/
*.db
*.db-shm
*.db-wal
*.log
logs/
cache/
memories/
sessions/
kanban/
state/

# Bootstrap seed (optional cleanup after profile bootstrap)
scripts/seed/

# Secrets
.env
.env.local
.env.*.local
*.pem
*.key
*.p12
*.pfx
secrets/

# Build/tool noise
node_modules/
.venv/
__pycache__/
.pytest_cache/
.DS_Store
Thumbs.db
.vscode/
.idea/
`;

const DOCKERIGNORE = `.git
.gitignore
node_modules
.venv
__pycache__
.pytest_cache
*.pyc
*.pyo
*.db
*.db-shm
*.db-wal
*.log
.env
.env.*
Agents
cache
logs
memories
sessions
kanban
state
scripts/seed
`;

const VALID_PROJECT_NAME = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;

/** @deprecated use allocateInstall / portsForSlot */
function defaultPortsFromSlug(slug) {
  return portsForSlot(1);
}

function validateProjectName(name) {
  if (!name || typeof name !== 'string') throw new Error('Project name is required.');
  const trimmed = name.trim();
  if (!trimmed || trimmed === '.' || trimmed === '..') {
    throw new Error('Project name must be a folder basename, not "." or "..".');
  }
  if (trimmed.includes('/') || trimmed.includes('\\') || path.isAbsolute(trimmed)) {
    throw new Error('Project name must be a folder basename, not a path.');
  }
  if (!VALID_PROJECT_NAME.test(trimmed)) {
    throw new Error('Project name must start with a letter or digit and use only letters, digits, hyphens, and underscores.');
  }
  return trimmed;
}

function resolveProjectTarget(out, name) {
  const safeName = validateProjectName(name);
  const outRoot = path.resolve(out);
  const target = path.resolve(outRoot, safeName);
  const relative = path.relative(outRoot, target);
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error('Project path escapes the output directory.');
  }
  if (target === outRoot) {
    throw new Error('Refusing to scaffold directly into the output directory root.');
  }
  return { outRoot, target, name: safeName };
}

function envFileContent(install, { example = false, nativeProfile = '', deploy = 'docker', hermesHome = '' } = {}) {
  return envFileLines(install, { example, nativeProfile, deploy, hermesHome });
}

function routesJsonContent(profiles, nativeProfile, projectName) {
  const ctx = renderContext(projectName);
  const routes = profiles.map((profile) => {
    const isNative = profile === nativeProfile;
    const displayName = isNative
      ? ctx.nativeAgentName
      : profile.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    return {
      id: profile,
      surface: 'ui',
      channel_id: `ui://agent/${profile}`,
      profile,
      display_name: displayName,
      role: profileDescription(profile, projectName),
      mode: 'lane',
    };
  });
  return {
    version: 1,
    default_profile: nativeProfile,
    routes,
  };
}

function writeRoutesJsonBlockSh(profiles, nativeProfile, projectName) {
  const payload = JSON.stringify(routesJsonContent(profiles, nativeProfile, projectName), null, 2);
  return `mkdir -p "$ROOT/Agents/workframe"
cat > "$ROOT/Agents/workframe/routes.json" <<'WF_ROUTES_EOF'
${payload}
WF_ROUTES_EOF
`;
}

function writeRoutesJsonBlockPs1(profiles, nativeProfile, projectName) {
  const payload = JSON.stringify(routesJsonContent(profiles, nativeProfile, projectName), null, 2);
  const escaped = payload.replace(/'/g, "''");
  return `$routesDir = Join-Path $Root "..\\Agents\\workframe"
New-Item -ItemType Directory -Force -Path $routesDir | Out-Null
@'
${payload}
'@ | Set-Content -Path (Join-Path $routesDir "routes.json") -Encoding utf8
`;
}

function hermesServiceVolumesBlock(_hermesHome = '', { proxyToken = true } = {}) {
  // ponytail: gateway + API + supervisor must share install Agents/ — never host %LOCALAPPDATA%\\hermes
  const agentsMount = './Agents:/opt/data';
  const proxyVol = proxyToken ? '      - workframe-proxy-token:/run/workframe-proxy:ro\n' : '';
  return `    volumes:
      - ${agentsMount}
      - ./Files:${WORKSPACE_DATA_MOUNT}
${proxyVol}      - ./scripts:/opt/install/scripts:ro
      - ./docker/cont-init-workspace-link.sh:/etc/cont-init.d/03-workspace-link:ro`;
}

function gatewayProxyBootstrap(profileEsc) {
  const proxy =
    'if [ -z "$WORKFRAME_PROXY_TOKEN" ] && [ -f /run/workframe-proxy/token ]; then export WORKFRAME_PROXY_TOKEN="$(tr -d \'\\r\\n\' < /run/workframe-proxy/token)"; fi; ';
  const base = `mkdir -p /opt/data/Avatars; chmod 0777 /opt/data/Avatars 2>/dev/null || true; if [ -d /opt/data/profiles/${profileEsc} ]; then export HERMES_HOME=/opt/data/profiles/${profileEsc}; export HOME=/opt/data/profiles/${profileEsc}; cd /opt/data/profiles/${profileEsc}; PROFILE_FLAG='-p ${profileEsc}'; else export HERMES_HOME=/opt/data; export HOME=/opt/data; PROFILE_FLAG=''; fi; exec /opt/hermes/bin/hermes $PROFILE_FLAG gateway run --replace`;
  return proxy + base;
}

function dockerComposePublicYaml(docker) {
  return `# Public VPS overlay — API has no docker.sock or host project mounts.
# Usage: docker compose -f docker-compose.yml -f docker-compose.public.yml up -d
name: ${docker.stack}

services:
  workframe-api:
    volumes:
      - ./workframe-api/public:/app/public:ro
      - ./workframe-api:/app:ro
      - ./workframe-api/data:/app/data
      - ./Agents:/opt/data
      - ./Files:${WORKSPACE_DATA_MOUNT}
      - ./scripts:/opt/install/scripts:ro
      - workframe-proxy-token:/run/workframe-proxy
    environment:
      - WORKFRAME_COMPOSE_DIR=/compose
      - WORKFRAME_PROJECT_ROOT=/compose

  workframe-supervisor:
    volumes:
      - ./Agents:/opt/data
      - /var/run/docker.sock:/var/run/docker.sock
      - ./scripts:/opt/install/scripts:ro
      - .:/compose
    environment:
      - WORKFRAME_SCRIPTS_DIR=/opt/install/scripts
      - WORKFRAME_COMPOSE_DIR=/compose
      - WORKFRAME_PROJECT_ROOT=/compose
      - WORKFRAME_HOST_PROJECT_ROOT=/compose
      - WORKFRAME_SUPERVISOR_ALLOW_RAW_EXEC=0
`;
}

function nginxConfYaml() {
  return `map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Workframe API: snapshot-lite, files, chat history, profile routing
    location /api/ {
        proxy_pass http://workframe-api:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
        proxy_buffering off;
        proxy_cache off;
        add_header X-Accel-Buffering no;
    }

    # Hermes admin dashboard: ops, secrets, skills
    location /hermes-dashboard/ {
        proxy_pass http://dashboard:9119/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Prefix /hermes-dashboard;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~* \\.(js|css|svg|webmanifest|png|jpg|jpeg|gif|ico|woff2?)$ {
        expires 1h;
        add_header Cache-Control "public, immutable";
    }
}
`;
}

function contInitWorkspaceLinkSh() {
  return `#!/bin/with-contenv sh
# Runs as root during s6 cont-init — before Hermes gateway starts.
. /opt/install/scripts/bootstrap-workspace-link.sh
`;
}

function dashboardProxyConf() {
  return `server {
  listen 9119;
  server_name _;

  location / {
    proxy_pass http://gateway:9119/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
`;
}

function dockerComposeYaml(projectName, docker, nativeProfile, _packProfiles, installId = '', hermesHome = '') {
  const labelProject = projectName.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  const installIdEsc = String(installId || '').replace(/"/g, '\\"');
  const profileEsc = nativeProfile.replace(/"/g, '\\"');
  const gatewayCmd = gatewayProxyBootstrap(profileEsc);
  return `name: ${docker.stack}

services:
  gateway:
    image: ${docker.image}
    container_name: ${docker.gateway}
    restart: unless-stopped
    command: [ "sh", "-lc", '${gatewayCmd.replace(/'/g, "''")}' ]
    environment:
      - HERMES_DASHBOARD=1
      - HERMES_DASHBOARD_HOST=0.0.0.0
      - HERMES_DASHBOARD_PORT=9119
      - HERMES_DASHBOARD_TUI=1
      - HERMES_DASHBOARD_BASIC_AUTH_USERNAME=\${HERMES_DASHBOARD_BASIC_AUTH_USERNAME:-workframe}
      - HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=\${HERMES_DASHBOARD_BASIC_AUTH_PASSWORD:-workframe-local}
      - HERMES_DASHBOARD_BASIC_AUTH_SECRET=\${HERMES_DASHBOARD_BASIC_AUTH_SECRET:-workframe-local-dashboard-secret}
      - HERMES_DASHBOARD_PUBLIC_URL=\${APP_BASE_URL:-http://127.0.0.1:\${WORKFRAME_UI_PORT}/hermes-dashboard}
      - WORKFRAME_PROXY_TOKEN=\${WORKFRAME_PROXY_TOKEN:-}
    labels:
      com.workframe.project: "${labelProject}"
      com.workframe.role: gateway
    ports:
      - "127.0.0.1:\${WORKFRAME_GATEWAY_PORT}:8642"
${hermesServiceVolumesBlock(hermesHome)}
    networks:
      - ${docker.network}

  dashboard:
    image: nginx:alpine
    container_name: ${docker.dashboard}
    restart: unless-stopped
    command: ["nginx", "-g", "daemon off;"]
    labels:
      com.workframe.project: "${labelProject}"
      com.workframe.role: dashboard
    ports:
      - "127.0.0.1:\${WORKFRAME_DASHBOARD_PORT}:9119"
    volumes:
      - ./docker/dashboard-proxy.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - gateway
    networks:
      - ${docker.network}

  workframe-api:
    build:
      context: ./workframe-api
      dockerfile: Dockerfile
    image: ${docker.workframeApi}-image
    container_name: ${docker.workframeApi}
    restart: unless-stopped
    working_dir: /app
    command: ["sh", "-lc", ". /opt/install/scripts/bootstrap-workspace-link.sh; exec python3 server.py"]
    labels:
      com.workframe.project: "${labelProject}"
      com.workframe.role: workframe-api
    ports:
      - "127.0.0.1:\${WORKFRAME_API_PORT}:8080"
    volumes:
      - ./workframe-api/public:/app/public:ro
      - ./workframe-api:/app:ro
      - ./workframe-api/data:/app/data
      - ./Agents:/opt/data
      - ./Files:${WORKSPACE_DATA_MOUNT}
      - ./scripts:/opt/install/scripts:ro
      - .:/project:ro
      - .:/compose:ro
      - workframe-proxy-token:/run/workframe-proxy
    env_file:
      - ./.env
    environment:
      - HERMES_DATA=/opt/data
      - WORKSPACE=/workspace
      - WORKFRAME_API_DATA_DIR=/app/data
      - BOARD_DB=/app/data/board.db
      - HOST=0.0.0.0
      - PORT=8080
      - WORKFRAME_COMPOSE_DIR=/compose
      - WORKFRAME_PROJECT_ROOT=/compose
      - WORKFRAME_HOST_COMPOSE_DIR=\${WORKFRAME_HOST_COMPOSE_DIR:-}
      - WORKFRAME_HOST_PROJECT_ROOT=\${WORKFRAME_HOST_PROJECT_ROOT:-}
      - WORKFRAME_API_VERSION=${PKG_VERSION}
      - WORKFRAME_NATIVE_PROFILE=${profileEsc}
      - WORKFRAME_PROJECT=${labelProject}
      - WORKFRAME_INSTALL_ID=${installIdEsc}
      - WORKFRAME_SLOT=\${WORKFRAME_SLOT:-1}
      - HERMES_DASHBOARD_URL=http://dashboard:9119
      - HERMES_DASHBOARD_PUBLIC_URL=\${APP_BASE_URL:-http://127.0.0.1:\${WORKFRAME_UI_PORT}/hermes-dashboard}
      - HERMES_DASHBOARD_BASIC_AUTH_USERNAME=\${HERMES_DASHBOARD_BASIC_AUTH_USERNAME:-workframe}
      - HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=\${HERMES_DASHBOARD_BASIC_AUTH_PASSWORD:-workframe-local}
      - WORKFRAME_GATEWAY_CONTAINER=${docker.gateway}
      - WORKFRAME_SUPERVISOR_URL=http://workframe-supervisor:8090
      - WORKFRAME_SUPERVISOR_TOKEN=\${WORKFRAME_SUPERVISOR_TOKEN}
      - WORKFRAME_DEPLOYMENT_MODE=\${WORKFRAME_DEPLOYMENT_MODE:-trusted_team}
      - WORKFRAME_PROXY_TOKEN=\${WORKFRAME_PROXY_TOKEN:-}
    depends_on:
      - gateway
      - workframe-supervisor
    networks:
      - ${docker.network}
      - ${docker.controlNetwork}

  workframe-supervisor:
    build:
      context: ./workframe-supervisor
      dockerfile: Dockerfile
    image: ${docker.workframeSupervisor}-image
    container_name: ${docker.workframeSupervisor}
    restart: unless-stopped
    labels:
      com.workframe.project: "${labelProject}"
      com.workframe.role: supervisor
    ports:
      - "127.0.0.1:\${WORKFRAME_SUPERVISOR_PORT}:8090"
    volumes:
      - ./Agents:/opt/data
      - /var/run/docker.sock:/var/run/docker.sock
      - ./scripts:/opt/install/scripts:ro
      - .:/compose
    env_file:
      - ./.env
    environment:
      - HERMES_DATA=/opt/data
      - WORKFRAME_NATIVE_PROFILE=${profileEsc}
      - WORKFRAME_GATEWAY_CONTAINER=${docker.gateway}
      - HOST=0.0.0.0
      - PORT=8090
      - WORKFRAME_SUPERVISOR_TOKEN=\${WORKFRAME_SUPERVISOR_TOKEN}
      - WORKFRAME_DEPLOYMENT_MODE=\${WORKFRAME_DEPLOYMENT_MODE:-trusted_team}
      - WORKFRAME_SCRIPTS_DIR=/opt/install/scripts
      - WORKFRAME_COMPOSE_DIR=/compose
      - WORKFRAME_PROJECT_ROOT=/compose
    depends_on:
      - gateway
    networks:
      - ${docker.controlNetwork}

  workframe:
    image: nginx:alpine
    container_name: ${docker.workframe}
    restart: unless-stopped
    labels:
      com.workframe.project: "${labelProject}"
      com.workframe.role: ui
    ports:
      - "127.0.0.1:\${WORKFRAME_UI_PORT}:80"
    volumes:
      - \${WORKFRAME_UI_STATIC_DIR:-./workframe-ui/public}:/usr/share/nginx/html:ro
      - ./workframe-ui/docker/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    environment:
      - WORKFRAME_GATEWAY_URL=http://gateway:8642
      - WORKFRAME_PROJECT=${labelProject}
    depends_on:
      - gateway
      - dashboard
      - workframe-api
    networks:
      - ${docker.network}

networks:
  ${docker.network}:
    driver: bridge
  ${docker.controlNetwork}:
    driver: bridge
    internal: true

volumes:
  workframe-proxy-token:
`;
}

function dockerComposeHostBindingsYaml(docker) {
  return `# ponytail: supervisor stack.apply via docker.sock — absolute host binds (Windows/macOS).
# Usage: docker compose -f docker-compose.yml -f docker-compose.host-bindings.yml up -d --force-recreate gateway
name: ${docker.stack}

services:
  gateway:
    volumes:
      - \${WORKFRAME_HOST_PROJECT_ROOT}/Agents:/opt/data
      - \${WORKFRAME_HOST_PROJECT_ROOT}/Files:${WORKSPACE_DATA_MOUNT}
      - workframe-proxy-token:/run/workframe-proxy:ro
      - \${WORKFRAME_HOST_PROJECT_ROOT}/scripts:/opt/install/scripts:ro
      - \${WORKFRAME_HOST_COMPOSE_DIR}/docker/cont-init-workspace-link.sh:/etc/cont-init.d/03-workspace-link:ro

  dashboard:
    volumes:
      - \${WORKFRAME_HOST_COMPOSE_DIR}/docker/dashboard-proxy.conf:/etc/nginx/conf.d/default.conf:ro

  workframe-api:
    build:
      context: \${WORKFRAME_HOST_PROJECT_ROOT}/workframe-api
    volumes:
      - \${WORKFRAME_HOST_PROJECT_ROOT}/workframe-api/public:/app/public:ro
      - \${WORKFRAME_HOST_PROJECT_ROOT}/workframe-api:/app:ro
      - \${WORKFRAME_HOST_PROJECT_ROOT}/workframe-api/data:/app/data
      - \${WORKFRAME_HOST_PROJECT_ROOT}/Agents:/opt/data
      - \${WORKFRAME_HOST_PROJECT_ROOT}/Files:${WORKSPACE_DATA_MOUNT}
      - \${WORKFRAME_HOST_PROJECT_ROOT}/scripts:/opt/install/scripts:ro
      - \${WORKFRAME_HOST_PROJECT_ROOT}:/project:ro
      - \${WORKFRAME_HOST_COMPOSE_DIR}:/compose:ro
      - workframe-proxy-token:/run/workframe-proxy

  workframe-supervisor:
    build:
      context: \${WORKFRAME_HOST_PROJECT_ROOT}/workframe-supervisor
    volumes:
      - \${WORKFRAME_HOST_PROJECT_ROOT}/Agents:/opt/data
      - \${WORKFRAME_HOST_PROJECT_ROOT}:/compose

  workframe:
    volumes:
      - \${WORKFRAME_HOST_PROJECT_ROOT}/workframe-ui/public:/usr/share/nginx/html:ro
      - \${WORKFRAME_HOST_COMPOSE_DIR}/workframe-ui/docker/nginx.conf:/etc/nginx/conf.d/default.conf:ro
`;
}

function setupSh(docker, nativeProfile, nativeAgentName) {
  return `#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p Agents Files

echo "Pulling Hermes image..."
docker pull ${docker.image}

cat <<'EOF'

Workframe Phase B — use ONE of these:

  FULL (recommended — credentials → native agent → Workframe UI):
    ./scripts/start-install.sh

  Open full installer in new terminal (TTY-friendly):
    ./scripts/launch-install.sh

  Already ran Hermes setup? Finish boot:
    ./scripts/install.sh

  Credentials / dashboard only:
    ./scripts/open-setup.sh

Phase C — chat with ${nativeAgentName}:
  ./scripts/chat.sh

WARNING: docker run ... hermes-agent:latest WITHOUT -p ${nativeProfile}
         starts generic default Hermes (OWL) — not ${nativeAgentName}.
EOF
`;
}

function setupPs1(docker, nativeProfile, nativeAgentName) {
  return `$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

New-Item -ItemType Directory -Force -Path Agents, Files | Out-Null

Write-Host 'Pulling Hermes image...'
docker pull ${docker.image}

Write-Host @'

Workframe Phase B — use ONE of these:

  FULL (recommended — credentials → native agent → Workframe UI):
    .\Workframe\scripts\start-install.ps1

  Open full installer in new window (TTY-friendly):
    .\Workframe\scripts\launch-install.ps1

  Already ran Hermes setup? Finish boot:
    .\Workframe\scripts\install.ps1

  Credentials / dashboard only:
    .\Workframe\scripts\open-setup.ps1

Phase C — chat with ${nativeAgentName}:
  .\Workframe\scripts\chat.ps1

WARNING: docker run ... hermes-agent:latest WITHOUT -p ${nativeProfile}
         starts generic default Hermes (OWL) — not ${nativeAgentName}.
'@
`;
}

function chatSh(nativeProfile, docker) {
  return `#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
"$ROOT/scripts/verify-bootstrap.sh"
if docker ps -aq -f "name=^${docker.chat}$" | grep -q .; then
  docker rm -f "${docker.chat}"
fi
exec docker run --rm -it --name "${docker.chat}" --entrypoint hermes \\
  -v "$ROOT/Agents:/opt/data" \\
  -v "$ROOT/Files:/opt/data/workspace" \\
  ${docker.image} -p ${nativeProfile} chat "$@"
`;
}

function chatPs1(nativeProfile, docker) {
  return `$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
& "$Root\\scripts\\verify-bootstrap.ps1"
if (docker ps -aq -f "name=^${docker.chat}$") {
  docker rm -f "${docker.chat}"
}
docker run --rm -it --name "${docker.chat}" --entrypoint hermes \`
  -v "$Root\\Agents:/opt/data" \`
  -v "$Root\\Files:/opt/data/workspace" \`
  ${docker.image} -p ${nativeProfile} chat @args
`;
}

function verifyBootstrapSh(nativeProfile) {
  return `#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ ! -f "$ROOT/Agents/profiles/${nativeProfile}/SOUL.md" ]; then
  echo "ERROR: Workframe not bootstrapped." >&2
  echo "Run: ./scripts/bootstrap-native.sh" >&2
  echo "Full pack fallback: ./scripts/bootstrap-profiles.sh" >&2
  echo "Bare Hermes default profile is NOT a Workframe install." >&2
  exit 1
fi
if [ ! -f "$ROOT/Agents/SOUL.md" ] || ! grep -q 'Workframe concierge' "$ROOT/Agents/SOUL.md"; then
  echo "ERROR: Agents/SOUL.md missing Workframe native identity." >&2
  echo "Re-run: ./scripts/bootstrap-native.sh" >&2
  exit 1
fi
_cfg="$ROOT/Agents/profiles/${nativeProfile}/config.yaml"
if [ -f "$_cfg" ] && grep -q '^  cwd: \\.' "$_cfg"; then
  echo "ERROR: profile terminal.cwd must be /workspace (Files/), not ." >&2
  echo "Re-run: ./scripts/bootstrap-native.sh" >&2
  exit 1
fi
`;
}

function verifyBootstrapPs1(nativeProfile) {
  return `$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$soul = Join-Path $Root 'Agents\\profiles\\${nativeProfile}\\SOUL.md'
if (-not (Test-Path $soul)) {
  throw @"
Workframe not bootstrapped.
Run: .\\scripts\\bootstrap-native.ps1
Full pack fallback: .\\scripts\\bootstrap-profiles.ps1
Bare Hermes default profile is NOT a Workframe install.
"@
}
$homeSoul = Join-Path $Root 'Agents\\SOUL.md'
if (-not (Test-Path $homeSoul) -or -not (Select-String -Path $homeSoul -Pattern 'Workframe concierge' -Quiet)) {
  throw @"
Agents/SOUL.md missing Workframe native identity.
Re-run: .\\scripts\\bootstrap-native.ps1
"@
}
$cfg = Join-Path $Root "Agents\\profiles\\${nativeProfile}\\config.yaml"
if ((Test-Path $cfg) -and (Select-String -Path $cfg -Pattern '^  cwd: \\.$' -Quiet)) {
  throw @"
Profile terminal.cwd must be /workspace (Files/), not .
Re-run: .\\scripts\\bootstrap-native.ps1
"@
}
`;
}

function profileCreateBlockSh(p, projectName, docker, containerSuffix) {
  const desc = profileDescription(p, projectName);
  const suffix = containerSuffix || p;
  const createName = `${docker.stack}-bootstrap-${suffix}`;
  const showName = `${createName}-show`;
  const retryName = `${createName}-retry`;
  const cleanName = `${createName}-clean`;
  return `mkdir -p "$ROOT/Agents/profiles"
echo "Creating profile: ${p}"
profile_config="$ROOT/Agents/profiles/${p}/config.yaml"
clean_profile_orphan_${suffix}() {
  docker run --rm --name "${cleanName}" --entrypoint hermes \\
    -v "$ROOT/Agents:/opt/data" \\
    -v "$ROOT/Files:/opt/data/workspace" \\
    ${docker.image} profile delete -y ${p} >/dev/null 2>&1 || true
  rm -rf "$ROOT/Agents/profiles/${p}"
}
if docker run --rm --name "${showName}-precheck" --entrypoint hermes \\
  -v "$ROOT/Agents:/opt/data" \\
  -v "$ROOT/Files:/opt/data/workspace" \\
  ${docker.image} profile show ${p} >/dev/null 2>&1 && [ -f "$profile_config" ]; then
  echo "Profile ${p} already exists, continuing."
else
  clean_profile_orphan_${suffix}
  set +e
  create_out=$(docker run --rm --name "${createName}" --entrypoint hermes \\
    -v "$ROOT/Agents:/opt/data" \\
    -v "$ROOT/Files:/opt/data/workspace" \\
    ${docker.image} profile create ${p} --clone --description "${desc.replace(/"/g, '\\"')}" 2>&1)
  create_code=$?
  set -e
  if [ "$create_code" -ne 0 ]; then
    if docker run --rm --name "${showName}" --entrypoint hermes \\
      -v "$ROOT/Agents:/opt/data" \\
      -v "$ROOT/Files:/opt/data/workspace" \\
      ${docker.image} profile show ${p} >/dev/null 2>&1 && [ -f "$profile_config" ]; then
      echo "Profile ${p} already exists, continuing."
    else
      echo "Retrying profile create after cleaning incomplete registration: ${p}"
      clean_profile_orphan_${suffix}
      docker run --rm --name "${retryName}" --entrypoint hermes \\
        -v "$ROOT/Agents:/opt/data" \\
        -v "$ROOT/Files:/opt/data/workspace" \\
        ${docker.image} profile create ${p} --clone --description "${desc.replace(/"/g, '\\"')}" || {
        echo "$create_out" >&2
        echo "ERROR: failed to create profile ${p}" >&2
        exit 1
      }
    fi
  fi
fi
`;
}

function profileCreateBlockPs1(p, projectName, docker, containerSuffix) {
  const desc = profileDescription(p, projectName).replace(/'/g, "''");
  const suffix = containerSuffix || p;
  const createName = `${docker.stack}-bootstrap-${suffix}`;
  const showName = `${createName}-show`;
  const retryName = `${createName}-retry`;
  const cleanName = `${createName}-clean`;
  return `Write-Host "Creating profile: ${p}"
$profilesRoot = Join-Path $Root "Agents\\profiles"
$profileDir = Join-Path $profilesRoot "${p}"
$profileConfig = Join-Path $profileDir "config.yaml"
New-Item -ItemType Directory -Force -Path $profilesRoot | Out-Null

docker run --rm --name "${showName}-precheck" --entrypoint hermes \`
  -v "$Root\\Agents:/opt/data" \`
  -v "$Root\\Files:/opt/data/workspace" \`
  ${docker.image} profile show ${p} 2>$null | Out-Null
$profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
if ($profileReady) {
  Write-Host "Profile ${p} already exists, continuing."
} else {
  docker run --rm --name "${cleanName}" --entrypoint hermes \`
    -v "$Root\\Agents:/opt/data" \`
    -v "$Root\\Files:/opt/data/workspace" \`
    ${docker.image} profile delete -y ${p} 2>$null | Out-Null
  if (Test-Path $profileDir) {
    Remove-Item -Recurse -Force $profileDir
  }
  $createOut = docker run --rm --name "${createName}" --entrypoint hermes \`
    -v "$Root\\Agents:/opt/data" \`
    -v "$Root\\Files:/opt/data/workspace" \`
    ${docker.image} profile create ${p} --clone --description "${desc.replace(/"/g, '`"')}" 2>&1
  if ($LASTEXITCODE -ne 0) {
    docker run --rm --name "${showName}" --entrypoint hermes \`
      -v "$Root\\Agents:/opt/data" \`
      -v "$Root\\Files:/opt/data/workspace" \`
      ${docker.image} profile show ${p} 2>$null | Out-Null
    $profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
    if ($profileReady) {
      Write-Host "Profile ${p} already exists, continuing."
    } else {
      Write-Host "Retrying profile create after cleaning incomplete registration: ${p}"
      docker run --rm --name "${cleanName}-retry" --entrypoint hermes \`
        -v "$Root\\Agents:/opt/data" \`
        -v "$Root\\Files:/opt/data/workspace" \`
        ${docker.image} profile delete -y ${p} 2>$null | Out-Null
      if (Test-Path $profileDir) {
        Remove-Item -Recurse -Force $profileDir
      }
      $createOut = docker run --rm --name "${retryName}" --entrypoint hermes \`
        -v "$Root\\Agents:/opt/data" \`
        -v "$Root\\Files:/opt/data/workspace" \`
        ${docker.image} profile create ${p} --clone --description "${desc.replace(/"/g, '`"')}" 2>&1
      if ($LASTEXITCODE -ne 0) {
        throw "Failed to create profile ${p}: $createOut"
      }
    }
  }
}
`;
}

function copySeedArtifactsSh(profile, nativeProfile, { includeSetup = false } = {}) {
  let out = `if [ -f "$ROOT/scripts/seed/profiles/${profile}/SOUL.md" ]; then
  mkdir -p "$ROOT/Agents/profiles/${profile}"
  cp "$ROOT/scripts/seed/profiles/${profile}/SOUL.md" "$ROOT/Agents/profiles/${profile}/SOUL.md"
fi
if [ -f "$ROOT/scripts/seed/profiles/${profile}/AGENTS.md" ]; then
  mkdir -p "$ROOT/Agents/profiles/${profile}"
  cp "$ROOT/scripts/seed/profiles/${profile}/AGENTS.md" "$ROOT/Agents/profiles/${profile}/AGENTS.md"
fi
`;
  if (includeSetup && profile === nativeProfile) {
    out += `# Hermes identity reads HERMES_HOME/SOUL.md (= Agents/SOUL.md), not profile subdir alone
if [ -f "$ROOT/scripts/seed/profiles/${profile}/SOUL.md" ]; then
  cp "$ROOT/scripts/seed/profiles/${profile}/SOUL.md" "$ROOT/Agents/SOUL.md"
fi
`;
    out += `if [ -f "$ROOT/scripts/seed/profiles/${profile}/SETUP.md" ]; then
  cp "$ROOT/scripts/seed/profiles/${profile}/SETUP.md" "$ROOT/Agents/profiles/${profile}/SETUP.md"
fi
`;
    out += `if [ -d "$ROOT/scripts/seed/profiles/${profile}/skills" ]; then
  mkdir -p "$ROOT/Agents/profiles/${profile}/skills"
  cp -R "$ROOT/scripts/seed/profiles/${profile}/skills/." "$ROOT/Agents/profiles/${profile}/skills/"
fi
`;
  }
  return out;
}

function patchTerminalCwdSh(profileSlug) {
  return `# Project workspace is /workspace (Files/) — terminal cwd + AGENTS.md auto-load
_cfg="$ROOT/Agents/profiles/${profileSlug}/config.yaml"
if [ -f "$_cfg" ] && grep -q '^  cwd: ' "$_cfg"; then
  if sed --version >/dev/null 2>&1; then
    sed -i.bak 's|^  cwd: .*|  cwd: /workspace|' "$_cfg" && rm -f "$_cfg.bak"
  else
    sed -i '' 's|^  cwd: .*|  cwd: /workspace|' "$_cfg"
  fi
fi
`;
}

function patchTerminalCwdPs1(profileSlug) {
  return `$cfg = Join-Path $Root "Agents\\profiles\\${profileSlug}\\config.yaml"
if (Test-Path $cfg) {
  $content = Get-Content $cfg -Raw
  $content = $content -replace '(?m)^  cwd: .*', '  cwd: /workspace'
  Set-Content -Path $cfg -Value $content -NoNewline
}
`;
}

function copySeedArtifactsPs1(profile, nativeProfile, { includeSetup = false } = {}) {
  let out = `$seed = Join-Path $Root "scripts\\seed\\profiles\\${profile}\\SOUL.md"
$destDir = Join-Path $Root "Agents\\profiles\\${profile}"
if (Test-Path $seed) {
  New-Item -ItemType Directory -Force -Path $destDir | Out-Null
  Copy-Item $seed (Join-Path $destDir "SOUL.md") -Force
}
$agentsSeed = Join-Path $Root "scripts\\seed\\profiles\\${profile}\\AGENTS.md"
if (Test-Path $agentsSeed) {
  New-Item -ItemType Directory -Force -Path $destDir | Out-Null
  Copy-Item $agentsSeed (Join-Path $destDir "AGENTS.md") -Force
}
`;
  if (includeSetup && profile === nativeProfile) {
    out += `# Hermes identity reads HERMES_HOME/SOUL.md (= Agents/SOUL.md), not profile subdir alone
$homeSoulDest = Join-Path $Root "Agents\\SOUL.md"
if (Test-Path $seed) {
  Copy-Item $seed $homeSoulDest -Force
}
`;
    out += `$setupSeed = Join-Path $Root "scripts\\seed\\profiles\\${profile}\\SETUP.md"
if (Test-Path $setupSeed) {
  Copy-Item $setupSeed (Join-Path $destDir "SETUP.md") -Force
}
`;
    out += `$skillsSeed = Join-Path $Root "scripts\\seed\\profiles\\${profile}\\skills"
if (Test-Path $skillsSeed) {
  $skillsDest = Join-Path $destDir "skills"
  New-Item -ItemType Directory -Force -Path $skillsDest | Out-Null
  Copy-Item -Path (Join-Path $skillsSeed '*') -Destination $skillsDest -Recurse -Force
}
`;
  }
  return out;
}

function profileUseBlockSh(nativeProfile, docker) {
  return `echo "Setting default profile to ${nativeProfile}..."
docker run --rm --name "${docker.bootstrapUse}" --entrypoint hermes \\
  -v "$ROOT/Agents:/opt/data" \\
  -v "$ROOT/Files:/opt/data/workspace" \\
  ${docker.image} profile use ${nativeProfile}
`;
}

function profileUseBlockPs1(nativeProfile, docker) {
  return `Write-Host "Setting default profile to ${nativeProfile}..."
docker run --rm --name "${docker.bootstrapUse}" --entrypoint hermes \`
  -v "$Root\\Agents:/opt/data" \`
  -v "$Root\\Files:/opt/data/workspace" \`
  ${docker.image} profile use ${nativeProfile}
`;
}

function configureProfileApiSh(nativeProfile, docker) {
  const stack = docker.stack;
  return `# Ensure api_server platform is configured for the native profile
docker run --rm --name "${stack}-bootstrap-api" --entrypoint hermes \\
  -v "$ROOT/Agents:/opt/data" \\
  -v "$ROOT/Files:/opt/data/workspace" \\
  ${docker.image} -p ${nativeProfile} config set platforms.api_server.enabled true 2>/dev/null || true
docker run --rm --name "${stack}-bootstrap-api-host" --entrypoint hermes \\
  -v "$ROOT/Agents:/opt/data" \\
  -v "$ROOT/Files:/opt/data/workspace" \\
  ${docker.image} -p ${nativeProfile} config set platforms.api_server.extra.host 0.0.0.0 2>/dev/null || true
docker run --rm --name "${stack}-bootstrap-api-key" --entrypoint hermes \\
  -v "$ROOT/Agents:/opt/data" \\
  -v "$ROOT/Files:/opt/data/workspace" \\
  ${docker.image} -p ${nativeProfile} config set platforms.api_server.extra.key workframe-local-key 2>/dev/null || true
`;
}

function bootstrapNativeSh(nativeProfile, projectName, docker) {
  return `#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p Agents Files

${seedNativeFromPackageSh(nativeProfile)}

if [ ! -d "$ROOT/Agents" ]; then
  echo "Agents/ missing. Run Hermes setup first."
  exit 1
fi

${profileCreateBlockSh(nativeProfile, projectName, docker, 'native')}
${configureProfileApiSh(nativeProfile, docker)}
${copySeedArtifactsSh(nativeProfile, nativeProfile, { includeSetup: true })}

# Strip UTF-8 BOM from SOUL.md if present (hermes setup writes BOM which silently blocks agent startup)
for _soul in "$ROOT/Agents/SOUL.md" "$ROOT/Agents/profiles/${nativeProfile}/SOUL.md"; do
  if [ -f "$_soul" ] && head -c 3 "$_soul" | grep -qP '\xef\xbb\xbf'; then
    tail -c +4 "$_soul" > "\${_soul}.nobom" && mv "\${_soul}.nobom" "$_soul"
    echo "Stripped BOM from $_soul"
  fi
done

${patchTerminalCwdSh(nativeProfile)}
${profileUseBlockSh(nativeProfile, docker)}
${writeRoutesJsonBlockSh([nativeProfile], nativeProfile, projectName)}
echo "Native bootstrap complete (${nativeProfile}). Create agents: node scripts/agent-lifecycle.mjs create --slug <name> --spawn"
docker run --rm --name "${docker.bootstrapList}" --entrypoint hermes \\
  -v "$ROOT/Agents:/opt/data" \\
  -v "$ROOT/Files:/opt/data/workspace" \\
  ${docker.image} profile list
`;
}

function configureProfileApiPs1(nativeProfile, docker) {
  const stack = docker.stack;
  return `$cfg = Join-Path $Root "Agents\\profiles\\${nativeProfile}\\config.yaml"
  docker run --rm --name "${stack}-bootstrap-api" --entrypoint hermes \`
    -v "$Root\\Agents:/opt/data" \`
    -v "$Root\\Files:/opt/data/workspace" \`
    ${docker.image} -p ${nativeProfile} config set platforms.api_server.enabled true 2>$null
  docker run --rm --name "${stack}-bootstrap-api-host" --entrypoint hermes \`
    -v "$Root\\Agents:/opt/data" \`
    -v "$Root\\Files:/opt/data/workspace" \`
    ${docker.image} -p ${nativeProfile} config set platforms.api_server.extra.host 0.0.0.0 2>$null
  docker run --rm --name "${stack}-bootstrap-api-key" --entrypoint hermes \`
    -v "$Root\\Agents:/opt/data" \`
    -v "$Root\\Files:/opt/data/workspace" \`
    ${docker.image} -p ${nativeProfile} config set platforms.api_server.extra.key workframe-local-key 2>$null
`;
}

function bootstrapNativePs1(nativeProfile, projectName, docker) {
  return `$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

New-Item -ItemType Directory -Force -Path Agents, Files | Out-Null

${seedNativeFromPackagePs1(nativeProfile)}

if (-not (Test-Path "$Root\\Agents")) {
  throw "Agents/ missing. Run Hermes setup first."
}

${profileCreateBlockPs1(nativeProfile, projectName, docker, 'native')}
${configureProfileApiPs1(nativeProfile, docker)}
${copySeedArtifactsPs1(nativeProfile, nativeProfile, { includeSetup: true })}

# Strip UTF-8 BOM from SOUL.md if present
foreach ($soul in @("$Root\Agents\SOUL.md", "$Root\Agents\profiles\$nativeProfile\SOUL.md")) {
  if (Test-Path $soul) {
    $bytes = [System.IO.File]::ReadAllBytes($soul)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xef -and $bytes[1] -eq 0xbb -and $bytes[2] -eq 0xbf) {
      [System.IO.File]::WriteAllBytes($soul, $bytes[3..($bytes.Length-1)])
      Write-Host "Stripped BOM from $soul"
    }
  }
}

${patchTerminalCwdPs1(nativeProfile)}
${profileUseBlockPs1(nativeProfile, docker)}
${writeRoutesJsonBlockPs1([nativeProfile], nativeProfile, projectName)}
Write-Host "Native bootstrap complete (${nativeProfile}). Create agents: node scripts/agent-lifecycle.mjs create --slug <name> --spawn"
docker run --rm --name "${docker.bootstrapList}" --entrypoint hermes \`
  -v "$Root\\Agents:/opt/data" \`
  -v "$Root\\Files:/opt/data/workspace" \`
  ${docker.image} profile list
`;
}

function addProfileSh(nativeProfile, specialists, projectName, docker) {
  const allowed = specialists.join(' ');
  const caseArms = specialists.map((s) => `  "${s}") PROFILE="${s}" ;;`).join('\n');
  return `#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

INPUT="\${1:-}"
if [ -z "$INPUT" ]; then
  echo "Usage: $0 <profile>" >&2
  echo "Specialists: ${allowed}" >&2
  exit 1
fi
if [ "$INPUT" = "${nativeProfile}" ]; then
  echo "Use bootstrap-native for ${nativeProfile}." >&2
  exit 1
fi
PROFILE=""
case "$INPUT" in
${caseArms}
  *)
    echo "Unknown profile: $INPUT" >&2
    echo "Available: ${allowed}" >&2
    exit 1
    ;;
esac

if [ ! -d "$ROOT/Agents" ]; then
  echo "Agents/ missing. Run Hermes setup first." >&2
  exit 1
fi

DESC=""
case "$PROFILE" in
${specialists.map((s) => {
    const d = profileDescription(s, projectName).replace(/"/g, '\\"');
    return `  "${s}") DESC="${d}" ;;`;
  }).join('\n')}
esac

set +e
create_out=$(docker run --rm --name "${docker.stack}-add-$PROFILE" --entrypoint hermes \\
  -v "$ROOT/Agents:/opt/data" \\
  -v "$ROOT/Files:/opt/data/workspace" \\
  ${docker.image} profile create "$PROFILE" --clone --description "$DESC" 2>&1)
create_code=$?
set -e
if [ "$create_code" -ne 0 ]; then
  if docker run --rm --name "${docker.stack}-add-$PROFILE-show" --entrypoint hermes \\
    -v "$ROOT/Agents:/opt/data" \\
    -v "$ROOT/Files:/opt/data/workspace" \\
    ${docker.image} profile show "$PROFILE" >/dev/null 2>&1; then
    echo "Profile $PROFILE already exists, continuing."
  else
    echo "$create_out" >&2
    echo "ERROR: failed to create profile $PROFILE" >&2
    exit 1
  fi
fi

if [ -f "$ROOT/scripts/seed/profiles/$PROFILE/SOUL.md" ]; then
  mkdir -p "$ROOT/Agents/profiles/$PROFILE"
  cp "$ROOT/scripts/seed/profiles/$PROFILE/SOUL.md" "$ROOT/Agents/profiles/$PROFILE/SOUL.md"
fi
if [ -f "$ROOT/scripts/seed/profiles/$PROFILE/AGENTS.md" ]; then
  mkdir -p "$ROOT/Agents/profiles/$PROFILE"
  cp "$ROOT/scripts/seed/profiles/$PROFILE/AGENTS.md" "$ROOT/Agents/profiles/$PROFILE/AGENTS.md"
fi
${patchTerminalCwdSh('$PROFILE')}

echo "Profile $PROFILE ready."
echo "Register + DM bootstrap: open Workframe → Agents → open $PROFILE (or Create agent) so your u-* runtime and session bind."
echo "If services are not running, start the base stack: docker compose up -d"
`;
}

function addProfilePs1(nativeProfile, specialists, projectName, docker) {
  const allowed = specialists.map((s) => `'${s}'`).join(', ');
  const descMap = specialists.map((s) => {
    const d = profileDescription(s, projectName).replace(/'/g, "''");
    return `  '${s}' = '${d}'`;
  }).join('\n');
  return `param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Profile
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Allowed = @(${allowed})
if ($Profile -eq '${nativeProfile}') {
  throw "Use bootstrap-native for ${nativeProfile}."
}
if ($Allowed -notcontains $Profile) {
  throw "Unknown profile '$Profile'. Available: $($Allowed -join ', ')"
}
if (-not (Test-Path "$Root\\Agents")) {
  throw "Agents/ missing. Run Hermes setup first."
}

$Descriptions = @{
${descMap}
}
$desc = $Descriptions[$Profile]

$createOut = docker run --rm --name "${docker.stack}-add-$Profile" --entrypoint hermes \`
  -v "$Root\\Agents:/opt/data" \`
  -v "$Root\\Files:/opt/data/workspace" \`
  ${docker.image} profile create $Profile --clone --description "$desc" 2>&1
if ($LASTEXITCODE -ne 0) {
  docker run --rm --name "${docker.stack}-add-$Profile-show" --entrypoint hermes \`
    -v "$Root\\Agents:/opt/data" \`
    -v "$Root\\Files:/opt/data/workspace" \`
    ${docker.image} profile show $Profile 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) {
    Write-Host "Profile $Profile already exists, continuing."
  } else {
    throw "Failed to create profile ${'$'}($Profile): ${'$'}createOut"
  }
}

$seed = Join-Path $Root "scripts\\seed\\profiles\\$Profile\\SOUL.md"
$destDir = Join-Path $Root "Agents\\profiles\\$Profile"
if (Test-Path $seed) {
  New-Item -ItemType Directory -Force -Path $destDir | Out-Null
  Copy-Item $seed (Join-Path $destDir "SOUL.md") -Force
}
$agentsSeed = Join-Path $Root "scripts\\seed\\profiles\\$Profile\\AGENTS.md"
if (Test-Path $agentsSeed) {
  New-Item -ItemType Directory -Force -Path $destDir | Out-Null
  Copy-Item $agentsSeed (Join-Path $destDir "AGENTS.md") -Force
}
${patchTerminalCwdPs1('$Profile')}

Write-Host "Profile $Profile ready."
Write-Host "Register + DM bootstrap: open Workframe → Agents → open $Profile (or Create agent) so your u-* runtime and session bind."
Write-Host "If services are not running, start the base stack: docker compose up -d"
`;
}

function openSetupSh(docker, ports) {
  return `#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DASH_PORT="${ports.dashboard}"
if [ -f "$ROOT/.env" ]; then
  val=$(grep -E '^WORKFRAME_DASHBOARD_PORT=' "$ROOT/.env" | tail -n1 | cut -d= -f2- || true)
  if [ -n "$val" ]; then DASH_PORT="$val"; fi
fi

echo "Workframe secure setup — credentials never belong in chat."
echo ""
echo "Full Phase B (recommended): ./scripts/start-install.sh"
echo ""
echo "Hermes setup (interactive, writes to Agents/):"
echo "  docker run --rm -it --name ${docker.setup} --entrypoint hermes \\\\"
echo "    -v \\"\\$PWD/Agents:/opt/data\\" \\\\"
echo "    -v \\"\\$PWD/Files:/opt/data/workspace\\" \\\\"
echo "    ${docker.image} setup"
echo ""
echo "Dashboard (ops UI): http://127.0.0.1:\${DASH_PORT}"
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://127.0.0.1:\${DASH_PORT}" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open "http://127.0.0.1:\${DASH_PORT}" >/dev/null 2>&1 || true
fi
`;
}

function openChatPs1(ports) {
  return `$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$DashPort = '${ports.dashboard}'
$envFile = Join-Path $Root '.env'
if (Test-Path $envFile) {
  $line = Get-Content $envFile | Where-Object { $_ -match '^WORKFRAME_DASHBOARD_PORT=' } | Select-Object -Last 1
  if ($line) { $DashPort = ($line -split '=', 2)[1].Trim() }
}

$url = "http://127.0.0.1:$DashPort/chat"
Write-Host "Opening Hermes browser chat (embedded TUI): $url"
$deadline = (Get-Date).AddSeconds(45)
while ((Get-Date) -lt $deadline) {
  try {
    $null = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
    break
  } catch {
    Start-Sleep -Seconds 2
  }
}
try {
  Start-Process $url | Out-Null
} catch {
  Write-Host "Open manually: $url"
}
`;
}

function openChatSh(ports) {
  return `#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DASH_PORT="${ports.dashboard}"
if [ -f "$ROOT/.env" ]; then
  val=$(grep -E '^WORKFRAME_DASHBOARD_PORT=' "$ROOT/.env" | tail -n1 | cut -d= -f2- || true)
  if [ -n "$val" ]; then DASH_PORT="$val"; fi
fi

URL="http://127.0.0.1:\${DASH_PORT}/chat"
echo "Opening Hermes browser chat (embedded TUI): $URL"
for _ in $(seq 1 22); do
  if curl -fsS -o /dev/null "$URL" 2>/dev/null; then break; fi
  sleep 2
done
if command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then open "$URL" >/dev/null 2>&1 || true
else echo "Open manually: $URL"
fi
`;
}

function openWorkframeApiPs1(ports) {
  return `$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$ApiPort = '${ports.api}'
$envFile = Join-Path $Root '.env'
if (Test-Path $envFile) {
  $line = Get-Content $envFile | Where-Object { $_ -match '^WORKFRAME_API_PORT=' } | Select-Object -Last 1
  if ($line) { $ApiPort = ($line -split '=', 2)[1].Trim() }
}

$url = "http://127.0.0.1:$ApiPort/"
Write-Host "Opening Workframe API: $url"
$deadline = (Get-Date).AddSeconds(45)
while ((Get-Date) -lt $deadline) {
  try {
    $null = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
    break
  } catch {
    Start-Sleep -Seconds 2
  }
}
try {
  Start-Process $url | Out-Null
} catch {
  Write-Host "Open manually: $url"
}
`;
}

function openWorkframeApiSh(ports) {
  return `#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

API_PORT="${ports.api}"
if [ -f "$ROOT/.env" ]; then
  val=$(grep -E '^WORKFRAME_API_PORT=' "$ROOT/.env" | tail -n1 | cut -d= -f2- || true)
  if [ -n "$val" ]; then API_PORT="$val"; fi
fi

URL="http://127.0.0.1:\${API_PORT}/"
echo "Opening Workframe API: $URL"
for _ in $(seq 1 22); do
  if curl -fsS -o /dev/null "$URL" 2>/dev/null; then break; fi
  sleep 2
done
if command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then open "$URL" >/dev/null 2>&1 || true
else echo "Open manually: $URL"
fi
`;
}

function updateHermesPs1(_packProfiles) {
  return `$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$services = @(docker compose config --services 2>$null | Where-Object { $_ -match '^(gateway|dashboard)$' })
if (-not $services.Count) { $services = @('gateway', 'dashboard') }

Write-Host 'Pulling latest Hermes image...'
docker compose pull @services
Write-Host 'Recreating Hermes containers (in-container hermes update is unsupported in Docker)...'
docker compose up -d --force-recreate @services
Write-Host 'Done. Mission control and workframe unchanged unless you recreate the full stack.'
`;
}

function updateHermesSh(_packProfiles) {
  return `#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mapfile -t SERVICES < <(docker compose config --services 2>/dev/null | grep -E '^(gateway|dashboard)$' || true)
if [ "\${#SERVICES[@]}" -eq 0 ]; then
  SERVICES=(gateway dashboard)
fi

echo "Pulling latest Hermes image..."
docker compose pull "\${SERVICES[@]}"
echo "Recreating Hermes containers (in-container hermes update is unsupported in Docker)..."
docker compose up -d --force-recreate "\${SERVICES[@]}"
echo "Done. Mission control and workframe unchanged unless you recreate the full stack."
`;
}

function launchPhaseBInstaller(target, { wait = false, noBrowser = false } = {}) {
  if (process.platform === 'win32') {
    const script = path.join(target, 'scripts', 'start-install.ps1');
    if (!fs.existsSync(script)) return false;
    if (wait) {
      const args = [
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        script,
        '-NoPrompt',
      ];
      if (noBrowser) args.push('-NoBrowser');
      const child = spawnSync('powershell.exe', args, { cwd: target, stdio: 'inherit' });
      if (child.error) throw child.error;
      if (child.status !== 0) {
        throw new Error(`Phase B installer failed (${child.status ?? 'unknown exit'})`);
      }
      return true;
    }
    const escaped = script.replace(/'/g, "''");
    const child = spawn(
      'powershell.exe',
      [
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-Command',
        `Start-Process powershell.exe -WindowStyle Normal -ArgumentList '-NoExit','-NoProfile','-ExecutionPolicy','Bypass','-File','${escaped}'`,
      ],
      {
        cwd: target,
        detached: true,
        stdio: 'ignore',
        windowsHide: false,
      },
    );
    child.unref();
    return true;
  }
  const script = path.join(target, 'scripts', 'start-install.sh');
  if (!fs.existsSync(script)) return false;
  if (wait) {
    const args = ['--no-prompt'];
    if (noBrowser) args.push('--no-browser');
    const child = spawnSync(script, args, { cwd: target, stdio: 'inherit' });
    if (child.error) throw child.error;
    if (child.status !== 0) {
      throw new Error(`Phase B installer failed (${child.status ?? 'unknown exit'})`);
    }
    return true;
  }
  const child = spawn(script, [], {
    cwd: target,
    detached: true,
    stdio: 'ignore',
  });
  child.unref();
  return true;
}

function openInstallBrowserBlockSh() {
  return `echo ""
echo "Opening Workframe setup wizard (/install)..."
"$ROOT/scripts/open-install-ui.sh" || true
`;
}

function openInstallBrowserBlockPs1() {
  return `Write-Host ''
Write-Host 'Opening Workframe setup wizard (/install)...' -ForegroundColor Green
& "$Root\\scripts\\open-install-ui.ps1"
`;
}

function openWorkframeBrowserBlockSh() {
  return `echo ""
echo "Opening Workframe UI..."
"$ROOT/scripts/open-workframe-ui.sh" || true
`;
}

function openWorkframeBrowserBlockPs1() {
  return `Write-Host ''
Write-Host 'Opening Workframe UI...' -ForegroundColor Green
& "$Root\\scripts\\open-workframe-ui.ps1"
`;
}

function openSetupPs1(docker, ports) {
  return `$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$DashPort = '${ports.dashboard}'
$envFile = Join-Path $Root '.env'
if (Test-Path $envFile) {
  $line = Get-Content $envFile | Where-Object { $_ -match '^WORKFRAME_DASHBOARD_PORT=' } | Select-Object -Last 1
  if ($line) {
    $DashPort = ($line -split '=', 2)[1].Trim()
  }
}

Write-Host 'Workframe secure setup - credentials never belong in chat.'
Write-Host ''
Write-Host 'Full Phase B (recommended): .\\scripts\\start-install.ps1'
Write-Host ''
Write-Host 'Hermes setup only (interactive, writes to Agents/):'
Write-Host "  docker run --rm -it --name ${docker.setup} --entrypoint hermes \`"
Write-Host '    -v "$PWD\\Agents:/opt/data" \`'
Write-Host '    -v "$PWD\\Files:/opt/data/workspace" \`'
Write-Host '    ${docker.image} setup'
Write-Host ''
$url = "http://127.0.0.1:$DashPort"
Write-Host "Dashboard (ops UI): $url"
try {
  Start-Process $url | Out-Null
} catch {
  Write-Host 'Open the dashboard URL manually in your browser.'
}
`;
}

function installPs1(nativeProfile, nativeAgentName, docker, ports) {
  return `$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$config = Join-Path $Root 'Agents\\config.yaml'
if (-not (Test-Path $config)) {
  throw @"
Hermes is not initialized in Agents/.
Run the full Phase B installer: .\\scripts\\start-install.ps1
Or run Hermes setup first, then re-run: .\\scripts\\install.ps1
"@
}

Write-Host "Bootstrapping ${nativeAgentName} (${nativeProfile})..."
& "$Root\\scripts\\bootstrap-native.ps1"
& "$Root\\scripts\\verify-bootstrap.ps1"

Write-Host 'Starting full stack (gateway, dashboard, workframe-api, Workframe UI)...'
${composeUpPs1Block()}

Write-Host ''
Write-Host "Phase B complete - ${nativeAgentName} is ready." -ForegroundColor Green
Write-Host '  Browser chat (TUI): http://127.0.0.1:${ports.dashboard}/chat'
Write-Host '  Terminal chat: .\\scripts\\chat.ps1'
Write-Host '  Workframe UI: http://127.0.0.1:${ports.ui}'
Write-Host '  Hermes ops dashboard: http://127.0.0.1:${ports.dashboard}'
Write-Host '  Add specialists: .\\scripts\\add-profile.ps1 <slug>'
${openWorkframeBrowserBlockPs1()}
`;
}

function installSh(nativeProfile, nativeAgentName, docker, ports) {
  return `#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f "$ROOT/Agents/config.yaml" ]; then
  echo "Hermes is not initialized in Agents/." >&2
  echo "Run: ./scripts/start-install.sh" >&2
  exit 1
fi

echo "Bootstrapping ${nativeAgentName} (${nativeProfile})..."
"$ROOT/scripts/bootstrap-native.sh"
"$ROOT/scripts/verify-bootstrap.sh"

echo "Starting full stack (gateway, dashboard, workframe-api, Workframe UI)..."
${composeUpBashBlock()}

echo ""
echo "Phase B complete — ${nativeAgentName} is ready."
echo "  Browser chat (TUI): http://127.0.0.1:${ports.dashboard}/chat"
echo "  Terminal chat: ./scripts/chat.sh"
echo "  Workframe UI: http://127.0.0.1:${ports.ui}"
echo "  Hermes ops dashboard: http://127.0.0.1:${ports.dashboard}"
echo "  Add specialists: ./scripts/add-profile.sh <slug>"
${openWorkframeBrowserBlockSh()}
`;
}

function startInstallPs1(docker, nativeProfile, nativeAgentName, ports) {
  return `param(
  [switch]$NoBrowser,
  [switch]$NoPrompt
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

New-Item -ItemType Directory -Force -Path Agents, Files | Out-Null

Write-Host ''
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ' Workframe install (UI-first)' -ForegroundColor Cyan
Write-Host " Project: ${nativeAgentName}" -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''

if (-not $NoBrowser) {
  & "$Root\\scripts\\open-install-ui.ps1"
}

Write-Host 'Step 1/2 - Starting Docker stack...' -ForegroundColor Yellow
${composeUpPs1Block()}
if ($LASTEXITCODE -ne 0) {
  Write-Host 'docker compose up failed.' -ForegroundColor Red
  Read-Host 'Press Enter to close'
  exit $LASTEXITCODE
}

Write-Host ''
Write-Host "Step 2/2 - Bootstrap ${nativeAgentName} (preserves existing profiles)..." -ForegroundColor Yellow
& "$Root\\scripts\\bootstrap-native.ps1"
& "$Root\\scripts\\verify-bootstrap.ps1"

Write-Host ''
Write-Host '========================================' -ForegroundColor Green
Write-Host " Install ready - continue in the browser" -ForegroundColor Green
Write-Host '========================================' -ForegroundColor Green
Write-Host ''
Write-Host '  Install UI:        http://127.0.0.1:${ports.ui}/install'
Write-Host '  Workframe UI:      http://127.0.0.1:${ports.ui}'
Write-Host '  Hermes dashboard:  http://127.0.0.1:${ports.dashboard}'
Write-Host ''
Write-Host 'LLM keys are configured in the onboarding UI - no Hermes TUI required.' -ForegroundColor DarkGray
if (-not $NoBrowser) {
  Write-Host ''
  Write-Host 'Opening Workframe setup wizard (/install)...' -ForegroundColor Green
  & "$Root\\scripts\\open-install-ui.ps1"
}
if (-not $NoPrompt) {
  Read-Host 'Press Enter to close'
}
`;
}

function startInstallSh(docker, nativeProfile, nativeAgentName, ports) {
  return `#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NO_BROWSER=0
for arg in "$@"; do
  case "$arg" in
    --no-browser) NO_BROWSER=1 ;;
    --no-prompt) ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

mkdir -p Agents Files

echo ""
echo "========================================"
echo " Workframe install (UI-first)"
echo " Project: ${nativeAgentName}"
echo "========================================"
echo ""

if [ "$NO_BROWSER" -eq 0 ]; then
  "$ROOT/scripts/open-install-ui.sh" || true
fi

echo "Step 1/2 — Starting Docker stack..."
${composeUpBashBlock()}

echo ""
echo "Step 2/2 — Bootstrap ${nativeAgentName} (preserves existing profiles)..."
"$ROOT/scripts/bootstrap-native.sh"
"$ROOT/scripts/verify-bootstrap.sh"

echo ""
echo "========================================"
echo " Install ready - continue in the browser"
echo "========================================"
echo ""
echo "  Install UI:        http://127.0.0.1:${ports.ui}/install"
echo "  Workframe UI:      http://127.0.0.1:${ports.ui}"
echo "  Hermes dashboard:  http://127.0.0.1:${ports.dashboard}/"
echo ""
echo "LLM keys are configured in the onboarding UI - no Hermes TUI required."
if [ "$NO_BROWSER" -eq 0 ]; then
  echo ""
  echo "Opening Workframe setup wizard (/install)..."
  "$ROOT/scripts/open-install-ui.sh" || true
fi
`;
}

function launchInstallPs1() {
  return `$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Root 'scripts\\start-install.ps1'
Start-Process powershell -ArgumentList @('-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Script)
Write-Host 'Opened installer in a new window.'
Write-Host 'Browser opens /install immediately — configure everything in the UI.'
`;
}

function launchInstallSh() {
  return `#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
START="$ROOT/scripts/start-install.sh"
PAUSE='read -r -p "Press Enter to close..." _'

launch_in_terminal() {
  local cmd="cd $(printf '%q' "$ROOT") && exec $(printf '%q' "$START"); echo; $PAUSE"
  case "$(uname -s)" in
    Darwin)
      local root_esc
      root_esc=$(printf %s "$ROOT" | sed "s/'/'\\\\''/g")
      osascript <<APPLESCRIPT >/dev/null 2>&1
tell application "Terminal"
  activate
  do script "cd '\${root_esc}' && exec './scripts/start-install.sh'"
end tell
APPLESCRIPT
      return 0
      ;;
    Linux)
      if command -v gnome-terminal >/dev/null 2>&1; then
        gnome-terminal -- bash -lc "$cmd"
        return 0
      fi
      if command -v konsole >/dev/null 2>&1; then
        konsole -e bash -lc "$cmd"
        return 0
      fi
      if command -v xfce4-terminal >/dev/null 2>&1; then
        xfce4-terminal -e bash -lc "$cmd"
        return 0
      fi
      if command -v xterm >/dev/null 2>&1; then
        xterm -e bash -lc "$cmd"
        return 0
      fi
      ;;
  esac
  return 1
}

if [ -z "\${WORKFRAME_LAUNCH_IN_PLACE:-}" ]; then
  if launch_in_terminal; then
    echo "Opened Phase B installer in a new terminal."
    echo "Complete Hermes setup there — Workframe UI opens automatically when the stack is up."
    exit 0
  fi
fi

echo "Running Phase B installer in this terminal..."
exec "$START"
`;
}

function bootstrapProfilesSh(profiles, projectName, nativeProfile, docker) {
  const blocks = profiles.map((p) => {
    const isNative = p === nativeProfile;
    return `${profileCreateBlockSh(p, projectName, docker, p)}
${copySeedArtifactsSh(p, nativeProfile, { includeSetup: isNative })}
${patchTerminalCwdSh(p)}
`;
  });
  return `#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d "$ROOT/Agents" ]; then
  echo "Agents/ missing. Run Hermes setup first."
  exit 1
fi

${blocks.join('\n')}
${profileUseBlockSh(nativeProfile, docker)}
${writeRoutesJsonBlockSh(profiles, nativeProfile, projectName)}
echo "Full pack bootstrap complete. Start services with: docker compose up -d"
docker run --rm --name "${docker.bootstrapList}" --entrypoint hermes \\
  -v "$ROOT/Agents:/opt/data" \\
  -v "$ROOT/Files:/opt/data/workspace" \\
  ${docker.image} profile list
`;
}

function bootstrapProfilesPs1(profiles, projectName, nativeProfile, docker) {
  const blocks = profiles.map((p) => {
    const isNative = p === nativeProfile;
    return `${profileCreateBlockPs1(p, projectName, docker, p)}
${copySeedArtifactsPs1(p, nativeProfile, { includeSetup: isNative })}
${patchTerminalCwdPs1(p)}
`;
  });
  return `$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path "$Root\\Agents")) {
  throw "Agents/ missing. Run Hermes setup first."
}

${blocks.join('\n')}
${profileUseBlockPs1(nativeProfile, docker)}
${writeRoutesJsonBlockPs1(profiles, nativeProfile, projectName)}
Write-Host "Full pack bootstrap complete. Start services with: docker compose up -d"
docker run --rm --name "${docker.bootstrapList}" --entrypoint hermes \`
  -v "$Root\\Agents:/opt/data" \`
  -v "$Root\\Files:/opt/data/workspace" \`
  ${docker.image} profile list
`;
}

const CI_WORKFLOW = `name: workframe-security

on:
  push:
  pull_request:

jobs:
  security-and-scaffold:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: packages/create-workframe
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Run security audit
        run: python3 scripts/security_audit.py

      - name: Generate scaffold with Node installer
        run: node bin/create-workframe.js --name CiNodeDemo --pack core --out /tmp --ci --force

      - name: Verify generated layout
        run: |
          test -f /tmp/CiNodeDemo/docker-compose.yml
          test -f /tmp/CiNodeDemo/Files/AGENTS.md
          test -f /tmp/CiNodeDemo/SETUP.md
          test -f /tmp/CiNodeDemo/scripts/bootstrap-profiles.sh
          test -f /tmp/CiNodeDemo/scripts/bootstrap-profiles.ps1
          test -f /tmp/CiNodeDemo/scripts/bootstrap-native.sh
          test -f /tmp/CiNodeDemo/scripts/bootstrap-native.ps1
          test -f /tmp/CiNodeDemo/scripts/add-profile.ps1
          test -f /tmp/CiNodeDemo/scripts/open-setup.ps1
          test -f /tmp/CiNodeDemo/workframe-ui/public/index.html
          test -f /tmp/CiNodeDemo/workframe-ui/public/workframe-config.json
          test -f /tmp/CiNodeDemo/workframe-ui/docker/nginx.conf
          test -f /tmp/CiNodeDemo/scripts/open-workframe-ui.ps1
          test -f /tmp/CiNodeDemo/scripts/open-workframe-ui.sh
          test -f /tmp/CiNodeDemo/.github/workflows/workframe-security.yml
          node -e "
            const fs=require('fs');
            for (const dir of ['CiNodeDemo']) {
              const root='/tmp/'+dir;
              const m=JSON.parse(fs.readFileSync(root+'/workframe-manifest.json','utf8'));
              const slug=m.native_agent?.profile_slug;
              if (!slug) throw new Error(dir+': manifest missing native_agent.profile_slug');
              if (!fs.existsSync(root+'/scripts/seed/profiles/'+slug+'/SOUL.md')) throw new Error(dir+': missing native SOUL seed');
              if (!fs.existsSync(root+'/scripts/seed/profiles/'+slug+'/SETUP.md')) throw new Error(dir+': missing native SETUP playbook seed');
              if (m.bootstrap?.default !== 'native') throw new Error(dir+': bootstrap.default should be native');
              if (!m.bootstrap?.open_workframe_ui_script_ps1) throw new Error(dir+': manifest missing open_workframe_ui_script_ps1');
              const cfg=JSON.parse(fs.readFileSync(root+'/workframe-ui/public/workframe-config.json','utf8'));
              if (cfg.native_profile!==slug) throw new Error(dir+': workframe-config native_profile mismatch');
              const chat=fs.readFileSync(root+'/scripts/chat.sh','utf8');
              if (!chat.includes('-p '+slug)) throw new Error(dir+': chat.sh missing native profile');
              if (!chat.includes('--name '+slug+'-chat')) throw new Error(dir+': chat.sh missing named chat container');
              const compose=fs.readFileSync(root+'/docker-compose.yml','utf8');
              if (!compose.includes(slug+'-gateway')) throw new Error(dir+': compose missing named gateway container');
              if (!compose.includes('WORKFRAME_UI_STATIC_DIR:-./workframe-ui/public') && !compose.includes('./workframe-ui/public:/usr/share/nginx/html')) throw new Error(dir+': compose missing workframe-ui mount');
              const start=fs.readFileSync(root+'/scripts/start-install.ps1','utf8');
              if (!start.includes('open-workframe-ui.ps1')) throw new Error(dir+': start-install should open Workframe UI');
              const setup=fs.readFileSync(root+'/SETUP.md','utf8');
              if (!setup.includes('bootstrap-native')) throw new Error(dir+': SETUP.md missing native bootstrap');
            }
          "
`;

function parseArgs(argv) {
  const args = {
    yes: false,
    ci: false,
    force: false,
    telegram: null,
    discord: null,
    runDockerPull: false,
    installGuideOnly: true,
    slot: null,
    installId: null,
    deploy: 'docker',
  };
  const positional = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--yes' || a === '-y') args.yes = true;
    else if (a === '--ci') { args.ci = true; args.yes = true; }
    else if (a === '--force') args.force = true;
    else if (a === '--name') args.name = argv[++i];
    else if (a.startsWith('--name=')) args.name = a.split('=', 2)[1];
    else if (a === '--pack') args.pack = argv[++i];
    else if (a.startsWith('--pack=')) args.pack = a.split('=', 2)[1];
    else if (a === '--out') args.out = argv[++i];
    else if (a.startsWith('--out=')) args.out = a.split('=', 2)[1];
    else if (a === '--telegram') args.telegram = true;
    else if (a === '--no-telegram') args.telegram = false;
    else if (a === '--discord') args.discord = true;
    else if (a === '--no-discord') args.discord = false;
    else if (a === '--run-docker-pull') args.runDockerPull = true;
    else if (a === '--allow-install-actions') args.installGuideOnly = false;
    else if (a === '--no-launch') args.noLaunch = true;
    else if (a === '--wait') args.waitForInstall = true;
    else if (a === '--no-browser') args.noBrowser = true;
    else if (a === '--slot') args.slot = Number(argv[++i]);
    else if (a.startsWith('--slot=')) args.slot = Number(a.split('=', 2)[1]);
    else if (a === '--deploy') args.deploy = argv[++i];
    else if (a.startsWith('--deploy=')) args.deploy = a.split('=', 2)[1];
    else if (a === '--help' || a === '-h') args.help = true;
    else if (a.startsWith('-')) throw new Error(`Unknown option: ${a}`);
    else positional.push(a);
  }
  if (!args.name && positional.length > 0) args.name = positional[0];
  // Project name on CLI → scaffold with defaults (native-only pack, cwd out) and launch Phase B.
  if (args.name && !args.help) {
    args.yes = true;
    args.force = true;
    if (!args.ci) {
      args.installGuideOnly = false;
      args.runDockerPull = true;
    }
  }
  return args;
}

function usage() {
  console.log(`create-workframe

Usage:
  npx create-workframe [ProjectName] [--name MyProject] [--pack native] [--out .] [--deploy auto|native|docker]

Examples:
  npx create-workframe MyProject --out ./projects
  npx create-workframe --name MyProject --pack engineering --out D:/Projects

One command does scaffold + Phase B installer (new terminal). Meta dev: scripts/new-project.ps1 or npm run new-project.

Flags:
  --force                  Overwrite target directory if it exists (validated paths only)
  --ci                     Non-interactive strict mode (implies -y)
  --run-docker-pull        Attempt docker pull after scaffold
  --allow-install-actions  Allow installer to execute shell install actions
  -y, --yes                Non-interactive defaults
  --no-launch              Scaffold only; do not open Phase B installer
  --wait                   Run Phase B here and fail if installation fails
  --no-browser             With --wait, do not open the system browser
`);
}

function readText(file) { return fs.readFileSync(file, 'utf8'); }
function writeText(file, content) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content, 'utf8');
}

function copyWorkframeApiTemplate(target) {
  const src = path.join(PKG_ROOT, 'workframe-api');
  const dest = path.join(target, 'workframe-api');
  if (!fs.existsSync(src)) throw new Error(`Missing workframe-api template: ${src}`);
  fs.cpSync(src, dest, {
    recursive: true,
    filter: (from) => {
      const base = path.basename(from);
      return base !== '__pycache__' && !base.endsWith('.pyc');
    },
  });
}

function copyWorkframeSupervisorTemplate(target) {
  const src = path.join(PKG_ROOT, 'workframe-supervisor');
  const dest = path.join(target, 'workframe-supervisor');
  if (!fs.existsSync(src)) {
    throw new Error(`Missing workframe-supervisor template: ${src}. Run sync-canonical-to-package.mjs`);
  }
  fs.cpSync(src, dest, {
    recursive: true,
    filter: (from) => {
      const base = path.basename(from);
      return base !== '__pycache__' && !base.endsWith('.pyc');
    },
  });
}

function copyWorkframeUiTemplate(target, packProfiles) {
  const src = path.join(PKG_ROOT, 'workframe-ui');
  const dest = path.join(target, 'workframe-ui');
  const publicSrc = path.join(src, 'public');
  if (!fs.existsSync(publicSrc) || !fs.existsSync(path.join(publicSrc, 'index.html'))) {
    throw new Error(
      'Missing bundled Workframe UI. Run: node packages/create-workframe/scripts/bundle-workframe-ui.mjs',
    );
  }
  fs.mkdirSync(path.join(target, 'docker'), { recursive: true });
  fs.mkdirSync(path.join(dest, 'docker'), { recursive: true });
  writeText(path.join(dest, 'docker', 'nginx.conf'), nginxConfYaml(packProfiles));
  writeText(path.join(target, 'docker', 'dashboard-proxy.conf'), dashboardProxyConf());
  writeText(path.join(target, 'docker', 'cont-init-workspace-link.sh'), contInitWorkspaceLinkSh());
  fs.cpSync(publicSrc, path.join(dest, 'public'), { recursive: true });
}

function copyTree(src, dst) {
  if (!fs.existsSync(src)) return;
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const from = path.join(src, entry.name);
    const to = path.join(dst, entry.name);
    if (entry.isDirectory()) copyTree(from, to);
    else if (entry.isFile()) {
      fs.mkdirSync(path.dirname(to), { recursive: true });
      fs.copyFileSync(from, to);
    }
  }
}

function slugify(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'workframe';
}

function dockerContainerNames(projectName) {
  const slug = slugify(projectName);
  return {
    slug,
    stack: slug,
    displayName: projectName,
    image: 'nousresearch/hermes-agent:latest',
    network: `${slug}-net`,
    gateway: `${slug}-gateway`,
    dashboard: `${slug}-dashboard`,
    workframeApi: `${slug}-workframe-api`,
    workframeSupervisor: `${slug}-workframe-supervisor`,
    workframe: `${slug}-workframe`,
    chat: `${slug}-chat`,
    setup: `${slug}-setup`,
    controlNetwork: `${slug}-control-net`,
    profileDashboard: (profile) => `${slug}-dashboard-${profile}`,
    bootstrapProfile: (profile) => `${slug}-bootstrap-${profile}`,
    bootstrapProfileShow: (profile) => `${slug}-bootstrap-${profile}-show`,
    bootstrapUse: `${slug}-bootstrap-use`,
    bootstrapList: `${slug}-bootstrap-list`,
  };
}

function nativeProfileSlug(projectName) {
  return `${slugify(projectName)}-agent`;
}

function nativeAgentName(projectName) {
  return `${projectName} Agent`;
}

function renderContext(projectName, ports = null) {
  const projectSlug = slugify(projectName);
  return {
    projectName,
    projectSlug,
    nativeProfileSlug: nativeProfileSlug(projectName),
    nativeAgentName: nativeAgentName(projectName),
    dashboardPort: ports?.dashboard != null ? String(ports.dashboard) : '',
  };
}

function render(text, ctx) {
  const context = typeof ctx === 'string' ? renderContext(ctx) : ctx;
  let out = text;
  for (const [key, value] of Object.entries(context)) {
    out = out.replaceAll(`{${key}}`, value);
  }
  return out;
}

function resolvePackProfiles(baseProfiles, projectName) {
  const native = nativeProfileSlug(projectName);
  return [...new Set(baseProfiles.map((p) => (p === PROJECT_AGENT_SLOT ? native : p)))];
}

function profileDescription(profile, projectName) {
  if (profile === nativeProfileSlug(projectName)) {
    return `${nativeAgentName(projectName)}: host, concierge, project manager, orchestrator, and Workframe admin.`;
  }
  return PROFILE_DESCRIPTIONS[profile] ?? `${profile} specialist profile.`;
}

function profileSoulSource(profile, projectName) {
  const templateDir = profile === nativeProfileSlug(projectName) ? NATIVE_SOUL_TEMPLATE : profile;
  return path.join(PROFILES_DIR, templateDir, 'SOUL.md');
}

function profileAgentsSource(profile, projectName) {
  const templateDir = profile === nativeProfileSlug(projectName) ? NATIVE_SOUL_TEMPLATE : profile;
  return path.join(PROFILES_DIR, templateDir, 'AGENTS.md');
}

function profileSetupSource() {
  return path.join(PROFILES_DIR, NATIVE_SOUL_TEMPLATE, 'SETUP.md');
}

function nativeConfigYaml(projectName, agentName, personality) {
  const personalityLine = personality ? `# Personality: ${personality}
` : "";
  return `${personalityLine}model:
  default: google/gemini-2.5-flash
  provider: openrouter
  base_url: https://openrouter.ai/api/v1
  api_mode: chat_completions
fallback_providers:
- provider: openrouter
  model: anthropic/claude-sonnet-4.5
- provider: openrouter
  model: meta-llama/llama-3.3-70b-instruct:free
providers: {}
credential_pool_strategies: {}
toolsets:
  - hermes-cli
  - terminal
agent:
  max_turns: 90
  gateway_timeout: 1800
  restart_drain_timeout: 180
  api_max_retries: 3
  service_tier: ''
  tool_use_enforcement: auto
  task_completion_guidance: true
  environment_probe: true
  gateway_timeout_warning: 900
  clarify_timeout: 600
  gateway_notify_interval: 180
  gateway_auto_continue_freshness: 3600
  image_input_mode: auto
  disabled_toolsets: []
  verbose: false
  reasoning_effort: medium
terminal:
  backend: local
  modal_mode: auto
  cwd: /workspace
  timeout: 180
web:
  backend: ''
  search_backend: ''
  extract_backend: ''
browser:
  inactivity_timeout: 120
  allow_private_urls: false
file_read_max_chars: 100000
tool_output:
  max_bytes: 50000
  max_lines: 2000
  max_line_length: 2000
compression:
  enabled: true
  threshold: 0.5
  target_ratio: 0.2
openrouter:
  response_cache: true
  response_cache_ttl: 300
display:
  streaming: true
  language: en
  show_reasoning: false
skills:
  external_dirs: []
  template_vars: true
  inline_shell: false
context:
  engine: compressor
delegation:
  inherit_mcp_toolsets: true
  max_iterations: 50
  child_timeout_seconds: 600
  max_spawn_depth: 1
  orchestrator_enabled: false
gateway:
  strict: false
  trust_recent_files: true
  trust_recent_files_seconds: 600
sessions:
  auto_prune: true
  retention_days: 14
logging:
  level: INFO
memory:
  memory_enabled: true
  user_profile_enabled: true
platforms:
  api_server:
    enabled: true
    extra:
      host: 0.0.0.0
      port: 18639
      key: workframe-local-key
onboarding:
  seen:
    tool_progress_prompt: true
`;
}

function loadPacks() { return JSON.parse(readText(PACKS_PATH)).packs ?? {}; }

function listAllProfiles() {
  return fs.readdirSync(PROFILES_DIR, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort();
}

function listSpecialistProfiles() {
  return listAllProfiles().filter((p) => p !== NATIVE_SOUL_TEMPLATE);
}

function listProfilesToSeed(projectName) {
  const native = nativeProfileSlug(projectName);
  return [native, ...listSpecialistProfiles()];
}

function openInstallUiPs1(ports) {
  return `$ErrorActionPreference = 'SilentlyContinue'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$UiPort = '${ports.ui}'
$envFile = Join-Path $Root '.env'
if (Test-Path $envFile) {
  $line = Get-Content $envFile | Where-Object { $_ -match '^WORKFRAME_UI_PORT=' } | Select-Object -Last 1
  if ($line) { $UiPort = ($line -split '=', 2)[1].Trim() }
}
$url = "http://127.0.0.1:$UiPort/install"
Write-Host "Opening install UI: $url" -ForegroundColor Cyan
Start-Process $url | Out-Null
`;
}

function openInstallUiSh(ports) {
  return `#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

UI_PORT="${ports.ui}"
if [ -f "$ROOT/.env" ]; then
  val=$(grep -E '^WORKFRAME_UI_PORT=' "$ROOT/.env" | tail -n1 | cut -d= -f2- || true)
  if [ -n "$val" ]; then UI_PORT="$val"; fi
fi
URL="http://127.0.0.1:\${UI_PORT}/install"
echo "Opening install UI: $URL"
if command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then open "$URL" >/dev/null 2>&1 || true
else echo "Open manually: $URL"
fi
`;
}

function seedNativeFromPackagePs1(nativeProfile) {
  return `$seedBase = Join-Path $Root "scripts\\seed\\profiles\\${nativeProfile}"
$profileDir = Join-Path $Root "Agents\\profiles\\${nativeProfile}"
$profileConfig = Join-Path $profileDir "config.yaml"
if (-not (Test-Path $profileConfig) -and (Test-Path (Join-Path $seedBase "config.yaml"))) {
  Write-Host "Seeding ${nativeProfile} from package (UI-first install)..." -ForegroundColor DarkGray
  New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
  Copy-Item -Path (Join-Path $seedBase '*') -Destination $profileDir -Recurse -Force
  $homeSoul = Join-Path $Root "Agents\\SOUL.md"
  $seedSoul = Join-Path $seedBase "SOUL.md"
  if (Test-Path $seedSoul) { Copy-Item $seedSoul $homeSoul -Force }
}
`;
}

function seedNativeFromPackageSh(nativeProfile) {
  return `seed_base="$ROOT/scripts/seed/profiles/${nativeProfile}"
profile_dir="$ROOT/Agents/profiles/${nativeProfile}"
profile_config="$profile_dir/config.yaml"
if [ ! -f "$profile_config" ] && [ -f "$seed_base/config.yaml" ]; then
  echo "Seeding ${nativeProfile} from package (UI-first install)..."
  mkdir -p "$profile_dir"
  cp -R "$seed_base/." "$profile_dir/"
  if [ -f "$seed_base/SOUL.md" ]; then cp "$seed_base/SOUL.md" "$ROOT/Agents/SOUL.md"; fi
fi
`;
}

function openWorkframeUiPs1(ports) {
  return `$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$UiPort = '${ports.ui}'
$envFile = Join-Path $Root '.env'
if (Test-Path $envFile) {
  $line = Get-Content $envFile | Where-Object { $_ -match '^WORKFRAME_UI_PORT=' } | Select-Object -Last 1
  if ($line) { $UiPort = ($line -split '=', 2)[1].Trim() }
}

Write-Host 'Starting Workframe stack (if needed)...'
docker compose up -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$url = "http://127.0.0.1:$UiPort/"
Write-Host "Opening Workframe UI: $url"
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
  try {
    $null = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
    $boot = Invoke-RestMethod -Uri "http://127.0.0.1:$UiPort/api/hermes/bootstrap" -TimeoutSec 3
    if ($boot.ok) { break }
  } catch {
    Start-Sleep -Seconds 2
  }
}
try {
  Start-Process $url | Out-Null
} catch {
  Write-Host "Open manually: $url"
}
`;
}

function openWorkframeUiSh(ports) {
  return `#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

UI_PORT="${ports.ui}"
if [ -f "$ROOT/.env" ]; then
  val=$(grep -E '^WORKFRAME_UI_PORT=' "$ROOT/.env" | tail -n1 | cut -d= -f2- || true)
  if [ -n "$val" ]; then UI_PORT="$val"; fi
fi

echo "Starting Workframe stack (if needed)..."
docker compose up -d

URL="http://127.0.0.1:\${UI_PORT}/"
echo "Opening Workframe UI: $URL"
for _ in $(seq 1 45); do
  if curl -fsS -o /dev/null "$URL" 2>/dev/null && curl -fsS "$URL/api/hermes/bootstrap" 2>/dev/null | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then break; fi
  sleep 2
done
if command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then open "$URL" >/dev/null 2>&1 || true
else echo "Open manually: $URL"
fi
`;
}

function prepareTarget(target, force) {
  if (fs.existsSync(target)) {
    if (!force) throw new Error(`Target already exists: ${target}. Use --force to overwrite.`);
    const stat = fs.statSync(target);
    if (!stat.isDirectory()) throw new Error(`Refusing to remove non-directory target: ${target}`);
    fs.rmSync(target, { recursive: true, force: true });
  }
}

function onboardingDoc({ projectName, pack, profiles, specialists, telegram, discord, ports, nativeProfileSlug: nativeSlug, nativeAgentName: nativeName, docker }) {
  const tg = telegram ? 'Enabled in plan (optional integration chosen).' : 'Skipped (can enable later).';
  const dc = discord ? 'Enabled in plan (optional integration chosen).' : 'Skipped (can enable later).';
  return `# ${projectName} setup

Operator guide for this **generated project instance**. Workframe method docs live in the meta installer repo — not here.

## Install phases (Workframe method)

| Phase | What | Command |
|-------|------|---------|
| A | Scaffold | Already done (\`create-workframe\`) |
| B | Credentials + minimal boot | Hermes setup → \`bootstrap-native\` |
| C | Agent-guided setup | Chat with **${nativeName}** — installs specialists, Discord/TG |

## Boot order (Phase B)

| Step | Command | Purpose |
|------|---------|---------|
| **All-in-one** | \`./scripts/start-install.sh\` or \`./scripts/start-install.ps1\` | Opens \`/install\` in browser → Docker stack → onboarding UI |
| New terminal | \`./scripts/launch-install.sh\` or \`./scripts/launch-install.ps1\` | Same, TTY-friendly |
| After Hermes setup only | \`./scripts/install.sh\` or \`./scripts/install.ps1\` | bootstrap-native + compose + open chat |
| Phase C chat | \`./scripts/chat.sh\` / \`./scripts/chat.ps1\` or browser \`/chat\` | **${nativeName}** (dashboard runs with \`--tui\`) |

> **Do not** run bare \`docker run ... hermes-agent:latest\` without \`-p ${nativeSlug}\`.
> That starts generic default Hermes (OWL) — not **${nativeName}**.

### Secure credentials

**macOS / Linux**

\`\`\`bash
./scripts/start-install.sh      # full Phase B (recommended)
./scripts/launch-install.sh     # same, new terminal
./scripts/open-setup.sh         # credentials / dashboard link only
\`\`\`

**Windows**

\`\`\`powershell
.\\scripts\\start-install.ps1     # full install (UI-first, recommended)
.\\scripts\\launch-install.ps1   # same, new window
.\\scripts\\open-setup.ps1         # credentials / dashboard link only
\`\`\`

## Native agent

- **Display name:** ${nativeName}
- **Hermes profile:** \`${nativeSlug}\`
- **Setup playbook (after bootstrap):** \`Agents/profiles/${nativeSlug}/SETUP.md\`

## Add specialists (Phase C — or run yourself)

**macOS / Linux:** \`./scripts/add-profile.sh dev\` · **Windows:** \`.\\scripts\\add-profile.ps1 dev\`

Catalog: ${specialists.join(', ')}

**Reference pack fallback:** \`./scripts/bootstrap-profiles.sh\` or \`.\\scripts\\bootstrap-profiles.ps1\`

Creates: ${profiles.join(', ')}

## 1) Phase B — complete boot (recommended)

\`create-workframe\` launches the installer automatically. Or run manually:

\`\`\`bash
./scripts/start-install.sh    # macOS / Linux
\`\`\`

\`\`\`powershell
.\\scripts\\start-install.ps1   # Windows
\`\`\`

Runs: Hermes setup (interactive) → \`bootstrap-native\` → \`docker compose up -d\` → browser opens \`/chat\`.

## 1b) Or finish after Hermes setup alone

\`\`\`bash
./scripts/install.sh
\`\`\`

\`\`\`powershell
.\\scripts\\install.ps1
\`\`\`

## 2) Chat with ${nativeName} (Phase C)

\`\`\`bash
./scripts/chat.sh
\`\`\`

\`\`\`powershell
.\\scripts\\chat.ps1
\`\`\`

${nativeName} reads the setup playbook and can walk you through Discord/TG channel binding (tutorial-style: one channel per specialist).

## 4) Stack (gateway + dashboard + workframe-api + Workframe UI)

\`\`\`bash
docker compose up -d
\`\`\`

| Service | URL | Container | Role |
|---------|-----|-----------|------|
| **Browser chat (TUI)** | http://127.0.0.1:${ports.dashboard}/chat | \`${docker.dashboard}\` | Hermes embedded terminal chat |
| **Workframe API** | http://127.0.0.1:${ports.api} | \`${docker.workframeApi}\` | UI backend + profile control plane |
| **Workframe UI** | http://127.0.0.1:${ports.ui} | \`${docker.workframe}\` | Product shell — chat, files, activity |
| Hermes dashboard | http://127.0.0.1:${ports.dashboard} | \`${docker.dashboard}\` | Ops: profiles, keys, logs |
| Gateway (API) | http://127.0.0.1:${ports.gateway} | \`${docker.gateway}\` | Discord / Telegram / API |

Open Workframe UI: \`./scripts/open-workframe-ui.sh\` or \`.\\scripts\\open-workframe-ui.ps1\`

Open Workframe API: \`./scripts/open-workframe-api.sh\` or \`.\\scripts\\open-workframe-api.ps1\`

Update Hermes (Docker): \`./scripts/update-hermes.sh\` or \`.\\scripts\\update-hermes.ps1\`

## 6) Workframe CLI (project lifecycle)

A \`workframe.mjs\` CLI is included in \`scripts/\` for ongoing project management:

\`\`\`bash
node scripts/workframe.mjs doctor       # Validate layout, compose, manifest, Docker runtime
node scripts/workframe.mjs setup        # Open Hermes setup (credentials)
node scripts/workframe.mjs start        # Start full stack (docker compose up -d)
node scripts/workframe.mjs stop         # Stop all stack containers
node scripts/workframe.mjs restart      # Restart the full stack
node scripts/workframe.mjs status       # Show running containers
node scripts/workframe.mjs logs [-f]    # Tail gateway logs
node scripts/workframe.mjs ui           # Open Workframe UI in browser
\`\`\`

Run from the project root (where \`workframe-manifest.json\` lives).

## 5) Chat integrations (optional)
- Telegram: ${tg} — control channel → **${nativeSlug}**
- Discord: ${dc} — \`#dev\` → \`dev\`, etc. (exclusive channel ID binds)

## Agent pack
- Pack: **${pack}**
- Pack reference set: ${profiles.join(', ')}
- Specialist catalog: ${specialists.join(', ')}

## Layout
- \`Files/\` → \`/workspace\` (project truth — commit this)
- \`Agents/\` → \`/opt/data\` (runtime only — never commit)

## Requirements
- Docker (Desktop on macOS/Windows, Engine on Linux)
- Interactive terminal for Hermes setup (\`-it\`)
- Node.js for \`npx create-workframe\` (scaffold only)
`;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) return usage();

  const packs = loadPacks();
  const packNames = Object.keys(packs).sort();
  const defaults = {
    name: args.name ?? 'workframe-app',
    agentName: null, // null means "use default derived from project name"
    personality: '',
    pack: args.pack ?? 'native',
    out: args.out ?? process.cwd(),
    telegram: args.telegram ?? false,
    discord: args.discord ?? false,
  };

  if (!packNames.includes(defaults.pack)) {
    throw new Error(`Unknown pack '${defaults.pack}'. Available: ${packNames.join(', ')}`);
  }

  const rl = readline.createInterface({ input, output });
  try {
    let name = defaults.name;
    let pack = defaults.pack;
    let out = defaults.out;
    let telegram = defaults.telegram;
    let discord = defaults.discord;
    let agentName = defaults.agentName;
    let personality = defaults.personality;

    if (!args.yes) {
      name = (await rl.question(`Project name [${name}]: `)).trim() || name;
      const suggestedAgentName = nativeAgentName(name);
      const agentNameInput = (await rl.question(`Agent name [${suggestedAgentName}]: `)).trim();
      agentName = agentNameInput || null; // null = use default
      const personalityInput = (await rl.question(`Agent personality (optional, e.g. "friendly, methodical, builder"): `)).trim();
      personality = personalityInput || defaults.personality;
      pack = (await rl.question(`Agent pack ${packNames.join('/')} [${pack}]: `)).trim() || pack;
      out = (await rl.question(`Output directory [${out}]: `)).trim() || out;
      if (args.telegram === null) telegram = /^y(es)?$/i.test((await rl.question('Enable Telegram steps? [y/N]: ')).trim());
      if (args.discord === null) discord = /^y(es)?$/i.test((await rl.question('Enable Discord steps? [y/N]: ')).trim());
    }

    if (!packNames.includes(pack)) throw new Error(`Unknown pack '${pack}'. Available: ${packNames.join(', ')}`);

    const { target, name: safeName } = resolveProjectTarget(out, name);

    const allProfiles = listSpecialistProfiles();
    const baseProfiles = packs[pack].profiles || [];
    const extraProfiles = [];

    if (!args.yes) {
      const extra = (await rl.question(`Optional extra profiles from [${allProfiles.join(', ')}], or blank: `)).trim();
      if (extra) {
        for (const prof of extra.split(',').map((v) => v.trim()).filter(Boolean)) {
          if (!allProfiles.includes(prof)) throw new Error(`Unknown profile '${prof}'. Allowed: ${allProfiles.join(', ')}`);
          extraProfiles.push(prof);
        }
      }
    }

    const profiles = resolvePackProfiles([...baseProfiles, ...extraProfiles], safeName);
    const specialists = listSpecialistProfiles();
    const slug = slugify(safeName);
    const install = await allocateInstall({
      projectName: safeName,
      preferredSlot: args.slot ?? null,
      installId: args.installId ?? null,
    });
    const ports = install.ports;
    const effectiveAgentName = agentName || nativeAgentName(safeName);
    const ctx = { ...renderContext(safeName, ports), nativeAgentName: effectiveAgentName, agentPersonality: personality };
    const nativeSlug = ctx.nativeProfileSlug;
    const nativeName = effectiveAgentName;
    const docker = dockerContainerNames(safeName);
    const deploy = resolveDeployMode(args.deploy ?? 'docker');
    const hermesHome = deploy === 'native' ? detectHermesHome() : '';
    if (deploy === 'native' && !hermesHome) {
      throw new Error('Native deploy needs an existing Hermes install (config.yaml). Run hermes setup first, or use --deploy docker.');
    }
    const filesRoot = path.join(target, 'Files');

    prepareTarget(target, args.force);

    fs.mkdirSync(filesRoot, { recursive: true });
    fs.mkdirSync(path.join(target, 'Agents'), { recursive: true });
    writeText(path.join(target, 'Agents', '.gitkeep'), '');
    if (deploy === 'native') {
      writeText(
        path.join(target, 'NATIVE-HERMES.txt'),
        `Native deploy — host Hermes detected at:\n${hermesHome}\n\nDocker stack still uses ./Agents at /opt/data (isolated install runtime).\nOptional: run host gateway with hermes gateway run using host HERMES_HOME.\n`,
      );
    }

    const workspaceReadme = readText(path.join(PKG_ROOT, 'rules', 'workspace-README.md')).replace(
      /\{projectName\}/g,
      safeName,
    );
    writeText(path.join(filesRoot, 'README.md'), workspaceReadme);
    writeText(path.join(filesRoot, 'AGENTS.md'), render(readText(path.join(PKG_ROOT, 'rules', 'AGENTS.md')), ctx));
    writeText(path.join(filesRoot, '.hermes.md'), render(readText(path.join(PKG_ROOT, 'rules', '.hermes.md')), ctx));

    copyWorkframeApiTemplate(target);
    copyWorkframeSupervisorTemplate(target);
    copyWorkframeUiTemplate(target, [nativeSlug]);
    writeText(
      path.join(target, 'workframe-ui', 'public', 'workframe-config.json'),
      `${JSON.stringify({ project_name: safeName, native_profile: nativeSlug, package_version: PKG_VERSION }, null, 2)}\n`,
    );

    writeText(path.join(target, 'SETUP.md'), onboardingDoc({
      projectName: safeName,
      pack,
      profiles,
      specialists,
      telegram,
      discord,
      ports,
      nativeProfileSlug: nativeSlug,
      nativeAgentName: nativeName,
      docker,
    }));

    const seedProfiles = listProfilesToSeed(safeName);
    const setupTemplate = profileSetupSource();
    if (!fs.existsSync(setupTemplate)) throw new Error(`Missing native setup playbook: ${setupTemplate}`);

    for (const prof of seedProfiles) {
      const src = profileSoulSource(prof, safeName);
      if (!fs.existsSync(src)) throw new Error(`Missing profile template: ${src}`);
      writeText(
        path.join(target, 'scripts', 'seed', 'profiles', prof, 'SOUL.md'),
        render(readText(src), ctx),
      );
      const agentsSrc = profileAgentsSource(prof, safeName);
      if (fs.existsSync(agentsSrc)) {
        writeText(
          path.join(target, 'scripts', 'seed', 'profiles', prof, 'AGENTS.md'),
          render(readText(agentsSrc), ctx),
        );
      }
      if (prof === nativeSlug) {
        writeText(
          path.join(target, 'scripts', 'seed', 'profiles', prof, 'SETUP.md'),
          render(readText(setupTemplate), ctx),
        );
        // Generate config.yaml for native profile
        writeText(
          path.join(target, 'scripts', 'seed', 'profiles', prof, 'config.yaml'),
          nativeConfigYaml(safeName, effectiveAgentName, personality),
        );
        const nativeSkillsSrc = path.join(PKG_ROOT, 'profiles', 'workframe-agent', 'skills');
        if (fs.existsSync(nativeSkillsSrc)) {
          copyTree(nativeSkillsSrc, path.join(target, 'scripts', 'seed', 'profiles', prof, 'skills'));
        }
      }
    }

    const agentTemplateSrc = path.join(PKG_ROOT, 'scripts', 'seed', 'agent-template', 'SOUL.md');
    if (fs.existsSync(agentTemplateSrc)) {
      writeText(path.join(target, 'scripts', 'seed', 'agent-template', 'SOUL.md'), readText(agentTemplateSrc));
    }
    const agentAgentsSrc = path.join(PKG_ROOT, 'scripts', 'seed', 'agent-template', 'AGENTS.md');
    if (fs.existsSync(agentAgentsSrc)) {
      writeText(path.join(target, 'scripts', 'seed', 'agent-template', 'AGENTS.md'), readText(agentAgentsSrc));
    }

    writeText(path.join(target, '.gitignore'), GITIGNORE);
    writeText(path.join(target, '.dockerignore'), DOCKERIGNORE);
    writeText(path.join(target, '.env.example'), envFileContent(install, { example: true, nativeProfile: nativeSlug, deploy, hermesHome }) + `WORKFRAME_HOST_COMPOSE_DIR=/path/to/${slug}\nWORKFRAME_HOST_PROJECT_ROOT=/path/to/${slug}\n`);
    const hostRoot = target.replace(/\\/g, '/');
    writeText(
      path.join(target, '.env'),
      envFileContent(install, { nativeProfile: nativeSlug, deploy, hermesHome })
        + `WORKFRAME_HOST_COMPOSE_DIR=${hostRoot}\nWORKFRAME_HOST_PROJECT_ROOT=${hostRoot}\n`,
    );
    writeText(path.join(target, 'docker-compose.yml'), dockerComposeYaml(safeName, docker, nativeSlug, [nativeSlug], install.installId, hermesHome));
    writeText(path.join(target, 'docker-compose.host-bindings.yml'), dockerComposeHostBindingsYaml(docker));
    writeText(path.join(target, 'docker-compose.public.yml'), dockerComposePublicYaml(docker));
    const publicDeployDoc = path.join(PKG_ROOT, 'docs', 'PUBLIC_DEPLOY.md');
    if (fs.existsSync(publicDeployDoc)) {
      writeText(path.join(target, 'docs', 'PUBLIC_DEPLOY.md'), readText(publicDeployDoc));
    }
    writeText(
      path.join(target, 'docker-compose.dev-authority.yml'),
      `# NEVER use on public/VPS hosts — trusted local dev only (docker.sock on workframe-api).\n# Trusted local dev — API admin updates (docker.sock on workframe-api)\nname: ${docker.stack}\n\nservices:\n  workframe-api:\n    volumes:\n      - ./workframe-api/public:/app/public:ro\n      - ./workframe-api:/app\n      - ./workframe-api/data:/app/data\n      - ./Agents:/opt/data\n      - ./Files:${WORKSPACE_DATA_MOUNT}\n      - ./scripts:/opt/install/scripts:ro\n      - .:/project\n      - /var/run/docker.sock:/var/run/docker.sock\n    environment:\n      - WORKFRAME_ENABLE_ADMIN_UPDATES=1\n      - WORKFRAME_COMPOSE_DIR=/project\n      - WORKFRAME_PROJECT_ROOT=/project\n`,
    );

    writeText(
      path.join(target, 'README.md'),
      `# ${safeName}\n\nWorkframe project generated by \`create-workframe\`.\n\n## Quick start\n\n\`create-workframe\` opens the installer automatically. Your browser lands on **/install** while Docker starts — then the onboarding UI walks you through mode, SMTP, and setup.\n\n**macOS / Linux**\n\n\`\`\`bash\n./scripts/start-install.sh\n# or open install UI anytime:\n./scripts/open-install-ui.sh\n\`\`\`\n\n**Windows**\n\n\`\`\`powershell\n.\\scripts\\start-install.ps1\n.\\scripts\\open-install-ui.ps1\n\`\`\`\n\nPrimary surface: **Workframe UI** at \`http://127.0.0.1:WORKFRAME_UI_PORT/install\` then \`/onboarding\`. LLM keys are configured in onboarding — no Hermes TUI required.\n\nRe-bootstrap only: \`./scripts/install.sh\` or \`.\\scripts\\install.ps1\`\n\n## Project management (workframe CLI)\n\n\`\`\`bash\nnode scripts/workframe.mjs doctor       # Validate layout, compose, manifest, Docker runtime\nnode scripts/workframe.mjs setup        # Open Hermes setup (credentials)\nnode scripts/workframe.mjs start        # Start full stack (docker compose up -d)\nnode scripts/workframe.mjs stop         # Stop all stack containers\nnode scripts/workframe.mjs restart      # Restart the full stack\nnode scripts/workframe.mjs status       # Show running containers\nnode scripts/workframe.mjs logs [-f]    # Tail gateway logs\nnode scripts/workframe.mjs ui           # Open Workframe UI in browser\n\`\`\`\n\nRun from the project root (where \`workframe-manifest.json\` lives).\n\nWorkspace: \`Files/\` · Runtime: \`Agents/\`\n`,
    );

    writeText(path.join(target, 'scripts', 'setup.sh'), setupSh(docker, nativeSlug, nativeName));
    fs.chmodSync(path.join(target, 'scripts', 'setup.sh'), 0o755);
    writeText(path.join(target, 'scripts', 'setup.ps1'), setupPs1(docker, nativeSlug, nativeName));
    writeText(path.join(target, 'scripts', 'bootstrap-native.sh'), bootstrapNativeSh(nativeSlug, safeName, docker));
    fs.chmodSync(path.join(target, 'scripts', 'bootstrap-native.sh'), 0o755);
    writeText(path.join(target, 'scripts', 'bootstrap-native.ps1'), bootstrapNativePs1(nativeSlug, safeName, docker));
    writeText(path.join(target, 'scripts', 'bootstrap-profiles.sh'), bootstrapProfilesSh(profiles, safeName, nativeSlug, docker));
    fs.chmodSync(path.join(target, 'scripts', 'bootstrap-profiles.sh'), 0o755);
    writeText(path.join(target, 'scripts', 'bootstrap-profiles.ps1'), bootstrapProfilesPs1(profiles, safeName, nativeSlug, docker));
    writeText(path.join(target, 'scripts', 'add-profile.sh'), addProfileSh(nativeSlug, specialists, safeName, docker));
    fs.chmodSync(path.join(target, 'scripts', 'add-profile.sh'), 0o755);
    writeText(path.join(target, 'scripts', 'add-profile.ps1'), addProfilePs1(nativeSlug, specialists, safeName, docker));
    writeText(path.join(target, 'scripts', 'open-setup.sh'), openSetupSh(docker, ports));
    fs.chmodSync(path.join(target, 'scripts', 'open-setup.sh'), 0o755);
    writeText(path.join(target, 'scripts', 'open-setup.ps1'), openSetupPs1(docker, ports));
    writeText(path.join(target, 'scripts', 'install.sh'), installSh(nativeSlug, nativeName, docker, ports));
    fs.chmodSync(path.join(target, 'scripts', 'install.sh'), 0o755);
    writeText(path.join(target, 'scripts', 'install.ps1'), installPs1(nativeSlug, nativeName, docker, ports));
    writeText(path.join(target, 'scripts', 'start-install.sh'), startInstallSh(docker, nativeSlug, nativeName, ports));
    fs.chmodSync(path.join(target, 'scripts', 'start-install.sh'), 0o755);
    writeText(path.join(target, 'scripts', 'start-install.ps1'), startInstallPs1(docker, nativeSlug, nativeName, ports));
    writeText(path.join(target, 'scripts', 'launch-install.ps1'), launchInstallPs1());
    writeText(path.join(target, 'scripts', 'launch-install.sh'), launchInstallSh());
    fs.chmodSync(path.join(target, 'scripts', 'launch-install.sh'), 0o755);
    writeText(path.join(target, 'scripts', 'open-chat.ps1'), openChatPs1(ports));
    writeText(path.join(target, 'scripts', 'open-chat.sh'), openChatSh(ports));
    fs.chmodSync(path.join(target, 'scripts', 'open-chat.sh'), 0o755);
    writeText(path.join(target, 'scripts', 'open-workframe-api.ps1'), openWorkframeApiPs1(ports));
    writeText(path.join(target, 'scripts', 'open-workframe-ui.ps1'), openWorkframeUiPs1(ports));
    writeText(path.join(target, 'scripts', 'open-install-ui.ps1'), openInstallUiPs1(ports));
    writeText(path.join(target, 'scripts', 'open-workframe-api.sh'), openWorkframeApiSh(ports));
    writeText(path.join(target, 'scripts', 'open-workframe-ui.sh'), openWorkframeUiSh(ports));
    writeText(path.join(target, 'scripts', 'open-install-ui.sh'), openInstallUiSh(ports));
    fs.chmodSync(path.join(target, 'scripts', 'open-workframe-api.sh'), 0o755);
    fs.chmodSync(path.join(target, 'scripts', 'open-workframe-ui.sh'), 0o755);
    fs.chmodSync(path.join(target, 'scripts', 'open-install-ui.sh'), 0o755);
    writeText(path.join(target, 'scripts', 'update-hermes.ps1'), updateHermesPs1(profiles));
    writeText(path.join(target, 'scripts', 'update-hermes.sh'), updateHermesSh(profiles));
    fs.chmodSync(path.join(target, 'scripts', 'update-hermes.sh'), 0o755);
    for (const scriptName of ['apply-update-hermes.sh', 'apply-update-workframe.sh', 'restart-gateway-hermes.sh', 'compose-docker-host.sh', 'setup-stack-secrets.sh', 'bootstrap-workspace-link.sh', 'verify-public-deploy.sh', 'fix-zk-encryption-key.sh']) {
      const src = path.join(PKG_ROOT, 'scripts', scriptName);
      if (fs.existsSync(src)) {
        fs.copyFileSync(src, path.join(target, 'scripts', scriptName));
        fs.chmodSync(path.join(target, 'scripts', scriptName), 0o755);
      }
    }
    const lifecycleSrc = path.join(PKG_ROOT, 'scripts', 'agent-lifecycle.mjs');
    if (fs.existsSync(lifecycleSrc)) {
      writeText(path.join(target, 'scripts', 'agent-lifecycle.mjs'), readText(lifecycleSrc));
    }
    const registryLib = path.join(PKG_ROOT, 'scripts', 'lib', 'workframe-registry.mjs');
    if (fs.existsSync(registryLib)) {
      fs.mkdirSync(path.join(target, 'scripts', 'lib'), { recursive: true });
      writeText(path.join(target, 'scripts', 'lib', 'workframe-registry.mjs'), readText(registryLib));
    }
    const identityLib = path.join(PKG_ROOT, 'scripts', 'lib', 'install-identity.mjs');
    if (fs.existsSync(identityLib)) {
      fs.mkdirSync(path.join(target, 'scripts', 'lib'), { recursive: true });
      writeText(path.join(target, 'scripts', 'lib', 'install-identity.mjs'), readText(identityLib));
    }
    // Copy workframe CLI for global project management (doctor, setup, stop, start, restart, status, logs, ui)
    const workframeCliSrc = path.join(PKG_ROOT, 'bin', 'workframe.js');
    if (fs.existsSync(workframeCliSrc)) {
      writeText(path.join(target, 'scripts', 'workframe.mjs'), readText(workframeCliSrc));
      fs.chmodSync(path.join(target, 'scripts', 'workframe.mjs'), 0o755);
    }
    const presetDirs = ['agents', 'users', 'logos'];
    const publicAssets = path.join(PKG_ROOT, 'workframe-ui', 'public', 'assets');
    for (const dir of presetDirs) {
      const src = path.join(publicAssets, dir);
      if (!fs.existsSync(src)) continue;
      const seedDir = path.join(target, 'scripts', 'seed', 'assets', dir);
      fs.mkdirSync(seedDir, { recursive: true });
      fs.cpSync(src, seedDir, { recursive: true });
    }
    writeText(path.join(target, 'scripts', 'chat.sh'), chatSh(nativeSlug, docker));
    fs.chmodSync(path.join(target, 'scripts', 'chat.sh'), 0o755);
    writeText(path.join(target, 'scripts', 'chat.ps1'), chatPs1(nativeSlug, docker));
    writeText(path.join(target, 'scripts', 'verify-bootstrap.sh'), verifyBootstrapSh(nativeSlug));
    fs.chmodSync(path.join(target, 'scripts', 'verify-bootstrap.sh'), 0o755);
    writeText(path.join(target, 'scripts', 'verify-bootstrap.ps1'), verifyBootstrapPs1(nativeSlug));

    const manifest = {
      generator: `create-workframe@${PKG_VERSION}`,
      generated_at_utc: new Date().toISOString(),
      package_version: PKG_VERSION,
      hermes_tag: 'latest',
      deployment_posture: 'trusted_team',
      compose_overlays: {
        public: 'docker-compose.public.yml',
        dev_authority: 'docker-compose.dev-authority.yml',
      },
      project_name: safeName,
      project_slug: slug,
      install_id: install.installId,
      install_slot: install.slot,
      pack,
      profiles,
      profiles_pack_bootstrap: profiles,
      profiles_catalog: specialists,
      profiles_seeded: seedProfiles,
      profiles_installed_after_native_bootstrap: [nativeSlug],
      bootstrap: {
        default: 'native',
        phase_b_script: 'scripts/start-install.ps1',
        phase_b_script_sh: 'scripts/start-install.sh',
        phase_b_script_ps1: 'scripts/start-install.ps1',
        launch_script_sh: 'scripts/launch-install.sh',
        launch_script_ps1: 'scripts/launch-install.ps1',
        post_credentials_script: 'scripts/install.ps1',
        post_credentials_script_sh: 'scripts/install.sh',
        post_credentials_script_ps1: 'scripts/install.ps1',
        native_script: 'scripts/bootstrap-native.ps1',
        native_script_sh: 'scripts/bootstrap-native.sh',
        native_script_ps1: 'scripts/bootstrap-native.ps1',
        full_pack_script: 'scripts/bootstrap-profiles.ps1',
        full_pack_script_sh: 'scripts/bootstrap-profiles.sh',
        full_pack_script_ps1: 'scripts/bootstrap-profiles.ps1',
        add_profile_script: 'scripts/add-profile.ps1',
        add_profile_script_sh: 'scripts/add-profile.sh',
        add_profile_script_ps1: 'scripts/add-profile.ps1',
        secure_setup_script: 'scripts/open-setup.ps1',
        secure_setup_script_sh: 'scripts/open-setup.sh',
        secure_setup_script_ps1: 'scripts/open-setup.ps1',
        open_chat_script_sh: 'scripts/open-chat.sh',
        open_chat_script_ps1: 'scripts/open-chat.ps1',
        open_workframe_api_script_sh: 'scripts/open-workframe-api.sh',
        open_workframe_api_script_ps1: 'scripts/open-workframe-api.ps1',
        open_workframe_ui_script_sh: 'scripts/open-workframe-ui.sh',
        open_workframe_ui_script_ps1: 'scripts/open-workframe-ui.ps1',
        update_hermes_script_sh: 'scripts/update-hermes.sh',
        update_hermes_script_ps1: 'scripts/update-hermes.ps1',
      },
      native_agent: {
        display_name: nativeName,
        profile_slug: nativeSlug,
        setup_playbook_seed: `scripts/seed/profiles/${nativeSlug}/SETUP.md`,
      },
      docker: {
        image: docker.image,
        stack: docker.stack,
        network: docker.network,
        runtime: 'docker',
        containers: {
          gateway: docker.gateway,
          dashboard: docker.dashboard,
          workframe_api: docker.workframeApi,
          workframe: docker.workframe,
          chat: docker.chat,
          setup: docker.setup,
        },
        workframe_api_image: 'python:3-alpine',
        ui_image_placeholder: 'nginx:alpine',
        ui_image_target: 'workframe-ui (bundled SPA in workframe-ui/public)',
      },
      ports,
      integrations: { telegram, discord },
      layout: { workspace: 'Files', runtime: 'Agents' },
      security: {
        no_instance_data_in_template: true,
        runtime_state_directory: 'Agents',
        credentials_never_in_llm: true,
      },
    };
    writeText(path.join(target, 'workframe-manifest.json'), JSON.stringify(manifest, null, 2) + '\n');

    if (args.runDockerPull) {
      if (args.installGuideOnly) {
        console.log('Skipped docker pull: run with --allow-install-actions to execute install commands.');
      } else {
        const res = spawnSync('docker', ['pull', 'nousresearch/hermes-agent:latest'], { stdio: 'inherit' });
        if (res.status !== 0) console.warn('docker pull failed; continue manually.');
      }
    }

    console.log(`✅ Scaffold created: ${target}`);
    console.log(`Native agent: ${nativeName} (${nativeSlug})`);
    console.log(`Install id: ${install.installId} (slot ${install.slot})`);
    console.log(`Ports: UI ${ports.ui}, API ${ports.api}, gateway ${ports.gateway}, dashboard ${ports.dashboard}`);
    console.log(`Bootstrap default: bootstrap-native (full pack: ${profiles.length} profiles)`);
    console.log(`SOUL seeds: ${seedProfiles.length} profiles + native SETUP playbook`);
    if (!args.ci && !args.noLaunch) {
      if (launchPhaseBInstaller(target, {
        wait: Boolean(args.waitForInstall),
        noBrowser: Boolean(args.noBrowser),
      })) {
        console.log('');
        console.log(args.waitForInstall
          ? 'Installer completed successfully.'
          : 'Launching installer — browser opens /install immediately.');
        console.log(`Continue setup at http://127.0.0.1:${ports.ui}/install`);
      }
    } else if (args.noLaunch) {
      console.log('Next: ./scripts/start-install.sh or .\\scripts\\start-install.ps1');
    } else {
      console.log('Next: SETUP.md');
    }
  } finally {
    rl.close();
  }
}

main().catch((err) => {
  console.error(`ERROR: ${err.message}`);
  process.exit(1);
});
