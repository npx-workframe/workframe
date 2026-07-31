import { BEGIN_QUESTIONS, buildFirstMirror } from './mirror.js';
import { sanitizeBoundedText } from './text.js';

export async function runBegin({ json = false, seed = {}, ask, close }) {
  const session = { ...seed };
  let stopped = false;
  let stop_reason = null;

  for (const question of BEGIN_QUESTIONS) {
    if (sanitizeBoundedText(session[question.key])) continue;

    if (!ask) break;

    const answer = await ask(question);
    if (answer === null) {
      stopped = true;
      stop_reason = 'eof_or_interrupt';
      break;
    }

    const text = sanitizeBoundedText(answer);
    if (!text) {
      stopped = true;
      stop_reason = 'empty';
      break;
    }
    session[question.key] = text;
  }

  const mirror = buildFirstMirror(session, { stopped, stop_reason });
  if (close) close();
  return { session, mirror };
}

export function printBeginMirror(mirror, color) {
  console.log(color.brightGreen('\n  WORKFRAME // FIRST MIRROR'));
  console.log(color.dim('  Memory only. No files written. No network calls.'));
  for (const [key, field] of Object.entries(mirror.fields)) {
    const value = field.value ?? color.dim('unresolved');
    console.log(`  ${color.bold(key)}: ${value} (${field.provenance})`);
  }
  if (mirror.unresolved_questions.length) {
    console.log(color.dim(`  unresolved: ${mirror.unresolved_questions.join(', ')}`));
  }
  console.log('');
}
