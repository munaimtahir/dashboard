import React from 'react'

export default function Button({ variant, children, ...props }) {
  const klass = ['btn', variant ? variant : ''].join(' ').trim()
  return (
    <button className={klass} {...props}>
      {children}
    </button>
  )
}
