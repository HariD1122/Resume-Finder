const REC = { Shortlist: 'chip-green', Hold: 'chip-amber', Pass: 'chip-red', 'Pass (location)': 'chip-red' }
export function RecChip({ value }) {
  return <span className={`chip ${REC[value] || 'chip-grey'}`}>{value || 'Not found'}</span>
}
const GATE = { OK: 'chip-green', Confirm: 'chip-amber', 'Not relocating': 'chip-red' }
export function GateChip({ value }) {
  return <span className={`chip ${GATE[value] || 'chip-grey'}`}>{value || 'Not found'}</span>
}
export function RoleChip({ role }) {
  return <span className="chip chip-blue">{role === 'SPM' ? 'Sr PM' : 'PM'}</span>
}
