export type BrowserMode = 'preview' | 'code' | 'edit' | 'navigate'

export type TabSource = 'file' | 'url' | 'content'

export type NavigationEntry = {
  location: string
  mode: BrowserMode
  source: TabSource
  fileId?: string
  title?: string
}

export type BrowserTab = {
  id: string
  title: string
  location: string
  source: TabSource
  fileId?: string
  mode: BrowserMode
  content: string
  savedContent: string
  undoStack: string[]
  undoIndex: number
  navigationStack: NavigationEntry[]
  navigationIndex: number
  /** Bumped to remount navigate/native views on reload. */
  reloadNonce: number
}

export type OpenFilePayload = {
  fileId: string
  fileName: string
  relativePath: string
}

export type OpenContentPayload = {
  id: string
  title: string
  content: string
  mode?: BrowserMode
}
