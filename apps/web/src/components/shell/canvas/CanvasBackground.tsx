import { getThemeCanvasTexture } from '@/lib/canvas-layers'
import { useDocumentTheme } from '@/hooks/useDocumentTheme'

import { AtmosphereBg } from '@/components/shell/canvas/AtmosphereBg'
import { DotGrid } from '@/components/shell/canvas/DotGrid'
import { MoleskineGrid } from '@/components/shell/canvas/MoleskineGrid'

/** Fixed canvas behind shell: atmosphere + per-theme texture component. */
export function CanvasBackground() {
  const theme = useDocumentTheme()
  const texture = getThemeCanvasTexture(theme)

  return (
    <div className="wf-canvas" aria-hidden="true">
      <AtmosphereBg />
      {texture === 'dots' ? <DotGrid /> : <MoleskineGrid />}
    </div>
  )
}
