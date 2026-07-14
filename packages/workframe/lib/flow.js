import { interpretCandidateChoice, interpretConsent } from './dialogue.js';
import { cleanFreeText, createSessionSeed } from './session.js';

export class InputEndedError extends Error {
  constructor(reason = 'eof') {
    super(`Input ended: ${reason}`);
    this.name = 'InputEndedError';
    this.reason = reason;
  }
}

function writeLines(write, lines) {
  for (const line of lines) write(line);
}

function reasonFromAbort(signal, fallback = 'interrupt') {
  const reason = signal?.reason;
  if (reason instanceof InputEndedError) return reason.reason;
  if (typeof reason?.reason === 'string') return reason.reason;
  if (reason?.name === 'TimeoutError') return 'timeout';
  return fallback;
}

async function askQuestion(ask, prompt, timeoutMs) {
  try {
    return await ask(prompt, { timeoutMs });
  } catch (error) {
    if (error instanceof InputEndedError) throw error;
    if (error?.name === 'AbortError' || error?.name === 'TimeoutError') {
      throw new InputEndedError(error.name === 'TimeoutError' ? 'timeout' : 'interrupt');
    }
    if (error?.code === 'ERR_USE_AFTER_CLOSE') throw new InputEndedError('eof');
    throw error;
  }
}

async function selectCandidate({ ask, write, candidates, timeoutMs }) {
  if (candidates.length === 0) return null;
  if (candidates.length === 1) return candidates[0];

  writeLines(write, [
    '',
    '  I found more than one inference path I can verify:',
    ...candidates.map((candidate) => `    ▶ ${candidate.label}`),
  ]);

  let answer = await askQuestion(ask, '\n  Which one should we speak through?\n  > ', timeoutMs);
  let selection = interpretCandidateChoice(answer, candidates);
  if (selection.kind === 'selected') return selection.candidate;

  const reason = selection.kind === 'ambiguous'
    ? 'You named more than one path.'
    : 'I could not treat that as one definite path.';
  answer = await askQuestion(
    ask,
    `\n  ${reason} Name one path, exclude paths until one remains, or explicitly delegate the choice.\n  > `,
    timeoutMs,
  );
  selection = interpretCandidateChoice(answer, candidates);
  return selection.kind === 'selected' ? selection.candidate : null;
}

export async function runInteractiveFlow({
  candidates,
  begin,
  ask,
  verify,
  signal,
  write = () => {},
  timeoutMs = 120_000,
}) {
  let candidate;
  try {
    candidate = await selectCandidate({ ask, write, candidates, timeoutMs });
  } catch (error) {
    if (error instanceof InputEndedError) {
      write(`\n  Input ${error.reason === 'timeout' ? 'timed out' : 'ended'}. Nothing was sent or changed.\n`);
      return { status: 'stopped', reason: error.reason };
    }
    throw error;
  }

  if (!candidate) {
    write('\n  I could not resolve one inference path safely. Nothing was sent or changed.\n');
    return { status: 'stopped', reason: candidates.length === 0 ? 'no-candidate' : 'ambiguous-candidate' };
  }

  writeLines(write, [
    '',
    `  I can make one tiny verification call through ${candidate.label}.`,
    `  Payer: ${candidate.billingSource}.`,
    `  Credential source: ${candidate.credentialSource}.`,
    `  Invocation: ${candidate.invocation}.`,
    '  No other credential or authority handle will be sent.',
    '  The selected credential is never printed or persisted by Workframe.',
    '  Nothing will be installed, adopted, overwritten, or changed.',
  ]);

  let consent;
  try {
    consent = interpretConsent(await askQuestion(ask, '\n  Shall I make that exact verification call?\n  > ', timeoutMs));
    if (consent === 'unknown') {
      consent = interpretConsent(await askQuestion(
        ask,
        '\n  I could not treat that as authorization. Say an explicit yes or no.\n  > ',
        timeoutMs,
      ));
    }
  } catch (error) {
    if (error instanceof InputEndedError) {
      write(`\n  Input ${error.reason === 'timeout' ? 'timed out' : 'ended'}. Nothing was sent or changed.\n`);
      return { status: 'stopped', reason: error.reason };
    }
    throw error;
  }

  if (consent !== 'yes') {
    write('\n  No explicit approval was received. Nothing was sent or changed.\n');
    return { status: 'stopped', reason: consent === 'no' ? 'declined' : 'ambiguous-consent' };
  }

  if (signal?.aborted) {
    const reason = reasonFromAbort(signal);
    write(`\n  Verification cancelled (${reason}). Nothing else was sent or changed.\n`);
    return { status: 'stopped', reason, candidate };
  }

  write(`\n  Opening the approved minimal link through ${candidate.label}...`);
  let verification;
  try {
    verification = await verify(candidate, { signal });
  } catch (error) {
    if (signal?.aborted || error?.name === 'AbortError' || error instanceof InputEndedError) {
      const reason = error instanceof InputEndedError ? error.reason : reasonFromAbort(signal);
      write(`\n  Verification cancelled (${reason}). No Socratic session was started.\n`);
      return { status: 'stopped', reason, candidate };
    }
    verification = { ok: false, detail: error instanceof Error ? error.message : String(error) };
  }

  if (verification?.cancelled) {
    const reason = verification.reason || reasonFromAbort(signal, 'timeout');
    write(`\n  Verification cancelled (${reason}). No Socratic session was started.\n`);
    return { status: 'stopped', reason, candidate };
  }

  if (!verification?.ok) {
    writeLines(write, [
      '  × LINK FAILED',
      `  ${verification?.detail || 'Verification failed.'}`,
      '',
    ]);
    return { status: 'failed', reason: 'verification-failed', candidate };
  }

  writeLines(write, ['  ▶ LINK VERIFIED', `  ${verification.detail || `${candidate.label} responded.`}`, '']);
  if (!begin) return { status: 'linked', candidate };

  let preferredName;
  let objective;
  try {
    write('\n  Welcome home, human.');
    write('  We will begin with what is true now. This is a draft, not a commitment.');
    preferredName = await askQuestion(
      ask,
      '\n  Before we define a system, who is speaking? What should I call you?\n  > ',
      timeoutMs,
    );
    objective = cleanFreeText(await askQuestion(
      ask,
      '\n  What are you trying to bring into existence, change, or understand?\n  > ',
      timeoutMs,
    ));
  } catch (error) {
    if (error instanceof InputEndedError) {
      write(`\n  Input ${error.reason === 'timeout' ? 'timed out' : 'ended'}. No draft was persisted.\n`);
      return { status: 'stopped', reason: error.reason, candidate };
    }
    throw error;
  }

  if (!objective) {
    writeLines(write, [
      '\n  I do not yet have a stated objective to mirror.',
      '  No files were written and nothing was installed or changed.\n',
    ]);
    return { status: 'stopped', reason: 'missing-objective', candidate };
  }

  const seed = createSessionSeed({ preferredName, objective, candidate });
  writeLines(write, [
    '',
    '  MIRROR // FIRST DRAFT',
    `    Human: ${seed.human.preferredName}`,
    `    Stated aim: ${seed.entity.statedObjective}`,
    `    Inference path: ${seed.inference.label} (${seed.inference.status})`,
    '    Open questions: purpose, constraints, success criteria',
    '',
    '  I have mirrored only what you said.',
    '  This draft exists in memory only. No files were written.',
    '  No package, runtime, agent, Architectonic layer, or Workframe installation was changed.\n',
  ]);
  return { status: 'completed', candidate, seed };
}
