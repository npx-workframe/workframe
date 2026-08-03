import { createRequire } from 'node:module'

/**
 * One-shot visual QA for shell + settings (ABX campaign).
 * Run: node .harness/visual-qa-abx.mjs
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'

const require = createRequire(import.meta.url)
// The Windows dogfood/QA runtime is supplied by the browser harness rather
// than bundled into the product workspace. Keep this runner aligned with the
// other local visual-QA scripts so it works from a clean source checkout.
const { chromium } = require('C:/Users/alan/.cursor/plugins/cache/cursor-public/browse/release_v0.2.4/node_modules/playwright')

const BASE = process.env.WF_QA_URL || 'http://127.0.0.1:18644'
const EMAIL = process.env.WF_QA_EMAIL
if (!EMAIL) {
  console.error('Set WF_QA_EMAIL (never commit credentials or operator emails to the repo).')
  process.exit(1)
}
const OUT_DIR = join(process.cwd(), '.harness', 'qa-screenshots', '2026-07-25-abx')
const DESKTOP = { width: 1280, height: 900 }
const MOBILE = { width: 390, height: 844 }

const VISIBLE_THEMES = [
  'minimal-light', 'minimal-dark',
  'neo-light', 'neo-dark',
  'brutalist-light', 'brutalist-dark',
  'liquid-glass-light', 'liquid-glass-dark',
  'frosted-glass-light', 'frosted-glass-dark',
  'bauhaus', 'newspaper', 'notebook', 'blueprint',
]

const PROVIDER_IDS = [
  'openai', 'anthropic', 'google', 'gemini', 'grok', 'perplexity',
  'openrouter', 'cursor', 'github', 'nvidia', 'brave', 'stripe',
]

const findings = []

function bug(id, severity, surface, theme, viewport, title, hint, evidence = '') {
  findings.push({ id, severity, surface, theme, viewport, title, hint, evidence })
}

async function shot(page, name) {
  mkdirSync(OUT_DIR, { recursive: true })
  const path = join(OUT_DIR, `${name}.png`)
  await page.screenshot({ path, fullPage: false })
  return path
}

async function loginIfNeeded(page) {
  await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 60000 })
  await page.waitForTimeout(2000)

  const emailInput = page.locator('input[type="email"], input[name="email"], input[autocomplete="email"]').first()
  if (await emailInput.isVisible({ timeout: 3000 }).catch(() => false)) {
    await emailInput.fill(EMAIL)
    const continueBtn = page.getByRole('button', { name: /continue|send|sign in|log in/i }).first()
    if (await continueBtn.isVisible().catch(() => false)) await continueBtn.click()
    await page.waitForTimeout(1500)

    // Try OTP from API response in dev mode
    const otpInput = page.locator('input[inputmode="numeric"], input[name="code"], input[autocomplete="one-time-code"]').first()
    if (await otpInput.isVisible({ timeout: 5000 }).catch(() => false)) {
      const res = await page.request.post(`${BASE}/api/auth/otp/request`, {
        data: { email: EMAIL },
        headers: { 'Content-Type': 'application/json' },
      }).catch(() => null)
      let code = ''
      if (res?.ok()) {
        const body = await res.json().catch(() => ({}))
        code = String(body.code || body.otp || body.dev_code || '')
      }
      if (!code) {
        bug('AUTH-001', 'blocker', 'auth', '-', 'desktop', 'Cannot obtain OTP (DEV_LOCAL_UNSAFE off)', 'infra/compose or install .env', 'OTP screen visible, no dev code in API')
        return false
      }
      await otpInput.fill(code)
      const verifyBtn = page.getByRole('button', { name: /verify|continue|sign in/i }).first()
      if (await verifyBtn.isVisible().catch(() => false)) await verifyBtn.click()
      await page.waitForTimeout(3000)
    }
  }

  // Skip onboarding wizard if present
  for (let i = 0; i < 8; i++) {
    const skip = page.getByRole('button', { name: /skip|later|just me|continue|get started|done/i }).first()
    const close = page.getByRole('button', { name: /close/i }).first()
    if (await skip.isVisible({ timeout: 2000 }).catch(() => false)) {
      await skip.click()
      await page.waitForTimeout(1000)
      continue
    }
    if (await close.isVisible({ timeout: 500 }).catch(() => false)) {
      const dialog = page.locator('[role="dialog"]').first()
      if (await dialog.isVisible().catch(() => false)) {
        await close.click().catch(() => {})
        await page.waitForTimeout(800)
        continue
      }
    }
    break
  }

  const shell = page.locator('.dockview-theme-abyss, .wf-shell, [class*="dockview"], .wf-workspace').first()
  const hasShell = await shell.isVisible({ timeout: 8000 }).catch(() => false)
  if (!hasShell) {
    await shot(page, 'blocked-no-shell')
    bug('SHELL-000', 'blocker', 'shell', '-', 'desktop', 'Main shell not reachable after login/wizard', 'components/shell/', await page.title())
    return false
  }
  return true
}

async function openProfileSettings(page) {
  const triggers = [
    page.getByRole('button', { name: /profile|account|settings/i }),
    page.locator('[aria-label*="profile" i], [aria-label*="account" i], [data-testid="user-menu"]').first(),
    page.locator('.wf-shell__user, .wf-user-trigger, button.wf-avatar').first(),
  ]
  for (const t of triggers) {
    if (await t.isVisible({ timeout: 1500 }).catch(() => false)) {
      await t.click()
      await page.waitForTimeout(800)
      break
    }
  }
  const sheet = page.locator('.wf-settings-sheet, [role="dialog"]').filter({ hasText: /profile|appearance|connect/i }).first()
  return sheet.isVisible({ timeout: 5000 }).catch(() => false)
}

async function setTheme(page, themeId) {
  await page.evaluate((id) => {
    document.documentElement.dataset.theme = id
    localStorage.setItem('workframe-theme', id)
    window.dispatchEvent(new CustomEvent('workframe-theme-change', { detail: id }))
  }, themeId)
  await page.waitForTimeout(400)
}

async function auditBrandMarks(page, theme, viewport) {
  const marks = page.locator('img.wf-brand-mark, .wf-brand-mark')
  const count = await marks.count()
  for (let i = 0; i < count; i++) {
    const el = marks.nth(i)
    const box = await el.boundingBox().catch(() => null)
    const cls = (await el.getAttribute('class').catch(() => '')) || ''
    const src = await el.getAttribute('src').catch(() => null)
    const isFallback = cls.includes('wf-brand-mark--fallback')
    const natural = await el.evaluate((node) => {
      if (node.tagName !== 'IMG') return { ok: false, w: 0, h: 0 }
      const img = /** @type {HTMLImageElement} */ (node)
      return { ok: img.naturalWidth > 0 && img.naturalHeight > 0, w: img.naturalWidth, h: img.naturalHeight }
    }).catch(() => ({ ok: false, w: 0, h: 0 }))

    if (isFallback || !natural.ok) {
      const label = await el.getAttribute('aria-label').catch(() => '') || src || `mark-${i}`
      bug(
        `BRAND-${theme}-${viewport}-${i}`,
        'major',
        'provider-icons',
        theme,
        viewport,
        `Brand mark failed or fallback letter shown: ${label}`,
        'components/ui/BrandMark.tsx, lib/brandAssets.ts, styles for .wf-brand-mark',
        `fallback=${isFallback} src=${src} natural=${natural.w}x${natural.h}`,
      )
    }
  }
}

async function checkOverflow(page, theme, viewport, surface) {
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement
    return {
      h: doc.scrollHeight > window.innerHeight + 2,
      w: doc.scrollWidth > window.innerWidth + 2,
    }
  })
  if (overflow.w) {
    bug(`OVERFLOW-W-${surface}`, 'minor', surface, theme, viewport, `Horizontal overflow on ${surface}`, 'styles/shell, mobile-inner-pages.css')
  }
}

async function testSettingsTabs(page, theme, viewport) {
  const tabs = [
    { name: /profile/i, key: 'profile' },
    { name: /connect/i, key: 'connect' },
    { name: /agents/i, key: 'agents' },
    { name: /appearance/i, key: 'appearance' },
  ]
  for (const tab of tabs) {
    const btn = page.getByRole('button', { name: tab.name }).or(page.getByRole('tab', { name: tab.name })).first()
    if (await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await btn.click()
      await page.waitForTimeout(600)
      await checkOverflow(page, theme, viewport, `settings-${tab.key}`)
      if (tab.key === 'appearance') {
        const options = page.locator('.wf-theme-settings__option')
        const n = await options.count()
        if (n !== 14) {
          bug('THEME-COUNT', 'major', 'appearance', theme, viewport, `Expected 14 theme options, saw ${n}`, 'lib/themeOptions.ts, components/settings/ThemePickerGrid.tsx')
        }
      }
      if (tab.key === 'connect') {
        await auditBrandMarks(page, theme, viewport)
      }
    } else {
      bug(`TAB-MISS-${tab.key}`, 'major', 'settings', theme, viewport, `Settings tab missing: ${tab.key}`, 'components/workspace/UserProfileSheet.tsx')
    }
  }
}

async function testTheme(page, theme, viewportName, size) {
  await page.setViewportSize(size)
  await setTheme(page, theme)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(1500)

  const applied = await page.evaluate(() => document.documentElement.dataset.theme)
  if (applied !== theme) {
    bug(`THEME-APPLY-${theme}`, 'major', 'shell', theme, viewportName, `Theme not applied after reload (got ${applied})`, 'hooks/useDocumentTheme.ts, hooks/useTheme.ts')
  }

  await checkOverflow(page, theme, viewportName, 'shell')
  await shot(page, `shell-${theme}-${viewportName}`)

  const opened = await openProfileSettings(page)
  if (opened) {
    await testSettingsTabs(page, theme, viewportName)
    await shot(page, `settings-appearance-${theme}-${viewportName}`)
    const close = page.getByRole('button', { name: /close/i }).first()
    if (await close.isVisible().catch(() => false)) await close.click()
  } else {
    bug('SETTINGS-OPEN', 'major', 'settings', theme, viewportName, 'Could not open profile settings sheet', 'components/workspace/UserProfileSheet.tsx')
  }
}

async function testProviderDemoPage(page) {
  // Inject a demo grid of all provider marks for verification
  await page.evaluate((ids) => {
    const root = document.createElement('div')
    root.id = 'wf-qa-provider-grid'
    root.style.cssText = 'position:fixed;inset:40px;z-index:99999;background:var(--wf-canvas,#111);padding:16px;display:grid;grid-template-columns:repeat(4,1fr);gap:12px;overflow:auto'
    for (const id of ids) {
      const cell = document.createElement('div')
      cell.style.cssText = 'border:1px solid #666;padding:8px;text-align:center'
      cell.dataset.provider = id
      const img = document.createElement('img')
      img.className = 'wf-brand-mark wf-brand-img--theme'
      img.alt = id
      img.src = `/src/assets/brands/${id}.svg`
      cell.appendChild(img)
      const label = document.createElement('div')
      label.textContent = id
      cell.appendChild(label)
      root.appendChild(cell)
    }
    document.body.appendChild(root)
  }, PROVIDER_IDS)
  await page.waitForTimeout(500)
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext()
  const page = await context.newPage()

  const ok = await loginIfNeeded(page)
  if (!ok) {
    console.log(JSON.stringify({ findings, blocked: true }, null, 2))
    await browser.close()
    return
  }

  // Sample themes for full matrix: all on desktop, subset on mobile for time
  for (const theme of VISIBLE_THEMES) {
    await testTheme(page, theme, 'desktop', DESKTOP)
  }
  for (const theme of ['minimal-light', 'neo-dark', 'brutalist-light', 'liquid-glass-dark', 'bauhaus', 'blueprint']) {
    await testTheme(page, theme, 'mobile', MOBILE)
  }

  // Model picker / provider icons via settings connect + model trigger if available
  await page.setViewportSize(DESKTOP)
  await openProfileSettings(page)
  const connectTab = page.getByRole('button', { name: /connect/i }).or(page.getByRole('tab', { name: /connect/i })).first()
  if (await connectTab.isVisible().catch(() => false)) {
    await connectTab.click()
    await page.waitForTimeout(800)
    await auditBrandMarks(page, 'connect-panel', 'desktop')
    await shot(page, 'connect-providers-desktop')
  }

  await browser.close()
  console.log(JSON.stringify({ findings, screenshotDir: OUT_DIR, themesTested: VISIBLE_THEMES.length }, null, 2))
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
