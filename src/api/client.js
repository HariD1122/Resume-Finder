// Thin fetch helpers. All calls are relative /api paths; no secrets ever live in the browser.
const CODE_KEY = 'rf_access_code'

export const getAccessCode = () => {
  try { return sessionStorage.getItem(CODE_KEY) || '' } catch { return '' }
}
export const setAccessCode = (c) => {
  try { c ? sessionStorage.setItem(CODE_KEY, c) : sessionStorage.removeItem(CODE_KEY) } catch { /* ignore */ }
}

const headers = () => {
  const c = getAccessCode()
  return c ? { 'X-Access-Code': c } : {}
}

export class ApiError extends Error {
  constructor(message, status, code, body) {
    super(message)
    this.status = status
    this.code = code
    this.body = body
  }
}

async function request(path, opts = {}) {
  let res
  try {
    res = await fetch(path, { ...opts, headers: { ...headers(), ...(opts.headers || {}) } })
  } catch {
    throw new ApiError('Network error. Check your connection and retry.', 0, 'network')
  }
  let body = null
  try { body = await res.json() } catch { /* non-JSON */ }
  if (!res.ok) {
    if (res.status === 401) window.dispatchEvent(new Event('rf-unauthorized'))
    throw new ApiError(body?.error?.message || body?.message || `Request failed (${res.status})`, res.status, body?.error?.code, body)
  }
  return body
}

const jsonOpts = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  health: () => request('/api/health'),
  authCheck: () => request('/api/auth-check'),
  config: () => request('/api/config'),
  candidates: (role) => request(`/api/candidates?role=${role}`),
  contacts: () => request('/api/contacts'),
  resumeUrl: (id) => request(`/api/resume-url?candidate_id=${encodeURIComponent(id)}`),
  reset: () => request('/api/reset', { method: 'POST' }),
  emails: () => request('/api/emails'),
  editEmail: (id, { subject, body }) => request(`/api/emails/${encodeURIComponent(id)}`, jsonOpts('PUT', { subject, body })),
  setInterviewDate: (interview_at) => request('/api/emails/interview-date', jsonOpts('POST', { interview_at })),
  sendEmail: (id, version) => request(`/api/emails/${encodeURIComponent(id)}/send`, jsonOpts('POST', { confirm: true, version })),
}

// XHR so we get real upload progress. onUploaded fires when the bytes have been sent.
export function uploadResume(file, role, { onProgress, onUploaded } = {}) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/upload')
    const c = getAccessCode()
    if (c) xhr.setRequestHeader('X-Access-Code', c)
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total)
    xhr.upload.onload = () => onUploaded?.()
    xhr.onerror = () => reject(new ApiError('Network error during upload. Please retry.', 0, 'network'))
    xhr.onload = () => {
      let body = null
      try { body = JSON.parse(xhr.responseText) } catch { /* ignore */ }
      if (xhr.status === 200) return resolve({ status: 'saved', ...body })
      if (xhr.status === 409) return resolve({ status: 'duplicate', ...body })
      if (xhr.status === 401) window.dispatchEvent(new Event('rf-unauthorized'))
      reject(new ApiError(body?.error?.message || `Upload failed (${xhr.status})`, xhr.status, body?.error?.code, body))
    }
    const fd = new FormData()
    fd.append('file', file)
    fd.append('role', role)
    xhr.send(fd)
  })
}
