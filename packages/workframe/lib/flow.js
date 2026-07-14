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

function inputReasonFromSignal(signal, fallback = 'interrupt') {
  const reason = signal?.reason;
  if (reason instanceof InputEndedError) return reason.reason;
  if (typeof reason?.reason === 'string') return reason.reason;
  return fallback;
}

function throwIfAborted(signal) {
  if (signal?.aborted) throw new InputEndedError(inputReasonFromSignal(signal));
}

async function askQuestion(ask, prompt, timeoutMs) {
  try {
    return await ask(prompt, { timeoutMs });
  } catch (error) {
    if (error instanceof InputEndedError) throw error;
    if (error?.name === 'AbortError') throw new InputEndedError('timeout');
    if (error?.code === 'ERR_USE_AFTER_CLOSE') throw new InputEndedError('eof');
    throw error;
  }
}

async function selectCandidate({ ask, write, candidates, timeoutMs }) {
  if (candidates.length === 0) return null;
  if (candidates.length === 1) return candidates[0];

  writeLines(write, [
    '',
    '  I found more than one inference path I can test:',
    ...candidates.map((candidate) => `    ▶ ${candidate.label}`),
  ]);

  let answer = await askQuestion(ask, '\n  Which one should we speak through?\n  > ', timeoutMs);
  let selection = interpretCandidateChoice(answer, candidates);
  if (selection.kind === 'selected') return selection.candidate;

  const reason = selection.kind === 'ambiguous'
    ? 'You named more than one path.'
    : 'I could not tell which path you meant.';
  answer = await askQuestion(
    ask,
    `\n  ${reason} Name one path exactly, or explicitly delegate the choice.\n  > `,
    timeoutMs,
  );
  selection = interpretCandidateChoice(answer, candidates);
  return selection.kind === 'selected' ? selection.candidate : null;
}

function stopForInput(write, error, suffix = 'Nothing was sent or changed.') {
  write(`\n  Input ${error.reason === 'timeout' ? 'timed out' : 'ended'}. ${suffix}\n`);
  return { status: 'stopped', reason: error.reason };
}

export async function runInteractiveFlow({
  candidates,
  begin,
  ask,
  verify,
  write = () => {},
  timeoutMs = 120_000,
  signal,
}) {
  let candidate;
  try {
    throwIfAborted(signal);
    candidate = await selectCandidate({ ask, write, candidates, timeoutMs });
  } catch (error) {
    if (error instanceof InputEndedError) return stopForInput(write, error);
    throw error;
  }

  if (!candidate) {
    write('\n  I could not resolve one inference path safely. Nothing was sent or changed.\n');
    return { status: 'stopped', reason: candidates.length === 0 ? 'no-candidate' : 'ambiguous-candidate' };
  }

  writeLines(write, [
    '',
    `  I can make one tiny verification call through ${candidate.label}.`,
    `  Billing source: ${candidate.billing}.`,
    `  ${candidate.credentialDisclosure}`,
    '  Nothing else will be installed or changed.',
  ]);

  let consent;
  try {
    consent = interpretConsent(await askQuestion(ask, '\n  Shall I test this exact link?\n  > ', timeoutMs));
    if (consent === 'unknown') {
      consent = interpretConsent(await askQuestion(
        ask,
        '\n  I could not treat that as authorization. Say an explicit yes or no.\n  > ',
        timeoutMs,
      ));
    }
  } catch (error) {
    if (error instanceof InputEndedError) return stopForInput(write, error);
    throw error;
  }

  if (consent !== 'yes') {
    write('\n  No explicit approval was received. Nothing was sent or changed.\n');
    return { status: 'stopped', reason: consent === 'no' ? 'declined' : 'ambiguous-consent' };
  }

  let verification;
  try {
    throwIfAborted(signal);
    verification = await verify(candidate, { signal });
    throwIfAborted(signal);
  } catch (error) {
    if (error instanceof InputEndedError || signal?.aborted || error?.name === 'AbortError') {
      const reason = error instanceof InputEndedError ? error.reason : inputReasonFromSignal(signal);
      write('\n  Verification was interrupted. The inference process was cancelled and no draft was created.\n');
      return { status: 'stopped', reason, candidate };
    }
    verification = { ok: false, detail: error instanceof Error ? error.message : String(error) };
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
    throwIfAborted(signal);
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
      const stopped = stopForInput(write, error, 'No draft was persisted.');
      return { ...stopped, candidate };
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
    '  No package, runtime, agent, or Workframe installation was changed.\n',
  ]);
  return { status: 'completed', candidate, seed };
}
