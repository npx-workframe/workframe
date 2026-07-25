#!/usr/bin/env node
/**
 * ABX visual QA — theme smoke matrix (node fetch only; no Playwright).
 * ponytail: reads generated theme registry + writes pending theme×screen checklist.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const registryPath = path.join(root, 'apps/web/src/generated/architectonicThemes.ts');
const checklistPath = path.join(root, 'docs/ledger/audits/theme-smoke-checklist.json');

/** Mirrors HIDDEN_THEME_PICKER_IDS in apps/web/src/lib/themeOptions.ts */
const HIDDEN_THEME_PICKER_IDS = new Set(['mono', 'neo-color', 'minimal-color', 'leather-book']);

/** Screen matrix from docs/ledger/audits/2026-07-25-abx-visual-qa.md */
const SCREENS = [
  { id: 'install-window', label: 'Install window' },
  { id: 'auth-otp', label: 'Auth OTP' },
  { id: 'wizard', label: 'Wizard (all steps)' },
  { id: 'shell-dockview', label: 'Shell / Dockview' },
  { id: 'chat-composer', label: 'Chat / composer' },
  { id: 'files-browser-activity', label: 'Files / Browser / Activity' },
  { id: 'settings', label: 'Settings (profile, connect, agents, appearance, updates)' },
  { id: 'modals-dialogs', label: 'Modals / dialogs' },
  { id: 'provider-model-pickers', label: 'Provider / model pickers' },
];

const FAMILY_LABELS = {
  lines: 'Lines',
  neo: 'Neo',
  brutalist: 'Brutalist',
  glass: 'Glass',
  custom: 'Custom',
};

function fail(msg) {
  console.error(`theme-smoke-matrix: ${msg}`);
  process.exit(1);
}

function parseArgs(argv) {
  const args = { url: null, writeOnly: false, json: false };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--url') {
      args.url = argv[++i];
      if (!args.url) fail('--url requires a value');
    } else if (arg === '--write-only') {
      args.writeOnly = true;
    } else if (arg === '--json') {
      args.json = true;
    } else if (arg === '--help' || arg === '-h') {
      args.help = true;
    } else {
      fail(`unknown argument: ${arg}`);
    }
  }
  return args;
}

function loadThemeRegistry() {
  if (!fs.existsSync(registryPath)) {
    fail(`missing theme registry: ${registryPath}`);
  }
  const raw = fs.readFileSync(registryPath, 'utf8');
  const match = raw.match(/export const ARCHITECTONIC_THEME_REGISTRY = ([\s\S]+?)\s+as const/);
  if (!match) fail(`could not parse ${registryPath}`);
  return JSON.parse(match[1]);
}

function visibleThemes(registry) {
  return registry.themes
    .filter((theme) => !HIDDEN_THEME_PICKER_IDS.has(theme.id))
    .map((theme) => ({
      id: theme.id,
      label: theme.label,
      family: theme.family,
      familyLabel: FAMILY_LABELS[theme.family] ?? theme.family,
      style: theme.style,
      mode: theme.mode,
      texture: theme.texture,
    }));
}

function buildMatrix(themes) {
  const matrix = [];
  for (const theme of themes) {
    for (const screen of SCREENS) {
      matrix.push({
        theme: theme.id,
        screen: screen.id,
        status: 'pending',
        desktop: 'pending',
        mobile: 'pending',
        notes: '',
      });
    }
  }
  return matrix;
}

function printThemes(themes) {
  console.log(`Visible themes (${themes.length}):`);
  for (const theme of themes) {
    console.log(
      `  ${theme.id.padEnd(22)} family=${theme.familyLabel.padEnd(10)} style=${theme.style}`,
    );
  }
  console.log('');
  console.log(`Hidden from picker (${HIDDEN_THEME_PICKER_IDS.size}): ${[...HIDDEN_THEME_PICKER_IDS].join(', ')}`);
}

async function checkHealth(baseUrl) {
  const url = new URL('/api/meta', baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`);
  const started = Date.now();
  let response;
  try {
    response = await fetch(url, { headers: { accept: 'application/json' } });
  } catch (err) {
    return {
      ok: false,
      url: url.toString(),
      error: err instanceof Error ? err.message : String(err),
      latency_ms: Date.now() - started,
    };
  }

  const latency_ms = Date.now() - started;
  let body = null;
  let parseError = null;
  try {
    body = await response.json();
  } catch (err) {
    parseError = err instanceof Error ? err.message : String(err);
  }

  const metaOk = Boolean(body && body.ok === true);
  return {
    ok: response.ok && metaOk,
    url: url.toString(),
    status: response.status,
    latency_ms,
    meta: body,
    parse_error: parseError,
  };
}

function writeChecklist({ themes, health }) {
  const checklist = {
    schema_version: '0.1',
    campaign: 'ABX visual QA',
    generated_at: new Date().toISOString(),
    source: {
      theme_registry: 'apps/web/src/generated/architectonicThemes.ts',
      visible_filter: 'apps/web/src/lib/themeOptions.ts HIDDEN_THEME_PICKER_IDS',
      audit: 'docs/ledger/audits/2026-07-25-abx-visual-qa.md',
    },
    themes,
    screens: SCREENS,
    health: health ?? null,
    matrix: buildMatrix(themes),
    summary: {
      theme_count: themes.length,
      screen_count: SCREENS.length,
      cell_count: themes.length * SCREENS.length,
      pending_count: themes.length * SCREENS.length,
    },
  };

  fs.mkdirSync(path.dirname(checklistPath), { recursive: true });
  fs.writeFileSync(checklistPath, `${JSON.stringify(checklist, null, 2)}\n`, 'utf8');
  return checklist;
}

function printUsage() {
  console.log(`Usage: node scripts/workframe/theme-smoke-matrix.mjs [options]

Options:
  --url <base>     Fetch /api/meta and verify install health
  --write-only     Skip health check; write checklist only
  --json           Print checklist JSON to stdout after write
  -h, --help       Show this help

Examples:
  node scripts/workframe/theme-smoke-matrix.mjs
  node scripts/workframe/theme-smoke-matrix.mjs --url http://127.0.0.1:18644
  node scripts/workframe/theme-smoke-matrix.mjs --url http://127.0.0.1:18644 --json
`);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printUsage();
    process.exit(0);
  }

  const registry = loadThemeRegistry();
  const themes = visibleThemes(registry);
  if (themes.length !== 14) {
    fail(`expected 14 visible themes, found ${themes.length}`);
  }

  printThemes(themes);

  let health = null;
  if (args.url) {
    health = await checkHealth(args.url);
    if (health.ok) {
      const version = health.meta?.package_version || '?';
      console.log(`Health: OK ${health.url} (${health.status}, ${health.latency_ms}ms, v${version})`);
    } else {
      console.error(`Health: FAIL ${health.url}`);
      if (health.error) console.error(`  error: ${health.error}`);
      if (health.status) console.error(`  status: ${health.status}`);
      if (health.parse_error) console.error(`  parse: ${health.parse_error}`);
      if (health.meta && health.meta.ok !== true) console.error('  meta.ok is not true');
    }
  } else if (!args.writeOnly) {
    console.log('Health: skipped (pass --url to probe /api/meta)');
  }

  const checklist = writeChecklist({ themes, health });
  console.log('');
  console.log(`Checklist: ${path.relative(root, checklistPath)}`);
  console.log(
    `Matrix: ${checklist.summary.theme_count} themes × ${checklist.summary.screen_count} screens = ${checklist.summary.cell_count} pending cells`,
  );

  if (args.json) {
    console.log(JSON.stringify(checklist, null, 2));
  }

  if (health && !health.ok) {
    process.exit(1);
  }
}

main().catch((err) => {
  fail(err instanceof Error ? err.message : String(err));
});
