/** Fixed canvas behind shell: gradient, orbs, overlay, grid (theme tokens). */
export function CanvasBackground() {
  return (
    <div className="wf-canvas" aria-hidden="true">
      <div className="wf-canvas__gradient" />
      <div className="wf-canvas__orb wf-canvas__orb--primary" />
      <div className="wf-canvas__orb wf-canvas__orb--secondary" />
      <div className="wf-canvas__overlay" />
      <div className="wf-canvas__grid" />
    </div>
  )
}
