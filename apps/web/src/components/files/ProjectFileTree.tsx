import { useCallback, useEffect, useRef, useState } from 'react'

import { FileTree } from '@/components/ui/file-tree'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useOpenWorkspaceFile } from '@/hooks/useOpenWorkspaceFile'
import {
  collectFolderDescendantIds,
  findNode,
  folderListPath,
  getPathToNode,
  getRelativePathFromRoot,
  getSiblingFolderIds,
  mergeFolderChildren,
  mergeTreePreserveLoaded,
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

function expandFolderIds(previous: Set<string>, rootId: string, tree: FileTreeNode, nodeId: string): Set<string> {
  const next = new Set(previous)
  next.add(rootId)

  if (previous.has(nodeId)) {
    next.delete(nodeId)
    const folderNode = findNode(tree, nodeId)
    if (folderNode) {
      for (const id of collectFolderDescendantIds(folderNode)) {
        next.delete(id)
      }
    }
    return next
  }

  const path = getPathToNode(tree, nodeId)
  for (const id of path) {
    next.add(id)
  }
  if (!path.includes(nodeId)) {
    next.add(nodeId)
  }
  for (const id of getSiblingFolderIds(tree, nodeId)) {
    next.delete(id)
  }
  return next
}

export function ProjectFileTree({ projectName = 'Workframe' }: ProjectFileTreeProps) {
  const openFile = useOpenWorkspaceFile()
  const [tree, setTree] = useState<FileTreeNode>(
    () =>
      getCachedFilesTree() ?? {
        id: 'root',
        name: projectName,
        type: 'folder',
        children: [],
      },
  )
  const treeRef = useRef(tree)
  treeRef.current = tree

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

  const applyTree = useCallback((incoming: FileTreeNode) => {
    setTree((previous) => {
      const next = mergeTreePreserveLoaded(previous, incoming)
      setCachedFilesTree(next)
      return next
    })
  }, [])

  useEffect(() => {
    let cancelled = false
    void fetchFilesTree().then((root) => {
      if (!cancelled) applyTree(root)
    })
    return () => {
      cancelled = true
    }
  }, [applyTree])

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
        if (!cancelled) applyTree(root)
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
  }, [applyTree, workspaceId])

  const collapseToRoot = useCallback(() => {
    setExpandedIds(new Set([treeRef.current.id]))
    setSelectedId(null)
  }, [])

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
      const currentTree = treeRef.current

      if (node.id === currentTree.id) {
        collapseToRoot()
        setSelectedId(currentTree.id)
        return
      }

      setExpandedIds((previous) => expandFolderIds(previous, currentTree.id, currentTree, node.id))
      setSelectedId(node.id)

      if (node.type !== 'folder' || node.children_loaded === true || loadingFoldersRef.current.has(node.id)) {
        return
      }

      loadingFoldersRef.current.add(node.id)
      try {
        const relativePath = folderListPath(currentTree, node)
        const children = await fetchFolderChildren(relativePath)
        setTree((previous) => {
          const next = mergeFolderChildren(previous, node.id, children)
          setCachedFilesTree(next)
          return next
        })
      } catch {
        // ponytail: folder stays expanded; retry on next click
      } finally {
        loadingFoldersRef.current.delete(node.id)
      }
    },
    [collapseToRoot],
  )

  const onFileClick = useCallback(
    (node: FileTreeNode) => {
      const currentTree = treeRef.current
      setExpandedIds(new Set(getPathToNode(currentTree, node.id)))
      setSelectedId(node.id)

      const relativePath = getRelativePathFromRoot(currentTree, node.id) ?? folderListPath(currentTree, node)
      if (relativePath) {
        openFile({
          fileId: node.id,
          fileName: node.name,
          relativePath,
        })
      }
    },
    [openFile],
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
