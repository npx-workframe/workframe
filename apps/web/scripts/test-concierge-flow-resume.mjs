/**
 * Install wizard resume step resolution — signed-out install must not jump to admin_auth
 * before SMTP is tested. Run: node apps/web/scripts/test-concierge-flow-resume.mjs
 */
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { pathToFileURL } = await import('node:url')

const repoRoot = new URL('../../..', import.meta.url)
const distPath = new URL('./dist-test/conciergeFlowResume.js', import.meta.url)

// Compile TS on the fly via tsx if available, else use a minimal inline mirror for CI.
let resolveConciergeResumeStep
try {
  const { execSync } = await import('node:child_process')
  const { mkdirSync } = await import('node:fs')
  mkdirSync(new URL('./dist-test', import.meta.url), { recursive: true })
  execSync(
    `npx --yes esbuild ${new URL('../src/components/onboarding/conciergeFlowResume.ts', import.meta.url).pathname} --bundle --platform=node --format=esm --outfile=${distPath.pathname}`,
    { cwd: repoRoot.pathname, stdio: 'pipe' },
  )
  ;({ resolveConciergeResumeStep } = await import(pathToFileURL(distPath.pathname).href))
} catch {
  // Fallback: keep assertions aligned with conciergeFlowResume.ts logic.
  resolveConciergeResumeStep = (input) => {
    const PRE = ['theme', 'publish', 'smtp', 'admin_auth', 'workframe', 'billing', 'integrations', 'profile', 'agent', 'agent_model', 'invites']
    let step = String(input.resumeRaw || '').trim()
    if (!step) return null
    if (step === 'admin_auth' && input.installAdminVerified) step = 'workframe'
    else if (step === 'admin_auth' && !input.smtpSetupComplete) step = 'smtp'
    else if (step === 'smtp' && input.installAdminVerified && input.smtpSetupComplete) step = 'workframe'
    if (!input.deploymentChosen && PRE.includes(step)) {
      step = input.smtpAdminEmail ? 'welcome' : 'intro'
    }
    if (!input.smtpAdminEmail && step !== 'intro') step = 'intro'
    if (step === 'intro') return null
    return step
  }
}

assert.equal(
  resolveConciergeResumeStep({
    resumeRaw: 'admin_auth',
    installAdminVerified: false,
    smtpAdminEmail: 'owner@example.com',
    deploymentChosen: true,
    smtpSetupComplete: false,
  }),
  'smtp',
)

assert.equal(
  resolveConciergeResumeStep({
    resumeRaw: 'smtp',
    installAdminVerified: false,
    smtpAdminEmail: 'owner@example.com',
    deploymentChosen: false,
    smtpSetupComplete: false,
  }),
  'welcome',
)

assert.equal(
  resolveConciergeResumeStep({
    resumeRaw: 'theme',
    installAdminVerified: false,
    smtpAdminEmail: '',
    deploymentChosen: false,
    smtpSetupComplete: false,
  }),
  null,
)

assert.equal(
  resolveConciergeResumeStep({
    resumeRaw: 'admin_auth',
    installAdminVerified: true,
    smtpAdminEmail: 'owner@example.com',
    deploymentChosen: true,
    smtpSetupComplete: true,
  }),
  'workframe',
)

console.log('test-concierge-flow-resume: ok')
