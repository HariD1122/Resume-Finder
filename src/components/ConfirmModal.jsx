import { useEffect, useRef, useState } from 'react'

export default function ConfirmModal({ open, busy, onCancel, onConfirm }) {
  const [text, setText] = useState('')
  const ref = useRef(null)
  const input = useRef(null)

  useEffect(() => {
    if (!open) { setText(''); return undefined }
    const prev = document.activeElement
    input.current?.focus()
    const onKey = (e) => {
      if (e.key === 'Escape' && !busy) { onCancel(); return }
      if (e.key !== 'Tab') return
      const f = ref.current?.querySelectorAll('button:not(:disabled), input')
      if (!f || !f.length) return
      const first = f[0]
      const last = f[f.length - 1]
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); prev?.focus?.() }
  }, [open, busy, onCancel])

  if (!open) return null
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && !busy && onCancel()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="reset-title" aria-describedby="reset-desc" ref={ref}>
        <h2 id="reset-title">Reset all data?</h2>
        <p id="reset-desc">This permanently deletes every candidate, score, extracted contact and stored resume file for BOTH roles. This cannot be undone.</p>
        <label htmlFor="reset-confirm" className="muted" style={{ display: 'block', marginTop: 12 }}>Type <b>RESET</b> to confirm</label>
        <input id="reset-confirm" ref={input} value={text} onChange={(e) => setText(e.target.value)} autoComplete="off" />
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className="btn btn-danger-solid" onClick={onConfirm} disabled={text !== 'RESET' || busy}>
            {busy ? <><span className="spinner" /> Deleting…</> : 'Delete everything'}
          </button>
        </div>
      </div>
    </div>
  )
}
