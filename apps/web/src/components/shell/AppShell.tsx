import type { ReactNode } from 'react'

import { AtmosphereBackground } from '@/components/shell/AtmosphereBackground'

type AppShellProps = {
  projectName?: string
  subtitle?: string
  brandLogoUrl?: string
  headerActions?: ReactNode
  mainFill?: boolean
  footerStatus?: string
  children?: ReactNode
}

export function AppShell({
  mainFill = false,
  children,
}: AppShellProps) {
  return (
    <div className="wf-shell wf-shell--chromeless">
      <AtmosphereBackground />

      <main className={mainFill ? 'wf-shell__main wf-shell__main--fill' : 'wf-shell__main'}>
        {children}
      </main>
    </div>
  )
}
