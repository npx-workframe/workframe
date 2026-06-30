import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App.tsx'
import './index.css'
import './styles/themes/architectonic.overrides.css'
import './styles/themes/brutal.overrides.css'
import './styles/themes/neo.overrides.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
