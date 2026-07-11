import { useEffect, useMemo, useState } from 'react'

import { SettingsPanelBody } from '@/components/workspace/SettingsPanelBody'
import { SettingsSheetFrame } from '@/components/workspace/SettingsSheetFrame'
import { PanelStatus } from '@/components/ui/PanelPrimitives'
import { fetchHermesSkills, type HermesSkillRow } from '@/lib/hermesCatalogApi'
import { cn } from '@/lib/utils'

type SkillsDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function SkillsDialog({ open, onOpenChange }: SkillsDialogProps) {
  const [skills, setSkills] = useState<HermesSkillRow[]>([])
  const [filter, setFilter] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) {
      setFilter('')
      return
    }
    setError(null)
    setLoading(true)
    fetchHermesSkills()
      .then(setSkills)
      .catch((err) => {
        setSkills([])
        setError(err instanceof Error ? err.message : 'Could not load skills')
      })
      .finally(() => setLoading(false))
  }, [open])

  const filtered = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    if (!needle) return skills
    return skills.filter((skill) =>
      skill.name.toLowerCase().includes(needle) ||
      skill.description.toLowerCase().includes(needle) ||
      (skill.category ?? '').toLowerCase().includes(needle),
    )
  }, [skills, filter])

  const groups = useMemo(() => {
    const map = new Map<string, HermesSkillRow[]>()
    for (const skill of filtered) {
      const category = skill.category || 'Uncategorized'
      const bucket = map.get(category) ?? []
      bucket.push(skill)
      map.set(category, bucket)
    }
    return [...map.entries()].map(([category, rows]) => ({ category, rows }))
  }, [filtered])

  return (
    <SettingsSheetFrame
      open={open}
      onClose={() => onOpenChange(false)}
      title="Skills"
      sectionLabel="Installed skills"
      summary={`${filtered.length} installed`}
      titleId="wf-skills-dialog-title"
      sheetClassName="wf-dialog-content--settings-compact"
      loading={loading}
    >
      <SettingsPanelBody error={error}>
        <input
          type="search"
          className="wf-dialog__search"
          placeholder="Filter skills…"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          aria-label="Filter skills"
        />

        <div className="wf-model-picker__list wf-model-picker__list--embedded wf-scroll wf-scroll--vertical">
          {groups.map((group) => (
            <div key={group.category} className="wf-dialog__group">
              <p className="wf-dialog__group-label">{group.category}</p>
              {group.rows.map((skill) => (
                <div
                  key={skill.name}
                  className={cn('wf-dialog__option wf-dialog__option--single-line', !skill.enabled && 'opacity-60')}
                >
                  <span className="wf-dialog__option-label">{skill.name}</span>
                  {!skill.enabled ? <span className="wf-dialog__option-tag">off</span> : null}
                </div>
              ))}
            </div>
          ))}
          {!error && filtered.length === 0 ? (
            <PanelStatus>{loading ? 'Loading skills…' : 'No skills match this filter.'}</PanelStatus>
          ) : null}
        </div>
      </SettingsPanelBody>
    </SettingsSheetFrame>
  )
}
