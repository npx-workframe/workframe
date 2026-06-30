import { copyFileSync, existsSync, readFileSync, rmSync } from 'node:fs'
import { execSync } from 'node:child_process'
import { build } from 'esbuild'

if (existsSync('dist/preload.js')) rmSync('dist/preload.js')
if (existsSync('dist/assets')) rmSync('dist/assets', { recursive: true })

execSync('tsc -p tsconfig.json', { stdio: 'inherit' })

await build({
  entryPoints: ['src/preload.ts'],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  outfile: 'dist/preload.cjs',
  external: ['electron'],
})

copyFileSync('loading.html', 'dist/loading.html')

// ponytail: fail build if preload regresses to ESM syntax
const preload = readFileSync('dist/preload.cjs', 'utf8')
if (/^\s*import\s/m.test(preload)) {
  throw new Error('preload.cjs must be CommonJS (found ESM import)')
}
