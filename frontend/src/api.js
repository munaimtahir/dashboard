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

async function requestText(path, opts = {}) {
  const token = getToken()
  const headers = new Headers(opts.headers || {})
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const res = await fetch(path, { ...opts, headers })
  const text = await res.text()

  if (!res.ok) {
    let detail = text || res.statusText
    try {
      const parsed = text ? JSON.parse(text) : null
      detail = parsed?.detail || parsed?.raw || detail
    } catch { }
    const err = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
    err.status = res.status
    throw err
  }

  return text
}

export const api = {
  login: (password) => request('/api/auth/login', { method: 'POST', body: JSON.stringify({ password }) }),
  serverSummary: () => request('/api/server/summary'),
  apps: () => request('/api/apps'),
  app: (key) => request(`/api/apps/${encodeURIComponent(key)}`),
  logs: (key, lines) => requestText(`/api/apps/${encodeURIComponent(key)}/logs?lines=${lines}`),
  action: (key, action) => request(`/api/apps/${encodeURIComponent(key)}/${action}`, { method: 'POST' }),
  discover: (params = {}) => {
    const qs = new URLSearchParams()
    if (params.project) qs.set('project', params.project)
    if (params.contains) qs.set('contains', params.contains)
    const s = qs.toString()
    return request(`/api/discover${s ? `?${s}` : ''}`)
  },
  manifest: () => request('/api/manifest'),
  upsertManifestApp: (body) => request('/api/manifest/apps', { method: 'POST', body: JSON.stringify(body) }),
  reloadManifest: () => request('/api/manifest/reload', { method: 'POST' }),
  backupsPlan: () => request('/api/backups/plan'),
  backupsValidate: () => request('/api/backups/validate'),
  backupsSimulate: () => request('/api/backups/simulate', { method: 'POST' }),

  // Inventory
  inventoryPreview: () => request('/api/inventory/preview', { method: 'POST' }),
  inventorySync: () => request('/api/inventory/sync', { method: 'POST' }),

  // Ops
  opsStatus: (key) => request(`/api/apps/${encodeURIComponent(key)}/ops/status`),
  opsStart: (key) => request(`/api/apps/${encodeURIComponent(key)}/ops/start`, { method: 'POST' }),
  opsStop: (key) => request(`/api/apps/${encodeURIComponent(key)}/ops/stop`, { method: 'POST' }),
  opsRestart: (key) => request(`/api/apps/${encodeURIComponent(key)}/ops/restart`, { method: 'POST' }),
  opsDeploy: (key, confirm) => request(`/api/apps/${encodeURIComponent(key)}/ops/deploy`, {
    method: 'POST',
    headers: { 'X-Confirm': confirm }
  }),
  opsLogs: (key, lines) => requestText(`/api/apps/${encodeURIComponent(key)}/ops/logs?lines=${lines}`),
  auditLogs: (limit) => request(`/api/audit/logs?limit=${limit || 50}`),
}
