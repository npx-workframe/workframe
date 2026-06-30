import { useCallback, useEffect, useRef } from 'react'

/** Debounce rapid callbacks (e.g. SSE room reload storms). */
export function useDebouncedCallback<T extends (...args: never[]) => void>(
  callback: T,
  delayMs: number,
): T {
  const callbackRef = useRef(callback)
  const timerRef = useRef<number | null>(null)

  callbackRef.current = callback

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current)
    }
  }, [])

  return useCallback((...args: Parameters<T>) => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current)
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null
      callbackRef.current(...args)
    }, delayMs)
  }, [delayMs]) as T
}
