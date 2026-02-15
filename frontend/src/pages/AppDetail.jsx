import React, { useState, useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import Card from '../components/Card.jsx'
import Badge from '../components/Badge.jsx'
import Button from '../components/Button.jsx'
import ConfirmModal from '../components/ConfirmModal.jsx'
import LogsViewer from '../components/LogsViewer.jsx'
import Spinner from '../components/Spinner.jsx'
import { api } from '../api.js'

function DeployModal({ open, appKey, onClose, onConfirm, busy }) {
  const [input, setInput] = useState('')
  const expected = `DEPLOY ${appKey}`

  useEffect(() => { if (open) setInput('') }, [open])

  if (!open) return null

  return (
    <div className="modalOverlay" role="dialog" aria-modal="true">
      <div className="modal">
        <div className="modalTitle">Deploy {appKey}</div>
        <div className="modalBody">
          <div style={{ marginBottom: 10, color: '#e74c3c' }}>
            ⚠️ This will run the deploy script and may result in downtime.
          </div>
          <div style={{ marginBottom: 10 }}>
            Type <code>{expected}</code> to confirm:
          </div>
          <input
            className="input"
            autoFocus
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={expected}
          />
        </div>
        <div className="modalActions">
          <Button disabled={busy} onClick={onClose}>Cancel</Button>
          <Button
            variant="danger"
            disabled={busy || input !== expected}
            onClick={() => onConfirm(input)}
          >
            {busy ? <span className="btnInline"><Spinner size={14} /> Deploying</span> : 'Deploy'}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function AppDetail() {
  const { key } = useParams()
  const [app, setApp] = useState(null)
  const [opsStatus, setOpsStatus] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [actionFeedback, setActionFeedback] = useState(null)
  const [pendingAction, setPendingAction] = useState(null)

  const [lines, setLines] = useState(200)
  const [log, setLog] = useState('')
  const [logError, setLogError] = useState('')
  const [logLoading, setLogLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)

  async function load() {
    setError('')
    try {
      const [a, s] = await Promise.all([
        api.app(key),
        api.opsStatus(key)
      ])
      setApp(a)
      setOpsStatus(s)
    } catch (e) {
      setError(e.message || String(e))
    }
  }

  async function loadLogs() {
    setLogError('')
    setLogLoading(true)
    try {
      // Prefer ops logs if available, fallback to container logs if not configured ???
      // Requirement says "GET /api/apps/{key}/ops/logs?lines=200"
      // But we should probably look at what the user wants. 
      // Existing log viewer uses container logs. Ops logs are different (execution logs).
      // Requirement: "Link to view log tail (reuse existing log viewer or add modal)" on /ops-jobs
      // For App Detail, let's keep showing container logs in the main viewer, 
      // but maybe show ops logs in the feedback or a separate tab? 
      // The instruction says "GET /api/apps/{key}/ops/logs" is for ops logs.
      // I'll stick to container logs for the main viewer for now to keep existing functionality,
      // as ops logs are ephemeral for the action.
      // Wait, "App Detail: Ops panel...". 

      const text = await api.logs(key, lines)
      setLog(text || '')
    } catch (e) {
      setLogError(e.message || String(e))
    } finally {
      setLogLoading(false)
    }
  }

  useEffect(() => { load() }, [key])
  useEffect(() => { loadLogs() }, [key, lines])
  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(() => { loadLogs() }, 5000)
    return () => clearInterval(id)
  }, [autoRefresh, key, lines])

  async function runAction(action, confirmHeader) {
    setBusy(true)
    setError('')
    setActionFeedback(null)
    try {
      let res
      if (action === 'start') res = await api.opsStart(key)
      else if (action === 'stop') res = await api.opsStop(key)
      else if (action === 'restart') res = await api.opsRestart(key)
      else if (action === 'deploy') res = await api.opsDeploy(key, confirmHeader)
      else throw new Error("Unknown action")

      if (res?.updated_app_status) setApp(res.updated_app_status)
      else await load()

      // Update usage/container logs
      await loadLogs()

      setActionFeedback({
        ok: res?.success,
        action,
        exitCode: res?.exit_code,
        message: res?.message || '',
        tail: res?.tail
      })

      // If failed, show error in main error box too?
      if (!res?.success) {
        setError(res?.message || 'Action failed')
      }

    } catch (e) {
      setError(e.message || String(e))
      setActionFeedback({ ok: false, action, exitCode: null, message: e.message || String(e) })
    } finally {
      setBusy(false)
    }
  }

  const isConfigured = opsStatus && opsStatus.configured
  const available = new Set(opsStatus ? opsStatus.available_actions : [])

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
              <Card title="Ops Actions">
                <div className="small" style={{ marginBottom: 10 }}>
                  {isConfigured
                    ? 'Safe ops scripts allowlisted.'
                    : 'Ops scripts not configured for this app.'}
                </div>

                {actionFeedback ? (
                  <div style={{ marginBottom: 10, padding: 8, background: actionFeedback.ok ? '#f0fff4' : '#fff5f5', borderRadius: 4 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Badge
                        label={`${actionFeedback.ok ? 'Success' : 'Failure'}: ${actionFeedback.action}`}
                        status={actionFeedback.ok ? 'HEALTHY' : 'DOWN'}
                      />
                      {actionFeedback.exitCode !== null && <span className="small">Exit: {actionFeedback.exitCode}</span>}
                    </div>
                    {actionFeedback.message && <div className="small" style={{ marginTop: 6, fontWeight: 'bold' }}>{actionFeedback.message}</div>}
                    {actionFeedback.tail && (
                      <div className="code-block" style={{ marginTop: 6, fontSize: 11, maxHeight: 100, overflow: 'auto' }}>
                        {actionFeedback.tail}
                      </div>
                    )}
                  </div>
                ) : null}

                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <Button
                    variant="primary"
                    disabled={!isConfigured || busy || !available.has('start')}
                    onClick={() => setPendingAction('start')}
                  >
                    {busy && pendingAction === 'start' ? <Spinner size={14} /> : 'Start'}
                  </Button>
                  <Button
                    variant="danger"
                    disabled={!isConfigured || busy || !available.has('stop')}
                    onClick={() => setPendingAction('stop')}
                  >
                    {busy && pendingAction === 'stop' ? <Spinner size={14} /> : 'Stop'}
                  </Button>
                  <Button
                    disabled={!isConfigured || busy || !available.has('restart')}
                    onClick={() => setPendingAction('restart')}
                  >
                    {busy && pendingAction === 'restart' ? <Spinner size={14} /> : 'Restart'}
                  </Button>
                  <Button
                    variant="primary"
                    disabled={!isConfigured || busy || !available.has('deploy')}
                    style={{ marginLeft: 'auto', background: isConfigured && available.has('deploy') ? '#8e44ad' : undefined }}
                    onClick={() => setPendingAction('deploy')}
                  >
                    {busy && pendingAction === 'deploy' ? <Spinner size={14} /> : 'Deploy'}
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

      {/* Standard Confirm Modal for Start/Stop/Restart */}
      <ConfirmModal
        open={!!pendingAction && pendingAction !== 'deploy' && !busy}
        title="Confirm action"
        message={`Are you sure you want to ${pendingAction} ${app?.name || key}?`}
        confirmLabel={`Yes, ${pendingAction}`}
        onClose={() => setPendingAction(null)}
        onConfirm={async () => {
          const action = pendingAction
          setPendingAction(action) // Keep it set to show busy state in buttons (or handling via busy state)
          await runAction(action)
          setPendingAction(null)
        }}
      />

      {/* Special Deploy Modal */}
      <DeployModal
        open={pendingAction === 'deploy' && !busy} // Hide if busy to prevent double submit, but we are handling busy inside 
        appKey={key}
        busy={busy}
        onClose={() => setPendingAction(null)}
        onConfirm={async (input) => {
          // Modal handles validation, calls this
          await runAction('deploy', input)
          setPendingAction(null)
        }}
      />
    </div>
  )
}
