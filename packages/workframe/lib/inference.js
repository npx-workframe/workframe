import os from 'node:os';
import { spawn } from 'node:child_process';
import process from 'node:process';
import { firstLine, run, TEST_TIMEOUT_MS } from './runtime.js';

const INFERENCE_ENV_ALLOWLIST = ['PATH', 'Path', 'PATHEXT', 'SystemRoot', 'COMSPEC', 'ComSpec', 'HOME', 'USERPROFILE', 'TEMP', 'TMP'];

function minimalInferenceEnv() {
  const env = {};
  for (const key of INFERENCE_ENV_ALLOWLIST) {
    if (process.env[key]) env[key] = process.env[key];
  }
  if (process.env.OPENAI_API_KEY) env.OPENAI_API_KEY = process.env.OPENAI_API_KEY;
  if (process.env.OPENROUTER_API_KEY) env.OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
  if (process.env.ANTHROPIC_API_KEY) env.ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;
  return env;
}

export function spawnCancellable(command, args, options = {}) {
  const env = options.env ?? minimalInferenceEnv();
  const child = spawn(command, args, {
    cwd: options.cwd ?? os.tmpdir(),
    env,
    shell: false,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  let settled = false;
  const abortSignal = options.signal;
  const onAbort = () => {
    if (settled || !child.pid) return;
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'], { windowsHide: true, shell: false });
    } else {
      child.kill('SIGTERM');
    }
  };
  if (abortSignal) {
    if (abortSignal.aborted) onAbort();
    abortSignal.addEventListener('abort', onAbort, { once: true });
  }

  return new Promise((resolve) => {
    let stdout = '';
    let stderr = '';
    child.stdout?.on('data', (chunk) => { stdout += chunk; });
    child.stderr?.on('data', (chunk) => { stderr += chunk; });
    child.on('error', (error) => {
      settled = true;
      resolve({ ok: false, stdout, stderr, error: String(error.message || error), cancelled: abortSignal?.aborted });
    });
    child.on('close', (code) => {
      settled = true;
      resolve({
        ok: code === 0 && !abortSignal?.aborted,
        stdout: stdout.trim(),
        stderr: stderr.trim(),
        cancelled: abortSignal?.aborted,
      });
    });
    if (options.timeoutMs) {
      setTimeout(() => {
        if (!settled) onAbort();
      }, options.timeoutMs);
    }
  });
}

async function testOpenAI(signal) {
  const response = await fetch('https://api.openai.com/v1/responses', {
    method: 'POST',
    headers: {
      authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model: 'gpt-4o-mini',
      input: 'Reply with exactly WORKFRAME_OK and nothing else.',
      max_output_tokens: 8,
    }),
    signal,
  });
  const body = await response.text();
  return { ok: response.ok && /WORKFRAME_OK/i.test(body), detail: response.ok ? 'OpenAI responded.' : `OpenAI HTTP ${response.status}.` };
}

async function testOpenRouter(signal) {
  const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      authorization: `Bearer ${process.env.OPENROUTER_API_KEY}`,
      'content-type': 'application/json',
      'x-title': 'Workframe local link test',
    },
    body: JSON.stringify({
      model: 'openai/gpt-4o-mini',
      messages: [{ role: 'user', content: 'Reply with exactly WORKFRAME_OK and nothing else.' }],
      max_tokens: 8,
      temperature: 0,
    }),
    signal,
  });
  const body = await response.text();
  return { ok: response.ok && /WORKFRAME_OK/i.test(body), detail: response.ok ? 'OpenRouter responded.' : `OpenRouter HTTP ${response.status}.` };
}

export async function runVerification(candidate, { signal } = {}) {
  if (candidate.id === 'codex-runtime') {
    const result = await spawnCancellable('codex', [
      'exec', '--skip-git-repo-check', '--sandbox', 'read-only', '--color', 'never',
      'Reply with exactly WORKFRAME_OK and nothing else. Do not inspect files or run tools.',
    ], { signal, timeoutMs: TEST_TIMEOUT_MS });
    const text = `${result.stdout}\n${result.stderr}`;
    return {
      ok: result.ok && /WORKFRAME_OK/i.test(text),
      cancelled: result.cancelled,
      detail: result.cancelled ? 'Cancelled.' : result.ok ? 'Codex responded.' : firstLine(result.stderr || result.error || 'Codex failed.'),
    };
  }

  if (candidate.id === 'claude-runtime') {
    const result = await spawnCancellable('claude', [
      '-p', '--permission-mode', 'plan', '--max-turns', '1', '--max-budget-usd', '0.02',
      '--no-session-persistence', 'Reply with exactly WORKFRAME_OK and nothing else.',
    ], { signal, timeoutMs: TEST_TIMEOUT_MS });
    const text = `${result.stdout}\n${result.stderr}`;
    return {
      ok: result.ok && /WORKFRAME_OK/i.test(text),
      cancelled: result.cancelled,
      detail: result.cancelled ? 'Cancelled.' : result.ok ? 'Claude responded.' : firstLine(result.stderr || result.error || 'Claude failed.'),
    };
  }

  if (candidate.id === 'openai-api') return testOpenAI(signal);
  if (candidate.id === 'openrouter-api') return testOpenRouter(signal);

  return { ok: false, cancelled: false, detail: 'No verification adapter for candidate.' };
}

// Legacy status flow — opportunistic pick retained for status-only UX until WF-CLI-003 dialogue replaces it.
export function chooseTestCandidate(report) {
  const runtime = Object.fromEntries(report.runtimes.map((item) => [item.id, item]));
  const provider = Object.fromEntries(report.providers.map((item) => [item.id, item]));
  if (runtime.codex?.status === 'authenticated') {
    return { id: 'codex', label: 'Codex CLI', billing: 'your existing Codex / ChatGPT account or configured provider' };
  }
  if (runtime.claude?.status === 'verified') {
    return { id: 'claude', label: 'Claude Code', billing: 'your existing Claude account or Anthropic provider' };
  }
  if (provider.openrouter?.status === 'configured') {
    return { id: 'openrouter', label: 'OpenRouter', billing: 'the OpenRouter key already present in your environment' };
  }
  if (provider.openai?.status === 'configured') {
    return { id: 'openai', label: 'OpenAI', billing: 'the OpenAI key already present in your environment' };
  }
  return null;
}

export async function runLegacyTest(candidate) {
  if (candidate.id === 'codex') {
    const result = run('codex', [
      'exec', '--skip-git-repo-check', '--sandbox', 'read-only', '--color', 'never',
      'Reply with exactly WORKFRAME_OK and nothing else. Do not inspect files or run tools.',
    ], { timeout: TEST_TIMEOUT_MS, cwd: os.tmpdir() });
    return { ok: result.ok && /WORKFRAME_OK/i.test(`${result.stdout}\n${result.stderr}`), detail: result.ok ? 'Codex responded.' : firstLine(result.stderr || result.error || 'Codex test failed.') };
  }
  if (candidate.id === 'claude') {
    const result = run('claude', [
      '-p', '--permission-mode', 'plan', '--max-turns', '1', '--max-budget-usd', '0.02',
      '--no-session-persistence', 'Reply with exactly WORKFRAME_OK and nothing else.',
    ], { timeout: TEST_TIMEOUT_MS, cwd: os.tmpdir() });
    return { ok: result.ok && /WORKFRAME_OK/i.test(`${result.stdout}\n${result.stderr}`), detail: result.ok ? 'Claude responded.' : firstLine(result.stderr || result.error || 'Claude test failed.') };
  }
  if (candidate.id === 'openrouter') return testOpenRouter();
  if (candidate.id === 'openai') return testOpenAI();
  return { ok: false, detail: 'No test adapter is available.' };
}
