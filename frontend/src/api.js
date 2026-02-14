export function getToken() {
  return localStorage.getItem('dash_token') || ''
}

export function setToken(t) {
  localStorage.setItem('dash_token', t)
}

export function clearToken() {
  localStorage.removeItem('dash_token')
}

async function request(path, opts = {}) {
  const token = getToken()
  const headers = new Headers(opts.headers || {})
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const res = await fetch(path, { ...opts, headers })
  const text = await res.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch { data = { raw: text } }

  if (!res.ok) {
    const detail = data?.detail || data?.raw || res.statusText
    const err = new Error(detail)
    err.status = res.status
    throw err
  }

  return data
}

export const api = {
  login: (password) => request('/api/auth/login', { method: 'POST', body: JSON.stringify({ password }) }),
  serverSummary: () => request('/api/server/summary'),
  apps: () => request('/api/apps'),
  app: (key) => request(`/api/apps/${encodeURIComponent(key)}`),
  logs: (key, lines) => request(`/api/apps/${encodeURIComponent(key)}/logs?lines=${lines}`),
  action: (key, action) => request(`/api/apps/${encodeURIComponent(key)}/${action}`, { method: 'POST' }),
  discover: () => request('/api/discover')
}
