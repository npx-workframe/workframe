import { createRequire } from 'node:module'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const require = createRequire(import.meta.url)
const { chromium } = require('C:/Users/alan/.cursor/plugins/cache/cursor-public/browse/release_v0.2.4/node_modules/playwright')

const BASE = 'http://127.0.0.1:28644'
const OUT = join(process.cwd(), 'docs/ledger/audits/2026-07-25-abx-screenshots')
const THEMES = [
  'minimal-light', 'minimal-dark', 'neo-light', 'neo-dark',
  'brutalist-light', 'brutalist-dark', 'liquid-glass-light', 'liquid-glass-dark',
  'frosted-glass-light', 'frosted-glass-dark', 'bauhaus', 'newspaper', 'notebook', 'blueprint',
]
const LABELS = {
  'minimal-light': 'Minimal Light', 'minimal-dark': 'Minimal Dark',
  'neo-light': 'Neo Light', 'neo-dark': 'Neo Dark',
  'brutalist-light': 'Brutalist Light', 'brutalist-dark': 'Brutalist Dark',
  'liquid-glass-light': 'Liquid Glass Light', 'liquid-glass-dark': 'Liquid Glass Dark',
  'frosted-glass-light': 'Frosted Glass Light', 'frosted-glass-dark': 'Frosted Glass Dark',
  bauhaus: 'Bauhaus', newspaper: 'Newspaper', notebook: 'Notebook', blueprint: 'Blueprint',
}

const findings = []

function parseRgb(str) {
  const m = String(str || '').match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (!m) return null
  return [Number(m[1]), Number(m[2]), Number(m[3])]
}

function contrastRatio(fg, bg) {
  const L = (c) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  const l1 = 0.2126 * L(fg[0]) + 0.7152 * L(fg[1]) + 0.0722 * L(fg[2])
  const l2 = 0.2126 * L(bg[0]) + 0.7152 * L(bg[1]) + 0.0722 * L(bg[2])
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
}

function add(severity, id, step, theme, issue, evidence = '') {
  findings.push({ severity, id, step, theme, issue, evidence })
}

async function switchTheme(page, theme) {
  await page.evaluate((id) => {
    localStorage.setItem('wf-theme', id)
    document.documentElement.dataset.theme = id
  }, theme)
  const trigger = page.locator('.wf-theme-switcher__trigger')
  if (await trigger.isVisible().catch(() => false)) {
    await trigger.click()
    await page.waitForTimeout(200)
    const item = page.locator('.wf-theme-switcher__item').filter({ hasText: LABELS[theme] })
    if (await item.count()) await item.first().click()
    else await page.keyboard.press('Escape')
    await page.waitForTimeout(300)
  }
}

async function audit(page, step, theme) {
  const data = await page.evaluate(() => {
    const cs = (el) => (el ? getComputedStyle(el) : null)
    const title = document.querySelector('.wf-onboarding-page__title')?.textContent?.trim() || ''
    const disabledBtns = [...document.querySelectorAll('.wf-onboarding-page__footer button:disabled, .wf-onboarding-page__footer button[disabled]')]
      .map((b) => ({ text: b.textContent?.trim(), color: cs(b).color, bg: cs(b).backgroundColor, opacity: cs(b).opacity }))
    const menu = document.querySelector('.wf-theme-switcher__menu')
    let menuClip = null
    if (menu) {
      const r = menu.getBoundingClientRect()
      menuClip = { h: r.right > innerWidth || r.left < 0, v: r.bottom > innerHeight }
    }
    return {
      applied: document.documentElement.dataset.theme,
      title,
      disabledBtns,
      menuClip,
      overflow: document.documentElement.scrollWidth > innerWidth + 2,
      hasThemeGrid: Boolean(document.querySelector('.wf-theme-settings__option')),
      hasAdminEmail: Boolean(document.querySelector('#wf-intro-admin-email')),
      hasModeGrid: Boolean(document.querySelector('.wf-wizard-mode-grid')),
    }
  })

  mkdirSync(join(OUT, step), { recursive: true })
  await page.screenshot({ path: join(OUT, step, `${theme}.png`) })

  if (data.applied !== theme) add('major', 'THEME-APPLY', step, theme, `Theme not applied (${data.applied})`)
  if (data.overflow) add('minor', 'OVERFLOW', step, theme, 'Horizontal page overflow')
  if (data.menuClip?.h) add('major', 'MENU-CLIP', step, theme, 'Theme menu clipped horizontally')
  if (data.menuClip?.v) add('minor', 'MENU-CLIP-V', step, theme, 'Theme menu clipped vertically')

  for (const btn of data.disabledBtns) {
    const fg = parseRgb(btn.color)
    const bg = parseRgb(btn.bg)
    if (fg && bg) {
      const ratio = contrastRatio(fg, bg)
      if (ratio < 3) {
        add('major', 'DISABLED-CTA', step, theme, `Disabled footer CTA "${btn.text}" contrast ${ratio.toFixed(2)}:1`, `${btn.color} on ${btn.bg}`)
      } else if (ratio < 4.5) {
        add('minor', 'DISABLED-CTA', step, theme, `Disabled footer CTA "${btn.text}" marginal contrast ${ratio.toFixed(2)}:1`)
      }
    }
  }

  // Theme picker grid on theme step
  if (data.hasThemeGrid) {
    const swatchIssues = await page.evaluate(() => {
      const issues = []
      for (const el of document.querySelectorAll('.wf-theme-settings__option')) {
        const label = el.querySelector('.wf-theme-settings__label')?.textContent?.trim()
        const fill = el.querySelector('.wf-theme-settings__fill')
        if (!fill) continue
        const cs = getComputedStyle(fill)
        const border = cs.borderColor
        const bg = cs.backgroundColor
        if (border === bg) issues.push(`${label}: swatch border blends with fill`)
      }
      return issues
    })
    for (const msg of swatchIssues.slice(0, 2)) add('minor', 'SWATCH-BORDER', step, theme, msg)
  }

  return data.title
}

async function cycle(page, step) {
  for (const theme of THEMES) {
    await switchTheme(page, theme)
    await audit(page, step, theme)
  }
}

async function gotoRail(page, label) {
  const btn = page.locator('.wf-onboarding-wizard__step-btn').filter({ hasText: label }).first()
  if (!(await btn.isVisible({ timeout: 2000 }).catch(() => false))) return false
  const cls = await btn.getAttribute('class').catch(() => '')
  if (!cls?.includes('is-clickable')) return false
  await btn.click()
  await page.waitForTimeout(900)
  return true
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 90000 })

  const visited = []
  const targets = [
    { rail: 'Welcome', key: 'intro' },
    { rail: 'Your Theme', key: 'theme' },
    { rail: 'Deployment', key: 'welcome' },
    { rail: 'Email delivery', key: 'smtp' },
  ]

  for (const t of targets) {
    const ok = await gotoRail(page, t.rail)
    if (!ok && t.key !== 'smtp') continue
    const title = await page.locator('.wf-onboarding-page__title').textContent().catch(() => '')
    visited.push({ key: t.key, title, navigated: ok })
    await cycle(page, t.key)
  }

  // Mobile pass on smtp + theme
  await page.setViewportSize({ width: 390, height: 844 })
  await gotoRail(page, 'Email delivery')
  for (const theme of ['minimal-light', 'neo-dark', 'liquid-glass-dark', 'frosted-glass-light', 'brutalist-light', 'blueprint']) {
    await switchTheme(page, theme)
    await audit(page, 'smtp-mobile', theme)
    const trigger = page.locator('.wf-theme-switcher__trigger')
    if (await trigger.isVisible().catch(() => false)) {
      await trigger.click()
      await page.waitForTimeout(200)
      const menuClip = await page.evaluate(() => {
        const m = document.querySelector('.wf-theme-switcher__menu')
        if (!m) return null
        const r = m.getBoundingClientRect()
        return r.right > innerWidth || r.left < 0 || r.bottom > innerHeight
      })
      if (menuClip) add('major', 'MENU-CLIP-MOBILE', 'smtp-mobile', theme, 'Theme menu clipped on 390px viewport')
      await page.keyboard.press('Escape')
    }
  }

  console.log(JSON.stringify({ visited, findingsCount: findings.length, findings }, null, 2))
  await browser.close()
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
