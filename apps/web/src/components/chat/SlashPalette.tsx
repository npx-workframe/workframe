import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react'

import { PopoverMenu, type PopoverItem, type PopoverMenuHandle } from '@/components/chat/PopoverMenu'
import { fetchHermesCommands, type HermesSlashCommand } from '@/lib/hermesCatalogApi'

type SlashPaletteProps = {
  anchor: HTMLTextAreaElement | null
  isOpen: boolean
  value: string
  onPick: (command: HermesSlashCommand) => void
}

export type SlashPaletteHandle = PopoverMenuHandle

/**
 * Slash-command picker. Renders only when the composer value starts
 * with `/` and the command catalog has loaded. Shares the `.wf-popover`
 * family with the skills menu.
 */
export const SlashPalette = forwardRef<SlashPaletteHandle, SlashPaletteProps>(
  function SlashPalette({ anchor, isOpen, value, onPick }, ref) {
    const [commands, setCommands] = useState<HermesSlashCommand[]>([])
    const menuRef = useRef<PopoverMenuHandle>(null)
    const fetchedRef = useRef(false)

    useEffect(() => {
      if (fetchedRef.current) return
      fetchedRef.current = true
      fetchHermesCommands()
        .then((rows) => setCommands(rows))
        .catch(() => setCommands([]))
    }, [])

    useImperativeHandle(
      ref,
      () => ({
        up: () => menuRef.current?.up(),
        down: () => menuRef.current?.down(),
        accept: () => menuRef.current?.accept(),
      }),
      [],
    )

    // Don't block rendering on catalog load — show palette immediately,
    // the empty state handles the loading gracefully.
    if (!isOpen) return null

    const filter = value.startsWith('/') ? value.slice(1) : ''

    const items: PopoverItem[] = commands.map((cmd) => ({
      id: cmd.name,
      name: cmd.name,
      description: cmd.description,
      aliases: cmd.aliases,
      argsHint: cmd.args_hint || undefined,
    }))

    return (
      <PopoverMenu
        ref={menuRef}
        anchor={anchor}
        isOpen={isOpen}
        onClose={() => {
          // The slash palette doesn't own its open state — the
          // composer derives it from the textarea value.
        }}
        header={{ label: 'Slash commands', hint: '↑↓ navigate · Tab complete · ↵ dispatch' }}
        items={items}
        onSelect={(item) => {
          const cmd = commands.find((c) => c.name === item.id)
          if (cmd) onPick(cmd)
        }}
        filter={filter}
        emptyMessage={`No commands match /${filter}`}
      />
    )
  },
)
