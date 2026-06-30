import { useRef, type KeyboardEvent, type RefObject } from 'react'
import { Upload, User } from 'lucide-react'

import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

export function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error || new Error('Failed to read avatar image'))
    reader.readAsDataURL(file)
  })
}

type ProfileEditableFieldProps<T extends string> = {
  field: T
  editingField: T | null
  onStartEdit: (field: T) => void
  onStopEdit: () => void
  disabled?: boolean
  displayClassName?: string
  placeholder: string
  value: string
  onChange: (value: string) => void
  multiline?: boolean
  inputIdPrefix?: string
  mono?: boolean
}

export function ProfileEditableField<T extends string>({
  field,
  editingField,
  onStartEdit,
  onStopEdit,
  disabled,
  displayClassName,
  placeholder,
  value,
  onChange,
  multiline,
  inputIdPrefix = 'wf-profile',
  mono,
}: ProfileEditableFieldProps<T>) {
  const isEditing = editingField === field
  const inputId = `${inputIdPrefix}-${field}`

  const stopOnEnter = (event: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    if (!multiline && event.key === 'Enter') {
      event.preventDefault()
      onStopEdit()
    }
  }

  if (isEditing) {
    if (multiline) {
      return (
        <Textarea
          id={inputId}
          className={cn(
            'wf-profile-badge__input wf-profile-badge__input--bio',
            mono && 'wf-profile-badge__input--mono',
          )}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onBlur={onStopEdit}
          onKeyDown={stopOnEnter}
          placeholder={placeholder}
          disabled={disabled}
          autoFocus
          rows={mono ? 10 : 4}
        />
      )
    }

    return (
      <Input
        id={inputId}
        className="wf-profile-badge__input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onBlur={onStopEdit}
        onKeyDown={stopOnEnter}
        placeholder={placeholder}
        disabled={disabled}
        autoFocus
      />
    )
  }

  return (
    <button
      type="button"
      className={cn(
        'wf-profile-badge__display',
        displayClassName,
        mono && 'wf-profile-badge__display--mono',
        !value.trim() && 'wf-profile-badge__display--empty',
      )}
      onClick={() => onStartEdit(field)}
      disabled={disabled}
    >
      {value.trim() || placeholder}
    </button>
  )
}

type ProfileBadgeAvatarProps = {
  avatarUrl: string
  disabled?: boolean
  fileName?: string
  inputRef: RefObject<HTMLInputElement | null>
  onPick: (file: File | null) => void
}

export function ProfileBadgeAvatar({
  avatarUrl,
  disabled,
  fileName,
  inputRef,
  onPick,
}: ProfileBadgeAvatarProps) {
  const fallbackInputRef = useRef<HTMLInputElement | null>(null)
  const resolvedRef = inputRef ?? fallbackInputRef

  return (
    <>
      <button
        type="button"
        className="wf-profile-badge__avatar"
        onClick={() => resolvedRef.current?.click()}
        disabled={disabled}
        aria-label="Upload avatar"
      >
        {avatarUrl ? (
          <img key={avatarUrl} src={avatarUrl} alt="" />
        ) : (
          <span className="wf-profile-badge__avatar-placeholder" aria-hidden="true">
            <User />
          </span>
        )}
        <span className="wf-profile-badge__avatar-overlay" aria-hidden="true">
          <Upload />
        </span>
      </button>
      <input
        ref={resolvedRef}
        type="file"
        accept="image/*"
        className="wf-user-settings__file-input"
        onChange={(event) => onPick(event.target.files?.[0] ?? null)}
      />
      {fileName ? <p className="wf-profile-badge__avatar-hint">{fileName}</p> : null}
    </>
  )
}
