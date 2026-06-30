/** In-memory dogfood store — future /Files/ gateway will replace this. */
const artifactStore = new Map<string, string>()

const SVG_LOGO = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" fill="none">
  <rect width="120" height="120" rx="28" fill="#0a0a0f"/>
  <circle cx="60" cy="60" r="34" stroke="#7c3aed" stroke-width="6"/>
  <path d="M42 62 L56 76 L82 46" stroke="#0e7490" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`

const PNG_PLACEHOLDER =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">
    <defs>
      <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop stop-color="#6d28d9" offset="0"/>
        <stop stop-color="#0e7490" offset="1"/>
      </linearGradient>
    </defs>
    <rect width="100%" height="100%" fill="url(#g)"/>
    <text x="50%" y="50%" fill="white" font-family="sans-serif" font-size="28" text-anchor="middle" dominant-baseline="middle">Workframe hero.png</text>
  </svg>`)

const SEED: Record<string, string> = {
  'readme-md': `# Workframe

Welcome to your **{ProjectName}** workspace — a Hermes-backed project shell with chat, files, and an in-app browser.

This readme is a **markdown style showcase**: every common GFM element below is styled via \`markdown.css\` and rendered in the browser preview panel.

---

## Surfaces at a glance

1. **Chat** — talk to \`{ProjectName} Agent\` and specialists
2. **Files** — browse \`/Files/\` from the explorer tree
3. **Browser** — preview, code, edit, and navigate artifacts

### Quick task list

- [x] Open \`readme.md\` in preview mode
- [x] Toggle **light / dark** and re-check syntax colors
- [ ] Wire the gateway for live \`/Files/\` reads

---

## Typography samples

Regular paragraph with *emphasis*, **strong weight**, ~~strikethrough~~, and <ins>underlined insert</ins>. You can combine **_bold italic_** in one span.

Inline code like \`Agents/profiles/\` and keyboard hints: save with <kbd>Ctrl</kbd>+<kbd>S</kbd> (or <kbd>⌘</kbd>+<kbd>S</kbd>).

H<sub>2</sub>O and E=mc<sup>2</sup> demonstrate subscript and superscript. <mark>Highlighted text</mark> uses a mint-tinted background.

Abbreviations work too: <abbr title="General File Manager">GFM</abbr> is the markdown dialect we target.

> **Dogfood note:** this content lives in mock artifacts until the gateway wires \`/Files/\`.
>
> Nested blockquote:
>
> > The browser panel should feel like a first-class reading surface — generous padding, readable measure, and theme-aware code color.

---

## Links & media

- [Workframe vision doc](/Files/workframe.md) *(placeholder link)*
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — upstream runtime
- [Marked GFM spec](https://github.github.com/gfm/)

![Workframe placeholder hero](/Files/assets/hero.png)

*Figure: demo image reference — opens from the file tree when wired.*

---

## Lists

### Unordered (nested)

- Crew rail profiles
  - Visionary
  - Architect
  - Dev
- Files panel
  - Folders collapse on re-click
  - Type icons + capability routing
- Browser modes
  - Preview / Code / Edit / Navigate

### Ordered

1. Scaffold UI in \`packages/workframe-ui\`
2. Dogfood in meta Docker stack
3. Ship via \`create-workframe\` installer

---

## Table

| Surface | Primary action | Default mode |
|--------|----------------|--------------|
| Chat | Message composer | Chat |
| Files | Open in browser | Tree |
| Browser | Preview artifact | Preview |
| Code | Syntax highlight | Code |

---

## Code blocks

### TypeScript

\`\`\`typescript
import type { BrowserTab } from '@/lib/browserTypes'

export function openMarkdownPreview(tab: BrowserTab) {
  return tab.content.includes('# ') ? 'rich' : 'plain'
}
\`\`\`

### YAML

\`\`\`yaml
project: {ProjectName}
gateway:
  port: 18642
crew:
  - workframe-agent
  - architect
\`\`\`

### Shell

\`\`\`bash
npm run build:meta
# hard refresh http://127.0.0.1:18644
\`\`\`

---

## Definition list

<dl>
  <dt>Atmosphere</dt>
  <dd>Full-bleed gradient + grid behind transparent panels.</dd>
  <dt>Browser panel</dt>
  <dd>Netscape-style chrome with tabs, URL bar, and mode toolbar.</dd>
  <dt>Markdown preview</dt>
  <dd>GFM via <code>marked</code> + <code>markdown.css</code> + hljs for fences.</dd>
</dl>

---

## Details / callouts

<details>
  <summary>What gets styled?</summary>

  Headings **h1–h6**, paragraphs, emphasis, links, lists (including tasks), blockquotes, rules, tables, images, \`inline code\`, fenced blocks, \`kbd\`, \`mark\`, sub/sup, abbreviations, definition lists, address, figure/figcaption, details/summary, and HTML callout boxes.

</details>

<div class="wf-md-callout wf-md-callout--note">
  <p class="wf-md-callout__title">Note</p>
  <p>Preview padding is intentionally generous — <strong>48–72px</strong> vertical and up to <strong>64px</strong> horizontal — so long docs breathe on wide panels.</p>
</div>

<div class="wf-md-callout wf-md-callout--warn">
  <p class="wf-md-callout__title">Warning</p>
  <p>Binary and office formats still route to the unsupported view until conversion or download actions exist.</p>
</div>

---

## Address block

<address>
  <strong>{ProjectName}</strong><br />
  Local dev: <code>http://127.0.0.1:18644</code><br />
  Mounts: <code>Agents/</code> → <code>/opt/data</code>, <code>Files/</code> → <code>/workspace</code>
</address>

---

#### Meta heading level four

##### Meta heading level five

###### Meta heading level six

---

*Last updated: dogfood session — flip preview ↔ code ↔ edit to compare raw and rendered markdown.*
`,
  'website-index-html': `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Workframe Preview</title>
    <link rel="stylesheet" href="styles/globals.css" />
  </head>
  <body>
    <main class="shell">
      <p class="eyebrow">Browser preview</p>
      <h1>Hello from index.html</h1>
      <p>This page is rendered inside the Workframe browser panel.</p>
    </main>
  </body>
</html>
`,
  'website-styles-globals-css': `:root {
  color-scheme: dark;
  --bg: #0a0a0f;
  --text: #e8e8ee;
  --accent: #7c3aed;
}

body {
  margin: 0;
  font-family: "Inter Tight", system-ui, sans-serif;
  background: radial-gradient(circle at top, #1a1033, var(--bg));
  color: var(--text);
}

.shell {
  min-height: 100vh;
  display: grid;
  place-content: center;
  gap: 12px;
  padding: 48px;
}

.eyebrow {
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-size: 11px;
  color: #0e7490;
}

h1 {
  margin: 0;
  font-size: clamp(32px, 5vw, 48px);
}
`,
  'assets-logo-svg': SVG_LOGO,
  'assets-hero-png': PNG_PLACEHOLDER,
  'assets-data-csv': `name,role,status
Workframe Agent,orchestrator,active
Architect,specialist,idle
Docs,specialist,active
`,
  'assets-demo-webm': 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.webm',
  'assets-demo-mp3': 'https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3',
  'assets-guide-pdf': 'https://mozilla.github.io/pdf.js/web/compressed.tracemonkey-pldi-09.pdf',
  dockerfile: `FROM node:22-alpine
WORKDIR /workspace
COPY package*.json ./
RUN npm ci
COPY . .
CMD ["npm", "run", "dev"]
`,
  'env-example': `VITE_WORKFRAME_PROJECT={ProjectName}
WORKFRAME_GATEWAY_PORT=18642
WORKFRAME_DASHBOARD_PORT=19119
`,
  'config-app-yml': `project: {ProjectName}
gateway:
  port: 18642
crew:
  - workframe-agent
  - architect
  - dev
`,
  'config-settings-toml': `[project]
name = "{ProjectName}"

[gateway]
port = 18642
`,
  'scripts-setup-py': `#!/usr/bin/env python3
"""Bootstrap helpers for {ProjectName}."""

def main() -> None:
    print("Workframe setup stub")

if __name__ == "__main__":
    main()
`,
  'scripts-deploy-sh': `#!/usr/bin/env bash
set -euo pipefail
echo "Deploy {ProjectName} UI"
npm run build:meta
`,
  'scripts-app-js': `export function greet(name) {
  return \`Hello from \${name}\`
}

console.log(greet("{ProjectName}"))
`,
  'scripts-query-sql': `-- Recent sessions (dogfood)
SELECT profile, COUNT(*) AS sessions
FROM messages
GROUP BY profile
ORDER BY sessions DESC;
`,
  'logs-gateway-log': `[2026-05-30T12:01:04Z] gateway started
[2026-05-30T12:01:06Z] telegram connected
[2026-05-30T12:04:19Z] session opened: workframe-agent
`,
}

function seedArtifacts(projectName: string) {
  if (artifactStore.size > 0) return

  for (const [id, content] of Object.entries(SEED)) {
    artifactStore.set(
      id,
      content.replaceAll('{ProjectName}', projectName).replaceAll('Workframe', projectName),
    )
  }
}

export function getArtifactContent(fileId: string, projectName: string): string {
  seedArtifacts(projectName)
  return artifactStore.get(fileId) ?? `// Empty artifact for ${fileId}\n`
}

export function saveArtifactContent(fileId: string, content: string) {
  artifactStore.set(fileId, content)
}

export function isBinaryPreview(fileName: string) {
  const ext = fileName.split('.').pop()?.toLowerCase() ?? ''
  return ['png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'webm', 'mp3', 'wav', 'pdf'].includes(ext)
}

export function isMediaUrl(content: string) {
  return /^https?:\/\//i.test(content.trim())
}
