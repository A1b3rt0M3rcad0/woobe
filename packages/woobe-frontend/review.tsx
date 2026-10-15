// Dedicated development entry. The production build only includes index.html.
import { createRoot } from 'react-dom/client'
import { Gallery } from '../../tests/e2e/review/Gallery'
import './src/index.css'
import './src/styles/chat-surface-details.css'
createRoot(document.getElementById('root')!).render(<Gallery />)
