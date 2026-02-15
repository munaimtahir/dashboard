import React from 'react'
import { Link } from 'react-router-dom'
import Card from '../components/Card.jsx'
import Badge from '../components/Badge.jsx'
import Button from '../components/Button.jsx'
import { api } from '../api.js'

function fmtSize(mb) {
  if (mb === null || mb === undefined) return '—'
  const v = Number(mb)
  if (!Number.isFinite(v)) return '—'
  if (v >= 1024) return `${(v / 1024).toFixed(2)} GB`
  return `${v.toFixed(0)} MB`
}

export default function Backups() {
  const [plan, setPlan] = React.useState(null)
  const [validation, setValidation] = React.useState(null)
  const [message, setMessage] = React.useState('')
  const [error, setError] = React.useState('')
  const [busy, setBusy] = React.useState(false)

  async function doPlan() {
    setBusy(true); setError(''); setMessage('')
    try {
      const p = await api.backupsPlan()
      setPlan(p)
      setValidation(p.validation || null)
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  async function doValidate() {
    setBusy(true); setError(''); setMessage('')
    try {
      const v = await api.backupsValidate()
      setValidation(v)
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  async function doSimulate() {
    setBusy(true); setError(''); setMessage('')
    try {
      const r = await api.backupsSimulate()
      setMessage(r.message || 'Simulation complete')
      setPlan(r.plan || null)
      setValidation(r.plan?.validation || null)
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  const estMb = plan?.estimated_total_mb
  const dbCount = plan?.databases?.length || 0
  const mediaCount = plan?.media?.length || 0
  const ready = validation?.ready
  const issues = validation?.issues || []

  return (
    <div className="container">
      <div className="header">
        <div>
          <div className="title">Backups (Dry Run)</div>
          <div className="subtitle">Planning and validation only. No files created.</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Link to="/" className="btn">Back</Link>
        </div>
      </div>

      {error ? <div className="card" style={{ borderColor: 'rgba(231,76,60,0.45)' }}>{error}</div> : null}
      {message ? <div className="card" style={{ borderColor: 'rgba(76,201,240,0.35)' }}>{message}</div> : null}

      {ready === false ? (
        <div className="card" style={{ marginBottom: 12, borderColor: 'rgba(231,76,60,0.45)' }}>
          <h3>Validation Failed</h3>
          <div className="small">
            {issues.length ? issues.map((x, i) => <div key={i}>{x}</div>) : 'Unknown issue'}
          </div>
        </div>
      ) : null}

      <div className="grid" style={{ marginBottom: 12 }}>
        <div style={{ gridColumn: 'span 6' }}>
          <Card title="Backup Simulation">
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Button variant="primary" disabled={busy} onClick={doPlan}>Generate Plan</Button>
              <Button disabled={busy} onClick={doValidate}>Validate Environment</Button>
              <Button disabled={busy} onClick={doSimulate}>Simulate Backup</Button>
            </div>
          </Card>
        </div>
        <div style={{ gridColumn: 'span 6' }}>
          <Card title="Summary">
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <Badge label={`Estimated: ${fmtSize(estMb)}`} status="HEALTHY" />
              <Badge label={`DB containers: ${dbCount}`} status={dbCount ? 'HEALTHY' : 'DEGRADED'} />
              <Badge label={`Media folders: ${mediaCount}`} status={mediaCount ? 'HEALTHY' : 'DEGRADED'} />
              <Badge label={`Validation: ${ready === undefined ? 'N/A' : (ready ? 'Ready' : 'Not ready')}`} status={ready ? 'HEALTHY' : 'DOWN'} />
            </div>
          </Card>
        </div>
      </div>

      {plan ? (
        <div className="grid">
          <div style={{ gridColumn: 'span 12' }}>
            <Card title="Plan (JSON)">
              <pre className="logs">{JSON.stringify(plan, null, 2)}</pre>
            </Card>
          </div>
        </div>
      ) : null}
    </div>
  )
}

