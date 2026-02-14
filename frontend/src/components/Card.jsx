import React from 'react'

export default function Card({ title, children, style }) {
  return (
    <div className="card" style={style}>
      {title ? <h3>{title}</h3> : null}
      {children}
    </div>
  )
}
