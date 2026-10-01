import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client.js'
import EmptyState from './EmptyState.jsx'
import { RefreshIcon } from './Icons.jsx'
import { RoleChip } from './StatusChip.jsx'
import { fmtDate } from '../utils.js'

const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

// "2026-10-12T10:30" -> "Monday, 12 October 2026, 10:30 AM"
export function formatInterview(local) {
  if (!local) return ''
  const [d, t] = local.split('T')
  const [y, m, day] = d.split('-').map(Number)
  const [hh, mm] = t.split(':').map(Number)
  const dt = new Date(y, m - 1, day)
  const h12 = hh % 12 === 0 ? 12 : hh % 12
  return `${DAYS[dt.getDay()]}, ${day} ${MONTHS[m - 1]} ${y}, ${h12}:${String(mm).padStart(2, '0')} ${hh >= 12 ? 'PM' : 'AM'}`
}

const STATUS = { draft: ['Draft', 'chip-amber'], failed: ['Send failed', 'chip-red'], sent: ['Sent', 'chip-green'], sending: ['Sending', 'chip-blue'] }

function SendDialog({ item, from, busy, onCancel, onConfirm }) {
  const ref = useRef(null)
  useEffect(() => {
    const prev = document.activeElement
    ref.current?.querySelector('button')?.focus()
    const onKey = (e) => {
      if (e.key === 'Escape' && !busy) onCancel()
      if (e.key !== 'Tab') return
      const f = ref.current?.querySelectorAll('button:not(:disabled)')
      if (!f?.length) return
      const first = f[0], last = f[f.length - 1]
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); prev?.focus?.() }
  }, [busy, onCancel])
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && !busy && onCancel()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="send-title" ref={ref}>
        <h2 id="send-title" style={{ color: 'var(--blue-900)' }}>Send this email?</h2>
        <p>This will send a real email to the candidate. It cannot be unsent.</p>
        <dl className="send-facts">
          <dt>To</dt><dd>{item.full_name} &lt;{item.to_email}&gt;</dd>
          <dt>From</dt><dd>{from}</dd>
          <dt>Subject</dt><dd>{item.subject}</dd>
          <dt>Interview</dt><dd>{item.interview_at}</dd>
        </dl>
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className="btn btn-primary" onClick={onConfirm} disabled={busy}>
            {busy ? <><span className="spinner" /> Sending…</> : 'Yes, send email'}
          </button>
        </div>
      </div>
    </div>
  )
}

function EmailCard({ item, from, edit, onChange, onSave, onSend, busy }) {
  const dirty = edit && (edit.subject !== item.subject || edit.body !== item.body)
  const [label, cls] = STATUS[item.status] || STATUS.draft
  const subject = edit?.subject ?? item.subject
  const body = edit?.body ?? item.body
  const id = `em-${item.candidate_id}`
  return (
    <article className="card email-card" aria-labelledby={`${id}-h`}>
      <header className="email-head">
        <div>
          <h3 id={`${id}-h`}>{item.full_name || 'Name not found'} <RoleChip role={item.role} /></h3>
          <div className="muted">To: {item.to_email || <span className="notfound">Not found</span>} - score {item.weighted_score.toFixed(1)}</div>
        </div>
        <span className={`chip ${cls}`}>{label}</span>
      </header>
      <label htmlFor={`${id}-s`} className="field-label">Subject</label>
      <input id={`${id}-s`} className="text-input" value={subject} disabled={!item.editable}
        onChange={(e) => onChange(item.candidate_id, { subject: e.target.value, body })} />
      <label htmlFor={`${id}-b`} className="field-label">Message</label>
      <textarea id={`${id}-b`} className="text-area" rows={16} value={body} disabled={!item.editable}
        onChange={(e) => onChange(item.candidate_id, { subject, body: e.target.value })} />
      {item.status === 'sent' && <p className="queue-note">Sent on {fmtDate(item.sent_at)}. Sent emails cannot be edited.</p>}
      {item.status === 'failed' && item.error && <p className="queue-note bad" role="alert">{item.error}</p>}
      {item.editable && item.blockers.length > 0 && <ul className="blockers">{item.blockers.map((b) => <li key={b}>{b}</li>)}</ul>}
      {item.editable && (
        <div className="email-actions">
          <button className="btn btn-secondary" disabled={!dirty || busy} onClick={() => onSave(item.candidate_id)}>Save changes</button>
          <button className="btn btn-primary" disabled={!item.can_send || dirty || busy} onClick={() => onSend(item)}
            title={dirty ? 'Save your changes first' : undefined}>Review and send…</button>
          {dirty && <span className="muted">Unsaved changes. Save before sending.</span>}
        </div>
      )}
    </article>
  )
}

export default function EmailsTab({ notify, onGoUpload, onChanged }) {
  const [state, setState] = useState({ loaded: false, loading: false, emails: [], from: '', configured: true, interview_at: null })
  const [edits, setEdits] = useState({})
  const [when, setWhen] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [confirm, setConfirm] = useState(null)
  const [sending, setSending] = useState(false)

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true }))
    try {
      const r = await api.emails()
      setState({ loaded: true, loading: false, emails: r.emails, from: r.from, configured: r.configured, interview_at: r.interview_at })
      setEdits((e) => Object.fromEntries(Object.entries(e).filter(([id, v]) => {
        const it = r.emails.find((x) => x.candidate_id === id)
        return it && (v.subject !== it.subject || v.body !== it.body)
      })))
      onChanged?.(r.emails)
    } catch (e) {
      setState((s) => ({ ...s, loaded: true, loading: false }))
      notify('error', e.message || 'Could not load emails.')
    }
  }, [notify, onChanged])

  useEffect(() => { load() }, [load])

  const applyDate = async () => {
    const text = formatInterview(when)
    if (!text) return notify('warning', 'Choose a date and time first.')
    const dirtyCount = Object.keys(edits).length
    if (dirtyCount && !window.confirm('Some drafts have unsaved edits. Applying the date reloads them and discards those edits. Continue?')) return
    try {
      const r = await api.setInterviewDate(text)
      setEdits({})
      notify('success', `Interview date applied to ${r.updated} draft${r.updated === 1 ? '' : 's'}.`)
      await load()
    } catch (e) { notify('error', e.message) }
  }

  const save = async (id) => {
    setBusyId(id)
    try {
      await api.editEmail(id, edits[id])
      notify('success', 'Draft saved.')
      setEdits((e) => { const n = { ...e }; delete n[id]; return n })
      await load()
    } catch (e) { notify('error', e.message); await load() }
    setBusyId(null)
  }

  const doSend = async () => {
    setSending(true)
    try {
      await api.sendEmail(confirm.candidate_id, confirm.version)
      notify('success', `Email sent to ${confirm.full_name}.`)
      setConfirm(null)
    } catch (e) { notify('error', e.message); setConfirm(null) }
    setSending(false)
    await load()
  }

  const { emails, loaded, loading } = state
  const drafts = emails.filter((e) => e.status !== 'sent').length
  const testSender = /onboarding@resend\.dev/i.test(state.from)

  return (
    <section aria-labelledby="emails-h">
      <div className="toolbar">
        <h2 id="emails-h" className="grow">Emails</h2>
        <button className="btn btn-secondary" onClick={load} disabled={loading}>{loading ? <span className="spinner" /> : <RefreshIcon />} Refresh</button>
      </div>
      <div className="card" style={{ marginBottom: 16 }}>
        <p>Drafts are written only for <strong>shortlisted</strong> candidates. <strong>Nothing is sent until you review an email and confirm.</strong> You can edit any draft before sending.</p>
        <p className="muted" style={{ marginTop: 6 }}>From: {state.from || 'not set'} - Venue and phone number are filled in automatically.</p>
        {!state.configured && <p className="error-text" role="alert">Email sending is not configured on the server (RESEND_API_KEY is missing).</p>}
        {testSender && <p className="queue-note" style={{ color: 'var(--amber-fg)' }}>The sender is Resend's test address, which only delivers to your own Resend account email. Verify a domain in Resend and set RESEND_FROM to send to candidates.</p>}
        <div className="date-row">
          <label htmlFor="interview-when" className="field-label" style={{ margin: 0 }}>Interview date and time</label>
          <input id="interview-when" type="datetime-local" className="text-input" style={{ maxWidth: 240 }} value={when} onChange={(e) => setWhen(e.target.value)} />
          <button className="btn btn-secondary" onClick={applyDate} disabled={!when || !emails.some((e) => e.editable)}>Apply to all drafts</button>
        </div>
        {state.interview_at && <p className="muted" style={{ marginTop: 6 }}>Current: {state.interview_at}</p>}
      </div>

      {!loaded ? (
        <div className="card">{[...Array(4)].map((_, i) => <div key={i} className="skeleton" style={{ margin: '14px 0', width: `${90 - i * 10}%` }} />)}</div>
      ) : emails.length === 0 ? (
        <EmptyState onGoUpload={onGoUpload} title="No shortlisted candidates yet" text="Emails are drafted only for candidates the system recommends to shortlist." />
      ) : (
        <>
          <p className="summary-line" style={{ marginBottom: 12 }}>{emails.length} email{emails.length === 1 ? '' : 's'} - {drafts} not yet sent</p>
          <div className="email-list">
            {emails.map((it) => (
              <EmailCard key={it.candidate_id} item={it} from={state.from} edit={edits[it.candidate_id]} busy={busyId === it.candidate_id}
                onChange={(id, v) => setEdits((e) => ({ ...e, [id]: v }))} onSave={save} onSend={setConfirm} />
            ))}
          </div>
        </>
      )}
      {confirm && <SendDialog item={confirm} from={state.from} busy={sending} onCancel={() => setConfirm(null)} onConfirm={doSend} />}
    </section>
  )
}
