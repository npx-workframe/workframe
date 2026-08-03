#!/usr/bin/env node
/** Validate the canonical Workframe ledger contract and print the active rail item. */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ledgerPath = path.join(root, 'docs/ledger/ledger.json')
const ledger = JSON.parse(fs.readFileSync(ledgerPath, 'utf8'))
const statuses = new Set(['backlog', 'ready', 'in_progress', 'review', 'blocked', 'approval_required', 'done', 'deferred', 'cancelled'])
const priorities = new Set(['P0', 'P1', 'P2', 'P3'])
const errors = []
const ids = new Set()

if (ledger.schema_version !== '1.0') errors.push('schema_version must be 1.0')
if (typeof ledger.project !== 'string' || !ledger.project.trim()) errors.push('project is required')
if (typeof ledger.updated !== 'string' || !ledger.updated.trim()) errors.push('updated is required')
if (!Array.isArray(ledger.items)) errors.push('items must be an array')

for (const [index, item] of (ledger.items || []).entries()) {
  const at = `items[${index}]`
  for (const key of ['id', 'title', 'status', 'priority', 'owner_role']) {
    if (typeof item?.[key] !== 'string' || !item[key].trim()) errors.push(`${at}.${key} is required`)
  }
  for (const key of ['acceptance', 'depends_on', 'evidence']) {
    if (!Array.isArray(item?.[key])) errors.push(`${at}.${key} must be an array`)
  }
  if (!Array.isArray(item?.acceptance) || item.acceptance.length === 0) errors.push(`${at}.acceptance must not be empty`)
  if (!statuses.has(item?.status)) errors.push(`${at}.status is not a rail status: ${item?.status}`)
  if (!priorities.has(item?.priority)) errors.push(`${at}.priority is invalid: ${item?.priority}`)
  if (ids.has(item?.id)) errors.push(`duplicate item id: ${item.id}`)
  ids.add(item?.id)
  if (item?.status === 'in_progress' && (!item.claim?.assignee || !item.claim?.claimed_at)) {
    errors.push(`${item.id} is in_progress without claim.assignee and claim.claimed_at`)
  }
  if (item?.status === 'done' && !item.evidence?.length) errors.push(`${item.id} is done without evidence`)
  if (item?.status === 'approval_required' && !item.stop_line) errors.push(`${item.id} requires approval without a stop_line`)
}

for (const item of ledger.items || []) {
  for (const dependency of item.depends_on || []) {
    const dep = ledger.items.find((candidate) => candidate.id === dependency)
    if (!dep) errors.push(`${item.id} depends on missing item ${dependency}`)
    if (item.status === 'ready' && dep?.status !== 'done') errors.push(`${item.id} is ready with unmet dependency ${dependency}`)
  }
}

if (errors.length) {
  console.error(errors.map((error) => `[ledger] ${error}`).join('\n'))
  process.exit(1)
}

const active = ledger.items.filter((item) => item.status === 'in_progress')
const next = ledger.items
  .filter((item) => item.status === 'ready')
  .filter((item) => (item.depends_on || []).every((dependency) => ledger.items.find((candidate) => candidate.id === dependency)?.status === 'done'))
  .sort((a, b) => a.priority.localeCompare(b.priority) || a.id.localeCompare(b.id))[0] || null

console.log(JSON.stringify({ ok: true, active: active.map((item) => item.id), next: next?.id || null }, null, 2))
