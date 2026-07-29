#!/usr/bin/env node

const args = process.argv.slice(2);
const command = args.find((arg) => !arg.startsWith('-'));

if (command === 'start') {
  const { runOriginStart } = await import('./origin-start.js');
  await runOriginStart(args.slice(args.indexOf('start') + 1));
} else {
  await import('./workframe.js');
  if (command === 'help') {
    console.log('\nAdditional command:\n  start      Begin the experimental plan-only formation preflight.');
  }
}
