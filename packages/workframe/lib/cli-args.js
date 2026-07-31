import readline from 'node:readline/promises';
import { BEGIN_QUESTIONS } from './mirror.js';

export function createInteractiveAsk() {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  let interrupted = false;

  process.once('SIGINT', () => {
    interrupted = true;
    rl.close();
  });

  const ask = async (question) => {
    if (!process.stdin.isTTY || interrupted) return null;
    console.log(`\n  ${question.architect}`);
    try {
      return await rl.question(`  ${question.prompt}\n  > `);
    } catch {
      return null;
    }
  };

  const close = () => rl.close();
  return { ask, close, rl };
}

export function seedFromFlags(args) {
  const session = {};
  for (const question of BEGIN_QUESTIONS) {
    const inline = args.find((arg) => arg.startsWith(`--${question.key}=`));
    if (inline) session[question.key] = inline.slice(question.key.length + 3);
    const index = args.indexOf(`--${question.key}`);
    if (index >= 0 && args[index + 1] && !args[index + 1].startsWith('-')) {
      session[question.key] = args[index + 1];
    }
  }
  return session;
}

export function findFlagValue(args, name) {
  const inline = args.find((arg) => arg.startsWith(`${name}=`));
  if (inline) return inline.slice(name.length + 1);
  const index = args.indexOf(name);
  if (index >= 0 && args[index + 1] && !args[index + 1].startsWith('-')) return args[index + 1];
  return undefined;
}
