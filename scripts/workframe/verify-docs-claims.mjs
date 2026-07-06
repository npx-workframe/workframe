#!/usr/bin/env node
/**
 * WF-006: public docs must not claim beyond release-scope.json proven set.
 * ponytail: line-local qualifier check — same line or previous non-blank line.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const scopePath = path.join(root, 'operations/release-scope.json');

function fail(msg) {
  console.error(`verify-docs-claims: ${msg}`);
  process.exit(1);
}

function loadScope() {
  if (!fs.existsSync(scopePath)) fail(`missing ${scopePath}`);
  return JSON.parse(fs.readFileSync(scopePath, 'utf8'));
}

function listMarkdownFiles(relRoot) {
  const abs = path.join(root, relRoot);
  if (!fs.existsSync(abs)) return [];
  if (relRoot.endsWith('.md')) return [relRoot];
  const out = [];
  for (const ent of fs.readdirSync(abs, { withFileTypes: true })) {
    const rel = path.join(relRoot, ent.name).replace(/\\/g, '/');
    if (ent.isDirectory()) out.push(...listMarkdownFiles(rel));
    else if (ent.name.endsWith('.md')) out.push(rel);
  }
  return out;
}

function lineHasQualifier(line, qualifiers) {
  return qualifiers.some((q) => q.test(line));
}

function collectHits(file, text, rules, qualifiers) {
  const lines = text.split('\n');
  const hits = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    let prev = '';
    for (let j = i - 1; j >= 0; j--) {
      if (lines[j].trim()) {
        prev = lines[j];
        break;
      }
    }
    const context = `${prev}\n${line}`;
    if (lineHasQualifier(line, qualifiers) || lineHasQualifier(prev, qualifiers)) continue;
    for (const rule of rules) {
      if (rule.pattern.test(line) || rule.pattern.test(context)) {
        hits.push({ file, line: i + 1, rule: rule.id, message: rule.message, text: line.trim() });
        break;
      }
    }
  }
  return hits;
}

const scope = loadScope();
const qualifiers = (scope.qualifier_patterns || []).map((p) => new RegExp(p, 'i'));
const rules = (scope.claim_rules || []).map((r) => ({
  ...r,
  pattern: new RegExp(r.pattern, 'i'),
}));

const files = (scope.scan_roots || []).flatMap((rel) => listMarkdownFiles(rel));
if (!files.length) fail('no markdown files to scan');

const allHits = [];
for (const rel of files) {
  const text = fs.readFileSync(path.join(root, rel), 'utf8');
  allHits.push(...collectHits(rel, text, rules, qualifiers));
}

if (allHits.length) {
  console.error('verify-docs-claims: DENY — unsupported public claims:');
  for (const h of allHits.slice(0, 30)) {
    console.error(`  ${h.file}:${h.line} [${h.rule}] ${h.message}`);
    console.error(`    ${h.text}`);
  }
  if (allHits.length > 30) console.error(`  … and ${allHits.length - 30} more`);
  process.exit(1);
}

console.log(`verify-docs-claims: ALLOW — ${files.length} file(s), ${rules.length} rule(s)`);
