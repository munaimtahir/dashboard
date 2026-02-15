import React from 'react'
import Card from './Card.jsx'
import Spinner from './Spinner.jsx'

export default function LogsViewer({ lines, setLines, log, loading, error, autoRefresh, setAutoRefresh, onRefresh, disableControls }) {
  return (
    <Card title="Logs">
      <div className="row" style={{ marginBottom: 10 }}>
        {!disableControls && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div className="small">Tail</div>
            <select
              className="input"
              style={{ maxWidth: 180 }}
              value={lines || 200}
              onChange={(e) => setLines && setLines(parseInt(e.target.value, 10))}
              disabled={!setLines}
            >
              <option value={100}>100</option>
              <option value={200}>200</option>
              <option value={500}>500</option>
            </select>
            {setAutoRefresh && (
              <label className="toggle">
                <input type="checkbox" checked={!!autoRefresh} onChange={(e) => setAutoRefresh(!!e.target.checked)} />
                <span>Auto refresh</span>
              </label>
            )}
          </div>
        )}
        <button className="btn" onClick={onRefresh} disabled={loading}>Refresh</button>
      </div>
      {loading ? <div className="small" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Spinner size={14} /> Loading logs...</div> : null}
      {error ? <div className="small" style={{ color: '#f39c12' }}>{String(error)}</div> : null}
      <pre className="logs">{log || ''}</pre>
    </Card>
  )
}
