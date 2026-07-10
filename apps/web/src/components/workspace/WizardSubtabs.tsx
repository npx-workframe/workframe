export type WizardSubtab = {
  id: string
  label: string
}

type WizardSubtabsProps = {
  tabs: readonly WizardSubtab[]
  activeTab: string
  onTabChange: (tabId: string) => void
  ariaLabel: string
}

export function WizardSubtabs({ tabs, activeTab, onTabChange, ariaLabel }: WizardSubtabsProps) {
  return (
    <div className="wf-wizard-subtabs" role="tablist" aria-label={ariaLabel}>
      {tabs.map(({ id, label }) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={activeTab === id}
          className={`wf-wizard-subtabs__btn${activeTab === id ? ' is-active' : ''}`}
          onClick={() => onTabChange(id)}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
