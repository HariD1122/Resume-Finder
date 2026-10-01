import Tabs from './Tabs.jsx'

const TIP = {
  ok: 'Backend, Supabase and Gemini are reachable',
  warn: 'Degraded: part of the system is unreachable',
  down: 'Backend is not reachable',
  unk: 'Checking connection',
}

export default function Header({ active, onChange, counts, health }) {
  const state = !health ? 'unk' : health.error ? 'down' : health.status === 'ok' ? 'ok' : 'warn'
  let tip = TIP[state]
  if (state === 'warn') tip = `Degraded: Supabase ${health.supabase ? 'OK' : 'down'}, Gemini ${health.gemini ? 'OK' : 'down'}`
  return (
    <header className="header">
      <div className="header-inner">
        <div className="brand">
          <div className="logo" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
          </div>
          <div>
            <h1>
              Resume Finder
              <span className={`status-dot dot-${state}`} role="img" aria-label={tip} title={tip} />
            </h1>
            <small>Hiring shortlist assistant</small>
          </div>
        </div>
        <Tabs active={active} onChange={onChange} counts={counts} />
      </div>
    </header>
  )
}
