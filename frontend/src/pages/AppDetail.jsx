import React from 'react'
import { Link, useParams } from 'react-router-dom'
import Card from '../components/Card.jsx'
import Badge from '../components/Badge.jsx'
import Button from '../components/Button.jsx'
import ConfirmModal from '../components/ConfirmModal.jsx'
import LogsViewer from '../components/LogsViewer.jsx'
import Spinner from '../components/Spinner.jsx'
import { api } from '../api.js'

export default function AppDetail() {
  const { key } = useParams()
  const [app, setApp] = React.useState(null)
  const [error, setError] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const [actionFeedback, setActionFeedback] = React.useState(null)
  const [pendingAction, setPendingAction] = React.useState(null)

  const [lines, setLines] = React.useState(200)
  const [log, setLog] = React.useState('')
  const [logError, setLogError] = React.useState('')
  const [logLoading, setLogLoading] = React.useState(false)
  const [autoRefresh, setAutoRefresh] = React.useState(false)

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
      const text = await api.logs(key, lines)
      setLog(text || '')
    } catch (e) {
      setLogError(e.message || String(e))
    } finally {
      setLogLoading(false)
    }
  }

  React.useEffect(() => { load() }, [key])
  React.useEffect(() => { loadLogs() }, [key, lines])
  React.useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(() => { loadLogs() }, 5000)
    return () => clearInterval(id)
  }, [autoRefresh, key, lines])

  async function runAction(action) {
    setBusy(true)
    setError('')
    setActionFeedback(null)
    try {
      const res = await api.action(key, action)
      if (res?.status) setApp(res.status)
      else await load()
      await loadLogs()
      setActionFeedback({ ok: !!res?.ok, action, exitCode: res?.exit_code, message: res?.message || '' })
    } catch (e) {
      setError(e.message || String(e))
      setActionFeedback({ ok: false, action, exitCode: null, message: e.message || String(e) })
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
                {actionFeedback ? (
                  <div style={{ marginBottom: 10 }}>
                    <Badge
                      label={`${actionFeedback.ok ? 'Success' : 'Failure'}: ${actionFeedback.action}${actionFeedback.exitCode !== null && actionFeedback.exitCode !== undefined ? ` (exit ${actionFeedback.exitCode})` : ''}`}
                      status={actionFeedback.ok ? 'HEALTHY' : 'DOWN'}
                    />
                    {actionFeedback.message ? <div className="small" style={{ marginTop: 6 }}>{actionFeedback.message}</div> : null}
                  </div>
                ) : null}
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <Button variant="primary" disabled={busy} onClick={() => setPendingAction('start')}>
                    {busy && pendingAction === 'start' ? <span className="btnInline"><Spinner size={14} /> Starting</span> : 'Start'}
                  </Button>
                  <Button variant="danger" disabled={busy} onClick={() => setPendingAction('stop')}>
                    {busy && pendingAction === 'stop' ? <span className="btnInline"><Spinner size={14} /> Stopping</span> : 'Stop'}
                  </Button>
                  <Button disabled={busy} onClick={() => setPendingAction('restart')}>
                    {busy && pendingAction === 'restart' ? <span className="btnInline"><Spinner size={14} /> Restarting</span> : 'Restart'}
                  </Button>
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
            autoRefresh={autoRefresh}
            setAutoRefresh={setAutoRefresh}
            onRefresh={loadLogs}
          />
        </>
      ) : null}

      <ConfirmModal
        open={!!pendingAction && !busy}
        title="Confirm action"
        message={`Are you sure you want to ${pendingAction} ${app?.name || key}?`}
        confirmLabel={`Yes, ${pendingAction}`}
        onClose={() => setPendingAction(null)}
        onConfirm={async () => {
          const action = pendingAction
          setPendingAction(action)
          await runAction(action)
          setPendingAction(null)
        }}
      />
    </div>
  )
}
