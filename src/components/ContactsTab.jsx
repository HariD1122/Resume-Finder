import { useMemo, useState } from 'react'
import DataToolbar from './DataToolbar.jsx'
import EmptyState from './EmptyState.jsx'
import { CopyIcon } from './Icons.jsx'
import { RoleChip } from './StatusChip.jsx'
import { fmtDate, fmtPhone } from '../utils.js'

const NF = <span className="notfound">Not found</span>

function Copy({ text, label, notify }) {
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); notify('success', `${label} copied`) } catch { notify('error', 'Could not copy to clipboard') }
  }
  return <button className="icon-btn" aria-label={`Copy ${label}`} onClick={copy}><CopyIcon /></button>
}

function SortTh({ k, sort, onSort, children }) {
  return (
    <th scope="col" aria-sort={sort.key === k ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button onClick={() => onSort(k)}>{children}{sort.key === k ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : ''}</button>
    </th>
  )
}

export default function ContactsTab({ contacts, loading, loaded, sync, onRefresh, onReset, onGoUpload, onDownload, notify }) {
  const [q, setQ] = useState('')
  const [role, setRole] = useState('All')
  const [sort, setSort] = useState({ key: 'created_at', dir: 'desc' })

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const f = sort.dir === 'asc' ? 1 : -1
    return contacts
      .filter((c) => (role === 'All' || c.role === role) &&
        (!needle || [c.full_name, c.email, c.phone, c.address].some((v) => (v || '').toLowerCase().includes(needle))))
      .sort((a, b) => {
        const x = (a[sort.key] || '').toString().toLowerCase(), y = (b[sort.key] || '').toString().toLowerCase()
        return (x < y ? -1 : x > y ? 1 : 0) * f
      })
  }, [contacts, q, role, sort])

  const setKey = (key) => setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: key === 'created_at' ? 'desc' : 'asc' }))

  return (
    <section aria-labelledby="contacts-h">
      <div className="toolbar"><h2 id="contacts-h" className="grow">Contacts</h2></div>
      <DataToolbar sync={sync} loading={loading} onRefresh={onRefresh} onReset={onReset} />
      {!loaded ? (
        <div className="card">{[...Array(5)].map((_, i) => <div key={i} className="skeleton" style={{ margin: '14px 0', width: `${90 - i * 8}%` }} />)}</div>
      ) : contacts.length === 0 ? (
        <EmptyState onGoUpload={onGoUpload} />
      ) : (
        <>
          <div className="toolbar">
            <input className="search" type="search" placeholder="Search name, email, phone or address" aria-label="Search contacts" value={q} onChange={(e) => setQ(e.target.value)} />
            <label className="sr-only" htmlFor="role-filter">Filter by role</label>
            <select id="role-filter" className="select" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="All">All roles</option><option value="PM">PM</option><option value="SPM">Sr PM</option>
            </select>
          </div>
          <div className="table-wrap" tabIndex={0} aria-label="Contacts table, scrollable">
            <table>
              <thead>
                <tr>
                  <SortTh sort={sort} onSort={setKey} k="full_name">Name</SortTh><SortTh sort={sort} onSort={setKey} k="role">Role applied</SortTh><SortTh sort={sort} onSort={setKey} k="phone">Phone</SortTh><SortTh sort={sort} onSort={setKey} k="email">Email</SortTh>
                  <SortTh sort={sort} onSort={setKey} k="address">Address</SortTh><th scope="col">Resume</th><SortTh sort={sort} onSort={setKey} k="created_at">Date added</SortTh>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && <tr><td colSpan={7} className="muted">No contacts match this search.</td></tr>}
                {rows.map((c) => (
                  <tr key={c.id}>
                    <td className="cand-name">{c.full_name || NF}</td>
                    <td><RoleChip role={c.role} /></td>
                    <td>{c.phone ? <span className="copyable"><a href={`tel:${c.phone}`}>{fmtPhone(c.phone)}</a><Copy text={c.phone} label="phone" notify={notify} /></span> : NF}</td>
                    <td>{c.email ? <span className="copyable"><a href={`mailto:${c.email}`}>{c.email}</a><Copy text={c.email} label="email" notify={notify} /></span> : NF}</td>
                    <td>{c.address || NF}</td>
                    <td>{c.has_resume ? <button className="btn btn-secondary btn-sm" onClick={() => onDownload(c.id)}>Download</button> : NF}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>{fmtDate(c.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}
