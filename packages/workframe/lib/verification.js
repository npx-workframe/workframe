import os from 'node:os';
import process from 'node:process';

import { HTTP_TIMEOUT_MS, VERIFICATION_TIMEOUT_MS } from './package-info.js';
import { abortReason, buildInferenceEnv, firstLine, runChildCommand } from './process.js';

const VERIFICATION_TOKEN = 'WORKFRAME_OK';
const exactToken = (value) => typeof value === 'string' && value.trim() === VERIFICATION_TOKEN;
const lastExact = (messages) => messages.length > 0 && exactToken(messages.at(-1));

export function parseCodexVerificationOutput(stdout) {
  const messages = [];
  for (const line of String(stdout || '').split(/\r?\n/)) {
    if (!line.trim()) continue;
    try {
      const event = JSON.parse(line);
      if (event?.type === 'item.completed' && event?.item?.type === 'agent_message') messages.push(event.item.text);
      else if (event?.type === 'message' && event?.role === 'assistant') messages.push(typeof event.content === 'string' ? event.content : event.text);
    } catch {
      // Ignore non-JSON diagnostics and prompt echoes.
    }
  }
  return lastExact(messages);
}

export function parseClaudeVerificationOutput(stdout) {
  try {
    const payload = JSON.parse(String(stdout || ''));
    return payload?.type === 'result' && payload?.subtype === 'success' && exactToken(payload.result);
  } catch {
    return false;
  }
}

export function parseOpenAIResponse(payload) {
  const messages = [];
  for (const output of payload?.output || []) {
    if (output?.type !== 'message' || output?.role !== 'assistant') continue;
    for (const content of output.content || []) if (content?.type === 'output_text') messages.push(content.text);
  }
  return lastExact(messages);
}

export function parseOpenRouterResponse(payload) {
  return exactToken(payload?.choices?.[0]?.message?.content);
}

function timeoutSignal(parentSignal, timeoutMs) {
  const controller = new AbortController();
  const fromParent = () => controller.abort(parentSignal.reason || new DOMException('Aborted', 'AbortError'));
  if (parentSignal?.aborted) fromParent();
  else parentSignal?.addEventListener?.('abort', fromParent, { once: true });
  const timer = setTimeout(() => controller.abort(new DOMException('Verification timed out', 'TimeoutError')), timeoutMs);
  timer.unref?.();
  return {
    signal: controller.signal,
    close() {
      clearTimeout(timer);
      parentSignal?.removeEventListener?.('abort', fromParent);
    },
  };
}

async function readJson(response) {
  try { return await response.json(); } catch { return null; }
}

async function testHttpProvider(candidate, sourceEnv, fetchImpl, parentSignal) {
  const timed = timeoutSignal(parentSignal, HTTP_TIMEOUT_MS);
  try {
    const openAI = candidate.adapter === 'openai-http';
    const response = await fetchImpl(openAI ? 'https://api.openai.com/v1/responses' : 'https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: {
        authorization: `Bearer ${sourceEnv[candidate.credentialEnvNames[0]]}`,
        'content-type': 'application/json',
        ...(openAI ? {} : { 'x-title': 'Workframe local link test' }),
      },
      body: JSON.stringify(openAI ? {
        model: 'gpt-4o-mini', input: 'Reply with exactly WORKFRAME_OK and nothing else.', max_output_tokens: 8,
      } : {
        model: 'openai/gpt-4o-mini',
        messages: [{ role: 'user', content: 'Reply with exactly WORKFRAME_OK and nothing else.' }],
        max_tokens: 8, temperature: 0,
      }),
      signal: timed.signal,
    });
    const payload = await readJson(response);
    return {
      ok: response.ok && (openAI ? parseOpenAIResponse(payload) : parseOpenRouterResponse(payload)),
      detail: response.ok ? `${openAI ? 'OpenAI' : 'OpenRouter'} responded.` : `${openAI ? 'OpenAI' : 'OpenRouter'} returned HTTP ${response.status}.`,
    };
  } catch {
    if (timed.signal.aborted) {
      return {
        ok: false, cancelled: true,
        reason: timed.signal.reason?.name === 'TimeoutError' ? 'timeout' : abortReason(parentSignal),
        detail: 'Verification request cancelled.',
      };
    }
    return { ok: false, detail: `${candidate.label} verification request failed.` };
  } finally {
    timed.close();
  }
}

export async function runInferenceTest(candidate, options = {}) {
  const sourceEnv = options.env || process.env;
  const execute = options.execute || runChildCommand;
  const signal = options.signal;
  const childEnv = buildInferenceEnv(candidate, sourceEnv);
  if (candidate.adapter === 'codex-cli') {
    const result = await execute('codex', [
      'exec', '--json', '--skip-git-repo-check', '--sandbox', 'read-only', '--color', 'never',
      'Reply with exactly WORKFRAME_OK and nothing else. Do not inspect files or run tools.',
    ], { timeout: VERIFICATION_TIMEOUT_MS, cwd: os.tmpdir(), env: childEnv, redactionEnv: sourceEnv, signal });
    if (result.cancelled) return result;
    return { ok: result.ok && parseCodexVerificationOutput(result.stdout), detail: result.ok ? 'Codex responded.' : firstLine(result.stderr || result.error || 'Codex verification failed.') };
  }
  if (candidate.adapter === 'claude-cli') {
    const result = await execute('claude', [
      '-p', '--output-format', 'json', '--permission-mode', 'plan', '--max-turns', '1',
      '--max-budget-usd', '0.02', '--no-session-persistence',
      'Reply with exactly WORKFRAME_OK and nothing else.',
    ], { timeout: VERIFICATION_TIMEOUT_MS, cwd: os.tmpdir(), env: childEnv, redactionEnv: sourceEnv, signal });
    if (result.cancelled) return result;
    return { ok: result.ok && parseClaudeVerificationOutput(result.stdout), detail: result.ok ? 'Claude responded.' : firstLine(result.stderr || result.error || 'Claude verification failed.') };
  }
  if (['openai-http', 'openrouter-http'].includes(candidate.adapter)) {
    return testHttpProvider(candidate, sourceEnv, options.fetch || globalThis.fetch, signal);
  }
  return { ok: false, detail: 'No verification adapter is available.' };
}
