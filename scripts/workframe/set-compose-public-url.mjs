#!/usr/bin/env node
/**
 * Set public URL keys in compose .env (APP_BASE_URL, WORKFRAME_PUBLIC_HOST, CORS, ALLOWED_HOSTS).
 * HERMES_DASHBOARD_PUBLIC_URL is derived from APP_BASE_URL in docker-compose.yml.
 * Usage: node set-compose-public-url.mjs https://dev.example.com [--env path/to/.env]
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const args = process.argv.slice(2);

if (args.includes('--self-check')) {
  function normalizePublicUrl(raw) {
    let u = String(raw || '').trim();
    if (!u) throw new Error('url required');
    if (!/^https?:\/\//i.test(u)) u = `https://${u}`;
    const parsed = new URL(u);
    if (!parsed.hostname) throw new Error('invalid hostname');
    return `https://${parsed.hostname}`;
  }
  if (normalizePublicUrl('dev.example.com') !== 'https://dev.example.com') {
    throw new Error('normalizePublicUrl failed');
  }
  console.log('self-check ok');
  process.exit(0);
}

const envFlag = args.indexOf('--env');
let envPath =
  envFlag >= 0 ? args[envFlag + 1] : path.join(path.dirname(fileURLToPath(import.meta.url)), '../../infra/compose/workframe/.env');
const urlArg = args.find((a) => !a.startsWith('--') && a !== envPath);

if (!urlArg?.trim()) {
  console.error('Usage: node set-compose-public-url.mjs <https://host> [--env path/to/.env]');
  process.exit(1);
}

function normalizePublicUrl(raw) {
  let u = String(raw || '').trim();
  if (!u) throw new Error('url required');
  if (!/^https?:\/\//i.test(u)) u = `https://${u}`;
  const parsed = new URL(u);
  if (!parsed.hostname) throw new Error('invalid hostname');
  return `https://${parsed.hostname}`;
}

function hostnameFromUrl(url) {
  return new URL(url).hostname;
}

function setKv(text, key, val) {
  const line = `${key}=${val}`;
  const re = new RegExp(`^${key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}=.*$`, 'm');
  if (re.test(text)) return text.replace(re, line);
  return `${text}${text.endsWith('\n') || !text ? '' : '\n'}${line}\n`;
}

const publicUrl = normalizePublicUrl(urlArg);
const host = hostnameFromUrl(publicUrl);

if (!fs.existsSync(envPath)) {
  const example = `${envPath}.example`;
  if (fs.existsSync(example)) {
    fs.mkdirSync(path.dirname(envPath), { recursive: true });
    fs.copyFileSync(example, envPath);
    console.log(`Created ${envPath} from example`);
  } else {
    throw new Error(`Missing env file: ${envPath}`);
  }
}

let text = fs.readFileSync(envPath, 'utf8');
text = setKv(text, 'APP_BASE_URL', publicUrl);
text = setKv(text, 'WORKFRAME_PUBLIC_HOST', host);
text = setKv(text, 'ALLOWED_HOSTS', host);
text = setKv(text, 'CORS_ALLOW_ORIGIN', publicUrl);
fs.writeFileSync(envPath, text);

console.log(
  JSON.stringify(
    {
      ok: true,
      env: envPath,
      app_base_url: publicUrl,
      hermes_dashboard_public_url: `${publicUrl}/hermes-dashboard`,
      host,
    },
    null,
    2,
  ),
);
