import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Store } from './pages/Store'
import { AppProvider } from './state/app'
import { LiveProvider } from './state/live'

export default function App() {
  return (
    <AppProvider>
      <LiveProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Store />} />
              <Route path="painel" element={<Dashboard />} />
              <Route path="dashboard" element={<Navigate to="/painel" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </LiveProvider>
    </AppProvider>
  )
}
