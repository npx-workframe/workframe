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
  css: { Icon: Braces, color: 'var(--wf-cyan)' },
  scss: { Icon: Braces, color: 'var(--wf-cyan)' },
  js: { Icon: FileCode2, color: 'var(--wf-warning)' },
  ts: { Icon: FileCode2, color: 'var(--wf-accent)' },
  tsx: { Icon: FileCode2, color: 'var(--wf-accent)' },
  jsx: { Icon: FileCode2, color: 'var(--wf-warning)' },
  json: { Icon: FileJson2, color: 'var(--wf-mint)' },
  py: { Icon: FileCode2, color: 'var(--wf-cyan)' },
  yaml: { Icon: FileCode2, color: 'var(--wf-warning)' },
  yml: { Icon: FileCode2, color: 'var(--wf-warning)' },
  toml: { Icon: FileCode2, color: 'var(--wf-muted)' },
  sh: { Icon: FileCode2, color: 'var(--wf-mint)' },
  bash: { Icon: FileCode2, color: 'var(--wf-mint)' },
  sql: { Icon: FileCode2, color: 'var(--wf-cyan)' },
  graphql: { Icon: FileCode2, color: 'var(--wf-violet-glow)' },
  gql: { Icon: FileCode2, color: 'var(--wf-violet-glow)' },
  xml: { Icon: FileCode2, color: 'var(--wf-warning)' },
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
  pdf: { Icon: FileText, color: 'var(--wf-error)' },
  doc: { Icon: FileText, color: 'var(--wf-accent)' },
  docx: { Icon: FileText, color: 'var(--wf-accent)' },
  xls: { Icon: Sheet, color: 'var(--wf-mint)' },
  xlsx: { Icon: Sheet, color: 'var(--wf-mint)' },
  ppt: { Icon: FileText, color: 'var(--wf-warning)' },
  pptx: { Icon: FileText, color: 'var(--wf-warning)' },
  zip: { Icon: FileArchive, color: 'var(--wf-muted)' },
  tar: { Icon: FileArchive, color: 'var(--wf-muted)' },
  gz: { Icon: FileArchive, color: 'var(--wf-muted)' },
}

const FILE_NAME_ICONS: Record<string, FileTypePresentation> = {
  dockerfile: { Icon: FileCode2, color: 'var(--wf-accent)' },
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
