import { normalizeAnswer } from './text.js';

const AFFIRMATIVE_PATTERNS = [
  /\buse codex\b/,
  /\bchoose codex\b/,
  /\bpick codex\b/,
  /\bgo with codex\b/,
  /\buse claude\b/,
  /\bchoose claude\b/,
  /\bpick claude\b/,
  /\buse openrouter\b/,
  /\bchoose openrouter\b/,
  /\buse openai\b/,
  /\bchoose openai\b/,
  /\buse anthropic\b/,
  /\bchoose anthropic\b/,
];

const NEGATIVE_CONTEXT = [
  /\bdon t\b/,
  /\bdo not\b/,
  /\bnot\b/,
  /\bnever\b/,
  /\bavoid\b/,
  /\bwithout\b/,
  /\bdistrust\b/,
  /\bdon t trust\b/,
  /\bi don t know\b/,
  /\bsounds risky\b/,
  /\bis installed\b/,
  /\bis risky\b/,
];

const DESCRIPTIVE_ONLY = [
  /\bi don t know anything about\b/,
  /\bi don t trust\b/,
  /\bclaude is installed\b/,
  /\bclaude sounds risky\b/,
];

export function resolveCandidateSelection(text, candidates) {
  const normalized = normalizeAnswer(text);
  if (!normalized) return { status: 'unresolved', reason: 'empty' };

  if (DESCRIPTIVE_ONLY.some((pattern) => pattern.test(normalized))) {
    return { status: 'unresolved', reason: 'descriptive_or_negative_context' };
  }

  const exclusions = new Set();
  if (/\bnot claude\b|\bdon t use claude\b|\bwithout claude\b/.test(normalized)) exclusions.add('claude-runtime');
  if (/\bnot codex\b|\bdon t use codex\b|\bwithout codex\b/.test(normalized)) exclusions.add('codex-runtime');
  if (/\bnot openrouter\b|\bdon t use openrouter\b/.test(normalized)) exclusions.add('openrouter-api');
  if (/\bnot openai\b|\bdon t use openai\b/.test(normalized)) exclusions.add('openai-api');

  const affirmativeHits = candidates.filter((candidate) => {
    if (exclusions.has(candidate.id)) return false;
    const token = candidate.id.replace('-api', '').replace('-runtime', '');
    const usePattern = new RegExp(`\\b(use|choose|pick|go with)\\s+${token}\\b`);
    return usePattern.test(normalized) || AFFIRMATIVE_PATTERNS.some((pattern) => pattern.test(normalized) && pattern.source.includes(token));
  });

  if (affirmativeHits.length === 1) return { status: 'selected', candidate: affirmativeHits[0] };
  if (affirmativeHits.length > 1) return { status: 'unresolved', reason: 'ambiguous' };

  if (NEGATIVE_CONTEXT.some((pattern) => pattern.test(normalized)) && !AFFIRMATIVE_PATTERNS.some((pattern) => pattern.test(normalized))) {
    return { status: 'unresolved', reason: 'negative_without_affirmative' };
  }

  return { status: 'unresolved', reason: 'no_affirmative_selection' };
}
