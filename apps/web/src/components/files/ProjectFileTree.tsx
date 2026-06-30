import { useCallback, useEffect, useRef, useState } from 'react'

import { FileTree } from '@/components/ui/file-tree'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useBrowserWorkspace } from '@/contexts/BrowserWorkspaceContext'
import {
  collectFolderDescendantIds,
  findNode,
  getPathToNode,
  getRelativePathFromRoot,
  getSiblingFolderIds,
  mergeFolderChildren,
  type FileTreeNode,
} from '@/lib/fileTreeTypes'
import {
  fetchFolderChildren,
  fetchFilesState,
  fetchFilesTree,
  getCachedFilesState,
  getCachedFilesTree,
  invalidateFilesTreeCache,
  setCachedFilesTree,
} from '@/lib/filesApi'
import { workframeAuthApi, watchWorkspaceEvents } from '@/lib/workframeAuthApi'

type ProjectFileTreeProps = {
  projectName?: string
}

export function ProjectFileTree({ projectName = 'Workframe' }: ProjectFileTreeProps) {
  const { openFile } = useBrowserWorkspace()
  const [tree, setTree] = useState<FileTreeNode>(
    () =>
      getCachedFilesTree() ?? {
        id: 'root',
        name: projectName,
        type: 'folder',
        children: [],
      },
  )
  const containerRef = useRef<HTMLDivElement>(null)
  const revisionRef = useRef(String(getCachedFilesState()?.revision || ''))
  const [workspaceId, setWorkspaceId] = useState('')
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set([tree.id]))
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const loadingFoldersRef = useRef(new Set<string>())

  useEffect(() => {
    setExpandedIds(new Set([tree.id]))
    setSelectedId(null)
  }, [tree.id])

  useEffect(() => {
    let cancelled = false
    void fetchFilesTree().then((root) => {
      if (!cancelled) setTree(root)
    })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    void workframeAuthApi.getMe().then((profile) => {
      if (cancelled) return
      const wid =
        profile.current_workspace?.id ?? profile.default_workspace?.id ?? profile.workspaces?.[0]?.id ?? ''
      setWorkspaceId(wid)
    })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    const refreshTree = async () => {
      try {
        const state = await fetchFilesState()
        const revision = String(state.revision || '')
        if (!revision || revision === revisionRef.current) return
        revisionRef.current = revision
        invalidateFilesTreeCache()
        const root = await fetchFilesTree()
        if (!cancelled) setTree(root)
      } catch {
        // ignore sync misses; next interval can recover
      }
    }

    void refreshTree()
    const timer = window.setInterval(() => {
      void refreshTree()
    }, 3000)
    const stopEvents = workspaceId
      ? watchWorkspaceEvents(workspaceId, (frame) => {
          const filesRevision = String(frame.files_revision || '')
          if (filesRevision && filesRevision !== revisionRef.current) {
            void refreshTree()
          }
        })
      : () => {}

    return () => {
      cancelled = true
      window.clearInterval(timer)
      stopEvents()
    }
  }, [workspaceId])

  const collapseToRoot = useCallback(() => {
    setExpandedIds(new Set([tree.id]))
    setSelectedId(null)
  }, [tree.id])

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        collapseToRoot()
      }
    }

    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [collapseToRoot])

  const onFolderClick = useCallback(
    async (node: FileTreeNode) => {
      if (node.id === tree.id) {
        collapseToRoot()
        setSelectedId(tree.id)
        return
      }

      if (node.type === 'folder' && node.children_loaded !== true && !loadingFoldersRef.current.has(node.id)) {
        loadingFoldersRef.current.add(node.id)
        try {
          const relativePath = getRelativePathFromRoot(tree, node.id) ?? ''
          const children = await fetchFolderChildren(relativePath)
          setTree((previous) => {
            const next = mergeFolderChildren(previous, node.id, children)
            setCachedFilesTree(next)
            return next
          })
        } catch {
          // ignore lazy load errors; folder can be retried on next click
        } finally {
          loadingFoldersRef.current.delete(node.id)
        }
      }

      setExpandedIds((previous) => {
        const next = new Set(previous)
        next.add(tree.id)

        if (next.has(node.id)) {
          next.delete(node.id)
          const folderNode = findNode(tree, node.id)
          if (folderNode) {
            for (const id of collectFolderDescendantIds(folderNode)) {
              next.delete(id)
            }
          }
        } else {
          for (const id of getPathToNode(tree, node.id)) {
            next.add(id)
          }
          for (const id of getSiblingFolderIds(tree, node.id)) {
            next.delete(id)
          }
        }

        return next
      })
      setSelectedId(node.id)
    },
    [collapseToRoot, tree],
  )

  const onFileClick = useCallback(
    (node: FileTreeNode) => {
      setExpandedIds(new Set(getPathToNode(tree, node.id)))
      setSelectedId(node.id)

      const relativePath = getRelativePathFromRoot(tree, node.id)
      if (relativePath) {
        openFile({
          fileId: node.id,
          fileName: node.name,
          relativePath,
        })
      }
    },
    [openFile, tree],
  )

  return (
    <ScrollArea ref={containerRef} className="wf-file-explorer">
      <FileTree
        root={tree}
        expandedIds={expandedIds}
        selectedId={selectedId}
        onFolderClick={onFolderClick}
        onFileClick={onFileClick}
      />
    </ScrollArea>
  )
}
