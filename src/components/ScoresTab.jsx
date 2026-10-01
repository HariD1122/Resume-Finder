import { Fragment, useMemo, useState } from 'react'
import DataToolbar from './DataToolbar.jsx'
import EmptyState from './EmptyState.jsx'
import { ChevronIcon } from './Icons.jsx'
import { GateChip, RecChip } from './StatusChip.jsx'
import { ROLE_NAMES } from '../utils.js'

const REC_ORDER = { Shortlist: 0, Hold: 1, Pass: 2, 'Pass (location)': 3 }
const GATE_ORDER = { OK: 0, Confirm: 1, 'Not relocating': 2 }
const FILTERS = ['All', 'Shortlist', 'Hold', 'Pass']

function sortValue(c, key) {
  switch (key) {
    case 'rank': return c.rank
    case 'name': return (c.full_name || '').toLowerCase()
    case 'years': return c.pm_years ?? -1
    case 'weighted': return c.weighted_score
    case 'gate': return GATE_ORDER[c.location_gate] ?? 9
    case 'rec': return REC_ORDER[c.recommendation] ?? 9
    default: return c.scores?.[key]?.score ?? -1
  }
}

const tint = (n) => ({ background: `rgba(59,130,246,${(n / 5) * 0.42})` })

function Detail({ c, reqs, onDownload }) {
  return (
    <div className="detail">
      <p>{c.summary || <span className="notfound">No summary available</span>}</p>
      <div className="contact-line">
        <span>Email: {c.email ? <a href={`mailto:${c.email}`}>{c.email}</a> : <span className="notfound">Not found</span>}</span>
        <span>Phone: {c.phone ? <a href={`tel:${c.phone}`}>{c.phone}</a> : <span className="notfound">Not found</span>}</span>
        {c.file_name && <button className="btn btn-secondary btn-sm" onClick={() => onDownload(c.id)}>Download resume</button>}
      </div>
      <h4>Why this score</h4>
      <ul className="req-list">
        {reqs.map((r) => {
          const s = c.scores?.[r.id]
          const noEv = !s || !s.evidence || s.evidence === 'No evidence found' || s.evidence === 'none'
          return (
            <li key={r.id} className="req-item">
              <span><strong>{r.label}</strong> <span className="muted">(weight {r.weight})</span></span>
              <span className="req-score">{s ? s.score : 0} / 5</span>
              <span className="q">{r.kind === 'computed' ? 'Computed by the system' : noEv ? 'No evidence found' : `“${s.evidence}”`}</span>
              <span className="r">{s?.reason || ''}</span>
            </li>
          )
        })}
      </ul>
      {c.probe_questions?.length > 0 && (
        <>
          <h4>Suggested things to probe</h4>
          <ul className="probe-list">{c.probe_questions.map((p, i) => <li key={i}>{p}</li>)}</ul>
        </>
      )}
      {c.extraction_notes && <p className="muted" style={{ marginTop: 12 }}>Notes: {c.extraction_notes}</p>}
    </div>
  )
}

function SortTh({ k, sort, onSort, children, title, className }) {
  const aria = sort.key === k ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'
  return (
    <th scope="col" aria-sort={aria} className={className} title={title}>
      <button onClick={() => onSort(k)}>{children}{sort.key === k ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : ''}</button>
    </th>
  )
}

export default function ScoresTab({ role, onRole, cfg, data, loading, loaded, sync, onRefresh, onReset, onGoUpload, onDownload }) {
  const [sort, setSort] = useState({ key: 'weighted', dir: 'desc' })
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState('All')
  const [open, setOpen] = useState(() => new Set())

  const reqs = cfg?.roles?.[role]?.requirements || []
  const all = data?.[role]?.candidates || []

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    let r = all.filter((c) => {
      if (filter === 'Pass' && !c.recommendation.startsWith('Pass')) return false
      if (filter !== 'All' && filter !== 'Pass' && c.recommendation !== filter) return false
      return !needle || [c.full_name, c.current_company, c.current_title].some((v) => (v || '').toLowerCase().includes(needle))
    })
    const f = sort.dir === 'asc' ? 1 : -1
    r = [...r].sort((a, b) => {
      const x = sortValue(a, sort.key), y = sortValue(b, sort.key)
      return (x < y ? -1 : x > y ? 1 : a.rank - b.rank) * f
    })
    return r
  }, [all, q, filter, sort])

  const stat = {
    n: all.length,
    sl: all.filter((c) => c.recommendation === 'Shortlist').length,
    hold: all.filter((c) => c.recommendation === 'Hold').length,
    pass: all.filter((c) => c.recommendation.startsWith('Pass')).length,
    avg: all.length ? (all.reduce((s, c) => s + c.weighted_score, 0) / all.length).toFixed(1) : '0.0',
  }

  const setSortKey = (key) => setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: key === 'name' || key === 'rank' || key === 'gate' || key === 'rec' ? 'asc' : 'desc' }))
  const toggle = (id) => setOpen((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })
  const colCount = 3 + reqs.length + 3

  return (
    <section aria-labelledby="scores-h">
      <div className="toolbar">
        <h2 id="scores-h" className="grow">Scores</h2>
        <div className="segmented" role="group" aria-label="Role">
          {Object.entries(ROLE_NAMES).map(([code, name]) => (
            <button key={code} aria-pressed={role === code} onClick={() => onRole(code)}>{name}</button>
          ))}
        </div>
      </div>
      <DataToolbar sync={sync} loading={loading} onRefresh={onRefresh} onReset={onReset} />

      {!loaded ? (
        <div className="card">{[...Array(5)].map((_, i) => <div key={i} className="skeleton" style={{ margin: '14px 0', width: `${90 - i * 8}%` }} />)}</div>
      ) : all.length === 0 ? (
        <EmptyState onGoUpload={onGoUpload} />
      ) : (
        <>
          <div className="stats">
            <div className="stat"><b>{stat.n}</b><span>Candidates</span></div>
            <div className="stat"><b>{stat.sl}</b><span>Shortlist</span></div>
            <div className="stat"><b>{stat.hold}</b><span>Hold</span></div>
            <div className="stat"><b>{stat.pass}</b><span>Pass</span></div>
            <div className="stat"><b>{stat.avg}</b><span>Average score</span></div>
          </div>
          <div className="toolbar">
            <input className="search" type="search" placeholder="Search name, company or title" aria-label="Search candidates" value={q} onChange={(e) => setQ(e.target.value)} />
            <div className="filter-chips" role="group" aria-label="Filter by recommendation">
              {FILTERS.map((f) => <button key={f} aria-pressed={filter === f} onClick={() => setFilter(f)}>{f}</button>)}
            </div>
          </div>
          <div className="table-wrap" tabIndex={0} aria-label="Candidate scores table, scrollable">
            <table>
              <thead>
                <tr>
                  <SortTh sort={sort} onSort={setSortKey} k="rank" className="sticky-1">Rank</SortTh>
                  <SortTh sort={sort} onSort={setSortKey} k="name" className="sticky-2">Candidate</SortTh>
                  <SortTh sort={sort} onSort={setSortKey} k="years" className="num">PM years</SortTh>
                  {reqs.map((r) => (
                    <SortTh sort={sort} onSort={setSortKey} key={r.id} k={r.id} className="num" title={`${r.label}. Top score: ${r.focus}`}>{r.short} ({r.weight})</SortTh>
                  ))}
                  <SortTh sort={sort} onSort={setSortKey} k="weighted" className="num">Weighted (0-100)</SortTh>
                  <SortTh sort={sort} onSort={setSortKey} k="gate">Location gate</SortTh>
                  <SortTh sort={sort} onSort={setSortKey} k="rec">Recommendation</SortTh>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && <tr><td colSpan={colCount} className="muted">No candidates match this search or filter.</td></tr>}
                {rows.map((c) => (
                  <Fragment key={c.id}>
                    <tr className="row-click" onClick={() => toggle(c.id)}>
                      <td className="sticky-1 num"><b>{c.rank}</b></td>
                      <td className="sticky-2">
                        <button className="expand-btn" aria-expanded={open.has(c.id)} aria-label={`${open.has(c.id) ? 'Collapse' : 'Expand'} details for ${c.full_name || 'candidate'}`}
                          onClick={(e) => { e.stopPropagation(); toggle(c.id) }}>
                          <ChevronIcon open={open.has(c.id)} />
                        </button>{' '}
                        <span className="cand-name">{c.full_name || <span className="notfound">Name not found</span>}</span>
                        <div className="cand-sub">{[c.current_title, c.current_company].filter(Boolean).join(' at ') || 'Not found'}</div>
                      </td>
                      <td className="num">{c.pm_years ?? <span className="notfound">Not found</span>}</td>
                      {reqs.map((r) => {
                        const n = c.scores?.[r.id]?.score ?? 0
                        return <td key={r.id} className="score-cell" style={tint(n)}>{n}</td>
                      })}
                      <td className="weighted">{c.weighted_score.toFixed(1)}</td>
                      <td><GateChip value={c.location_gate} /></td>
                      <td><RecChip value={c.recommendation} /></td>
                    </tr>
                    {open.has(c.id) && (
                      <tr className="detail-row"><td colSpan={colCount}><Detail c={c} reqs={reqs} onDownload={onDownload} /></td></tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}
