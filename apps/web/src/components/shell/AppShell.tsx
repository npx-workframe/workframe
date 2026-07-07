import type { ReactNode } from 'react'

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
      <main className={mainFill ? 'wf-shell__main wf-shell__main--fill' : 'wf-shell__main'}>
        {children}
      </main>
    </div>
  )
}
