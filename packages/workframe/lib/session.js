const MAX_ANSWER_LENGTH = 2_000;

export function cleanFreeText(value, maxLength = MAX_ANSWER_LENGTH) {
  return String(value || '')
    .replace(/[\0\u0001-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, maxLength);
}

export function parsePreferredName(value) {
  const answer = cleanFreeText(value, 120);
  if (!answer) return 'human';

  const match = answer.match(/^(?:please\s+)?(?:call me|my name is|i am|i'm)\s+(.+)$/i);
  const candidate = cleanFreeText(match ? match[1] : answer, 80)
    .replace(/[.!?]+$/g, '')
    .trim();
  return candidate || 'human';
}

export function createSessionSeed({ preferredName, objective, candidate }) {
  return {
    status: 'draft',
    persistence: 'memory-only',
    human: {
      preferredName: parsePreferredName(preferredName),
    },
    entity: {
      statedObjective: cleanFreeText(objective),
      unresolved: ['purpose', 'constraints', 'success criteria'],
    },
    inference: {
      id: candidate.id,
      label: candidate.label,
      status: 'verified',
      billingSource: candidate.billingSource,
      credentialSource: candidate.credentialSource,
    },
  };
}
