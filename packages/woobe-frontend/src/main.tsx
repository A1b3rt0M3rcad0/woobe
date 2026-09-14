import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'
import './styles/dashboard-reference.css'
import './styles/dashboard-fill.css'
import './styles/chat-surface-details.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
