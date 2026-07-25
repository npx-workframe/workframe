#!/usr/bin/env node
/**
 * Generate Workframe favicon, PWA, and OG assets from workframe-color.svg.
 * White canvas + centered purple mark (#79689D).
 *
 * Run: node scripts/workframe/generate-branding-assets.mjs
 * Requires: sharp (root devDependency)
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const MARK_PATHS = `<path d="M24 0H0V384H24V0Z" fill="#79689D"/>
<path d="M96 0H48V384H96V0Z" fill="#79689D" fill-opacity="0.8"/>
<path d="M384 0H240V384H384V0Z" fill="#79689D" fill-opacity="0.4"/>
<path d="M216 0H120V384H216V0Z" fill="#79689D" fill-opacity="0.6"/>`

const BRAND_COLOR = '#79689D'
const OUT_DIRS = [
  path.join(ROOT, 'apps/web/public'),
  path.join(ROOT, 'apps/web/src/assets/branding'),
  path.join(ROOT, 'apps/website/public'),
]

function framedSquareSvg(size, iconSize) {
  const offset = (size - iconSize) / 2
  const scale = iconSize / 384
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
<rect width="${size}" height="${size}" fill="#ffffff"/>
<g transform="translate(${offset} ${offset}) scale(${scale})">
${MARK_PATHS}
</g>
</svg>`
}

function ogImageSvg() {
  const w = 1200
  const h = 630
  const icon = 320
  const offset = (w - icon) / 2
  const y = (h - icon) / 2
  const scale = icon / 384
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
<rect width="${w}" height="${h}" fill="#ffffff"/>
<g transform="translate(${offset} ${y}) scale(${scale})">
${MARK_PATHS}
</g>
<text x="${w / 2}" y="${h - 72}" text-anchor="middle" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="42" font-weight="600" fill="#27272a">Workframe</text>
<text x="${w / 2}" y="${h - 28}" text-anchor="middle" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="22" fill="#5d5d66">The Social OS for Autonomous Businesses</text>
</svg>`
}

function faviconSvg() {
  return framedSquareSvg(32, 28)
}

async function main() {
  let sharp
  try {
    sharp = (await import('sharp')).default
  } catch {
    console.error('Install sharp: pnpm add -D sharp -w')
    process.exit(1)
  }

  for (const dir of OUT_DIRS) {
    fs.mkdirSync(dir, { recursive: true })
  }

  const writes = []
  const writeSvg = (name, svg) => {
    for (const dir of OUT_DIRS) {
      const dest = path.join(dir, name)
      if (name === 'og-default.png' && dir.includes('assets/branding')) {
        fs.writeFileSync(path.join(dir, 'og-default.svg'), ogImageSvg())
        continue
      }
      fs.writeFileSync(dest.endsWith('.png') ? dest.replace('.png', '.svg') : dest, svg)
    }
  }

  writeSvg('favicon.svg', faviconSvg())
  writeSvg('workframe-mark-1024.svg', framedSquareSvg(1024, 512))

  const pngJobs = [
    ['icon-32.png', framedSquareSvg(32, 28), 32],
    ['icon-96.png', framedSquareSvg(96, 84), 96],
    ['apple-touch-icon.png', framedSquareSvg(180, 156), 180],
    ['icon-192.png', framedSquareSvg(192, 168), 192],
    ['icon-512.png', framedSquareSvg(512, 448), 512],
    ['og-default.png', ogImageSvg(), null],
  ]

  for (const [name, svg, size] of pngJobs) {
    const pipeline = sharp(Buffer.from(svg))
    if (name === 'og-default.png') {
      const buf = await pipeline.png().toBuffer()
      for (const dir of OUT_DIRS) {
        if (dir.includes('assets/branding')) {
          fs.writeFileSync(path.join(dir, 'og-default.svg'), ogImageSvg())
        }
        fs.writeFileSync(path.join(dir, name), buf)
      }
      writes.push(name)
      continue
    }
    const buf = await pipeline.resize(size, size).png().toBuffer()
    for (const dir of OUT_DIRS) {
      fs.writeFileSync(path.join(dir, name), buf)
    }
    writes.push(name)
  }

  // favicon.ico (32px) for legacy browsers
  const icoBuf = await sharp(Buffer.from(faviconSvg())).resize(32, 32).png().toBuffer()
  for (const dir of [OUT_DIRS[0], OUT_DIRS[2]]) {
    fs.writeFileSync(path.join(dir, 'favicon.ico'), icoBuf)
  }

  console.log('generate-branding-assets: OK')
  console.log('  svg: favicon.svg, workframe-mark-1024.svg')
  console.log('  png:', writes.join(', '))
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
