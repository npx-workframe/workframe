import type { LucideIcon } from 'lucide-react'
import {
  Braces,
  File,
  FileArchive,
  FileCode2,
  FileImage,
  FileJson2,
  FileSpreadsheet,
  FileText,
  FileType,
  Folder,
  FolderOpen,
  Sheet,
} from 'lucide-react'

import { getFileCapability, getFileExtension } from '@/lib/fileCapabilities'

export type FileTypePresentation = {
  Icon: LucideIcon
  color: string
}

const EXTENSIONS: Record<string, FileTypePresentation> = {
  md: { Icon: FileText, color: 'var(--wf-cyan)' },
  mdx: { Icon: FileText, color: 'var(--wf-cyan)' },
  txt: { Icon: FileType, color: 'var(--wf-muted)' },
  log: { Icon: FileText, color: 'var(--wf-muted)' },
  html: { Icon: FileCode2, color: 'var(--wf-violet-glow)' },
  htm: { Icon: FileCode2, color: 'var(--wf-violet-glow)' },
  css: { Icon: Braces, color: '#3b82f6' },
  scss: { Icon: Braces, color: '#3b82f6' },
  js: { Icon: FileCode2, color: '#eab308' },
  ts: { Icon: FileCode2, color: '#2563eb' },
  tsx: { Icon: FileCode2, color: '#2563eb' },
  jsx: { Icon: FileCode2, color: '#eab308' },
  json: { Icon: FileJson2, color: 'var(--wf-mint)' },
  py: { Icon: FileCode2, color: '#3b82f6' },
  yaml: { Icon: FileCode2, color: '#eab308' },
  yml: { Icon: FileCode2, color: '#eab308' },
  toml: { Icon: FileCode2, color: 'var(--wf-muted)' },
  sh: { Icon: FileCode2, color: 'var(--wf-mint)' },
  bash: { Icon: FileCode2, color: 'var(--wf-mint)' },
  sql: { Icon: FileCode2, color: '#06b6d4' },
  graphql: { Icon: FileCode2, color: '#ec4899' },
  gql: { Icon: FileCode2, color: '#ec4899' },
  xml: { Icon: FileCode2, color: '#f97316' },
  csv: { Icon: FileSpreadsheet, color: 'var(--wf-mint)' },
  tsv: { Icon: FileSpreadsheet, color: 'var(--wf-mint)' },
  ini: { Icon: FileText, color: 'var(--wf-muted)' },
  cfg: { Icon: FileText, color: 'var(--wf-muted)' },
  conf: { Icon: FileText, color: 'var(--wf-muted)' },
  env: { Icon: FileText, color: 'var(--wf-muted)' },
  png: { Icon: FileImage, color: 'var(--wf-violet-glow)' },
  jpg: { Icon: FileImage, color: 'var(--wf-violet-glow)' },
  jpeg: { Icon: FileImage, color: 'var(--wf-violet-glow)' },
  gif: { Icon: FileImage, color: 'var(--wf-violet-glow)' },
  webp: { Icon: FileImage, color: 'var(--wf-violet-glow)' },
  svg: { Icon: FileImage, color: 'var(--wf-mint)' },
  pdf: { Icon: FileText, color: '#ef4444' },
  doc: { Icon: FileText, color: '#2563eb' },
  docx: { Icon: FileText, color: '#2563eb' },
  xls: { Icon: Sheet, color: 'var(--wf-mint)' },
  xlsx: { Icon: Sheet, color: 'var(--wf-mint)' },
  ppt: { Icon: FileText, color: '#f97316' },
  pptx: { Icon: FileText, color: '#f97316' },
  zip: { Icon: FileArchive, color: 'var(--wf-muted)' },
  tar: { Icon: FileArchive, color: 'var(--wf-muted)' },
  gz: { Icon: FileArchive, color: 'var(--wf-muted)' },
}

const FILE_NAME_ICONS: Record<string, FileTypePresentation> = {
  dockerfile: { Icon: FileCode2, color: '#2563eb' },
  makefile: { Icon: FileCode2, color: 'var(--wf-muted)' },
  '.env': { Icon: FileText, color: 'var(--wf-mint)' },
  '.env.example': { Icon: FileText, color: 'var(--wf-mint)' },
  '.gitignore': { Icon: FileText, color: 'var(--wf-muted)' },
}

export function getNodePresentation(
  name: string,
  type: 'file' | 'folder',
  expanded: boolean,
): FileTypePresentation {
  if (type === 'folder') {
    return expanded
      ? { Icon: FolderOpen, color: 'var(--wf-violet-glow)' }
      : { Icon: Folder, color: 'var(--wf-muted)' }
  }

  const normalized = name.toLowerCase()
  if (FILE_NAME_ICONS[normalized]) {
    return FILE_NAME_ICONS[normalized]
  }

  if (getFileCapability(name).unsupported) {
    const ext = getFileExtension(name)
    return EXTENSIONS[ext] ?? { Icon: FileArchive, color: 'var(--wf-muted)' }
  }

  const ext = getFileExtension(name)
  return EXTENSIONS[ext] ?? { Icon: File, color: 'var(--wf-muted)' }
}
