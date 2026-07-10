import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { WfActionButton } from '@/components/ui/WfActionButton'
import { DeviceCodeOAuthPanel } from '@/components/integrations/DeviceCodeOAuthPanel'
import { useDeviceCodeOAuth } from '@/hooks/useDeviceCodeOAuth'
import type { ProviderConnectRow } from '@/lib/workframeAuthApi'

export type DeviceCodeOAuthPresentation = 'dialog' | 'inline'

export type DeviceCodeOAuthFlowProps = {
  row: ProviderConnectRow | null
  workspaceId?: string
  active: boolean
  presentation?: DeviceCodeOAuthPresentation
  /** When false, errors stay in the panel (avoids duplicate notices in settings sheets). */
  reportToParent?: boolean
  onActiveChange?: (active: boolean) => void
  onConnected?: () => void
  onError?: (message: string) => void
}

/**
 * Single device-code OAuth surface — shared by wizard, settings sheets, and chat modals.
 * Use `inline` when the parent is already a Dialog (avoids nested modal bleed-through).
 */
export function DeviceCodeOAuthFlow({
  row,
  workspaceId,
  active,
  presentation = 'dialog',
  reportToParent,
  onActiveChange,
  onConnected,
  onError,
}: DeviceCodeOAuthFlowProps) {
  const bubbleErrors = reportToParent ?? presentation === 'dialog'
  const oauth = useDeviceCodeOAuth({
    providerId: row?.id ?? '',
    providerLabel: row?.label ?? 'Provider',
    workspaceId,
    active: active && Boolean(row),
    onConnected,
    onError: bubbleErrors ? onError : undefined,
  })

  if (!row || !active) return null

  const panel = (
    <DeviceCodeOAuthPanel
      providerId={row.id}
      providerLabel={row.label}
      verificationUri={oauth.verificationUri}
      userCode={oauth.userCode}
      status={oauth.status}
      message={oauth.message}
      copied={oauth.copied}
      presentation={presentation}
      onCopyCode={() => void oauth.copyCode()}
      onCancel={
        presentation === 'inline'
          ? () => onActiveChange?.(false)
          : undefined
      }
    />
  )

  if (presentation === 'inline') {
    return panel
  }

  return (
    <Dialog open={active} onOpenChange={(next) => onActiveChange?.(next)}>
      <DialogContent
        className="wf-auth-dialog wf-dialog-content--device-oauth"
        overlayClassName="wf-dialog-overlay--opaque"
      >
        <DialogHeader>
          <DialogTitle>Connect {row.label}</DialogTitle>
        </DialogHeader>
        {panel}
        <DialogFooter>
          <WfActionButton wizardSize onClick={() => onActiveChange?.(false)}>
            {oauth.status === 'connected' ? 'Done' : 'Cancel'}
          </WfActionButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
