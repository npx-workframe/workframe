export const MAX_ANSWER_LENGTH = 2000;

export function sanitizeBoundedText(value, maxLen = MAX_ANSWER_LENGTH) {
  return String(value ?? '')
    .replace(/[\0-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '')
    .trim()
    .slice(0, maxLen);
}

export function normalizeAnswer(value) {
  return sanitizeBoundedText(value)
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9' ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function interpretConsent(value) {
  const answer = normalizeAnswer(value);
  if (!answer) return 'unknown';

  const noPatterns = [
    /\bno\b/, /\bnope\b/, /\bnah\b/, /\bnegative\b/, /\bnot now\b/,
    /\bdon t\b/, /\bdo not\b/, /\bstop\b/, /\bskip\b/, /\blater\b/,
    /\bnot yet\b/, /\bi d rather not\b/, /\bi would rather not\b/,
  ];
  const yesPatterns = [
    /\byes\b/, /\byep\b/, /\byeah\b/, /\byup\b/, /\baffirmative\b/,
    /\bsure\b/, /\bok\b/, /\bokay\b/, /\bgo ahead\b/, /\bdo it\b/,
    /\bproceed\b/, /\bplease\b/, /\btest it\b/, /\bsounds good\b/,
    /\blet s do it\b/, /\blets do it\b/, /\bwhy not\b/,
  ];

  if (noPatterns.some((pattern) => pattern.test(answer))) return 'no';
  if (yesPatterns.some((pattern) => pattern.test(answer))) return 'yes';
  return 'unknown';
}

export function fieldProvenance(value) {
  return sanitizeBoundedText(value) ? 'stated' : 'unresolved';
}
