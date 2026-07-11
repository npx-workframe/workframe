import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { WorkframeNoticeInfo, WorkframeNoticeTone } from '@/lib/workframeErrors'
import { formatWorkframeError, noticeMessage } from '@/lib/workframeErrors'

type WorkframeNoticeProps = {
  info?: WorkframeNoticeInfo | null
  message?: string | null
  tone?: WorkframeNoticeTone
  className?: string
  role?: 'status' | 'alert'
  actionLabel?: string
  onAction?: () => void
}

function resolveInfo(props: WorkframeNoticeProps): WorkframeNoticeInfo | null {
  if (props.info) {
    const text = props.info.message?.trim()
    if (!text) return null
    return props.info
  }
  const message = props.message?.trim()
  if (!message) return null
  return formatWorkframeError(message)
}

function splitNoticeMessage(message: string): { title?: string; body: string } {
  const match = message.match(/^([^:]{2,48}):\s+(.+)$/s)
  if (!match) return { body: message }
  return { title: match[1].trim(), body: match[2].trim() }
}

const HIDDEN_CODES = new Set(['forbidden', 'no_session', 'unauthorized', 'install_closed'])

export function WorkframeNotice({
  info,
  message,
  tone,
  className,
  role = 'alert',
  actionLabel,
  onAction,
}: WorkframeNoticeProps) {
  const resolved = resolveInfo({ info, message, tone })
  if (!resolved) return null
  const resolvedTone = tone ?? resolved.tone
  const label = actionLabel ?? resolved.actionLabel
  const action = onAction
  const { title, body } = splitNoticeMessage(resolved.message)
  const showTitle = Boolean(title && (resolved.hint || body !== resolved.message))
  const showCode =
    resolved.code &&
    !HIDDEN_CODES.has(resolved.code) &&
    !resolved.code.startsWith('http_') &&
    !resolved.hint

  return (
    <div
      className={cn('wf-notice', `wf-notice--${resolvedTone}`, className)}
      role={role}
      aria-live="polite"
    >
      {showTitle ? <p className="wf-notice__title">{title}</p> : null}
      <p className="wf-notice__message">{showTitle ? body : resolved.message}</p>
      {resolved.hint ? <p className="wf-notice__hint">{resolved.hint}</p> : null}
      {label && action ? (
        <div className="wf-notice__actions">
          <Button type="button" size="sm" variant="outline" onClick={action}>
            {label}
          </Button>
        </div>
      ) : null}
      {showCode ? <p className="wf-notice__code">{resolved.code}</p> : null}
    </div>
  )
}

export function WorkframeStatusNotice({
  message,
  className,
}: {
  message?: string | null
  className?: string
}) {
  const text = message?.trim()
  if (!text) return null
  return (
    <p className={cn('wf-notice wf-notice--status', className)} role="status">
      {text}
    </p>
  )
}

export { noticeMessage }
