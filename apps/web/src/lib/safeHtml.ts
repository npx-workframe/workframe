import DOMPurify from 'dompurify'

/** Sanitize agent-controlled HTML before innerHTML / srcDoc. */
export function safeHtml(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    FORBID_TAGS: ['style', 'form'],
    FORBID_ATTR: ['onerror', 'onload', 'onclick'],
  })
}
