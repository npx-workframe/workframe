import { Plus, X } from 'lucide-react'

import { useBrowserWorkspace } from '@/contexts/BrowserWorkspaceContext'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

export function BrowserTabBar() {
  const { tabs, activeTabId, selectTab, closeTab, openNewTab } = useBrowserWorkspace()

  return (
    <ScrollArea axis="horizontal" className="wf-browser-tabs" role="tablist" aria-label="Open files">
      {tabs.map((tab) => {
        const isActive = tab.id === activeTabId
        const isDirty = tab.source === 'file' && tab.content !== tab.savedContent

        return (
          <div
            key={tab.id}
            className={cn('wf-browser-tabs__tab', isActive && 'wf-browser-tabs__tab--active')}
            role="tab"
            aria-selected={isActive}
          >
            <button
              type="button"
              className="wf-browser-tabs__label"
              onClick={() => selectTab(tab.id)}
            >
              {isDirty ? `${tab.title} •` : tab.title}
            </button>
            <button
              type="button"
              className="wf-browser-tabs__close"
              onClick={() => closeTab(tab.id)}
              aria-label={`Close ${tab.title}`}
            >
              <X aria-hidden="true" />
            </button>
          </div>
        )
      })}
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="wf-browser-tabs__add"
        onClick={openNewTab}
        aria-label="New tab"
      >
        <Plus aria-hidden="true" />
      </Button>
    </ScrollArea>
  )
}
