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
  if (props.info) return props.info
  const message = props.message?.trim()
  if (!message) return null
  return formatWorkframeError(message)
}

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

  return (
    <div
      className={cn('wf-notice', `wf-notice--${resolvedTone}`, className)}
      role={role}
      aria-live="polite"
    >
      <p className="wf-notice__message">{resolved.message}</p>
      {resolved.hint ? <p className="wf-notice__hint">{resolved.hint}</p> : null}
      {label && action ? (
        <div className="wf-notice__actions">
          <Button type="button" size="sm" variant="outline" onClick={action}>
            {label}
          </Button>
        </div>
      ) : null}
      {resolved.code && resolved.code.startsWith('http_') ? null : resolved.code ? (
        <p className="wf-notice__code">{resolved.code}</p>
      ) : null}
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
