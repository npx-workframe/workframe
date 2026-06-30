#!/usr/bin/env node
/**
 * Doctor repair for dogfood compose (infra/compose/workframe).
 * Explicit opt-in — provisions missing u-* runtimes for agent DM rooms.
 *
 *   node scripts/workframe/doctor-repair.mjs           # audit only
 *   node scripts/workframe/doctor-repair.mjs --repair  # provision missing
 */
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const composeDir = path.resolve(__dirname, '../../infra/compose/workframe');
const repair = process.argv.includes('--repair');

function run() {
  const fn = repair ? 'doctor_repair_agent_dm_runtimes(repair=True)' : 'doctor_audit_agent_dm_runtimes()';
  const py = `import json, server; print(json.dumps(server.${fn}))`;
  const res = spawnSync(
    'docker',
    ['compose', 'exec', '-T', 'workframe-api', 'python3', '-c', py],
    { cwd: composeDir, encoding: 'utf8' },
  );
  if (res.status !== 0) {
    console.error(res.stderr || res.stdout || 'docker compose exec failed — is the stack running?');
    process.exit(res.status || 1);
  }
  const out = (res.stdout || '').trim();
  let data;
  try {
    data = JSON.parse(out.split('\n').pop());
  } catch {
    console.error('Unexpected output:', out);
    process.exit(1);
  }
  console.log(JSON.stringify(data, null, 2));
  if (repair) {
    const failed = data.failed?.length ?? 0;
    const still = data.still_missing?.length ?? 0;
    if (failed || still) process.exit(1);
    return;
  }
  if ((data.missing?.length ?? 0) > 0) process.exit(1);
}

run();
