#!/usr/bin/env node
/**
 * Pick next backlog item for agent loops.
 * ponytail: O(n) scan; fine for <200 items — index by wave if backlog grows.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '../..');
const backlogPath = join(root, 'docs/ledger/backlog.json');

const args = process.argv.slice(2);
const jsonOut = args.includes('--json');
const role = args.includes('--role') ? args[args.indexOf('--role') + 1] : 'implementer';
const wantId = args.includes('--id') ? args[args.indexOf('--id') + 1] : null;

const backlog = JSON.parse(readFileSync(backlogPath, 'utf8'));
const items = backlog.items;
const byId = Object.fromEntries(items.map((i) => [i.id, i]));

function depsMet(item) {
  return (item.depends_on || []).every((id) => {
    const d = byId[id];
    return d && (d.status === 'done' || d.status === 'partial');
  });
}

const pri = { P0: 0, P1: 1, P2: 2, P3: 3 };

if (wantId) {
  const item = byId[wantId];
  if (!item) {
    console.error(`unknown id: ${wantId}`);
    process.exit(1);
  }
  if (jsonOut) console.log(JSON.stringify(item, null, 2));
  else printItem(item);
  process.exit(0);
}

if (role === 'reviewer') {
  const review = items.filter((i) => i.status === 'review');
  review.sort((a, b) => pri[a.priority] - pri[b.priority]);
  const pick = review[0];
  if (!pick) {
    console.log(jsonOut ? 'null' : 'No items in review.');
    process.exit(0);
  }
  if (jsonOut) console.log(JSON.stringify(pick, null, 2));
  else printItem(pick);
  process.exit(0);
}

const candidates = items.filter(
  (i) => i.status === 'todo' && depsMet(i) && i.priority !== 'P3'
);
candidates.sort((a, b) => pri[a.priority] - pri[b.priority] || a.id.localeCompare(b.id));

const pick = candidates[0];
if (!pick) {
  console.log(jsonOut ? 'null' : 'No eligible todo items (check depends_on or deferred).');
  process.exit(0);
}

if (jsonOut) console.log(JSON.stringify(pick, null, 2));
else printItem(pick);

function printItem(item) {
  console.log(`${item.id} [${item.priority}] ${item.status} — ${item.title}`);
  console.log(`wave: ${item.wave}`);
  if (item.summary) console.log(`summary: ${item.summary}`);
  if (item.acceptance?.length) {
    console.log('acceptance:');
    for (const a of item.acceptance) console.log(`  - ${a}`);
  }
  if (item.spec?.spec) console.log(`spec: ${item.spec.spec}`);
  else console.log(`spec: docs/ledger/specs/${item.id}/spec.md (create if missing)`);
}
