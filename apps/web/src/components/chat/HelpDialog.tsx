import { useEffect, useMemo, useState } from 'react'

import { DialogFrame } from '@/components/dialogs/DialogFrame'
import { ScrollArea } from '@/components/ui/scroll-area'
import { fetchHermesCommands, type HermesSlashCommand } from '@/lib/hermesCatalogApi'

type HelpDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

type Group = { category: string; commands: HermesSlashCommand[] }

export function HelpDialog({ open, onOpenChange }: HelpDialogProps) {
  const [commands, setCommands] = useState<HermesSlashCommand[]>([])
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    if (!open) {
      setFilter('')
      return
    }
    setError(null)
    fetchHermesCommands()
      .then(setCommands)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load commands'))
  }, [open])

  const groups = useMemo<Group[]>(() => {
    const needle = filter.trim().toLowerCase()
    const filtered = needle
      ? commands.filter(
          (c) =>
            c.name.toLowerCase().includes(needle) ||
            c.description.toLowerCase().includes(needle) ||
            (c.aliases ?? []).some((a) => a.toLowerCase().includes(needle)),
        )
      : commands
    const map = new Map<string, HermesSlashCommand[]>()
    for (const cmd of filtered) {
      const bucket = map.get(cmd.category) ?? []
      bucket.push(cmd)
      map.set(cmd.category, bucket)
    }
    return [...map.entries()].map(([category, list]) => ({ category, commands: list }))
  }, [commands, filter])

  return (
    <DialogFrame
      open={open}
      onOpenChange={onOpenChange}
      title="Slash commands"
      description="Type a command in the composer (start with /) and press Enter. Wired commands execute locally; others are placeholders for upcoming slices."
      contentClassName="wf-dialog--help"
    >
      <input
        type="search"
        className="wf-dialog__search"
        placeholder="Filter commands…"
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
        autoFocus
        aria-label="Filter commands"
      />
      {error ? <p className="wf-dialog__error">{error}</p> : null}
      <ScrollArea axis="vertical" className="wf-dialog__list">
        {groups.map((group) => (
          <div key={group.category} className="wf-dialog__group">
            <p className="wf-dialog__group-label">{group.category}</p>
            {group.commands.map((cmd) => (
              <div key={cmd.name} className="wf-dialog__help-row">
                <span className="wf-dialog__option-label">
                  {cmd.name}
                  {cmd.aliases && cmd.aliases.length > 0 ? (
                    <span className="wf-dialog__option-aliases">
                      {cmd.aliases.map((a) => ` ${a}`).join('')}
                    </span>
                  ) : null}
                </span>
                {cmd.args_hint ? (
                  <span className="wf-dialog__option-id">{cmd.args_hint}</span>
                ) : null}
                <span className="wf-dialog__option-desc">{cmd.description}</span>
                {cmd.wired === false ? (
                  <span className="wf-dialog__option-tag" aria-label="Not yet wired">
                    wip
                  </span>
                ) : null}
              </div>
            ))}
          </div>
        ))}
      </ScrollArea>
    </DialogFrame>
  )
}
