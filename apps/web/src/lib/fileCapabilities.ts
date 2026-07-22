import type { BrowserMode } from '@/lib/browserTypes'

export type FileCapability = {
  previewable: boolean
  editable: boolean
  defaultMode: BrowserMode
  language: string
  mimeType: string
  /** Binary / office — show honest unsupported state, not fake code view. */
  unsupported?: boolean
}

const DEFAULT: FileCapability = {
  previewable: false,
  editable: true,
  defaultMode: 'code',
  language: 'plaintext',
  mimeType: 'text/plain',
}

const UNSUPPORTED: FileCapability = {
  previewable: false,
  editable: false,
  defaultMode: 'preview',
  language: 'plaintext',
  mimeType: 'application/octet-stream',
  unsupported: true,
}

const code = (
  language: string,
  mimeType = 'text/plain',
  overrides: Partial<FileCapability> = {},
): FileCapability => ({
  previewable: false,
  editable: true,
  defaultMode: 'code',
  language,
  mimeType,
  ...overrides,
})

const previewText = (
  language: string,
  mimeType = 'text/plain',
  overrides: Partial<FileCapability> = {},
): FileCapability => ({
  previewable: true,
  editable: true,
  defaultMode: 'preview',
  language,
  mimeType,
  ...overrides,
})

const CAPABILITIES: Record<string, FileCapability> = {
  // ── Tier 1: text / dev workspace ─────────────────────────────────────────
  md: previewText('markdown', 'text/markdown'),
  mdx: previewText('markdown', 'text/markdown'),
  mmd: previewText('mermaid', 'text/plain'),
  mermaid: previewText('mermaid', 'text/plain'),
  txt: previewText('plaintext', 'text/plain'),
  env: code('plaintext', 'text/plain'),
  py: code('python', 'text/x-python'),
  yaml: code('yaml', 'text/yaml'),
  yml: code('yaml', 'text/yaml'),
  toml: code('ini', 'text/plain'),
  sh: code('bash', 'application/x-sh'),
  bash: code('bash', 'application/x-sh'),
  xml: code('xml', 'application/xml'),
  sql: code('sql', 'application/sql'),
  graphql: code('graphql', 'text/plain'),
  gql: code('graphql', 'text/plain'),

  // ── Tier 2 ───────────────────────────────────────────────────────────────
  tsv: previewText('plaintext', 'text/tab-separated-values'),
  log: previewText('plaintext', 'text/plain'),
  ini: code('ini', 'text/plain'),
  cfg: code('ini', 'text/plain'),
  conf: code('ini', 'text/plain'),

  // ── Existing coverage ────────────────────────────────────────────────────
  html: previewText('html', 'text/html'),
  htm: previewText('html', 'text/html'),
  css: code('css', 'text/css'),
  js: code('javascript', 'text/javascript'),
  ts: code('typescript', 'text/typescript'),
  tsx: code('typescript', 'text/typescript'),
  jsx: code('javascript', 'text/javascript'),
  json: { ...previewText('json', 'application/json'), defaultMode: 'code' },
  svg: previewText('xml', 'image/svg+xml'),
  png: { previewable: true, editable: false, defaultMode: 'preview', language: 'plaintext', mimeType: 'image/png' },
  jpg: { previewable: true, editable: false, defaultMode: 'preview', language: 'plaintext', mimeType: 'image/jpeg' },
  jpeg: { previewable: true, editable: false, defaultMode: 'preview', language: 'plaintext', mimeType: 'image/jpeg' },
  gif: { previewable: true, editable: false, defaultMode: 'preview', language: 'plaintext', mimeType: 'image/gif' },
  webp: { previewable: true, editable: false, defaultMode: 'preview', language: 'plaintext', mimeType: 'image/webp' },
  csv: previewText('plaintext', 'text/csv'),
  pdf: { previewable: true, editable: false, defaultMode: 'preview', language: 'plaintext', mimeType: 'application/pdf' },
  mp4: { previewable: true, editable: false, defaultMode: 'preview', language: 'plaintext', mimeType: 'video/mp4' },
  webm: { previewable: true, editable: false, defaultMode: 'preview', language: 'plaintext', mimeType: 'video/webm' },
  mp3: { previewable: true, editable: false, defaultMode: 'preview', language: 'plaintext', mimeType: 'audio/mpeg' },
  wav: { previewable: true, editable: false, defaultMode: 'preview', language: 'plaintext', mimeType: 'audio/wav' },

  // ── Tier 3: binary / office (honest unsupported) ───────────────────────
  doc: UNSUPPORTED,
  docx: UNSUPPORTED,
  odt: UNSUPPORTED,
  rtf: UNSUPPORTED,
  xls: UNSUPPORTED,
  xlsx: UNSUPPORTED,
  ods: UNSUPPORTED,
  ppt: UNSUPPORTED,
  pptx: UNSUPPORTED,
  odp: UNSUPPORTED,
  zip: UNSUPPORTED,
  tar: UNSUPPORTED,
  gz: UNSUPPORTED,
  tgz: UNSUPPORTED,
  bz2: UNSUPPORTED,
  xz: UNSUPPORTED,
  '7z': UNSUPPORTED,
  rar: UNSUPPORTED,
  exe: UNSUPPORTED,
  dll: UNSUPPORTED,
  bin: UNSUPPORTED,
  wasm: UNSUPPORTED,
  iso: UNSUPPORTED,
  dmg: UNSUPPORTED,
}

/** Extensionless or special filenames. */
const FILE_NAME_CAPABILITIES: Record<string, FileCapability> = {
  dockerfile: code('dockerfile', 'text/plain'),
  'dockerfile.dev': code('dockerfile', 'text/plain'),
  makefile: code('makefile', 'text/plain'),
  '.env': code('plaintext', 'text/plain'),
  '.env.example': code('plaintext', 'text/plain'),
  '.env.local': code('plaintext', 'text/plain'),
  '.gitignore': code('plaintext', 'text/plain'),
  '.gitattributes': code('plaintext', 'text/plain'),
  '.editorconfig': code('ini', 'text/plain'),
}

export function getFileExtension(fileName: string) {
  const index = fileName.lastIndexOf('.')
  if (index <= 0) return ''
  return fileName.slice(index + 1).toLowerCase()
}

export function getFileCapability(fileName: string): FileCapability {
  const normalized = fileName.toLowerCase()

  if (FILE_NAME_CAPABILITIES[normalized]) {
    return FILE_NAME_CAPABILITIES[normalized]
  }

  const ext = getFileExtension(fileName)
  if (ext && CAPABILITIES[ext]) {
    return CAPABILITIES[ext]
  }

  return DEFAULT
}

export function isUnsupportedFile(fileName: string) {
  return Boolean(getFileCapability(fileName).unsupported)
}

export function hasKnownFileCapability(fileName: string) {
  const normalized = fileName.toLowerCase()
  if (FILE_NAME_CAPABILITIES[normalized]) return true
  const ext = getFileExtension(fileName)
  return Boolean(ext && CAPABILITIES[ext])
}

export function isUrl(value: string) {
  return /^https?:\/\//i.test(value.trim())
}
