import { isMermaidLang, mermaidSourceFromFence } from '@/lib/hydrateMermaid'

export type MarkdownBlock =
  | { kind: 'markdown'; text: string }
  | { kind: 'mermaid'; source: string }

const FENCE_RE = /```([^\n`]+)\r?\n([\s\S]*?)```/g

export function splitMarkdownBlocks(content: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = []
  let lastIndex = 0

  for (const match of content.matchAll(FENCE_RE)) {
    const full = match[0]
    const lang = match[1] ?? ''
    const body = match[2] ?? ''
    const index = match.index ?? 0
    const fenceLang = lang.trim().split(/\s+/)[0] ?? ''

    if (!isMermaidLang(fenceLang)) continue

    if (index > lastIndex) {
      blocks.push({ kind: 'markdown', text: content.slice(lastIndex, index) })
    }
    blocks.push({ kind: 'mermaid', source: mermaidSourceFromFence(lang, body) })
    lastIndex = index + full.length
  }

  if (lastIndex < content.length) {
    blocks.push({ kind: 'markdown', text: content.slice(lastIndex) })
  }

  if (blocks.length === 0) {
    blocks.push({ kind: 'markdown', text: content })
  }

  return blocks
}

// ponytail: runnable fence split — typed langs must become mermaid blocks
if (splitMarkdownBlocks('```gantt\ntitle A\n```').length !== 1) {
  throw new Error('splitMarkdownBlocks gantt fence failed')
}
