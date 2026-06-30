import { Input, type InputProps } from '@/components/ui/input'
import { savedSecretPlaceholder } from '@/lib/secretField'

type SecretInputProps = Omit<InputProps, 'type'> & {
  saved?: boolean
  emptyPlaceholder?: string
}

export function SecretInput({
  saved = false,
  emptyPlaceholder = 'Paste secret',
  placeholder,
  ...props
}: SecretInputProps) {
  return (
    <Input
      type="password"
      autoComplete="off"
      placeholder={placeholder ?? savedSecretPlaceholder(saved, emptyPlaceholder)}
      {...props}
    />
  )
}
