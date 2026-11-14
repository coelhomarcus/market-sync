import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

createRoot(document.getElementById('root')!).render(
  // sem StrictMode: em dev ele dispararia cada consulta duas vezes e duplicaria as métricas
  <App />,
)
