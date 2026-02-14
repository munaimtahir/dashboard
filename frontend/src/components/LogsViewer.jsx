import React from 'react'
import Card from './Card.jsx'

export default function LogsViewer({ lines, setLines, log, loading, error }) {
  return (
    <Card title="Logs">
      <div className="row" style={{ marginBottom: 10 }}>
        <div className="small">Tail</div>
        <select
          className="input"
          style={{ maxWidth: 180 }}
          value={lines}
          onChange={(e) => setLines(parseInt(e.target.value, 10))}
        >
          <option value={100}>100</option>
          <option value={200}>200</option>
          <option value={500}>500</option>
        </select>
      </div>
      {loading ? <div className="small">Loading logs...</div> : null}
      {error ? <div className="small" style={{ color: '#f39c12' }}>{String(error)}</div> : null}
      <pre className="logs">{log || ''}</pre>
    </Card>
  )
}
