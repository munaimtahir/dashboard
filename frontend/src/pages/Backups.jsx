import React from 'react'
import { Link } from 'react-router-dom'
import Card from '../components/Card.jsx'
import Button from '../components/Button.jsx'
import { api } from '../api.js'

function fmtSize(mb) {
  if (mb === null || mb === undefined) return '—'
  const v = Number(mb)
  if (!Number.isFinite(v)) return '—'
  if (v >= 1024) return `${(v / 1024).toFixed(2)} GB`
  return `${v.toFixed(0)} MB`
}

function StatusBadge({ status }) {
    let color = '#7f8c8d'; // grey
    if (status === 'READY') color = '#2ecc71'; // green
    if (status === 'WARNING') color = '#f1c40f'; // yellow
    if (status === 'MISSING') color = '#e74c3c'; // red

    return (
        <span style={{
            backgroundColor: color,
            color: '#fff',
            padding: '2px 8px',
            borderRadius: 4,
            fontSize: 12,
            fontWeight: 'bold'
        }}>
            {status}
        </span>
    )
}

function Drawer({ app, onClose }) {
    if (!app) return null;
    return (
        <div style={{
            position: 'fixed', top: 0, right: 0, bottom: 0, width: '400px',
            backgroundColor: '#1f2937', borderLeft: '1px solid #374151',
            zIndex: 1000, padding: 20, overflowY: 'auto',
            boxShadow: '-5px 0 15px rgba(0,0,0,0.5)',
            color: '#f3f4f6'
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <h2 style={{ margin: 0 }}>{app.name}</h2>
                <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#fff', fontSize: 24, cursor: 'pointer' }}>×</button>
            </div>

            <div style={{ marginBottom: 20 }}>
                <h4 style={{ borderBottom: '1px solid #374151', paddingBottom: 5, marginBottom: 10 }}>General</h4>
                <div style={{ marginBottom: 5 }}><strong>Key:</strong> {app.key}</div>
                <div style={{ marginBottom: 5 }}><strong>Domain:</strong> {app.domain || '—'}</div>
                <div style={{ marginBottom: 5 }}><strong>Folder:</strong> {app.folder} {app.folder_exists ? '✅' : '❌'}</div>
                <div style={{ marginBottom: 5 }}><strong>Est. Size:</strong> {fmtSize(app.estimated_app_total_mb)}</div>
                <div style={{ marginTop: 8 }}><StatusBadge status={app.status} /></div>
            </div>

            {app.issues && app.issues.length > 0 && (
                <div style={{ border: '1px solid #ef4444', padding: 10, borderRadius: 4, marginBottom: 20, backgroundColor: 'rgba(239, 68, 68, 0.1)' }}>
                    <h4 style={{ color: '#ef4444', marginTop: 0, marginBottom: 5 }}>Issues</h4>
                    <ul style={{ paddingLeft: 20, margin: 0 }}>
                        {app.issues.map((iss, i) => <li key={i}>{iss}</li>)}
                    </ul>
                </div>
            )}

            <div style={{ marginBottom: 20 }}>
                <h4 style={{ borderBottom: '1px solid #374151', paddingBottom: 5, marginBottom: 10 }}>Running Containers ({app.running_containers.length})</h4>
                {app.running_containers.length === 0 ? <div style={{ color: '#9ca3af' }}>None</div> : (
                    <ul style={{ paddingLeft: 20, margin: 0 }}>
                        {app.running_containers.map(c => (
                            <li key={c.name} style={{ marginBottom: 5 }}>
                                {c.name} <span style={{ fontSize: 11, padding: '1px 4px', borderRadius: 2, backgroundColor: c.status.startsWith('Up') ? '#059669' : '#dc2626' }}>{c.status}</span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            <div style={{ marginBottom: 20 }}>
                <h4 style={{ borderBottom: '1px solid #374151', paddingBottom: 5, marginBottom: 10 }}>Required Containers ({app.required_containers.length})</h4>
                {app.required_containers.length === 0 ? <div style={{ color: '#9ca3af' }}>None</div> : (
                    <ul style={{ paddingLeft: 20, margin: 0 }}>
                        {app.required_containers.map(c => (
                            <li key={c.name} style={{ marginBottom: 5 }}>
                                {c.name} <span style={{ fontSize: 11, color: '#9ca3af' }}>({c.role})</span> {c.missing ? <span style={{ color: '#ef4444' }}>MISSING ❌</span> : '✅'}
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            <div style={{ marginBottom: 20 }}>
                <h4 style={{ borderBottom: '1px solid #374151', paddingBottom: 5, marginBottom: 10 }}>Media ({app.media.length})</h4>
                {app.media.length === 0 ? <div style={{ color: '#9ca3af' }}>None</div> : (
                    <ul style={{ paddingLeft: 20, margin: 0 }}>
                        {app.media.map(m => (
                            <li key={m.path} style={{ marginBottom: 5 }}>
                                <div style={{ fontSize: 13, wordBreak: 'break-all' }}>{m.path}</div>
                                <div style={{ fontSize: 11, color: '#9ca3af' }}>
                                    {m.exists ? fmtSize(m.size_mb) : 'Missing'} {m.warning ? `(${m.warning})` : ''}
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            <div style={{ marginBottom: 20 }}>
                <h4 style={{ borderBottom: '1px solid #374151', paddingBottom: 5, marginBottom: 10 }}>Configs ({app.configs.length})</h4>
                {app.configs.length === 0 ? <div style={{ color: '#9ca3af' }}>None</div> : (
                    <ul style={{ paddingLeft: 20, margin: 0 }}>
                        {app.configs.map(c => (
                            <li key={c.path} style={{ marginBottom: 5 }}>
                                <div style={{ fontSize: 13, wordBreak: 'break-all' }}>{c.path}</div>
                                <div style={{ fontSize: 11, color: '#9ca3af' }}>
                                    {c.exists ? `${c.size_kb} KB` : 'Missing'}
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    )
}

export default function Backups() {
  const [plan, setPlan] = React.useState(null)
  const [error, setError] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const [selectedApp, setSelectedApp] = React.useState(null)

  async function loadPlan() {
    setBusy(true); setError('');
    try {
      const p = await api.backupsPlan()
      setPlan(p)
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  React.useEffect(() => {
      loadPlan()
  }, [])

  const summary = plan?.summary || {}
  const apps = plan?.applications || []

  return (
    <div className="container">
      <div className="header">
        <div>
          <div className="title">Backups Inventory</div>
          <div className="subtitle">Dry Run & Planning</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button disabled={busy} onClick={loadPlan}>Refresh Plan</Button>
          <Link to="/" className="btn">Back</Link>
        </div>
      </div>

      {error ? <div className="card" style={{ borderColor: 'rgba(231,76,60,0.45)' }}>{error}</div> : null}

      {/* Summary Panel */}
      {plan && (
          <div className="grid" style={{ marginBottom: 20 }}>
              <div style={{ gridColumn: 'span 12' }}>
                  <Card title="Inventory Summary">
                      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'center' }}>
                          <div style={{ textAlign: 'center' }}>
                              <div style={{ fontSize: 24, fontWeight: 'bold' }}>{fmtSize(summary.estimated_total_mb)}</div>
                              <div style={{ fontSize: 12, color: '#9ca3af' }}>Total Estimated Size</div>
                          </div>
                          <div style={{ width: 1, height: 40, background: '#374151' }}></div>
                          <div style={{ textAlign: 'center' }}>
                              <div style={{ fontSize: 24, fontWeight: 'bold' }}>{summary.apps_count}</div>
                              <div style={{ fontSize: 12, color: '#9ca3af' }}>Applications</div>
                          </div>
                          <div style={{ textAlign: 'center' }}>
                              <div style={{ fontSize: 24, fontWeight: 'bold' }}>{summary.db_containers_count}</div>
                              <div style={{ fontSize: 12, color: '#9ca3af' }}>DB Containers</div>
                          </div>
                          <div style={{ textAlign: 'center' }}>
                              <div style={{ fontSize: 24, fontWeight: 'bold' }}>{summary.media_paths_count}</div>
                              <div style={{ fontSize: 12, color: '#9ca3af' }}>Media Paths</div>
                          </div>
                          <div style={{ flex: 1 }}></div>
                          <div style={{ textAlign: 'right' }}>
                              <div style={{
                                  padding: '5px 10px',
                                  borderRadius: 4,
                                  background: summary.ready ? '#059669' : '#dc2626',
                                  fontWeight: 'bold',
                                  color: '#fff'
                              }}>
                                  {summary.ready ? 'READY' : 'ISSUES DETECTED'}
                              </div>
                          </div>
                      </div>
                      {summary.issues && summary.issues.length > 0 && (
                          <div style={{ marginTop: 10, color: '#ef4444', fontSize: 13 }}>
                              {summary.issues.map((iss, i) => <div key={i}>• {iss}</div>)}
                          </div>
                      )}
                  </Card>
              </div>
          </div>
      )}

      {/* Inventory Table */}
      {plan && (
          <div className="card" style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 800 }}>
                  <thead>
                      <tr style={{ borderBottom: '1px solid #374151', textAlign: 'left' }}>
                          <th style={{ padding: 10 }}>App</th>
                          <th style={{ padding: 10 }}>Folder</th>
                          <th style={{ padding: 10 }}>Running</th>
                          <th style={{ padding: 10 }}>Required</th>
                          <th style={{ padding: 10 }}>Media Size</th>
                          <th style={{ padding: 10 }}>Total Est.</th>
                          <th style={{ padding: 10 }}>Status</th>
                      </tr>
                  </thead>
                  <tbody>
                      {apps.map(app => (
                          <tr key={app.key}
                              onClick={() => setSelectedApp(app)}
                              className="tr-hover"
                              style={{ borderBottom: '1px solid #374151', cursor: 'pointer' }}
                          >
                              <td style={{ padding: 10 }}>
                                  <div style={{ fontWeight: 'bold' }}>{app.name}</div>
                                  <div style={{ fontSize: 11, color: '#9ca3af' }}>{app.key}</div>
                              </td>
                              <td style={{ padding: 10 }}>
                                  {app.folder_exists ? '✅' : '❌'}
                              </td>
                              <td style={{ padding: 10 }}>{app.running_containers.length}</td>
                              <td style={{ padding: 10 }}>
                                  {app.required_containers.length}
                                  {app.required_containers.some(c => c.missing) ? <span style={{ color: '#ef4444', marginLeft: 5 }}>⚠</span> : null}
                              </td>
                              <td style={{ padding: 10 }}>
                                  {fmtSize(app.media.reduce((acc, m) => acc + (m.size_mb || 0), 0))}
                              </td>
                              <td style={{ padding: 10, fontWeight: 'bold' }}>{fmtSize(app.estimated_app_total_mb)}</td>
                              <td style={{ padding: 10 }}>
                                  <StatusBadge status={app.status} />
                              </td>
                          </tr>
                      ))}
                  </tbody>
              </table>
          </div>
      )}

      {selectedApp && (
          <>
            <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', zIndex: 999 }} onClick={() => setSelectedApp(null)}></div>
            <Drawer app={selectedApp} onClose={() => setSelectedApp(null)} />
          </>
      )}

      <style>{`
        .tr-hover:hover {
            background-color: rgba(255, 255, 255, 0.05);
        }
      `}</style>
    </div>
  )
}
