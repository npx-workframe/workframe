/** Color + gradient, orbs, vignette — no texture grid. */
export function AtmosphereBg() {
  return (
    <div className="wf-atmosphere-bg" aria-hidden="true">
      <div className="wf-atmosphere-bg__gradient" />
      <div className="wf-atmosphere-bg__orb wf-atmosphere-bg__orb--primary" />
      <div className="wf-atmosphere-bg__orb wf-atmosphere-bg__orb--secondary" />
      <div className="wf-atmosphere-bg__overlay" />
    </div>
  )
}
