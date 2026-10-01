import { RefreshIcon, TrashIcon } from './Icons.jsx'

// Shared Refresh / Reset controls and the sync line for the Scores and Contacts tabs
export default function DataToolbar({ sync, loading, onRefresh, onReset }) {
  return (
    <div className="toolbar">
      <div className="grow sync-line" aria-live="polite">
        {sync ? (
          <>
            Last updated {sync.time} IST - {sync.count} candidate{sync.count === 1 ? '' : 's'} -{' '}
            <span className={sync.inSync ? 'ok' : 'bad'}>{sync.inSync ? 'In sync' : 'Out of sync - refreshed again'}</span>
          </>
        ) : 'Not loaded yet'}
      </div>
      <button className="btn btn-secondary" onClick={onRefresh} disabled={loading}>
        {loading ? <span className="spinner" /> : <RefreshIcon />} Refresh
      </button>
      <button className="btn btn-danger" onClick={onReset} disabled={loading}><TrashIcon /> Reset</button>
    </div>
  )
}
