type BootScreenProps = {
  label?: string
}

export function BootScreen({ label = 'Loading Workframe' }: BootScreenProps) {
  return (
    <div className="wf-boot-screen" role="status" aria-live="polite" aria-busy="true">
      <p className="wf-boot-screen__label">{label}</p>
      <div
        className="wf-boot-screen__track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="wf-boot-screen__bar" />
      </div>
    </div>
  )
}
