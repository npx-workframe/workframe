import { toast } from 'sonner'

import { WorkframeErrorToast } from '@/components/ui/WorkframeErrorToast'
import type { WorkframeNoticeAction, WorkframeNoticeInfo } from '@/lib/workframeErrors'

type ShowWorkframeErrorOptions = {
  id?: string
  authorName?: string
  avatarUrl?: string | null
  onAction?: (action: WorkframeNoticeAction) => void
  durationMs?: number
}

export function showWorkframeError(notice: WorkframeNoticeInfo, options?: ShowWorkframeErrorOptions) {
  const toastId = options?.id ?? notice.code ?? `wf-error-${Date.now()}`
  toast.custom(
    (id) => (
      <WorkframeErrorToast
        notice={notice}
        authorName={options?.authorName ?? 'Workframe'}
        avatarUrl={options?.avatarUrl}
        onAction={options?.onAction}
        onDismiss={() => toast.dismiss(id)}
      />
    ),
    {
      id: toastId,
      duration: options?.durationMs ?? 10_000,
      className: 'wf-toast-host',
    },
  )
}

export function dismissWorkframeError(id?: string) {
  if (id) toast.dismiss(id)
  else toast.dismiss()
}
