import process from 'node:process';
import readline from 'node:readline';

import { InputEndedError } from './flow.js';

const QUESTION_TIMEOUT_MS = 120_000;

export function createTerminalDialogue({
  input = process.stdin,
  output = process.stdout,
  signals = process,
  createInterface = readline.createInterface,
} = {}) {
  const rl = createInterface({ input, output });
  const controller = new AbortController();
  let closed = false;
  let terminalReason = null;
  let pending = null;

  function settlePending({ answer, error } = {}) {
    if (!pending) return;
    const current = pending;
    pending = null;
    clearTimeout(current.timer);
    if (error) current.reject(error);
    else current.resolve(answer);
  }

  function stop(reason) {
    if (!terminalReason) terminalReason = reason;
    const ended = new InputEndedError(terminalReason);
    if (!controller.signal.aborted) controller.abort(ended);
    settlePending({ error: ended });
    if (!closed) rl.close();
  }

  function onSigint() {
    stop('interrupt');
  }

  function onInputEnd() {
    stop('eof');
  }

  function onClose() {
    closed = true;
    if (pending) settlePending({ error: new InputEndedError(terminalReason || 'eof') });
  }

  rl.on('SIGINT', onSigint);
  rl.on('close', onClose);
  signals.on?.('SIGINT', onSigint);
  input.once?.('end', onInputEnd);

  return {
    signal: controller.signal,
    ask(prompt, { timeoutMs = QUESTION_TIMEOUT_MS } = {}) {
      if (pending) return Promise.reject(new Error('A terminal question is already pending.'));
      if (closed || terminalReason) return Promise.reject(new InputEndedError(terminalReason || 'eof'));

      return new Promise((resolve, reject) => {
        pending = { resolve, reject, timer: null };
        pending.timer = setTimeout(() => stop('timeout'), timeoutMs);

        try {
          rl.question(prompt, (answer) => settlePending({ answer }));
        } catch (error) {
          if (error?.code === 'ERR_USE_AFTER_CLOSE') {
            stop(terminalReason || 'eof');
            return;
          }
          settlePending({ error });
        }
      });
    },
    close() {
      input.off?.('end', onInputEnd);
      signals.off?.('SIGINT', onSigint);
      rl.off?.('SIGINT', onSigint);
      rl.off?.('close', onClose);
      if (!closed) rl.close();
    },
  };
}
