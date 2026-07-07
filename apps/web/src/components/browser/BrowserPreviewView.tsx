import { useMemo } from 'react'

import { BrowserUnsupportedView } from '@/components/browser/BrowserUnsupportedView'
import { MarkdownContent } from '@/components/markdown/MarkdownContent'
import { MermaidDiagram } from '@/components/markdown/MermaidDiagram'
import { MarkdownHtml } from '@/components/markdown/MarkdownHtml'
import { safeHtml } from '@/lib/safeHtml'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { BrowserTab } from '@/lib/browserTypes'
import { getFileCapability } from '@/lib/fileCapabilities'
import { workspaceFileServeUrl } from '@/lib/filesApi'
import { isMediaUrl } from '@/lib/mockBrowserArtifacts'
import {
  renderCsvPreview,
  renderPlainTextPreview,
  renderTsvPreview,
} from '@/lib/renderMarkdown'
import { cn } from '@/lib/utils'

type BrowserPreviewViewProps = {
  tab: BrowserTab
}

export function BrowserPreviewView({ tab }: BrowserPreviewViewProps) {
  const capability = getFileCapability(tab.title)
  const ext = tab.title.split('.').pop()?.toLowerCase() ?? ''

  const markdownText = useMemo(() => {
    if (capability.unsupported) return null
    if (tab.source === 'content') return tab.content
    if (ext === 'md' || ext === 'mdx') return tab.content
    return null
  }, [capability.unsupported, ext, tab.content, tab.source])

  const mermaidSource = useMemo(() => {
    if (capability.unsupported) return null
    if (ext === 'mmd' || ext === 'mermaid') return tab.content
    return null
  }, [capability.unsupported, ext, tab.content])

  const html = useMemo(() => {
    if (capability.unsupported) return ''
    if (markdownText !== null || mermaidSource !== null) return ''
    if (ext === 'csv') {
      return renderCsvPreview(tab.content)
    }
    if (ext === 'tsv') {
      return renderTsvPreview(tab.content)
    }
    if (ext === 'txt' || ext === 'log') {
      return renderPlainTextPreview(tab.content)
    }
    if (ext === 'html' || ext === 'htm') {
      return tab.content
    }
    if (ext === 'json') {
      try {
        return `<div class="wf-browser-preview__surface"><pre class="wf-browser-preview__json">${escapeHtml(JSON.stringify(JSON.parse(tab.content), null, 2))}</pre></div>`
      } catch {
        return `<div class="wf-browser-preview__surface"><pre class="wf-browser-preview__json">${escapeHtml(tab.content)}</pre></div>`
      }
    }
    return ''
  }, [capability.unsupported, ext, markdownText, mermaidSource, tab.content])

  if (capability.unsupported) {
    return <BrowserUnsupportedView tab={tab} />
  }

  if (isMediaUrl(tab.content)) {
    if (capability.mimeType.startsWith('video/')) {
      return (
        <ScrollArea className="wf-browser-pane wf-browser-preview wf-browser-preview--media">
          <video className="wf-browser-preview__media" controls src={tab.content} />
        </ScrollArea>
      )
    }
    if (capability.mimeType.startsWith('audio/')) {
      return (
        <ScrollArea className="wf-browser-pane wf-browser-preview wf-browser-preview--media">
          <audio className="wf-browser-preview__audio" controls src={tab.content} />
        </ScrollArea>
      )
    }
    if (ext === 'pdf') {
      return (
        <ScrollArea className="wf-browser-pane wf-browser-preview wf-browser-preview--embed">
          <iframe
            className="wf-browser-preview__frame wf-browser-preview__frame--pdf"
            src={tab.content}
            title={tab.title}
          />
        </ScrollArea>
      )
    }
    if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) {
      return (
        <ScrollArea className="wf-browser-pane wf-browser-preview wf-browser-preview--media">
          <img className="wf-browser-preview__image" src={tab.content} alt={tab.title} />
        </ScrollArea>
      )
    }
  }

  if (ext === 'svg') {
    return (
      <ScrollArea className="wf-browser-pane wf-browser-preview wf-browser-preview--media wf-browser-preview--svg">
        <div dangerouslySetInnerHTML={{ __html: safeHtml(tab.content) }} />
      </ScrollArea>
    )
  }

  if (ext === 'html' || ext === 'htm') {
    return (
      <div className="wf-browser-pane wf-browser-preview wf-browser-preview--embed">
        <iframe
          key={tab.reloadNonce}
          className="wf-browser-preview__frame wf-browser-preview__frame--html"
          src={tab.source === 'file' ? workspaceFileServeUrl(tab.location) : undefined}
          srcDoc={tab.source === 'file' ? undefined : tab.content}
          title={tab.title}
          allow="fullscreen; autoplay; clipboard-read; clipboard-write; gamepad"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-pointer-lock allow-modals"
        />
      </div>
    )
  }

  if (mermaidSource !== null) {
    return (
      <ScrollArea
        className={cn(
          'wf-browser-pane wf-browser-preview wf-browser-preview--flush wf-browser-preview--rich',
          'wf-browser-preview--mermaid',
        )}
      >
        <div className="wf-browser-preview__surface wf-browser-preview--mermaid">
          <MermaidDiagram source={mermaidSource} />
        </div>
      </ScrollArea>
    )
  }

  if (markdownText !== null) {
    return (
      <ScrollArea
        className={cn(
          'wf-browser-pane wf-browser-preview wf-browser-preview--flush wf-browser-preview--rich',
          `wf-browser-preview--${ext}`,
        )}
      >
        <MarkdownContent
          text={markdownText}
          className="wf-browser-preview__surface"
          wrapperClass="wf-markdown"
        />
      </ScrollArea>
    )
  }

  return (
    <ScrollArea
      className={cn(
        'wf-browser-pane wf-browser-preview wf-browser-preview--flush wf-browser-preview--rich',
        `wf-browser-preview--${ext}`,
      )}
    >
      <MarkdownHtml
        className="wf-browser-preview__surface"
        html={html}
      />
    </ScrollArea>
  )
}

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
}
