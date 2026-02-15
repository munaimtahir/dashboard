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
            fontSize: 11,
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
            position: 'fixed', top: 0, right: 0, bottom: 0, width: '450px',
            backgroundColor: '#1f2937', borderLeft: '1px solid #374151',
            zIndex: 1000, padding: 25, overflowY: 'auto',
            boxShadow: '-5px 0 15px rgba(0,0,0,0.5)',
            color: '#f3f4f6'
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 25 }}>
                <h2 style={{ margin: 0 }}>{app.name}</h2>
                <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#fff', fontSize: 24, cursor: 'pointer' }}>×</button>
            </div>

            <div style={{ marginBottom: 25 }}>
                <h4 style={{ borderBottom: '1px solid #374151', paddingBottom: 5, marginBottom: 12, color: '#9ca3af', fontSize: 13, textTransform: 'uppercase' }}>General</h4>
                <div style={{ marginBottom: 6 }}><strong>Key:</strong> {app.key}</div>
                <div style={{ marginBottom: 6 }}><strong>Domain:</strong> {app.domain || '—'}</div>
                <div style={{ marginBottom: 6 }}>
                    <strong>Folder:</strong> <code style={{ fontSize: 12 }}>{app.folder}</code> {app.folder_exists ? '✅' : '❌'}
                </div>
                <div style={{ marginBottom: 6 }}><strong>Size:</strong> {fmtSize(app.estimated_app_total_mb)}</div>
                <div style={{ marginTop: 10 }}><StatusBadge status={app.status} /></div>
            </div>

            {app.issues && app.issues.length > 0 && (
                <div style={{ border: '1px solid #ef4444', padding: 12, borderRadius: 6, marginBottom: 25, backgroundColor: 'rgba(239, 68, 68, 0.1)' }}>
                    <h4 style={{ color: '#ef4444', marginTop: 0, marginBottom: 8, fontSize: 14 }}>Inventory Issues</h4>
                    <ul style={{ paddingLeft: 20, margin: 0, fontSize: 13 }}>
                        {app.issues.map((iss, i) => <li key={i}>{iss}</li>)}
                    </ul>
                </div>
            )}

            <div style={{ marginBottom: 25 }}>
                <h4 style={{ borderBottom: '1px solid #374151', paddingBottom: 5, marginBottom: 12, color: '#9ca3af', fontSize: 13, textTransform: 'uppercase' }}>Running Containers ({app.running_containers.length})</h4>
                {app.running_containers.length === 0 ? <div style={{ color: '#9ca3af', fontSize: 13 }}>None detected</div> : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {app.running_containers.map(c => (
                            <div key={c.name} style={{ backgroundColor: '#111827', padding: '8px 12px', borderRadius: 4, border: '1px solid #374151' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                                    <span style={{ fontWeight: 'bold' }}>{c.name}</span>
                                    <span style={{ fontSize: 11, padding: '1px 6px', borderRadius: 3, backgroundColor: c.status.startsWith('running') ? '#059669' : '#dc2626' }}>{c.status}</span>
                                </div>
                                <div style={{ fontSize: 11, color: '#9ca3af' }}>Image: {c.image}</div>
                                {c.ports && c.ports.length > 0 && (
                                    <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>Ports: {c.ports.join(', ')}</div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div style={{ marginBottom: 25 }}>
                <h4 style={{ borderBottom: '1px solid #374151', paddingBottom: 5, marginBottom: 12, color: '#9ca3af', fontSize: 13, textTransform: 'uppercase' }}>Required Containers ({app.required_containers.length})</h4>
                {app.required_containers.length === 0 ? <div style={{ color: '#9ca3af', fontSize: 13 }}>None</div> : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {app.required_containers.map(c => (
                            <div key={c.name} style={{ backgroundColor: '#111827', padding: '8px 12px', borderRadius: 4, border: '1px solid #374151' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                                    <span style={{ fontWeight: 'bold' }}>{c.name}</span>
                                    <span style={{ fontSize: 11 }}>{c.missing ? <span style={{ color: '#ef4444' }}>MISSING ❌</span> : <span style={{ color: '#2ecc71' }}>READY ✅</span>}</span>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#9ca3af' }}>
                                    <span>Role: {c.role}</span>
                                    <span>Exit Code: {c.exit_code !== null ? c.exit_code : 'N/A'}</span>
                                </div>
                                <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>Status: {c.status}</div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div style={{ marginBottom: 25 }}>
                <h4 style={{ borderBottom: '1px solid #374151', paddingBottom: 5, marginBottom: 12, color: '#9ca3af', fontSize: 13, textTransform: 'uppercase' }}>Media Paths ({app.media.length})</h4>
                {app.media.length === 0 ? <div style={{ color: '#9ca3af', fontSize: 13 }}>None</div> : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {app.media.map(m => (
                            <div key={m.path} style={{ fontSize: 13 }}>
                                <div style={{ color: m.exists ? '#f3f4f6' : '#9ca3af' }}>{m.path} {m.exists ? '✅' : '❌'}</div>
                                <div style={{ fontSize: 11, color: '#9ca3af', marginLeft: 15 }}>
                                    {m.exists ? fmtSize(m.size_mb) : 'Missing'} {m.warning ? `| ${m.warning}` : ''}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div style={{ marginBottom: 25 }}>
                <h4 style={{ borderBottom: '1px solid #374151', paddingBottom: 5, marginBottom: 12, color: '#9ca3af', fontSize: 13, textTransform: 'uppercase' }}>Configurations ({app.configs.length})</h4>
                {app.configs.length === 0 ? <div style={{ color: '#9ca3af', fontSize: 13 }}>None</div> : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {app.configs.map(c => (
                            <div key={c.path} style={{ fontSize: 13 }}>
                                <div style={{ color: c.exists ? '#f3f4f6' : '#9ca3af' }}>{c.path} {c.exists ? '✅' : '❌'}</div>
                                {c.exists && <div style={{ fontSize: 11, color: '#9ca3af', marginLeft: 15 }}>{c.size_kb} KB</div>}
                            </div>
                        ))}
                    </div>
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
    const [showIssues, setShowIssues] = React.useState(false)

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
                    <div className="title">Backup UI Inventory</div>
                    <div className="subtitle">Phase B-UI2 — Per-App Breakdown</div>
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                    <Button disabled={busy} onClick={loadPlan}>{busy ? 'Refreshing...' : 'Refresh Plan'}</Button>
                    <Link to="/" className="btn" style={{ textDecoration: 'none', background: '#374151' }}>Back</Link>
                </div>
            </div>

            {error ? <div style={{ padding: 15, background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', borderRadius: 8, marginBottom: 20, color: '#ef4444' }}>{error}</div> : null}

            {/* Summary Panel */}
            {plan && (
                <div style={{ marginBottom: 25 }}>
                    <Card>
                        <div style={{ display: 'flex', gap: 25, flexWrap: 'wrap', alignItems: 'center', padding: '5px 0' }}>
                            <div style={{ textAlign: 'center' }}>
                                <div style={{ fontSize: 28, fontWeight: 'bold', color: '#60a5fa' }}>{fmtSize(summary.estimated_total_mb)}</div>
                                <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>ESTIMATED TOTAL</div>
                            </div>
                            <div style={{ width: 1, height: 50, background: '#374151' }}></div>
                            <div style={{ textAlign: 'center' }}>
                                <div style={{ fontSize: 24, fontWeight: 'bold' }}>{summary.apps_count}</div>
                                <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>APPS</div>
                            </div>
                            <div style={{ textAlign: 'center' }}>
                                <div style={{ fontSize: 24, fontWeight: 'bold' }}>{summary.db_containers_count}</div>
                                <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>REQUIRED DBs</div>
                            </div>
                            <div style={{ textAlign: 'center' }}>
                                <div style={{ fontSize: 24, fontWeight: 'bold' }}>{summary.media_paths_count}</div>
                                <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>MEDIA PATHS</div>
                            </div>
                            <div style={{ flex: 1 }}></div>
                            <div style={{ textAlign: 'right' }}>
                                <div
                                    onClick={() => summary.issues?.length > 0 && setShowIssues(!showIssues)}
                                    style={{
                                        padding: '8px 16px',
                                        borderRadius: 6,
                                        background: summary.ready ? 'rgba(5, 150, 105, 0.2)' : 'rgba(220, 38, 38, 0.2)',
                                        border: `1px solid ${summary.ready ? '#059669' : '#dc2626'}`,
                                        fontWeight: 'bold',
                                        color: summary.ready ? '#10b981' : '#ef4444',
                                        cursor: summary.issues?.length > 0 ? 'pointer' : 'default',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 8
                                    }}>
                                    {summary.ready ? '● SYSTEM READY' : `● ${summary.issues?.length || 0} WARNINGS`}
                                    {summary.issues?.length > 0 && <span style={{ fontSize: 10 }}>{showIssues ? '▲' : '▼'}</span>}
                                </div>
                            </div>
                        </div>
                        {showIssues && summary.issues && summary.issues.length > 0 && (
                            <div style={{ marginTop: 20, padding: 15, background: 'rgba(0,0,0,0.2)', borderRadius: 6, border: '1px solid #374151' }}>
                                {summary.issues.map((iss, i) => <div key={i} style={{ color: '#ef4444', fontSize: 13, marginBottom: 5 }}>• {iss}</div>)}
                            </div>
                        )}
                    </Card>
                </div>
            )}

            {/* Inventory Table */}
            {plan && (
                <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ background: '#1f2937', borderBottom: '1px solid #374151', textAlign: 'left' }}>
                                <th style={{ padding: '15px 20px', fontSize: 13, color: '#9ca3af' }}>APP</th>
                                <th style={{ padding: '15px 20px', fontSize: 13, color: '#9ca3af' }}>FOLDER</th>
                                <th style={{ padding: '15px 20px', fontSize: 13, color: '#9ca3af' }}>CONTAINERS</th>
                                <th style={{ padding: '15px 20px', fontSize: 13, color: '#9ca3af' }}>REQUIRED</th>
                                <th style={{ padding: '15px 20px', fontSize: 13, color: '#9ca3af' }}>MEDIA SIZE</th>
                                <th style={{ padding: '15px 20px', fontSize: 13, color: '#9ca3af' }}>TOTAL</th>
                                <th style={{ padding: '15px 20px', fontSize: 13, color: '#9ca3af' }}>STATUS</th>
                            </tr>
                        </thead>
                        <tbody>
                            {apps.map(app => (
                                <tr key={app.key}
                                    onClick={() => setSelectedApp(app)}
                                    className="tr-hover"
                                    style={{ borderBottom: '1px solid #374151', cursor: 'pointer', transition: 'background 0.2s' }}
                                >
                                    <td style={{ padding: '15px 20px' }}>
                                        <div style={{ fontWeight: 'bold', color: '#f3f4f6' }}>{app.name}</div>
                                        <div style={{ fontSize: 11, color: '#9ca3af' }}>{app.key}</div>
                                    </td>
                                    <td style={{ padding: '15px 20px' }}>
                                        <div style={{ fontSize: 12, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#9ca3af' }} title={app.folder}>{app.folder}</div>
                                        <div style={{ fontSize: 10, marginTop: 4, fontWeight: 'bold', color: app.folder_exists ? '#059669' : '#dc2626' }}>
                                            {app.folder_exists ? '● EXISTS' : '○ MISSING'}
                                        </div>
                                    </td>
                                    <td style={{ padding: '15px 20px' }}>
                                        <div
                                            style={{ fontSize: 13 }}
                                            title={app.running_containers.map(c => `${c.name} (${c.status})`).join('\n')}
                                        >
                                            {app.running_containers.length} running
                                        </div>
                                    </td>
                                    <td style={{ padding: '15px 20px' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <span style={{ fontSize: 13 }}>{app.required_containers.length}</span>
                                            {app.required_containers.some(c => c.missing) && (
                                                <span style={{ backgroundColor: 'rgba(220, 38, 38, 0.2)', color: '#ef4444', fontSize: 10, padding: '2px 6px', borderRadius: 4, border: '1px solid #dc2626', fontWeight: 'bold' }}>MISSING</span>
                                            )}
                                        </div>
                                    </td>
                                    <td style={{ padding: '15px 20px' }}>
                                        <div style={{ fontSize: 13 }}>{fmtSize(app.media.reduce((acc, m) => acc + (m.size_mb || 0), 0))}</div>
                                        <div style={{ fontSize: 10, color: '#9ca3af' }}>{app.media.filter(m => m.exists).length} paths</div>
                                    </td>
                                    <td style={{ padding: '15px 20px', fontWeight: 'bold', color: '#60a5fa' }}>{fmtSize(app.estimated_app_total_mb)}</td>
                                    <td style={{ padding: '15px 20px' }}>
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
                    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', zIndex: 999, backdropFilter: 'blur(2px)' }} onClick={() => setSelectedApp(null)}></div>
                    <Drawer app={selectedApp} onClose={() => setSelectedApp(null)} />
                </>
            )}

            <style>{`
        .tr-hover:hover {
            background-color: rgba(255, 255, 255, 0.03);
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 30px;
        }
        .title {
            font-size: 24px;
            font-weight: bold;
            color: #f3f4f6;
        }
        .subtitle {
            font-size: 14px;
            color: #9ca3af;
            margin-top: 4px;
        }
        .btn {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 6px;
            background: #2563eb;
            color: #fff;
            font-weight: 500;
            border: none;
            cursor: pointer;
            font-size: 14px;
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
      `}</style>
        </div>
    )
}
