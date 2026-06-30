import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'

const COMPOSER_MAX_VH = 30
const COMPOSER_EXPAND_EXTRA_PX = 120

function maxComposerPx() {
  return Math.round(window.innerHeight * (COMPOSER_MAX_VH / 100))
}

export function useVerticalSplit(initialComposerPx = 120, minComposerPx = 0) {
  const [composerHeight, setComposerHeight] = useState(initialComposerPx)
  const dragging = useRef(false)
  const startY = useRef(0)
  const startHeight = useRef(initialComposerPx)
  const minPx = Math.max(0, minComposerPx)

  useEffect(() => {
    setComposerHeight((current) => {
      const maxPx = maxComposerPx()
      const floor = minPx > 0 ? minPx : current
      return Math.min(maxPx, Math.max(floor, current))
    })
  }, [minPx])

  const onSashPointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      dragging.current = true
      startY.current = event.clientY
      startHeight.current = composerHeight
      event.currentTarget.setPointerCapture(event.pointerId)
    },
    [composerHeight],
  )

  const onSashPointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (!dragging.current) return
      const delta = startY.current - event.clientY
      const maxPx = maxComposerPx()
      const floor = minPx > 0 ? minPx : 56
      const next = Math.min(maxPx, Math.max(floor, startHeight.current + delta))
      setComposerHeight(next)
    },
    [minPx],
  )

  const onSashPointerUp = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    dragging.current = false
    event.currentTarget.releasePointerCapture(event.pointerId)
  }, [])

  const collapseComposer = useCallback(() => {
    if (minPx > 0) setComposerHeight(minPx)
  }, [minPx])

  const expandComposer = useCallback(() => {
    const floor = minPx > 0 ? minPx : 120
    setComposerHeight(Math.min(maxComposerPx(), floor + COMPOSER_EXPAND_EXTRA_PX))
  }, [minPx])

  useEffect(() => {
    const onResize = () => {
      setComposerHeight((current) => {
        const maxPx = maxComposerPx()
        const floor = minPx > 0 ? minPx : current
        return Math.min(maxPx, Math.max(floor, current))
      })
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [minPx])

  return {
    composerHeight,
    composerMinPx: minPx,
    composerMaxPx: maxComposerPx(),
    onSashPointerDown,
    onSashPointerMove,
    onSashPointerUp,
    collapseComposer,
    expandComposer,
  }
}

export { COMPOSER_MAX_VH }
