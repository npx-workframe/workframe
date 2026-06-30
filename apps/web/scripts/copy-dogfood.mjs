#!/usr/bin/env node
/**
 * Copy built workframe-ui dist to a generated project for dogfood testing.
 * Usage: node scripts/copy-dogfood.mjs [targetDir]
 * Default target: ../../../AIfred/workframe-ui/public (sibling under D:\\Workframe)
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PKG_ROOT = path.resolve(__dirname, '..')
const DIST = path.join(PKG_ROOT, 'dist')
const DEFAULT_TARGET = path.resolve(PKG_ROOT, '../../../AIfred/workframe-ui/public')

const target = path.resolve(process.argv[2] || DEFAULT_TARGET)

if (!fs.existsSync(DIST)) {
  console.error('Missing dist/. Run npm run build first.')
  process.exit(1)
}

fs.mkdirSync(target, { recursive: true })

for (const entry of fs.readdirSync(DIST, { withFileTypes: true })) {
  const src = path.join(DIST, entry.name)
  const dest = path.join(target, entry.name)
  if (entry.isDirectory()) {
    fs.rmSync(dest, { recursive: true, force: true })
    fs.cpSync(src, dest, { recursive: true })
  } else {
    fs.copyFileSync(src, dest)
  }
}

console.log(`Copied ${DIST} → ${target}`)
