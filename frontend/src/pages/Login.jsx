import React from 'react'
import { useNavigate } from 'react-router-dom'
import Card from '../components/Card.jsx'
import Button from '../components/Button.jsx'
import { api, setToken } from '../api.js'

export default function Login() {
  const nav = useNavigate()
  const [password, setPassword] = React.useState('')
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState('')

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await api.login(password)
      setToken(res.token)
      nav('/')
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container" style={{ maxWidth: 520 }}>
      <div className="header">
        <div>
          <div className="title">Dashboard v1</div>
          <div className="subtitle">Admin login</div>
        </div>
      </div>

      <Card title="Password">
        <form onSubmit={onSubmit}>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter admin password"
            autoFocus
          />
          <div style={{ height: 10 }} />
          <Button className="btn" variant="primary" disabled={loading || !password}>
            {loading ? 'Signing in...' : 'Sign in'}
          </Button>
          {error ? <div className="small" style={{ marginTop: 10, color: '#f39c12' }}>{error}</div> : null}
        </form>
      </Card>
    </div>
  )
}
