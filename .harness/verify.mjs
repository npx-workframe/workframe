#!/usr/bin/env node
/**
 * Workframe harness verify — runs feature_list.json scenarios and updates passes flags.
 * ponytail: sequential shell exec; upgrade path = matrix runner + junit output.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const listPath = path.join(root, ".harness", "feature_list.json");
const checkOnly =
  process.argv.includes("--check") || process.env.HARNESS_CHECK === "1";
const data = JSON.parse(readFileSync(listPath, "utf8"));

let failed = 0;
let blockedLocal = 0;
for (const s of data.scenarios) {
  if (s.verify.startsWith("manual")) {
    console.log(`[skip] ${s.id}: ${s.verify}`);
    continue;
  }
  if (s.owner === "cursor-local") {
    if (s.passes) {
      console.log(`[pass] ${s.id}: local (recorded)`);
    } else {
      blockedLocal++;
      console.log(`[blocked-local] ${s.id}: not passing — run verify-release-gates before publish`);
    }
    continue;
  }
  const r = spawnSync(s.verify, { shell: true, cwd: root, stdio: "inherit" });
  s.passes = r.status === 0;
  if (!s.passes) failed++;
  console.log(s.passes ? `[pass] ${s.id}` : `[fail] ${s.id}`);
}

if (!checkOnly) {
  data.updated = new Date().toISOString().slice(0, 10);
  writeFileSync(listPath, JSON.stringify(data, null, 2) + "\n");
} else {
  console.log(`[harness] check-only mode — ${failed ? failed + " failed" : "all passed"}`);
  if (blockedLocal) {
    console.log(
      `[harness] ${blockedLocal} local gate(s) blocked — CI may pass; release requires node scripts/workframe/verify-release-gates.mjs`,
    );
  }
}
process.exit(failed ? 1 : 0);
