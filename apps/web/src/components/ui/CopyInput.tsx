import { useCallback, useState } from 'react'

import { cn } from '@/lib/utils'

type CopyInputProps = {
  value: string
  label?: string
  id?: string
  className?: string
  mono?: boolean
  /** Pill field → round copy chip; otherwise chip radius = control radius + inset. */
  pill?: boolean
}

function CopyIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="9" y="9" width="11" height="11" rx="2" stroke="currentColor" strokeWidth="1.75" />
      <path
        d="M5 15V5a2 2 0 0 1 2-2h10"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M5 12.5l4.5 4.5L19 7.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function CopyInput({ value, label, id, className, mono = true, pill = false }: CopyInputProps) {
  const [copied, setCopied] = useState(false)

  const copy = useCallback(async () => {
    if (!value) return
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard unavailable */
    }
  }, [value])

  return (
    <div className={cn('wf-copy-input', pill && 'wf-copy-input--pill', className)}>
      <input
        id={id}
        readOnly
        value={value}
        aria-label={label}
        className={cn('wf-copy-input__value', mono && 'wf-copy-input__value--mono')}
      />
      <button
        type="button"
        className="wf-copy-input__btn"
        onClick={() => void copy()}
        disabled={!value}
        aria-label={copied ? 'Copied' : label ? `Copy ${label}` : 'Copy'}
      >
        {copied ? <CheckIcon /> : <CopyIcon />}
      </button>
    </div>
  )
}
