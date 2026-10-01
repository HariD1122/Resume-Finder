import { useRef, useState } from 'react'
import { UploadIcon } from './Icons.jsx'
import { RecChip, RoleChip } from './StatusChip.jsx'
import { fmtSize, ROLE_NAMES } from '../utils.js'

const BADGE = { Queued: 'chip-grey', Uploading: 'chip-blue', Reading: 'chip-blue', Extracting: 'chip-blue', Scoring: 'chip-blue', Saved: 'chip-green', Duplicate: 'chip-amber', Failed: 'chip-red' }
const PROGRESS = { Queued: 0, Reading: 40, Extracting: 60, Scoring: 80, Saved: 100, Duplicate: 100, Failed: 100 }

function UploadZone({ onFiles }) {
  const [over, setOver] = useState(false)
  const input = useRef(null)
  const open = () => input.current?.click()
  return (
    <div
      className={`dropzone${over ? ' over' : ''}`} role="button" tabIndex={0} aria-label="Drag and drop resumes here, or browse files"
      onClick={open} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), open())}
      onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); if (e.dataTransfer.files?.length) onFiles(e.dataTransfer.files) }}
    >
      <UploadIcon size={44} />
      <div className="big">Drag and drop resumes here</div>
      <div>or <span className="link">browse files</span></div>
      <p className="muted" style={{ marginTop: 8 }}>PDF or DOCX, up to 4 MB each. Multiple files allowed.</p>
      <input ref={input} type="file" multiple accept=".pdf,.docx,.doc" hidden
        onChange={(e) => { if (e.target.files?.length) onFiles(e.target.files); e.target.value = '' }} />
    </div>
  )
}

function Row({ it, onRetry, onRemove, onViewScores }) {
  const pct = it.status === 'Uploading' ? Math.round(it.progress * 0.3) : PROGRESS[it.status] ?? 0
  const res = it.result
  const hintMismatch = res && res.applied_role_hint && res.applied_role_hint !== 'unknown' && res.applied_role_hint !== it.role
  return (
    <li className="queue-row">
      <div>
        <div className="queue-name">{it.name}</div>
        <div className="queue-meta">
          <span>{fmtSize(it.size)}</span><RoleChip role={it.role} />
          <span className={`chip ${BADGE[it.status]}`}>{it.status}</span>
        </div>
      </div>
      <div className="queue-actions">
        {it.status === 'Failed' && it.file && !/larger than 4 MB|Unsupported|empty/.test(it.message) && (
          <button className="btn btn-secondary btn-sm" onClick={() => onRetry(it.id)}>Retry</button>
        )}
        {it.status === 'Queued' && <button className="btn btn-secondary btn-sm" onClick={() => onRemove(it.id)}>Remove</button>}
      </div>
      <div className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${it.name} progress`}>
        <div style={{ width: `${pct}%`, background: it.status === 'Failed' ? '#DC2626' : undefined }} />
      </div>
      {(it.status === 'Failed' || it.status === 'Duplicate') && <div className={`queue-note ${it.status === 'Failed' ? 'bad' : ''}`}>{it.message}</div>}
      {res && it.status === 'Saved' && (
        <div className="queue-note">
          <strong>{res.candidate?.full_name || 'Name not found'}</strong> - score {res.result.weighted_score.toFixed(1)}{' '}
          <RecChip value={res.result.recommendation} />{' '}
          {hintMismatch && <span className="chip chip-amber" title="The CV states a different target role than the one selected">Looks like a {ROLE_NAMES[res.applied_role_hint]} CV</span>}{' '}
          <a href="#scores" onClick={() => onViewScores(it.role)}>View in Scores</a>
        </div>
      )}
    </li>
  )
}

export default function UploadTab({ role, onRole, q, onViewScores }) {
  const { queue, summary } = q
  return (
    <section aria-labelledby="upload-h">
      <div className="card">
        <h2 id="upload-h" style={{ marginBottom: 12 }}>Upload resumes</h2>
        <div className="upload-controls">
          <span id="role-label" style={{ fontWeight: 600 }}>Role for these files</span>
          <div className="segmented" role="group" aria-labelledby="role-label">
            {Object.entries(ROLE_NAMES).map(([code, name]) => (
              <button key={code} aria-pressed={role === code} onClick={() => onRole(code)}>{name}</button>
            ))}
          </div>
        </div>
        <UploadZone onFiles={(files) => q.addFiles(files, role)} />
      </div>
      {queue.length > 0 && (
        <div className="card" aria-live="polite">
          <div className="toolbar" style={{ marginBottom: 8 }}>
            <div className="grow summary-line">
              Processed {summary.processed} of {summary.total} - {summary.saved} saved, {summary.duplicate} duplicate, {summary.failed} failed
            </div>
            {summary.queued > 0 && <button className="btn btn-secondary btn-sm" onClick={q.cancelRemaining}>Cancel remaining</button>}
            {!summary.busy && <button className="btn btn-secondary btn-sm" onClick={q.clear}>Clear list</button>}
          </div>
          <ul className="queue">
            {queue.map((it) => <Row key={it.id} it={it} onRetry={q.retry} onRemove={q.remove} onViewScores={onViewScores} />)}
          </ul>
        </div>
      )}
    </section>
  )
}
