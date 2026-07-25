import { useEffect } from 'react'

import { syncIphoneStandalonePwaAttribute } from '@/lib/iphoneStandalonePwa'

export function useIphoneStandalonePwa(): void {
  useEffect(() => {
    const sync = () => {
      syncIphoneStandalonePwaAttribute()
    }

    sync()
    const mq = window.matchMedia('(display-mode: standalone)')
    mq.addEventListener('change', sync)
    return () => mq.removeEventListener('change', sync)
  }, [])
}
