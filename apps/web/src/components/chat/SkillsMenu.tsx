import { Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { PopoverMenu, type PopoverItem } from '@/components/chat/PopoverMenu'
import { Button } from '@/components/ui/button'
import {
  fetchHermesSkills,
  type HermesSkillRow,
} from '@/lib/hermesCatalogApi'

type SkillsMenuProps = {
  /** Called when the user picks a skill. The composer dispatches
   *  the skill via the slash command pipeline; we don't insert
   *  `/skillname` into the textarea first. */
  onPick: (skill: HermesSkillRow) => void
}

/**
 * Skills discoverability surface. Click the trigger to open a list
 * of every installed skill. Picking one dispatches it immediately
 * (no Enter needed) — the user has already committed by clicking.
 * Shares the `.wf-popover` visual with the slash palette.
 */
export function SkillsMenu({ onPick }: SkillsMenuProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [skills, setSkills] = useState<HermesSkillRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    void fetchHermesSkills()
      .then((rows) => {
        setSkills(rows)
      })
      .catch((err) => {
        setSkills([])
        setError(err instanceof Error ? err.message : 'Could not load skills')
      })
  }, [])

  // Close on outside click. We bail when the target is the trigger
  // itself (so the toggle in onClick has a chance to flip state
  // before we re-close) or inside the popover (so picking an item
  // doesn't race the close).
  useEffect(() => {
    if (!isOpen) return
    const onMouseDown = (e: MouseEvent) => {
      const target = e.target as Node | null
      if (!target) return
      if (triggerRef.current?.contains(target)) return
      if (target instanceof Element && target.closest('.wf-popover')) return
      setIsOpen(false)
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [isOpen])

  const items: PopoverItem[] = skills.map((skill) => ({
    id: skill.name,
    name: `/${skill.name}`,
    description: skill.description,
  }))

  return (
    <>
      <Button
        ref={triggerRef}
        type="button"
        variant="toolbar"
        size="toolbarText"
        aria-label="Browse skills"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((v) => !v)}
      >
        <Sparkles aria-hidden="true" />
        <span>Skills</span>
      </Button>
      <PopoverMenu
        anchor={triggerRef.current}
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        header={{ label: 'Skills', hint: 'click to invoke' }}
        items={items}
        onSelect={(item) => {
          const skill = skills.find((s) => s.name === item.id)
          if (skill) onPick(skill)
          setIsOpen(false)
        }}
        emptyMessage={error ?? 'No skills installed'}
        minWidth={380}
      />
    </>
  )
}
