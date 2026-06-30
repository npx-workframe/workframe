#!/usr/bin/env node
/**
 * Sanitize a child profile's .env after cloning.
 * Removes platform credentials (telegram, discord, slack, etc.)
 * Keeps LLM provider keys (OPENROUTER, OPENAI, ANTHROPIC, etc.)
 *
 * Usage: node sanitize-child-env.mjs <slug>
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

const PLATFORM_KEY_RE = /^(TELEGRAM_|DISCORD_|SLACK_|WHATSAPP_|SIGNAL_|MATTERMATRIX_|HOMEASSISTANT_|QQBOT_|YUANBAO_|GOOGLE_CHAT_|TEAMS_|MATRIX_)/;

const slug = process.argv[2];
if (!slug) {
  console.error('Usage: node sanitize-child-env.mjs <slug>');
  process.exit(1);
}

const envPath = path.join(ROOT, 'Agents', 'profiles', slug, '.env');
if (!fs.existsSync(envPath)) {
  console.error(`No .env found at ${envPath}`);
  process.exit(1);
}

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

console.log(`Sanitized ${slug}/.env:`);
if (removed.length) {
  console.log(`  Removed: ${removed.join(', ')}`);
}
const keptKeys = kept.filter(l => l.trim() && !l.trim().startsWith('#')).map(l => l.split('=')[0]);
if (keptKeys.length) {
  console.log(`  Kept: ${keptKeys.join(', ')}`);
}
