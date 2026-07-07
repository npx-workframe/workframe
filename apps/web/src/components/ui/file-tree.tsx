import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type CSSProperties,
  type ReactNode,
} from 'react'
import { ChevronRight } from 'lucide-react'

import { getNodePresentation } from '@/lib/fileTypeStyle'
import type { FileTreeNode } from '@/lib/fileTreeTypes'
import { cn } from '@/lib/utils'

export type TreeViewElement = FileTreeNode

type FileTreeContextValue = {
  rootId: string
  expandedIds: Set<string>
  selectedId: string | null
  onFolderClick: (node: FileTreeNode) => void
  onFileClick: (node: FileTreeNode) => void
}

const FileTreeContext = createContext<FileTreeContextValue | null>(null)

function useFileTreeContext() {
  const context = useContext(FileTreeContext)
  if (!context) {
    throw new Error('File tree components must be used within <FileTree>.')
  }
  return context
}

type FileTreeProps = {
  root: FileTreeNode
  expandedIds: Set<string>
  selectedId?: string | null
  onFolderClick: (node: FileTreeNode) => void
  onFileClick: (node: FileTreeNode) => void
  className?: string
  children?: ReactNode
}

export function FileTree({
  root,
  expandedIds,
  selectedId = null,
  onFolderClick,
  onFileClick,
  className,
  children,
}: FileTreeProps) {
  const value = useMemo(
    () => ({
      rootId: root.id,
      expandedIds,
      selectedId,
      onFolderClick,
      onFileClick,
    }),
    [root.id, expandedIds, selectedId, onFolderClick, onFileClick],
  )

  return (
    <FileTreeContext.Provider value={value}>
      <div className={cn('wf-file-tree', className)} role="tree" aria-label={root.name}>
        {children ?? <FileTreeBranch node={root} depth={0} isRoot />}
      </div>
    </FileTreeContext.Provider>
  )
}

type FileTreeBranchProps = {
  node: FileTreeNode
  depth: number
  isRoot?: boolean
}

function FileTreeBranch({ node, depth, isRoot = false }: FileTreeBranchProps) {
  const { expandedIds, selectedId, onFolderClick, onFileClick } = useFileTreeContext()
  const isFolder = node.type === 'folder'
  const isExpanded = expandedIds.has(node.id)
  const isSelected = selectedId === node.id
  const { Icon, color } = getNodePresentation(node.name, node.type, isFolder && isExpanded)

  const handleClick = useCallback(() => {
    if (isFolder) onFolderClick(node)
    else onFileClick(node)
  }, [isFolder, node, onFolderClick, onFileClick])

  return (
    <div
      className={cn('wf-file-tree__branch', isRoot && 'wf-file-tree__branch--root')}
      role="treeitem"
      aria-expanded={isFolder ? isExpanded : undefined}
      aria-selected={isSelected}
      data-depth={depth}
    >
      <button
        type="button"
        className={cn(
          'wf-file-tree__row',
          isSelected && 'wf-file-tree__row--selected',
          isRoot && 'wf-file-tree__row--root',
        )}
        style={{ '--file-color': color, paddingLeft: `${8 + depth * 10}px` } as CSSProperties}
        onClick={handleClick}
      >
        <Icon className="wf-file-tree__icon" aria-hidden="true" />
        <span className="wf-file-tree__label">{node.name}</span>
        {isFolder ? (
          <ChevronRight
            className={cn('wf-file-tree__chevron', isExpanded && 'wf-file-tree__chevron--open')}
            aria-hidden="true"
          />
        ) : null}
      </button>

      {isFolder && isExpanded ? (
        <div className="wf-file-tree__children" role="group">
          {(node.children ?? []).map((child) => (
            <FileTreeBranch key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function FileTreeFromElements({
  elements,
  ...props
}: Omit<FileTreeProps, 'root' | 'children'> & { elements: TreeViewElement[] }) {
  const root = elements[0]
  if (!root) return null
  return <FileTree root={root} {...props} />
}
