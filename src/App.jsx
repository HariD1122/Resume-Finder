import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api/client.js'
import AccessGate from './components/AccessGate.jsx'
import ConfirmModal from './components/ConfirmModal.jsx'
import ContactsTab from './components/ContactsTab.jsx'
import Header from './components/Header.jsx'
import { TAB_IDS } from './components/Tabs.jsx'
import Toasts from './components/Toast.jsx'
import ScoresTab from './components/ScoresTab.jsx'
import UploadTab from './components/UploadTab.jsx'
import { useUploadQueue } from './useUploadQueue.js'
import { fmtTime } from './utils.js'

const tabFromHash = () => {
  const h = window.location.hash.replace('#', '')
  return TAB_IDS.includes(h) ? h : 'upload'
}
const norm = (v) => v || null

export default function App() {
  const [tab, setTab] = useState(tabFromHash)
  const [locked, setLocked] = useState(false)
  const [cfg, setCfg] = useState(null)
  const [health, setHealth] = useState(null)
  const [data, setData] = useState({ PM: null, SPM: null })
  const [contacts, setContacts] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [sync, setSync] = useState(null)
  const [uploadRole, setUploadRole] = useState('PM')
  const [scoreRole, setScoreRole] = useState('PM')
  const [toasts, setToasts] = useState([])
  const [resetOpen, setResetOpen] = useState(false)
  const [resetting, setResetting] = useState(false)
  const lastRefresh = useRef(0)

  const goTab = useCallback((id) => { window.location.hash = id; setTab(id) }, [])
  useEffect(() => {
    const on = () => setTab(tabFromHash())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])

  const notify = useCallback((type, message, action) => {
    setToasts((t) => [...t, { id: `${Date.now()}${Math.random()}`, type, message, action }])
  }, [])
  const closeToast = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), [])

  const fetchAll = useCallback(async () => {
    const [pm, spm, ct] = await Promise.all([api.candidates('PM'), api.candidates('SPM'), api.contacts()])
    setData({ PM: pm, SPM: spm })
    setContacts(ct.contacts)
    return { pm, spm }
  }, [])

  const refresh = useCallback(async ({ quiet = false } = {}) => {
    setLoading(true)
    try {
      let { pm, spm } = await fetchAll()
      const h = await api.health()
      setHealth(h)
      let inSync = true
      if (h.counts) {
        const same = (r, x) => r.count === h.counts[x] && norm(r.latest_updated_at) === norm(h.latest_by_role?.[x])
        if (!same(pm, 'PM') || !same(spm, 'SPM')) {
          inSync = false
          await fetchAll() // one more fetch, per spec
        }
      }
      setSync({ time: fmtTime(), count: pm.count + spm.count, inSync })
      setLoaded(true)
      lastRefresh.current = Date.now()
    } catch (e) {
      setLoaded(true)
      if (!quiet) notify('error', e.message || 'Could not refresh.')
      setHealth((h) => h && { ...h, error: true })
    } finally {
      setLoading(false)
    }
  }, [fetchAll, notify])

  const queue = useUploadQueue({
    onSaved: (res) => {
      notify('success', `Saved ${res.candidate?.full_name || 'candidate'}: ${res.result.recommendation} (${res.result.weighted_score.toFixed(1)})`)
      fetchAll().then(({ pm, spm }) => setSync({ time: fmtTime(), count: pm.count + spm.count, inSync: true })).catch(() => {})
    },
  })

  // Boot: check access, then load config and data
  const boot = useCallback(async () => {
    try {
      const h = await api.health()
      setHealth(h)
      if (h.access_required && h.supabase === undefined) { setLocked(true); return }
      setLocked(false)
      const [c] = await Promise.all([api.config(), refresh({ quiet: true })])
      setCfg(c)
    } catch {
      setHealth({ error: true })
      setLoaded(true)
    }
  }, [refresh])

  useEffect(() => { boot() }, [boot])
  useEffect(() => {
    const on = () => setLocked(true)
    window.addEventListener('rf-unauthorized', on)
    return () => window.removeEventListener('rf-unauthorized', on)
  }, [])

  // Health indicator every 60 s; refresh when the tab regains focus (at most every 30 s)
  useEffect(() => {
    if (locked) return undefined
    const id = setInterval(() => api.health().then(setHealth).catch(() => setHealth({ error: true })), 60000)
    const onFocus = () => { if (document.visibilityState === 'visible' && Date.now() - lastRefresh.current > 30000) refresh({ quiet: true }) }
    document.addEventListener('visibilitychange', onFocus)
    window.addEventListener('focus', onFocus)
    return () => { clearInterval(id); document.removeEventListener('visibilitychange', onFocus); window.removeEventListener('focus', onFocus) }
  }, [locked, refresh])

  const download = useCallback(async (id) => {
    try {
      const { url } = await api.resumeUrl(id) // signed on click, expires in 10 minutes
      window.open(url, '_blank', 'noopener')
    } catch (e) { notify('error', e.message || 'Could not open the resume.') }
  }, [notify])

  const doReset = async () => {
    setResetting(true)
    try {
      await api.reset()
      queue.clear()
      setData({ PM: { count: 0, candidates: [] }, SPM: { count: 0, candidates: [] } })
      setContacts([])
      setSync({ time: fmtTime(), count: 0, inSync: true })
      setResetOpen(false)
      notify('success', 'All data cleared. You can start again from the Upload tab.', { label: 'Go to Upload', onClick: () => goTab('upload') })
    } catch (e) {
      notify('error', e.message || 'Reset failed. Nothing may have been deleted; please refresh and try again.')
    } finally { setResetting(false) }
  }

  if (locked) return <AccessGate onUnlocked={() => { setLocked(false); boot() }} />

  const counts = { upload: 0, scores: (data.PM?.count || 0) + (data.SPM?.count || 0), contacts: contacts.length }
  const common = { loading, loaded, sync, onRefresh: () => refresh(), onReset: () => setResetOpen(true), onGoUpload: () => goTab('upload'), onDownload: download }

  return (
    <div className="app">
      <Header active={tab} onChange={goTab} counts={counts} health={health} />
      <main className="main" id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {tab === 'upload' && (
          <UploadTab role={uploadRole} onRole={setUploadRole} q={queue}
            onViewScores={(r) => { setScoreRole(r); goTab('scores') }} />
        )}
        {tab === 'scores' && <ScoresTab role={scoreRole} onRole={setScoreRole} cfg={cfg} data={data} {...common} />}
        {tab === 'contacts' && <ContactsTab contacts={contacts} notify={notify} {...common} />}
      </main>
      <footer className="footer">Recommendations only. A person makes every hiring decision.</footer>
      <Toasts toasts={toasts} onClose={closeToast} />
      <ConfirmModal open={resetOpen} busy={resetting} onCancel={() => setResetOpen(false)} onConfirm={doReset} />
    </div>
  )
}
