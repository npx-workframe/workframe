import { apiGet, apiPost } from '@/lib/apiClient'
import { authenticatedFetch } from '@/lib/authenticatedFetch'
import type { FileTreeNode } from '@/lib/fileTreeTypes'
import { parseApiErrorResponse, WorkframeApiError } from '@/lib/workframeErrors'

type FilesTreeResponse = {
  root: FileTreeNode
}

type FilesListResponse = {
  path: string
  children: FileTreeNode[]
}

type FilesStateResponse = {
  revision: string
  files?: number
  updated_at?: string
  latest_path?: string
}

type FileReadResponse = {
  path: string
  content: string
}

type FilesDeleteResponse = {
  ok: boolean
  deleted: string[]
  count: number
}

let filesTreePromise: Promise<FileTreeNode> | null = null
const fileContentCache = new Map<string, Promise<string>>()
const FILE_TREE_CACHE_KEY = 'wf-files-tree-cache'
const FILE_STATE_CACHE_KEY = 'wf-files-state-cache'
const FILE_CONTENT_CACHE_PREFIX = 'wf-file-content:'
export const WORKSPACE_FILES_DELETED = 'workframe:files-deleted'

function readStorage<T>(key: string): T | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

function writeStorage(key: string, value: unknown): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // ignore quota / private mode errors
  }
}

export async function fetchFilesState(): Promise<FilesStateResponse> {
  const state = await apiGet<FilesStateResponse>('/api/files/state')
  writeStorage(FILE_STATE_CACHE_KEY, state)
  return state
}

export function getCachedFilesState(): FilesStateResponse | null {
  return readStorage<FilesStateResponse>(FILE_STATE_CACHE_KEY)
}

export async function fetchFilesTree(): Promise<FileTreeNode> {
  if (!filesTreePromise) {
    filesTreePromise = apiGet<FilesTreeResponse>('/api/files/tree')
      .then((data) => {
        writeStorage(FILE_TREE_CACHE_KEY, data.root)
        return data.root
      })
      .catch((err) => {
        filesTreePromise = null
        throw err
      })
  }
  return filesTreePromise
}

export function getCachedFilesTree(): FileTreeNode | null {
  return readStorage<FileTreeNode>(FILE_TREE_CACHE_KEY)
}

export async function fetchFolderChildren(path = ''): Promise<FileTreeNode[]> {
  const query = path.trim() ? `?path=${encodeURIComponent(path.trim())}` : ''
  const data = await apiGet<FilesListResponse>(`/api/files/list${query}`)
  return data.children ?? []
}

export function setCachedFilesTree(root: FileTreeNode): void {
  writeStorage(FILE_TREE_CACHE_KEY, root)
  filesTreePromise = Promise.resolve(root)
}

export async function readFileByPath(path: string): Promise<string> {
  const key = path.trim()
  if (!fileContentCache.has(key)) {
    const cached = getCachedFileContent(key)
    if (cached != null) {
      fileContentCache.set(key, Promise.resolve(cached))
    } else {
      fileContentCache.set(
        key,
        apiGet<FileReadResponse>(`/api/files/read?path=${encodeURIComponent(path)}`)
          .then((data) => {
            writeStorage(`${FILE_CONTENT_CACHE_PREFIX}${key}`, data.content)
            return data.content
          })
          .catch((err) => {
            fileContentCache.delete(key)
            throw err
          }),
      )
    }
  }
  const current = await fileContentCache.get(key)!
  if (getCachedFileContent(key) !== current) {
    writeStorage(`${FILE_CONTENT_CACHE_PREFIX}${key}`, current)
  }
  return current
}

export function getCachedFileContent(path: string): string | null {
  return readStorage<string>(`${FILE_CONTENT_CACHE_PREFIX}${path.trim()}`)
}

export function setCachedFileContent(path: string, content: string): void {
  writeStorage(`${FILE_CONTENT_CACHE_PREFIX}${path.trim()}`, content)
  fileContentCache.set(path.trim(), Promise.resolve(content))
}

export async function refreshFileByPath(path: string): Promise<string> {
  const key = path.trim()
  const content = await apiGet<FileReadResponse>(`/api/files/read?path=${encodeURIComponent(path)}`)
    .then((data) => data.content)
  setCachedFileContent(key, content)
  return content
}

export async function writeFileByPath(path: string, content: string): Promise<void> {
  await apiPost('/api/files/write', { path, content })
  setCachedFileContent(path.trim(), content)
  filesTreePromise = null
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = String(reader.result ?? '')
      const comma = result.indexOf(',')
      resolve(comma >= 0 ? result.slice(comma + 1) : result)
    }
    reader.onerror = () => reject(reader.error ?? new Error('read failed'))
    reader.readAsDataURL(file)
  })
}

export async function uploadBinaryFile(path: string, file: File): Promise<string> {
  const content_base64 = await fileToBase64(file)
  const data = await apiPost<{ path: string }>('/api/files/upload', { path, content_base64 })
  filesTreePromise = null
  return data.path ?? path
}

function normalizedSelectedPaths(paths: string[]): string[] {
  return [...new Set(paths.map(normalizeWorkspaceFilePath).filter(Boolean))]
}

function safeDownloadName(value: string, fallback: string): string {
  const normalized = value.trim().replace(/[<>:"/\\|?*\u0000-\u001f]+/g, '-').replace(/\s+/g, ' ')
  return normalized || fallback
}

function saveBrowserBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function downloadResponse(response: Response, method: string, path: string): Promise<Blob> {
  if (!response.ok) {
    throw new WorkframeApiError(await parseApiErrorResponse(response), method, path)
  }
  return response.blob()
}

export async function downloadWorkspaceFiles(
  paths: string[],
  archiveName = 'workframe-files',
  containsFolders = false,
): Promise<string> {
  const selected = normalizedSelectedPaths(paths)
  if (!selected.length) throw new Error('Select at least one file.')

  if (selected.length === 1 && !containsFolders) {
    const path = selected[0]
    const response = await authenticatedFetch(workspaceRawUrl(path))
    const filename = safeDownloadName(path.split('/').pop() ?? '', 'download')
    saveBrowserBlob(await downloadResponse(response, 'GET', '/api/files/raw'), filename)
    return filename
  }

  const endpoint = '/api/files/archive'
  const response = await authenticatedFetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ paths: selected }),
  })
  const filename = `${safeDownloadName(archiveName, 'workframe-files').replace(/\.zip$/i, '')}.zip`
  saveBrowserBlob(await downloadResponse(response, 'POST', endpoint), filename)
  return filename
}

export async function deleteWorkspaceFiles(paths: string[]): Promise<FilesDeleteResponse> {
  const selected = normalizedSelectedPaths(paths)
  if (!selected.length) throw new Error('Select at least one file.')
  const result = await apiPost<FilesDeleteResponse>('/api/files/delete', { paths: selected })
  filesTreePromise = null
  for (const path of result.deleted ?? selected) invalidateFileContentCache(path)
  clearCachedFilesTree()
  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new CustomEvent(WORKSPACE_FILES_DELETED, { detail: { paths: result.deleted ?? selected } }),
    )
  }
  return result
}

export function invalidateFilesTreeCache(): void {
  filesTreePromise = null
}

export function invalidateFileContentCache(path?: string): void {
  if (typeof window !== 'undefined') {
    try {
      if (path) localStorage.removeItem(`${FILE_CONTENT_CACHE_PREFIX}${path.trim()}`)
    } catch {
      // ignore storage misses
    }
  }
  if (path) {
    fileContentCache.delete(path.trim())
    return
  }
  fileContentCache.clear()
}

export function clearCachedFilesTree(): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.removeItem(FILE_TREE_CACHE_KEY)
    localStorage.removeItem(FILE_STATE_CACHE_KEY)
  } catch {
    // ignore storage misses
  }
}

export function normalizeWorkspaceFilePath(path: string): string {
  const normalized = path.trim().replace(/\\/g, '/')
  // Agent tools see the workspace at /workspace, while the BFF file routes
  // accept paths relative to that root. Persisted chat attachments can use
  // either form, so normalize at the URL boundary instead of rewriting
  // message history.
  return normalized
    .replace(/^\/workspace(?:\/|$)/i, '')
    .replace(/^workspace(?:\/|$)/i, '')
    .replace(/^\/+/, '')
}

export function workspaceRawUrl(path: string): string {
  return `/api/files/raw?path=${encodeURIComponent(normalizeWorkspaceFilePath(path))}`
}

/** Path-style workspace URL so HTML relative assets (js/css) resolve correctly in iframes. */
export function workspaceFileServeUrl(path: string): string {
  const trimmed = normalizeWorkspaceFilePath(path)
  if (!trimmed) return '/api/files/workspace/'
  return `/api/files/workspace/${trimmed.split('/').map((segment) => encodeURIComponent(segment)).join('/')}`
}
