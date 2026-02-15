import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Card from '../components/Card.jsx'
import Button from '../components/Button.jsx'
import Badge from '../components/Badge.jsx'
import { api } from '../api.js'

function pickProject(c) {
  return c.compose_project || c.labels?.['com.docker.compose.project'] || ''
}

function pickService(c) {
  return c.compose_service || c.labels?.['com.docker.compose.service'] || ''
}

export default function Discover() {
  const nav = useNavigate()
  const [data, setData] = React.useState(null)
  const [error, setError] = React.useState('')
  const [q, setQ] = React.useState('')
  const [selected, setSelected] = React.useState(() => new Set())

  const [formOpen, setFormOpen] = React.useState(false)
  const [key, setKey] = React.useState('')
  const [name, setName] = React.useState('')
  const [domain, setDomain] = React.useState('')
  const [backendHealthUrl, setBackendHealthUrl] = React.useState('')
  const [frontendUrl, setFrontendUrl] = React.useState('')
  const [saving, setSaving] = React.useState(false)
  const [saveError, setSaveError] = React.useState('')

  async function load() {
    setError('')
    try {
      const d = await api.discover()
      setData(d)
    } catch (e) {
      setError(e.message || String(e))
    }
  }

  React.useEffect(() => { load() }, [])

  const containers = (data?.containers || [])
  const filtered = containers.filter((c) => {
    const s = (q || '').trim().toLowerCase()
    if (!s) return true
    const hay = `${c.name} ${pickProject(c)} ${pickService(c)} ${c.image}`.toLowerCase()
    return hay.includes(s)
  })

  function toggle(name) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  async function submit() {
    setSaving(true)
    setSaveError('')
    try {
      const body = {
        key,
        name,
        domain: domain || null,
        containers: Array.from(selected),
        backend_health_url: backendHealthUrl || null,
        frontend_url: frontendUrl || null
      }
      await api.upsertManifestApp(body)
      await api.reloadManifest()
      nav('/')
    } catch (e) {
      setSaveError(e.message || String(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="container">
      <div className="header">
        <div>
          <div className="title">Container Discovery</div>
          <div className="subtitle">Select containers and create/update an app in the manifest</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Link to="/" className="btn">Back</Link>
          <button className="btn" onClick={load}>Refresh</button>
        </div>
      </div>

      {error ? <div className="card" style={{ borderColor: 'rgba(243,156,18,0.35)' }}>{error}</div> : null}

      <div className="grid" style={{ marginBottom: 12 }}>
        <div style={{ gridColumn: 'span 6' }}>
          <Card title="Search">
            <input className="input" placeholder="Filter by name/project/service…" value={q} onChange={(e) => setQ(e.target.value)} />
            <div className="small" style={{ marginTop: 8 }}>{filtered.length} containers</div>
          </Card>
        </div>
        <div style={{ gridColumn: 'span 6' }}>
          <Card title="Selection">
            <div className="small" style={{ marginBottom: 10 }}>{selected.size} selected</div>
            <Button variant="primary" disabled={!selected.size} onClick={() => setFormOpen(true)}>Create App from Selection</Button>
          </Card>
        </div>
      </div>

      {formOpen ? (
        <div className="grid" style={{ marginBottom: 12 }}>
          <div style={{ gridColumn: 'span 12' }}>
            <Card title="Manifest Upsert">
              {saveError ? <div className="small" style={{ color: '#f39c12', marginBottom: 10 }}>{saveError}</div> : null}
              <div className="grid">
                <div style={{ gridColumn: 'span 4' }}>
                  <div className="small" style={{ marginBottom: 6 }}>Key</div>
                  <input className="input" value={key} onChange={(e) => setKey(e.target.value)} placeholder="lims" />
                </div>
                <div style={{ gridColumn: 'span 4' }}>
                  <div className="small" style={{ marginBottom: 6 }}>Name</div>
                  <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="LIMS" />
                </div>
                <div style={{ gridColumn: 'span 4' }}>
                  <div className="small" style={{ marginBottom: 6 }}>Domain</div>
                  <input className="input" value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="lims.alshifalab.pk" />
                </div>
                <div style={{ gridColumn: 'span 6' }}>
                  <div className="small" style={{ marginBottom: 6 }}>Backend health URL</div>
                  <input className="input" value={backendHealthUrl} onChange={(e) => setBackendHealthUrl(e.target.value)} placeholder="http://127.0.0.1:8012/api/health/" />
                </div>
                <div style={{ gridColumn: 'span 6' }}>
                  <div className="small" style={{ marginBottom: 6 }}>Frontend URL</div>
                  <input className="input" value={frontendUrl} onChange={(e) => setFrontendUrl(e.target.value)} placeholder="https://lims.alshifalab.pk" />
                </div>
              </div>

              <div className="small" style={{ marginTop: 10, marginBottom: 10 }}>
                Containers: {Array.from(selected).join(', ')}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <Button disabled={saving} onClick={() => setFormOpen(false)}>Cancel</Button>
                <Button variant="primary" disabled={saving} onClick={submit}>{saving ? 'Saving…' : 'Save'}</Button>
              </div>
            </Card>
          </div>
        </div>
      ) : null}

      <div className="card">
        <h3>Containers</h3>
        <table className="table">
          <thead>
            <tr>
              <th />
              <th>Name</th>
              <th>Compose</th>
              <th>Status</th>
              <th>Ports</th>
              <th>Image</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => {
              const project = pickProject(c)
              const service = pickService(c)
              const isSelected = selected.has(c.name)
              const status = c.status || c.state?.Status || 'unknown'
              return (
                <tr key={c.name}>
                  <td>
                    <input type="checkbox" checked={isSelected} onChange={() => toggle(c.name)} />
                  </td>
                  <td>
                    <div>{c.name}</div>
                    <div className="small">{c.id}</div>
                  </td>
                  <td>
                    <div>{project || '—'}</div>
                    <div className="small">{service || '—'}</div>
                  </td>
                  <td>
                    <Badge label={status} status={status === 'running' ? 'HEALTHY' : 'DOWN'} />
                  </td>
                  <td className="small">{(c.ports || []).join(', ') || '—'}</td>
                  <td className="small">{c.image}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

