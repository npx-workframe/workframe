import { useCallback, useState } from 'react'

import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'

/** Local error state wired to the centralized Workframe error formatter. */
export function useWorkframeError() {
  const [error, setError] = useState('')
  const clearError = useCallback(() => setError(''), [])
  const setFromError = useCallback((err: unknown, context?: string) => {
    setError(formatWorkframeErrorMessage(err, context))
  }, [])
  return { error, setError, clearError, setFromError, hasError: Boolean(error) }
}
