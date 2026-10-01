import { useRef } from 'react'

export const TAB_IDS = ['upload', 'scores', 'contacts']
const LABELS = { upload: 'Upload', scores: 'Scores', contacts: 'Contacts' }

export default function Tabs({ active, onChange, counts }) {
  const refs = useRef({})
  const onKey = (e) => {
    const i = TAB_IDS.indexOf(active)
    let n = null
    if (e.key === 'ArrowRight') n = TAB_IDS[(i + 1) % 3]
    if (e.key === 'ArrowLeft') n = TAB_IDS[(i + 2) % 3]
    if (e.key === 'Home') n = TAB_IDS[0]
    if (e.key === 'End') n = TAB_IDS[2]
    if (n) { e.preventDefault(); onChange(n); refs.current[n]?.focus() }
  }
  return (
    <div className="tabs" role="tablist" aria-label="Sections" onKeyDown={onKey}>
      {TAB_IDS.map((id) => (
        <button key={id} ref={(el) => (refs.current[id] = el)} role="tab" id={`tab-${id}`} aria-controls={`panel-${id}`}
          aria-selected={active === id} tabIndex={active === id ? 0 : -1} className="tab" onClick={() => onChange(id)}>
          {LABELS[id]}
          {counts[id] > 0 && <span className="badge" aria-label={`${counts[id]} items`}>{counts[id]}</span>}
        </button>
      ))}
    </div>
  )
}
