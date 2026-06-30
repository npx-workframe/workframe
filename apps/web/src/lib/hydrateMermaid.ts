const MERMAID_ALIASES = new Set(['mermaid', 'mmd', 'graph', 'flowchart'])

// Agents often fence with the diagram type as the lang tag (```sequenceDiagram) not ```mermaid.
const MERMAID_LANG_RE =
  /^(?:graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|gitGraph|journey|mindmap|timeline|quadrantChart|requirementDiagram|C4Context|C4Container|C4Component|C4Dynamic|C4Deployment|sankey|block|xychart|zenuml|packet|kanban|architecture|wireframe|treemap|sankey-beta|block-beta|xychart-beta)(?:-v\d+|-beta|-alpha)?$/i

const DIAGRAM_USE_MAX_WIDTH_FALSE = {
  flowchart: { useMaxWidth: false },
  sequence: { useMaxWidth: false },
  gantt: { useMaxWidth: false },
  class: { useMaxWidth: false },
  state: { useMaxWidth: false },
  er: { useMaxWidth: false },
  journey: { useMaxWidth: false },
  pie: { useMaxWidth: false },
  requirement: { useMaxWidth: false },
  gitGraph: { useMaxWidth: false },
  c4: { useMaxWidth: false },
  mindmap: { useMaxWidth: false },
  timeline: { useMaxWidth: false },
  quadrantChart: { useMaxWidth: false },
  xyChart: { useMaxWidth: false },
  sankey: { useMaxWidth: false },
  block: { useMaxWidth: false },
} as const

const MERMAID_THEME_VARIABLES = {
  darkMode: true,
  background: 'transparent',
  primaryColor: '#2d2640',
  primaryTextColor: '#e8e8ee',
  primaryBorderColor: '#9d8df5',
  lineColor: '#c4c4cc',
  secondaryColor: '#1e1e28',
  tertiaryColor: '#12121a',
  mainBkg: '#2d2640',
  textColor: '#e8e8ee',
  titleColor: '#f4f4f5',
  nodeBorder: '#9d8df5',
  clusterBkg: '#1e1e28',
  edgeLabelBackground: '#1e1e28',
  actorBorder: '#9d8df5',
  actorBkg: '#2d2640',
  actorTextColor: '#e8e8ee',
  signalColor: '#e8e8ee',
  signalTextColor: '#e8e8ee',
  labelBoxBkgColor: '#2d2640',
  labelBoxBorderColor: '#9d8df5',
  labelTextColor: '#e8e8ee',
  taskBkgColor: '#7c6cf0',
  taskTextColor: '#f4f4f5',
  taskTextLightColor: '#f4f4f5',
  taskBorderColor: '#9d8df5',
  sectionBkgColor: '#1e1e28',
  altSectionBkgColor: '#2d2640',
  gridColor: '#71717a',
  todayLineColor: '#f472b6',
  classText: '#e8e8ee',
} as const

let mermaidReady: Promise<typeof import('mermaid').default> | null = null

function loadMermaid() {
  if (!mermaidReady) {
    mermaidReady = import('mermaid').then(({ default: mermaid }) => {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'loose',
        theme: 'dark',
        themeVariables: MERMAID_THEME_VARIABLES,
        fontFamily: 'Inter Tight, ui-sans-serif, system-ui, sans-serif',
        ...DIAGRAM_USE_MAX_WIDTH_FALSE,
      })
      return mermaid
    })
  }
  return mermaidReady
}

function nextDiagramId() {
  return `wf-mmd-${Math.random().toString(36).slice(2, 10)}`
}

function normalizeLang(lang: string) {
  return lang.trim().split(/\s+/)[0] ?? ''
}

export function isMermaidLang(lang: string | undefined) {
  const token = normalizeLang(lang ?? '')
  if (!token) return false
  const lower = token.toLowerCase()
  if (MERMAID_ALIASES.has(lower)) return true
  return MERMAID_LANG_RE.test(token)
}

export function mermaidSourceFromFence(lang: string, text: string) {
  const body = text.replace(/\r\n/g, '\n').trimEnd()
  const fenceLang = normalizeLang(lang)
  if (!fenceLang || fenceLang.toLowerCase() === 'mermaid' || fenceLang.toLowerCase() === 'mmd') {
    return body
  }

  const firstLine = body.split('\n')[0]?.trim() ?? ''
  const firstToken = normalizeLang(firstLine)
  if (firstToken && isMermaidLang(firstToken)) return body

  return `${fenceLang}\n${body}`
}

export function mermaidBlockHtml(source: string) {
  const normalized = source.replace(/\r\n/g, '\n').trimEnd()
  return `<div class="wf-mermaid wf-mermaid--pending wf-scroll wf-scroll--horizontal" role="img" aria-label="Diagram"><template class="wf-mermaid__source">${escapeHtml(normalized)}</template></div>\n`
}

function readMermaidSource(node: HTMLElement) {
  const template = node.querySelector('template.wf-mermaid__source')
  if (template?.textContent) return template.textContent

  const encoded = node.dataset.mermaidSource
  if (encoded) return decodeURIComponent(encoded)

  return ''
}

function readViewBoxSize(svg: SVGSVGElement): { width: number; height: number } {
  const viewBox = svg.getAttribute('viewBox')
  if (viewBox) {
    const parts = viewBox.split(/[\s,]+/).map((part) => Number.parseFloat(part))
    if (parts.length === 4 && parts[2] > 0 && parts[3] > 0) {
      return { width: parts[2], height: parts[3] }
    }
  }

  const width = Number.parseFloat(svg.getAttribute('width') ?? '')
  const height = Number.parseFloat(svg.getAttribute('height') ?? '')
  if (width > 0 && height > 0) return { width, height }

  try {
    const box = svg.getBBox()
    if (box.width > 0 && box.height > 0) return { width: box.width, height: box.height }
  } catch {
    // ponytail: getBBox throws when svg not in layout yet
  }

  return { width: 0, height: 0 }
}

export function mountMermaidSvg(container: HTMLElement, svgHtml: string) {
  container.innerHTML = svgHtml.trim()
  const svg = container.querySelector('svg')
  if (!(svg instanceof SVGSVGElement)) return

  const { width, height } = readViewBoxSize(svg)

  svg.style.display = 'block'
  svg.style.width = '100%'
  svg.style.maxWidth = '100%'
  svg.style.height = 'auto'
  svg.style.overflow = 'visible'
  svg.setAttribute('width', '100%')
  svg.removeAttribute('height')

  if (width > 0 && height > 0) {
    svg.style.aspectRatio = `${width} / ${height}`
    container.style.aspectRatio = `${width} / ${height}`
    container.style.width = '100%'
    if (!svg.getAttribute('viewBox')) {
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`)
    }
  }
}

export async function renderMermaidDiagram(source: string) {
  const mermaid = await loadMermaid()
  return mermaid.render(nextDiagramId(), source)
}

export async function hydrateMermaid(root: ParentNode) {
  const nodes = root.querySelectorAll<HTMLElement>('.wf-mermaid:not([data-mermaid-rendered])')
  if (nodes.length === 0) return

  const mermaid = await loadMermaid()

  for (const node of nodes) {
    const source = readMermaidSource(node)
    if (!source.trim()) {
      node.dataset.mermaidRendered = 'true'
      node.classList.remove('wf-mermaid--pending')
      continue
    }

    try {
      const { svg, bindFunctions } = await mermaid.render(nextDiagramId(), source)
      mountMermaidSvg(node, svg)
      bindFunctions?.(node)
      node.dataset.mermaidRendered = 'true'
      node.classList.remove('wf-mermaid--pending')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not render diagram'
      node.innerHTML = `<pre class="wf-mermaid__error">${escapeHtml(message)}</pre>`
      node.dataset.mermaidRendered = 'error'
      node.classList.remove('wf-mermaid--pending')
    }
  }
}

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
}

// ponytail: runnable fence gate — agents use typed langs, not only ```mermaid
if (!isMermaidLang('sequenceDiagram') || mermaidSourceFromFence('sequenceDiagram', 'A->>B') !== 'sequenceDiagram\nA->>B') {
  throw new Error('mermaid fence normalization failed')
}
