import React from 'react'
import { Link, useParams } from 'react-router-dom'
import Card from '../components/Card.jsx'
import Badge from '../components/Badge.jsx'
import Button from '../components/Button.jsx'
import LogsViewer from '../components/LogsViewer.jsx'
import { api } from '../api.js'

export default function AppDetail() {
  const { key } = useParams()
  const [app, setApp] = React.useState(null)
  const [error, setError] = React.useState('')
  const [busy, setBusy] = React.useState(false)

  const [lines, setLines] = React.useState(200)
  const [log, setLog] = React.useState('')
  const [logError, setLogError] = React.useState('')
  const [logLoading, setLogLoading] = React.useState(false)

  async function load() {
    setError('')
    try {
      const a = await api.app(key)
      setApp(a)
    } catch (e) {
      setError(e.message || String(e))
    }
  }

  async function loadLogs() {
    setLogError('')
    setLogLoading(true)
    try {
      const r = await api.logs(key, lines)
      setLog(r.log || '')
    } catch (e) {
      setLogError(e.message || String(e))
    } finally {
      setLogLoading(false)
    }
  }

  React.useEffect(() => { load() }, [key])
  React.useEffect(() => { loadLogs() }, [key, lines])

  async function doAction(action) {
    if (!confirm(`Confirm: ${action} ${key}?`)) return
    setBusy(true)
    setError('')
    try {
      await api.action(key, action)
      await load()
      await loadLogs()
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container">
      <div className="header">
        <div>
          <div className="title">{app ? app.name : 'App'}</div>
          <div className="subtitle">key: {key}</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Link to="/" className="btn">Back</Link>
          <button className="btn" onClick={() => { load(); loadLogs(); }}>Refresh</button>
        </div>
      </div>

      {error ? <div className="card" style={{ borderColor: 'rgba(243,156,18,0.35)' }}>{error}</div> : null}

      {app ? (
        <>
          <div className="grid" style={{ marginBottom: 12 }}>
            <div style={{ gridColumn: 'span 6' }}>
              <Card title="Status">
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <Badge label={`Overall: ${app.overall_status}`} status={app.overall_status} />
                  <Badge label={`Backend: ${app.backend_check ? (app.backend_check.ok ? 'OK' : 'Fail') : 'N/A'}`} status={app.backend_check?.ok ? 'HEALTHY' : 'DOWN'} />
                  <Badge label={`Frontend: ${app.frontend_check ? (app.frontend_check.ok ? 'OK' : 'Fail') : 'N/A'}`} status={app.frontend_check?.ok ? 'HEALTHY' : 'DOWN'} />
                </div>
                <div style={{ height: 10 }} />
                <div><b>Reason:</b> {app.reason}</div>
                <div className="small"><b>Recommendation:</b> {app.recommendation}</div>
              </Card>
            </div>
            <div style={{ gridColumn: 'span 6' }}>
              <Card title="Actions">
                <div className="small" style={{ marginBottom: 10 }}>Allowlist only. Rate limit: 3 actions / 5 minutes.</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <Button variant="primary" disabled={busy} onClick={() => doAction('start')}>Start</Button>
                  <Button variant="danger" disabled={busy} onClick={() => doAction('stop')}>Stop</Button>
                  <Button disabled={busy} onClick={() => doAction('restart')}>Restart</Button>
                </div>
              </Card>
            </div>
          </div>

          <div className="grid" style={{ marginBottom: 12 }}>
            <div style={{ gridColumn: 'span 12' }}>
              <Card title="Containers">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Exists</th>
                      <th>Status</th>
                      <th>Running</th>
                      <th>Exit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {app.container_info.map((c) => (
                      <tr key={c.name}>
                        <td>{c.name}</td>
                        <td>{c.exists ? 'yes' : 'no'}</td>
                        <td>{c.status}</td>
                        <td>{c.running ? 'yes' : 'no'}</td>
                        <td>{(c.exit_code === null || c.exit_code === undefined) ? '-' : c.exit_code}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            </div>
          </div>

          <LogsViewer
            lines={lines}
            setLines={setLines}
            log={log}
            loading={logLoading}
            error={logError}
          />
        </>
      ) : null}
    </div>
  )
}
