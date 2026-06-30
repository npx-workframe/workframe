#!/usr/bin/env node
/**
 * Botfather agent lifecycle â€” native profile only.
 * Create/update/spawn/delete child agents; registry + avatar assignment.
 */
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  assignAvatar,
  getAgentRecord,
  installProfileSkills,
  listInstalledSkillIds,
  loadAvatarCatalog,
  pickAvatarId,
  readModelFromConfig,
  removeAgentRecord,
  routesRegistryPath,
  stripForbiddenChildSkills,
  upsertAgentRecord,
  upsertRouteRecord,
} from './lib/workframe-registry.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = process.cwd();
const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,63}$/;

function readManifest() {
  const p = path.join(ROOT, 'workframe-manifest.json');
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : {};
}

function nativeProfile(manifest) {
  return manifest.native_agent?.profile_slug ?? 'workframe-agent';
}

function dockerImage(manifest) {
  return manifest.docker?.image ?? 'nousresearch/hermes-agent:latest';
}

function dockerStack(manifest) {
  return manifest.docker?.stack ?? manifest.project_slug ?? 'workframe';
}

function assertSlug(slug, label = 'slug') {
  if (!slug || !SLUG_RE.test(slug)) {
    throw new Error(`Invalid ${label}: use lowercase letters, digits, and hyphens (max 64 chars).`);
  }
}

function assertManagedChild(slug, action) {
  const native = nativeProfile(readManifest());
  assertSlug(slug);
  if (slug === native) {
    throw new Error(`Botfather cannot ${action} the native profile (${native}). Manage child agents only.`);
  }
}

function profileDir(slug) {
  return path.join(ROOT, 'Agents', 'profiles', slug);
}

function run(cmd, args, { allowFail = false } = {}) {
  const res = spawnSync(cmd, args, { encoding: 'utf8', cwd: ROOT });
  if (res.status !== 0 && !allowFail) {
    const detail = (res.stderr || res.stdout || '').trim();
    throw new Error(`${cmd} ${args.join(' ')} failed${detail ? `: ${detail}` : ''}`);
  }
  return res;
}

function runHermes(profileArgs, hermesArgs, { allowFail = false, name } = {}) {
  const manifest = readManifest();
  const image = dockerImage(manifest);
  const stack = dockerStack(manifest);
  const containerName = name ?? `${stack}-lifecycle-${Date.now()}`;
  const args = [
    'run',
    '--rm',
    '--name',
    containerName,
    '--entrypoint',
    'hermes',
    '-v',
    `${path.join(ROOT, 'Agents')}:/opt/data`,
    '-v',
    `${path.join(ROOT, 'Files')}:/workspace`,
    image,
    ...profileArgs,
    ...hermesArgs,
  ];
  return run('docker', args, { allowFail });
}

function patchTerminalCwd(slug) {
  const cfgPath = path.join(profileDir(slug), 'config.yaml');
  if (!fs.existsSync(cfgPath)) return;
  const content = fs.readFileSync(cfgPath, 'utf8');
  const next = content.replace(/^  cwd: .*$/m, '  cwd: /workspace');
  if (next !== content) fs.writeFileSync(cfgPath, next);
}

/** Strip platform credentials from a cloned child .env, keeping only LLM/provider keys. */
function sanitizeChildEnv(slug) {
  const envPath = path.join(profileDir(slug), '.env');
  if (!fs.existsSync(envPath)) return { removed: [], kept: [] };

  const PLATFORM_KEY_RE = /^(TELEGRAM_|DISCORD_|SLACK_|WHATSAPP_|SIGNAL_|MATTERMATRIX_|HOMEASSISTANT_|QQBOT_|YUANBAO_|GOOGLE_CHAT_|TEAMS_|MATRIX_)/;
  const LLM_KEY_RE = /^(OPENROUTER_|OPENAI_|ANTHROPIC_|GOOGLE_|COHERE_|MISTRAL_|TOGETHER_|FIREWORKS_|DEEPSEEK_|ZAI_|KIMI_|MINIMAX_|AWS_|BEDROCK_|XAI_|GROQ_|OLLAMA_|LITELLM_|VOYAGE_|JINA_|SERP_|BRAVE_|TAVILY_|EXA_|FIRECRAWL_|APIFY_|SCRAPFLY_|PROXYCURL_|CLEARBIT_|HUNTER_|ZEROBOUNCE_|RESEND_|SENDGRID_|MAILGUN_|POSTMARK_|TWILIO_|VONAGE_|MESSAGEBIRD_|PLIVO_|SINCH_|BANDWIDTH_|TELNYX_|VOXIMPLANT_|AGORA_|DAILY_|MUX_|CLOUDFLARE_|R2_|S3_|GCS_|AZURE_|SUPABASE_|UPSTASH_|REDIS_|POSTGRES_|MYSQL_|SQLITE_|MONGODB_|DYNAMODB_|COUCHBASE_|CASSANDRA_|NEO4J_|ARANGODB_|INFLUXDB_|TIMESCALEDB_|QUESTDB_|CLICKHOUSE_|DATABRICKS_|SNOWFLAKE_|BIGQUERY_|REDSHIFT_|ATHENA_|TRINO_|PRESTO_|DRILL_|HIVE_|SPARK_|FLINK_|KAFKA_|RABBITMQ_|NATS_|MQTT_|WEBSOCKET_|GRPC_|GRAPHQL_|REST_|OAUTH_|JWT_|API_KEY_|SECRET_|TOKEN_|PASSWORD_|CREDENTIAL_|AUTH_)/;

  const lines = fs.readFileSync(envPath, 'utf8').split('\n');
  const kept = [];
  const removed = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      kept.push(line);
      continue;
    }
    const key = trimmed.split('=')[0];
    if (PLATFORM_KEY_RE.test(key)) {
      removed.push(key);
    } else {
      kept.push(line);
    }
  }

  fs.writeFileSync(envPath, kept.join('\n') + (kept.length && !kept[kept.length - 1].endsWith('\n') ? '\n' : ''));
  return { removed, kept: kept.filter(l => l.trim() && !l.trim().startsWith('#')).map(l => l.split('=')[0]) };
}

/** Disable all messaging platforms in a child profile config. */
function disableChildPlatforms(slug) {
  const cfgPath = path.join(profileDir(slug), 'config.yaml');
  if (!fs.existsSync(cfgPath)) return;

  const platforms = ['telegram', 'discord', 'slack', 'whatsapp', 'signal', 'mattermost', 'matrix', 'homeassistant', 'qqbot', 'yuanbao', 'google_chat', 'teams'];
  let content = fs.readFileSync(cfgPath, 'utf8');

  // Disable each platform
  for (const p of platforms) {
    // Match "  <platform>:" followed by "    enabled: true" and set to false
    const re = new RegExp(`(\\s+${p}:\\n(?:\\s+\\w+:.*\\n)*?\\s+enabled:\\s*)true`, 'g');
    content = content.replace(re, '$1false');
  }

  fs.writeFileSync(cfgPath, content);
}

function syncProfileManifest(slug, description) {
  const dir = profileDir(slug);
  fs.mkdirSync(dir, { recursive: true });
  const yaml = [
    `description: ${JSON.stringify(description)}`,
    'description_auto: false',
    'soul:',
    `  file: /opt/data/profiles/${slug}/SOUL.md`,
    '',
  ].join('\n');
  fs.writeFileSync(path.join(dir, 'profile.yaml'), yaml, 'utf8');
}

function defaultSoul(displayName, role) {
  return `# ${displayName}

Mission
- ${role}

Ask for
- scope, constraints, and done criteria before heavy work.

Preferred skills/tools
- load on demand for the task at hand. You cannot create or manage other agents.

Handoff
- changed files, test evidence, blockers. Escalate crew changes to the native Botfather agent.
`;
}

function resolveSoul(slug, { displayName, role, soulFile, soulText, fromSeed }) {
  if (soulText) return soulText.trim() + '\n';
  if (soulFile) {
    const abs = path.isAbsolute(soulFile) ? soulFile : path.join(ROOT, soulFile);
    if (!fs.existsSync(abs)) throw new Error(`SOUL file not found: ${soulFile}`);
    return fs.readFileSync(abs, 'utf8');
  }
  const seed = path.join(ROOT, 'scripts', 'seed', 'profiles', slug, 'SOUL.md');
  if (fromSeed && fs.existsSync(seed)) return fs.readFileSync(seed, 'utf8');
  const template = path.join(ROOT, 'scripts', 'seed', 'agent-template', 'SOUL.md');
  if (fromSeed && fs.existsSync(template)) {
    return fs
      .readFileSync(template, 'utf8')
      .replace(/\{displayName\}/g, displayName)
      .replace(/\{role\}/g, role)
      .replace(/\{slug\}/g, slug);
  }
  return defaultSoul(displayName, role);
}

function syncDashboards(appendProfile) {
  void appendProfile;
}

function composeSpawn(slug) {
  void slug;
  run('docker', ['compose', 'up', '-d', 'gateway', 'dashboard', 'workframe-api', 'workframe']);
}

function composeStop(slug) {
  void slug;
}

function composeRecreate() {
  run('docker', ['compose', 'up', '-d', '--force-recreate']);
}

function profileExists(slug) {
  const res = runHermes([], ['profile', 'show', slug], {
    allowFail: true,
    name: `${dockerStack(readManifest())}-show-${slug}`,
  });
  return res.status === 0;
}

function buildConfigSnapshot(slug) {
  const manifest = readManifest();
  const native = nativeProfile(manifest);
  const record = getAgentRecord(ROOT, slug);
  const soulPath = path.join(profileDir(slug), 'SOUL.md');
  const soulPreview = fs.existsSync(soulPath) ? fs.readFileSync(soulPath, 'utf8').slice(0, 800) : null;
  return {
    profile: slug,
    is_native: slug === native,
    owner: record?.owner || native,
    display_name: record?.display_name || null,
    role: record?.role || null,
    model: record?.model || readModelFromConfig(ROOT, slug),
    avatar_id: record?.avatar_id || null,
    avatar_url: record?.avatar_url || null,
    skills: listInstalledSkillIds(ROOT, slug),
    soul_path: `/opt/data/profiles/${slug}/SOUL.md`,
    soul_preview: soulPreview,
    created_at: record?.created_at || null,
    updated_at: record?.updated_at || null,
  };
}

function cmdGetConfig(opts) {
  assertSlug(opts.slug);
  if (!profileExists(opts.slug)) throw new Error(`Profile not found: ${opts.slug}`);
  console.log(JSON.stringify({ ok: true, action: 'get-config', config: buildConfigSnapshot(opts.slug) }, null, 2));
}

function cmdUpdateConfig(opts) {
  assertManagedChild(opts.slug, 'update-config');
  if (!profileExists(opts.slug)) throw new Error(`Profile not found: ${opts.slug}`);
  const manifest = readManifest();
  const native = nativeProfile(manifest);
  const patch = {};
  if (opts.displayName) patch.display_name = opts.displayName;
  if (opts.role) {
    patch.role = opts.role;
    runHermes([], ['profile', 'describe', opts.slug, opts.role], { allowFail: true });
  }
  if (opts.description) {
    runHermes([], ['profile', 'describe', opts.slug, opts.description], { allowFail: true });
  }
  if (opts.model) {
    runHermes(['-p', opts.slug], ['config', 'set', 'model.default', opts.model]);
    patch.model = opts.model;
  }
  if (opts.avatar) {
    const url = assignAvatar(ROOT, opts.slug, opts.avatar);
    patch.avatar_id = opts.avatar;
    patch.avatar_url = url;
  }
  if (opts.soulFile || opts.soulText) {
    const soul = resolveSoul(opts.slug, {
      displayName: opts.displayName || opts.slug,
      role: opts.role || 'Specialist',
      soulFile: opts.soulFile,
      soulText: opts.soulText,
      fromSeed: false,
    });
    fs.mkdirSync(profileDir(opts.slug), { recursive: true });
    fs.writeFileSync(path.join(profileDir(opts.slug), 'SOUL.md'), soul);
  }
  syncProfileManifest(opts.slug, opts.description || opts.role || patch.role || `${opts.slug} specialist profile.`);
  let skillsInstalled = null;
  if (opts.fromSeed || opts.skillsFrom || opts.skillsDir) {
    skillsInstalled = installProfileSkills(ROOT, opts.slug, {
      sourceSlug: opts.skillsFrom || opts.slug,
      skillsDir: opts.skillsDir,
    });
    patch.skills = listInstalledSkillIds(ROOT, opts.slug);
  }
  const record = upsertAgentRecord(ROOT, opts.slug, patch, native);
  syncDashboards(opts.slug);
  console.log(
    JSON.stringify(
      {
        ok: true,
        action: 'update-config',
        config: { ...buildConfigSnapshot(opts.slug), ...record },
        skills_installed: skillsInstalled,
      },
      null,
      2,
    ),
  );
}

function cmdPickAvatar(opts) {
  const avatarId = opts.avatar || pickAvatarId(ROOT, { avoidReuse: true });
  const catalog = loadAvatarCatalog(ROOT);
  const row = catalog.avatars.find((a) => a.id === avatarId);
  console.log(JSON.stringify({ ok: true, action: 'pick-avatar', avatar_id: avatarId, avatar_url: row?.url }, null, 2));
}

function cmdSetAvatar(opts) {
  assertManagedChild(opts.slug, 'set-avatar');
  if (!opts.avatar) throw new Error('--avatar is required');
  if (!profileExists(opts.slug)) throw new Error(`Profile not found: ${opts.slug}`);
  const manifest = readManifest();
  const url = assignAvatar(ROOT, opts.slug, opts.avatar);
  upsertAgentRecord(ROOT, opts.slug, { avatar_id: opts.avatar, avatar_url: url }, nativeProfile(manifest));
  syncDashboards(opts.slug);
  console.log(JSON.stringify({ ok: true, action: 'set-avatar', profile: opts.slug, avatar_id: opts.avatar, avatar_url: url }, null, 2));
}

function cmdCreate(opts) {
  const manifest = readManifest();
  const native = nativeProfile(manifest);
  assertManagedChild(opts.slug, 'create');

  const displayName = opts.displayName || opts.slug.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  const role = opts.role || `${displayName} specialist for ${manifest.project_name ?? 'this project'}.`;
  const description = opts.description || role;

  if (!profileExists(opts.slug)) {
    const created = runHermes([], ['profile', 'create', opts.slug, '--clone', '--no-skills', '--description', description], {
      allowFail: true,
      name: `${dockerStack(manifest)}-create-${opts.slug}`,
    });
    if (created.status !== 0) {
      throw new Error(`Failed to create profile ${opts.slug}: ${(created.stderr || created.stdout || '').trim()}`);
    }
  } else {
    console.log(`Profile ${opts.slug} already exists — updating artifacts.`);
  }

  // Strip platform credentials and disable messaging platforms
  const envResult = sanitizeChildEnv(opts.slug);
  disableChildPlatforms(opts.slug);

  runHermes([], ['profile', 'describe', opts.slug, description], { allowFail: true });

  const soul = resolveSoul(opts.slug, {
    displayName,
    role,
    soulFile: opts.soulFile,
    soulText: opts.soulText,
    fromSeed: opts.fromSeed,
  });
  const dir = profileDir(opts.slug);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'SOUL.md'), soul);
  syncProfileManifest(opts.slug, description);
  patchTerminalCwd(opts.slug);
  stripForbiddenChildSkills(ROOT, opts.slug);

  let model = opts.model || null;
  if (model) {
    runHermes(['-p', opts.slug], ['config', 'set', 'model.default', model]);
  } else {
    model = readModelFromConfig(ROOT, opts.slug);
  }

  const avatarId = opts.avatar || pickAvatarId(ROOT, { avoidReuse: true });
  const avatarUrl = assignAvatar(ROOT, opts.slug, avatarId);

  upsertAgentRecord(
    ROOT,
    opts.slug,
    {
      display_name: displayName,
      role,
      model,
      avatar_id: avatarId,
      avatar_url: avatarUrl,
      skills: [],
    },
    native,
  );

  let skillsInstalled = null;
  if (opts.fromSeed || opts.skillsFrom || opts.skillsDir) {
    skillsInstalled = installProfileSkills(ROOT, opts.slug, {
      sourceSlug: opts.skillsFrom || opts.slug,
      skillsDir: opts.skillsDir,
    });
  }
  const skills = listInstalledSkillIds(ROOT, opts.slug);
  upsertAgentRecord(ROOT, opts.slug, { skills }, native);

  upsertRouteRecord(ROOT, opts.slug, {
    id: opts.slug,
    surface: 'ui',
    channel_id: `ui://agent/${opts.slug}`,
    profile: opts.slug,
    display_name: displayName,
    role: opts.slug,
    avatar_id: avatarId,
    avatar_url: avatarUrl,
    mode: 'profile-gateway',
    dashboard_path: '/hermes-dashboard',
    chat_port: 18610 + (opts.slug.split('').reduce((a, c) => a + c.charCodeAt(0), 0) % 100),
  });

  syncDashboards(opts.slug);
  if (opts.spawn) composeSpawn(opts.slug);

  console.log(
    JSON.stringify(
      {
        ok: true,
        action: 'create',
        profile: opts.slug,
        displayName,
        avatar_id: avatarId,
        avatar_url: avatarUrl,
        skills,
        skills_installed: skillsInstalled,
        spawned: Boolean(opts.spawn),
      },
      null,
      2,
    ),
  );
}

function cmdAddSkills(opts) {
  assertManagedChild(opts.slug, 'add-skills');
  if (!profileExists(opts.slug)) throw new Error(`Profile not found: ${opts.slug}`);
  if (!opts.fromSeed && !opts.skillsFrom && !opts.skillsDir) {
    throw new Error('add-skills requires --from-seed, --skills-from, or --skills-dir');
  }
  const result = installProfileSkills(ROOT, opts.slug, {
    sourceSlug: opts.skillsFrom || opts.slug,
    skillsDir: opts.skillsDir,
  });
  const skills = listInstalledSkillIds(ROOT, opts.slug);
  upsertAgentRecord(ROOT, opts.slug, { skills }, nativeProfile(readManifest()));
  console.log(JSON.stringify({ ok: true, action: 'add-skills', profile: opts.slug, skills, ...result }, null, 2));
}

function cmdUpdateSoul(opts) {
  assertManagedChild(opts.slug, 'update-soul');
  if (!profileExists(opts.slug)) throw new Error(`Profile not found: ${opts.slug}`);
  const soul = resolveSoul(opts.slug, {
    displayName: opts.displayName || opts.slug,
    role: opts.role || 'Specialist',
    soulFile: opts.soulFile,
    soulText: opts.soulText,
    fromSeed: false,
  });
  fs.mkdirSync(profileDir(opts.slug), { recursive: true });
  fs.writeFileSync(path.join(profileDir(opts.slug), 'SOUL.md'), soul);
  const record = getAgentRecord(ROOT, opts.slug);
  syncProfileManifest(opts.slug, record?.role || `${opts.slug} specialist profile.`);
  upsertAgentRecord(ROOT, opts.slug, {}, nativeProfile(readManifest()));
  console.log(JSON.stringify({ ok: true, action: 'update-soul', profile: opts.slug }, null, 2));
}

function cmdSetModel(opts) {
  assertManagedChild(opts.slug, 'set-model');
  if (!opts.model) throw new Error('--model is required');
  if (!profileExists(opts.slug)) throw new Error(`Profile not found: ${opts.slug}`);
  runHermes(['-p', opts.slug], ['config', 'set', 'model.default', opts.model]);
  upsertAgentRecord(ROOT, opts.slug, { model: opts.model }, nativeProfile(readManifest()));
  console.log(JSON.stringify({ ok: true, action: 'set-model', profile: opts.slug, model: opts.model }, null, 2));
}

function cmdSpawn(opts) {
  assertSlug(opts.slug);
  syncDashboards(opts.slug);
  composeSpawn(opts.slug);
  console.log(JSON.stringify({ ok: true, action: 'spawn', profile: opts.slug }, null, 2));
}

function cmdStop(opts) {
  assertSlug(opts.slug);
  composeStop(opts.slug);
  console.log(JSON.stringify({ ok: true, action: 'stop', profile: opts.slug }, null, 2));
}

function cmdDelete(opts) {
  assertManagedChild(opts.slug, 'delete');

  composeStop(opts.slug);
  if (profileExists(opts.slug)) {
    runHermes([], ['profile', 'delete', '-y', opts.slug], { allowFail: true });
  }
  const dir = profileDir(opts.slug);
  if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true, force: true });
  removeAgentRecord(ROOT, opts.slug);
  syncDashboards();
  if (opts.recreate) composeRecreate();
  console.log(JSON.stringify({ ok: true, action: 'delete', profile: opts.slug }, null, 2));
}

function cmdList() {
  const res = runHermes([], ['profile', 'list'], { name: `${dockerStack(readManifest())}-list` });
  process.stdout.write(res.stdout || '');
}

function usage() {
  console.log(`Usage: node scripts/agent-lifecycle.mjs <command> [options]

Botfather-only lifecycle for child agents (native profile manages; children cannot).

Commands:
  create         Create child profile, SOUL, avatar, registry, sync dashboard
  get-config     Read merged agent config (registry + model + SOUL preview)
  update-config  Patch display name, role, model, avatar, SOUL, skills
  add-skills     Install skills from seed (--from-seed / --skills-from / --skills-dir)
  pick-avatar    Random avatar id (avoids in-use when possible)
  set-avatar     Assign catalog avatar to child agent
  update-soul    Rewrite SOUL.md
  set-model      Set model.default
  spawn          docker compose up -d (base 4 services)
  stop           no-op (single dashboard architecture)
  delete         Stop, delete profile, registry entry, resync compose
  list           hermes profile list

Shared options:
  --slug <slug>            Profile slug (required for most commands)

Create / update-config / add-skills:
  --display-name, --role, --description, --model
  --avatar <id>            Catalog id (create auto-picks if omitted)
  --soul-file, --soul-text
  --from-seed              Seed SOUL; with create/add-skills also copies seed skills/
  --skills-from <slug>     Copy skills from scripts/seed/profiles/<slug>/skills
  --skills-dir <path>      Copy skills tree from workspace path
  --spawn                  Start dashboard after create
`);
}

function parse(argv) {
  const out = { command: argv[0], spawn: false, fromSeed: false, recreate: false };
  for (let i = 1; i < argv.length; i++) {
    const a = argv[i];
    const next = () => {
      if (i + 1 >= argv.length) throw new Error(`Missing value for ${a}`);
      return argv[++i];
    };
    if (a === '--spawn') out.spawn = true;
    else if (a === '--from-seed') out.fromSeed = true;
    else if (a === '--recreate') out.recreate = true;
    else if (a === '--slug') out.slug = next();
    else if (a === '--display-name') out.displayName = next();
    else if (a === '--role') out.role = next();
    else if (a === '--description') out.description = next();
    else if (a === '--model') out.model = next();
    else if (a === '--avatar') out.avatar = next();
    else if (a === '--soul-file') out.soulFile = next();
    else if (a === '--soul-text') out.soulText = next();
    else if (a === '--skills-from') out.skillsFrom = next();
    else if (a === '--skills-dir') out.skillsDir = next();
    else if (a.startsWith('--slug=')) out.slug = a.slice(7);
    else if (a.startsWith('--display-name=')) out.displayName = a.slice(15);
    else if (a.startsWith('--role=')) out.role = a.slice(7);
    else if (a.startsWith('--model=')) out.model = a.slice(8);
    else if (a.startsWith('--avatar=')) out.avatar = a.slice(9);
    else if (a.startsWith('--soul-file=')) out.soulFile = a.slice(12);
    else if (a.startsWith('--soul-text=')) out.soulText = a.slice(12);
    else if (a.startsWith('--skills-from=')) out.skillsFrom = a.slice(14);
    else if (a.startsWith('--skills-dir=')) out.skillsDir = a.slice(13);
    else throw new Error(`Unknown argument: ${a}`);
  }
  return out;
}

function main() {
  const argv = process.argv.slice(2);
  if (!argv.length || argv[0] === '-h' || argv[0] === '--help') {
    usage();
    process.exit(argv.length ? 0 : 1);
  }
  const opts = parse(argv);
  switch (opts.command) {
    case 'create':
      if (!opts.slug) throw new Error('create requires --slug');
      cmdCreate(opts);
      break;
    case 'get-config':
      if (!opts.slug) throw new Error('get-config requires --slug');
      cmdGetConfig(opts);
      break;
    case 'update-config':
      if (!opts.slug) throw new Error('update-config requires --slug');
      cmdUpdateConfig(opts);
      break;
    case 'pick-avatar':
      cmdPickAvatar(opts);
      break;
    case 'set-avatar':
      if (!opts.slug) throw new Error('set-avatar requires --slug');
      cmdSetAvatar(opts);
      break;
    case 'add-skills':
      if (!opts.slug) throw new Error('add-skills requires --slug');
      cmdAddSkills(opts);
      break;
    case 'update-soul':
      if (!opts.slug) throw new Error('update-soul requires --slug');
      if (!opts.soulFile && !opts.soulText) throw new Error('update-soul requires --soul-file or --soul-text');
      cmdUpdateSoul(opts);
      break;
    case 'set-model':
      if (!opts.slug) throw new Error('set-model requires --slug');
      cmdSetModel(opts);
      break;
    case 'spawn':
      if (!opts.slug) throw new Error('spawn requires --slug');
      cmdSpawn(opts);
      break;
    case 'stop':
      if (!opts.slug) throw new Error('stop requires --slug');
      cmdStop(opts);
      break;
    case 'delete':
      if (!opts.slug) throw new Error('delete requires --slug');
      cmdDelete(opts);
      break;
    case 'list':
      cmdList();
      break;
    default:
      throw new Error(`Unknown command: ${opts.command}`);
  }
}

try {
  main();
} catch (err) {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
}

