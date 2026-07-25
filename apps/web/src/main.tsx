import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App.tsx'
import { syncIphoneStandalonePwaAttribute } from '@/lib/iphoneStandalonePwa'
import './index.css'

syncIphoneStandalonePwaAttribute()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
