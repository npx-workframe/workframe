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

export const findings = []

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
    await page.waitForTimeout(250)
  }
}

async function audit(page, step, theme) {
  const data = await page.evaluate(() => {
    const cs = (el) => getComputedStyle(el)
    const btns = [...document.querySelectorAll('button')].filter((b) =>
      /test email|verification|started|theme|team on docker/i.test(b.textContent || ''),
    )
    const menu = document.querySelector('.wf-theme-switcher__menu')
    let menuClip = false
    if (menu) {
      const r = menu.getBoundingClientRect()
      menuClip = r.right > innerWidth || r.left < 0 || r.bottom > innerHeight
    }
    return {
      theme: document.documentElement.dataset.theme,
      title: document.querySelector('.wf-onboarding-page__title')?.textContent?.trim(),
      btns: btns.map((b) => ({
        text: b.textContent?.trim(),
        disabled: b.disabled,
        opacity: cs(b).opacity,
      })),
      overflow: document.documentElement.scrollWidth > innerWidth + 2,
      menuClip,
      swatchCount: document.querySelectorAll('.wf-theme-settings__option').length,
    }
  })

  mkdirSync(join(OUT, step), { recursive: true })
  await page.screenshot({ path: join(OUT, step, `${theme}.png`) })

  if (data.theme !== theme) add('major', 'THEME-APPLY', step, theme, `Theme not applied (got ${data.theme})`)
  if (data.overflow) add('minor', 'OVERFLOW', step, theme, 'Horizontal overflow')
  if (data.menuClip) add('major', 'MENU-CLIP', step, theme, 'Theme dropdown clipped in viewport')

  for (const btn of data.btns) {
    if (btn.disabled && parseFloat(btn.opacity || '1') <= 0.5) {
      add('major', 'DISABLED-FADE', step, theme, `Disabled CTA "${btn.text}" opacity ${btn.opacity} — nearly invisible`)
    }
  }

  if (step === 'theme' && data.swatchCount !== 14) {
    add('major', 'SWATCH-COUNT', step, theme, `Theme grid shows ${data.swatchCount} options, expected 14`)
  }
}

async function cycleFixed(page, step) {
  for (const theme of THEMES) {
    await switchTheme(page, theme)
    await audit(page, step, theme)
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 90000 })

  for (const label of ['Welcome', 'Your Theme', 'Deployment', 'Email delivery']) {
    const btn = page.locator('button.wf-onboarding-wizard__step-btn').filter({ hasText: label }).first()
    if (!(await btn.count())) continue
    await btn.click()
    await page.waitForTimeout(900)
    const key = label.toLowerCase().replace(/\s+/g, '-')
    await cycleFixed(page, key)
  }

  await page.setViewportSize({ width: 390, height: 844 })
  await page.locator('button.wf-onboarding-wizard__step-btn').filter({ hasText: 'Email delivery' }).first().click()
  for (const theme of ['minimal-light', 'neo-dark', 'liquid-glass-dark', 'frosted-glass-light', 'brutalist-light', 'blueprint']) {
    await switchTheme(page, theme)
    await audit(page, 'smtp-mobile', theme)
    await page.locator('.wf-theme-switcher__trigger').click().catch(() => {})
    await page.waitForTimeout(200)
    const clipped = await page.evaluate(() => {
      const m = document.querySelector('.wf-theme-switcher__menu')
      if (!m) return false
      const r = m.getBoundingClientRect()
      return r.right > innerWidth || r.left < 0 || r.bottom > innerHeight
    })
    if (clipped) add('major', 'MENU-CLIP-MOBILE', 'smtp-mobile', theme, 'Theme menu clipped on 390px viewport')
    await page.keyboard.press('Escape')
  }

  console.log(JSON.stringify({ findingsCount: findings.length, findings }, null, 2))
  await browser.close()
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
