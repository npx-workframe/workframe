#!/usr/bin/env node
/** Workframe compatibility selector. The Architectonic Rail protocol is canonical. */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "../..");
const ledger = JSON.parse(readFileSync(join(root, "docs/ledger/ledger.json"), "utf8"));
const args = process.argv.slice(2);
const jsonOut = args.includes("--json");
const wantId = args.includes("--id") ? args[args.indexOf("--id") + 1] : null;
const role = args.includes("--role") ? args[args.indexOf("--role") + 1] : null;
const byId = new Map(ledger.items.map((item) => [item.id, item]));
const priority = { P0: 0, P1: 1, P2: 2, P3: 3 };

let item;
if (wantId) {
  item = byId.get(wantId);
  if (!item) throw new Error(`unknown id: ${wantId}`);
} else {
  const status = role === "reviewer" ? "review" : "ready";
  item = ledger.items
    .filter((candidate) => candidate.status === status)
    .filter((candidate) => candidate.depends_on.every((id) => byId.get(id)?.status === "done"))
    .filter((candidate) => !role || role === "reviewer" || candidate.owner_role === role)
    .sort((a, b) => priority[a.priority] - priority[b.priority] || a.id.localeCompare(b.id))[0];
}

if (!item) {
  console.log(jsonOut ? "null" : "No eligible Workframe item.");
  process.exit(0);
}
if (jsonOut) console.log(JSON.stringify(item, null, 2));
else {
  console.log(`${item.id} [${item.priority}] ${item.status} — ${item.title}`);
  console.log(`owner: ${item.owner_role}`);
  for (const criterion of item.acceptance) console.log(`acceptance: ${criterion}`);
}
