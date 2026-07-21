import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import type {
  BrowserMode,
  BrowserTab,
  NavigationEntry,
  OpenContentPayload,
  OpenFilePayload,
} from '@/lib/browserTypes'
import { getFileCapability, hasKnownFileCapability, isUrl } from '@/lib/fileCapabilities'
import {
  dedupeFileTabs,
  fileTabId,
  findFileTab,
} from '@/lib/browserTabUtils'
import {
  fetchFilesState,
  fetchFilesTree,
  getCachedFileContent,
  readFileByPath,
  refreshFileByPath,
  setCachedFileContent,
  writeFileByPath,
} from '@/lib/filesApi'
import { findFileNodeByPath, getRelativePathFromRoot } from '@/lib/fileTreeTypes'

type BrowserWorkspaceContextValue = {
  projectName: string
  tabs: BrowserTab[]
  activeTabId: string | null
  activeTab: BrowserTab | null
  openFile: (payload: OpenFilePayload) => void
  openContent: (payload: OpenContentPayload) => void
  openUrl: (url: string) => void
  openNewTab: () => void
  closeTab: (tabId: string) => void
  selectTab: (tabId: string) => void
  setTabMode: (tabId: string, mode: BrowserMode) => void
  setLocationDraft: (tabId: string, location: string) => void
  commitLocation: (tabId: string, location: string) => void
  goBack: () => void
  reloadTab: (tabId: string) => void
  updateTabContent: (tabId: string, content: string) => void
  undoEdit: (tabId: string) => void
  saveTab: (tabId: string) => void
}

const BrowserWorkspaceContext = createContext<BrowserWorkspaceContextValue | null>(null)

function createNavigationEntry(
  tab: Pick<BrowserTab, 'location' | 'mode' | 'source' | 'fileId' | 'title'>,
): NavigationEntry {
  return {
    location: tab.location,
    mode: tab.mode,
    source: tab.source,
    fileId: tab.fileId,
    title: tab.title,
  }
}

function resolveFileMode(capability: ReturnType<typeof getFileCapability>): BrowserMode {
  if (capability.unsupported) return 'preview'
  if (capability.previewable) return capability.defaultMode
  return 'code'
}

function createFileTab(
  payload: OpenFilePayload,
): BrowserTab {
  const capability = getFileCapability(payload.fileName)
  const content = ''
  const mode = resolveFileMode(capability)
  const tabId = fileTabId(payload.relativePath)

  const entry = createNavigationEntry({
    location: payload.relativePath,
    mode,
    source: 'file',
    fileId: payload.fileId,
    title: payload.fileName,
  })

  return {
    id: tabId,
    title: payload.fileName,
    location: payload.relativePath,
    source: 'file',
    fileId: payload.fileId,
    mode,
    content,
    savedContent: content,
    undoStack: [content],
    undoIndex: 0,
    navigationStack: [entry],
    navigationIndex: 0,
    reloadNonce: 0,
  }
}

function mergeOpenFileTab(
  existing: BrowserTab,
  payload: OpenFilePayload,
  cachedContent: string,
): BrowserTab {
  const tabId = fileTabId(payload.relativePath)
  const capability = getFileCapability(payload.fileName)
  const mode =
    existing.source === 'file' && existing.mode !== 'navigate'
      ? existing.mode
      : resolveFileMode(capability)

  return {
    ...existing,
    id: tabId,
    title: payload.fileName,
    location: payload.relativePath,
    source: 'file',
    fileId: payload.fileId,
    mode,
    content: existing.content || cachedContent,
    savedContent: existing.savedContent || cachedContent,
    undoStack: existing.undoStack.length ? existing.undoStack : [cachedContent],
    undoIndex: existing.undoIndex,
  }
}

function urlTabId(url: string) {
  return `url:${url}`
}

function urlTabLabel(url: string) {
  const base = typeof window !== 'undefined' ? window.location.href : 'http://127.0.0.1/'
  try {
    const parsed = new URL(url, base)
    if (parsed.pathname.includes('hermes-dashboard')) return 'Dashboard'
    return parsed.hostname || parsed.pathname.replace(/^\/+/, '') || url
  } catch {
    return url
  }
}

function normalizeBrowserUrl(input: string) {
  const trimmed = input.trim()
  if (!trimmed) return ''
  if (isUrl(trimmed) || trimmed.startsWith('/')) return trimmed
  const fileName = trimmed.replace(/\\/g, '/').split('/').at(-1) || trimmed
  if (
    trimmed.startsWith('./') ||
    trimmed.startsWith('../') ||
    trimmed.includes('\\') ||
    hasKnownFileCapability(fileName)
  ) {
    return trimmed.replace(/^\.\//, '')
  }
  const host = trimmed.split('/')[0]
  const hostLike =
    /^(?:localhost|\d{1,3}(?:\.\d{1,3}){3})(?::\d+)?$/i.test(host) ||
    /^[a-z0-9-]+(?:\.[a-z0-9-]+)+(?::\d+)?$/i.test(host)
  if (hostLike) {
    const normalizedHost = trimmed.replace(/^www\./i, '')
    return `https://${host.startsWith('localhost') ? normalizedHost : `www.${normalizedHost}`}`
  }
  return trimmed
}

function createUrlTab(url: string): BrowserTab {
  const title = urlTabLabel(url)
  const entry = createNavigationEntry({
    location: url,
    mode: 'navigate',
    source: 'url',
    title,
  })

  return {
    id: urlTabId(url),
    title,
    location: url,
    source: 'url',
    mode: 'navigate',
    content: '',
    savedContent: '',
    undoStack: [''],
    undoIndex: 0,
    navigationStack: [entry],
    navigationIndex: 0,
    reloadNonce: 0,
  }
}

function createContentTab(payload: OpenContentPayload): BrowserTab {
  const mode: BrowserMode = payload.mode ?? 'preview'
  return {
    id: payload.id,
    title: payload.title,
    location: payload.id,
    source: 'content',
    mode,
    content: payload.content,
    savedContent: payload.content,
    undoStack: [payload.content],
    undoIndex: 0,
    navigationStack: [],
    navigationIndex: -1,
    reloadNonce: 0,
  }
}

function createEmptyUrlTab(): BrowserTab {
  return {
    id: 'url:new',
    title: 'New Tab',
    location: '',
    source: 'url',
    mode: 'navigate',
    content: '',
    savedContent: '',
    undoStack: [''],
    undoIndex: 0,
    navigationStack: [],
    navigationIndex: -1,
    reloadNonce: 0,
  }
}

function reloadableFilePath(tab: BrowserTab) {
  const path = tab.location.trim()
  if (!path || isUrl(path)) return null
  if (tab.source === 'file') return path
  if (tab.source === 'content') return path
  return null
}

type BrowserWorkspaceProviderProps = {
  projectName: string
  children: ReactNode
}

export function BrowserWorkspaceProvider({ projectName, children }: BrowserWorkspaceProviderProps) {
  const [tabs, setTabs] = useState<BrowserTab[]>([])
  const [activeTabId, setActiveTabId] = useState<string | null>(null)
  const fileRevisionRef = useRef('')
  const tabsRef = useRef<BrowserTab[]>([])
  const bootstrappedRef = useRef(false)

  useEffect(() => {
    tabsRef.current = tabs
  }, [tabs])

  const activeTab = useMemo(
    () => tabs.find((tab) => tab.id === activeTabId) ?? null,
    [activeTabId, tabs],
  )

  const pushNavigation = useCallback((tab: BrowserTab, next: NavigationEntry) => {
    const trimmed = tab.navigationStack.slice(0, tab.navigationIndex + 1)
    trimmed.push(next)
    return { navigationStack: trimmed, navigationIndex: trimmed.length - 1 }
  }, [])

  const openFile = useCallback(
    (payload: OpenFilePayload) => {
      const tabId = fileTabId(payload.relativePath)
      const cachedContent = getCachedFileContent(payload.relativePath) ?? ''

      setTabs((previous) => {
        const existing = findFileTab(previous, payload.relativePath)
        if (existing) {
          const merged = mergeOpenFileTab(existing, payload, cachedContent)
          return dedupeFileTabs(
            previous.map((tab) => (tab.id === existing.id ? merged : tab)),
            payload.relativePath,
            tabId,
          )
        }
        return [
          ...previous,
          {
            ...createFileTab(payload),
            content: cachedContent,
            savedContent: cachedContent,
            undoStack: [cachedContent],
            undoIndex: 0,
          },
        ]
      })
      setActiveTabId(tabId)

      void refreshFileByPath(payload.relativePath).then((content) => {
        setTabs((previous) =>
          previous.map((tab) =>
            tab.id === tabId && tab.content === tab.savedContent
              ? {
                  ...tab,
                  content,
                  savedContent: content,
                  undoStack: [content],
                  undoIndex: 0,
                }
              : tab,
          ),
        )
      })
    },
    [],
  )

  const openUrl = useCallback((url: string) => {
    const normalized = normalizeBrowserUrl(url)
    if (!isUrl(normalized) && !normalized.startsWith('/')) return

    const id = urlTabId(normalized)
    setTabs((previous) => {
      if (previous.some((tab) => tab.id === id)) return previous
      return [...previous, createUrlTab(normalized)]
    })
    setActiveTabId(id)
  }, [])

  const openNewTab = useCallback(() => {
    setTabs((previous) => {
      if (previous.some((tab) => tab.id === 'url:new')) return previous
      return [...previous, createEmptyUrlTab()]
    })
    setActiveTabId('url:new')
  }, [])

  const openContent = useCallback((payload: OpenContentPayload) => {
    setTabs((previous) => {
      const existing = previous.find((tab) => tab.id === payload.id)
      if (existing) {
        return previous.map((tab) =>
          tab.id === payload.id
            ? { ...tab, title: payload.title, content: payload.content, savedContent: payload.content, mode: payload.mode ?? tab.mode }
            : tab,
        )
      }
      return [...previous, createContentTab(payload)]
    })
    setActiveTabId(payload.id)
  }, [])

  const closeTab = useCallback((tabId: string) => {
    setTabs((previous) => {
      const next = previous.filter((tab) => tab.id !== tabId)
      setActiveTabId((current) => {
        if (current !== tabId) return current
        if (next.length === 0) return null
        return next.at(-1)?.id ?? null
      })
      return next
    })
  }, [])

  const selectTab = useCallback((tabId: string) => {
    setActiveTabId(tabId)
  }, [])

  const setTabMode = useCallback(
    (tabId: string, mode: BrowserMode) => {
      setTabs((previous) =>
        previous.map((tab) => {
          if (tab.id !== tabId) return tab

          const nav = pushNavigation(tab, createNavigationEntry({ ...tab, mode }))
          return { ...tab, mode, ...nav }
        }),
      )
    },
    [pushNavigation],
  )

  const setLocationDraft = useCallback((tabId: string, location: string) => {
    setTabs((previous) =>
      previous.map((tab) => (tab.id === tabId ? { ...tab, location } : tab)),
    )
  }, [])

  const commitLocation = useCallback(
    (tabId: string, location: string) => {
      const trimmed = normalizeBrowserUrl(location)
      if (!trimmed) return

      if (isUrl(trimmed)) {
        const next = createUrlTab(trimmed)
        setTabs((previous) => [
          ...previous.filter((tab) => tab.id !== tabId && tab.id !== next.id),
          next,
        ])
        setActiveTabId(next.id)
        return
      }

      const relativePath = trimmed.replace(/\\/g, '/').replace(/^\.\//, '')
      const fileName = relativePath.split('/').at(-1) || relativePath
      const next = createFileTab({
        fileId: `path:${relativePath}`,
        fileName,
        relativePath,
      })
      const cached = getCachedFileContent(relativePath)
      if (cached != null) {
        next.content = cached
        next.savedContent = cached
        next.undoStack = [cached]
      }
      setTabs((previous) => [
        ...previous.filter((tab) => tab.id !== tabId && tab.id !== next.id),
        next,
      ])
      setActiveTabId(next.id)
      void refreshFileByPath(relativePath)
        .then((content) => {
          setTabs((previous) => previous.map((tab) =>
            tab.id === next.id && tab.content === tab.savedContent
              ? { ...tab, content, savedContent: content, undoStack: [content], undoIndex: 0 }
              : tab,
          ))
        })
        .catch(() => {
          // A missing relative path is a valid new editable file.
        })
    },
    [],
  )

  const goBack = useCallback(() => {
    if (!activeTabId) return

    setTabs((previous) =>
      previous.map((tab) => {
        if (tab.id !== activeTabId || tab.navigationIndex <= 0) return tab

        const nextIndex = tab.navigationIndex - 1
        const entry = tab.navigationStack[nextIndex]

        if (entry.source === 'url' && isUrl(entry.location)) {
          openUrl(entry.location)
          return tab
        }

        return {
          ...tab,
          navigationIndex: nextIndex,
          location: entry.location,
          mode: entry.mode,
          title: entry.title ?? tab.title,
          fileId: entry.fileId ?? tab.fileId,
        }
      }),
    )
  }, [activeTabId, openUrl])

  const reloadTab = useCallback((tabId: string) => {
    const tab = tabsRef.current.find((item) => item.id === tabId)
    if (!tab) return

    const filePath = reloadableFilePath(tab)
    if (filePath) {
      void refreshFileByPath(filePath)
        .then((content) => {
          setTabs((previous) =>
            previous.map((current) =>
              current.id === tabId
                ? {
                    ...current,
                    content,
                    savedContent: content,
                    undoStack: [content],
                    undoIndex: 0,
                  }
                : current,
            ),
          )
        })
        .catch(() => {
          // keep current tab content if refresh fails
        })
      return
    }

    if (tab.source === 'url' && tab.mode === 'navigate' && tab.location.trim()) {
      setTabs((previous) =>
        previous.map((current) =>
          current.id === tabId
            ? { ...current, reloadNonce: current.reloadNonce + 1 }
            : current,
        ),
      )
    }
  }, [])

  const updateTabContent = useCallback((tabId: string, content: string) => {
    const tab = tabsRef.current.find((item) => item.id === tabId)
    if (tab?.source === 'file') {
      setCachedFileContent(tab.location, content)
    }
    setTabs((previous) =>
      previous.map((tab) => {
        if (tab.id !== tabId) return tab

        const undoStack = tab.undoStack.slice(0, tab.undoIndex + 1)
        undoStack.push(content)

        return {
          ...tab,
          content,
          undoStack,
          undoIndex: undoStack.length - 1,
        }
      }),
    )
  }, [])

  const undoEdit = useCallback((tabId: string) => {
    setTabs((previous) =>
      previous.map((tab) => {
        if (tab.id !== tabId || tab.undoIndex <= 0) return tab

        const undoIndex = tab.undoIndex - 1
        return {
          ...tab,
          undoIndex,
          content: tab.undoStack[undoIndex] ?? tab.content,
        }
      }),
    )
  }, [])

  const saveTab = useCallback(
    (tabId: string) => {
      setTabs((previous) =>
        previous.map((tab) => {
          if (tab.id !== tabId || tab.source !== 'file') return tab

          void writeFileByPath(tab.location, tab.content)
          return {
            ...tab,
            savedContent: tab.content,
            undoStack: [tab.content],
            undoIndex: 0,
          }
        }),
      )
    },
    [],
  )

  useEffect(() => {
    let cancelled = false

    const syncFiles = async () => {
      try {
        const state = await fetchFilesState()
        const revision = String(state.revision || '')
        if (!revision || revision === fileRevisionRef.current) return
        fileRevisionRef.current = revision

        const fileTabs = tabsRef.current.filter((tab) => tab.source === 'file')
        await Promise.all(
          fileTabs.map(async (tab) => {
            if (tab.content !== tab.savedContent) return
            try {
              const content = await refreshFileByPath(tab.location)
              if (cancelled) return
              setTabs((previous) =>
                previous.map((current) =>
                  current.id === tab.id && current.content === current.savedContent
                    ? {
                        ...current,
                        content,
                        savedContent: content,
                        undoStack: [content],
                        undoIndex: 0,
                      }
                    : current,
                ),
              )
            } catch {
              // keep current tab content if refresh fails
            }
          }),
        )
      } catch {
        // ignore polling errors; next interval can recover
      }
    }

    void syncFiles()
    const timer = window.setInterval(() => {
      void syncFiles()
    }, 3000)

    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    if (bootstrappedRef.current) return
    bootstrappedRef.current = true

    void (async () => {
      try {
        const root = await fetchFilesTree()
        const readme =
          findFileNodeByPath(root, 'README.md') ??
          findFileNodeByPath(root, 'readme.md')
        if (readme) {
          const relativePath = getRelativePathFromRoot(root, readme.id)
          if (relativePath) {
            openFile({
              fileId: readme.id,
              fileName: readme.name,
              relativePath,
            })
            return
          }
        }

        const content = await readFileByPath('README.md')
        if (content.trim()) {
          openFile({
            fileId: 'readme-md',
            fileName: 'README.md',
            relativePath: 'README.md',
          })
          return
        }

        setTabs((previous) => (previous.length === 0 ? [createEmptyUrlTab()] : previous))
        setActiveTabId((current) => current ?? 'url:new')
      } catch {
        setTabs((previous) => (previous.length === 0 ? [createEmptyUrlTab()] : previous))
        setActiveTabId((current) => current ?? 'url:new')
      }
    })()
  }, [openFile])

  const value = useMemo(
    () => ({
      projectName,
      tabs,
      activeTabId,
      activeTab,
      openFile,
      openContent,
      openUrl,
      openNewTab,
      closeTab,
      selectTab,
      setTabMode,
      setLocationDraft,
      commitLocation,
      goBack,
      reloadTab,
      updateTabContent,
      undoEdit,
      saveTab,
    }),
    [
      projectName,
      tabs,
      activeTabId,
      activeTab,
      openFile,
      openContent,
      openUrl,
      openNewTab,
      closeTab,
      selectTab,
      setTabMode,
      setLocationDraft,
      commitLocation,
      goBack,
      reloadTab,
      updateTabContent,
      undoEdit,
      saveTab,
    ],
  )

  return (
    <BrowserWorkspaceContext.Provider value={value}>{children}</BrowserWorkspaceContext.Provider>
  )
}

export function useBrowserWorkspace() {
  const context = useContext(BrowserWorkspaceContext)
  if (!context) {
    throw new Error('useBrowserWorkspace must be used within BrowserWorkspaceProvider')
  }
  return context
}

export function useBrowserChromeState(tab: BrowserTab | null) {
  if (!tab) {
    return {
      canBack: false,
      canReload: false,
      canEdit: false,
      canCode: false,
      canPreview: false,
      canUndo: false,
      canSave: false,
      isDirty: false,
      isMarkdown: false,
      unsupported: false,
    }
  }

  const capability = tab.source === 'file' ? getFileCapability(tab.title) : null
  const isDirty = tab.source === 'file' && tab.content !== tab.savedContent
  const unsupported = Boolean(capability?.unsupported)

  const filePath = reloadableFilePath(tab)
  const canReload = Boolean(
    filePath ||
      (tab.source === 'url' && tab.mode === 'navigate' && tab.location.trim()),
  )

  return {
    canBack: tab.navigationIndex > 0,
    canReload,
    canEdit: !unsupported && tab.source === 'file' && Boolean(capability?.editable),
    canCode: !unsupported && tab.source === 'file',
    canPreview: !unsupported && Boolean(capability?.previewable && tab.source === 'file'),
    canUndo: !unsupported && tab.mode === 'edit' && tab.undoIndex > 0,
    canSave: !unsupported && tab.mode === 'edit' && isDirty && Boolean(capability?.editable),
    isDirty,
    isMarkdown: !unsupported && getFileCapability(tab.title).language === 'markdown',
    unsupported,
  }
}
