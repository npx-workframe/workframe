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

const EXPLICIT_AFFIRMATIVE_ANSWERS = new Set([
  'yes',
  'yes please',
  'yes do it',
  'yes test it',
  'yep',
  'yeah',
  'yup',
  'affirmative',
  'approved',
  'i approve',
  'i consent',
  'sure',
  'ok',
  'okay',
  'go ahead',
  'do it',
  'proceed',
  'test it',
  'sounds good',
  'sounds good proceed',
  'lets do it',
]);

const AMBIGUITY_PATTERNS = [
  /\b(if|unless|maybe|perhaps|possibly|probably|depending)\b/,
  /\b(but|however|although|though)\b/,
  /\b(what|why|how|when|where|which|who)\b/,
  /\b(explain|clarify|tell me|show me|before|first)\b/,
  /\b(can you|could you|would you)\b/,
];

const HEDGED_SELECTION_PATTERNS = [
  /\bmaybe\b/,
  /\bperhaps\b/,
  /\bpossibly\b/,
  /\bprobably\b/,
  /\bi guess\b/,
  /\bi think\b/,
  /\bnot sure\b/,
  /\bunsure\b/,
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
  const raw = String(value || '').trim();
  const answer = normalizeAnswer(raw);
  if (!answer) return 'unknown';
  if (NEGATIVE_CONSENT_PATTERNS.some((pattern) => pattern.test(answer))) return 'no';
  if (raw.includes('?')) return 'unknown';
  if (AMBIGUITY_PATTERNS.some((pattern) => pattern.test(answer))) return 'unknown';
  return EXPLICIT_AFFIRMATIVE_ANSWERS.has(answer) ? 'yes' : 'unknown';
}

function candidateTerms(candidate) {
  return [candidate.id, candidate.label, ...(candidate.aliases || [])]
    .map(normalizeAnswer)
    .filter(Boolean);
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function mentionsTerm(answer, term) {
  if (!term) return false;
  return new RegExp(`(?:^|\\s)${escapeRegExp(term)}(?:$|\\s)`).test(answer);
}

function isExcluded(answer, term) {
  return EXCLUSION_MARKERS.some((marker) => {
    const normalizedMarker = normalizeAnswer(marker);
    const markerIndex = answer.indexOf(normalizedMarker);
    const termIndex = answer.indexOf(term);
    return markerIndex >= 0 && termIndex > markerIndex && termIndex - markerIndex < 40;
  });
}

function isQuestion(value, answer) {
  const raw = String(value || '').trim();
  return raw.includes('?')
    || /^(what|which|who|why|how|when|where|can|could|would|should|is|are|do|does)\b/.test(answer);
}

function delegatesSelection(answer) {
  return /\b(use|choose|pick|select|take|go with)\s+(?:the\s+)?(?:first|default|recommended|best|whichever|anything|any one|your choice)\b/.test(answer)
    || /\byou\s+(?:choose|pick|select|decide)\b/.test(answer);
}

export function interpretCandidateChoice(value, candidates) {
  const answer = normalizeAnswer(value);
  if (!answer || candidates.length === 0) return { kind: 'unknown' };
  if (isQuestion(value, answer)) return { kind: 'unknown' };
  if (HEDGED_SELECTION_PATTERNS.some((pattern) => pattern.test(answer))) return { kind: 'unknown' };

  const explicit = [];
  const excluded = new Set();

  for (const candidate of candidates) {
    const terms = candidateTerms(candidate);
    const matchedTerms = terms.filter((term) => mentionsTerm(answer, term));
    if (matchedTerms.length === 0) continue;
    if (matchedTerms.some((term) => isExcluded(answer, term))) {
      excluded.add(candidate.id);
    } else {
      explicit.push({
        candidate,
        specificity: Math.max(...matchedTerms.map((term) => term.length)),
      });
    }
  }

  if (explicit.length > 0) {
    const families = new Set(explicit.map(({ candidate }) => {
      const normalizedId = normalizeAnswer(candidate.family || candidate.id);
      return normalizedId.split(' ')[0];
    }));
    if (families.size > 1) {
      return { kind: 'ambiguous', candidates: explicit.map((match) => match.candidate) };
    }
    const highestSpecificity = Math.max(...explicit.map((match) => match.specificity));
    const strongest = explicit.filter((match) => match.specificity === highestSpecificity);
    if (strongest.length === 1) return { kind: 'selected', candidate: strongest[0].candidate };
    return { kind: 'ambiguous', candidates: strongest.map((match) => match.candidate) };
  }

  const remaining = candidates.filter((candidate) => !excluded.has(candidate.id));
  if (excluded.size > 0 && remaining.length === 1) {
    return { kind: 'selected', candidate: remaining[0] };
  }

  if (delegatesSelection(answer) && remaining.length > 0) {
    return { kind: 'selected', candidate: remaining[0] };
  }

  return { kind: 'unknown' };
}
