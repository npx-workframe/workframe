import { useCallback, useRef, type ChangeEvent, type ReactElement } from 'react'

import { readFileAsDataUrl } from '@/components/workspace/profileBadge'
import { validateAvatarFile } from '@/lib/workframeErrors'

export function useAvatarFileUpload(onChange: (url: string) => void) {
  const inputRef = useRef<HTMLInputElement | null>(null)

  const openFilePicker = useCallback(() => {
    inputRef.current?.click()
  }, [])

  const onFileChange = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0] ?? null
      event.target.value = ''
      if (!file) return
      const invalid = validateAvatarFile(file)
      if (invalid) return
      const dataUrl = await readFileAsDataUrl(file)
      onChange(dataUrl)
    },
    [onChange],
  )

  const fileInput: ReactElement = (
    <input
      ref={inputRef}
      type="file"
      accept="image/png,image/jpeg,image/webp,image/gif"
      className="sr-only"
      onChange={(e) => void onFileChange(e)}
    />
  )

  return { openFilePicker, fileInput }
}
