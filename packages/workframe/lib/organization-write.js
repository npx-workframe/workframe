import fs from 'node:fs';
import path from 'node:path';

function today() {
  return new Date().toISOString().slice(0, 10);
}

function upsertSection(markdown, heading, bodyLines) {
  const section = `${heading}\n\n${bodyLines.join('\n')}\n`;
  if (markdown.includes(heading)) {
    const parts = markdown.split(heading);
    const after = parts[1] ?? '';
    const nextHeading = after.search(/^## /m);
    const tail = nextHeading >= 0 ? after.slice(nextHeading) : '';
    return `${parts[0]}${section}${tail}`.trimEnd() + '\n';
  }
  return `${markdown.trimEnd()}\n\n${section}`;
}

export function writeOrganizationFromDraft(workspaceRoot, draft) {
  const orgDir = path.join(workspaceRoot, 'organization');
  if (!fs.existsSync(orgDir)) throw new Error(`Missing organization directory: ${orgDir}`);

  const projectFallback = `---\ntype: project\nstatus: stated\nsource_status: workframe-cli\n---\n\n# Project Index\n\n| Project | Purpose | Owner | Canonical sources | Status | Decisions | Open questions |\n| --- | --- | --- | --- | --- | --- | --- |\n`;
  const identityFallback = `---\ntype: identity\nstatus: stated\n---\n\n# Actors and Authority\n\n## Humans and organizations\n\n| Actor | Role | Can decide | Can approve | Can delegate | Can stop | Privacy boundary |\n| --- | --- | --- | --- | --- | --- | --- |\n`;

  const projectPath = path.join(orgDir, 'project.md');
  const identityPath = path.join(orgDir, 'identity.md');
  if (!fs.existsSync(projectPath)) fs.writeFileSync(projectPath, projectFallback);
  if (!fs.existsSync(identityPath)) fs.writeFileSync(identityPath, identityFallback);

  const human = draft.authority_root?.value || draft.entity?.value || 'unresolved';
  const purpose = draft.purpose?.value || 'unresolved';
  const why = draft.why?.value || '';
  const success = draft.success_criteria?.value || '';
  const constraints = draft.constraints?.value || '';
  const entity = draft.entity?.value || 'unresolved';
  const surface = draft.execution_surface?.value || '';

  let projectMd = fs.readFileSync(projectPath, 'utf8');
  projectMd = upsertSection(projectMd, '## Active project (Workframe CLI)', [
    `| ${entity} | ${purpose} | ${human} | workframe begin | active | see decisions.md | see open-questions.md |`,
    '',
    '### Why it matters',
    why || '- unresolved',
    '',
    '### Success criteria',
    success || '- unresolved',
    '',
    '### Constraints',
    constraints || '- unresolved',
    '',
    '### Execution surface',
    surface || '- unresolved',
  ]);
  fs.writeFileSync(projectPath, projectMd);

  let identityMd = fs.readFileSync(identityPath, 'utf8');
  identityMd = upsertSection(identityMd, '## Humans and organizations (Workframe CLI)', [
    `| ${human} | authority root | yes | yes | yes | yes | collaboration facts only |`,
  ]);
  fs.writeFileSync(identityPath, identityMd);

  const openPath = path.join(orgDir, 'open-questions.md');
  const openRows = (draft.unresolved_questions || []).map((key) =>
    `| ${key} | blocks downstream certainty | begin mirror | ${human} | next session | open |`,
  );
  if (openRows.length) {
    let openMd = fs.readFileSync(openPath, 'utf8');
    openMd = `${openMd.trimEnd()}\n${openRows.join('\n')}\n`;
    fs.writeFileSync(openPath, openMd);
  }

  const decisionsPath = path.join(orgDir, 'decisions.md');
  const decisionRow = `| ${today()} | Instantiate Architectonic workspace for ${entity} | ${human} | workframe apply | ${entity} scope | none recorded | when purpose changes |`;
  let decisionsMd = fs.readFileSync(decisionsPath, 'utf8');
  decisionsMd = `${decisionsMd.trimEnd()}\n${decisionRow}\n`;
  fs.writeFileSync(decisionsPath, decisionsMd);

  return {
    written: [projectPath, identityPath, openPath, decisionsPath],
  };
}

export function linkOrganizationToWorkframeFiles(cellRoot, workspaceRoot) {
  const filesRoot = path.join(cellRoot, 'Files');
  const target = path.join(filesRoot, 'organization');
  const source = path.join(workspaceRoot, 'organization');
  if (!fs.existsSync(source)) throw new Error(`Missing source organization: ${source}`);
  fs.mkdirSync(filesRoot, { recursive: true });
  fs.cpSync(source, target, { recursive: true, force: true });
  const pointer = path.join(filesRoot, 'WORKFRAME-KB.md');
  fs.writeFileSync(pointer, `# Knowledge base pointer

Canonical Architectonic organization files are mirrored under \`Files/organization/\`.
Upstream workspace: ${workspaceRoot}

Truth order in Workframe: Files > Kanban > Chat.
`, 'utf8');
  return { linked: target, pointer };
}
