import { useCallback, useEffect, useRef, useState } from 'react'
import { Download, ListChecks, LoaderCircle, Trash2, X } from 'lucide-react'

import { ConfirmDialog } from '@/components/dialogs/ConfirmDialog'
import { Button } from '@/components/ui/button'
import { FileTree } from '@/components/ui/file-tree'
import { ScrollArea } from '@/components/ui/scroll-area'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'
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
  deleteWorkspaceFiles,
  downloadWorkspaceFiles,
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
  const [selectionMode, setSelectionMode] = useState(false)
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(() => new Set())
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [busyAction, setBusyAction] = useState<'download' | 'delete' | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [noticeTone, setNoticeTone] = useState<'neutral' | 'caution'>('neutral')
  const loadingFoldersRef = useRef(new Set<string>())

  useEffect(() => {
    setExpandedIds(new Set([tree.id]))
    setSelectedId(null)
    setSelectionMode(false)
    setSelectedPaths(new Set())
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

  const onCheckedChange = useCallback((node: FileTreeNode, checked: boolean) => {
    if (node.type !== 'file') return
    setSelectedPaths((previous) => {
      const next = new Set(previous)
      if (checked) next.add(node.id)
      else next.delete(node.id)
      return next
    })
    setNotice(null)
  }, [])

  const exitSelectionMode = useCallback(() => {
    setSelectionMode(false)
    setSelectedPaths(new Set())
    setDeleteDialogOpen(false)
    setNotice(null)
  }, [])

  const refreshAfterMutation = useCallback(async () => {
    invalidateFilesTreeCache()
    const root = await fetchFilesTree()
    setTree(root)
    setCachedFilesTree(root)
    setExpandedIds(new Set([root.id]))
    setSelectedId(null)
    try {
      revisionRef.current = String((await fetchFilesState()).revision || '')
    } catch {
      revisionRef.current = ''
    }
  }, [])

  const handleDownload = useCallback(async () => {
    if (!selectedPaths.size || busyAction) return
    setBusyAction('download')
    setNotice(null)
    try {
      const filename = await downloadWorkspaceFiles([...selectedPaths], `${projectName}-files`)
      setNoticeTone('neutral')
      setNotice(`Downloaded ${filename}.`)
    } catch (error) {
      setNoticeTone('caution')
      setNotice(error instanceof Error ? error.message : 'Could not download the selected files.')
    } finally {
      setBusyAction(null)
    }
  }, [busyAction, projectName, selectedPaths])

  const handleDelete = useCallback(async () => {
    if (!selectedPaths.size || busyAction) return
    const count = selectedPaths.size
    setBusyAction('delete')
    setNotice(null)
    try {
      await deleteWorkspaceFiles([...selectedPaths])
      await refreshAfterMutation()
      setSelectedPaths(new Set())
      setSelectionMode(false)
      setNoticeTone('neutral')
      setNotice(`Deleted ${count} ${count === 1 ? 'file' : 'files'}.`)
    } catch (error) {
      setNoticeTone('caution')
      setNotice(error instanceof Error ? error.message : 'Could not delete the selected files.')
    } finally {
      setBusyAction(null)
    }
  }, [busyAction, refreshAfterMutation, selectedPaths])

  return (
    <div ref={containerRef} className="wf-file-explorer">
      <div className="wf-file-explorer__toolbar" role="toolbar" aria-label="Navigator file actions">
        {selectionMode ? (
          <>
            <span className="wf-file-explorer__selection-count" aria-live="polite">
              {selectedPaths.size} selected
            </span>
            <Button
              type="button"
              variant="toolbar"
              size="toolbarIcon"
              onClick={() => void handleDownload()}
              disabled={!selectedPaths.size || busyAction !== null}
              aria-label="Download selected files"
              title="Download selected files"
            >
              {busyAction === 'download' ? <LoaderCircle className="wf-spin" /> : <Download />}
            </Button>
            <Button
              type="button"
              variant="toolbar"
              size="toolbarIcon"
              className="wf-file-explorer__delete-btn"
              onClick={() => setDeleteDialogOpen(true)}
              disabled={!selectedPaths.size || busyAction !== null}
              aria-label="Delete selected files"
              title="Delete selected files"
            >
              {busyAction === 'delete' ? <LoaderCircle className="wf-spin" /> : <Trash2 />}
            </Button>
            <Button
              type="button"
              variant="toolbar"
              size="toolbarIcon"
              onClick={exitSelectionMode}
              disabled={busyAction !== null}
              aria-label="Exit file selection"
              title="Exit file selection"
            >
              <X />
            </Button>
          </>
        ) : (
          <Button
            type="button"
            variant="toolbar"
            size="toolbarText"
            onClick={() => {
              setSelectionMode(true)
              setSelectedId(null)
              setNotice(null)
            }}
          >
            <ListChecks />
            Select files
          </Button>
        )}
      </div>

      <WorkframeNotice
        message={notice}
        tone={noticeTone}
        className="wf-file-explorer__notice"
        role="status"
      />

      <ScrollArea axis="vertical" inset="sm" className="wf-file-explorer__scroll">
        <FileTree
          root={tree}
          expandedIds={expandedIds}
          selectedId={selectedId}
          selectionMode={selectionMode}
          checkedIds={selectedPaths}
          onFolderClick={onFolderClick}
          onFileClick={onFileClick}
          onCheckedChange={onCheckedChange}
        />
      </ScrollArea>

      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title={`Delete ${selectedPaths.size === 1 ? 'file' : `${selectedPaths.size} files`}?`}
        description="The selected files will be permanently removed from this project. This cannot be undone."
        confirmLabel="Delete"
        confirmVariant="warn"
        onConfirm={() => void handleDelete()}
      />
    </div>
  )
}
