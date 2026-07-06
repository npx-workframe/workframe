#!/usr/bin/env node
/**
 * Pick next backlog item for agent loops.
 * Stage order from backlog.json program_stages (WF-040) — default B→C→D.
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

const stageRank = buildStageRank(backlog.program_stages);
const outOfScope = loadOutOfScope();

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
  (i) =>
    (i.status === 'todo' || i.status === 'partial') &&
    depsMet(i) &&
    i.priority !== 'P3' &&
    !outOfScope.has(i.id)
);
candidates.sort((a, b) => {
  const ra = stageRank(a.id);
  const rb = stageRank(b.id);
  return (
    ra.stage - rb.stage ||
    ra.order - rb.order ||
    pri[a.priority] - pri[b.priority] ||
    a.id.localeCompare(b.id)
  );
});

const pick = candidates[0];
if (!pick) {
  console.log(jsonOut ? 'null' : 'No eligible todo items (check depends_on or deferred).');
  process.exit(0);
}

if (jsonOut) console.log(JSON.stringify(pick, null, 2));
else printItem(pick);

function buildStageRank(programStages) {
  const idToStage = {};
  const idOrderInStage = {};
  if (programStages?.by_stage) {
    for (const [stage, ids] of Object.entries(programStages.by_stage)) {
      ids.forEach((id, i) => {
        idToStage[id] = stage;
        idOrderInStage[id] = i;
      });
    }
  }
  const pickOrder = programStages?.pick_order ?? ['B', 'C', 'D'];
  const order = [...pickOrder, 'meta', 'A', 'E', 'F'];
  const rank = Object.fromEntries(order.map((s, i) => [s, i]));
  return (id) => ({
    stage: rank[idToStage[id]] ?? 99,
    order: idOrderInStage[id] ?? 999,
  });
}

function loadOutOfScope() {
  try {
    const queues = JSON.parse(readFileSync(join(root, 'operations/pm/queues.json'), 'utf8'));
    return new Set(queues.out_of_scope ?? []);
  } catch {
    return new Set();
  }
}

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
