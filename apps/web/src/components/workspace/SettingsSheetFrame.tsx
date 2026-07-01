import type { ReactNode } from 'react'
import { useMemo } from 'react'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

type SettingsTab = {
  id: string
  label: string
}

const SOLO_SECTION_ID = '__section'

type SettingsSheetFrameProps = {
  open: boolean
  onClose: () => void
  title?: string
  /** Solo-rail nav label when `tabs` is omitted — defaults to `title`. */
  sectionLabel?: string
  summary?: string
  titleId?: string
  tabs?: SettingsTab[]
  activeTab?: string
  onTabChange?: (tabId: string) => void
  footer?: ReactNode
  /** Primary actions pinned above the loading bar in the main column. */
  actions?: ReactNode
  /** Indeterminate bar pinned to the bottom of the main (right) column. */
  loading?: boolean
  /** Single inner scroll region (e.g. embedded model list) — outer shell does not scroll. */
  contentFill?: boolean
  sheetClassName?: string
  children: ReactNode
}

export function SettingsSheetFrame({
  open,
  onClose,
  title,
  sectionLabel,
  summary,
  titleId = 'wf-settings-sheet-title',
  tabs,
  activeTab,
  onTabChange,
  footer,
  actions,
  loading = false,
  contentFill = false,
  sheetClassName,
  children,
}: SettingsSheetFrameProps) {
  const shellTitle = title || 'Settings'
  const soloRail = !tabs?.length
  const effectiveTabs = useMemo(
    () =>
      tabs?.length
        ? tabs
        : [{ id: SOLO_SECTION_ID, label: sectionLabel?.trim() || shellTitle }],
    [sectionLabel, shellTitle, tabs],
  )
  const effectiveActiveTab = activeTab ?? effectiveTabs[0]?.id
  const panelTitle =
    effectiveTabs.find((tab) => tab.id === effectiveActiveTab)?.label || shellTitle

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) onClose() }}>
      <DialogContent
        showClose
        className={cn(
          'wf-dialog-content--settings-shell',
          contentFill && 'wf-dialog-content--settings-fill',
          sheetClassName,
        )}
      >
        <aside className="wf-settings-shell__rail">
          <div className="wf-settings-shell__rail-head">
            <h2 className="wf-settings-shell__rail-title">{shellTitle}</h2>
          </div>
          <nav className="wf-settings-shell__nav" role="tablist" aria-label="Settings sections">
            {effectiveTabs.map((tab) =>
              soloRail ? (
                <span
                  key={tab.id}
                  role="tab"
                  aria-selected
                  className="wf-settings-shell__nav-btn wf-settings-shell__nav-btn--solo"
                >
                  {tab.label}
                </span>
              ) : (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={effectiveActiveTab === tab.id}
                  className="wf-settings-shell__nav-btn"
                  onClick={() => onTabChange?.(tab.id)}
                >
                  {tab.label}
                </button>
              ),
            )}
          </nav>
          {footer ? <div className="wf-settings-shell__rail-footer">{footer}</div> : null}
        </aside>

        <div className="wf-settings-shell__main">
          <header className="wf-settings-shell__header">
            <div>
              <DialogTitle id={titleId}>{panelTitle}</DialogTitle>
              {summary ? <DialogDescription>{summary}</DialogDescription> : null}
            </div>
          </header>

          <ScrollArea
            axis="vertical"
            className={cn('wf-settings-shell__scroll', contentFill && 'wf-settings-shell__scroll--fill')}
          >
            <div className={cn('wf-settings-shell__body', contentFill && 'wf-settings-shell__body--fill')}>
              {children}
            </div>
          </ScrollArea>

          {actions ? <div className="wf-settings-shell__actions">{actions}</div> : null}

          {loading ? (
            <div
              className="wf-settings-shell__load-footer"
              role="status"
              aria-live="polite"
              aria-busy="true"
              aria-label="Loading settings"
            >
              <div className="wf-settings-shell__load-track" role="progressbar" aria-valuemin={0} aria-valuemax={100}>
                <div className="wf-settings-shell__load-bar" />
              </div>
            </div>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  )
}
