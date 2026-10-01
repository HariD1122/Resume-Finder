import { useCallback, useEffect, useRef, useState } from 'react'
import { uploadResume } from './api/client.js'
import { MAX_BYTES } from './utils.js'

export const CONCURRENCY = 1 // keep at 1-2 to respect Gemini rate limits
const ACTIVE = ['Uploading', 'Reading', 'Extracting', 'Scoring']
const PROGRESS = { Queued: 0, Uploading: 10, Reading: 40, Extracting: 60, Scoring: 80, Saved: 100, Duplicate: 100, Failed: 100 }

const VALID_EXT = /\.(pdf|docx|doc)$/i
let seq = 0

export function useUploadQueue({ onSaved }) {
  const [queue, setQueue] = useState([])
  const running = useRef(0)
  const started = useRef(new Set())
  const timers = useRef({})
  const onSavedRef = useRef(onSaved)
  onSavedRef.current = onSaved

  const patch = useCallback((id, p) => setQueue((q) => q.map((it) => (it.id === id ? { ...it, ...p } : it))), [])

  const addFiles = useCallback((files, role) => {
    const items = Array.from(files).map((file) => {
      const base = { id: `f${++seq}`, file, name: file.name, size: file.size, role, status: 'Queued', progress: 0, message: '' }
      if (!VALID_EXT.test(file.name)) return { ...base, status: 'Failed', message: 'Unsupported file type. Use PDF or DOCX.' }
      if (file.size === 0) return { ...base, status: 'Failed', message: 'The file is empty.' }
      if (file.size > MAX_BYTES) return { ...base, status: 'Failed', message: 'File is larger than 4 MB. Please compress it.' }
      return base
    })
    setQueue((q) => [...q, ...items])
  }, [])

  const run = useCallback(async (item) => {
    const clear = () => { (timers.current[item.id] || []).forEach(clearTimeout); delete timers.current[item.id] }
    patch(item.id, { status: 'Uploading', progress: 0 })
    try {
      const res = await uploadResume(item.file, item.role, {
        onProgress: (f) => patch(item.id, { progress: Math.round(f * 100) }),
        onUploaded: () => {
          patch(item.id, { status: 'Reading' })
          timers.current[item.id] = [
            setTimeout(() => patch(item.id, { status: 'Extracting' }), 1500),
            setTimeout(() => patch(item.id, { status: 'Scoring' }), 5000),
          ]
        },
      })
      clear()
      if (res.status === 'duplicate') {
        patch(item.id, { status: 'Duplicate', message: res.message || 'Already added for this role.' })
      } else {
        patch(item.id, { status: 'Saved', result: res })
        onSavedRef.current?.(res, item)
      }
    } catch (e) {
      clear()
      patch(item.id, { status: 'Failed', message: e.message || 'Upload failed.' })
    } finally {
      running.current -= 1
      setQueue((q) => [...q]) // wake the scheduler
    }
  }, [patch])

  useEffect(() => {
    if (running.current >= CONCURRENCY) return
    const next = queue.find((q) => q.status === 'Queued' && !started.current.has(q.id))
    if (!next) return
    started.current.add(next.id)
    running.current += 1
    run(next)
  }, [queue, run])

  useEffect(() => {
    const busy = queue.some((q) => q.status === 'Queued' || ACTIVE.includes(q.status))
    if (!busy) return undefined
    const h = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', h)
    return () => window.removeEventListener('beforeunload', h)
  }, [queue])

  const retry = useCallback((id) => {
    started.current.delete(id)
    patch(id, { status: 'Queued', message: '', progress: 0 })
  }, [patch])
  const remove = useCallback((id) => setQueue((q) => q.filter((it) => it.id !== id || it.status !== 'Queued')), [])
  const cancelRemaining = useCallback(() => setQueue((q) => q.filter((it) => it.status !== 'Queued')), [])
  const clear = useCallback(() => { setQueue([]) }, [])

  const processed = queue.filter((q) => ['Saved', 'Duplicate', 'Failed'].includes(q.status))
  const summary = {
    total: queue.length,
    processed: processed.length,
    saved: queue.filter((q) => q.status === 'Saved').length,
    duplicate: queue.filter((q) => q.status === 'Duplicate').length,
    failed: queue.filter((q) => q.status === 'Failed').length,
    busy: queue.some((q) => q.status === 'Queued' || ACTIVE.includes(q.status)),
    queued: queue.filter((q) => q.status === 'Queued').length,
  }
  return { queue, addFiles, retry, remove, cancelRemaining, clear, summary, PROGRESS }
}
