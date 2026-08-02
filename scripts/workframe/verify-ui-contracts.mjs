#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const profilePath = path.join(
  root,
  'apps/web/src/components/workspace/UserProfileSheet.tsx',
);
const profileSource = fs.readFileSync(profilePath, 'utf8');
const updatesSource = fs.readFileSync(
  path.join(root, 'apps/web/src/components/workspace/StackUpdatesPanel.tsx'),
  'utf8',
);
const failures = [];

function requireContract(condition, message) {
  if (!condition) failures.push(message);
}

requireContract(
  profileSource.includes("import { WfActionButton } from '@/components/ui/WfActionButton'"),
  'UserProfileSheet must use the theme-aware WfActionButton.',
);
requireContract(
  !profileSource.includes("import { Button } from '@/components/ui/button'"),
  'UserProfileSheet must not import the legacy filled Button.',
);

const actionsStart = profileSource.indexOf('      actions={');
const footerStart = profileSource.indexOf('      footer={', actionsStart);
requireContract(actionsStart >= 0, 'UserProfileSheet must provide SettingsSheetFrame actions.');
requireContract(footerStart > actionsStart, 'UserProfileSheet actions must precede the rail footer.');

if (actionsStart >= 0 && footerStart > actionsStart) {
  const actions = profileSource.slice(actionsStart, footerStart);
  requireContract(actions.includes("tab === 'profile'"), 'Profile Save must only appear on the profile tab.');
  requireContract(actions.includes('<WfActionButton'), 'Profile Save must be a WfActionButton.');
  requireContract(actions.includes('tone="primary"'), 'Profile Save must use the primary theme-aware tone.');
  requireContract(actions.includes('Save changes'), 'Profile Save must remain in the settings action footer.');
}

if (footerStart >= 0) {
  const bodyStart = profileSource.indexOf('\n    >', footerStart);
  if (bodyStart >= 0) {
    const body = profileSource.slice(bodyStart);
    requireContract(
      !body.includes('Save changes'),
      'Profile Save must not be rendered inside scrollable settings body content.',
    );
  }
}

requireContract(
  updatesSource.includes("reloadUrl.searchParams.set('_wf_reload', Date.now().toString(36))"),
  'Stack updater reload must use a unique URL so stale index HTML cannot survive an update.',
);
requireContract(
  updatesSource.includes('window.location.replace(reloadUrl.toString())'),
  'Stack updater must navigate to the cache-busted Workframe URL after health verification.',
);
requireContract(
  !updatesSource.includes('window.location.reload()'),
  'Stack updater must not use a cache-reusable location.reload().',
);

if (failures.length) {
  console.error('UI CONTRACT VERIFY FAILED:');
  for (const failure of failures) console.error(`  - ${failure}`);
  process.exit(1);
}

console.log('OK: profile settings Save is pinned to the theme-aware action footer.');
