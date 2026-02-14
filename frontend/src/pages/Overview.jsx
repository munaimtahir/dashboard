import React from 'react'
import Card from '../components/Card.jsx'
import AppGrid from '../components/AppGrid.jsx'
import { api } from '../api.js'

function fmtBytes(n) {
  if (!n && n !== 0) return 'N/A'
  const units = ['B','KB','MB','GB','TB']
  let v = n
  let i = 0
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${v.toFixed(1)} ${units[i]}`
}

function fmtUptime(sec) {
  const s = Math.floor(sec)
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  return `${d}d ${h}h ${m}m`
}

export default function Overview() {
  const [summary, setSummary] = React.useState(null)
  const [apps, setApps] = React.useState([])
  const [error, setError] = React.useState('')

  async function load() {
    setError('')
    try {
      const [s, a] = await Promise.all([api.serverSummary(), api.apps()])
      setSummary(s)
      setApps(a)
    } catch (e) {
      setError(e.message || String(e))
    }
  }

  React.useEffect(() => { load() }, [])

  return (
    <div className="container">
      <div className="header">
        <div>
          <div className="title">Dashboard v1</div>
          <div className="subtitle">Server and app health</div>
        </div>
        <button className="btn" onClick={load}>Refresh</button>
      </div>

      {error ? <div className="card" style={{ borderColor: 'rgba(243,156,18,0.35)' }}>{error}</div> : null}

      <div className="grid" style={{ marginBottom: 12 }}>
        <div style={{ gridColumn: 'span 4' }}>
          <Card title="Uptime">
            <div className="kpi">{summary ? fmtUptime(summary.uptime_seconds) : '...'}</div>
            <div className="small">Load: {summary ? `${summary.loadavg_1.toFixed(2)} ${summary.loadavg_5.toFixed(2)} ${summary.loadavg_15.toFixed(2)}` : '...'}</div>
          </Card>
        </div>
        <div style={{ gridColumn: 'span 4' }}>
          <Card title="CPU">
            <div className="kpi">{summary ? `${summary.cpu_percent.toFixed(0)}%` : '...'}</div>
            <div className="small">Approximate (v1)</div>
          </Card>
        </div>
        <div style={{ gridColumn: 'span 4' }}>
          <Card title="RAM">
            <div className="kpi">{summary ? `${summary.ram_used_percent.toFixed(0)}%` : '...'}</div>
            <div className="small">{summary ? `${fmtBytes(summary.ram_used_bytes)} / ${fmtBytes(summary.ram_total_bytes)}` : '...'}</div>
          </Card>
        </div>
        <div style={{ gridColumn: 'span 4' }}>
          <Card title="Disk">
            <div className="kpi">{summary ? `${summary.disk_used_percent.toFixed(0)}%` : '...'}</div>
            <div className="small">{summary ? `${fmtBytes(summary.disk_used_bytes)} / ${fmtBytes(summary.disk_total_bytes)}` : '...'}</div>
          </Card>
        </div>
        <div style={{ gridColumn: 'span 4' }}>
          <Card title="Docker">
            <div className="kpi">{summary ? (summary.docker_ok ? 'OK' : 'Fail') : '...'}</div>
            <div className="small">Docker socket ping</div>
          </Card>
        </div>
        <div style={{ gridColumn: 'span 4' }}>
          <Card title="Caddy">
            <div className="kpi">{summary ? (summary.caddy_ok ? 'OK' : 'Unknown') : '...'}</div>
            <div className="small">Host TCP check</div>
          </Card>
        </div>
      </div>

      {summary?.notes?.length ? (
        <div className="card" style={{ marginBottom: 12 }}>
          <h3>Notes</h3>
          <div className="small">
            {summary.notes.map((n, i) => <div key={i}>{n}</div>)}
          </div>
        </div>
      ) : null}

      <AppGrid apps={apps} />
    </div>
  )
}
