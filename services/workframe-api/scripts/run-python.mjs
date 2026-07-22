import { spawnSync } from 'node:child_process'

const requestedArgs = process.argv.slice(2)
const candidates = process.platform === 'win32'
  ? [
      { command: 'python', prefix: [] },
      { command: 'py', prefix: ['-3'] },
      { command: 'python3', prefix: [] },
    ]
  : [
      { command: 'python3', prefix: [] },
      { command: 'python', prefix: [] },
    ]

for (const candidate of candidates) {
  const result = spawnSync(candidate.command, [...candidate.prefix, ...requestedArgs], {
    stdio: 'inherit',
  })
  if (result.error?.code === 'ENOENT') continue
  if (result.error) {
    console.error(`Could not run ${candidate.command}: ${result.error.message}`)
    process.exit(1)
  }
  process.exit(result.status ?? 1)
}

console.error('Python 3 was not found. Install Python 3 and ensure py, python, or python3 is available.')
process.exit(1)
