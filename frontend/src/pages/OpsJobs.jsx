import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import Card from '../components/Card.jsx'
import Badge from '../components/Badge.jsx'
import LogsViewer from '../components/LogsViewer.jsx'
import { api } from '../api.js'

function fmtTime(ts) {
    if (!ts) return '-'
    return new Date(ts * 1000).toLocaleString()
}

export default function OpsJobs() {
    const [logs, setLogs] = useState([])
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    // For viewing specific logs
    const [viewLogKey, setViewLogKey] = useState(null)
    const [logContent, setLogContent] = useState('')
    const [logLoading, setLogLoading] = useState(false)
    const [logError, setLogError] = useState('')

    async function load() {
        setLoading(true)
        setError('')
        try {
            const data = await api.auditLogs(100)
            setLogs(data)
        } catch (e) {
            setError(e.message || String(e))
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => { load() }, [])

    async function viewLog(key) {
        setViewLogKey(key)
        setLogLoading(true)
        setLogContent('')
        setLogError('')
        try {
            const text = await api.opsLogs(key, 500)
            setLogContent(text)
        } catch (e) {
            setLogError(e.message || String(e))
        } finally {
            setLogLoading(false)
        }
    }

    return (
        <div className="container">
            <div className="header">
                <div>
                    <div className="title">Ops Jobs</div>
                    <div className="subtitle">Audit log of recent actions</div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <Link to="/" className="btn">Back</Link>
                    <button className="btn" onClick={load}>Refresh</button>
                </div>
            </div>

            {error ? <div className="card" style={{ borderColor: 'rgba(243,156,18,0.35)' }}>{error}</div> : null}

            <Card>
                <table className="table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>App</th>
                            <th>Action</th>
                            <th>Result</th>
                            <th>Exit</th>
                            <th>Message</th>
                            <th>User/IP</th>
                            <th>Log</th>
                        </tr>
                    </thead>
                    <tbody>
                        {logs.map(L => {
                            const isOps = L.action.startsWith('ops:')
                            const appKey = L.app_key
                            return (
                                <tr key={L.id}>
                                    <td style={{ fontSize: '0.85em', whiteSpace: 'nowrap' }}>{fmtTime(L.timestamp)}</td>
                                    <td>
                                        <Link to={`/app/${appKey}`} style={{ fontWeight: 'bold', color: 'inherit', textDecoration: 'none' }}>
                                            {appKey}
                                        </Link>
                                    </td>
                                    <td>{L.action}</td>
                                    <td>
                                        <Badge
                                            label={L.result}
                                            status={L.result === 'success' ? 'HEALTHY' : 'DOWN'}
                                        />
                                    </td>
                                    <td>{L.exit_code !== null ? L.exit_code : '-'}</td>
                                    <td style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={L.message}>
                                        {L.message}
                                    </td>
                                    <td style={{ fontSize: '0.85em' }}>{L.client_ip}</td>
                                    <td>
                                        {isOps && (
                                            <button className="btn small" onClick={() => viewLog(appKey)}>
                                                Latest Log
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            )
                        })}
                        {!loading && logs.length === 0 && (
                            <tr>
                                <td colSpan={8} style={{ textAlign: 'center', padding: 20 }}>No logs found</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </Card>

            {/* Modal for viewing log */}
            {viewLogKey && (
                <div className="modalOverlay" role="dialog" aria-modal="true" onClick={() => setViewLogKey(null)}>
                    <div className="modal" style={{ maxWidth: 900, width: '90%', height: '80vh', display: 'flex', flexDirection: 'column' }} onClick={e => e.stopPropagation()}>
                        <div className="modalTitle">Latest Ops Log: {viewLogKey}</div>
                        <div className="modalBody" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                            <LogsViewer
                                lines={500}
                                log={logContent}
                                loading={logLoading}
                                error={logError}
                                onRefresh={() => viewLog(viewLogKey)}
                                disableAutoRefresh={true}
                            />
                        </div>
                        <div className="modalActions">
                            <button className="btn" onClick={() => setViewLogKey(null)}>Close</button>
                        </div>
                    </div>
                </div>
            )}

        </div>
    )
}
