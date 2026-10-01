import { useEffect } from 'react'

function Item({ t, onClose }) {
  useEffect(() => {
    if (t.type === 'error') return undefined // errors stay until closed
    const id = setTimeout(() => onClose(t.id), 5000)
    return () => clearTimeout(id)
  }, [t, onClose])
  return (
    <div className={`toast toast-${t.type}`} role={t.type === 'error' ? 'alert' : 'status'}>
      <span>{t.message}</span>
      {t.action && (
        <button type="button" style={{ fontSize: '0.85rem', textDecoration: 'underline' }}
          onClick={() => { t.action.onClick(); onClose(t.id) }}>{t.action.label}</button>
      )}
      <button type="button" aria-label="Dismiss notification" onClick={() => onClose(t.id)}>×</button>
    </div>
  )
}

export default function Toasts({ toasts, onClose }) {
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => <Item key={t.id} t={t} onClose={onClose} />)}
    </div>
  )
}
