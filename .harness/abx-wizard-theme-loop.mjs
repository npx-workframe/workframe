/**
 * ABX install wizard + 14-theme visual loop.
 * Run: node .harness/abx-wizard-theme-loop.mjs
 */
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { chromium } = require('C:/Users/alan/.cursor/plugins/cache/cursor-public/browse/release_v0.2.4/node_modules/playwright')
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'

const BASE = process.env.WF_ABX_URL || 'http://127.0.0.1:28644'
const API = process.env.WF_ABX_API || 'http://127.0.0.1:29120'
const ADMIN_EMAIL = process.env.WF_QA_ADMIN_EMAIL || 'admin@example.com'
const OUT_DIR = join(process.cwd(), 'docs/ledger/audits/2026-07-25-abx-screenshots')
const AUDIT_PATH = join(process.cwd(), 'docs/ledger/audits/2026-07-25-abx-visual-qa.md')

const THEMES = [
  'minimal-light', 'minimal-dark', 'neo-light', 'neo-dark',
  'brutalist-light', 'brutalist-dark', 'liquid-glass-light', 'liquid-glass-dark',
  'frosted-glass-light', 'frosted-glass-dark', 'bauhaus', 'newspaper', 'notebook', 'blueprint',
]

const THEME_LABELS = {
  'minimal-light': 'Minimal Light', 'minimal-dark': 'Minimal Dark',
  'neo-light': 'Neo Light', 'neo-dark': 'Neo Dark',
  'brutalist-light': 'Brutalist Light', 'brutalist-dark': 'Brutalist Dark',
  'liquid-glass-light': 'Liquid Glass Light', 'liquid-glass-dark': 'Liquid Glass Dark',
  'frosted-glass-light': 'Frosted Glass Light', 'frosted-glass-dark': 'Frosted Glass Dark',
  bauhaus: 'Bauhaus', newspaper: 'Newspaper', notebook: 'Notebook', blueprint: 'Blueprint',
}

const findings = []
const stepLog = []
let wizardStatus = 'unknown'

function loadEnvFile(path) {
  const out = {}
  try {
    for (const line of readFileSync(path, 'utf8').split(/\r?\n/)) {
      const t = line.trim()
      if (!t || t.startsWith('#')) continue
      const i = t.indexOf('=')
      if (i < 1) continue
      out[t.slice(0, i).trim()] = t.slice(i + 1).trim()
    }
  } catch { /* optional */ }
  return out
}

function addFinding(severity, id, step, theme, issue, evidence = '') {
  findings.push({ severity, id, step, theme, issue, evidence })
}

function luminance(r, g, b) {
  const [rs, gs, bs] = [r, g, b].map((c) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs
}

function contrastRatio(fg, bg) {
  const l1 = luminance(...fg)
  const l2 = luminance(...bg)
  const lighter = Math.max(l1, l2)
  const darker = Math.min(l1, l2)
  return (lighter + 0.05) / (darker + 0.05)
}

function parseRgb(str) {
  const m = String(str || '').match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (!m) return null
  return [Number(m[1]), Number(m[2]), Number(m[3])]
}

async function collectMetrics(page) {
  return page.evaluate(() => {
    const pick = (sel) => document.querySelector(sel)
    const cs = (el) => (el ? getComputedStyle(el) : null)
    const root = document.documentElement
    const wizardTitle = pick('.wf-onboarding-page__title, .wf-wizard-panel__title, h1')
    const primaryBtn = pick('.wf-onboarding-page__footer button[data-tone="primary"], .wf-wizard-footer button.tone-primary, .wf-onboarding-page__footer .wf-action-btn--primary')
      || pick('.wf-onboarding-page__footer button:last-child')
    const themeTrigger = pick('.wf-theme-switcher__trigger')
    const menu = pick('.wf-theme-switcher__menu')
    const rail = pick('.wf-onboarding-rail')
    const body = pick('.wf-onboarding-page__body, .wf-wizard-panel__body')

    const layout = {}
    if (menu) {
      const r = menu.getBoundingClientRect()
      layout.themeMenu = {
        clippedH: r.right > window.innerWidth || r.left < 0,
        clippedV: r.bottom > window.innerHeight,
        right: r.right,
        vw: window.innerWidth,
      }
    }

    return {
      theme: root.dataset.theme,
      title: wizardTitle?.textContent?.trim() || '',
      stepText: pick('.wf-onboarding-rail__step.is-current, .wf-wizard-rail__item.is-active')?.textContent?.trim() || '',
      hasThemeSwitcher: Boolean(themeTrigger),
      overflow: {
        h: document.documentElement.scrollWidth > window.innerWidth + 2,
        w: document.documentElement.scrollWidth > window.innerWidth + 2,
      },
      surfaces: {
        primaryBtn: primaryBtn ? {
          bg: cs(primaryBtn).backgroundColor,
          color: cs(primaryBtn).color,
          opacity: cs(primaryBtn).opacity,
        } : null,
        rail: rail ? { bg: cs(rail).backgroundColor, color: cs(rail).color } : null,
        body: body ? { bg: cs(body).backgroundColor } : null,
        page: { bg: cs(root).backgroundColor },
      },
      layout,
      glass: root.dataset.style === 'glass',
    }
  })
}

async function auditTheme(page, stepName, theme) {
  const m = await collectMetrics(page)
  const slug = `${stepName}/${theme}`
  mkdirSync(OUT_DIR, { recursive: true })
  await page.screenshot({ path: join(OUT_DIR, `${slug}.png`), fullPage: false })

  if (m.theme !== theme) {
    addFinding('major', 'THEME-APPLY', stepName, theme, `data-theme is "${m.theme}" after selecting ${theme}`, slug)
  }
  if (!m.hasThemeSwitcher) {
    addFinding('major', 'THEME-SWITCHER', stepName, theme, 'Header theme switcher missing on wizard step', slug)
  }
  if (m.layout?.themeMenu?.clippedH) {
    addFinding('major', 'MENU-CLIP-H', stepName, theme, 'Theme dropdown clipped horizontally', JSON.stringify(m.layout.themeMenu))
  }
  if (m.layout?.themeMenu?.clippedV) {
    addFinding('minor', 'MENU-CLIP-V', stepName, theme, 'Theme dropdown clipped vertically', JSON.stringify(m.layout.themeMenu))
  }
  if (m.overflow?.w) {
    addFinding('minor', 'OVERFLOW', stepName, theme, `Horizontal overflow on ${stepName}`, slug)
  }

  const btn = m.surfaces?.primaryBtn
  if (btn?.bg && btn?.color) {
    const fg = parseRgb(btn.color)
    const bg = parseRgb(btn.bg)
    if (fg && bg) {
      const ratio = contrastRatio(fg, bg)
      if (ratio < 4.5) {
        addFinding('major', 'BTN-CONTRAST', stepName, theme, `Primary CTA contrast ${ratio.toFixed(2)}:1`, `${btn.color} on ${btn.bg}`)
      }
    }
    if (btn.opacity && parseFloat(btn.opacity) < 0.5) {
      addFinding('minor', 'BTN-FADE', stepName, theme, `Primary CTA low opacity (${btn.opacity})`, slug)
    }
  }

  if (m.glass && (theme.includes('glass') || theme.includes('frosted'))) {
    const pageBg = m.surfaces?.page?.bg
    const bodyBg = m.surfaces?.body?.bg
    if (pageBg && bodyBg && pageBg === bodyBg) {
      addFinding('minor', 'GLASS-FLAT', stepName, theme, 'Glass theme: wizard body blends with page canvas', `${pageBg}`)
    }
  }

  return m
}

async function switchTheme(page, theme) {
  await page.evaluate((id) => {
    localStorage.setItem('wf-theme', id)
    document.documentElement.dataset.theme = id
    document.documentElement.dataset.archTheme = id
  }, theme)

  const label = THEME_LABELS[theme]
  const trigger = page.locator('.wf-theme-switcher__trigger')
  if (await trigger.isVisible({ timeout: 1500 }).catch(() => false)) {
    await trigger.click()
    await page.waitForTimeout(250)
    const item = page.locator('.wf-theme-switcher__item').filter({ hasText: label })
    if (await item.count()) {
      await item.first().click()
      await page.waitForTimeout(350)
      return true
    }
    await page.keyboard.press('Escape')
  }
  await page.waitForTimeout(200)
  return true
}

async function cycleThemesOnStep(page, stepName) {
  const results = []
  for (const theme of THEMES) {
    await switchTheme(page, theme)
    const m = await auditTheme(page, stepName, theme)
    results.push({ theme, title: m.title })
  }
  return results
}

async function detectStep(page) {
  const meta = await page.evaluate(() => {
    const stepLabel = document.querySelector('.wf-onboarding-page__step-label, .wf-wizard-panel__step')?.textContent?.trim() || ''
    const title = document.querySelector('.wf-onboarding-page__title, .wf-wizard-panel__title, h1')?.textContent?.trim() || ''
    const hasSmtpHost = Boolean(document.querySelector('#wf-smtp-host'))
    const hasThemeGrid = Boolean(document.querySelector('.wf-theme-settings__option'))
    const hasAdminEmail = Boolean(document.querySelector('#wf-intro-admin-email'))
    const hasOtp = Boolean(document.querySelector('.wf-auth-otp-panel__cell, .wf-auth__otp-input'))
    const hasModeGrid = Boolean(document.querySelector('.wf-wizard-mode-grid'))
    return { stepLabel, title, hasSmtpHost, hasThemeGrid, hasAdminEmail, hasOtp, hasModeGrid }
  })

  if (meta.hasAdminEmail && meta.title.includes('Set up')) return 'intro'
  if (meta.hasThemeGrid || meta.title.includes('Pick a theme')) return 'theme'
  if (meta.hasModeGrid || (meta.title === 'Deployment' && !meta.hasSmtpHost)) return 'welcome'
  if (meta.hasSmtpHost || meta.title === 'Email delivery') return 'smtp'
  if (meta.hasOtp || meta.title.includes('Verify admin email')) return 'admin_auth'
  if (meta.title === 'Workframe Profile') return 'workframe'
  if (meta.title === 'Billing Model') return 'billing'
  if (meta.title === 'Integrations') return 'integrations'
  if (meta.title === 'Your Identity' || meta.title.startsWith('Join ')) return 'profile'
  if (meta.title === 'Your Agent') return 'agent'
  if (meta.title.includes("Agent's Model") || meta.title.includes('Provider & model')) return 'agent_model'
  if (meta.title === 'Your Team') return 'invites'
  if (meta.title.includes('Sign in')) return 'auth'
  return 'unknown'
}

async function waitForStepChange(page, prev, timeout = 30000) {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    const cur = await detectStep(page)
    if (cur !== prev) return cur
    await page.waitForTimeout(400)
  }
  return await detectStep(page)
}

async function fillOtp(page, code) {
  const digits = String(code).replace(/\D/g, '').slice(0, 6)
  const cells = page.locator('.wf-auth-otp-panel__cell input, .wf-auth__otp-input')
  if (await cells.count()) {
    await cells.first().click()
    await page.keyboard.type(digits)
    await page.waitForTimeout(500)
    return
  }
  const single = page.locator('input[inputmode="numeric"], input[autocomplete="one-time-code"]').first()
  if (await single.isVisible().catch(() => false)) await single.fill(digits)
}

async function main() {
  const env = loadEnvFile(join(process.cwd(), 'infra/compose/workframe/.env'))
  const smtp = {
    host: env.SMTP_HOST || 'smtp.gmail.com',
    port: env.SMTP_PORT || '587',
    user: env.SMTP_USER || 'hey@fabricadeprojetos.com',
    pass: env.SMTP_PASS || process.env.WF_SMTP_PASS || '',
    from: env.EMAIL_FROM || 'noreply@workfra.me',
  }

  const health = await fetch(`${API}/api/health`).then((r) => r.json()).catch(() => ({}))
  const install = await fetch(`${API}/api/install/status`).then((r) => r.json()).catch(() => ({}))

  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })

  try {
    await page.goto(BASE, { waitUntil: 'networkidle', timeout: 90000 })
    let step = await detectStep(page)

    // Resume-friendly: skip steps already completed in persisted wizard state
    const skipIntro = step !== 'intro' && step !== 'unknown'

    if (install.install_complete && step === 'auth') {
      wizardStatus = 'already_complete'
      stepLog.push({ step: 'auth', note: 'Install complete; login gate shown' })
      await cycleThemesOnStep(page, 'auth-login')
    } else if (!install.install_window_open && step !== 'intro') {
      wizardStatus = 'install_window_closed'
      await cycleThemesOnStep(page, step)
    } else {
      wizardStatus = 'in_progress'

      // INTRO
      if (step === 'intro' && !skipIntro) {
        await cycleThemesOnStep(page, 'intro')
        await page.fill('#wf-intro-admin-email', ADMIN_EMAIL)
        await page.getByRole('button', { name: 'Get started' }).click()
        step = await waitForStepChange(page, 'intro')
        stepLog.push({ step: 'intro', advancedTo: step })
      }

      // THEME
      if (step === 'theme') {
        await cycleThemesOnStep(page, 'theme')
        await page.getByRole('button', { name: /Use this theme|Skip for now/i }).first().click()
        step = await waitForStepChange(page, 'theme')
        stepLog.push({ step: 'theme', advancedTo: step })
      }

      // WELCOME / deployment
      if (step === 'welcome') {
        await cycleThemesOnStep(page, 'welcome')
        await page.getByRole('button', { name: 'My team on Docker' }).click()
        await page.waitForTimeout(2000)
        step = await waitForStepChange(page, 'welcome')
        stepLog.push({ step: 'welcome', advancedTo: step })
      }

      // SMTP
      if (step === 'smtp') {
        await cycleThemesOnStep(page, 'smtp')
        if (!smtp.pass) {
          addFinding('blocker', 'SMTP-PASS', 'smtp', '-', 'SMTP password unavailable for automation', 'Set WF_SMTP_PASS or compose .env')
          wizardStatus = 'blocked_smtp'
        } else {
          await page.fill('#wf-smtp-host', smtp.host)
          await page.fill('#wf-smtp-port', String(smtp.port))
          await page.fill('#wf-smtp-user', smtp.user)
          await page.fill('#wf-smtp-pass', smtp.pass)
          await page.fill('#wf-smtp-from', smtp.from)
          await page.getByRole('button', { name: 'Send test email' }).click()
          await page.waitForTimeout(15000)
          const statusBadge = await page.locator('.wf-onboarding-smtp-status__badge').textContent().catch(() => '')
          const err = await page.locator('.wf-auth__alert, .wf-notice, [role="alert"]').first().textContent().catch(() => '')
          if (/fail|error/i.test(err) && !/tested|ready/i.test(statusBadge || '')) {
            addFinding('blocker', 'SMTP-TEST', 'smtp', '-', 'SMTP test failed', String(err).slice(0, 200))
            wizardStatus = 'blocked_smtp_test'
          } else {
            const cont = page.getByRole('button', { name: /Continue to verification|Continue/i })
            await cont.click()
            step = await waitForStepChange(page, 'smtp')
            stepLog.push({ step: 'smtp', advancedTo: step })
          }
        }
      }

      // ADMIN OTP
      if (step === 'admin_auth') {
        await cycleThemesOnStep(page, 'admin_auth')
        let otp = await page.locator('.wf-auth__dev-code-value').textContent().catch(() => '')
        if (!otp?.trim()) {
          const respPromise = page.waitForResponse((r) => r.url().includes('/api/auth/start') && r.request().method() === 'POST', { timeout: 15000 }).catch(() => null)
          await page.getByRole('button', { name: /send|resend|verify/i }).first().click({ timeout: 5000 }).catch(() => {})
          const resp = await respPromise
          if (resp?.ok()) {
            const body = await resp.json().catch(() => ({}))
            otp = body.otp_code || ''
          }
        }
        if (!otp?.trim()) {
          otp = await page.locator('.wf-auth__dev-code-value').textContent().catch(() => '')
        }
        if (!otp?.trim()) {
          addFinding('blocker', 'OTP', 'admin_auth', '-', 'Could not obtain admin OTP (secure mode; email sent)', 'Check mailbox or enable WORKFRAME_E2E on loopback')
          wizardStatus = 'blocked_otp'
        } else {
          await fillOtp(page, otp.trim())
          await page.waitForTimeout(4000)
          step = await detectStep(page)
          stepLog.push({ step: 'admin_auth', advancedTo: step })
        }
      }

      // Remaining wizard steps (theme cycle each)
      const advance = async (stepName, buttonName) => {
        if (step !== stepName) return
        await cycleThemesOnStep(page, stepName)
        const btn = page.getByRole('button', { name: buttonName })
        if (await btn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await btn.click()
          const prev = step
          step = await waitForStepChange(page, prev)
          stepLog.push({ step: stepName, advancedTo: step })
        }
      }

      if (step === 'workframe') await advance('workframe', 'Continue')
      if (step === 'billing') {
        await cycleThemesOnStep(page, 'billing')
        const workspace = page.locator('input[name="wf-credential-mode"][value="workspace"], label:has-text("Company-pays")')
        if (await workspace.count()) await workspace.first().click().catch(() => {})
        await page.getByRole('button', { name: 'Continue' }).click()
        step = await waitForStepChange(page, 'billing')
        stepLog.push({ step: 'billing', advancedTo: step })
      }
      if (step === 'integrations') await advance('integrations', 'Skip')
      if (step === 'profile') {
        await cycleThemesOnStep(page, 'profile')
        const nameInput = page.locator('#wf-profile-display-name, input[name="displayName"]').first()
        if (await nameInput.isVisible().catch(() => false)) await nameInput.fill('Alan')
        await page.getByRole('button', { name: 'Continue' }).click()
        step = await waitForStepChange(page, 'profile')
        stepLog.push({ step: 'profile', advancedTo: step })
      }
      if (step === 'agent') await advance('agent', 'Continue')
      if (step === 'agent_model') {
        await cycleThemesOnStep(page, 'agent_model')
        const modelTab = page.getByRole('button', { name: /model/i }).first()
        if (await modelTab.isVisible().catch(() => false)) await modelTab.click()
        await page.waitForTimeout(1000)
        const modelOption = page.locator('[data-model-id], .wf-model-picker__option, [role="option"]').first()
        if (await modelOption.isVisible({ timeout: 5000 }).catch(() => false)) {
          await modelOption.click().catch(() => {})
        }
        const launch = page.getByRole('button', { name: /Continue|Launch Workframe/i })
        if (await launch.isEnabled().catch(() => false)) {
          await launch.click()
          step = await waitForStepChange(page, 'agent_model')
          stepLog.push({ step: 'agent_model', advancedTo: step })
        } else {
          addFinding('blocker', 'AGENT-MODEL', 'agent_model', '-', 'Cannot continue without LLM provider/model', 'Connect provider or use workspace billing with stack LLM')
          wizardStatus = 'blocked_agent_model'
        }
      }
      if (step === 'invites') await advance('invites', 'Skip')

      const finalInstall = await fetch(`${API}/api/install/status`).then((r) => r.json()).catch(() => ({}))
      if (finalInstall.install_complete) wizardStatus = 'complete'
      else if (wizardStatus === 'in_progress') wizardStatus = `partial_${step}`
    }

    // Dedupe findings by id+step+theme
    const seen = new Set()
    const unique = findings.filter((f) => {
      const k = `${f.id}|${f.step}|${f.theme}|${f.issue}`
      if (seen.has(k)) return false
      seen.add(k)
      return true
    })

    appendAudit(unique, stepLog, wizardStatus, { health, install })
    console.log(JSON.stringify({ wizardStatus, steps: stepLog, findings: unique.length, top: unique.slice(0, 15) }, null, 2))
  } finally {
    await browser.close()
  }
}

function appendAudit(unique, stepLog, status, meta) {
  const now = new Date().toISOString()
  const bySeverity = { blocker: 0, major: 0, minor: 0 }
  for (const f of unique) bySeverity[f.severity] = (bySeverity[f.severity] || 0) + 1

  const top10 = [...unique]
    .sort((a, b) => {
      const rank = { blocker: 0, major: 1, minor: 2 }
      return (rank[a.severity] ?? 3) - (rank[b.severity] ?? 3)
    })
    .slice(0, 10)

  const block = `
## Run ${now}

**Target:** ${BASE} (API ${API})  
**Wizard status:** \`${status}\`  
**create-workframe@0.1.26 on npm:** yes  
**Browser MCP:** unavailable on Windows (browse ENOENT / EACCES on .sock); used Playwright via \`.harness/abx-wizard-theme-loop.mjs\`

### Health at run
\`\`\`json
${JSON.stringify(meta.health, null, 2)}
\`\`\`

### Install status at run
\`\`\`json
${JSON.stringify(meta.install, null, 2)}
\`\`\`

### Wizard step log
${stepLog.map((s) => `- **${s.step}** → ${s.advancedTo || s.note || '—'}`).join('\n')}

### Theme matrix
- Surfaces audited: ${[...new Set(unique.map((f) => f.step))].join(', ') || 'see step log'}
- Themes per step: 14 (${THEMES.join(', ')})
- Screenshots: \`${OUT_DIR}\`

### Finding counts
| Severity | Count |
|----------|-------|
| blocker | ${bySeverity.blocker || 0} |
| major | ${bySeverity.major || 0} |
| minor | ${bySeverity.minor || 0} |

### Top 10 UI issues
${top10.map((f, i) => `${i + 1}. **[${f.severity}]** \`${f.id}\` — ${f.issue} _(step: ${f.step}, theme: ${f.theme})_${f.evidence ? ` — ${f.evidence}` : ''}`).join('\n')}

### All findings (${unique.length})
${unique.map((f) => `- [${f.severity}] ${f.id} @ ${f.step}/${f.theme}: ${f.issue}`).join('\n')}

`

  let existing = ''
  try { existing = readFileSync(AUDIT_PATH, 'utf8') } catch { existing = '# ABX visual QA audit — 2026-07-25\n' }
  if (existing.includes('_(populated during Phase 3–4)_')) {
    existing = existing.replace('_(populated during Phase 3–4)_', block.trim())
  } else {
    existing = existing.trimEnd() + '\n' + block
  }
  writeFileSync(AUDIT_PATH, existing)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
