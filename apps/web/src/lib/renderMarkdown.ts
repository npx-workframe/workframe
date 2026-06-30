import { marked } from 'marked'

import { highlightCode } from '@/lib/highlightCode'
import { isMermaidLang, mermaidBlockHtml, mermaidSourceFromFence } from '@/lib/hydrateMermaid'
import { safeHtml } from '@/lib/safeHtml'

marked.setOptions({
  gfm: true,
  breaks: true,
})

marked.use({
  renderer: {
    code({ text, lang }) {
      const language = lang?.trim().split(/\s+/)[0] || 'plaintext'
      const safeLang = language.replace(/[^a-z0-9_-]/gi, '') || 'plaintext'
      if (isMermaidLang(safeLang)) {
        return mermaidBlockHtml(mermaidSourceFromFence(language, text))
      }
      const highlighted = highlightCode(text, safeLang)
      return `<pre class="wf-markdown__pre wf-scroll wf-scroll--both"><code class="hljs language-${safeLang}">${highlighted}</code></pre>\n`
    },
  },
})

export function renderMarkdownInner(content: string) {
  return safeHtml(marked.parse(content) as string)
}

export function renderMarkdown(content: string, wrapperClass = 'wf-markdown wf-syntax') {
  return `<article class="${wrapperClass}">${renderMarkdownInner(content)}</article>`
}

function renderCsvTable(rows: string[][]) {
  if (rows.length === 0) return '<p class="wf-browser-preview__empty">Empty CSV</p>'

  const [header, ...body] = rows
  const headHtml = header.map((cell) => `<th>${escapeHtml(cell)}</th>`).join('')
  const bodyHtml = body
    .map(
      (row) =>
        `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>`,
    )
    .join('')

  return `<table class="wf-browser-preview__table"><thead><tr>${headHtml}</tr></thead><tbody>${bodyHtml}</tbody></table>`
}

export function renderCsvPreview(content: string) {
  const rows = content
    .trim()
    .split('\n')
    .map((line) => line.split(',').map((cell) => cell.trim()))

  const table = renderCsvTable(rows)
  return `<div class="wf-browser-preview__surface wf-browser-preview__csv">${table}</div>`
}

export function renderTsvPreview(content: string) {
  const rows = content
    .trim()
    .split('\n')
    .map((line) => line.split('\t').map((cell) => cell.trim()))

  const table = renderCsvTable(rows)
  return `<div class="wf-browser-preview__surface wf-browser-preview__csv">${table}</div>`
}

export function renderMermaidPreview(content: string) {
  return `<div class="wf-browser-preview__surface wf-browser-preview--mermaid">${mermaidBlockHtml(content)}</div>`
}

export function renderPlainTextPreview(content: string) {
  return `<div class="wf-browser-preview__surface"><pre class="wf-browser-preview__plaintext">${escapeHtml(content)}</pre></div>`
}

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}
