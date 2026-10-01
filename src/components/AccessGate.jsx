import { useState } from 'react'
import { api, setAccessCode } from '../api/client.js'

export default function AccessGate({ onUnlocked }) {
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    setAccessCode(code)
    try {
      await api.authCheck()
      onUnlocked()
    } catch {
      setAccessCode('')
      setError('That access code was not accepted.')
    }
    setBusy(false)
  }
  return (
    <div className="gate">
      <form onSubmit={submit}>
        <h2>Resume Finder</h2>
        <p className="muted">Enter the access code to continue.</p>
        <label htmlFor="code" className="sr-only">Access code</label>
        <input id="code" type="password" autoComplete="off" value={code} onChange={(e) => setCode(e.target.value)} placeholder="Access code" autoFocus />
        {error && <p className="error-text" role="alert">{error}</p>}
        <button className="btn btn-primary" disabled={!code || busy}>{busy ? 'Checking…' : 'Continue'}</button>
      </form>
    </div>
  )
}
