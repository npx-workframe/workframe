#!/usr/bin/env node
/**
 * Ensure WORKFRAME_HOST_* paths exist in compose .env (VPS in-app publish/sync).
 * Usage: node ensure-compose-host-paths.mjs --project-root /opt/workframe/repo [--env path]
 */
import fs from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
const rootFlag = args.indexOf('--project-root');
const envFlag = args.indexOf('--env');
const projectRoot =
  rootFlag >= 0 ? args[rootFlag + 1] : '/opt/workframe/repo';
const envPath =
  envFlag >= 0
    ? args[envFlag + 1]
    : path.join(projectRoot, 'infra/compose/workframe/.env');
const composeDir = path.join(projectRoot, 'infra/compose/workframe');

function setIfEmpty(text, key, val) {
  const esc = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(`^${esc}=(.*)$`, 'm');
  const m = text.match(re);
  if (m && String(m[1] || '').trim()) return text;
  const line = `${key}=${val}`;
  if (m) return text.replace(re, line);
  return `${text}${text.endsWith('\n') || !text ? '' : '\n'}${line}\n`;
}

if (!fs.existsSync(envPath)) {
  console.error(`Missing env file: ${envPath}`);
  process.exit(1);
}

let text = fs.readFileSync(envPath, 'utf8');
text = setIfEmpty(text, 'WORKFRAME_HOST_PROJECT_ROOT', projectRoot.replace(/\\/g, '/'));
text = setIfEmpty(text, 'WORKFRAME_HOST_COMPOSE_DIR', composeDir.replace(/\\/g, '/'));
fs.writeFileSync(envPath, text);

console.log(
  JSON.stringify(
    {
      ok: true,
      env: envPath,
      project_root: projectRoot.replace(/\\/g, '/'),
      compose_dir: composeDir.replace(/\\/g, '/'),
    },
    null,
    2,
  ),
);
