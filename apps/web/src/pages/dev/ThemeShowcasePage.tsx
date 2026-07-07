import { useMemo, useState, type ReactNode } from 'react'

import { ThemeSwitcher } from '@/components/shell/ThemeSwitcher'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Textarea } from '@/components/ui/textarea'
import { useTheme } from '@/hooks/useTheme'

const PALETTE_TOKENS = [
  '--wf-bg',
  '--wf-text',
  '--wf-muted',
  '--wf-border',
  '--wf-border-strong',
  '--wf-surface',
  '--wf-primary',
  '--wf-violet',
  '--wf-cyan',
  '--wf-mint',
  '--wf-error',
  '--wf-success',
  '--wf-warning',
  '--wf-divider-color',
] as const

const SEMANTIC_TOKENS = [
  '--wf-accent',
  '--wf-accent-foreground',
  '--wf-scrollbar-thumb',
  '--wf-scrollbar-thumb-hover',
  '--wf-scrollbar-track',
  '--wf-notice-fg',
  '--wf-notice-muted',
  '--wf-control-fg',
  '--wf-control-fg-hover',
  '--wf-btn-fg',
  '--wf-btn-fg-inactive',
] as const

const TYPE_SAMPLES = [
  { token: '--wf-type-meta', label: 'Meta', sample: 'Panel meta · 10px' },
  { token: '--wf-type-caption', label: 'Caption', sample: 'Caption labels · 11px' },
  { token: '--wf-type-ui', label: 'UI', sample: 'Buttons and chrome · 12px' },
  { token: '--wf-type-body', label: 'Body', sample: 'Composer and settings body · 13px' },
] as const

function Swatch({ token }: { token: string }) {
  const style = useMemo(
    () => ({
      background: `var(${token})`,
      border: '1px solid var(--wf-border-strong)',
    }),
    [token],
  )

  return (
    <div className="wf-theme-showcase__swatch">
      <div className="wf-theme-showcase__swatch-chip" style={style} />
      <code>{token}</code>
    </div>
  )
}

function SpecCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="wf-theme-showcase__card">
      <h2>{title}</h2>
      {children}
    </section>
  )
}

export function ThemeShowcasePage() {
  const { theme } = useTheme()
  const [liveToken, setLiveToken] = useState('--wf-accent')
  const [liveValue, setLiveValue] = useState('')

  const scrollLines = useMemo(
    () => Array.from({ length: 40 }, (_, index) => `Scroll line ${index + 1} — hover the thumb, not the panel.`),
    [],
  )

  const applyLiveToken = () => {
    const value = liveValue.trim()
    if (!value) return
    document.documentElement.style.setProperty(liveToken, value)
  }

  const resetLiveToken = () => {
    document.documentElement.style.removeProperty(liveToken)
    setLiveValue('')
  }

  return (
    <div className="wf-theme-showcase">
      <header className="wf-theme-showcase__header">
        <div>
          <p className="wf-theme-showcase__eyebrow">UI lab · /dev/theme (or ?wf-dev=theme)</p>
          <h1>Theme &amp; token contract</h1>
          <p className="wf-theme-showcase__lede">
            Theme: <strong>{theme}</strong> — palette primitives, semantic aliases, type scale, and custom scrollbar
            thumbs (white default, accent purple on thumb hover in neo).
          </p>
        </div>
        <ThemeSwitcher />
      </header>

      <SpecCard title="Palette primitives">
        <div className="wf-theme-showcase__grid">
          {PALETTE_TOKENS.map((token) => (
            <Swatch key={token} token={token} />
          ))}
        </div>
      </SpecCard>

      <SpecCard title="Semantic aliases">
        <div className="wf-theme-showcase__grid">
          {SEMANTIC_TOKENS.map((token) => (
            <Swatch key={token} token={token} />
          ))}
        </div>
      </SpecCard>

      <SpecCard title="Type scale">
        <div className="wf-theme-showcase__type-list">
          {TYPE_SAMPLES.map(({ token, label, sample }) => (
            <div key={token} className="wf-theme-showcase__type-row">
              <code>{token}</code>
              <span className="wf-theme-showcase__type-label">{label}</span>
              <p className="wf-theme-showcase__type-sample" style={{ fontSize: `var(${token})` }}>
                {sample}
              </p>
            </div>
          ))}
        </div>
      </SpecCard>

      <SpecCard title="Scrollbar (ScrollArea + Textarea)">
        <div className="wf-theme-showcase__scroll-demo">
          <ScrollArea axis="vertical" inset="sm" className="wf-theme-showcase__scroll-panel">
            <div className="wf-theme-showcase__scroll-content">
              {scrollLines.map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
          </ScrollArea>
          <Textarea
            className="wf-theme-showcase__textarea"
            rows={6}
            defaultValue={scrollLines.join('\n')}
            aria-label="Scrollbar textarea sample"
          />
        </div>
        <p className="wf-theme-showcase__hint">
          WebKit uses <code>::-webkit-scrollbar-thumb</code> (no <code>scrollbar-color</code> — that blocks thumb
          hover). Gutter overrides live on each panel via <code>--wf-scroll-gutter-*</code>.
        </p>
      </SpecCard>

      <SpecCard title="Live token override (session only)">
        <div className="wf-theme-showcase__live">
          <label className="wf-theme-showcase__live-field">
            <span>Token</span>
            <input
              value={liveToken}
              onChange={(event) => setLiveToken(event.target.value)}
              spellCheck={false}
            />
          </label>
          <label className="wf-theme-showcase__live-field">
            <span>Value</span>
            <input
              value={liveValue}
              onChange={(event) => setLiveValue(event.target.value)}
              placeholder="#7c6a9e"
              spellCheck={false}
            />
          </label>
          <div className="wf-theme-showcase__live-actions">
            <button type="button" onClick={applyLiveToken}>
              Apply on &lt;html&gt;
            </button>
            <button type="button" onClick={resetLiveToken}>
              Reset token
            </button>
          </div>
        </div>
      </SpecCard>
    </div>
  )
}
