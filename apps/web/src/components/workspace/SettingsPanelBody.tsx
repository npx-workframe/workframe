import type { ReactNode } from 'react'

import { WorkframeNotice, WorkframeStatusNotice } from '@/components/ui/WorkframeNotice'
import { WizardSubtabs, type WizardSubtab } from '@/components/workspace/WizardSubtabs'
import { cn } from '@/lib/utils'

export type SettingsPanelBodyProps = {
  children: ReactNode
  className?: string
  /** Shell-owned error — omit when an embedded composable owns its own notice surface. */
  error?: string | null
  status?: string | null
  tabs?: readonly WizardSubtab[]
  activeTab?: string
  onTabChange?: (tabId: string) => void
  tablistLabel?: string
  compact?: boolean
  authOtp?: boolean
  /** Skip wf-wizard-panel wrapper — for fill layouts or bare grids. */
  bare?: boolean
}

/**
 * Standard settings / wizard panel shell: optional notices, wizard chrome, optional subtabs.
 * Composables (ProviderConnectPanel, ModelPickerPanel, DeviceCodeOAuthFlow, …) render inside.
 */
export function SettingsPanelBody({
  children,
  className,
  error,
  status,
  tabs,
  activeTab,
  onTabChange,
  tablistLabel = 'Sections',
  compact,
  authOtp,
  bare,
}: SettingsPanelBodyProps) {
  const showTabs = tabs?.length && activeTab && onTabChange

  const panel = (
    <>
      {showTabs ? (
        <WizardSubtabs
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={onTabChange}
          ariaLabel={tablistLabel}
        />
      ) : null}
      {children}
    </>
  )

  return (
    <div className="wf-settings-panel-body space-y-4" role="tabpanel">
      {error ? <WorkframeNotice message={error} /> : null}
      {status ? <WorkframeStatusNotice message={status} /> : null}

      {bare ? (
        panel
      ) : (
        <div
          className={cn(
            'wf-wizard-panel wf-onboarding-form',
            compact && 'wf-onboarding-compact',
            authOtp && 'wf-wizard-panel--auth-otp',
            className,
          )}
        >
          {panel}
        </div>
      )}
    </div>
  )
}
