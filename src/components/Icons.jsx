const p = { fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }
export const UploadIcon = ({ size = 40 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M17 8l-5-5-5 5" /><path d="M12 3v12" /></svg>
)
export const FileIcon = ({ size = 40 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...p}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="M9 13h6M9 17h6" /></svg>
)
export const RefreshIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" {...p}><path d="M21 12a9 9 0 1 1-3-6.7L21 8" /><path d="M21 3v5h-5" /></svg>
)
export const CopyIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" {...p}><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
)
export const ChevronIcon = ({ open }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" {...p} style={{ transform: open ? 'rotate(90deg)' : 'none', transition: 'transform .15s' }}><path d="M9 18l6-6-6-6" /></svg>
)
export const TrashIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" {...p}><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" /></svg>
)
