import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import { ScrollArea } from '@/components/ui/scroll-area'

/**
 * A single item in a popover. Slash commands, skills, or anything else
 * that the user can invoke from the composer. The shape is the same so
 * the visual is identical regardless of what's being listed.
 */
export type PopoverItem = {
  /** Stable id for React keys. Typically the command or skill name. */
  id: string
  /** Display name (e.g. "/new" or "/blackbox"). Shown mono, bold. */
  name: string
  /** Second line — tagline, role, or description. */
  description?: string
  /** Optional avatar for agent mention rows. */
  avatarUrl?: string | null
  /** Optional alternative names shown next to the name. */
  aliases?: string[]
  /** Args hint, shown right-aligned in the row header. */
  argsHint?: string
  /** Free-form meta node (e.g. a "wip" badge) shown under the description. */
  meta?: ReactNode
}

type PopoverMenuProps = {
  /** Element the menu anchors to. The menu sits above the anchor's top
   *  edge, with its bottom at `top - GAP`. */
  anchor: HTMLElement | null
  isOpen: boolean
  /** Called on Escape and (for popovers the parent owns) any other
   *  dismissal action. The parent decides what to do — for the slash
   *  palette it's a no-op since open state is derived from the
   *  textarea value; for the skills menu it flips internal state. */
  onClose: () => void
  header: { label: string; hint: string }
  items: PopoverItem[]
  /** Filter the items by this token (case-insensitive starts-with on
   *  name + aliases, contains on description). Empty string = no
   *  filter. */
  filter?: string
  /** What to show when the filter matches nothing. */
  emptyMessage?: string
  /** Called when the user clicks an item or accepts the current
   *  selection via keyboard. */
  onSelect: (item: PopoverItem) => void
  /** Minimum width — the menu is at least this wide even if the
   *  anchor is narrower. */
  minWidth?: number
}

export type PopoverMenuHandle = {
  up: () => void
  down: () => void
  accept: () => void
}

const VIEWPORT_MARGIN = 8
const GAP = 6
const MAX_HEIGHT = 360
const MIN_WIDTH = 360
const HEADER_HEIGHT = 41

/**
 * Shared popover primitive for the composer's inline menus. Positioned
 * with `position: fixed` so ancestor `overflow: hidden` (common in
 * panel layouts) can't clip it. Bottom-edge-up to the anchor so
 * shorter content doesn't leave a visual gap. Single source of
 * truth for the visual language shared by the slash palette and the
 * skills menu.
 */
export const PopoverMenu = forwardRef<PopoverMenuHandle, PopoverMenuProps>(
  function PopoverMenu(
    { anchor, isOpen, onClose, header, items, onSelect, filter, emptyMessage, minWidth = MIN_WIDTH },
    ref,
  ) {
    const [selectedIndex, setSelectedIndex] = useState(0)
    const [pos, setPos] = useState<{ bottom: number; left: number; width: number; maxHeight: number } | null>(null)
    const itemRefs = useRef<Array<HTMLButtonElement | null>>([])

    const filtered = useMemo(() => {
      if (!filter) return items
      const token = filter.toLowerCase()
      return items.filter((item) => {
        if (item.name.toLowerCase().startsWith(token)) return true
        if (item.name.slice(1).toLowerCase().startsWith(token)) return true
        if (item.aliases?.some((a) => a.toLowerCase().startsWith(token) || a.slice(1).toLowerCase().startsWith(token))) return true
        return item.description?.toLowerCase().includes(token) ?? false
      })
    }, [items, filter])

    // Reset selection to the top whenever the filter changes so ↑/↓
    // don't point past the end of a shorter list.
    useEffect(() => {
      setSelectedIndex(0)
    }, [filter])

    // Scroll the selected item into view as the user navigates.
    useEffect(() => {
      const el = itemRefs.current[selectedIndex]
      if (el) el.scrollIntoView({ block: 'nearest' })
    }, [selectedIndex])

    // Position the menu with its BOTTOM edge just above the anchor.
    // Re-measure on scroll / resize / focus changes so a panel move
    // doesn't strand the menu.
    useEffect(() => {
      if (!isOpen || !anchor) {
        setPos(null)
        return
      }
      const measure = () => {
        const rect = anchor.getBoundingClientRect()
        const maxWidth = Math.min(
          Math.max(minWidth, rect.width),
          window.innerWidth - VIEWPORT_MARGIN * 2,
        )
        let left = rect.left
        if (left + maxWidth > window.innerWidth - VIEWPORT_MARGIN) {
          left = window.innerWidth - VIEWPORT_MARGIN - maxWidth
        }
        if (left < VIEWPORT_MARGIN) left = VIEWPORT_MARGIN
        const bottom = window.innerHeight - rect.top + GAP
        const maxHeight = Math.min(
          MAX_HEIGHT,
          Math.max(120, rect.top - GAP - VIEWPORT_MARGIN),
        )
        setPos({ bottom, left, width: maxWidth, maxHeight })
      }
      measure()
      const onScroll = () => measure()
      const onResize = () => measure()
      window.addEventListener('scroll', onScroll, true)
      window.addEventListener('resize', onResize)
      return () => {
        window.removeEventListener('scroll', onScroll, true)
        window.removeEventListener('resize', onResize)
      }
    }, [isOpen, anchor, minWidth])

    // Escape closes the menu. Capture phase so it fires before the
    // textarea's keydown handler swallows it.
    useEffect(() => {
      if (!isOpen) return
      const onKey = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          e.stopPropagation()
          onClose()
        }
      }
      window.addEventListener('keydown', onKey, true)
      return () => window.removeEventListener('keydown', onKey, true)
    }, [isOpen, onClose])

    useImperativeHandle(
      ref,
      () => ({
        up: () => {
          if (filtered.length === 0) return
          setSelectedIndex((idx) => (idx - 1 + filtered.length) % filtered.length)
        },
        down: () => {
          if (filtered.length === 0) return
          setSelectedIndex((idx) => (idx + 1) % filtered.length)
        },
        accept: () => {
          const item = filtered[selectedIndex]
          if (item) onSelect(item)
        },
      }),
      [filtered, selectedIndex, onSelect],
    )

    if (!isOpen || !pos) return null

    const style: React.CSSProperties = {
      position: 'fixed',
      bottom: pos.bottom,
      left: pos.left,
      width: pos.width,
      maxHeight: pos.maxHeight,
      zIndex: 1000,
    }

    return (
      <div
        className="wf-popover"
        role="listbox"
        aria-label={header.label}
        style={style}
      >
        <div className="wf-popover__header">
          <span className="wf-popover__label">{header.label}</span>
          <span className="wf-popover__hint">{header.hint}</span>
        </div>
        <ScrollArea
          axis="vertical"
          className="wf-popover__list"
          style={{ maxHeight: pos.maxHeight - HEADER_HEIGHT }}
        >
          {filtered.length === 0 ? (
            <p className="wf-popover__empty">{emptyMessage ?? 'No matches'}</p>
          ) : (
            filtered.map((item, idx) => {
              const isSelected = idx === selectedIndex
              return (
                <button
                  type="button"
                  key={item.id}
                  ref={(el) => {
                    itemRefs.current[idx] = el
                  }}
                  role="option"
                  aria-selected={isSelected}
                  data-selected={isSelected ? 'true' : undefined}
                  className="wf-popover__row"
                  onMouseEnter={() => setSelectedIndex(idx)}
                  onClick={() => onSelect(item)}
                >
                  {item.avatarUrl ? (
                    <img
                      src={item.avatarUrl}
                      alt=""
                      className="wf-popover__row-avatar"
                      aria-hidden="true"
                    />
                  ) : null}
                  <div className="wf-popover__row-copy">
                    <div className="wf-popover__row-header">
                      <span className="wf-popover__row-name">{item.name}</span>
                      {item.aliases && item.aliases.length > 0 ? (
                        <span className="wf-popover__row-aliases">
                          {item.aliases.map((a) => ` ${a}`).join('')}
                        </span>
                      ) : null}
                      {item.argsHint ? (
                        <span className="wf-popover__row-args">{item.argsHint}</span>
                      ) : null}
                    </div>
                    {item.description ? (
                      <span className="wf-popover__row-desc">{item.description}</span>
                    ) : null}
                    {item.meta ? <div className="wf-popover__row-meta">{item.meta}</div> : null}
                  </div>
                </button>
              )
            })
          )}
        </ScrollArea>
      </div>
    )
  },
)
