import React, { useState, useEffect } from 'react'
import Button from './Button.jsx'
import Spinner from './Spinner.jsx'
import { api } from '../api.js'

export default function InventoryModal({ open, onClose, onSuccess }) {
    const [step, setStep] = useState('preview') // preview, syncing, done
    const [preview, setPreview] = useState(null)
    const [error, setError] = useState('')
    const [busy, setBusy] = useState(false)

    useEffect(() => {
        if (open) {
            setStep('preview')
            setPreview(null)
            setError('')
            setBusy(false)
            loadPreview()
        }
    }, [open])

    async function loadPreview() {
        setBusy(true)
        setError('')
        try {
            const res = await api.inventoryPreview()
            setPreview(res.summary)
        } catch (e) {
            setError(e.message || String(e))
        } finally {
            setBusy(false)
        }
    }

    async function doSync() {
        setBusy(true)
        setError('')
        try {
            const res = await api.inventorySync()
            const newManifest = res.manifest
            setStep('done')
            if (onSuccess) onSuccess(newManifest)
        } catch (e) {
            setError(e.message || String(e))
        } finally {
            setBusy(false)
        }
    }

    if (!open) return null

    let content = null
    let actions = null

    if (step === 'preview') {
        if (busy && !preview) {
            content = (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 20 }}>
                    <Spinner /> Scanning inventory...
                </div>
            )
        } else if (preview) {
            const hasChanges = (preview.added.length > 0 || preview.removed.length > 0 || preview.updated.length > 0)

            content = (
                <div>
                    <div style={{ marginBottom: 12 }}>
                        {hasChanges ? 'Found the following changes:' : 'No changes found. Everything is up to date.'}
                    </div>

                    {preview.added.length > 0 && (
                        <div style={{ marginBottom: 8, padding: 8, background: '#e6fffa', borderRadius: 4 }}>
                            <strong>Added ({preview.added.length}):</strong>
                            <div style={{ fontFamily: 'monospace', fontSize: '0.9em', marginTop: 4 }}>
                                {preview.added.join(', ')}
                            </div>
                        </div>
                    )}

                    {preview.removed.length > 0 && (
                        <div style={{ marginBottom: 8, padding: 8, background: '#fff5f5', borderRadius: 4 }}>
                            <strong>Removed ({preview.removed.length}):</strong>
                            <div style={{ fontFamily: 'monospace', fontSize: '0.9em', marginTop: 4 }}>
                                {preview.removed.join(', ')}
                            </div>
                        </div>
                    )}

                    {preview.updated.length > 0 && (
                        <div style={{ marginBottom: 8, padding: 8, background: '#ebf8ff', borderRadius: 4 }}>
                            <strong>Updated ({preview.updated.length}):</strong>
                            <div style={{ fontFamily: 'monospace', fontSize: '0.9em', marginTop: 4 }}>
                                {preview.updated.join(', ')}
                            </div>
                        </div>
                    )}

                    {preview.skipped_folders && preview.skipped_folders.length > 0 && (
                        <div style={{ marginTop: 12, fontSize: '0.85em', color: '#666' }}>
                            Skipped {preview.skipped_folders.length} folders (test/tmp/empty)
                        </div>
                    )}
                </div>
            )

            actions = (
                <>
                    <Button onClick={onClose} disabled={busy}>
                        {hasChanges ? 'Cancel' : 'Close'}
                    </Button>
                    {hasChanges && (
                        <Button variant="primary" onClick={doSync} disabled={busy}>
                            Sync Changes
                        </Button>
                    )}
                </>
            )
        } else if (error) {
            content = <div style={{ color: 'red' }}>Error loading preview.</div>
            actions = <Button onClick={onClose}>Close</Button>
        }
    } else if (step === 'done') {
        content = (
            <div style={{ textAlign: 'center', padding: 20 }}>
                <div style={{ fontSize: 32, marginBottom: 10 }}>✅</div>
                <div>Inventory synced successfully!</div>
            </div>
        )
        actions = (
            <Button variant="primary" onClick={onClose}>
                Close
            </Button>
        )
    }

    return (
        <div className="modalOverlay" role="dialog" aria-modal="true">
            <div className="modal" style={{ maxWidth: 500, width: '100%' }}>
                <div className="modalTitle">Sync Apps Inventory</div>

                {error && step !== 'done' && (
                    <div style={{ padding: 10, marginBottom: 10, background: '#fff5f5', color: '#c53030', borderRadius: 4 }}>
                        {error}
                    </div>
                )}

                <div className="modalBody">
                    {content}
                </div>

                <div className="modalActions">
                    {actions}
                </div>
            </div>
        </div>
    )
}
