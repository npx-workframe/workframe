const NEGATIVE_CONSENT_PATTERNS = [
  /\bno\b/,
  /\bnope\b/,
  /\bnah\b/,
  /\bnegative\b/,
  /\bnot now\b/,
  /\bdon't\b/,
  /\bdo not\b/,
  /\bstop\b/,
  /\bskip\b/,
  /\blater\b/,
  /\bnot yet\b/,
  /\bi'd rather not\b/,
  /\bi would rather not\b/,
];

const POSITIVE_CONSENT_PATTERNS = [
  /\byes\b/,
  /\byep\b/,
  /\byeah\b/,
  /\byup\b/,
  /\baffirmative\b/,
  /\bsure\b/,
  /\bok\b/,
  /\bokay\b/,
  /\bgo ahead\b/,
  /\bdo it\b/,
  /\bproceed\b/,
  /\bplease\b/,
  /\btest it\b/,
  /\bsounds good\b/,
  /\blet's do it\b/,
  /\blets do it\b/,
  /\bwhy not\b/,
];

const EXCLUSION_MARKERS = [
  'except',
  'not',
  "don't use",
  'do not use',
  'anything but',
  'anything except',
];

export function normalizeAnswer(value) {
  return String(value || '')
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
  if (NEGATIVE_CONSENT_PATTERNS.some((pattern) => pattern.test(answer))) return 'no';
  if (POSITIVE_CONSENT_PATTERNS.some((pattern) => pattern.test(answer))) return 'yes';
  return 'unknown';
}

function candidateTerms(candidate) {
  return [candidate.id, candidate.label, ...(candidate.aliases || [])]
    .map(normalizeAnswer)
    .filter(Boolean);
}

function mentionsTerm(answer, term) {
  if (!term) return false;
  return new RegExp(`(?:^|\\s)${escapeRegExp(term)}(?:$|\\s)`).test(answer);
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function isExcluded(answer, term) {
  return EXCLUSION_MARKERS.some((marker) => {
    const normalizedMarker = normalizeAnswer(marker);
    const markerIndex = answer.indexOf(normalizedMarker);
    const termIndex = answer.indexOf(term);
    return markerIndex >= 0 && termIndex > markerIndex && termIndex - markerIndex < 40;
  });
}

export function interpretCandidateChoice(value, candidates) {
  const answer = normalizeAnswer(value);
  if (!answer || candidates.length === 0) return { kind: 'unknown' };

  const explicit = [];
  const excluded = new Set();

  for (const candidate of candidates) {
    const terms = candidateTerms(candidate);
    if (!terms.some((term) => mentionsTerm(answer, term))) continue;
    if (terms.some((term) => isExcluded(answer, term))) {
      excluded.add(candidate.id);
    } else {
      explicit.push(candidate);
    }
  }

  if (explicit.length === 1) return { kind: 'selected', candidate: explicit[0] };
  if (explicit.length > 1) return { kind: 'ambiguous', candidates: explicit };

  const remaining = candidates.filter((candidate) => !excluded.has(candidate.id));
  if (excluded.size > 0 && remaining.length === 1) {
    return { kind: 'selected', candidate: remaining[0] };
  }

  if (/\b(first|default|recommended|best)\b/.test(answer)) {
    return { kind: 'selected', candidate: remaining[0] || candidates[0] };
  }

  if (/\b(any|anything|whichever|you choose|your choice)\b/.test(answer) && remaining.length > 0) {
    return { kind: 'selected', candidate: remaining[0] };
  }

  return { kind: 'unknown' };
}
