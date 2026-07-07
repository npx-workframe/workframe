#!/usr/bin/env node
/** CI/harness API self-checks — same coverage as package.json typecheck. */
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const dir = path.dirname(fileURLToPath(import.meta.url));
const py = process.env.PYTHON || 'python';
const steps = [
  ['-m', 'py_compile', 'server.py', 'zk_auth.py', 'email_sender.py', 'profile_config_yaml.py', 'route_registry.py', 'auth_gate.py', 'user_prefs.py', 'rooms.py', 'kanban_cron.py', 'hermes_profiles.py', 'profile_gateway.py', 'model_surface.py', 'provider_bootstrap.py', 'db_schema.py', 'workspace_files.py', 'activity_feed.py', 'run_surface_wiring.py', 'run_authority.py', 'run_ledger.py', 'domain/entities.py', 'domain/__init__.py'],
  ['test_public_routes.py'],
  ['test_route_registry.py'],
  ['test_billing_provider.py'],
  ['test_model_surface_consistency.py'],
  ['test_profile_model_yaml.py'],
  ['test_domain_entities.py'],
];

for (const args of steps) {
  const r = spawnSync(py, args, { cwd: dir, stdio: 'inherit' });
  if (r.error) {
    console.error(`typecheck spawn failed (${py}):`, r.error.message);
    process.exit(1);
  }
  if (r.status !== 0) process.exit(r.status ?? 1);
}
