#!/usr/bin/env node
/**
 * Sync profile dashboard compose services, nginx /hermes-profiles/* blocks, and routes.json
 * from installed Agents/profiles and workframe-manifest.json pack bootstrap list.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = process.cwd();

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function listInstalledProfiles(agentsRoot) {
  const profilesDir = path.join(agentsRoot, 'profiles');
  if (!fs.existsSync(profilesDir)) return [];
  return fs
    .readdirSync(profilesDir, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .filter((name) => {
      const dir = path.join(profilesDir, name);
      return fs.existsSync(path.join(dir, 'profile.yaml')) || fs.existsSync(path.join(dir, 'config.yaml'));
    })
    .sort();
}

function profileDashboardServiceBlock(profile, image, slug, network) {
  const esc = profile.replace(/"/g, '\\"');
  return `
  dashboard-${profile}:
    image: ${image}
    container_name: ${slug}-dashboard-${profile}
    restart: unless-stopped
    command: ["hermes", "-p", "${esc}", "dashboard", "--host", "0.0.0.0", "--insecure", "--tui"]
    labels:
      com.workframe.project: "${slug}"
      com.workframe.role: profile-dashboard
      com.workframe.profile: "${esc}"
    expose:
      - "9119"
    volumes:
      - ./Agents:/opt/data
      - ./Files:/workspace
      - ./scripts:/opt/install/scripts:ro
    environment:
      - GATEWAY_HEALTH_URL=http://gateway:8642
      - HERMES_DASHBOARD_TUI=1
    depends_on:
      - gateway
    networks:
      - ${network}`;
}

function nginxProfileBlock(profile) {
  return `
    location /hermes-profiles/${profile}/ {
        proxy_pass http://dashboard-${profile}:9119/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }`;
}

function syncCompose(profiles, manifest) {
  const composePath = path.join(ROOT, 'docker-compose.yml');
  if (!fs.existsSync(composePath)) {
    console.warn('docker-compose.yml not found — skip compose sync');
    return;
  }
  const docker = manifest.docker ?? {};
  const image = docker.image ?? 'nousresearch/hermes-agent:latest';
  const slug = manifest.project_slug ?? manifest.docker?.stack ?? 'workframe';
  const network = docker.network ?? `${slug}-net`;

  let compose = fs.readFileSync(composePath, 'utf8');

  for (const profile of profiles) {
    const serviceName = `dashboard-${profile}:`;
    if (compose.includes(serviceName)) continue;
    const block = profileDashboardServiceBlock(profile, image, slug, network);
    compose = compose.replace(/\n  mission-control:/, `${block}\n\n  mission-control:`);
  }

  const dependsMarker = '    depends_on:\n      - gateway\n      - dashboard';
  const workframeDepends = [
    '      - gateway',
    '      - dashboard',
    ...profiles.map((p) => `      - dashboard-${p}`),
    '      - mission-control',
  ].join('\n');
  compose = compose.replace(
    /(  workframe:[\s\S]*?    depends_on:\n)([\s\S]*?)(    networks:)/,
    `$1${workframeDepends}\n$3`,
  );

  fs.writeFileSync(composePath, compose);
}

function nginxConfPath() {
  const candidates = [
    path.join(ROOT, 'workframe-ui', 'docker', 'nginx.conf'),
    path.join(ROOT, 'packages', 'workframe-ui', 'docker', 'nginx.conf'),
  ];
  return candidates.find((p) => fs.existsSync(p)) ?? candidates[0];
}

function syncNginx(profiles) {
  const nginxPath = nginxConfPath();
  if (!fs.existsSync(nginxPath)) {
    console.warn(`${nginxPath} not found — skip nginx sync`);
    return;
  }
  let nginx = fs.readFileSync(nginxPath, 'utf8');
  const marker = '\n    location / {';
  const existing = new Set(
    [...nginx.matchAll(/location \/hermes-profiles\/([a-z0-9-]+)\//g)].map((m) => m[1]),
  );
  const additions = profiles.filter((p) => !existing.has(p)).map((p) => nginxProfileBlock(p)).join('');
  if (additions) {
    nginx = nginx.replace(marker, `${additions}${marker}`);
    fs.writeFileSync(nginxPath, nginx);
  }
}

function loadAgentRegistry() {
  const file = path.join(ROOT, 'Agents', 'workframe', 'agents.json');
  if (!fs.existsSync(file)) return {};
  try {
    const data = readJson(file);
    return data.agents || {};
  } catch {
    return {};
  }
}

function writeRoutes(profiles, manifest) {
  const native = manifest.native_agent?.profile_slug ?? profiles[0] ?? '';
  const projectName = manifest.project_name ?? 'Workframe';
  const agents = loadAgentRegistry();
  const routes = profiles.map((profile) => {
    const isNative = profile === native;
    const reg = agents[profile] || {};
    const displayName = reg.display_name
      || (isNative ? manifest.native_agent?.display_name ?? `${projectName} Agent` : profile.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()));
    return {
      id: profile,
      surface: 'ui',
      channel_id: `ui://agent/${profile}`,
      profile,
      display_name: displayName,
      role: reg.role || profile,
      avatar_id: reg.avatar_id || null,
      avatar_url: reg.avatar_url || null,
      mode: 'profile-dashboard',
      dashboard_path: `/hermes-profiles/${profile}`,
    };
  });
  const routesDir = path.join(ROOT, 'Agents', 'workframe');
  fs.mkdirSync(routesDir, { recursive: true });
  fs.writeFileSync(
    path.join(routesDir, 'routes.json'),
    `${JSON.stringify({ version: 1, default_profile: native, routes }, null, 2)}\n`,
  );
}

function main() {
  const args = process.argv.slice(2);
  let appendProfile = '';
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--append-profile' && args[i + 1]) appendProfile = args[++i];
  }

  const manifestPath = path.join(ROOT, 'workframe-manifest.json');
  const manifest = fs.existsSync(manifestPath) ? readJson(manifestPath) : {};
  const native = manifest.native_agent?.profile_slug ?? '';
  const installed = listInstalledProfiles(path.join(ROOT, 'Agents'));
  const profiles = [
    ...new Set([
      ...(native ? [native] : []),
      ...installed,
      ...(appendProfile ? [appendProfile] : []),
    ]),
  ].filter(Boolean).sort();

  if (!profiles.length) {
    console.warn('No installed profiles found for dashboard sync.');
    return;
  }

  syncCompose(profiles, manifest);
  syncNginx(profiles);
  writeRoutes(profiles, manifest);
  console.log(`Synced profile dashboards for: ${profiles.join(', ')}`);
  console.log('Run: docker compose up -d --force-recreate');
}

main();
