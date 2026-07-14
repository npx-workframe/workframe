import os from 'node:os';
import process from 'node:process';

import {
  abortReason,
  buildChildEnv,
  createAbortError,
  runCommandAsync,
  sanitizeExecutionResult,
} from './process.js';

const TEST_TIMEOUT_MS = 90_000;
const VERIFICATION_TOKEN = 'WORKFRAME_OK';

function firstLine(value) {
  return String(value || '').split(/\r?\n/).map((line) => line.trim()).find(Boolean) || '';
}

function exactVerificationToken(value) {
  return typeof value === 'string' && value.trim() === VERIFICATION_TOKEN;
}

function lastExactMessage(messages) {
  return messages.length > 0 && exactVerificationToken(messages.at(-1));
}

export function parseCodexVerificationOutput(stdout) {
  const messages = [];
  for (const line of String(stdout || '').split(/\r?\n/)) {
    if (!line.trim()) continue;
    let event;
    try {
      event = JSON.parse(line);
    } catch {
      continue;
    }
    if (event?.type === 'item.completed' && event?.item?.type === 'agent_message') {
      messages.push(event.item.text);
    } else if (event?.type === 'message' && event?.role === 'assistant') {
      messages.push(typeof event.content === 'string' ? event.content : event.text);
    }
  }
  return lastExactMessage(messages);
}

export function parseClaudeVerificationOutput(stdout) {
  let payload;
  try {
    payload = JSON.parse(String(stdout || ''));
  } catch {
    return false;
  }
  return payload?.type === 'result'
    && payload?.subtype === 'success'
    && exactVerificationToken(payload.result);
}

export function parseOpenAIResponse(payload) {
  const messages = [];
  for (const output of payload?.output || []) {
    if (output?.type !== 'message' || output?.role !== 'assistant') continue;
    for (const content of output.content || []) {
      if (content?.type === 'output_text') messages.push(content.text);
    }
  }
  return lastExactMessage(messages);
}

export function parseOpenRouterResponse(payload) {
  const content = payload?.choices?.[0]?.message?.content;
  return exactVerificationToken(content);
}

async function readJsonResponse(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function createRequestSignal(externalSignal, timeoutMs) {
  const controller = new AbortController();
  const onAbort = () => controller.abort(externalSignal.reason);
  if (externalSignal?.aborted) onAbort();
  else externalSignal?.addEventListener?.('abort', onAbort, { once: true });
  const timer = setTimeout(() => controller.abort(createAbortError('timeout')), timeoutMs);
  timer.unref?.();
  return {
    signal: controller.signal,
    cleanup() {
      clearTimeout(timer);
      externalSignal?.removeEventListener?.('abort', onAbort);
    },
  };
}

function rethrowExternalAbort(error, signal) {
  if (signal?.aborted) throw createAbortError(abortReason(signal));
  return error;
}

async function testOpenAI(env, fetchImpl, signal) {
  const request = createRequestSignal(signal, 30_000);
  let response;
  try {
    response = await fetchImpl('https://api.openai.com/v1/responses', {
      method: 'POST',
      headers: {
        authorization: `Bearer ${env.OPENAI_API_KEY}`,
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        input: 'Reply with exactly WORKFRAME_OK and nothing else.',
        max_output_tokens: 8,
      }),
      signal: request.signal,
    });
  } catch (error) {
    rethrowExternalAbort(error, signal);
    return { ok: false, detail: 'OpenAI verification request failed.' };
  } finally {
    request.cleanup();
  }
  const payload = await readJsonResponse(response);
  return {
    ok: response.ok && parseOpenAIResponse(payload),
    detail: response.ok ? 'OpenAI responded.' : `OpenAI returned HTTP ${response.status}.`,
  };
}

async function testOpenRouter(env, fetchImpl, signal) {
  const request = createRequestSignal(signal, 30_000);
  let response;
  try {
    response = await fetchImpl('https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: {
        authorization: `Bearer ${env.OPENROUTER_API_KEY}`,
        'content-type': 'application/json',
        'x-title': 'Workframe local link test',
      },
      body: JSON.stringify({
        model: 'openai/gpt-4o-mini',
        messages: [{ role: 'user', content: 'Reply with exactly WORKFRAME_OK and nothing else.' }],
        max_tokens: 8,
        temperature: 0,
      }),
      signal: request.signal,
    });
  } catch (error) {
    rethrowExternalAbort(error, signal);
    return { ok: false, detail: 'OpenRouter verification request failed.' };
  } finally {
    request.cleanup();
  }
  const payload = await readJsonResponse(response);
  return {
    ok: response.ok && parseOpenRouterResponse(payload),
    detail: response.ok ? 'OpenRouter responded.' : `OpenRouter returned HTTP ${response.status}.`,
  };
}

export async function runInferenceTest(candidate, dependencies = {}) {
  const sourceEnv = dependencies.env || process.env;
  const execute = dependencies.runAsync || runCommandAsync;
  const fetchImpl = dependencies.fetch || globalThis.fetch;
  const signal = dependencies.signal;
  const childEnv = buildChildEnv(candidate, sourceEnv, 'inference');
  const adapter = candidate.adapter || candidate.id;

  if (adapter === 'codex') {
    const raw = await execute('codex', [
      'exec',
      '--json',
      '--skip-git-repo-check',
      '--sandbox', 'read-only',
      '--color', 'never',
      'Reply with exactly WORKFRAME_OK and nothing else. Do not inspect files or run tools.',
    ], {
      timeout: TEST_TIMEOUT_MS,
      cwd: os.tmpdir(),
      env: childEnv,
      redactionEnv: sourceEnv,
      signal,
    });
    const result = sanitizeExecutionResult(raw, sourceEnv);
    return {
      ok: result.ok && parseCodexVerificationOutput(result.stdout),
      detail: result.ok ? 'Codex responded.' : firstLine(result.stderr || result.error || 'Codex test failed.'),
    };
  }
  if (adapter === 'claude') {
    const raw = await execute('claude', [
      '-p',
      '--output-format', 'json',
      '--permission-mode', 'plan',
      '--max-turns', '1',
      '--max-budget-usd', '0.02',
      '--no-session-persistence',
      'Reply with exactly WORKFRAME_OK and nothing else.',
    ], {
      timeout: TEST_TIMEOUT_MS,
      cwd: os.tmpdir(),
      env: childEnv,
      redactionEnv: sourceEnv,
      signal,
    });
    const result = sanitizeExecutionResult(raw, sourceEnv);
    return {
      ok: result.ok && parseClaudeVerificationOutput(result.stdout),
      detail: result.ok ? 'Claude responded.' : firstLine(result.stderr || result.error || 'Claude test failed.'),
    };
  }
  if (adapter === 'openrouter') return testOpenRouter(sourceEnv, fetchImpl, signal);
  if (adapter === 'openai') return testOpenAI(sourceEnv, fetchImpl, signal);
  return { ok: false, detail: 'No test adapter is available.' };
}
