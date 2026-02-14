import React from 'react'
import { Link } from 'react-router-dom'
import Badge from './Badge.jsx'

export default function AppGrid({ apps }) {
  return (
    <div className="card">
      <h3>Apps</h3>
      <table className="table">
        <thead>
          <tr>
            <th>App</th>
            <th>Containers</th>
            <th>Backend</th>
            <th>Frontend</th>
            <th>Overall</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {apps.map((a) => {
            const containersOk = a.container_info?.every((c) => c.exists && c.running)
            const backendOk = a.backend_check ? a.backend_check.ok : null
            const frontendOk = a.frontend_check ? a.frontend_check.ok : null

            return (
              <tr key={a.key}>
                <td>
                  <Link to={`/app/${encodeURIComponent(a.key)}`}
                    style={{ textDecoration: 'underline', textDecorationColor: 'rgba(255,255,255,0.25)' }}>
                    {a.name}
                  </Link>
                  <div className="small">{a.domain || a.key}</div>
                </td>
                <td>
                  <Badge label={containersOk ? 'OK' : 'Issue'} status={containersOk ? 'HEALTHY' : 'DOWN'} />
                  <div className="small" style={{ marginTop: 6 }}>
                    {(a.container_info || []).map((c) => (
                      <div key={c.name}>{c.name}: {c.status}{c.exit_code !== null && c.exit_code !== undefined ? ` (exit ${c.exit_code})` : ''}</div>
                    ))}
                  </div>
                </td>
                <td>
                  <Badge label={backendOk === null ? 'N/A' : (backendOk ? 'OK' : 'Fail')} status={backendOk ? 'HEALTHY' : 'DOWN'} />
                  <div className="small">{a.backend_health_url || ''}</div>
                </td>
                <td>
                  <Badge label={frontendOk === null ? 'N/A' : (frontendOk ? 'OK' : 'Fail')} status={frontendOk ? 'HEALTHY' : 'DOWN'} />
                  <div className="small">{a.frontend_url || ''}</div>
                </td>
                <td><Badge label={a.overall_status} status={a.overall_status} /></td>
                <td>
                  <div>{a.reason}</div>
                  <div className="small">{a.recommendation}</div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
