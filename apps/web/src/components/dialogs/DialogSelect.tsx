import { ChevronDown } from 'lucide-react'

import {
  DropdownMenu,
  DropdownMenuCheckItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'

export type DialogSelectOption = {
  value: string
  label: string
  description?: string
}

type DialogSelectProps = {
  id?: string
  value: string
  onValueChange: (value: string) => void
  options: DialogSelectOption[]
  disabled?: boolean
  placeholder?: string
  className?: string
}

export function DialogSelect({
  id,
  value,
  onValueChange,
  options,
  disabled,
  placeholder = 'Select…',
  className,
}: DialogSelectProps) {
  const selected = options.find((option) => option.value === value)

  return (
    <DropdownMenu>
      <div className={cn('wf-dialog-select', className)}>
        <DropdownMenuTrigger asChild disabled={disabled}>
          <button
            id={id}
            type="button"
            className="wf-dialog-select__control wf-dialog-select__trigger"
            disabled={disabled}
            aria-haspopup="listbox"
            aria-expanded={undefined}
          >
            <span className="wf-dialog-select__value">{selected?.label ?? placeholder}</span>
          </button>
        </DropdownMenuTrigger>
        <ChevronDown className="wf-dialog-select__chevron" aria-hidden="true" />
      </div>
      <DropdownMenuContent
        className="wf-dialog-select__menu wf-scroll wf-scroll--vertical"
        align="start"
        sideOffset={4}
      >
        {options.map((option) => (
          <DropdownMenuCheckItem
            key={option.value || '__empty'}
            checked={option.value === value}
            className={cn('wf-dialog-select__item', option.value === value && 'is-selected')}
            onSelect={() => onValueChange(option.value)}
          >
            <div className="wf-dialog-select__item-copy">
              <span className="wf-dialog-select__item-label">{option.label}</span>
              {option.description ? (
                <span className="wf-dialog-select__item-hint">{option.description}</span>
              ) : null}
            </div>
          </DropdownMenuCheckItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
