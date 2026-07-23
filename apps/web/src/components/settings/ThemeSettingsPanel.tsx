import { useState } from 'react'

import { useTheme } from '@/hooks/useTheme'
import type { Theme } from '@/lib/theme'
import { workframeAuthApi } from '@/lib/workframeAuthApi'
import { ThemePickerGrid } from '@/components/settings/ThemePickerGrid'
import { WorkframeNotice } from '@/components/ui/WorkframeNotice'

export function ThemeSettingsPanel() {
  const { theme, setTheme } = useTheme()
  const [saveError, setSaveError] = useState('')

  function selectTheme(next: Theme) {
    setTheme(next)
    setSaveError('')
    void workframeAuthApi.updateMe({ theme: next }).catch((error) => {
      setSaveError(error instanceof Error ? error.message : 'Could not save your theme.')
    })
  }

  return (
    <>
      {saveError ? <WorkframeNotice message={saveError} className="wf-notice--wizard" /> : null}
      <ThemePickerGrid value={theme} onChange={selectTheme} />
    </>
  )
}
