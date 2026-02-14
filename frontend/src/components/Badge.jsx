import React from 'react'

function cls(status) {
  if (status === 'HEALTHY' || status === true || status === 'running') return 'good'
  if (status === 'DEGRADED') return 'warn'
  return 'bad'
}

export default function Badge({ label, status }) {
  return (
    <span className="badge">
      <span className={`dot ${cls(status)}`} />
      <span>{label}</span>
    </span>
  )
}
