import React, { useState, useEffect } from 'react'
import Card from './Card.jsx'
import Badge from './Badge.jsx'
import Spinner from './Spinner.jsx'
import { api } from '../api.js'

export default function InspectorTab({ appKey }) {
    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [refreshing, setRefreshing] = useState(false)

    async function load(fresh = 0) {
        if (fresh) setRefreshing(true)
        else setLoading(true)
        setError('')
        try {
            const res = await api.inspect(appKey, fresh)
            setData(res)
        } catch (e) {
            setError(e.message || String(e))
        } finally {
            setLoading(false)
            setRefreshing(false)
        }
    }

    useEffect(() => { load() }, [appKey])

    if (loading) return <div style={{ padding: 40, textAlign: 'center' }}><Spinner /></div>

    if (error) return <Card title="Inspector Error"><div style={{ color: 'var(--bad)' }}>{error}</div></Card>

    if (!data) return null

    const { identity, containers, storage, databases, routing, issues } = data

    return (
        <div className="inspector-tab">
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
                <button className="btn" disabled={refreshing} onClick={() => load(1)}>
                    {refreshing ? <span className="btnInline"><Spinner size={14} /> Refreshing</span> : 'Refresh Inspector'}
                </button>
            </div>

            {issues && issues.length > 0 && (
                <Card title="Detected Issues" style={{ borderColor: 'rgba(231,76,60,0.4)', marginBottom: 20, background: 'rgba(231,76,60,0.05)' }}>
                    <ul style={{ margin: 0, paddingLeft: 20, color: 'var(--bad)' }}>
                        {issues.map((iss, i) => <li key={i} className="small" style={{ marginBottom: 4 }}>{iss}</li>)}
                    </ul>
                </Card>
            )}

            {/* Overview Section */}
            <div className="grid" style={{ marginBottom: 20 }}>
                <div style={{ gridColumn: 'span 12' }}>
                    <Card title="Overview">
                        <div className="grid">
                            <div style={{ gridColumn: 'span 4' }}>
                                <div className="small">Folder</div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                                    <code style={{ fontSize: 11, background: 'rgba(0,0,0,0.2)', padding: '2px 4px', borderRadius: 4 }}>{identity.folder}</code>
                                    <Badge label={identity.folder_exists ? 'Exists' : 'Missing'} status={identity.folder_exists ? 'HEALTHY' : 'DOWN'} />
                                </div>
                                <div className="small" style={{ marginTop: 8 }}>
                                    <b>Size:</b> {storage.folder_size_mb !== null ? `${storage.folder_size_mb} MB` : 'unknown'}
                                </div>
                            </div>
                            <div style={{ gridColumn: 'span 4' }}>
                                <div className="small">Compose Project</div>
                                <div style={{ fontWeight: 600, marginTop: 4 }}>{identity.compose_project || 'N/A'}</div>
                                <div className="small" style={{ marginTop: 8 }}>
                                    <b>Services:</b> {identity.compose_services.join(', ') || 'none'}
                                </div>
                            </div>
                            <div style={{ gridColumn: 'span 4' }}>
                                <div className="small">Routing (Caddy)</div>
                                <div style={{ marginTop: 4 }}>
                                    {routing && routing.length > 0 ? (
                                        routing.map((r, i) => (
                                            <div key={i} style={{ marginBottom: 8, padding: 6, background: 'rgba(255,255,255,0.03)', borderRadius: 6 }}>
                                                <div style={{ fontSize: 12, fontWeight: 600 }}>{r.domain}</div>
                                                <div className="small">→ {r.upstream}</div>
                                                <div className="small" style={{ marginTop: 4 }}>
                                                    {r.upstream_listening ? (
                                                        <span style={{ color: 'var(--good)' }}>● Upstream reachable on host</span>
                                                    ) : (
                                                        <span style={{ color: 'var(--warn)' }}>○ Port not listening on host</span>
                                                    )}
                                                </div>
                                            </div>
                                        ))
                                    ) : (
                                        <div className="small" style={{ color: 'var(--warn)' }}>No routing found for this app</div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </Card>
                </div>
            </div>

            {/* Containers Section */}
            <Card title="Containers Detail" style={{ marginBottom: 20 }}>
                <table className="table">
                    <thead>
                        <tr>
                            <th>Container</th>
                            <th>Image</th>
                            <th>Status / Health</th>
                            <th>Ports / Network</th>
                            <th style={{ textAlign: 'center' }}>Restarts</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(containers || []).map(c => (
                            <React.Fragment key={c.name}>
                                <tr>
                                    <td>
                                        <div style={{ fontWeight: 600 }}>{c.name}</div>
                                        <div className="small" style={{ opacity: 0.6 }}>{c.id_short}</div>
                                    </td>
                                    <td>
                                        <div className="small" style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={c.image}>
                                            {c.image}
                                        </div>
                                        <div className="small" style={{ opacity: 0.5, fontSize: 10 }}>Created: {new Date(c.created).toLocaleString()}</div>
                                    </td>
                                    <td>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <div className={`dot ${c.status === 'running' ? 'good' : (c.status === 'exited' && c.exit_code === 0 ? 'muted' : 'bad')}`} />
                                            <span style={{ textTransform: 'capitalize' }}>{c.status}</span>
                                        </div>
                                        <div className="small">Health: {c.health}</div>
                                        {c.exit_code !== 0 && c.exit_code !== null && <div className="small" style={{ color: 'var(--bad)' }}>Exit Code: {c.exit_code}</div>}
                                    </td>
                                    <td>
                                        {c.ports.length > 0 && (
                                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 4 }}>
                                                {c.ports.map((p, i) => <span key={i} className="small" style={{ background: 'rgba(255,255,255,0.05)', padding: '1px 4px', borderRadius: 3 }}>{p}</span>)}
                                            </div>
                                        )}
                                        {c.networks.map(n => (
                                            <div key={n.name} className="small" style={{ opacity: 0.8 }}>
                                                {n.name}: <span style={{ color: 'var(--accent)' }}>{n.ip_address}</span>
                                            </div>
                                        ))}
                                    </td>
                                    <td className="small" style={{ textAlign: 'center' }}>{c.restart_count}</td>
                                </tr>
                                <tr>
                                    <td colSpan="5" style={{ padding: '4px 8px 12px', borderBottom: '1px solid var(--border)' }}>
                                        <details style={{ cursor: 'pointer' }}>
                                            <summary className="small" style={{ opacity: 0.6 }}>View internal details (Mounts, Labels, Env Keys)</summary>
                                            <div style={{ padding: '12px', marginTop: 8, background: 'rgba(0,0,0,0.15)', borderRadius: 8, display: 'grid', gridTemplateColumns: 'minmax(0, 1.5fr) minmax(0, 1fr)', gap: 24 }}>
                                                <div>
                                                    <div className="small" style={{ fontWeight: 600, marginBottom: 6, color: 'var(--accent)' }}>Mounts</div>
                                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                                        {data.storage.bind_mounts.filter(bm => bm.usages.some(u => u.container === c.name)).map((bm, i) => (
                                                            bm.usages.filter(u => u.container === c.name).map((u, j) => (
                                                                <div key={`${i}-${j}`} className="small" style={{ display: 'flex', flexDirection: 'column', borderLeft: '2px solid var(--border)', paddingLeft: 8 }}>
                                                                    <div style={{ fontWeight: 600 }}>{u.destination}</div>
                                                                    <div style={{ opacity: 0.6, fontSize: 10 }}>← bind:{bm.source} ({u.rw ? 'rw' : 'ro'})</div>
                                                                </div>
                                                            ))
                                                        ))}
                                                        {data.storage.named_volumes.filter(nv => nv.used_by.some(u => u.container === c.name)).map((nv, i) => (
                                                            nv.used_by.filter(u => u.container === c.name).map((u, j) => (
                                                                <div key={`${i}-${j}`} className="small" style={{ display: 'flex', flexDirection: 'column', borderLeft: '2px solid var(--accent)', paddingLeft: 8 }}>
                                                                    <div style={{ fontWeight: 600 }}>{u.destination}</div>
                                                                    <div style={{ opacity: 0.6, fontSize: 10 }}>← volume:{nv.name} ({u.rw ? 'rw' : 'ro'})</div>
                                                                </div>
                                                            ))
                                                        ))}
                                                    </div>
                                                </div>
                                                <div>
                                                    <div className="small" style={{ fontWeight: 600, marginBottom: 6, color: 'var(--accent)' }}>Environment (Keys Only)</div>
                                                    <div className="small" style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                                                        {c.env_keys.map((k, i) => <span key={i} style={{ opacity: 0.8 }}>{k}{i < c.env_keys.length - 1 ? ',' : ''}</span>)}
                                                    </div>
                                                    <div className="small" style={{ fontWeight: 600, marginTop: 12, marginBottom: 6, color: 'var(--accent)' }}>Labels</div>
                                                    <div style={{ maxHeight: 150, overflow: 'auto', padding: 6, background: 'rgba(0,0,0,0.2)', borderRadius: 4 }}>
                                                        {Object.entries(c.labels).map(([k, v], i) => (
                                                            <div key={i} className="small" style={{ fontSize: 10, borderBottom: '1px solid rgba(255,255,255,0.03)', padding: '2px 0' }}>
                                                                <span style={{ opacity: 0.5 }}>{k}:</span> {v}
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            </div>
                                        </details>
                                    </td>
                                </tr>
                            </React.Fragment>
                        ))}
                    </tbody>
                </table >
            </Card >

            {/* Storage Section */}
            < div className="grid" style={{ marginBottom: 20 }
            }>
                <div style={{ gridColumn: 'span 6' }}>
                    <Card title="Named Volumes">
                        {storage.named_volumes.length === 0 ? <div className="small" style={{ padding: 10 }}>No named volumes</div> : (
                            <table className="table">
                                <thead>
                                    <tr>
                                        <th>Volume Name</th>
                                        <th style={{ textAlign: 'right' }}>Estimated Size</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {storage.named_volumes.map(v => (
                                        <tr key={v.name}>
                                            <td>
                                                <div style={{ fontWeight: 600, fontSize: 13 }}>{v.name}</div>
                                                <div className="small" style={{ opacity: 0.5, fontSize: 10, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }} title={v.mountpoint}>Host: {v.mountpoint}</div>
                                                <div className="small" style={{ marginTop: 4 }}>Used by: {v.used_by.map(u => u.container).join(', ')}</div>
                                            </td>
                                            <td style={{ textAlign: 'right', verticalAlign: 'middle' }}>
                                                {v.size_estimate_mb !== null ? (
                                                    <span style={{ fontWeight: 600 }}>{v.size_estimate_mb} MB</span>
                                                ) : (
                                                    <span style={{ color: 'var(--warn)', fontSize: 10 }}>size unknown</span>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </Card>
                </div>
                <div style={{ gridColumn: 'span 6' }}>
                    <Card title="Bind Mounts">
                        {storage.bind_mounts.length === 0 ? <div className="small" style={{ padding: 10 }}>No bind mounts</div> : (
                            <table className="table">
                                <thead>
                                    <tr>
                                        <th>Host Source</th>
                                        <th style={{ textAlign: 'right' }}>Size</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {storage.bind_mounts.map(b => (
                                        <tr key={b.source}>
                                            <td>
                                                <div style={{ fontWeight: 600, fontSize: 13, wordBreak: 'break-all' }}>{b.source}</div>
                                                <div className="small" style={{ marginTop: 4 }}>
                                                    {b.usages.map((u, i) => <div key={i}>{u.container} → {u.destination}</div>)}
                                                </div>
                                            </td>
                                            <td style={{ textAlign: 'right', verticalAlign: 'middle' }}>
                                                {b.size_mb !== null ? (
                                                    <span style={{ fontWeight: 600 }}>{b.size_mb} MB</span>
                                                ) : (
                                                    <span style={{ color: 'var(--warn)', fontSize: 10 }}>size unknown</span>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </Card>
                </div>
            </div >

            {/* Databases Section */}
            {
                databases && databases.length > 0 && (
                    <Card title="Detected Databases" style={{ marginBottom: 20 }}>
                        <div className="grid">
                            {databases.map((db, i) => (
                                <div key={i} style={{ gridColumn: 'span 4', padding: 12, background: 'rgba(255,255,255,0.03)', borderRadius: 10, border: '1px solid var(--border)' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                                        <div className="dot good" />
                                        <div style={{ fontWeight: 700, fontSize: 15 }}>{db.type}</div>
                                    </div>
                                    <div className="small" style={{ marginBottom: 2 }}><b>Role:</b> {db.role}</div>
                                    <div className="small" style={{ marginBottom: 2 }}><b>Container:</b> {db.container}</div>
                                    <div className="small" style={{ opacity: 0.7, fontSize: 10, wordBreak: 'break-all' }}><b>Image:</b> {db.image}</div>
                                    <div className="small" style={{ marginTop: 8 }}>
                                        <b>Exposed Ports:</b> {db.ports.join(', ') || 'none'}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </Card>
                )
            }

            {/* Folder sizing detail */}
            {
                (storage.media_size_mb !== null || storage.uploads_size_mb !== null) && (
                    <Card title="Standard Volumes Sizing">
                        <div style={{ display: 'flex', gap: 40 }}>
                            {storage.media_size_mb !== null && (
                                <div>
                                    <div className="small">media/ folder</div>
                                    <div style={{ fontSize: 18, fontWeight: 700 }}>{storage.media_size_mb} <span style={{ fontSize: 12, fontWeight: 400 }}>MB</span></div>
                                </div>
                            )}
                            {storage.uploads_size_mb !== null && (
                                <div>
                                    <div className="small">uploads/ folder</div>
                                    <div style={{ fontSize: 18, fontWeight: 700 }}>{storage.uploads_size_mb} <span style={{ fontSize: 12, fontWeight: 400 }}>MB</span></div>
                                </div>
                            )}
                        </div>
                    </Card>
                )
            }
        </div >
    )
}
