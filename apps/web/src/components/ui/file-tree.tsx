import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type CSSProperties,
  type ReactNode,
} from 'react'
import { ChevronRight } from 'lucide-react'

import { Checkbox } from '@/components/ui/checkbox'
import { getNodePresentation } from '@/lib/fileTypeStyle'
import type { FileTreeNode } from '@/lib/fileTreeTypes'
import { cn } from '@/lib/utils'

export type TreeViewElement = FileTreeNode

type FileTreeContextValue = {
  rootId: string
  expandedIds: Set<string>
  selectedId: string | null
  selectionMode: boolean
  checkedIds: Set<string>
  onFolderClick: (node: FileTreeNode) => void
  onFileClick: (node: FileTreeNode) => void
  onCheckedChange?: (node: FileTreeNode, checked: boolean) => void
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
  selectionMode?: boolean
  checkedIds?: Set<string>
  onFolderClick: (node: FileTreeNode) => void
  onFileClick: (node: FileTreeNode) => void
  onCheckedChange?: (node: FileTreeNode, checked: boolean) => void
  className?: string
  children?: ReactNode
}

export function FileTree({
  root,
  expandedIds,
  selectedId = null,
  selectionMode = false,
  checkedIds = new Set<string>(),
  onFolderClick,
  onFileClick,
  onCheckedChange,
  className,
  children,
}: FileTreeProps) {
  const value = useMemo(
    () => ({
      rootId: root.id,
      expandedIds,
      selectedId,
      selectionMode,
      checkedIds,
      onFolderClick,
      onFileClick,
      onCheckedChange,
    }),
    [
      root.id,
      expandedIds,
      selectedId,
      selectionMode,
      checkedIds,
      onFolderClick,
      onFileClick,
      onCheckedChange,
    ],
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
  const {
    expandedIds,
    selectedId,
    selectionMode,
    checkedIds,
    onFolderClick,
    onFileClick,
    onCheckedChange,
  } = useFileTreeContext()
  const isFolder = node.type === 'folder'
  const isExpanded = expandedIds.has(node.id)
  const isSelected = selectedId === node.id
  const isCheckable = selectionMode && !isFolder && !isRoot
  const isChecked = isCheckable && checkedIds.has(node.id)
  const { Icon, color } = getNodePresentation(node.name, node.type, isFolder && isExpanded)

  const handleClick = useCallback(() => {
    if (isFolder) onFolderClick(node)
    else if (isCheckable) onCheckedChange?.(node, !isChecked)
    else onFileClick(node)
  }, [isFolder, isCheckable, isChecked, node, onCheckedChange, onFolderClick, onFileClick])

  return (
    <div
      className={cn('wf-file-tree__branch', isRoot && 'wf-file-tree__branch--root')}
      role="treeitem"
      aria-expanded={isFolder ? isExpanded : undefined}
      aria-selected={isSelected}
      aria-checked={isCheckable ? isChecked : undefined}
      data-depth={depth}
    >
      <div className="wf-file-tree__row-shell">
        {isCheckable ? (
          <Checkbox
            checked={isChecked}
            onCheckedChange={(checked) => onCheckedChange?.(node, checked === true)}
            className="wf-file-tree__checkbox"
            aria-label={`Select ${node.name}`}
          />
        ) : null}
        <button
          type="button"
          className={cn(
            'wf-file-tree__row',
            isSelected && 'wf-file-tree__row--selected',
            isChecked && 'wf-file-tree__row--checked',
            isRoot && 'wf-file-tree__row--root',
          )}
          style={{ '--file-color': color } as CSSProperties}
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
      </div>

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
