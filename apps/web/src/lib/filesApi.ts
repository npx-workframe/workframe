import { apiGet, apiPost } from '@/lib/apiClient'
import type { FileTreeNode } from '@/lib/fileTreeTypes'

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

let filesTreePromise: Promise<FileTreeNode> | null = null
const fileContentCache = new Map<string, Promise<string>>()
const FILE_TREE_CACHE_KEY = 'wf-files-tree-cache'
const FILE_STATE_CACHE_KEY = 'wf-files-state-cache'
const FILE_CONTENT_CACHE_PREFIX = 'wf-file-content:'

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

export function workspaceRawUrl(path: string): string {
  return `/api/files/raw?path=${encodeURIComponent(path)}`
}

/** Path-style workspace URL so HTML relative assets (js/css) resolve correctly in iframes. */
export function workspaceFileServeUrl(path: string): string {
  const trimmed = path.trim().replace(/\\/g, '/').replace(/^\/+/, '')
  if (!trimmed) return '/api/files/workspace/'
  return `/api/files/workspace/${trimmed.split('/').map((segment) => encodeURIComponent(segment)).join('/')}`
}
