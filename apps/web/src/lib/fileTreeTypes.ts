export type FileTreeNode = {
  id: string
  name: string
  type: 'file' | 'folder'
  children?: FileTreeNode[]
  children_loaded?: boolean
}

export function buildMockProjectTree(projectName: string): FileTreeNode {
  return {
    id: 'root',
    name: projectName,
    type: 'folder',
    children: [
      { id: 'readme-md', name: 'readme.md', type: 'file' },
      { id: 'dockerfile', name: 'Dockerfile', type: 'file' },
      { id: 'env-example', name: '.env.example', type: 'file' },
      {
        id: 'config',
        name: 'config',
        type: 'folder',
        children: [
          { id: 'config-app-yml', name: 'app.yml', type: 'file' },
          { id: 'config-settings-toml', name: 'settings.toml', type: 'file' },
        ],
      },
      {
        id: 'scripts',
        name: 'scripts',
        type: 'folder',
        children: [
          { id: 'scripts-setup-py', name: 'setup.py', type: 'file' },
          { id: 'scripts-deploy-sh', name: 'deploy.sh', type: 'file' },
          { id: 'scripts-app-js', name: 'app.js', type: 'file' },
          { id: 'scripts-query-sql', name: 'query.sql', type: 'file' },
        ],
      },
      {
        id: 'website',
        name: 'website',
        type: 'folder',
        children: [
          { id: 'website-index-html', name: 'index.html', type: 'file' },
          {
            id: 'website-styles',
            name: 'styles',
            type: 'folder',
            children: [{ id: 'website-styles-globals-css', name: 'globals.css', type: 'file' }],
          },
        ],
      },
      {
        id: 'assets',
        name: 'assets',
        type: 'folder',
        children: [
          { id: 'assets-logo-svg', name: 'logo.svg', type: 'file' },
          { id: 'assets-hero-png', name: 'hero.png', type: 'file' },
          { id: 'assets-data-csv', name: 'data.csv', type: 'file' },
          { id: 'assets-demo-webm', name: 'demo.webm', type: 'file' },
          { id: 'assets-demo-mp3', name: 'demo.mp3', type: 'file' },
          { id: 'assets-guide-pdf', name: 'guide.pdf', type: 'file' },
          { id: 'assets-report-xlsx', name: 'report.xlsx', type: 'file' },
          { id: 'assets-brief-docx', name: 'brief.docx', type: 'file' },
          { id: 'assets-backup-zip', name: 'backup.zip', type: 'file' },
        ],
      },
      {
        id: 'logs',
        name: 'logs',
        type: 'folder',
        children: [{ id: 'logs-gateway-log', name: 'gateway.log', type: 'file' }],
      },
    ],
  }
}

export function getPathToNode(root: FileTreeNode, targetId: string): string[] {
  if (root.id === targetId) return [root.id]

  for (const child of root.children ?? []) {
    const path = getPathToNode(child, targetId)
    if (path.length > 0) return [root.id, ...path]
  }

  return []
}

export function findNode(root: FileTreeNode, targetId: string): FileTreeNode | null {
  if (root.id === targetId) return root

  for (const child of root.children ?? []) {
    const found = findNode(child, targetId)
    if (found) return found
  }

  return null
}

export function collectFolderDescendantIds(node: FileTreeNode): string[] {
  const ids: string[] = []

  for (const child of node.children ?? []) {
    if (child.type === 'folder') {
      ids.push(child.id, ...collectFolderDescendantIds(child))
    }
  }

  return ids
}

export function getSiblingFolderIds(root: FileTreeNode, nodeId: string): string[] {
  const path = getPathToNode(root, nodeId)
  if (path.length < 2) return []

  const parentId = path[path.length - 2]
  const parent = findNode(root, parentId)
  if (!parent) return []

  return (parent.children ?? [])
    .filter((child) => child.type === 'folder' && child.id !== nodeId)
    .flatMap((child) => [child.id, ...collectFolderDescendantIds(child)])
}

export function getRelativePathFromRoot(root: FileTreeNode, targetId: string): string | null {
  if (targetId === root.id) return null

  const ids = getPathToNode(root, targetId)
  if (ids.length === 0) return null

  const segments: string[] = []
  for (const id of ids.slice(1)) {
    const node = findNode(root, id)
    if (node) segments.push(node.name)
  }

  return segments.join('/')
}

export function flattenTree(root: FileTreeNode): FileTreeNode[] {
  const nodes = [root]
  for (const child of root.children ?? []) {
    nodes.push(...flattenTree(child))
  }
  return nodes
}

export function findFileNodeByPath(root: FileTreeNode, relativePath: string): FileTreeNode | null {
  const target = relativePath.trim().replace(/\\/g, '/').replace(/^\/+/, '').toLowerCase()
  if (!target) return null

  for (const node of flattenTree(root)) {
    if (node.type !== 'file') continue
    const path = getRelativePathFromRoot(root, node.id)
    if (!path) continue
    const norm = path.replace(/\\/g, '/').replace(/^\/+/, '').toLowerCase()
    if (norm === target) return node
  }

  return null
}

export function mergeFolderChildren(
  root: FileTreeNode,
  folderId: string,
  children: FileTreeNode[],
): FileTreeNode {
  if (root.id === folderId) {
    return {
      ...root,
      children,
      children_loaded: true,
    }
  }

  return {
    ...root,
    children: (root.children ?? []).map((child) => mergeFolderChildren(child, folderId, children)),
  }
}
