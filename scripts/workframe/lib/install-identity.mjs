/**
 * Per-install identity: slot-based localhost ports + stable install id for cookies.
 *
 * Slot N (1–99) → host ports N*10000 + tail:
 *   gateway 8642, dashboard 9119, api 9120, ui 8644
 *   slot 1 → 18642, 19119, 19120, 18644
 *   slot 2 → 28642, 29119, 29120, 28644
 *
 * ponytail: cookies use WORKFRAME_INSTALL_ID (not display name); auth DB is per install so same email can sign into many.
 */
import crypto from 'node:crypto';
import net from 'node:net';

export const PORT_TAIL = Object.freeze({
  gateway: 8642,
  dashboard: 9119,
  api: 9120,
  ui: 8644,
});

export function portsForSlot(slot) {
  const n = Number(slot);
  if (!Number.isInteger(n) || n < 1 || n > 99) {
    throw new Error(`WORKFRAME_SLOT must be 1–99, got ${slot}`);
  }
  const base = n * 10_000;
  return {
    slot: n,
    gateway: base + PORT_TAIL.gateway,
    dashboard: base + PORT_TAIL.dashboard,
    api: base + PORT_TAIL.api,
    ui: base + PORT_TAIL.ui,
  };
}

export function generateInstallId() {
  return `wf_${crypto.randomBytes(6).toString('hex')}`;
}

export function sessionCookieNameFromEnv(env = process.env) {
  const installId = String(env.WORKFRAME_INSTALL_ID || '').trim();
  if (installId) {
    const safe = installId.replace(/[^a-zA-Z0-9_-]+/g, '_').replace(/^_+|_+$/g, '');
    if (safe) return `${safe}_session`;
  }
  const slug = String(env.WORKFRAME_PROJECT || 'workframe')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '') || 'workframe';
  return `wf_${slug}_session`;
}

function portTaken(port, host = '127.0.0.1') {
  return new Promise((resolve) => {
    const socket = net.createConnection({ port, host });
    const done = (taken) => {
      socket.removeAllListeners();
      socket.destroy();
      resolve(taken);
    };
    socket.setTimeout(400);
    socket.once('connect', () => done(true));
    socket.once('timeout', () => done(false));
    socket.once('error', () => done(false));
  });
}

async function slotPortsFree(slot, host = '127.0.0.1') {
  const ports = portsForSlot(slot);
  for (const key of ['gateway', 'dashboard', 'api', 'ui']) {
    if (await portTaken(ports[key], host)) return false;
  }
  return true;
}

/**
 * Pick the first free slot, or use preferredSlot when its ports are free.
 */
export async function allocateInstall({
  projectName,
  preferredSlot = null,
  maxSlot = 9,
  host = '127.0.0.1',
  installId = null,
} = {}) {
  if (preferredSlot != null) {
    const slot = Number(preferredSlot);
    if (!await slotPortsFree(slot, host)) {
      throw new Error(
        `WORKFRAME_SLOT ${slot} ports are in use (${JSON.stringify(portsForSlot(slot))})`,
      );
    }
    return {
      installId: installId || generateInstallId(),
      projectName,
      slot,
      ports: portsForSlot(slot),
    };
  }

  for (let slot = 1; slot <= maxSlot; slot++) {
    if (await slotPortsFree(slot, host)) {
      return {
        installId: installId || generateInstallId(),
        projectName,
        slot,
        ports: portsForSlot(slot),
      };
    }
  }
  throw new Error(`No free Workframe install slot (1–${maxSlot}) on ${host}`);
}

export function envFileLines(install, { example = false, nativeProfile = '' } = {}) {
  const header = example
    ? '# Copy to .env — one install = one slot + one WORKFRAME_INSTALL_ID.\n# Same email may be used across installs; each has its own auth DB.\n'
    : '# Local Workframe install identity (.env is gitignored).\n';
  const { ports, installId, slot } = install;
  return `${header}WORKFRAME_INSTALL_ID=${installId}
WORKFRAME_SLOT=${slot}
WORKFRAME_PROJECT=${install.projectName}
WORKFRAME_GATEWAY_PORT=${ports.gateway}
WORKFRAME_DASHBOARD_PORT=${ports.dashboard}
WORKFRAME_UI_PORT=${ports.ui}
WORKFRAME_API_PORT=${ports.api}
WORKFRAME_MISSION_PORT=${ports.api}
WORKFRAME_NATIVE_PROFILE=${nativeProfile}
`;
}

// ponytail: runnable self-check — node scripts/lib/install-identity.mjs
import { pathToFileURL } from 'node:url';
const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  const p1 = portsForSlot(1);
  const p2 = portsForSlot(2);
  console.assert(p1.ui === 18644 && p1.api === 19120, 'slot 1 ports');
  console.assert(p2.ui === 28644 && p2.gateway === 28642, 'slot 2 ports');
  console.assert(sessionCookieNameFromEnv({ WORKFRAME_INSTALL_ID: 'wf_abc123' }) === 'wf_abc123_session');
  allocateInstall({ projectName: 'Test', preferredSlot: 99 }).catch(() => {});
  console.log('install-identity ok');
}
