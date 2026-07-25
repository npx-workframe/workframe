import { createRequire } from 'node:module'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const require = createRequire(import.meta.url)
const { chromium } = require('C:/Users/alan/.cursor/plugins/cache/cursor-public/browse/release_v0.2.4/node_modules/playwright')

const BASE = 'http://127.0.0.1:28644'
const OUT = 'd:/ab/projects/workframe/docs/ledger/audits/2026-07-25-abx-screenshots'
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
function add(severity, id, step, theme, issue, evidence = '') {
  findings.push({ severity, id, step, theme, issue, evidence })
}

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

async function metrics(page) {
  return page.evaluate(() => {
    const cs = (el) => (el ? getComputedStyle(el) : null)
    const root = document.documentElement
    const btn = document.querySelector('.wf-onboarding-page__footer button:last-child')
    const menu = document.querySelector('.wf-theme-switcher__menu')
    const rail = document.querySelector('.wf-onboarding-wizard__rail')
    const title = document.querySelector('.wf-onboarding-page__title')?.textContent?.trim()
    let layout = {}
    if (menu) {
      const r = menu.getBoundingClientRect()
      layout = { clippedH: r.right > innerWidth, clippedV: r.bottom > innerHeight }
    }
    return {
      theme: root.dataset.theme,
      title,
      hasSwitcher: Boolean(document.querySelector('.wf-theme-switcher__trigger')),
      overflow: document.documentElement.scrollWidth > innerWidth + 2,
      btn: btn ? { bg: cs(btn).backgroundColor, color: cs(btn).color, opacity: cs(btn).opacity } : null,
      rail: rail ? { bg: cs(rail).backgroundColor, color: cs(rail).color } : null,
      layout,
      glass: root.dataset.style === 'glass',
    }
  })
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
    if (await item.count()) {
      await item.first().click()
      await page.waitForTimeout(300)
    } else {
      await page.keyboard.press('Escape')
    }
  }
}

async function auditTheme(page, step, theme) {
  const m = await metrics(page)
  mkdirSync(join(OUT, step), { recursive: true })
  await page.screenshot({ path: join(OUT, step, `${theme}.png`) })

  if (m.theme !== theme) add('major', 'THEME-APPLY', step, theme, `Theme not applied (got ${m.theme})`)
  if (!m.hasSwitcher) add('major', 'NO-SWITCHER', step, theme, 'Theme switcher missing')
  if (m.layout?.clippedH) add('major', 'MENU-CLIP-H', step, theme, 'Theme menu clipped horizontally')
  if (m.layout?.clippedV) add('minor', 'MENU-CLIP-V', step, theme, 'Theme menu clipped vertically')
  if (m.overflow) add('minor', 'OVERFLOW', step, theme, 'Horizontal overflow')

  if (m.btn) {
    const fg = parseRgb(m.btn.color)
    const bg = parseRgb(m.btn.bg)
    if (fg && bg) {
      const ratio = contrastRatio(fg, bg)
      if (ratio < 4.5) add('major', 'BTN-CONTRAST', step, theme, `Primary CTA contrast ${ratio.toFixed(2)}:1`)
    }
    if (parseFloat(m.btn.opacity || '1') < 0.45) {
      add('minor', 'BTN-OPACITY', step, theme, `CTA faded (opacity ${m.btn.opacity})`)
    }
  }

  if (m.glass && theme.includes('glass') && m.rail) {
    const fg = parseRgb(m.rail.color)
    const bg = parseRgb(m.rail.bg)
    if (fg && bg && contrastRatio(fg, bg) < 3) {
      add('major', 'RAIL-CONTRAST', step, theme, 'Wizard rail text low contrast on glass theme')
    }
  }

  // Open theme menu for overlap audit
  const trigger = page.locator('.wf-theme-switcher__trigger')
  if (await trigger.isVisible().catch(() => false)) {
    await trigger.click()
    await page.waitForTimeout(250)
    const overlap = await page.evaluate(() => {
      const menu = document.querySelector('.wf-theme-switcher__menu')
      const panel = document.querySelector('.wf-onboarding-page__body')
      if (!menu || !panel) return null
      const mr = menu.getBoundingClientRect()
      const pr = panel.getBoundingClientRect()
      return { menuOverPanel: mr.top < pr.bottom && mr.bottom > pr.top && mr.left < pr.right }
    })
    if (overlap?.menuOverPanel) {
      add('minor', 'MENU-OVERLAP', step, theme, 'Theme dropdown overlaps wizard body content')
    }
    await page.keyboard.press('Escape')
  }
}

async function cycleThemes(page, step) {
  for (const theme of THEMES) {
    await switchTheme(page, theme)
    await auditTheme(page, step, theme)
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 90000 })

  const audited = []
  const railLabels = [
    'Email delivery', 'Workframe Profile', 'Billing Model', 'Integrations',
    'Your Identity', 'Your Agent', "Agent's Model", 'Your Team',
  ]

  for (const label of railLabels) {
    const btn = page.locator('.wf-onboarding-wizard__step-btn').filter({ hasText: label }).first()
    if (!(await btn.isVisible({ timeout: 2000 }).catch(() => false))) continue
    await btn.click()
    await page.waitForTimeout(900)
    const title = (await page.locator('.wf-onboarding-page__title').textContent().catch(() => label)) || label
    const key = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
    await cycleThemes(page, key)
    audited.push(key)
  }

  console.log(JSON.stringify({ audited, findingsCount: findings.length, findings }, null, 2))
  await browser.close()
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
