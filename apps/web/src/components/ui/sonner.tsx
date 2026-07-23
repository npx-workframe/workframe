import { Toaster as Sonner, type ToasterProps } from 'sonner'
import { isDarkTheme, isTheme } from '@/lib/theme'

function toasterTheme(): 'dark' | 'light' {
  if (typeof document === 'undefined') return 'light'
  const theme = document.documentElement.dataset.theme
  return isTheme(theme) && isDarkTheme(theme) ? 'dark' : 'light'
}

export function Toaster({ ...props }: ToasterProps) {
  return (
    <Sonner
      theme={toasterTheme()}
      className="wf-toaster"
      toastOptions={{
        classNames: {
          toast: 'wf-toast',
          title: 'wf-toast__title',
          description: 'wf-toast__description',
          actionButton: 'wf-toast__action',
          cancelButton: 'wf-toast__cancel',
        },
      }}
      {...props}
    />
  )
}
