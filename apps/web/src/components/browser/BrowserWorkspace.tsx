import { BrowserChrome } from '@/components/browser/BrowserChrome'
import { BrowserCodeView } from '@/components/browser/BrowserCodeView'
import { BrowserEditView } from '@/components/browser/BrowserEditView'
import { BrowserNavigateView } from '@/components/browser/BrowserNavigateView'
import { BrowserNativeViewBridge } from '@/components/browser/BrowserNativeViewBridge'
import { BrowserPreviewView } from '@/components/browser/BrowserPreviewView'
import { BrowserTabBar } from '@/components/browser/BrowserTabBar'
import { useBrowserWorkspace } from '@/contexts/BrowserWorkspaceContext'
import { isElectronRuntime } from '@/lib/runtime'

export function BrowserWorkspace() {
  const { activeTab } = useBrowserWorkspace()
  const useNativeWebview = isElectronRuntime()

  return (
    <div className="wf-browser">
      <BrowserTabBar />
      <BrowserChrome />

      <div className="wf-browser__viewport">
        {!activeTab ? (
          <div className="wf-browser__empty">
            <p className="wf-browser__empty-title">Browser</p>
            <p className="wf-browser__empty-body">
              Select a file in the explorer or paste a URL into the address bar.
            </p>
          </div>
        ) : null}

        {activeTab?.mode === 'preview' ? <BrowserPreviewView tab={activeTab} /> : null}
        {activeTab?.mode === 'code' ? <BrowserCodeView tab={activeTab} /> : null}
        {activeTab?.mode === 'edit' ? <BrowserEditView tab={activeTab} /> : null}
        {activeTab?.mode === 'navigate'
          ? useNativeWebview
            ? <BrowserNativeViewBridge tab={activeTab} />
            : <BrowserNavigateView tab={activeTab} />
          : null}
      </div>
    </div>
  )
}
