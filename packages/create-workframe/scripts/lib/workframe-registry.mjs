import fs from 'node:fs';
import path from 'node:path';

export const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,63}$/;

export function workframeDir(root) {
  return path.join(root, 'Agents', 'workframe');
}

export function agentsRegistryPath(root) {
  return path.join(workframeDir(root), 'agents.json');
}

export function avatarRegistryPath(root) {
  return path.join(workframeDir(root), 'avatar-registry.json');
}

export function ensureWorkframeDir(root) {
  fs.mkdirSync(workframeDir(root), { recursive: true });
}

export function loadAgentsRegistry(root) {
  const file = agentsRegistryPath(root);
  if (!fs.existsSync(file)) {
    return { version: 1, owner_profile: '', agents: {} };
  }
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

export function saveAgentsRegistry(root, data) {
  ensureWorkframeDir(root);
  fs.writeFileSync(agentsRegistryPath(root), `${JSON.stringify(data, null, 2)}\n`);
}

export function loadAvatarRegistry(root) {
  const file = avatarRegistryPath(root);
  if (!fs.existsSync(file)) {
    return { version: 1, weights: {}, assignments: {} };
  }
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

export function saveAvatarRegistry(root, data) {
  ensureWorkframeDir(root);
  fs.writeFileSync(avatarRegistryPath(root), `${JSON.stringify(data, null, 2)}\n`);
}

export function avatarCatalogPaths(root) {
  return [
    path.join(root, 'Files', 'packages', 'workframe-ui', 'public', 'assets', 'avatars', 'catalog.json'),
    path.join(root, 'Files', 'packages', 'create-workframe', 'shared', 'agent-avatars', 'catalog.json'),
    path.join(root, 'workframe-ui', 'public', 'assets', 'avatars', 'catalog.json'),
    path.join(root, 'packages', 'workframe-ui', 'public', 'assets', 'avatars', 'catalog.json'),
    path.join(root, 'packages', 'create-workframe', 'shared', 'agent-avatars', 'catalog.json'),
    path.join(root, 'scripts', 'seed', 'assets', 'avatars', 'catalog.json'),
    path.join(root, 'workframe-ui', 'public', 'assets', 'agents', 'catalog.json'),
    path.join(root, 'packages', 'create-workframe', 'shared', 'agent-avatars', 'catalog.json'),
  ];
}

export function loadAvatarCatalog(root) {
  for (const candidate of avatarCatalogPaths(root)) {
    if (fs.existsSync(candidate)) {
      const data = JSON.parse(fs.readFileSync(candidate, 'utf8'));
      const base = String(data.public_base || '/assets/avatars').replace(/\/$/, '');
      const avatars = (data.avatars || []).map((row) => ({
        id: String(row.id),
        file: String(row.file || `${row.id}.png`),
        label: String(row.label || row.id),
        url: `${base}/${row.file || `${row.id}.png`}`,
      }));
      if (avatars.length) return { base, avatars };
    }
  }
  throw new Error('Avatar catalog not found (expected workframe-ui/public/assets/avatars/catalog.json)');
}

export function avatarUrlForId(catalog, avatarId) {
  const row = catalog.avatars.find((a) => a.id === avatarId);
  return row?.url ?? `${catalog.base}/${avatarId}.png`;
}

/** Weighted pick: prefer unassigned avatars, then lowest weight; random tie-break. */
export function pickAvatarId(root, { avoidReuse = true } = {}) {
  const catalog = loadAvatarCatalog(root);
  const avatarRegistry = loadAvatarRegistry(root);
  const agentsRegistry = loadAgentsRegistry(root);
  const assigned = new Set(Object.values(avatarRegistry.assignments || {}));
  for (const row of Object.values(agentsRegistry.agents || {})) {
    if (row.avatar_id) assigned.add(row.avatar_id);
  }

  let pool = catalog.avatars;
  if (avoidReuse) {
    const unused = pool.filter((a) => !assigned.has(a.id));
    if (unused.length) pool = unused;
  }

  const weights = avatarRegistry.weights || {};
  let minWeight = Infinity;
  for (const avatar of pool) {
    const w = weights[avatar.id] ?? 0;
    if (w < minWeight) minWeight = w;
  }
  const candidates = pool.filter((a) => (weights[a.id] ?? 0) <= minWeight);
  const pick = candidates[Math.floor(Math.random() * candidates.length)];
  return pick.id;
}

export function assignAvatar(root, profile, avatarId) {
  const catalog = loadAvatarCatalog(root);
  if (!catalog.avatars.some((a) => a.id === avatarId)) {
    throw new Error(`Unknown avatar id: ${avatarId}`);
  }
  const avatarRegistry = loadAvatarRegistry(root);
  avatarRegistry.assignments = avatarRegistry.assignments || {};
  avatarRegistry.weights = avatarRegistry.weights || {};
  avatarRegistry.assignments[profile] = avatarId;
  avatarRegistry.weights[avatarId] = (avatarRegistry.weights[avatarId] ?? 0) + 1;
  saveAvatarRegistry(root, avatarRegistry);
  return avatarUrlForId(catalog, avatarId);
}

export function releaseAvatar(root, profile) {
  const avatarRegistry = loadAvatarRegistry(root);
  if (avatarRegistry.assignments?.[profile]) {
    delete avatarRegistry.assignments[profile];
    saveAvatarRegistry(root, avatarRegistry);
  }
}

export function upsertAgentRecord(root, profile, patch, ownerProfile) {
  const registry = loadAgentsRegistry(root);
  registry.owner_profile = registry.owner_profile || ownerProfile;
  registry.agents = registry.agents || {};
  const prev = registry.agents[profile] || {};
  const now = new Date().toISOString();
  registry.agents[profile] = {
    ...prev,
    ...patch,
    profile,
    owner: ownerProfile,
    updated_at: now,
    created_at: prev.created_at || now,
  };
  saveAgentsRegistry(root, registry);
  return registry.agents[profile];
}

export function removeAgentRecord(root, profile) {
  const registry = loadAgentsRegistry(root);
  if (registry.agents?.[profile]) {
    delete registry.agents[profile];
    saveAgentsRegistry(root, registry);
  }
  releaseAvatar(root, profile);
}

export function getAgentRecord(root, profile) {
  const registry = loadAgentsRegistry(root);
  return registry.agents?.[profile] ?? null;
}

export function readModelFromConfig(root, profile) {
  const cfgPath = path.join(root, 'Agents', 'profiles', profile, 'config.yaml');
  if (!fs.existsSync(cfgPath)) return null;
  const text = fs.readFileSync(cfgPath, 'utf8');
  const match = text.match(/^model:\s*\n(?:\s+.+\n)*?\s+default:\s*(.+)$/m);
  return match ? match[1].trim() : null;
}

const FORBIDDEN_CHILD_SKILLS = new Set(['botfather', 'crew-manager']);

export function profileSkillsSeedDir(root, sourceSlug) {
  return path.join(root, 'scripts', 'seed', 'profiles', sourceSlug, 'skills');
}

export function profileSkillsDir(root, profile) {
  return path.join(root, 'Agents', 'profiles', profile, 'skills');
}

function copyDirRecursive(src, dest) {
  if (!fs.existsSync(src)) return false;
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const from = path.join(src, entry.name);
    const to = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDirRecursive(from, to);
    else fs.copyFileSync(from, to);
  }
  return true;
}

function skillNameFromPath(skillsRoot, skillFile) {
  const rel = path.relative(skillsRoot, skillFile).replace(/\\/g, '/');
  const parts = rel.split('/');
  if (parts.length >= 2 && parts[parts.length - 1] === 'SKILL.md') {
    return parts[parts.length - 2];
  }
  return path.basename(path.dirname(skillFile));
}

export function listInstalledSkillIds(root, profile) {
  const skillsRoot = profileSkillsDir(root, profile);
  if (!fs.existsSync(skillsRoot)) return [];
  const ids = new Set();
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.name === 'SKILL.md') ids.add(skillNameFromPath(skillsRoot, full));
    }
  };
  walk(skillsRoot);
  return [...ids].sort();
}

/** Copy skills from seed (or another seed slug). Never installs botfather on children. */
export function installProfileSkills(root, targetProfile, { sourceSlug, skillsDir } = {}) {
  const dest = profileSkillsDir(root, targetProfile);
  let src = skillsDir ? (path.isAbsolute(skillsDir) ? skillsDir : path.join(root, skillsDir)) : null;
  if (!src) {
    const seedSlug = sourceSlug || targetProfile;
    src = profileSkillsSeedDir(root, seedSlug);
  }
  if (!fs.existsSync(src)) {
    return { installed: [], skipped: [], source: src };
  }

  const staging = path.join(dest, '.staging');
  fs.rmSync(staging, { recursive: true, force: true });
  copyDirRecursive(src, staging);

  const installed = [];
  const skipped = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.name === 'SKILL.md') {
        const id = skillNameFromPath(staging, full);
        if (FORBIDDEN_CHILD_SKILLS.has(id)) {
          skipped.push(id);
          fs.rmSync(path.dirname(full), { recursive: true, force: true });
        } else {
          installed.push(id);
        }
      }
    }
  };
  walk(staging);

  if (installed.length || skipped.length) {
    fs.mkdirSync(dest, { recursive: true });
    for (const entry of fs.readdirSync(staging, { withFileTypes: true })) {
      const from = path.join(staging, entry.name);
      const to = path.join(dest, entry.name);
      if (entry.isDirectory()) copyDirRecursive(from, to);
      else if (fs.existsSync(from)) fs.copyFileSync(from, to);
    }
  }
  fs.rmSync(staging, { recursive: true, force: true });
  return { installed: [...new Set(installed)].sort(), skipped: [...new Set(skipped)].sort(), source: src };
}

/** Remove botfather/crew-manager from a child profile after Hermes --clone. */
export function stripForbiddenChildSkills(root, profile) {
  const skillsRoot = profileSkillsDir(root, profile);
  if (!fs.existsSync(skillsRoot)) return { removed: [] };
  const removed = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === 'botfather' || entry.name === 'crew-manager') {
          fs.rmSync(full, { recursive: true, force: true });
          removed.push(entry.name);
        } else walk(full);
      } else if (entry.name === 'SKILL.md') {
        const id = skillNameFromPath(skillsRoot, full);
        if (FORBIDDEN_CHILD_SKILLS.has(id)) {
          fs.rmSync(path.dirname(full), { recursive: true, force: true });
          removed.push(id);
        }
      }
    }
  };
  walk(skillsRoot);
  return { removed: [...new Set(removed)].sort() };
}
