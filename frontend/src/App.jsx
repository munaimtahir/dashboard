import React from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { clearToken, getToken } from './api.js'
import Login from './pages/Login.jsx'
import Overview from './pages/Overview.jsx'
import AppDetail from './pages/AppDetail.jsx'
import Discover from './pages/Discover.jsx'
import Backups from './pages/Backups.jsx'

function RequireAuth({ children }) {
  const loc = useLocation()
  const token = getToken()
  if (!token) return <Navigate to="/login" replace state={{ from: loc.pathname }} />
  return children
}

export default function App() {
  // Quick escape hatch: if token is invalid, backend returns 401 and user can clear.
  // Provide a small keyboard shortcut: Shift+Esc clears token.
  React.useEffect(() => {
    function onKey(e) {
      if (e.shiftKey && e.key === 'Escape') {
        clearToken()
        window.location.href = '/login'
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<RequireAuth><Overview /></RequireAuth>} />
      <Route path="/app/:key" element={<RequireAuth><AppDetail /></RequireAuth>} />
      <Route path="/discover" element={<RequireAuth><Discover /></RequireAuth>} />
      <Route path="/backups" element={<RequireAuth><Backups /></RequireAuth>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
