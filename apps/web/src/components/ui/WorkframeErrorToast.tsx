import { X } from 'lucide-react'

import { AgentAvatar } from '@/components/ui/AgentAvatar'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
import type { WorkframeNoticeAction, WorkframeNoticeInfo } from '@/lib/workframeErrors'
import { cn } from '@/lib/utils'

type WorkframeErrorToastProps = {
  notice: WorkframeNoticeInfo
  authorName?: string
  avatarUrl?: string | null
  onAction?: (action: WorkframeNoticeAction) => void
  onDismiss?: () => void
  className?: string
}

export function WorkframeErrorToast({
  notice,
  authorName = 'Workframe',
  avatarUrl,
  onAction,
  onDismiss,
  className,
}: WorkframeErrorToastProps) {
  return (
    <article className={cn('wf-toast-message', className)} role="alert" aria-live="polite">
      <div className="wf-toast-message__header">
        <AgentAvatar
          src={avatarUrl}
          name={authorName}
          size="sm"
          className="wf-toast-message__avatar"
        />
        <div className="wf-toast-message__meta">
          <span className="wf-toast-message__author">{authorName}</span>
          <span className="wf-toast-message__badge">System</span>
        </div>
        {onDismiss ? (
          <button type="button" className="wf-toast-message__close" onClick={onDismiss} aria-label="Dismiss">
            <X size={14} aria-hidden />
          </button>
        ) : null}
      </div>
      <WorkframeNotice
        info={notice}
        className="wf-toast-message__notice"
        onAction={
          notice.action && onAction
            ? () => onAction(notice.action!)
            : undefined
        }
      />
    </article>
  )
}
