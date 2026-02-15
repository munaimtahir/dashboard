import React from 'react'
import Button from './Button.jsx'

export default function ConfirmModal({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  busy = false,
  onConfirm,
  onClose
}) {
  if (!open) return null

  return (
    <div className="modalOverlay" role="dialog" aria-modal="true">
      <div className="modal">
        <div className="modalTitle">{title || 'Confirm'}</div>
        <div className="modalBody">{message || ''}</div>
        <div className="modalActions">
          <Button disabled={busy} onClick={onClose}>Cancel</Button>
          <Button variant="primary" disabled={busy} onClick={onConfirm}>{confirmLabel}</Button>
        </div>
      </div>
    </div>
  )
}

