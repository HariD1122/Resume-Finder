const IST = 'Asia/Kolkata'

export const fmtTime = (d = new Date()) =>
  new Intl.DateTimeFormat('en-GB', { timeZone: IST, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(d)

export const fmtDate = (iso) => {
  if (!iso) return 'Not found'
  return new Intl.DateTimeFormat('en-IN', { timeZone: IST, day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(iso)) + ' IST'
}

export const fmtSize = (n) => (n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`)

// Indian numbers with a known country code display as +91 98765 43210; anything else is shown as found
export const fmtPhone = (p) => {
  if (!p) return null
  const digits = p.replace(/\D/g, '')
  if (p.startsWith('+91') && digits.length === 12) return `+91 ${digits.slice(2, 7)} ${digits.slice(7)}`
  return p
}

export const MAX_BYTES = 4 * 1024 * 1024
export const ROLE_NAMES = { PM: 'Product Manager', SPM: 'Senior Product Manager' }
export const ROLE_SHORT = { PM: 'PM', SPM: 'Sr PM' }
