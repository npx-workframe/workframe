import type { ReactNode } from 'react'

import { DialogFrame } from '@/components/dialogs/DialogFrame'
import { ThemeSwitcher } from '@/components/shell/ThemeSwitcher'
import { isElectronRuntime } from '@/lib/runtime'

export function OnboardingAuthGate({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <div className="wf-onboarding-page wf-onboarding-page--gate">
      <DialogFrame
        open
        modal={!isElectronRuntime()}
        onOpenChange={() => {}}
        title={title}
        description={description}
        headerActions={<ThemeSwitcher />}
        showClose={false}
        contentClassName="wf-auth-dialog"
      >
        {children}
      </DialogFrame>
    </div>
  )
}
