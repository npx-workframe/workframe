import { fieldProvenance, sanitizeBoundedText } from './text.js';

export const BEGIN_QUESTIONS = [
  {
    key: 'human',
    prompt: 'What should I call you here — name, role, or both?',
    architect: 'You invoked the entry path. I do not know who you are in this system yet.',
  },
  {
    key: 'entity',
    prompt: 'What entity, project, or organization are you defining?',
    architect: 'Every durable system needs a named carrier. What is yours?',
  },
  {
    key: 'purpose',
    prompt: 'What are you trying to bring into existence or change?',
    architect: 'State the change. Not the tool. The outcome.',
  },
  {
    key: 'why',
    prompt: 'Why does that matter?',
    architect: 'Purpose without reason becomes fashion. Why does this matter?',
  },
  {
    key: 'success',
    prompt: 'What would success look like?',
    architect: 'Define success so we can recognize arrival.',
  },
  {
    key: 'constraints',
    prompt: 'Which constraints or non-negotiables already exist?',
    architect: 'What must never happen? What is already fixed?',
  },
  {
    key: 'execution_surface',
    prompt: 'Do you need a shared Workframe cell with Hermes, or Architectonic files only?',
    architect: 'Execution has cost. Say whether you need a live cell or only structured knowledge.',
  },
];

export function buildFirstMirror(session, { stopped = false, stop_reason = null } = {}) {
  const unresolved = [];
  for (const question of BEGIN_QUESTIONS) {
    const value = sanitizeBoundedText(session[question.key]);
    if (!value) unresolved.push(question.key);
  }

  const fields = {
    human: { value: sanitizeBoundedText(session.human) || null, provenance: fieldProvenance(session.human) },
    entity: { value: sanitizeBoundedText(session.entity) || null, provenance: fieldProvenance(session.entity) },
    stated_purpose: { value: sanitizeBoundedText(session.purpose) || null, provenance: fieldProvenance(session.purpose) },
    why: { value: sanitizeBoundedText(session.why) || null, provenance: fieldProvenance(session.why) },
    goals: { value: sanitizeBoundedText(session.purpose) || null, provenance: fieldProvenance(session.purpose) },
    success_criteria: { value: sanitizeBoundedText(session.success) || null, provenance: fieldProvenance(session.success) },
    constraints: { value: sanitizeBoundedText(session.constraints) || null, provenance: fieldProvenance(session.constraints) },
    execution_surface: { value: sanitizeBoundedText(session.execution_surface) || null, provenance: fieldProvenance(session.execution_surface) },
  };

  return {
    schema_version: '0.1',
    mode: 'memory_only_mirror',
    stopped,
    stop_reason,
    fields,
    unresolved_questions: unresolved,
    mutations: [],
    network_calls: 0,
    credential_reads: 0,
  };
}

export function buildConstitutionalDraft(mirror) {
  const f = mirror.fields;
  return {
    schema_version: '0.1',
    mode: 'constitutional_draft',
    authority_root: { value: f.human.value, provenance: f.human.provenance },
    entity: { value: f.entity.value, provenance: f.entity.provenance },
    purpose: { value: f.stated_purpose.value, provenance: f.stated_purpose.provenance },
    why: { value: f.why.value, provenance: f.why.provenance },
    goals: { value: f.goals.value, provenance: f.goals.provenance },
    constraints: { value: f.constraints.value, provenance: f.constraints.provenance },
    success_criteria: { value: f.success_criteria.value, provenance: f.success_criteria.provenance },
    execution_surface: { value: f.execution_surface.value, provenance: f.execution_surface.provenance },
    unresolved_questions: mirror.unresolved_questions,
    provenance_rule: 'stated | inferred | confirmed | unresolved',
    mutations: [],
  };
}
