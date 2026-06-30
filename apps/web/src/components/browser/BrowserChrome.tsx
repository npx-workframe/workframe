import { useEffect, useState } from 'react'

import {
  ArrowLeft,
  Code2,
  Eye,
  Pencil,
  Redo2,
  RefreshCw,
  Save,
} from 'lucide-react'

import { useBrowserChromeState, useBrowserWorkspace } from '@/contexts/BrowserWorkspaceContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

export function BrowserChrome() {
  const {
    activeTab,
    activeTabId,
    commitLocation,
    openUrl,
    goBack,
    reloadTab,
    setTabMode,
    undoEdit,
    saveTab,
  } = useBrowserWorkspace()

  const chrome = useBrowserChromeState(activeTab)
  const [draftLocation, setDraftLocation] = useState(activeTab?.location ?? '')

  useEffect(() => {
    setDraftLocation(activeTab?.location ?? '')
  }, [activeTab?.location, activeTabId])

  const submitLocation = () => {
    if (activeTabId) {
      commitLocation(activeTabId, draftLocation)
      return
    }
    const trimmed = draftLocation.trim()
    if (!trimmed) return
    openUrl(trimmed)
  }

  return (
    <TooltipProvider delayDuration={400}>
      <div className="wf-browser-chrome">
        <div className="wf-browser-chrome__toolbar">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="toolbar"
                size="toolbarIcon"
                disabled={!activeTabId || !chrome.canBack}
                onClick={goBack}
                aria-label="Back"
              >
                <ArrowLeft aria-hidden="true" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Back</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="toolbar"
                size="toolbarIcon"
                disabled={!activeTabId || !chrome.canReload}
                onClick={() => activeTabId && reloadTab(activeTabId)}
                aria-label="Reload"
              >
                <RefreshCw aria-hidden="true" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Reload</TooltipContent>
          </Tooltip>

          <Input
            className="wf-browser-chrome__address"
            value={draftLocation}
            onChange={(event) => setDraftLocation(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                submitLocation()
              }
            }}
            placeholder="File path or URL"
            aria-label="File path or URL"
            spellCheck={false}
          />

          <div className="wf-browser-chrome__modes">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="toolbar"
                  size="toolbarIcon"
                  className={cn(activeTab?.mode === 'preview' && 'wf-tool-btn--active')}
                  disabled={!activeTabId || !chrome.canPreview}
                  onClick={() => activeTabId && setTabMode(activeTabId, 'preview')}
                  aria-label="Preview mode"
                >
                  <Eye aria-hidden="true" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Preview</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="toolbar"
                  size="toolbarIcon"
                  className={cn(activeTab?.mode === 'code' && 'wf-tool-btn--active')}
                  disabled={!activeTabId || !chrome.canCode}
                  onClick={() => activeTabId && setTabMode(activeTabId, 'code')}
                  aria-label="Code view"
                >
                  <Code2 aria-hidden="true" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Code view</TooltipContent>
            </Tooltip>
          </div>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="toolbar"
                size="toolbarIcon"
                className={cn(activeTab?.mode === 'edit' && 'wf-tool-btn--active')}
                disabled={!activeTabId || !chrome.canEdit}
                onClick={() => activeTabId && setTabMode(activeTabId, 'edit')}
                aria-label="Edit mode"
              >
                <Pencil aria-hidden="true" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Edit</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="toolbar"
                size="toolbarIcon"
                disabled={!activeTabId || !chrome.canUndo}
                onClick={() => activeTabId && undoEdit(activeTabId)}
                aria-label="Undo"
              >
                <Redo2 className="scale-x-[-1]" aria-hidden="true" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Undo</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="toolbar"
                size="toolbarIcon"
                className={cn(chrome.isDirty && 'wf-tool-btn--emphasis')}
                disabled={!activeTabId || !chrome.canSave}
                onClick={() => activeTabId && saveTab(activeTabId)}
                aria-label="Save"
              >
                <Save aria-hidden="true" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{chrome.isDirty ? 'Save changes' : 'Saved'}</TooltipContent>
          </Tooltip>
        </div>
      </div>
    </TooltipProvider>
  )
}
